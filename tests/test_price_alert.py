"""Phase 16 Plan 03: Price alert integration tests.

Tests for:
- _check_price_triggers (absolute target + percentage drop)
- _evaluate_price_triggers (dedup + disarm)
- _build_price_drop_event (payload)
- _pct_from_target, _cents_to_display, _pct_drop_from_last (pure helpers)
- last-price-before-append call order
- startup config seeding (update_item_price_config_sync)
- BotService.get_price_history accessor
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Pure math helpers
# ---------------------------------------------------------------------------


def test_pct_from_target_and_cents_display():
    """_pct_from_target and _cents_to_display compute correctly."""
    from core.orchestrator import _pct_from_target, _cents_to_display

    assert _pct_from_target(4500, 5000) == 10.0
    assert _pct_from_target(5000, 5000) == 0.0
    assert _pct_from_target(5500, 5000) == 0.0

    assert _cents_to_display(4999) == "$49.99"
    assert _cents_to_display(100) == "$1.00"
    assert _cents_to_display(0) == "$0.00"


def test_pct_drop_from_last():
    """_pct_drop_from_last computes correctly."""
    from core.orchestrator import _pct_drop_from_last

    assert _pct_drop_from_last(4500, 5000) == 10.0
    assert _pct_drop_from_last(5000, 5000) == 0.0
    assert _pct_drop_from_last(5500, 5000) == 0.0


# ---------------------------------------------------------------------------
# _check_price_triggers
# ---------------------------------------------------------------------------


def test_check_price_triggers_absolute():
    """_check_price_triggers fires when price_cents <= target_price."""
    from core.orchestrator import _check_price_triggers

    # At target
    assert _check_price_triggers(5000, 5000, None, None) is True
    # Below target
    assert _check_price_triggers(4500, 5000, None, None) is True
    # Above target: no fire
    assert _check_price_triggers(5001, 5000, None, None) is False
    # target_price None: no fire
    assert _check_price_triggers(100, None, None, None) is False


def test_check_price_triggers_pct_drop():
    """_check_price_triggers fires when drop from last price >= price_drop_pct."""
    from core.orchestrator import _check_price_triggers

    # 10% drop from 5000 to 4500, threshold 10.0: fire
    assert _check_price_triggers(4500, None, 10.0, 5000) is True
    # Only 5% drop, threshold 10.0: no fire
    assert _check_price_triggers(4750, None, 10.0, 5000) is False
    # Price increase: no fire
    assert _check_price_triggers(5500, None, 10.0, 5000) is False
    # price_drop_pct None: no fire
    assert _check_price_triggers(4500, None, None, 5000) is False
    # prev_price None (no history): no fire
    assert _check_price_triggers(4500, None, 10.0, None) is False


def test_pct_drop_trigger_no_false_positive_at_boundary():
    """C-01 regression: 9.96% drop must NOT fire a 10.0% threshold.

    Pre-fix bug: _pct_drop_from_last rounds 9.96 -> 10.0 before comparing,
    causing a false positive. Fix uses integer-cent arithmetic.
    """
    from core.orchestrator import _check_price_triggers

    # last=5000, current=4502 -> drop = 498/5000 = 9.96%: must NOT fire at 10.0
    assert _check_price_triggers(4502, None, 10.0, 5000) is False, (
        "9.96% drop should not fire a 10.0% threshold (C-01)"
    )

    # last=5000, current=4500 -> drop = 500/5000 = exactly 10%: MUST fire
    assert _check_price_triggers(4500, None, 10.0, 5000) is True, (
        "Exactly 10% drop must fire a 10.0% threshold (C-01)"
    )

    # last=5000, current=4499 -> drop = 501/5000 = 10.02%: MUST fire
    assert _check_price_triggers(4499, None, 10.0, 5000) is True, (
        "10.02% drop must fire a 10.0% threshold (C-01)"
    )


# ---------------------------------------------------------------------------
# _build_price_drop_event payload
# ---------------------------------------------------------------------------


def test_price_drop_event_payload():
    """Dispatched event has action==price_drop with correct payload fields."""
    from core.orchestrator import _build_price_drop_event

    event = _build_price_drop_event("Widget", "https://example.com/w", "FakePlugin", 4500, 5000)
    assert event.action == "price_drop"
    assert event.price_cents == 4500
    assert event.target_price_cents == 5000
    assert event.pct_from_target == 10.0

    # target_price None -> pct_from_target is None
    event2 = _build_price_drop_event("Widget", "https://example.com/w", "FakePlugin", 4500, None)
    assert event2.target_price_cents is None
    assert event2.pct_from_target is None


# ---------------------------------------------------------------------------
# REL-01 regression: price-history DB error must NOT propagate out of _check_and_buy
# ---------------------------------------------------------------------------


async def test_price_history_db_error_does_not_propagate(fake_plugin, tmp_data_dir):
    """REL-01: if a price DB call raises, _check_and_buy catches it and continues.

    Without the fix the exception escapes into run_plugin -> asyncio.TaskGroup
    which cancels ALL sibling tasks (whole bot down).
    """
    import asyncio
    import core.orchestrator as orch_mod
    from models import initialize_db, add_items_sync
    from core.orchestrator import _check_and_buy

    initialize_db()
    link = "https://fake.example.com/rel01"
    add_items_sync([("Widget", link, False, 1, False)])

    plugin = fake_plugin(domains=["fake.example.com"], available=False)
    plugin.get_price = AsyncMock(return_value=4500)

    write_queue = asyncio.Queue()

    # Make append_price_history_sync raise to simulate a DB failure
    with patch.object(orch_mod, "append_price_history_sync", side_effect=RuntimeError("db gone")):
        # Must not raise -- the exception is isolated inside _check_and_buy
        await _check_and_buy(plugin, "Widget", link, False, write_queue, dispatcher=None)


# ---------------------------------------------------------------------------
# Last-price read order (Pitfall 3): get_last_price_sync called before append
# ---------------------------------------------------------------------------


async def test_last_price_read_before_append(fake_plugin, tmp_data_dir):
    """get_last_price_sync must be called before append_price_history_sync in _check_and_buy."""
    import asyncio
    import models
    from models import initialize_db, add_items_sync
    from core.orchestrator import _check_and_buy

    initialize_db()
    link = "https://fake.example.com/item"
    add_items_sync([("Widget", link, False, 1, False)])
    # seed price config so _evaluate_price_triggers can proceed
    models.update_item_price_config_sync(link, 5000, None)

    plugin = fake_plugin(domains=["fake.example.com"], available=True)
    plugin.get_price = AsyncMock(return_value=4500)

    call_order = []

    original_get_last = models.get_last_price_sync
    original_append = models.append_price_history_sync

    def spy_get_last(l):
        call_order.append("get_last")
        return original_get_last(l)

    def spy_append(l, p, s, c="USD"):
        call_order.append("append")
        return original_append(l, p, s, c)

    write_queue = asyncio.Queue()

    # Patch the orchestrator module's local bindings (imported at module load via
    # "from models import ...") so run_in_executor picks up the spies (Pitfall 3).
    import core.orchestrator as orch_mod
    with patch.object(orch_mod, "get_last_price_sync", side_effect=spy_get_last), \
         patch.object(orch_mod, "append_price_history_sync", side_effect=spy_append):
        await _check_and_buy(plugin, "Widget", link, False, write_queue, dispatcher=None)

    # get_last must come before append
    assert "get_last" in call_order, f"get_last_price_sync was never called; order: {call_order}"
    assert "append" in call_order, f"append_price_history_sync was never called; order: {call_order}"
    get_last_idx = call_order.index("get_last")
    append_idx = call_order.index("append")
    assert get_last_idx < append_idx, (
        f"get_last_price_sync must be called before append_price_history_sync; "
        f"got order: {call_order}"
    )


# ---------------------------------------------------------------------------
# _evaluate_price_triggers dedup: fires once, stays silent while armed
# ---------------------------------------------------------------------------


async def test_price_alert_dedup_fires_once(fake_plugin, fake_notifier, tmp_data_dir):
    """First trigger dispatches a price_drop event and arms; armed cycle does not re-dispatch."""
    import asyncio
    import models
    from models import initialize_db, add_items_sync
    from notifications.dispatcher import NotificationDispatcher
    from core.orchestrator import _check_and_buy

    initialize_db()
    link = "https://fake.example.com/dedup"
    add_items_sync([("Widget", link, False, 1, False)])
    models.update_item_price_config_sync(link, 5000, None)

    notifier = fake_notifier()
    dispatcher = NotificationDispatcher([notifier])
    plugin = fake_plugin(domains=["fake.example.com"], available=True)
    plugin.get_price = AsyncMock(return_value=4500)

    write_queue = asyncio.Queue()

    # First cycle: should dispatch one price_drop event
    await _check_and_buy(plugin, "Widget", link, False, write_queue, dispatcher=dispatcher)
    price_events = [e for e in notifier.events if e.action == "price_drop"]
    assert len(price_events) == 1

    # Second cycle: armed; should NOT dispatch another price_drop
    await _check_and_buy(plugin, "Widget", link, False, write_queue, dispatcher=dispatcher)
    price_events2 = [e for e in notifier.events if e.action == "price_drop"]
    assert len(price_events2) == 1


# ---------------------------------------------------------------------------
# _evaluate_price_triggers: disarms when trigger no longer fires
# ---------------------------------------------------------------------------


async def test_price_alert_disarms_on_recovery(fake_plugin, fake_notifier, tmp_data_dir):
    """When trigger no longer fires, clear_price_alert_armed_sync is called (price recovery)."""
    import asyncio
    import models
    from models import initialize_db, add_items_sync
    from notifications.dispatcher import NotificationDispatcher
    from core.orchestrator import _check_and_buy

    initialize_db()
    link = "https://fake.example.com/disarm"
    add_items_sync([("Widget", link, False, 1, False)])
    models.update_item_price_config_sync(link, 5000, None)

    notifier = fake_notifier()
    dispatcher = NotificationDispatcher([notifier])
    plugin = fake_plugin(domains=["fake.example.com"], available=True)

    write_queue = asyncio.Queue()

    def price_drop_count():
        return sum(1 for e in notifier.events if e.action == "price_drop")

    # Cycle 1: price below target -> fire + arm
    plugin.get_price = AsyncMock(return_value=4500)
    await _check_and_buy(plugin, "Widget", link, False, write_queue, dispatcher=dispatcher)
    assert price_drop_count() == 1
    armed, _ = models.get_price_alert_state_sync(link)
    assert armed is True

    # Cycle 2: price recovers above target -> disarm
    plugin.get_price = AsyncMock(return_value=5500)
    await _check_and_buy(plugin, "Widget", link, False, write_queue, dispatcher=dispatcher)
    armed2, _ = models.get_price_alert_state_sync(link)
    assert armed2 is False

    # Cycle 3: price drops again -> should fire again (fresh window)
    plugin.get_price = AsyncMock(return_value=4500)
    await _check_and_buy(plugin, "Widget", link, False, write_queue, dispatcher=dispatcher)
    assert price_drop_count() == 2


# ---------------------------------------------------------------------------
# Price dedup independence: price alerts do not touch stock dedup columns
# ---------------------------------------------------------------------------


async def test_price_dedup_independent(fake_plugin, fake_notifier, tmp_data_dir):
    """T-01: firing a price alert does NOT write stock dedup columns.

    Captures (last_seen_available, last_notified) before a price-only cycle
    where available=False (no stock rising edge), then asserts those columns
    are byte-identical after the price_drop fires.  A price-path write to
    stock dedup columns would fail this test.
    """
    import asyncio
    import sqlite3
    import models
    from models import initialize_db, add_items_sync
    from notifications.dispatcher import NotificationDispatcher
    from core.orchestrator import _check_and_buy

    initialize_db()
    link = "https://fake.example.com/independent"
    add_items_sync([("Widget", link, False, 1, False)])
    models.update_item_price_config_sync(link, 5000, None)

    # Snapshot stock dedup state before the cycle
    was_avail_before, last_notified_before = models.get_item_notification_state_sync(link)
    assert was_avail_before is False
    assert last_notified_before is None

    notifier = fake_notifier()
    dispatcher = NotificationDispatcher([notifier])
    # available=False: no stock rising-edge so only the price path fires
    plugin = fake_plugin(domains=["fake.example.com"], available=False)
    plugin.get_price = AsyncMock(return_value=4500)

    write_queue = asyncio.Queue()
    await _check_and_buy(plugin, "Widget", link, False, write_queue, dispatcher=dispatcher)

    # Price alert must have fired
    assert any(e.action == "price_drop" for e in notifier.events)

    # price dedup columns updated by price path
    price_armed, price_last_notified = models.get_price_alert_state_sync(link)
    assert price_armed is True
    assert price_last_notified is not None

    # Stock dedup columns must be byte-identical to the snapshot (price path must not touch them)
    was_avail_after, last_notified_after = models.get_item_notification_state_sync(link)
    assert was_avail_after == was_avail_before, (
        f"price path wrote last_seen_available: was {was_avail_before}, now {was_avail_after}"
    )
    assert last_notified_after is last_notified_before or last_notified_after == last_notified_before, (
        f"price path wrote last_notified: was {last_notified_before!r}, now {last_notified_after!r}"
    )


# ---------------------------------------------------------------------------
# T-02: pct-drop trigger end-to-end integration tests
# ---------------------------------------------------------------------------


async def test_pct_drop_trigger_end_to_end(fake_plugin, fake_notifier, tmp_data_dir):
    """T-02a: pct-drop-only config fires exactly once on a 10% drop over two cycles.

    Cycle 1 seeds the price history (5000). Cycle 2 drops to 4500 (exactly 10%).
    One price_drop event with target_price_cents=None and price_cents=4500.
    Cycle 3 is a no-op (armed; dedup blocks).
    """
    import asyncio
    import models
    from models import initialize_db, add_items_sync, update_item_price_config_sync
    from notifications.dispatcher import NotificationDispatcher
    from core.orchestrator import _check_and_buy

    initialize_db()
    link = "https://fake.example.com/pct-drop-e2e"
    add_items_sync([("Widget", link, False, 1, False)])
    # pct-drop only, no absolute target
    update_item_price_config_sync(link, None, 10.0)

    notifier = fake_notifier()
    dispatcher = NotificationDispatcher([notifier])
    plugin = fake_plugin(domains=["fake.example.com"], available=False)
    write_queue = asyncio.Queue()

    def price_drop_events():
        return [e for e in notifier.events if e.action == "price_drop"]

    # Cycle 1: seed price history at 5000 (no prev_price yet, trigger can't fire)
    plugin.get_price = AsyncMock(return_value=5000)
    await _check_and_buy(plugin, "Widget", link, False, write_queue, dispatcher=dispatcher)
    assert len(price_drop_events()) == 0

    # Cycle 2: price drops to 4500 (exactly 10%) -> must fire once
    plugin.get_price = AsyncMock(return_value=4500)
    await _check_and_buy(plugin, "Widget", link, False, write_queue, dispatcher=dispatcher)
    events = price_drop_events()
    assert len(events) == 1
    assert events[0].target_price_cents is None
    assert events[0].price_cents == 4500

    # Cycle 3: armed; must NOT fire again
    plugin.get_price = AsyncMock(return_value=4500)
    await _check_and_buy(plugin, "Widget", link, False, write_queue, dispatcher=dispatcher)
    assert len(price_drop_events()) == 1


async def test_pct_drop_trigger_with_absolute_target(fake_plugin, fake_notifier, tmp_data_dir):
    """T-02b: absolute target fires in a single cycle when price <= target.

    Seed (target=5000, drop_pct=10.0); first cycle at 4500 fires immediately
    (no prior price needed for the absolute path). No double-fire in same cycle.
    """
    import asyncio
    import models
    from models import initialize_db, add_items_sync, update_item_price_config_sync
    from notifications.dispatcher import NotificationDispatcher
    from core.orchestrator import _check_and_buy

    initialize_db()
    link = "https://fake.example.com/abs-target-e2e"
    add_items_sync([("Widget", link, False, 1, False)])
    # both absolute target and pct-drop config
    update_item_price_config_sync(link, 5000, 10.0)

    notifier = fake_notifier()
    dispatcher = NotificationDispatcher([notifier])
    plugin = fake_plugin(domains=["fake.example.com"], available=False)
    write_queue = asyncio.Queue()

    # Single cycle at 4500 (<= target 5000): exactly one event, no double-fire
    plugin.get_price = AsyncMock(return_value=4500)
    await _check_and_buy(plugin, "Widget", link, False, write_queue, dispatcher=dispatcher)

    price_drop_events = [e for e in notifier.events if e.action == "price_drop"]
    assert len(price_drop_events) == 1, f"Expected 1 event, got {len(price_drop_events)}"
    assert price_drop_events[0].price_cents == 4500


# ---------------------------------------------------------------------------
# T-04: None/0 price from get_price must NOT call append or trigger evaluation
# ---------------------------------------------------------------------------


async def test_none_price_skips_history_and_triggers(fake_plugin, tmp_data_dir):
    """T-04a: get_price returning None must not call append_price_history_sync."""
    import asyncio
    import core.orchestrator as orch_mod
    from models import initialize_db, add_items_sync
    from core.orchestrator import _check_and_buy
    from unittest.mock import MagicMock

    initialize_db()
    link = "https://fake.example.com/none-price"
    add_items_sync([("Widget", link, False, 1, False)])

    plugin = fake_plugin(domains=["fake.example.com"], available=False)
    plugin.get_price = AsyncMock(return_value=None)

    append_spy = MagicMock()
    write_queue = asyncio.Queue()

    with patch.object(orch_mod, "append_price_history_sync", side_effect=append_spy):
        await _check_and_buy(plugin, "Widget", link, False, write_queue, dispatcher=None)

    append_spy.assert_not_called()


async def test_zero_price_skips_history_and_triggers(fake_plugin, tmp_data_dir):
    """T-04b: get_price returning 0 must not call append_price_history_sync."""
    import asyncio
    import core.orchestrator as orch_mod
    from models import initialize_db, add_items_sync
    from core.orchestrator import _check_and_buy
    from unittest.mock import MagicMock

    initialize_db()
    link = "https://fake.example.com/zero-price"
    add_items_sync([("Widget", link, False, 1, False)])

    plugin = fake_plugin(domains=["fake.example.com"], available=False)
    plugin.get_price = AsyncMock(return_value=0)

    append_spy = MagicMock()
    write_queue = asyncio.Queue()

    with patch.object(orch_mod, "append_price_history_sync", side_effect=append_spy):
        await _check_and_buy(plugin, "Widget", link, False, write_queue, dispatcher=None)

    append_spy.assert_not_called()


# ---------------------------------------------------------------------------
# Config seeding: update_item_price_config_sync called per config item
# ---------------------------------------------------------------------------


def test_seed_writes_price_config(tmp_data_dir):
    """Startup seed calls update_item_price_config_sync for each config item."""
    from models import initialize_db, add_items_sync, get_item_price_config_sync

    initialize_db()

    link1 = "https://amazon.com/item1"
    link2 = "https://bestbuy.com/item2"
    add_items_sync([
        ("Item1", link1, False, 1, False),
        ("Item2", link2, False, 1, False),
    ])

    # Simulate what main.py does: call update_item_price_config_sync per item
    from models import update_item_price_config_sync
    update_item_price_config_sync(link1, 4999, 10.0)
    update_item_price_config_sync(link2, None, None)

    config1 = get_item_price_config_sync(link1)
    assert config1 == (4999, 10.0)

    config2 = get_item_price_config_sync(link2)
    assert config2 == (None, None)


# ---------------------------------------------------------------------------
# PR-02: pct helpers guard non-positive denominator (orchestrator.py:70, 77)
# ---------------------------------------------------------------------------


def test_pct_helpers_guard_nonpositive_denominator():
    """PR-02: _pct_from_target and _pct_drop_from_last return 0.0 for zero or negative denominator.

    Exercises orchestrator.py:70 (target_cents <= 0 guard) and line 77
    (last_cents <= 0 guard) -- no ZeroDivisionError for either helper.
    """
    from core.orchestrator import _pct_from_target, _pct_drop_from_last

    # Zero denominator
    assert _pct_from_target(4500, 0) == 0.0
    assert _pct_drop_from_last(4500, 0) == 0.0

    # Negative denominator
    assert _pct_from_target(4500, -100) == 0.0
    assert _pct_drop_from_last(4500, -100) == 0.0


# ---------------------------------------------------------------------------
# PR-03: _evaluate_price_triggers early-returns on missing or null config (orch:123, 126)
# ---------------------------------------------------------------------------


async def test_evaluate_price_triggers_skips_when_no_config(tmp_data_dir):
    """PR-03: _evaluate_price_triggers returns early when config is absent or all-None.

    Sub-case 1: no item row in DB (get_item_price_config_sync returns None) ->
    early return at orchestrator.py:123; dispatcher.notify not called.
    Sub-case 2: item row exists but both target_price and price_drop_pct are None ->
    early return at orchestrator.py:126; dispatcher.notify not called.
    """
    import asyncio
    import models
    from models import initialize_db, add_items_sync
    from core.orchestrator import _evaluate_price_triggers

    loop = asyncio.get_running_loop()

    # Sub-case 1: no item row (get_item_price_config_sync returns None).
    initialize_db(delete=True)
    link_missing = "https://fake.example.com/noconfig"
    dispatcher1 = MagicMock()
    dispatcher1.notify = AsyncMock()
    plugin1 = MagicMock()
    await _evaluate_price_triggers(plugin1, "NoConfig", link_missing, 4500, None, dispatcher1, loop)
    dispatcher1.notify.assert_not_awaited()

    # Sub-case 2: item row exists but (None, None) config.
    link_null = "https://fake.example.com/nullconfig"
    add_items_sync([("NullConfig", link_null, False, 1, False)])
    # Do NOT call update_item_price_config_sync -- both fields default to NULL.
    dispatcher2 = MagicMock()
    dispatcher2.notify = AsyncMock()
    plugin2 = MagicMock()
    await _evaluate_price_triggers(plugin2, "NullConfig", link_null, 4500, None, dispatcher2, loop)
    dispatcher2.notify.assert_not_awaited()


# ---------------------------------------------------------------------------
# AB-01: get_price exception is isolated; availability path still runs (orch:209-210)
# ---------------------------------------------------------------------------


async def test_get_price_error_is_isolated_and_does_not_propagate(fake_plugin, tmp_data_dir):
    """AB-01: a RuntimeError from get_price is caught and logged; _check_and_buy does not raise.

    The availability/notification path continues to run after the get_price
    exception -- here an available item puts set_available into the write_queue.
    Exercises orchestrator.py:209-210 (get_price error isolation).
    """
    import asyncio
    import models
    from models import initialize_db, add_items_sync
    from core.orchestrator import _check_and_buy
    from unittest.mock import AsyncMock

    initialize_db()
    link = "https://fake.example.com/ab01"
    add_items_sync([("Widget", link, False, 1, False)])

    plugin = fake_plugin(domains=["fake.example.com"], available=True)
    plugin.check_availability = AsyncMock(return_value=True)
    plugin.get_price = AsyncMock(side_effect=RuntimeError("boom"))

    write_queue = asyncio.Queue()

    # Must not raise even though get_price raises.
    await _check_and_buy(plugin, "Widget", link, False, write_queue, dispatcher=None)

    # Availability path ran: rising edge put set_available in the queue.
    assert not write_queue.empty(), "Expected set_available entry in write_queue but queue is empty"
    item = await write_queue.get()
    assert item[0] == "set_available", f"Expected set_available, got {item[0]}"


# ---------------------------------------------------------------------------
# AB-02: get_price sequencing relative to check_availability (orch:201-203, 207-210)
# ---------------------------------------------------------------------------


async def test_get_price_invoked_alongside_check_availability_sequencing(fake_plugin, tmp_data_dir):
    """AB-02: get_price runs when check_availability returns False; skipped when it raises.

    Sub-case A: check_availability returns False (unavailable) -> get_price IS
    called (call_count == 1) because get_price runs after any successful
    check_availability call regardless of the boolean result.
    Sub-case B: check_availability raises -> _check_and_buy returns at orch:201-203
    BEFORE reaching get_price (call_count == 0); no exception propagated.
    """
    import asyncio
    import models
    from models import initialize_db, add_items_sync
    from core.orchestrator import _check_and_buy
    from unittest.mock import AsyncMock

    initialize_db()
    link_a = "https://fake.example.com/ab02a"
    link_b = "https://fake.example.com/ab02b"
    add_items_sync([("WidgetA", link_a, False, 1, False)])
    add_items_sync([("WidgetB", link_b, False, 1, False)])

    # Sub-case A: check_availability=False, get_price should still be called.
    plugin_a = fake_plugin(domains=["fake.example.com"], available=False)
    plugin_a.check_availability = AsyncMock(return_value=False)
    plugin_a.get_price = AsyncMock(return_value=None)
    write_queue_a = asyncio.Queue()
    await _check_and_buy(plugin_a, "WidgetA", link_a, False, write_queue_a, dispatcher=None)
    assert plugin_a.get_price.call_count == 1, (
        f"Expected get_price called once when available=False, got {plugin_a.get_price.call_count}"
    )

    # Sub-case B: check_availability raises -> early return before get_price.
    plugin_b = fake_plugin(domains=["fake.example.com"], available=False)
    plugin_b.check_availability = AsyncMock(side_effect=RuntimeError("network error"))
    plugin_b.get_price = AsyncMock()
    write_queue_b = asyncio.Queue()
    await _check_and_buy(plugin_b, "WidgetB", link_b, False, write_queue_b, dispatcher=None)
    assert plugin_b.get_price.call_count == 0, (
        f"Expected get_price NOT called when check_availability raises, got {plugin_b.get_price.call_count}"
    )


# ---------------------------------------------------------------------------
# BotService.get_price_history accessor
# ---------------------------------------------------------------------------


def test_get_price_history_accessor(tmp_data_dir):
    """BotService.get_price_history resolves name to link and returns rows; empty for unknown."""
    from models import initialize_db, add_items_sync, append_price_history_sync
    from core.service import BotService

    initialize_db()
    link = "https://amazon.com/widget"
    add_items_sync([("WidgetName", link, False, 1, False)])

    ts = datetime.now(timezone.utc).isoformat()
    append_price_history_sync(link, 4999, ts)

    svc = BotService.__new__(BotService)

    rows = svc.get_price_history("WidgetName", limit=10)
    assert len(rows) == 1
    assert rows[0][0] == 4999
    assert rows[0][1] == "USD"

    # Unknown name returns empty list
    empty = svc.get_price_history("DoesNotExist", limit=10)
    assert empty == []
