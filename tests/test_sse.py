"""test_sse.py: Wave 0 RED spike for Phase 27 SSE infrastructure.

Six isolation tests asserting the exact observable contract for /api/events.
Every test FAILS on missing implementation (ImportError / AttributeError / 404) --
NOT on collection or syntax errors.

A2 resolution: httpx iter_text() may chunk a single SSE frame across multiple reads.
All frame assertions join the first N chunks via "".join(chunks[:N]) instead of
indexing a single chunk, making them robust to chunking variability.

Lifespan note: the existing shared `client` fixture in test_web_dashboard.py does NOT
run the lifespan, so app.state.sse_hub is never initialized there. Each SSE test here
opens its own `with TestClient(create_app(mock_svc)) as client:` block so the lifespan
runs and SseHub is available. No shared client fixture is defined in this file.
"""
import pytest
pytest.importorskip("fastapi")

import re
from unittest.mock import MagicMock

from fastapi.testclient import TestClient


CRED_PATTERNS = ["password", "token", "key=", "cvv"]

# Number of chunks to collect per stream read before asserting.
# Joining the first N chunks handles httpx chunking variability (A2 resolution).
_CHUNK_WINDOW = 8


@pytest.fixture
def mock_svc():
    svc = MagicMock()
    svc.get_status.return_value = {"running": False, "uptime_secs": 0.0, "plugins": {}}
    svc.list_items.return_value = []
    return svc


# ---------------------------------------------------------------------------
# Helper: read up to N chunks from a streaming response context
# ---------------------------------------------------------------------------


def _collect_chunks(resp, n=_CHUNK_WINDOW):
    """Collect up to n text chunks from a streaming SSE response."""
    chunks = []
    for chunk in resp.iter_text():
        chunks.append(chunk)
        if len(chunks) >= n:
            break
    return chunks


# ---------------------------------------------------------------------------
# Test 1: retry line on stream open (criterion 4)
# ---------------------------------------------------------------------------


def test_sse_retry_line_on_open(mock_svc):
    """Stream opens with 'retry: 3000' directive before any other frame (SSE-02 criterion 4)."""
    from web import create_app
    import web.sse_hub as _sse_hub_mod

    _sse_hub_mod._POLL_INTERVAL_SECS = 0.05
    _sse_hub_mod._KEEPALIVE_SECS = 60.0

    try:
        with TestClient(create_app(mock_svc)) as client:
            with client.stream("GET", "/api/events") as resp:
                resp.raise_for_status()
                chunks = _collect_chunks(resp, n=_CHUNK_WINDOW)
                combined = "".join(chunks)
                assert "retry: 3000" in combined, (
                    f"'retry: 3000' not found in first {_CHUNK_WINDOW} chunks: {combined!r}"
                )
    finally:
        _sse_hub_mod._POLL_INTERVAL_SECS = 1.0
        _sse_hub_mod._KEEPALIVE_SECS = 15.0


# ---------------------------------------------------------------------------
# Test 2: status frame arrives on the stream (criterion 1)
# ---------------------------------------------------------------------------


def test_sse_status_frame_arrives(mock_svc):
    """A named 'event: status' frame with 'data:' arrives within the fast poll interval (SSE-02 criterion 1)."""
    from web import create_app
    import web.sse_hub as _sse_hub_mod

    _sse_hub_mod._POLL_INTERVAL_SECS = 0.05
    _sse_hub_mod._KEEPALIVE_SECS = 60.0

    try:
        with TestClient(create_app(mock_svc)) as client:
            with client.stream("GET", "/api/events") as resp:
                resp.raise_for_status()
                chunks = _collect_chunks(resp, n=_CHUNK_WINDOW)
                combined = "".join(chunks)
                assert "event: status" in combined, (
                    f"'event: status' not found in first {_CHUNK_WINDOW} chunks: {combined!r}"
                )
                assert "data:" in combined, (
                    f"'data:' not found in first {_CHUNK_WINDOW} chunks: {combined!r}"
                )
    finally:
        _sse_hub_mod._POLL_INTERVAL_SECS = 1.0
        _sse_hub_mod._KEEPALIVE_SECS = 15.0


# ---------------------------------------------------------------------------
# Test 3: keepalive comment emitted on idle (criterion 1 keepalive half)
# ---------------------------------------------------------------------------


def test_sse_keepalive_comment(mock_svc):
    """': keep-alive' SSE comment appears when queue is idle (keepalive_secs suppresses status, criterion 1)."""
    from web import create_app
    import web.sse_hub as _sse_hub_mod

    # High poll interval suppresses status frames; tiny keepalive triggers the comment quickly.
    _sse_hub_mod._POLL_INTERVAL_SECS = 60.0
    _sse_hub_mod._KEEPALIVE_SECS = 0.05

    try:
        with TestClient(create_app(mock_svc)) as client:
            with client.stream("GET", "/api/events") as resp:
                resp.raise_for_status()
                chunks = _collect_chunks(resp, n=_CHUNK_WINDOW)
                combined = "".join(chunks)
                assert ": keep-alive" in combined, (
                    f"': keep-alive' comment not found in first {_CHUNK_WINDOW} chunks: {combined!r}"
                )
    finally:
        _sse_hub_mod._POLL_INTERVAL_SECS = 1.0
        _sse_hub_mod._KEEPALIVE_SECS = 15.0


# ---------------------------------------------------------------------------
# Test 4: bot start/stop reflected in stream (criterion 3)
# ---------------------------------------------------------------------------


def test_sse_bot_start_stop_reflected(mock_svc):
    """After bot transitions to running=True, a status frame with 'running' data arrives (SSE-02 criterion 3)."""
    from web import create_app
    import web.sse_hub as _sse_hub_mod

    _sse_hub_mod._POLL_INTERVAL_SECS = 0.05
    _sse_hub_mod._KEEPALIVE_SECS = 60.0

    # Use a mutable holder so side_effect can flip the return value.
    call_count = [0]

    def get_status_side_effect():
        call_count[0] += 1
        if call_count[0] <= 2:
            return {"running": False, "uptime_secs": 0.0, "plugins": {}}
        return {"running": True, "uptime_secs": 1.5, "plugins": {}}

    mock_svc.get_status.side_effect = get_status_side_effect

    try:
        with TestClient(create_app(mock_svc)) as client:
            with client.stream("GET", "/api/events") as resp:
                resp.raise_for_status()
                # Collect more chunks to allow the poll loop to flip the running state.
                chunks = _collect_chunks(resp, n=16)
                combined = "".join(chunks)
                # The frame data is JSON; assert the running=true value appears.
                assert '"running": true' in combined or '"running":true' in combined, (
                    f"No 'running: true' frame found after bot flip. Combined: {combined!r}"
                )
    finally:
        _sse_hub_mod._POLL_INTERVAL_SECS = 1.0
        _sse_hub_mod._KEEPALIVE_SECS = 15.0


# ---------------------------------------------------------------------------
# Test 5: disconnect cleans the hub (criterion 2)
# ---------------------------------------------------------------------------


def test_sse_disconnect_cleans_hub(mock_svc):
    """After the stream context exits, SseHub._queues is empty (generator finally block ran, criterion 2).

    Asserts via len(app.state.sse_hub._queues) == 0 inside the still-open TestClient
    context but after the inner client.stream() context has exited.
    Does NOT rely on request.is_disconnected() which is unreliable in TestClient's
    in-process transport (RESEARCH open question A3).
    """
    from web import create_app
    import web.sse_hub as _sse_hub_mod

    _sse_hub_mod._POLL_INTERVAL_SECS = 0.05
    _sse_hub_mod._KEEPALIVE_SECS = 60.0

    try:
        with TestClient(create_app(mock_svc)) as client:
            # Open the stream, read one chunk, then exit the stream context.
            with client.stream("GET", "/api/events") as resp:
                resp.raise_for_status()
                # Read at least one chunk to confirm the generator subscribed.
                _collect_chunks(resp, n=1)
            # Stream context exited: generator finally block should have run.
            # Hub must now have zero queues.
            hub = client.app.state.sse_hub
            assert len(hub._queues) == 0, (
                f"SseHub._queues not empty after stream disconnect: {hub._queues!r}"
            )
    finally:
        _sse_hub_mod._POLL_INTERVAL_SECS = 1.0
        _sse_hub_mod._KEEPALIVE_SECS = 15.0


# ---------------------------------------------------------------------------
# Test 6: no credential patterns in SSE frames (SSE-03 carryover)
# ---------------------------------------------------------------------------


def test_sse_no_credential_patterns(mock_svc):
    """No credential-pattern strings appear in the first few SSE frames (SSE-03 carryover).

    Checks: password, key=, cvv (case-insensitive) and an email-like regex pattern.
    The '@' character is excluded from the exact-string check since JSON keys may
    safely include it in non-credential contexts; the email-like regex catches the
    dangerous form (user@host.tld).
    """
    from web import create_app
    import web.sse_hub as _sse_hub_mod

    _sse_hub_mod._POLL_INTERVAL_SECS = 0.05
    _sse_hub_mod._KEEPALIVE_SECS = 60.0

    try:
        with TestClient(create_app(mock_svc)) as client:
            with client.stream("GET", "/api/events") as resp:
                resp.raise_for_status()
                chunks = _collect_chunks(resp, n=_CHUNK_WINDOW)
                combined = "".join(chunks)

        for pattern in CRED_PATTERNS:
            assert pattern not in combined.lower(), (
                f"Credential pattern {pattern!r} found in SSE stream frames: {combined!r}"
            )
        email_re = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
        assert not email_re.search(combined), (
            f"Email-like pattern found in SSE stream frames: {combined!r}"
        )
    finally:
        _sse_hub_mod._POLL_INTERVAL_SECS = 1.0
        _sse_hub_mod._KEEPALIVE_SECS = 15.0
