"""Tests for RetailerPlugin.relaunch() -- sequence order + apply_stealth coverage.

REL-03: relaunch() runs teardown -> setup -> restore_session -> login in that fixed order.
All tests are RED until relaunch() is added to the ABC in Task 2.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, call, patch

from core.plugin_base import RetailerPlugin


# ---------------------------------------------------------------------------
# Minimal concrete stub for relaunch tests
# ---------------------------------------------------------------------------


def _make_recording_plugin():
    """Build a RetailerPlugin subclass with recording AsyncMocks.

    teardown, setup, restore_session, and login are AsyncMocks that append
    their method name to a shared call_order list via side_effect.
    """
    call_order: list[str] = []

    class _RecordingPlugin(RetailerPlugin):
        domain_patterns = ["relaunch.example.com"]

        async def check_availability(self, url: str) -> bool:
            return True

        async def auto_buy(self, url: str) -> bool:
            return False

    plugin = _RecordingPlugin(config=None)

    async def _teardown_side_effect():
        call_order.append("teardown")

    async def _setup_side_effect():
        call_order.append("setup")

    async def _restore_session_side_effect():
        call_order.append("restore_session")
        return False

    async def _login_side_effect():
        call_order.append("login")

    plugin.teardown = AsyncMock(side_effect=_teardown_side_effect)
    plugin.setup = AsyncMock(side_effect=_setup_side_effect)
    plugin.restore_session = AsyncMock(side_effect=_restore_session_side_effect)
    plugin.login = AsyncMock(side_effect=_login_side_effect)

    return plugin, call_order


# ---------------------------------------------------------------------------
# REL-03: sequence order
# ---------------------------------------------------------------------------


async def test_relaunch_sequence_order():
    """relaunch() must call teardown -> setup -> restore_session -> login in order."""
    plugin, call_order = _make_recording_plugin()

    await plugin.relaunch()

    assert call_order == ["teardown", "setup", "restore_session", "login"]


async def test_relaunch_skips_login_when_session_restored():
    """When restore_session() returns True, login must NOT be awaited."""
    plugin, call_order = _make_recording_plugin()

    # Override restore_session to return True
    async def _restore_true():
        call_order.append("restore_session")
        return True

    plugin.restore_session = AsyncMock(side_effect=_restore_true)

    await plugin.relaunch()

    assert "restore_session" in call_order
    assert "login" not in call_order
    # teardown and setup must still have run
    assert call_order[0] == "teardown"
    assert call_order[1] == "setup"
    assert call_order[2] == "restore_session"


async def test_relaunch_teardown_error_is_swallowed():
    """A RuntimeError from teardown must not propagate; setup and login still run."""
    call_order: list[str] = []

    class _ErrorPlugin(RetailerPlugin):
        domain_patterns = ["error.example.com"]

        async def check_availability(self, url: str) -> bool:
            return True

        async def auto_buy(self, url: str) -> bool:
            return False

    plugin = _ErrorPlugin(config=None)

    async def _failing_teardown():
        call_order.append("teardown")
        raise RuntimeError("simulated browser death")

    async def _record_setup():
        call_order.append("setup")

    async def _restore_false():
        call_order.append("restore_session")
        return False

    async def _record_login():
        call_order.append("login")

    plugin.teardown = AsyncMock(side_effect=_failing_teardown)
    plugin.setup = AsyncMock(side_effect=_record_setup)
    plugin.restore_session = AsyncMock(side_effect=_restore_false)
    plugin.login = AsyncMock(side_effect=_record_login)

    # Must not raise
    await plugin.relaunch()

    # teardown ran (and raised internally), but setup and login still ran
    assert "teardown" in call_order
    assert "setup" in call_order
    assert "login" in call_order


# ---------------------------------------------------------------------------
# REL-03: apply_stealth re-injection verified via setup() invocation
# ---------------------------------------------------------------------------


async def test_relaunch_apply_stealth_called():
    """relaunch() must await self.setup() exactly once (setup is the stealth injection point).

    This test uses plain AsyncMocks on a stub plugin; the contract is that
    relaunch awaits setup exactly once so that concrete plugins, whose setup()
    calls apply_stealth(self.driver.main_tab), re-inject stealth on the new
    browser.
    """
    plugin, call_order = _make_recording_plugin()

    await plugin.relaunch()

    plugin.setup.assert_awaited_once()
    assert "setup" in call_order


# ---------------------------------------------------------------------------
# BF-03 / D-15: relaunch() must honor a failed re-login, not silently treat it
# as authenticated.
# ---------------------------------------------------------------------------


async def test_relaunch_logs_error_on_failed_relogin():
    """When restore_session() is False and login() returns False, relaunch() must
    log an ERROR and must not treat the session as authenticated."""
    plugin, call_order = _make_recording_plugin()

    async def _login_fails():
        call_order.append("login")
        return False

    plugin.login = AsyncMock(side_effect=_login_fails)

    with patch("core.plugin_base.writeLog") as mock_write_log:
        await plugin.relaunch()

    assert call_order == ["teardown", "setup", "restore_session", "login"]
    error_calls = [
        c for c in mock_write_log.call_args_list if c.args and c.args[1] == "ERROR"
    ]
    assert any("re-login failed" in c.args[0] for c in error_calls), (
        f"Expected an ERROR log about failed re-login; got: {mock_write_log.call_args_list}"
    )


async def test_relaunch_no_error_log_on_successful_relogin():
    """When login() returns True after a failed restore_session, relaunch() must
    NOT log the re-login-failed ERROR."""
    plugin, call_order = _make_recording_plugin()

    async def _login_succeeds():
        call_order.append("login")
        return True

    plugin.login = AsyncMock(side_effect=_login_succeeds)

    with patch("core.plugin_base.writeLog") as mock_write_log:
        await plugin.relaunch()

    error_calls = [
        c for c in mock_write_log.call_args_list if c.args and c.args[1] == "ERROR"
    ]
    assert not any("re-login failed" in c.args[0] for c in error_calls)
