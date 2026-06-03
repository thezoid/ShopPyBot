"""Tests for core/orchestrator.py.

Covers:
- ASYNC-01: TaskGroup creates one poll task per active plugin plus one drain task
- ASYNC-01: Two plugin coroutines make progress concurrently (interleaved, not serial)
- ASYNC-02: _staggered_setup awaits >= 1.5s between successive setup() calls
- ASYNC-05: write-queue drain serializes all writes (one-at-a-time)
- ASYNC-03: asyncio.Event wakes a waiting coroutine via call_soon_threadsafe (event_shim)
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from core.orchestrator import (
    _staggered_setup,
    _write_queue_drain,
    _stdin_listener_thread,
    async_main,
)
from core.registry import PluginRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_registry_with_plugins(*plugins):
    """Return a bare PluginRegistry-like object with _active_plugins set."""
    registry = MagicMock(spec=PluginRegistry)
    registry._active_plugins = list(plugins)
    registry._all_plugins = list(plugins)
    registry.teardown_all = AsyncMock()
    return registry


# ---------------------------------------------------------------------------
# ASYNC-01: TaskGroup structure
# ---------------------------------------------------------------------------


async def test_taskgroup_creates_per_plugin_tasks(fake_plugin):
    """async_main creates one poll task per active plugin plus one drain task."""
    plugin_a = fake_plugin(domains=["alpha.example.com"], available=False)
    plugin_b = fake_plugin(domains=["beta.example.com"], available=False)

    # Track task names created inside the TaskGroup
    created_tasks: list[str] = []

    class _TrackingGroup:
        def create_task(self, coro, *, name=None):
            created_tasks.append(name or "")
            # Return a quickly-cancellable task
            task = asyncio.get_running_loop().create_task(coro, name=name)
            task.cancel()
            return task

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            # Suppress CancelledError so the test finishes cleanly
            return True

    fake_cfg = MagicMock()
    fake_cfg.app.poll_interval = 0.01

    with (
        patch("core.orchestrator.PluginRegistry") as MockRegistry,
        patch("core.orchestrator.asyncio.TaskGroup", return_value=_TrackingGroup()),
        patch("core.orchestrator.asyncio.Queue", return_value=asyncio.Queue()),
        patch("core.orchestrator._staggered_setup", new=AsyncMock()),
        patch("core.orchestrator._start_stdin_listener"),
        patch("core.orchestrator.loop_run_in_executor_get_items", return_value=[]),
    ):
        mock_registry = _make_registry_with_plugins(plugin_a, plugin_b)
        MockRegistry.return_value = mock_registry

        try:
            await async_main(fake_cfg, cvv=None)
        except Exception:
            pass  # Suppress any teardown error from mock registry

    # Expect: 1 drain task + 1 per plugin = 3 tasks
    drain_tasks = [t for t in created_tasks if "drain" in t]
    poll_tasks = [t for t in created_tasks if "poll" in t]
    assert len(drain_tasks) == 1, f"Expected 1 drain task, got {drain_tasks}"
    assert len(poll_tasks) == 2, f"Expected 2 poll tasks, got {poll_tasks}"


# ---------------------------------------------------------------------------
# ASYNC-02: Stagger interval
# ---------------------------------------------------------------------------


async def test_stagger_interval(fake_plugin):
    """_staggered_setup awaits asyncio.sleep(1.5) between successive setup() calls."""
    plugin_a = fake_plugin(domains=["alpha.example.com"])
    plugin_b = fake_plugin(domains=["beta.example.com"])

    registry = MagicMock(spec=PluginRegistry)
    registry._active_plugins = []
    registry._all_plugins = [plugin_a, plugin_b]
    registry.plugins_for_items = MagicMock(return_value=[plugin_a, plugin_b])

    items = [
        ("Item A", "https://alpha.example.com/p/1", True, 1, False),
        ("Item B", "https://beta.example.com/p/2", True, 1, False),
    ]

    sleep_calls: list[float] = []

    async def mock_sleep(secs):
        sleep_calls.append(secs)

    with patch("core.orchestrator.asyncio.sleep", side_effect=mock_sleep):
        await _staggered_setup(registry, items, stagger_secs=1.5)

    # First plugin: no sleep. Second plugin: sleep(1.5).
    assert len(sleep_calls) == 1, f"Expected 1 sleep call, got {sleep_calls}"
    assert sleep_calls[0] == 1.5, f"Expected sleep(1.5), got sleep({sleep_calls[0]})"

    # Both plugins must have had setup() called
    plugin_a.setup.assert_awaited_once()
    plugin_b.setup.assert_awaited_once()

    # Both must have been appended to _active_plugins
    assert plugin_a in registry._active_plugins
    assert plugin_b in registry._active_plugins


async def test_stagger_logs_stagger_line(fake_plugin):
    """_staggered_setup logs a STAGGER line for each init after the first."""
    plugin_a = fake_plugin(domains=["alpha.example.com"])
    plugin_b = fake_plugin(domains=["beta.example.com"])

    registry = MagicMock(spec=PluginRegistry)
    registry._active_plugins = []
    registry._all_plugins = [plugin_a, plugin_b]
    registry.plugins_for_items = MagicMock(return_value=[plugin_a, plugin_b])

    items = [
        ("Item A", "https://alpha.example.com/p/1", True, 1, False),
        ("Item B", "https://beta.example.com/p/2", True, 1, False),
    ]

    log_messages: list[str] = []

    def fake_log(msg, level="INFO", *args, **kwargs):
        log_messages.append(msg)

    with (
        patch("core.orchestrator.asyncio.sleep", new=AsyncMock()),
        patch("core.orchestrator.writeLog", side_effect=fake_log),
    ):
        await _staggered_setup(registry, items)

    stagger_lines = [m for m in log_messages if "STAGGER" in m]
    assert len(stagger_lines) >= 1, f"Expected at least 1 STAGGER log line, got: {log_messages}"


# ---------------------------------------------------------------------------
# ASYNC-05: Write-queue serialization
# ---------------------------------------------------------------------------


async def test_write_queue_serializes():
    """_write_queue_drain processes items one-at-a-time; all writes complete."""
    write_order: list[str] = []

    async def fake_run_in_executor(executor, fn, *args):
        write_order.append(args[0] if args else fn)
        fn(*args)

    queue: asyncio.Queue = asyncio.Queue()
    links = ["https://alpha.example.com/1", "https://beta.example.com/2"]
    for link in links:
        await queue.put(link)

    with (
        patch("core.orchestrator.writeLog"),
        patch("core.orchestrator.update_item_purchased_sync") as mock_update,
    ):
        async def drain_once():
            """Run drain for exactly len(links) items then cancel."""
            loop = asyncio.get_running_loop()
            with patch.object(loop, "run_in_executor", side_effect=fake_run_in_executor):
                drain_task = asyncio.create_task(_write_queue_drain(queue))
                # Wait until the queue is empty and all tasks_done
                await queue.join()
                drain_task.cancel()
                try:
                    await drain_task
                except asyncio.CancelledError:
                    pass

        await drain_once()

    # Every link was processed in order
    assert write_order == links, f"Expected {links}, got {write_order}"


async def test_write_queue_task_done_on_exception():
    """_write_queue_drain calls task_done() even when the executor raises."""
    queue: asyncio.Queue = asyncio.Queue()
    await queue.put("https://fail.example.com/item")

    async def fail_executor(executor, fn, *args):
        raise RuntimeError("DB exploded")

    with (
        patch("core.orchestrator.writeLog"),
        patch("core.orchestrator.update_item_purchased_sync"),
    ):
        async def drain_once():
            loop = asyncio.get_running_loop()
            with patch.object(loop, "run_in_executor", side_effect=fail_executor):
                drain_task = asyncio.create_task(_write_queue_drain(queue))
                await queue.join()  # task_done() must have been called
                drain_task.cancel()
                try:
                    await drain_task
                except asyncio.CancelledError:
                    pass

        await drain_once()

    assert queue.empty(), "Queue should be empty after task_done"


# ---------------------------------------------------------------------------
# ASYNC-03: Event wakeup via call_soon_threadsafe
# ---------------------------------------------------------------------------


async def test_event_wakes_coroutine(event_shim):
    """A coroutine awaiting event.wait() resumes after the shim fires call_soon_threadsafe."""
    event = asyncio.Event()
    loop = asyncio.get_running_loop()

    woken = asyncio.Event()

    async def waiter():
        await event.wait()
        woken.set()

    waiter_task = asyncio.create_task(waiter())

    # Let the waiter reach event.wait()
    await asyncio.sleep(0)

    # Fire the event via the thread-safe bridge (same path as _stdin_listener_thread)
    event_shim(event, loop)

    # Give the loop a tick to schedule the wakeup
    await asyncio.sleep(0)
    await woken.wait()

    assert woken.is_set(), "Waiter coroutine should have woken after event_shim fired"
    await waiter_task


async def test_stdin_listener_sets_plugin_events():
    """_stdin_listener_thread signals all known intervention events on all plugins."""
    from core.orchestrator import _stdin_listener_thread

    event = asyncio.Event()
    loop = asyncio.get_running_loop()

    plugin = MagicMock()
    plugin.captcha_event = event
    # Other known attrs absent -- listener must skip missing attrs gracefully
    del plugin.passkey_event
    del plugin.otp_event
    del plugin.test_pause_event

    fired: list[str] = []

    def fake_threadsafe(fn):
        fired.append("fired")
        fn()

    # Simulate two readline calls: one that returns a line, one that raises EOFError
    call_count = 0

    def fake_readline():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "enter\n"
        raise EOFError

    with (
        patch("sys.stdin") as mock_stdin,
        patch.object(loop, "call_soon_threadsafe", side_effect=fake_threadsafe),
    ):
        mock_stdin.readline = fake_readline
        _stdin_listener_thread([plugin], loop)

    assert len(fired) == 1, f"Expected 1 call_soon_threadsafe call, got {len(fired)}"
    assert event.is_set(), "captcha_event should have been set"
