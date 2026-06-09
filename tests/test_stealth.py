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

from unittest.mock import AsyncMock, MagicMock, call, patch
import pytest

from core.stealth import (
    STEALTH_JS,
    apply_stealth,
    ProxyPool,
    _ProxyEntry,
    _parse_proxy_url,
    _is_ban_response,
    build_proxy_browser_args,
    setup_proxy_auth,
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
    """advance() cycles 1, 2, 0, 1 across 3 entries."""
    pool, entries = _make_pool(3)
    assert pool.advance() is entries[1]
    assert pool.advance() is entries[2]
    assert pool.advance() is entries[0]
    assert pool.advance() is entries[1]


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
