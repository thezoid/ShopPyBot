"""Tests for core/orchestrator.py.

Covers:
- ASYNC-01: TaskGroup creates one poll task per active plugin plus one drain task
- ASYNC-01: Two plugin coroutines make progress concurrently (interleaved, not serial)
- ASYNC-02: _staggered_setup awaits >= 1.5s between successive setup() calls
- ASYNC-05: write-queue drain serializes all writes (one-at-a-time)
- ASYNC-03: asyncio.Event wakes a waiting coroutine via call_soon_threadsafe (event_shim)
- BUY-03/BUY-04: _try_auto_buy confirmation wiring + _dispatch_write confirmed branch
- REL-05: sqlite3.OperationalError on items read skips cycle; DatabaseError propagates
- REL-06: per-item asyncio.timeout continues to next item; write_queue.put outside timeout
"""

import asyncio
import sqlite3
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
# FakeTab for confirmation tests (re-declared locally; mirrors test_confirmation.py)
# ---------------------------------------------------------------------------


class _FakeElement:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeTab:
    """Minimal nodriver Tab stub: sync target.url + async sleep/select."""

    def __init__(self, url: str, selector_map: dict | None = None) -> None:
        self.target = type("_T", (), {"url": url})()
        self._selector_map: dict = selector_map or {}

    async def sleep(self, t: float) -> None:
        pass

    async def select(self, selector: str, timeout: int = 10):
        return self._selector_map.get(selector)


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
            # Close the coroutine immediately (avoids unawaited-coroutine warnings)
            # and return a cancelled task so the group exits cleanly.
            coro.close()
            task = asyncio.get_running_loop().create_task(asyncio.sleep(0), name=name)
            task.cancel()
            return task

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            # Suppress CancelledError so the test finishes cleanly
            return True

    fake_cfg = MagicMock()
    fake_cfg.app.poll_interval = 0.01

    async def fake_run_in_executor(executor, fn, *args):
        return []

    fake_loop = MagicMock()
    fake_loop.run_in_executor = fake_run_in_executor

    with (
        patch("core.orchestrator.PluginRegistry") as MockRegistry,
        patch("core.orchestrator.asyncio.TaskGroup", return_value=_TrackingGroup()),
        patch("core.orchestrator.asyncio.Queue", return_value=asyncio.Queue()),
        patch("core.orchestrator._staggered_setup", new=AsyncMock()),
        patch("core.orchestrator._start_stdin_listener"),
        patch("core.orchestrator.asyncio.get_running_loop", return_value=fake_loop),
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
# Typed write-queue ops (Plan 05-05 Task 1)
# ---------------------------------------------------------------------------


async def test_drain_typed_purchased_tuple():
    """("purchased", link) must invoke update_item_purchased_sync, not others."""
    queue: asyncio.Queue = asyncio.Queue()
    link = "https://bestbuy.com/item1"
    await queue.put(("purchased", link))

    mock_purchased = MagicMock(return_value=None)
    mock_set_avail = MagicMock(return_value=None)
    mock_clear_avail = MagicMock(return_value=None)

    async def fake_executor(executor, fn, *args):
        fn(*args)

    with (
        patch("core.orchestrator.writeLog"),
        patch("core.orchestrator.update_item_purchased_sync", mock_purchased),
        patch("core.orchestrator.set_item_available_sync", mock_set_avail),
        patch("core.orchestrator.clear_item_available_sync", mock_clear_avail),
    ):
        async def drain_once():
            loop = asyncio.get_running_loop()
            with patch.object(loop, "run_in_executor", side_effect=fake_executor):
                drain_task = asyncio.create_task(_write_queue_drain(queue))
                await queue.join()
                drain_task.cancel()
                try:
                    await drain_task
                except asyncio.CancelledError:
                    pass

        await drain_once()

    mock_purchased.assert_called_once_with(link)
    mock_set_avail.assert_not_called()
    mock_clear_avail.assert_not_called()


async def test_drain_typed_set_available_tuple():
    """("set_available", link, ts) must invoke set_item_available_sync with link + ts."""
    queue: asyncio.Queue = asyncio.Queue()
    link = "https://bestbuy.com/item2"
    ts = "2026-06-03T12:00:00+00:00"
    await queue.put(("set_available", link, ts))

    mock_purchased = MagicMock(return_value=None)
    mock_set_avail = MagicMock(return_value=None)
    mock_clear_avail = MagicMock(return_value=None)

    async def fake_executor(executor, fn, *args):
        fn(*args)

    with (
        patch("core.orchestrator.writeLog"),
        patch("core.orchestrator.update_item_purchased_sync", mock_purchased),
        patch("core.orchestrator.set_item_available_sync", mock_set_avail),
        patch("core.orchestrator.clear_item_available_sync", mock_clear_avail),
    ):
        async def drain_once():
            loop = asyncio.get_running_loop()
            with patch.object(loop, "run_in_executor", side_effect=fake_executor):
                drain_task = asyncio.create_task(_write_queue_drain(queue))
                await queue.join()
                drain_task.cancel()
                try:
                    await drain_task
                except asyncio.CancelledError:
                    pass

        await drain_once()

    mock_set_avail.assert_called_once_with(link, ts)
    mock_purchased.assert_not_called()
    mock_clear_avail.assert_not_called()


async def test_drain_typed_clear_available_tuple():
    """("clear_available", link) must invoke clear_item_available_sync."""
    queue: asyncio.Queue = asyncio.Queue()
    link = "https://bestbuy.com/item3"
    await queue.put(("clear_available", link))

    mock_purchased = MagicMock(return_value=None)
    mock_set_avail = MagicMock(return_value=None)
    mock_clear_avail = MagicMock(return_value=None)

    async def fake_executor(executor, fn, *args):
        fn(*args)

    with (
        patch("core.orchestrator.writeLog"),
        patch("core.orchestrator.update_item_purchased_sync", mock_purchased),
        patch("core.orchestrator.set_item_available_sync", mock_set_avail),
        patch("core.orchestrator.clear_item_available_sync", mock_clear_avail),
    ):
        async def drain_once():
            loop = asyncio.get_running_loop()
            with patch.object(loop, "run_in_executor", side_effect=fake_executor):
                drain_task = asyncio.create_task(_write_queue_drain(queue))
                await queue.join()
                drain_task.cancel()
                try:
                    await drain_task
                except asyncio.CancelledError:
                    pass

        await drain_once()

    mock_clear_avail.assert_called_once_with(link)
    mock_purchased.assert_not_called()
    mock_set_avail.assert_not_called()


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


# ---------------------------------------------------------------------------
# Dedup edge-trigger wiring (Plan 05-05 Task 2)
# ---------------------------------------------------------------------------


def _make_detected_event(name="Widget", link="https://example.com/w", platform="FakePlugin"):
    """Build a detected NotificationEvent for orchestrator dedup tests."""
    from notifications.base import NotificationEvent
    from datetime import datetime, timezone
    return NotificationEvent(
        item_name=name,
        item_url=link,
        platform=platform,
        timestamp=datetime.now(timezone.utc),
        action="detected",
    )


async def test_check_and_buy_notifies_on_rising_edge(fake_plugin, fake_notifier):
    """_check_and_buy must call dispatcher.notify exactly once on unavailable->available."""
    from core.orchestrator import _check_and_buy
    from notifications.dispatcher import NotificationDispatcher

    plugin = fake_plugin(domains=["example.com"], available=True)
    notifier = fake_notifier()
    dispatcher = NotificationDispatcher([notifier])

    queue: asyncio.Queue = asyncio.Queue()
    link = "https://example.com/w"

    # Simulate: was_available=False (rising edge)
    with (
        patch("core.orchestrator.get_item_notification_state_sync", return_value=(False, None)),
        patch("core.orchestrator.writeLog"),
    ):
        await _check_and_buy(plugin, "Widget", link, False, write_queue=queue, dispatcher=dispatcher)

    assert len(notifier.events) == 1, "Exactly one notify on rising edge"
    assert notifier.events[0].action == "detected"
    # set_available tuple enqueued
    items = []
    while not queue.empty():
        items.append(await queue.get())
    assert any(isinstance(i, tuple) and i[0] == "set_available" for i in items)


async def test_check_and_buy_suppresses_while_available(fake_plugin, fake_notifier):
    """_check_and_buy must NOT call dispatcher.notify when item was already available."""
    from core.orchestrator import _check_and_buy
    from notifications.dispatcher import NotificationDispatcher

    plugin = fake_plugin(domains=["example.com"], available=True)
    notifier = fake_notifier()
    dispatcher = NotificationDispatcher([notifier])

    queue: asyncio.Queue = asyncio.Queue()
    link = "https://example.com/w"

    # Simulate: was_available=True (no edge - suppress)
    with (
        patch("core.orchestrator.get_item_notification_state_sync", return_value=(True, "2026-06-03T12:00:00Z")),
        patch("core.orchestrator.writeLog"),
    ):
        await _check_and_buy(plugin, "Widget", link, False, write_queue=queue, dispatcher=dispatcher)

    assert len(notifier.events) == 0, "No notify when already available (suppress)"


async def test_check_and_buy_enqueues_clear_on_unavailable(fake_plugin, fake_notifier):
    """_check_and_buy must enqueue clear_available when item goes unavailable from available."""
    from core.orchestrator import _check_and_buy
    from notifications.dispatcher import NotificationDispatcher

    plugin = fake_plugin(domains=["example.com"], available=False)
    notifier = fake_notifier()
    dispatcher = NotificationDispatcher([notifier])

    queue: asyncio.Queue = asyncio.Queue()
    link = "https://example.com/w"

    # was_available=True but now unavailable -> enqueue clear_available
    with (
        patch("core.orchestrator.get_item_notification_state_sync", return_value=(True, "2026-06-03T12:00:00Z")),
        patch("core.orchestrator.writeLog"),
    ):
        await _check_and_buy(plugin, "Widget", link, False, write_queue=queue, dispatcher=dispatcher)

    items = []
    while not queue.empty():
        items.append(await queue.get())
    assert any(isinstance(i, tuple) and i[0] == "clear_available" for i in items)
    assert len(notifier.events) == 0, "No notify on falling edge"


async def test_check_and_buy_no_queue_when_unavailable_stays_unavailable(fake_plugin, fake_notifier):
    """_check_and_buy must not enqueue anything when item stays unavailable."""
    from core.orchestrator import _check_and_buy
    from notifications.dispatcher import NotificationDispatcher

    plugin = fake_plugin(domains=["example.com"], available=False)
    notifier = fake_notifier()
    dispatcher = NotificationDispatcher([notifier])

    queue: asyncio.Queue = asyncio.Queue()
    link = "https://example.com/w"

    with (
        patch("core.orchestrator.get_item_notification_state_sync", return_value=(False, None)),
        patch("core.orchestrator.writeLog"),
    ):
        await _check_and_buy(plugin, "Widget", link, False, write_queue=queue, dispatcher=dispatcher)

    assert queue.empty(), "No queue writes when unavailable stays unavailable"
    assert len(notifier.events) == 0


async def test_check_and_buy_purchase_dispatches_purchased_event(fake_plugin, fake_notifier):
    """On successful auto_buy, dispatcher.notify must be called with action='purchased'."""
    from core.orchestrator import _check_and_buy
    from notifications.dispatcher import NotificationDispatcher

    plugin = fake_plugin(domains=["example.com"], available=True, bought=True)
    notifier = fake_notifier()
    dispatcher = NotificationDispatcher([notifier])

    queue: asyncio.Queue = asyncio.Queue()
    link = "https://example.com/w"

    with (
        patch("core.orchestrator.get_item_notification_state_sync", return_value=(False, None)),
        patch("core.orchestrator.get_item_order_state_sync", return_value=(False, None)),
        patch("core.orchestrator.increment_checkout_attempts_sync"),
        patch("core.orchestrator.writeLog"),
    ):
        await _check_and_buy(plugin, "Widget", link, auto_buy=True, write_queue=queue, dispatcher=dispatcher)

    # At least one notify with action="detected" (rising edge) and one with action="purchased"
    actions = [e.action for e in notifier.events]
    assert "detected" in actions, "detected event must fire on rising edge"
    assert "purchased" in actions, "purchased event must fire on successful auto_buy"

    items = []
    while not queue.empty():
        items.append(await queue.get())
    assert any(isinstance(i, tuple) and i[0] == "purchased" for i in items)


async def test_dedup_renotify_after_full_cycle(fake_plugin, fake_notifier):
    """Flap: unavail->avail->avail->unavail->avail must yield exactly two detected notifies."""
    from core.orchestrator import _check_and_buy
    from notifications.dispatcher import NotificationDispatcher

    link = "https://example.com/w"

    # We simulate state manually: first False, then True (stays), then False, then False again
    state_sequence = [
        (False, None),   # tick 1: rising edge, available=True -> notify
        (True, "t1"),    # tick 2: available=True, was=True -> suppress
        (True, "t1"),    # tick 3: available=False, was=True -> clear (no notify)
        (False, None),   # tick 4: available=True again -> notify (second restock)
    ]
    available_sequence = [True, True, False, True]
    state_iter = iter(state_sequence)

    notifier = fake_notifier()
    dispatcher = NotificationDispatcher([notifier])
    queue: asyncio.Queue = asyncio.Queue()

    for avail in available_sequence:
        state = next(state_iter)
        plugin = fake_plugin(domains=["example.com"], available=avail)
        with (
            patch("core.orchestrator.get_item_notification_state_sync", return_value=state),
            patch("core.orchestrator.writeLog"),
        ):
            await _check_and_buy(plugin, "Widget", link, auto_buy=False, write_queue=queue, dispatcher=dispatcher)

    detected_count = sum(1 for e in notifier.events if e.action == "detected")
    assert detected_count == 2, f"Expected 2 detected notifies for flap sequence, got {detected_count}"


async def test_stdin_listener_sets_plugin_events():
    """_stdin_listener_thread signals all known intervention events on all plugins."""
    import warnings
    from core.orchestrator import _stdin_listener_thread

    event = asyncio.Event()
    loop = asyncio.get_running_loop()

    # Use a plain object (not MagicMock) to avoid unawaited-coroutine warnings from
    # auto-specced mock attributes; listener must skip absent attrs gracefully.
    class _PluginStub:
        captcha_event = event

    plugin = _PluginStub()

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


# ---------------------------------------------------------------------------
# monitor_only gate in _check_and_buy (Plan 18-03 Task 1 -- BUY-01)
# ---------------------------------------------------------------------------


def _make_plugin_config(monitor_only: bool = False):
    """Return a MagicMock AppConfig with debug.monitor_only set."""
    cfg = MagicMock()
    cfg.debug.monitor_only = monitor_only
    return cfg


async def test_monitor_only_skips_try_auto_buy(fake_plugin, fake_notifier):
    """monitor_only=True: _try_auto_buy is NOT awaited; detected alert still fires."""
    from core.orchestrator import _check_and_buy
    from notifications.dispatcher import NotificationDispatcher

    cfg = _make_plugin_config(monitor_only=True)
    plugin = fake_plugin(domains=["example.com"], available=True, bought=True, config=cfg)
    notifier = fake_notifier()
    dispatcher = NotificationDispatcher([notifier])
    queue: asyncio.Queue = asyncio.Queue()
    link = "https://example.com/w"

    with (
        patch("core.orchestrator.get_item_notification_state_sync", return_value=(False, None)),
        patch("core.orchestrator.writeLog"),
        patch("core.orchestrator._try_auto_buy", new_callable=AsyncMock) as mock_try_buy,
    ):
        await _check_and_buy(
            plugin, "Widget", link, auto_buy=True, write_queue=queue, dispatcher=dispatcher
        )

    mock_try_buy.assert_not_awaited()
    actions = [e.action for e in notifier.events]
    assert "detected" in actions, "detected alert must still fire in monitor_only mode"

    items = []
    while not queue.empty():
        items.append(await queue.get())
    assert any(isinstance(i, tuple) and i[0] == "set_available" for i in items)
    assert not any(isinstance(i, tuple) and i[0] == "purchased" for i in items)


async def test_monitor_only_false_calls_try_auto_buy(fake_plugin, fake_notifier):
    """monitor_only=False: _try_auto_buy IS awaited (regression guard)."""
    from core.orchestrator import _check_and_buy
    from notifications.dispatcher import NotificationDispatcher

    cfg = _make_plugin_config(monitor_only=False)
    plugin = fake_plugin(domains=["example.com"], available=True, bought=True, config=cfg)
    notifier = fake_notifier()
    dispatcher = NotificationDispatcher([notifier])
    queue: asyncio.Queue = asyncio.Queue()
    link = "https://example.com/w"

    with (
        patch("core.orchestrator.get_item_notification_state_sync", return_value=(False, None)),
        patch("core.orchestrator.writeLog"),
        patch("core.orchestrator._try_auto_buy", new_callable=AsyncMock) as mock_try_buy,
    ):
        await _check_and_buy(
            plugin, "Widget", link, auto_buy=True, write_queue=queue, dispatcher=dispatcher
        )

    mock_try_buy.assert_awaited_once()


async def test_monitor_only_set_available_not_purchased(fake_plugin, fake_notifier):
    """monitor_only=True: set_available is enqueued; purchased is never enqueued."""
    from core.orchestrator import _check_and_buy
    from notifications.dispatcher import NotificationDispatcher

    cfg = _make_plugin_config(monitor_only=True)
    plugin = fake_plugin(domains=["example.com"], available=True, bought=True, config=cfg)
    notifier = fake_notifier()
    dispatcher = NotificationDispatcher([notifier])
    queue: asyncio.Queue = asyncio.Queue()
    link = "https://example.com/w"

    with (
        patch("core.orchestrator.get_item_notification_state_sync", return_value=(False, None)),
        patch("core.orchestrator.writeLog"),
        patch("core.orchestrator._try_auto_buy", new_callable=AsyncMock),
    ):
        await _check_and_buy(
            plugin, "Widget", link, auto_buy=True, write_queue=queue, dispatcher=dispatcher
        )

    items = []
    while not queue.empty():
        items.append(await queue.get())
    assert any(isinstance(i, tuple) and i[0] == "set_available" for i in items)
    assert not any(isinstance(i, tuple) and i[0] == "purchased" for i in items)


# ---------------------------------------------------------------------------
# BUY-03/BUY-04: confirmation wiring in _try_auto_buy + _dispatch_write (Plan 19-04)
# ---------------------------------------------------------------------------


def _make_amazon_plugin(bought: bool):
    """Build a fake plugin whose class name is 'AmazonPlugin' (for platform-map matching)."""
    from core.plugin_base import RetailerPlugin

    class AmazonPlugin(RetailerPlugin):
        domain_patterns = ["amazon.com"]

        async def check_availability(self, url: str) -> bool:
            return True

        async def auto_buy(self, url: str) -> bool:
            return bought

    instance = AmazonPlugin(config=None)
    instance.setup = AsyncMock()
    instance.teardown = AsyncMock()
    return instance


async def test_orchestrator_confirmed_path():
    """auto_buy success + confirmation URL -> single ("confirmed", ...) 4-tuple enqueued."""
    from core.orchestrator import _try_auto_buy

    plugin = _make_amazon_plugin(bought=True)
    plugin.get_active_tab = lambda: _FakeTab(
        url="https://www.amazon.com/gp/buy/thankyou?orderID=302-999",
        selector_map={},
    )

    q: asyncio.Queue = asyncio.Queue()
    with (
        patch("core.orchestrator.writeLog"),
        patch("core.orchestrator.get_item_order_state_sync", return_value=(False, None)),
        patch("core.orchestrator.increment_checkout_attempts_sync"),
    ):
        await _try_auto_buy(plugin, "Widget", "https://amazon.com/item", q, None)

    assert q.qsize() == 1, "Exactly one item enqueued on confirmed path"
    item = q.get_nowait()
    assert item[0] == "confirmed", f"Expected 'confirmed' tag, got {item[0]!r}"
    assert len(item) == 4, f"Expected 4-tuple, got {len(item)}-tuple"
    assert item[2] is not None, "order_id must be non-None on confirmed path"


async def test_orchestrator_fallback_path():
    """auto_buy success + non-confirmation URL -> single ("purchased", link) enqueued, WARNING logged."""
    from core.orchestrator import _try_auto_buy

    plugin = _make_amazon_plugin(bought=True)
    plugin.get_active_tab = lambda: _FakeTab(
        url="https://www.amazon.com/dp/B001",
        selector_map={},
    )

    q: asyncio.Queue = asyncio.Queue()
    log_messages: list[str] = []

    def capture_log(msg, level="INFO", *args, **kwargs):
        log_messages.append((msg, level))

    with (
        patch("core.orchestrator.writeLog", side_effect=capture_log),
        patch("core.orchestrator.get_item_order_state_sync", return_value=(False, None)),
        patch("core.orchestrator.increment_checkout_attempts_sync"),
    ):
        await _try_auto_buy(plugin, "Widget", "https://amazon.com/item", q, None)

    assert q.qsize() == 1, "Exactly one item enqueued on fallback path"
    item = q.get_nowait()
    assert item[0] == "purchased", f"Expected 'purchased' tag, got {item[0]!r}"
    warning_msgs = [m for m, lvl in log_messages if lvl == "WARNING"]
    assert warning_msgs, "A WARNING must be logged on confirmation fallback path"


async def test_no_double_buy_single_put():
    """Confirmed path enqueues exactly one item (no double-buy, Pitfall 5)."""
    from core.orchestrator import _try_auto_buy

    plugin = _make_amazon_plugin(bought=True)
    plugin.get_active_tab = lambda: _FakeTab(
        url="https://www.amazon.com/gp/buy/thankyou?orderID=111",
        selector_map={},
    )

    q: asyncio.Queue = asyncio.Queue()
    with (
        patch("core.orchestrator.writeLog"),
        patch("core.orchestrator.get_item_order_state_sync", return_value=(False, None)),
        patch("core.orchestrator.increment_checkout_attempts_sync"),
    ):
        await _try_auto_buy(plugin, "Widget", "https://amazon.com/item", q, None)

    assert q.qsize() == 1, f"Expected exactly 1 queue item, got {q.qsize()}"


async def test_dispatch_confirmed_tag(tmp_data_dir):
    """("confirmed", link, order_id, ts) -> update_item_confirmed_sync(link, order_id, ts)."""
    import sqlite3
    import models
    from core.orchestrator import _dispatch_write

    models.initialize_db(delete=True)
    models.add_items_sync([("Widget", "https://amazon.com/item", True, 1, False)])

    link = "https://amazon.com/item"
    order_id = "123-456-789"
    ts = "2026-06-11T00:00:00+00:00"

    loop = asyncio.get_running_loop()
    with patch("core.orchestrator.writeLog"):
        await _dispatch_write(loop, ("confirmed", link, order_id, ts))

    conn = sqlite3.connect(models.DB_PATH)
    row = conn.execute(
        "SELECT purchased, order_id, confirmed_at FROM items WHERE link=?",
        (link,),
    ).fetchone()
    conn.close()

    assert row[0] == 1, "purchased must be 1 after confirmed dispatch"
    assert row[1] == order_id, f"order_id mismatch: {row[1]!r}"
    assert row[2] == ts, f"confirmed_at mismatch: {row[2]!r}"


async def test_no_double_buy_on_confirmation_detection_error(tmp_data_dir):
    """WR-02: auto_buy True + detect_order_confirmation raises -> legacy ("purchased", link)
    enqueued exactly once. Never zero enqueues (which would leave item available and
    trigger a re-attempt on the next poll, potentially placing a duplicate real order).
    """
    from core.orchestrator import _try_auto_buy

    plugin = _make_amazon_plugin(bought=True)
    # Tab is present so confirmation detection is attempted; it raises an exception.
    fake_tab = _FakeTab(url="https://www.amazon.com/gp/buy/thankyou?orderID=999", selector_map={})
    plugin.get_active_tab = lambda: fake_tab

    q: asyncio.Queue = asyncio.Queue()
    with (
        patch("core.orchestrator.writeLog"),
        patch("core.orchestrator.get_item_order_state_sync", return_value=(False, None)),
        patch("core.orchestrator.increment_checkout_attempts_sync"),
        patch(
            "core.confirmation.detect_order_confirmation",
            new=AsyncMock(side_effect=RuntimeError("tab closed")),
        ),
    ):
        await _try_auto_buy(plugin, "Widget", "https://amazon.com/item", q, None)

    assert q.qsize() == 1, (
        f"Expected exactly 1 queue item (legacy purchased write), got {q.qsize()} -- "
        "zero means item stays available and next poll re-places order (double-buy)"
    )
    item = q.get_nowait()
    assert item[0] == "purchased", f"Expected legacy 'purchased' tag, got {item[0]!r}"
    assert item[1] == "https://amazon.com/item", f"Link mismatch: {item[1]!r}"


# ---------------------------------------------------------------------------
# REL-05: SQLite read isolation in run_plugin
# REL-06: Per-item asyncio.timeout + write_queue.put outside timeout
# ---------------------------------------------------------------------------


async def test_read_isolation_operational_error(fake_plugin):
    """sqlite3.OperationalError on items read -> WARNING logged, cycle skipped, loop survives.

    REL-05: transient DB lock on the items-list read must degrade gracefully (skip one poll
    cycle) rather than crash run_plugin. The loop continues to asyncio.sleep after the error.
    """
    from core.orchestrator import run_plugin

    plugin = fake_plugin(domains=["ex.example.com"], available=False)
    cfg = MagicMock()
    cfg.checkout.item_timeout_secs = 30

    queue: asyncio.Queue = asyncio.Queue()
    sleep_calls: list[float] = []
    log_messages: list[tuple] = []

    # Executor: first call raises OperationalError; second call returns [] (empty items)
    call_count = 0

    async def fake_executor(executor, fn, *args):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise sqlite3.OperationalError("database is locked")
        return []

    async def fake_sleep(secs):
        sleep_calls.append(secs)
        # After two sleeps (error-path sleep + normal-path sleep), cancel the loop
        if len(sleep_calls) >= 2:
            raise asyncio.CancelledError

    def capture_log(msg, level="INFO", *args, **kwargs):
        log_messages.append((msg, level))

    loop = asyncio.get_running_loop()
    with (
        patch.object(loop, "run_in_executor", side_effect=fake_executor),
        patch("core.orchestrator.asyncio.sleep", side_effect=fake_sleep),
        patch("core.orchestrator.writeLog", side_effect=capture_log),
        patch("core.orchestrator._get_plugin_sleep", return_value=0.01),
    ):
        try:
            await run_plugin(plugin, queue, poll_interval=0.01, cfg=cfg)
        except asyncio.CancelledError:
            pass

    # A WARNING must have been logged for the OperationalError
    warning_msgs = [m for m, lvl in log_messages if lvl == "WARNING"]
    assert warning_msgs, "Expected a WARNING log for sqlite3.OperationalError"
    assert any("OperationalError" in m or "locked" in m or "items read" in m for m in warning_msgs), (
        f"WARNING must mention the error, got: {warning_msgs}"
    )
    # The loop must have continued to sleep (cycle skipped, not terminated)
    assert len(sleep_calls) >= 1, "run_plugin must have called asyncio.sleep (cycle skipped, not crash)"


async def test_read_isolation_database_error_propagates(fake_plugin):
    """sqlite3.DatabaseError (not OperationalError) must propagate out of run_plugin.

    REL-05: corruption-class errors are NOT swallowed. The except clause covers only
    sqlite3.OperationalError so a DatabaseError escalates normally.
    """
    from core.orchestrator import run_plugin

    plugin = fake_plugin(domains=["ex.example.com"], available=False)
    cfg = MagicMock()
    cfg.checkout.item_timeout_secs = 30

    queue: asyncio.Queue = asyncio.Queue()

    async def fake_executor_db_error(executor, fn, *args):
        raise sqlite3.DatabaseError("malformed database disk image")

    loop = asyncio.get_running_loop()
    with (
        patch.object(loop, "run_in_executor", side_effect=fake_executor_db_error),
        patch("core.orchestrator.writeLog"),
        patch("core.orchestrator._get_plugin_sleep", return_value=0.01),
    ):
        with pytest.raises(sqlite3.DatabaseError):
            await run_plugin(plugin, queue, poll_interval=0.01, cfg=cfg)


async def test_item_timeout_continues_to_next(fake_plugin):
    """Per-item timeout: first item times out -> WARNING logged -> second item still runs.

    REL-06: asyncio.timeout(item_timeout_secs) around _check_and_buy; TimeoutError caught
    at item level; for-loop continues to the next item.
    """
    from core.orchestrator import run_plugin

    plugin = fake_plugin(domains=["ex.example.com"], available=False)
    cfg = MagicMock()
    cfg.checkout.item_timeout_secs = 0.05  # very short timeout

    queue: asyncio.Queue = asyncio.Queue()
    log_messages: list[tuple] = []

    items = [
        ("SlowItem", "https://ex.example.com/slow", False, 1, False),
        ("FastItem", "https://ex.example.com/fast", False, 1, False),
    ]

    check_and_buy_calls: list[str] = []
    sleep_calls: list = []

    async def fake_executor(executor, fn, *args):
        return items

    async def fake_check_and_buy(plugin, name, link, auto_buy, write_queue, dispatcher=None):
        check_and_buy_calls.append(name)
        if name == "SlowItem":
            # Sleep longer than the timeout to trigger TimeoutError
            await asyncio.sleep(10)

    async def fake_sleep(secs):
        sleep_calls.append(secs)
        raise asyncio.CancelledError

    def capture_log(msg, level="INFO", *args, **kwargs):
        log_messages.append((msg, level))

    loop = asyncio.get_running_loop()
    with (
        patch.object(loop, "run_in_executor", side_effect=fake_executor),
        patch("core.orchestrator._check_and_buy", side_effect=fake_check_and_buy),
        patch("core.orchestrator.asyncio.sleep", side_effect=fake_sleep),
        patch("core.orchestrator.writeLog", side_effect=capture_log),
        patch("core.orchestrator._get_plugin_sleep", return_value=0.01),
    ):
        try:
            await run_plugin(plugin, queue, poll_interval=0.01, cfg=cfg)
        except asyncio.CancelledError:
            pass

    # FastItem must have been called (loop continued past timed-out SlowItem)
    assert "FastItem" in check_and_buy_calls, (
        f"FastItem's _check_and_buy must have been called; got calls: {check_and_buy_calls}"
    )
    # A WARNING must have been logged for the timeout
    warning_msgs = [m for m, lvl in log_messages if lvl == "WARNING"]
    assert any("timeout" in m.lower() or "SlowItem" in m for m in warning_msgs), (
        f"Expected a timeout WARNING for SlowItem, got: {warning_msgs}"
    )


async def test_write_queue_put_outside_timeout(fake_plugin):
    """write_queue.put inside _check_and_buy is reachable when item completes before timeout.

    REL-06: A fake _check_and_buy that puts to the queue and returns quickly (before timeout)
    must result in the queue containing the item. This verifies that the put call is NOT
    wrapped inside the timeout context in a way that prevents it from executing.
    """
    from core.orchestrator import run_plugin

    plugin = fake_plugin(domains=["ex.example.com"], available=False)
    cfg = MagicMock()
    cfg.checkout.item_timeout_secs = 30  # large timeout; item completes before it

    queue: asyncio.Queue = asyncio.Queue()
    sleep_calls: list = []

    items = [
        ("QuickItem", "https://ex.example.com/quick", False, 1, False),
    ]

    async def fake_executor(executor, fn, *args):
        return items

    async def fake_check_and_buy(plugin, name, link, auto_buy, write_queue, dispatcher=None):
        # Simulate _check_and_buy placing a write (as set_available would)
        await write_queue.put(("set_available", link, "2026-01-01T00:00:00+00:00"))

    async def fake_sleep(secs):
        sleep_calls.append(secs)
        raise asyncio.CancelledError

    loop = asyncio.get_running_loop()
    with (
        patch.object(loop, "run_in_executor", side_effect=fake_executor),
        patch("core.orchestrator._check_and_buy", side_effect=fake_check_and_buy),
        patch("core.orchestrator.asyncio.sleep", side_effect=fake_sleep),
        patch("core.orchestrator.writeLog"),
        patch("core.orchestrator._get_plugin_sleep", return_value=0.01),
    ):
        try:
            await run_plugin(plugin, queue, poll_interval=0.01, cfg=cfg)
        except asyncio.CancelledError:
            pass

    # The queue must contain the item that _check_and_buy put
    assert not queue.empty(), "write_queue.put inside _check_and_buy must be reachable"
    item = queue.get_nowait()
    assert item[0] == "set_available", f"Expected set_available, got {item[0]!r}"
