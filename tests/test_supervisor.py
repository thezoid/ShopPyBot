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
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.orchestrator import _is_browser_dead_exc
from core.registry import PluginRegistry

# Capture the real asyncio.sleep BEFORE any monkey-patching in tests.
# Used by instant_sleep helpers so they do not self-recurse.
_REAL_SLEEP = asyncio.sleep


async def _instant_sleep(t):
    """Replace orchestrator's asyncio.sleep with a zero-delay real yield."""
    await _REAL_SLEEP(0)


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


def _make_plugin(name: str):
    """Build a minimal plugin mock with a class name and AsyncMock relaunch."""
    plugin = MagicMock()
    plugin.__class__ = type(name, (object,), {"__name__": name})
    plugin.relaunch = AsyncMock()
    return plugin


# ---------------------------------------------------------------------------
# Context manager: swap orchestrator's asyncio.sleep for instant yield
# ---------------------------------------------------------------------------

import contextlib
import core.orchestrator as _orch


@contextlib.contextmanager
def _instant_sleep_ctx():
    """Replace core.orchestrator.asyncio.sleep with a real zero-delay yield.

    Uses _REAL_SLEEP captured before any patching to avoid self-recursion.
    Restores the original after the with-block.
    """
    original = _orch.asyncio.sleep
    _orch.asyncio.sleep = _instant_sleep
    try:
        yield
    finally:
        _orch.asyncio.sleep = original


# ---------------------------------------------------------------------------
# REL-01: crash isolation -- one crash does NOT cancel siblings
# ---------------------------------------------------------------------------


async def test_crash_one_plugin_others_survive():
    """Plugin A crashing does not cancel plugin B's run_plugin (REL-01 keystone).

    Strategy:
    - Plugin A: alert_on_errors=2, always raises -> parks after 2 crashes (supervise returns)
    - Plugin B: blocks on a future until cancelled, tracks that it was entered
    - Assert B was entered at least once while A crashed
    """
    from core.orchestrator import supervise

    cfg_a = _make_cfg(alert_on_errors=2, backoff_base=1.0, backoff_jitter=0.0)
    cfg_b = _make_cfg(alert_on_errors=100, backoff_base=1.0, backoff_jitter=0.0)

    a_call_count = 0
    b_call_count = 0
    b_started = asyncio.Event()

    plugin_a = _make_plugin("PluginA")
    plugin_b = _make_plugin("PluginB")
    registry_a = _make_registry_with_plugins(plugin_a)
    registry_b = _make_registry_with_plugins(plugin_b)

    async def run_a(*args, **kwargs):
        nonlocal a_call_count
        a_call_count += 1
        await _REAL_SLEEP(0)  # real yield so B can start
        raise RuntimeError("simulated crash")

    async def run_b(*args, **kwargs):
        nonlocal b_call_count
        b_call_count += 1
        b_started.set()
        await asyncio.get_running_loop().create_future()

    with patch("core.orchestrator.run_plugin") as mock_run, \
         patch("core.orchestrator.compute_delay", return_value=0.0), \
         _instant_sleep_ctx():

        async def dispatch(plugin, *args, **kwargs):
            if plugin is plugin_a:
                return await run_a(plugin, *args, **kwargs)
            return await run_b(plugin, *args, **kwargs)

        mock_run.side_effect = dispatch

        task_a = asyncio.create_task(
            supervise(plugin_a, asyncio.Queue(), 30, _make_dispatcher(), cfg_a, registry_a)
        )
        task_b = asyncio.create_task(
            supervise(plugin_b, asyncio.Queue(), 30, _make_dispatcher(), cfg_b, registry_b)
        )

        await task_a  # A parks after 2 crashes
        task_b.cancel()
        try:
            await task_b
        except asyncio.CancelledError:
            pass

    assert a_call_count >= 2, "Plugin A should have crashed at least budget times"
    assert b_call_count >= 1, "Plugin B must have run (REL-01 -- not cancelled by A)"


# ---------------------------------------------------------------------------
# REL-01: CancelledError propagates out of supervise()
# ---------------------------------------------------------------------------


async def test_supervise_propagates_cancelled():
    """CancelledError propagates out of supervise(); not absorbed by except Exception."""
    from core.orchestrator import supervise

    cfg = _make_cfg()
    started = asyncio.Event()

    async def blocking_run(*args, **kwargs):
        started.set()
        await asyncio.get_running_loop().create_future()

    plugin = _make_plugin("PluginX")
    registry = _make_registry_with_plugins(plugin)

    with patch("core.orchestrator.run_plugin", side_effect=blocking_run):
        task = asyncio.create_task(
            supervise(plugin, asyncio.Queue(), 30, _make_dispatcher(), cfg, registry)
        )
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


# ---------------------------------------------------------------------------
# REL-02: failure budget parks plugin + dispatcher notified
# ---------------------------------------------------------------------------


async def test_failure_budget_parks_plugin():
    """Plugin parked after alert_on_errors failures; dispatcher.notify action=plugin_parked."""
    from core.orchestrator import supervise

    cfg = _make_cfg(alert_on_errors=3, backoff_base=1.0, backoff_jitter=0.0)
    dispatcher = _make_dispatcher()

    plugin = _make_plugin("PluginPark")
    registry = _make_registry_with_plugins(plugin)

    with patch("core.orchestrator.run_plugin", side_effect=RuntimeError("boom")), \
         patch("core.orchestrator.compute_delay", return_value=0.0), \
         _instant_sleep_ctx():

        await supervise(plugin, asyncio.Queue(), 30, dispatcher, cfg, registry)

    assert dispatcher.notify.called, "dispatcher.notify must be called on park"
    actions = [c.args[0].action for c in dispatcher.notify.call_args_list]
    assert "plugin_parked" in actions, f"Expected 'plugin_parked' in {actions}"


# ---------------------------------------------------------------------------
# REL-02: window eviction -- old failures do not count
# ---------------------------------------------------------------------------


async def test_failure_budget_window_eviction():
    """Failures older than 600s window are evicted; 3rd budget not triggered (REL-02)."""
    from core.orchestrator import supervise

    cfg = _make_cfg(alert_on_errors=3, backoff_base=1.0, backoff_jitter=0.0)
    dispatcher = _make_dispatcher()

    plugin = _make_plugin("PluginEvict")
    registry = _make_registry_with_plugins(plugin)

    call_count = 0
    monotonic_vals = [0.0, 0.0, 700.0, 700.0, 700.0, 700.0, 700.0]
    mono_iter = iter(monotonic_vals)

    def fake_monotonic():
        try:
            return next(mono_iter)
        except StopIteration:
            return 700.0

    started_4th = asyncio.Event()

    async def controlled_run(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("early failure 1")
        if call_count == 2:
            raise RuntimeError("early failure 2")
        if call_count == 3:
            raise RuntimeError("late failure (new window)")
        started_4th.set()
        await asyncio.get_running_loop().create_future()

    with patch("core.orchestrator.run_plugin", side_effect=controlled_run), \
         patch("core.orchestrator.compute_delay", return_value=0.0), \
         patch("core.orchestrator.time") as mock_time, \
         _instant_sleep_ctx():

        mock_time.monotonic = fake_monotonic

        task = asyncio.create_task(
            supervise(plugin, asyncio.Queue(), 30, dispatcher, cfg, registry)
        )
        await started_4th.wait()
        assert not task.done(), "Plugin must NOT be parked (old failures evicted)"
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    park_calls = [
        c for c in dispatcher.notify.call_args_list
        if c.args[0].action == "plugin_parked"
    ]
    assert len(park_calls) == 0, "Plugin must NOT be parked when failures aged out"


# ---------------------------------------------------------------------------
# REL-03: browser-dead exception triggers assign_proxy + relaunch
# ---------------------------------------------------------------------------


async def test_browser_dead_triggers_relaunch():
    """Browser-dead exception -> assign_proxy + relaunch; ValueError -> no relaunch."""
    from core.orchestrator import supervise

    cfg = _make_cfg(alert_on_errors=10, backoff_base=1.0, backoff_jitter=0.0)

    with _instant_sleep_ctx():
        # --- Part 1: ConnectionError (browser-dead) -> relaunch ---
        plugin = _make_plugin("PluginDead")
        plugin.relaunch = AsyncMock()
        registry = _make_registry_with_plugins(plugin)

        call_count = 0
        reached_second = asyncio.Event()

        async def dead_then_block(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Connection closed")
            reached_second.set()
            await asyncio.get_running_loop().create_future()

        with patch("core.orchestrator.run_plugin", side_effect=dead_then_block), \
             patch("core.orchestrator.compute_delay", return_value=0.0):

            task = asyncio.create_task(
                supervise(plugin, asyncio.Queue(), 30, _make_dispatcher(), cfg, registry)
            )
            await reached_second.wait()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        registry.assign_proxy.assert_called_once_with(plugin)
        plugin.relaunch.assert_awaited_once()

        # --- Part 2: ValueError (non-browser) -> no relaunch ---
        plugin2 = _make_plugin("PluginOk")
        plugin2.relaunch = AsyncMock()
        registry2 = _make_registry_with_plugins(plugin2)

        call_count2 = 0
        reached_second2 = asyncio.Event()

        async def value_error_then_block(*args, **kwargs):
            nonlocal call_count2
            call_count2 += 1
            if call_count2 == 1:
                raise ValueError("not a browser error")
            reached_second2.set()
            await asyncio.get_running_loop().create_future()

        with patch("core.orchestrator.run_plugin", side_effect=value_error_then_block), \
             patch("core.orchestrator.compute_delay", return_value=0.0):

            task2 = asyncio.create_task(
                supervise(plugin2, asyncio.Queue(), 30, _make_dispatcher(), cfg, registry2)
            )
            await reached_second2.wait()
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
    """_is_browser_dead_exc matches exactly the 3 nodriver browser-death surfaces (CR-02).

    True cases: ConnectionError variants, RuntimeError("WebSocket..."),
    websockets.exceptions.ConnectionClosed.
    False cases: bare OSError, PermissionError, FileNotFoundError (disk/fs errors must NOT
    trigger a browser relaunch -- CR-02 fix).
    """
    # True: all three confirmed nodriver surfaces
    assert _is_browser_dead_exc(ConnectionError("Connection closed")) is True
    assert _is_browser_dead_exc(ConnectionError("Connection closing")) is True
    assert _is_browser_dead_exc(ConnectionRefusedError("refused")) is True  # ConnectionError subclass
    assert _is_browser_dead_exc(ConnectionResetError("reset")) is True  # ConnectionError subclass
    assert _is_browser_dead_exc(RuntimeError("WebSocket is not connected")) is True

    # False: bare OSError and disk/fs subclasses must NOT be browser-dead (CR-02)
    assert _is_browser_dead_exc(OSError("generic OS error")) is False
    assert _is_browser_dead_exc(PermissionError("permission denied")) is False
    assert _is_browser_dead_exc(FileNotFoundError("no such file")) is False
    assert _is_browser_dead_exc(IsADirectoryError("is a dir")) is False

    # False: other non-browser exceptions
    assert _is_browser_dead_exc(RuntimeError("some other error")) is False
    assert _is_browser_dead_exc(ValueError("not a browser error")) is False
    assert _is_browser_dead_exc(TypeError("type error")) is False
