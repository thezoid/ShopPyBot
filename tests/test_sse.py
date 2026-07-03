"""test_sse.py: Phase 27 SSE infrastructure tests.

These drive the async SSE generator (`web.routes.sse._event_generator`) and the
producer (`web.sse_hub._poll_loop`) DIRECTLY via asyncio, rather than streaming an
infinite generator through starlette's TestClient. starlette's in-process TestClient
transport buffers the entire response body before returning, so streaming a
never-ending SSE generator over it deadlocks. Driving the generator directly is the
clean, harness-agnostic way to assert the streaming contract — there is no
test-detection logic in production code.

A single TestClient test (no streaming) covers lifespan + route registration.
"""
import asyncio
import re

import pytest

pytest.importorskip("fastapi")

from unittest.mock import MagicMock

from fastapi.testclient import TestClient


CRED_PATTERNS = ["password", "token", "key=", "cvv"]


class _FakeRequest:
    """Minimal async request stub for _event_generator.

    is_disconnected() returns False for the first `disconnect_after` checks, then
    True — letting a test make the generator self-terminate via the disconnect path.
    With disconnect_after=None it never disconnects (the test bounds via max_frames).
    """

    def __init__(self, disconnect_after=None):
        self._checks = 0
        self._disconnect_after = disconnect_after

    async def is_disconnected(self):
        self._checks += 1
        if self._disconnect_after is not None and self._checks > self._disconnect_after:
            return True
        return False


@pytest.fixture
def mock_svc():
    svc = MagicMock()
    svc.get_status.return_value = {"running": False, "uptime_secs": 0.0, "plugins": {}}
    svc.list_items.return_value = []
    return svc


def _drive(gen, n):
    """Run async generator `gen`, collect up to n frames, then aclose(). Returns list[str]."""
    async def run():
        frames = []
        try:
            async for frame in gen:
                frames.append(frame)
                if len(frames) >= n:
                    break
        finally:
            await gen.aclose()
        return frames

    return asyncio.run(run())


# ---------------------------------------------------------------------------
# Criterion 4 (retry line) + criterion 1 (keepalive on idle)
# ---------------------------------------------------------------------------


def test_sse_retry_line_and_keepalive():
    """Stream opens with 'retry: 3000'; an idle queue yields ': keep-alive' comments."""
    from web.routes.sse import _event_generator
    from web.sse_hub import SseHub

    hub = SseHub()
    gen = _event_generator(_FakeRequest(), hub, keepalive_secs=0.01, max_frames=3)
    frames = _drive(gen, 3)
    combined = "".join(frames)

    assert combined.startswith("retry: 3000"), f"stream did not open with retry: {combined!r}"
    assert ": keep-alive" in combined, f"no keepalive comment on idle: {combined!r}"
    assert len(hub._queues) == 0, "generator finally did not unsubscribe the queue"


# ---------------------------------------------------------------------------
# Criterion 1 (data frame) — a broadcast status frame reaches the stream
# ---------------------------------------------------------------------------


def test_sse_status_frame_delivered():
    """A broadcast 'status' event is delivered to the connected client as a named frame."""
    from web.routes.sse import _event_generator
    from web.sse_hub import SseHub

    hub = SseHub()

    async def run():
        gen = _event_generator(_FakeRequest(), hub, keepalive_secs=5.0, max_frames=2)
        first = await gen.__anext__()  # retry frame; generator has now subscribed
        hub.broadcast("status", {"running": True, "uptime_secs": 1.5, "plugins": {}})
        second = await gen.__anext__()  # the status frame
        await gen.aclose()
        return first, second

    first, second = asyncio.run(run())
    assert first.startswith("retry: 3000")
    assert "event: status" in second, f"not a named status frame: {second!r}"
    assert '"running": true' in second, f"status payload missing running flag: {second!r}"


# ---------------------------------------------------------------------------
# Criterion 3 (bot start/stop reflected) — real _poll_loop is the producer
# ---------------------------------------------------------------------------


def test_poll_loop_reflects_bot_running_flip(monkeypatch):
    """The real _poll_loop polls get_status and broadcasts; a running=False->True flip reaches the stream."""
    from web.routes.sse import _event_generator
    from web.sse_hub import SseHub, _poll_loop
    import web.sse_hub as hubmod

    # Isolate this assertion to STATUS frames: stub the log tail so real log lines
    # from the test session don't flood the stream ahead of the running-flip status.
    monkeypatch.setattr(hubmod, "tail_log_lines", lambda cursor: ([], cursor))

    hub = SseHub()
    svc = MagicMock()
    calls = [0]

    def status():
        calls[0] += 1
        return {"running": calls[0] > 1, "uptime_secs": 0.0, "plugins": {}}

    svc.get_status.side_effect = status

    async def run():
        gen = _event_generator(_FakeRequest(), hub, keepalive_secs=5.0, max_frames=6)
        await gen.__anext__()  # retry; subscribe before the producer starts
        task = asyncio.create_task(_poll_loop(hub, svc, poll_interval=0.01))
        frames = []
        try:
            for _ in range(4):
                frames.append(await asyncio.wait_for(gen.__anext__(), timeout=2.0))
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            await gen.aclose()
        return frames

    combined = "".join(asyncio.run(run()))
    assert "event: status" in combined
    assert '"running": true' in combined, f"running flip not reflected in stream: {combined!r}"


# ---------------------------------------------------------------------------
# Criterion 2 (disconnect cleanup) — finally unsubscribes; hub left empty
# ---------------------------------------------------------------------------


def test_sse_disconnect_cleans_hub():
    """When the client disconnects, the generator's finally unsubscribes, leaving the hub empty."""
    from web.routes.sse import _event_generator
    from web.sse_hub import SseHub

    hub = SseHub()
    # disconnect_after=1 -> the loop breaks on the 2nd is_disconnected() check.
    gen = _event_generator(_FakeRequest(disconnect_after=1), hub, keepalive_secs=0.01, max_frames=None)
    _drive(gen, 50)  # generator self-terminates via the disconnect path well before 50
    assert len(hub._queues) == 0, "disconnect did not clean up the hub queue"


# ---------------------------------------------------------------------------
# SSE-03 carryover — no credential-pattern strings in delivered frames
# ---------------------------------------------------------------------------


def test_sse_no_credential_patterns():
    """A status frame carrying a scrubbed last_error (class name only) leaks no credentials."""
    from web.routes.sse import _event_generator
    from web.sse_hub import SseHub

    hub = SseHub()

    async def run():
        gen = _event_generator(_FakeRequest(), hub, keepalive_secs=5.0, max_frames=2)
        await gen.__anext__()  # retry; subscribe
        hub.broadcast(
            "status",
            {
                "running": False,
                "uptime_secs": 0.0,
                "plugins": {"Amazon": {"last_error": "ConnectionError", "consecutive_errors": 1}},
            },
        )
        frame = await gen.__anext__()
        await gen.aclose()
        return frame

    frame = asyncio.run(run())
    low = frame.lower()
    for pattern in CRED_PATTERNS:
        assert pattern not in low, f"credential pattern {pattern!r} in SSE frame: {frame!r}"
    email_re = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
    assert not email_re.search(frame), f"email-like pattern in SSE frame: {frame!r}"


# ---------------------------------------------------------------------------
# AF-02 — raw last_heartbeat must never reach the SSE "status" frame
# ---------------------------------------------------------------------------


def test_sse_status_frame_excludes_last_heartbeat():
    """A get_snapshot()-shaped status broadcast never leaks the raw last_heartbeat float."""
    from web.routes.sse import _event_generator
    from web.sse_hub import SseHub

    hub = SseHub()

    async def run():
        gen = _event_generator(_FakeRequest(), hub, keepalive_secs=5.0, max_frames=2)
        await gen.__anext__()  # retry; subscribe
        hub.broadcast(
            "status",
            {
                "running": True,
                "uptime_secs": 12.0,
                "plugins": {
                    "Amazon": {
                        "status": "running",
                        "consecutive_errors": 0,
                        "items_checked": 3,
                        "orders_confirmed": 0,
                        "last_error": None,
                        "heartbeat_age_secs": 5.3,
                    }
                },
            },
        )
        frame = await gen.__anext__()
        await gen.aclose()
        return frame

    frame = asyncio.run(run())
    assert "last_heartbeat" not in frame, f"raw last_heartbeat leaked into SSE frame: {frame!r}"
    assert "heartbeat_age_secs" in frame, f"heartbeat_age_secs missing from SSE frame: {frame!r}"


# ---------------------------------------------------------------------------
# Lifespan + route registration (TestClient, NO streaming)
# ---------------------------------------------------------------------------


def test_lifespan_creates_hub_and_registers_route(mock_svc):
    """create_app's lifespan builds app.state.sse_hub and registers GET /api/events."""
    from web import create_app

    with TestClient(create_app(mock_svc)) as client:
        assert getattr(client.app.state, "sse_hub", None) is not None, "lifespan did not create sse_hub"
        paths = {getattr(r, "path", None) for r in client.app.routes}
        assert "/api/events" in paths, f"/api/events not registered; routes={sorted(p for p in paths if p)}"
