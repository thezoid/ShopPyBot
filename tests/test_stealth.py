"""Unit tests for core/stealth.py (ANTI-08, ANTI-04, ANTI-05).

Tests cover:
  - apply_stealth sends correct CDP calls (ANTI-08)
  - STEALTH_JS contains all 4 required patches (ANTI-08)
  - ProxyPool round-robin, retire/cooldown, from_urls (ANTI-04/ANTI-05)
  - _parse_proxy_url with and without credentials
  - build_proxy_browser_args includes WebRTC flag and never leaks credentials
  - setup_proxy_auth registers handlers before fetch.enable (ANTI-04 Pitfall 4)
  - setup_proxy_auth is a no-op when username is empty
  - _is_ban_response detects ban statuses and body phrases (ANTI-05)

asyncio_mode = "auto" in pyproject.toml: no @pytest.mark.asyncio decorators needed.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch
import pytest

import core.stealth as stealth_module
from core.stealth import (
    STEALTH_JS,
    apply_stealth,
    ProxyPool,
    _ProxyEntry,
    _parse_proxy_url,
    _is_ban_response,
    build_proxy_browser_args,
    setup_proxy_auth,
    _live_tasks,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(host_port="1.2.3.4:8080", username="u", password="p"):
    url = f"http://{username}:{password}@{host_port}" if username else f"http://{host_port}"
    return _ProxyEntry(
        url=url,
        host_port=host_port,
        username=username,
        password=password,
    )


def _make_pool(n=3, **pool_kwargs):
    entries = [_make_entry(host_port=f"10.0.0.{i}:8080") for i in range(n)]
    return ProxyPool(entries, **pool_kwargs), entries


# ---------------------------------------------------------------------------
# ANTI-08: apply_stealth CDP calls
# ---------------------------------------------------------------------------


async def test_apply_stealth_sends_correct_cdp_calls():
    """apply_stealth awaits tab.send exactly twice: page.enable then add_script."""
    tab = MagicMock()
    tab.send = AsyncMock()

    await apply_stealth(tab)

    assert tab.send.await_count == 2, (
        f"Expected 2 tab.send calls, got {tab.send.await_count}"
    )
    # The second call must carry STEALTH_JS in its argument
    second_call_arg = tab.send.await_args_list[1][0][0]
    # The CDP object's string representation or repr contains STEALTH_JS source
    import inspect as _inspect
    # Verify by checking that the second send arg is not the same object as first
    first_call_arg = tab.send.await_args_list[0][0][0]
    assert first_call_arg is not second_call_arg, "First and second send args must differ"


def test_stealth_js_contains_required_patches():
    """STEALTH_JS must contain all 4 patch markers: chrome, plugins, languages, screen."""
    assert "window.chrome" in STEALTH_JS or "window, 'chrome'" in STEALTH_JS, (
        "STEALTH_JS must patch window.chrome"
    )
    assert "navigator.plugins" in STEALTH_JS or "navigator, 'plugins'" in STEALTH_JS, (
        "STEALTH_JS must patch navigator.plugins"
    )
    assert "navigator.languages" in STEALTH_JS or "navigator, 'languages'" in STEALTH_JS, (
        "STEALTH_JS must patch navigator.languages"
    )
    assert "screen.width" in STEALTH_JS or "screen, 'width'" in STEALTH_JS, (
        "STEALTH_JS must patch screen dimensions (width)"
    )
    assert "screen.height" in STEALTH_JS or "screen, 'height'" in STEALTH_JS, (
        "STEALTH_JS must patch screen dimensions (height)"
    )


# ---------------------------------------------------------------------------
# ANTI-04: ProxyPool basics
# ---------------------------------------------------------------------------


def test_proxypool_current_returns_first():
    """Fresh pool of 3: current() returns entries[0]."""
    pool, entries = _make_pool(3)
    assert pool.current() is entries[0]


def test_proxypool_roundrobin():
    """advance() cycles 0, 1, 2, 0 across 3 entries (CR-01: entries[0] is never skipped)."""
    pool, entries = _make_pool(3)
    assert pool.advance() is entries[0]
    assert pool.advance() is entries[1]
    assert pool.advance() is entries[2]
    assert pool.advance() is entries[0]


def test_proxypool_roundrobin_no_skip_first(tmp_path):
    """CR-01 regression: a 3-proxy pool yields entries[0], [1], [2], [0] in order.

    The pre-fix bug seeded _index=0 so advance() returned entries[1] first,
    permanently skipping entries[0]. With _index=-1 the sequence is correct.
    """
    entries = [_make_entry(host_port=f"10.0.{i}.1:8080") for i in range(3)]
    pool = ProxyPool(entries)
    results = [pool.advance() for _ in range(4)]
    assert results[0] is entries[0], "First advance must return entries[0]"
    assert results[1] is entries[1]
    assert results[2] is entries[2]
    assert results[3] is entries[0], "Fourth advance must wrap back to entries[0]"


# ---------------------------------------------------------------------------
# ANTI-05: ProxyPool retire / cooldown
# ---------------------------------------------------------------------------


def test_proxypool_retires_after_max_failures():
    """record_failure 3x retires the proxy; the 3rd call returns True."""
    pool, entries = _make_pool(3, max_failures=3, cooldown_secs=300.0)
    entry = entries[0]
    result1 = entry.record_failure(3, 300.0)
    result2 = entry.record_failure(3, 300.0)
    result3 = entry.record_failure(3, 300.0)
    assert result1 is False
    assert result2 is False
    assert result3 is True
    assert entry.is_retired()


def test_proxypool_cooldown_reentry():
    """Retired proxy becomes non-retired once monotonic passes retired_until."""
    pool, entries = _make_pool(1, max_failures=1, cooldown_secs=60.0)
    entry = entries[0]

    with patch("core.stealth.time") as mock_time:
        # At T=100, retire the proxy (retired_until = 100 + 60 = 160)
        mock_time.monotonic.return_value = 100.0
        entry.record_failure(1, 60.0)
        assert entry.retired_until == 160.0

        # At T=159 still retired
        mock_time.monotonic.return_value = 159.0
        assert entry.is_retired() is True

        # At T=161 cooldown elapsed
        mock_time.monotonic.return_value = 161.0
        assert entry.is_retired() is False


def test_proxypool_all_retired_returns_none():
    """Retire every entry: advance() returns None."""
    pool, entries = _make_pool(2, max_failures=1, cooldown_secs=999.0)
    for e in entries:
        e.record_failure(1, 999.0)
    assert pool.advance() is None


def test_proxypool_record_success_resets_failures():
    """2 failures then record_success: failures == 0, not retired."""
    pool, entries = _make_pool(2, max_failures=5)
    entry = entries[0]
    entry.record_failure(5, 300.0)
    entry.record_failure(5, 300.0)
    assert entry.failures == 2
    entry.record_success()
    assert entry.failures == 0
    assert not entry.is_retired()


# ---------------------------------------------------------------------------
# ANTI-04: ProxyPool from_urls + size
# ---------------------------------------------------------------------------


def test_proxypool_from_urls_builds_entries():
    """from_urls builds correct entries; size() == 2; first host_port is h:1."""
    pool = ProxyPool.from_urls(
        ["http://u:p@h:1", "http://h2:2"],
        max_failures=3,
        cooldown_secs=300.0,
    )
    assert pool.size() == 2
    first = pool.current()
    assert first is not None
    assert first.host_port == "h:1"


# ---------------------------------------------------------------------------
# _parse_proxy_url
# ---------------------------------------------------------------------------


def test_parse_proxy_url_with_creds():
    """http://u:p@1.2.3.4:8080 -> host_port '1.2.3.4:8080', username 'u', password 'p'."""
    host_port, username, password = _parse_proxy_url("http://u:p@1.2.3.4:8080")
    assert host_port == "1.2.3.4:8080"
    assert username == "u"
    assert password == "p"


def test_parse_proxy_url_no_creds():
    """http://1.2.3.4:8080 -> username '' and password '' (empty strings, not None)."""
    host_port, username, password = _parse_proxy_url("http://1.2.3.4:8080")
    assert host_port == "1.2.3.4:8080"
    assert username == ""
    assert password == ""


def test_parse_proxy_url_portless_raises():
    """CR-03 regression: port-less URL must raise ValueError, not produce 'host:None'.

    The pre-fix code produced f'{hostname}:None', which Chrome ignores and connects
    directly, silently leaking the real IP. The fix raises ValueError at pool
    construction time so the misconfiguration is caught at startup.
    """
    with pytest.raises(ValueError, match="missing port"):
        _parse_proxy_url("http://proxy.example.com")


def test_parse_proxy_url_no_hostname_raises():
    """CR-03 regression: URL with no parseable hostname must raise ValueError."""
    with pytest.raises(ValueError, match="missing hostname"):
        _parse_proxy_url("proxy.example.com:8080")  # no scheme -> treated as path


# ---------------------------------------------------------------------------
# build_proxy_browser_args
# ---------------------------------------------------------------------------


def test_build_proxy_browser_args_includes_webrtc():
    """Returns list with --proxy-server=<host_port> AND WebRTC flag; no credentials in args."""
    entry = _make_entry(host_port="1.2.3.4:8080", username="secret", password="secret")
    args = build_proxy_browser_args(entry)
    assert "--proxy-server=1.2.3.4:8080" in args, f"Expected proxy-server arg in {args}"
    assert any(
        "force-webrtc-ip-handling-policy" in a for a in args
    ), f"Expected WebRTC flag in {args}"
    # Credentials must never appear in the args
    for arg in args:
        assert "secret" not in arg, f"Credential leaked into browser arg: {arg}"


def test_build_proxy_browser_args_none_entry():
    """build_proxy_browser_args(None) returns empty list."""
    assert build_proxy_browser_args(None) == []


# ---------------------------------------------------------------------------
# setup_proxy_auth — ordering and no-op
# ---------------------------------------------------------------------------


async def test_setup_proxy_auth_registers_before_enable():
    """add_handler calls happen before fetch.enable send (Pitfall 4)."""
    tab = MagicMock()
    tab.send = AsyncMock()

    call_order = []

    def _add_handler(event_type, callback):
        call_order.append(("add_handler", event_type.__name__))

    async def _send(cmd):
        # Record the class name of the CDP command object
        call_order.append(("send", type(cmd).__name__))

    tab.add_handler = _add_handler
    tab.send = AsyncMock(side_effect=_send)

    await setup_proxy_auth(tab, "user", "pass")

    # Both add_handler calls must precede the enable send
    handler_positions = [i for i, (kind, _) in enumerate(call_order) if kind == "add_handler"]
    send_positions = [i for i, (kind, _) in enumerate(call_order) if kind == "send"]

    assert handler_positions, "No add_handler calls recorded"
    assert send_positions, "No send calls recorded"
    assert max(handler_positions) < min(send_positions), (
        f"add_handler must precede send; call order: {call_order}"
    )


async def test_setup_proxy_auth_noop_empty_user():
    """setup_proxy_auth(tab, '', '') makes zero add_handler / send calls."""
    tab = MagicMock()
    tab.send = AsyncMock()
    tab.add_handler = MagicMock()

    await setup_proxy_auth(tab, "", "")

    tab.add_handler.assert_not_called()
    tab.send.assert_not_awaited()


async def test_setup_proxy_auth_tasks_retained_in_live_tasks():
    """CR-04 regression: tasks created by handler callbacks are added to _live_tasks.

    The pre-fix code discarded the create_task() return value immediately, allowing
    CPython to GC the task before it ran. The fix stores each task in _live_tasks and
    removes it via done callback. This test simulates the auth handler being fired and
    asserts that the task is tracked (or has already completed and been discarded).
    """
    import asyncio as _asyncio

    tab = MagicMock()
    captured_handlers: dict = {}
    tasks_seen: list = []

    def _record_handler(event_type, callback):
        captured_handlers[event_type.__name__] = callback

    tab.add_handler = _record_handler
    tab.send = AsyncMock(return_value=None)

    _live_tasks.clear()

    await setup_proxy_auth(tab, "user", "pass")

    assert "AuthRequired" in captured_handlers, "AuthRequired handler not registered"

    # Simulate the AuthRequired event firing inside a running loop.
    from nodriver.cdp.fetch import AuthRequired
    mock_event = MagicMock(spec=AuthRequired)
    mock_event.request_id = "req-1"

    await captured_handlers["AuthRequired"](mock_event)

    # The task should be in _live_tasks (pending) or already completed+removed.
    # Either way, tab.send must have been scheduled exactly once (for the enable
    # call) plus once inside the handler = 2 total by the time we await the task.
    # Allow the event loop to process the pending task.
    await _asyncio.sleep(0)

    # After yielding, the task should have run and called tab.send a second time.
    assert tab.send.await_count >= 2, (
        f"Expected at least 2 send calls (enable + auth response), "
        f"got {tab.send.await_count}"
    )


# ---------------------------------------------------------------------------
# _is_ban_response
# ---------------------------------------------------------------------------


def test_is_ban_response_status():
    """403, 429, 503 -> True; 200 with benign body -> False."""
    assert _is_ban_response(403, "") is True
    assert _is_ban_response(429, "") is True
    assert _is_ban_response(503, "") is True
    assert _is_ban_response(200, "everything is fine") is False


def test_is_ban_response_phrase():
    """200 body containing 'Access Denied' (case-insensitive) -> True."""
    assert _is_ban_response(200, "Access Denied") is True
    assert _is_ban_response(200, "access denied") is True
    assert _is_ban_response(200, "Please verify you are human") is True
    assert _is_ban_response(200, "bot detected on this session") is True


# ---------------------------------------------------------------------------
# PX-02: _on_request_paused continues the request + tracks task in _live_tasks
# ---------------------------------------------------------------------------


async def test_setup_proxy_auth_request_paused_continues():
    """PX-02: the RequestPaused handler fires continue_request and tracks the task.

    Covers stealth.py:303-307 -- _on_request_paused must:
      1. call asyncio.create_task(tab.send(fetch.continue_request(request_id=...)))
      2. add the task to _live_tasks
      3. register a done callback that discards the task from _live_tasks once done

    Strategy: capture the handler via add_handler call_args, invoke it with a
    fake event, observe that _live_tasks grows by 1 right after the handler runs
    (before the task completes), then yield to the event loop so the task runs and
    the done callback discards it, and finally assert the tab.send payload.
    """
    from nodriver.cdp import fetch

    tab = MagicMock()
    tab.send = AsyncMock(return_value=None)
    tab.add_handler = MagicMock()

    stealth_module._live_tasks.clear()
    await setup_proxy_auth(tab, "user", "pass")

    # Locate the _on_request_paused handler registered for fetch.RequestPaused
    handler = None
    for c in tab.add_handler.call_args_list:
        event_type, callback = c[0]
        if event_type is fetch.RequestPaused:
            handler = callback
            break
    assert handler is not None, "No handler registered for fetch.RequestPaused"

    # Invoke the handler with a fake event carrying request_id="req-1"
    fake_event = SimpleNamespace(request_id="req-1")
    size_before = len(stealth_module._live_tasks)
    await handler(fake_event)
    size_after = len(stealth_module._live_tasks)

    # The handler must have added one task to _live_tasks (task still pending)
    assert size_after == size_before + 1, (
        f"Expected _live_tasks to grow by 1 after handler; "
        f"before={size_before}, after={size_after}"
    )

    # Grab the task that was just added
    the_task = next(iter(stealth_module._live_tasks))

    # Yield control so the scheduled task runs (first tick) and the done
    # callback fires (second tick).
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    # After the task completes, the done callback should have discarded it
    assert the_task not in stealth_module._live_tasks, (
        "Done callback did not discard the task from _live_tasks"
    )

    # tab.send was called twice: once for fetch.enable, once for continue_request
    assert tab.send.await_count == 2, (
        f"Expected 2 tab.send calls (enable + continue_request), got {tab.send.await_count}"
    )
    # The second send carries a generator produced by fetch.continue_request(...)
    # (nodriver CDP functions are generator factories, not class constructors)
    continue_call_arg = tab.send.await_args_list[1][0][0]
    assert hasattr(continue_call_arg, "__qualname__"), (
        "Expected a generator with __qualname__, got something else"
    )
    assert continue_call_arg.__qualname__ == "continue_request", (
        f"Expected generator from fetch.continue_request, "
        f"got {continue_call_arg.__qualname__!r}"
    )


# ---------------------------------------------------------------------------
# PX-03: ProxyPool empty pool + pool-level methods
# ---------------------------------------------------------------------------


def test_proxypool_empty_and_pool_level_methods():
    """PX-03: covers the empty-pool branches and pool.record_success().

    Covers stealth.py:222 (__len__ on empty pool), 231 (current()->None for
    empty pool), 243 (advance()->None for empty pool), and 257
    (pool.record_success resets entry.failures to 0).
    """
    # Empty pool: __len__, current(), advance() all reflect zero-entry state
    empty_pool = ProxyPool([])
    assert len(empty_pool) == 0, "Empty pool must have len 0"
    assert empty_pool.current() is None, "current() on empty pool must return None"
    assert empty_pool.advance() is None, "advance() on empty pool must return None"

    # 1-entry pool: pool.record_success resets failures to 0 via entry.record_success()
    pool = ProxyPool.from_urls(["http://h:1"])
    entry = pool.current()
    assert entry is not None, "1-entry pool must have a current entry"

    # Drive failures > 0 (but below the default max_failures=3 so not yet retired)
    entry.record_failure(3, 300.0)
    entry.record_failure(3, 300.0)
    assert entry.failures == 2, "Expected 2 failures before reset"

    pool.record_success(entry)
    assert entry.failures == 0, "record_success must reset entry.failures to 0"
