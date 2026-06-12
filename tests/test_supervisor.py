"""Tests for supervise() wrapper and _is_browser_dead_exc helper.

Covers:
- REL-01: crash one plugin, siblings keep running (TaskGroup isolation)
- REL-01: CancelledError propagates out of supervise() (not absorbed)
- REL-02: failure budget (alert_on_errors) parks plugin + dispatches notification
- REL-02: failure-budget window eviction (old failures do not count)
- REL-03: browser-dead exception triggers assign_proxy + relaunch
- Helper: _is_browser_dead_exc classification
"""

import asyncio
import time as _time_module
from collections import deque
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from core.orchestrator import _is_browser_dead_exc
from core.registry import PluginRegistry


# ---------------------------------------------------------------------------
# Helpers (copied verbatim from test_orchestrator.py L55-62)
# ---------------------------------------------------------------------------


def _make_registry_with_plugins(*plugins):
    """Return a bare PluginRegistry-like object with _active_plugins set."""
    registry = MagicMock(spec=PluginRegistry)
    registry._active_plugins = list(plugins)
    registry._all_plugins = list(plugins)
    registry.teardown_all = AsyncMock()
    registry.assign_proxy = MagicMock()
    return registry


def _make_cfg(alert_on_errors=3, backoff_base=2.0, backoff_jitter=0.0):
    """Build a minimal config mock with checkout fields."""
    checkout = MagicMock()
    checkout.alert_on_errors = alert_on_errors
    checkout.backoff_base = backoff_base
    checkout.backoff_jitter = backoff_jitter
    cfg = MagicMock()
    cfg.checkout = checkout
    return cfg


def _make_dispatcher():
    """Build a mock dispatcher with async notify."""
    dispatcher = MagicMock()
    dispatcher.notify = AsyncMock()
    return dispatcher


# ---------------------------------------------------------------------------
# REL-01: crash isolation -- one crash does NOT cancel siblings
# ---------------------------------------------------------------------------


async def test_crash_one_plugin_others_survive():
    """Plugin A crashing repeatedly does not cancel plugin B's run_plugin.

    supervise() absorbs all Exceptions before the TaskGroup boundary (REL-01
    keystone). Plugin B's run_plugin must be called at least once even when
    Plugin A crashes on every iteration.
    """
    from core.orchestrator import supervise

    cfg = _make_cfg(alert_on_errors=2, backoff_base=1.0, backoff_jitter=0.0)

    # Track calls to each plugin's run_plugin path
    b_call_count = 0
    a_call_count = 0

    async def crashing_run(*args, **kwargs):
        nonlocal a_call_count
        a_call_count += 1
        raise RuntimeError("simulated crash")

    async def ok_run(*args, **kwargs):
        nonlocal b_call_count
        b_call_count += 1
        # After being called once, park the plugin by never returning so the test can end
        await asyncio.sleep(999)

    plugin_a = MagicMock()
    plugin_a.__class__.__name__ = "PluginA"
    plugin_a.relaunch = AsyncMock()

    plugin_b = MagicMock()
    plugin_b.__class__.__name__ = "PluginB"

    registry = _make_registry_with_plugins(plugin_a, plugin_b)

    with patch("core.orchestrator.run_plugin") as mock_run_plugin, \
         patch("core.orchestrator.compute_delay", return_value=0.0), \
         patch("core.orchestrator.asyncio.sleep", new_callable=AsyncMock):

        async def side_effect(plugin, *args, **kwargs):
            if plugin is plugin_a:
                return await crashing_run(plugin, *args, **kwargs)
            else:
                return await ok_run(plugin, *args, **kwargs)

        mock_run_plugin.side_effect = side_effect

        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(
                    supervise(plugin_a, asyncio.Queue(), 30, _make_dispatcher(), cfg, registry),
                    name="poll-PluginA",
                )
                tg.create_task(
                    supervise(plugin_b, asyncio.Queue(), 30, _make_dispatcher(), cfg, registry),
                    name="poll-PluginB",
                )
        except* asyncio.CancelledError:
            pass

    # Plugin A was called (crashed), plugin B was called (kept running)
    assert a_call_count >= 1, "Plugin A should have been entered"
    assert b_call_count >= 1, "Plugin B must keep running when Plugin A crashes (REL-01)"


# ---------------------------------------------------------------------------
# REL-01: CancelledError propagates out of supervise()
# ---------------------------------------------------------------------------


async def test_supervise_propagates_cancelled():
    """CancelledError from a cancelled task propagates out of supervise() (REL-01).

    Cancelling the supervise() task must raise CancelledError to the caller,
    not be absorbed by the except Exception handler. This ensures clean shutdown.
    """
    from core.orchestrator import supervise

    cfg = _make_cfg()

    async def blocking_run(*args, **kwargs):
        await asyncio.sleep(999)

    plugin = MagicMock()
    plugin.__class__.__name__ = "PluginX"
    registry = _make_registry_with_plugins(plugin)

    with patch("core.orchestrator.run_plugin", side_effect=blocking_run):
        task = asyncio.create_task(
            supervise(plugin, asyncio.Queue(), 30, _make_dispatcher(), cfg, registry)
        )
        await asyncio.sleep(0)  # let the task start
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


# ---------------------------------------------------------------------------
# REL-02: failure budget parks plugin + dispatcher notified
# ---------------------------------------------------------------------------


async def test_failure_budget_parks_plugin():
    """Plugin exceeding alert_on_errors failures is parked; dispatcher notified (REL-02).

    With alert_on_errors=3 and run_plugin always raising, supervise() must:
    - return (park) after 3 failures
    - call dispatcher.notify with a NotificationEvent whose action == "plugin_parked"
    """
    from core.orchestrator import supervise

    cfg = _make_cfg(alert_on_errors=3, backoff_base=1.0, backoff_jitter=0.0)
    dispatcher = _make_dispatcher()

    plugin = MagicMock()
    plugin.__class__.__name__ = "PluginPark"
    registry = _make_registry_with_plugins(plugin)

    with patch("core.orchestrator.run_plugin", side_effect=RuntimeError("boom")), \
         patch("core.orchestrator.compute_delay", return_value=0.0), \
         patch("core.orchestrator.asyncio.sleep", new_callable=AsyncMock):

        await supervise(plugin, asyncio.Queue(), 30, dispatcher, cfg, registry)

    # dispatcher.notify must have been called with action="plugin_parked"
    assert dispatcher.notify.called, "dispatcher.notify must be called on park"
    notify_calls = dispatcher.notify.call_args_list
    actions = [c.args[0].action for c in notify_calls]
    assert "plugin_parked" in actions, f"Expected action='plugin_parked' in {actions}"


# ---------------------------------------------------------------------------
# REL-02: window eviction -- old failures do not count
# ---------------------------------------------------------------------------


async def test_failure_budget_window_eviction():
    """Failures older than the rolling window are evicted and do not count (REL-02).

    Scenario:
    1. Two failures at time T=0
    2. Clock advances past _FAILURE_WINDOW_SECS (600s)
    3. One more failure at T=700
    Budget = 3, but only 1 failure is in-window -> plugin is NOT parked.
    """
    from core.orchestrator import supervise, _FAILURE_WINDOW_SECS

    cfg = _make_cfg(alert_on_errors=3, backoff_base=1.0, backoff_jitter=0.0)
    dispatcher = _make_dispatcher()

    plugin = MagicMock()
    plugin.__class__.__name__ = "PluginEvict"
    registry = _make_registry_with_plugins(plugin)

    # We need fine control over monotonic() and a way to stop the supervise loop.
    # Strategy: run_plugin raises twice at T=0, then clock jumps to T=700,
    # then raises once more, then returns normally (allowing the loop to keep running).
    # After the 4th call (normal return), cancel the task to end the test.

    call_count = 0
    monotonic_values = [0.0, 0.0, 700.0, 700.0, 700.0, 700.0]  # enough values

    async def controlled_run(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise RuntimeError("early failure")
        if call_count == 3:
            raise RuntimeError("late failure")
        # 4th call: return normally; supervise loops -> cancel task to end
        await asyncio.sleep(999)

    monotonic_idx = 0

    def fake_monotonic():
        nonlocal monotonic_idx
        val = monotonic_values[min(monotonic_idx, len(monotonic_values) - 1)]
        monotonic_idx += 1
        return val

    with patch("core.orchestrator.run_plugin", side_effect=controlled_run), \
         patch("core.orchestrator.compute_delay", return_value=0.0), \
         patch("core.orchestrator.asyncio.sleep", new_callable=AsyncMock), \
         patch("core.orchestrator.time") as mock_time:

        mock_time.monotonic = fake_monotonic

        task = asyncio.create_task(
            supervise(plugin, asyncio.Queue(), 30, dispatcher, cfg, registry)
        )
        # Give it enough iterations to hit the eviction logic
        for _ in range(10):
            await asyncio.sleep(0)

        # Plugin should NOT be parked (only 1 in-window failure)
        assert not task.done() or not task.cancelled(), \
            "Plugin should NOT have been parked (old failures evicted from window)"
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert dispatcher.notify.call_count == 0 or \
           all(c.args[0].action != "plugin_parked" for c in dispatcher.notify.call_args_list), \
           "Plugin must NOT be parked when failures aged out of the window"


# ---------------------------------------------------------------------------
# REL-03: browser-dead exception triggers assign_proxy + relaunch
# ---------------------------------------------------------------------------


async def test_browser_dead_triggers_relaunch():
    """Browser-dead exception causes assign_proxy(plugin) + plugin.relaunch() (REL-03).

    Specifically:
    - ConnectionError -> assign_proxy called, relaunch awaited
    - Non-browser exception (ValueError) -> relaunch NOT called
    """
    from core.orchestrator import supervise

    cfg = _make_cfg(alert_on_errors=10, backoff_base=1.0, backoff_jitter=0.0)

    # --- Part 1: browser-dead exception triggers relaunch ---
    plugin = MagicMock()
    plugin.__class__.__name__ = "PluginDead"
    plugin.relaunch = AsyncMock()

    registry = _make_registry_with_plugins(plugin)

    call_count = 0

    async def dead_then_ok(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("Connection closed")
        await asyncio.sleep(999)

    with patch("core.orchestrator.run_plugin", side_effect=dead_then_ok), \
         patch("core.orchestrator.compute_delay", return_value=0.0), \
         patch("core.orchestrator.asyncio.sleep", new_callable=AsyncMock):

        task = asyncio.create_task(
            supervise(plugin, asyncio.Queue(), 30, _make_dispatcher(), cfg, registry)
        )
        for _ in range(10):
            await asyncio.sleep(0)

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    registry.assign_proxy.assert_called_once_with(plugin)
    plugin.relaunch.assert_awaited_once()

    # --- Part 2: non-browser exception does NOT trigger relaunch ---
    plugin2 = MagicMock()
    plugin2.__class__.__name__ = "PluginOk"
    plugin2.relaunch = AsyncMock()
    registry2 = _make_registry_with_plugins(plugin2)

    call_count2 = 0

    async def value_error_then_ok(*args, **kwargs):
        nonlocal call_count2
        call_count2 += 1
        if call_count2 == 1:
            raise ValueError("not a browser error")
        await asyncio.sleep(999)

    with patch("core.orchestrator.run_plugin", side_effect=value_error_then_ok), \
         patch("core.orchestrator.compute_delay", return_value=0.0), \
         patch("core.orchestrator.asyncio.sleep", new_callable=AsyncMock):

        task2 = asyncio.create_task(
            supervise(plugin2, asyncio.Queue(), 30, _make_dispatcher(), cfg, registry2)
        )
        for _ in range(10):
            await asyncio.sleep(0)

        task2.cancel()
        try:
            await task2
        except asyncio.CancelledError:
            pass

    plugin2.relaunch.assert_not_awaited()


# ---------------------------------------------------------------------------
# Helper: _is_browser_dead_exc classification
# ---------------------------------------------------------------------------


def test_is_browser_dead_exc_classification():
    """_is_browser_dead_exc returns True for browser-dead exceptions (REL-03)."""
    # ConnectionError -> True
    assert _is_browser_dead_exc(ConnectionError("Connection closed")) is True

    # OSError -> True (port not available during relaunch)
    assert _is_browser_dead_exc(OSError("OS error")) is True

    # RuntimeError with "WebSocket" in message -> True
    assert _is_browser_dead_exc(RuntimeError("WebSocket is not connected")) is True

    # RuntimeError without "WebSocket" -> False
    assert _is_browser_dead_exc(RuntimeError("some other error")) is False

    # ValueError -> False
    assert _is_browser_dead_exc(ValueError("not a browser error")) is False

    # TypeError -> False
    assert _is_browser_dead_exc(TypeError("type error")) is False
