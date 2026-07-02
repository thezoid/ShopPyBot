"""Tests for cart-retry logic in core/orchestrator.py (Plan 21-04).

Covers:
- BUY-05: pre-existing confirmed order_id -> auto_buy called 0 times (no double-buy)
- REL-08: with_retry + RetryPolicy driven by CheckoutConfig fields
- checkout_attempts increments once per attempt, before each attempt
- max_cart_retries=0 -> exactly 1 attempt (no retry)
- all attempts fail -> no enqueue (WR-02: enqueue only on success)
- success path -> exactly one enqueue OUTSIDE the retry loop (WR-02)
- backoff via compute_delay (asyncio.sleep patched for determinism)
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from core.orchestrator import _attempt_buy, _try_auto_buy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_checkout_config(max_cart_retries=3, backoff_base=2.0, backoff_jitter=0.0):
    cfg = MagicMock()
    cfg.max_cart_retries = max_cart_retries
    cfg.backoff_base = backoff_base
    cfg.backoff_jitter = backoff_jitter
    return cfg


def _make_plugin(auto_buy_returns):
    """Build a minimal plugin stub for cart-retry tests.

    auto_buy_returns: list of bool values returned by successive auto_buy calls.
    """
    plugin = MagicMock()
    plugin.__class__.__name__ = "FakePlugin"
    plugin._checkout_stage = "place-order"
    plugin.config.checkout = _make_checkout_config()
    plugin.auto_buy = AsyncMock(side_effect=auto_buy_returns)
    tab = MagicMock()
    plugin.get_active_tab = MagicMock(return_value=tab)
    return plugin, tab


# ---------------------------------------------------------------------------
# _attempt_buy unit tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_attempt_buy_false_returns_false_none():
    plugin, _ = _make_plugin([False])
    with patch("core.confirmation.detect_order_confirmation", new=AsyncMock()):
        result = await _attempt_buy(plugin, "https://fake.example.com/item")
    assert result == (False, None)
    plugin.auto_buy.assert_awaited_once()


@pytest.mark.asyncio
async def test_attempt_buy_true_with_order_id():
    plugin, tab = _make_plugin([True])
    order_id = "ORDER-123"
    with patch(
        "core.confirmation.detect_order_confirmation",
        new=AsyncMock(return_value=order_id),
    ):
        result = await _attempt_buy(plugin, "https://fake.example.com/item")
    assert result == (True, order_id)


@pytest.mark.asyncio
async def test_attempt_buy_true_detection_error_returns_true_none():
    plugin, _ = _make_plugin([True])
    with patch(
        "core.confirmation.detect_order_confirmation",
        side_effect=RuntimeError("page gone"),
    ):
        result = await _attempt_buy(plugin, "https://fake.example.com/item")
    assert result == (True, None)


@pytest.mark.asyncio
async def test_attempt_buy_auto_buy_exception_returns_false_none():
    plugin, _ = _make_plugin([])
    plugin.auto_buy = AsyncMock(side_effect=RuntimeError("crash"))
    with patch("core.confirmation.detect_order_confirmation", new=AsyncMock()):
        result = await _attempt_buy(plugin, "https://fake.example.com/item")
    assert result == (False, None)


# ---------------------------------------------------------------------------
# _try_auto_buy cart-retry tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirmed_order_in_db_zero_auto_buy_calls(tmp_data_dir):
    """BUY-05: if order_id already in DB, auto_buy must never be called."""
    plugin, _ = _make_plugin([True])
    write_queue = asyncio.Queue()

    with (
        patch("core.orchestrator.get_item_order_state_sync", return_value=(True, "ORD-EXISTING")),
        patch("core.orchestrator.increment_checkout_attempts_sync") as mock_inc,
        patch("core.confirmation.detect_order_confirmation", new=AsyncMock()),
        patch("asyncio.sleep", new=AsyncMock()),
    ):
        await _try_auto_buy(plugin, "Widget", "https://fake.com/item", write_queue, None)

    plugin.auto_buy.assert_not_awaited()
    assert mock_inc.call_count == 0
    assert write_queue.empty()


@pytest.mark.asyncio
async def test_retries_up_to_max_then_stops(tmp_data_dir):
    """With max_cart_retries=2, total=3 attempts; all fail -> no enqueue."""
    plugin, _ = _make_plugin([False, False, False])
    plugin.config.checkout = _make_checkout_config(max_cart_retries=2, backoff_jitter=0.0)
    write_queue = asyncio.Queue()

    with (
        patch("core.orchestrator.get_item_order_state_sync", return_value=(False, None)),
        patch("core.orchestrator.get_place_order_marker_sync", return_value=None),
        patch("core.orchestrator.increment_checkout_attempts_sync") as mock_inc,
        patch("core.confirmation.detect_order_confirmation", new=AsyncMock()),
        patch("asyncio.sleep", new=AsyncMock()),
    ):
        await _try_auto_buy(plugin, "Widget", "https://fake.com/item", write_queue, None)

    assert plugin.auto_buy.await_count == 3
    assert mock_inc.call_count == 3
    assert write_queue.empty()


@pytest.mark.asyncio
async def test_max_cart_retries_zero_single_attempt(tmp_data_dir):
    """max_cart_retries=0 -> total attempts=1; failure does NOT retry."""
    plugin, _ = _make_plugin([False])
    plugin.config.checkout = _make_checkout_config(max_cart_retries=0)
    write_queue = asyncio.Queue()

    with (
        patch("core.orchestrator.get_item_order_state_sync", return_value=(False, None)),
        patch("core.orchestrator.get_place_order_marker_sync", return_value=None),
        patch("core.orchestrator.increment_checkout_attempts_sync") as mock_inc,
        patch("core.confirmation.detect_order_confirmation", new=AsyncMock()),
        patch("asyncio.sleep", new=AsyncMock()),
    ):
        await _try_auto_buy(plugin, "Widget", "https://fake.com/item", write_queue, None)

    assert plugin.auto_buy.await_count == 1
    assert mock_inc.call_count == 1
    assert write_queue.empty()


@pytest.mark.asyncio
async def test_checkout_attempts_increments_before_each_attempt(tmp_data_dir):
    """checkout_attempts increments once per attempt, before the attempt."""
    plugin, _ = _make_plugin([False, True])
    plugin.config.checkout = _make_checkout_config(max_cart_retries=3, backoff_jitter=0.0)
    write_queue = asyncio.Queue()
    call_order = []

    def record_inc(link):
        call_order.append("increment")

    async def record_buy(url):
        call_order.append("auto_buy")
        # Return True on second call
        return len([x for x in call_order if x == "auto_buy"]) > 1

    plugin.auto_buy = AsyncMock(side_effect=record_buy)
    order_id = "ORD-NEW"

    with (
        patch("core.orchestrator.get_item_order_state_sync", return_value=(False, None)),
        patch("core.orchestrator.get_place_order_marker_sync", return_value=None),
        patch("core.orchestrator.increment_checkout_attempts_sync", side_effect=record_inc),
        patch(
            "core.confirmation.detect_order_confirmation",
            new=AsyncMock(return_value=order_id),
        ),
        patch("asyncio.sleep", new=AsyncMock()),
    ):
        await _try_auto_buy(plugin, "Widget", "https://fake.com/item", write_queue, None)

    # increment must come before the corresponding auto_buy
    assert call_order[0] == "increment"
    assert call_order[1] == "auto_buy"
    assert call_order[2] == "increment"
    assert call_order[3] == "auto_buy"


@pytest.mark.asyncio
async def test_single_enqueue_on_success_confirmed(tmp_data_dir):
    """Exactly one enqueue per successful buy; confirmed path (WR-02)."""
    plugin, _ = _make_plugin([True])
    plugin.config.checkout = _make_checkout_config(max_cart_retries=3, backoff_jitter=0.0)
    write_queue = asyncio.Queue()
    order_id = "ORD-CONFIRM"

    with (
        patch("core.orchestrator.get_item_order_state_sync", return_value=(False, None)),
        patch("core.orchestrator.get_place_order_marker_sync", return_value=None),
        patch("core.orchestrator.increment_checkout_attempts_sync"),
        patch(
            "core.confirmation.detect_order_confirmation",
            new=AsyncMock(return_value=order_id),
        ),
        patch("asyncio.sleep", new=AsyncMock()),
    ):
        await _try_auto_buy(plugin, "Widget", "https://fake.com/item", write_queue, None)

    assert write_queue.qsize() == 1
    item = await write_queue.get()
    assert item[0] == "confirmed"
    assert item[1] == "https://fake.com/item"
    assert item[2] == order_id


@pytest.mark.asyncio
async def test_single_enqueue_on_success_legacy(tmp_data_dir):
    """Exactly one legacy purchased enqueue when order_id is None (WR-02)."""
    plugin, _ = _make_plugin([True])
    plugin.config.checkout = _make_checkout_config(max_cart_retries=0)
    write_queue = asyncio.Queue()

    with (
        patch("core.orchestrator.get_item_order_state_sync", return_value=(False, None)),
        patch("core.orchestrator.get_place_order_marker_sync", return_value=None),
        patch("core.orchestrator.increment_checkout_attempts_sync"),
        patch(
            "core.confirmation.detect_order_confirmation",
            new=AsyncMock(return_value=None),
        ),
        patch("asyncio.sleep", new=AsyncMock()),
    ):
        await _try_auto_buy(plugin, "Widget", "https://fake.com/item", write_queue, None)

    assert write_queue.qsize() == 1
    item = await write_queue.get()
    assert item == ("purchased", "https://fake.com/item")


@pytest.mark.asyncio
async def test_backoff_sleep_called_between_failed_attempts(tmp_data_dir):
    """asyncio.sleep is called with a positive delay between failed attempts."""
    plugin, _ = _make_plugin([False, True])
    plugin.config.checkout = _make_checkout_config(
        max_cart_retries=2, backoff_base=2.0, backoff_jitter=0.0
    )
    write_queue = asyncio.Queue()
    sleep_calls = []

    async def fake_sleep(delay):
        sleep_calls.append(delay)

    order_id = "ORD-BACKOFF"
    with (
        patch("core.orchestrator.get_item_order_state_sync", return_value=(False, None)),
        patch("core.orchestrator.get_place_order_marker_sync", return_value=None),
        patch("core.orchestrator.increment_checkout_attempts_sync"),
        patch(
            "core.confirmation.detect_order_confirmation",
            new=AsyncMock(return_value=order_id),
        ),
        patch("asyncio.sleep", side_effect=fake_sleep),
    ):
        await _try_auto_buy(plugin, "Widget", "https://fake.com/item", write_queue, None)

    # One sleep between attempt 0 (fail) and attempt 1 (success)
    assert len(sleep_calls) == 1
    assert sleep_calls[0] >= 1.0  # backoff_base**0 = 1.0 + jitter(0) = 1.0


@pytest.mark.asyncio
async def test_second_attempt_sees_confirmed_order_from_first(tmp_data_dir):
    """If first attempt confirms, second on_attempt sees the order_id and exits."""
    plugin, _ = _make_plugin([True, True])
    plugin.config.checkout = _make_checkout_config(max_cart_retries=3, backoff_jitter=0.0)
    write_queue = asyncio.Queue()

    # First pre-read: no order; second pre-read: order exists (from first attempt's write)
    order_state_returns = [(False, None), (False, "ORD-PREV")]
    call_count = {"n": 0}

    def order_state_side_effect(link):
        val = order_state_returns[min(call_count["n"], len(order_state_returns) - 1)]
        call_count["n"] += 1
        return val

    with (
        patch("core.orchestrator.get_item_order_state_sync", side_effect=order_state_side_effect),
        patch("core.orchestrator.get_place_order_marker_sync", return_value=None),
        patch("core.orchestrator.increment_checkout_attempts_sync"),
        patch(
            "core.confirmation.detect_order_confirmation",
            new=AsyncMock(return_value="ORD-PREV"),
        ),
        patch("asyncio.sleep", new=AsyncMock()),
    ):
        await _try_auto_buy(plugin, "Widget", "https://fake.com/item", write_queue, None)

    # First attempt succeeds with order_id; second on_attempt raises AlreadyConfirmed
    # So total auto_buy calls = 1, total enqueues = 1
    assert plugin.auto_buy.await_count == 1
    assert write_queue.qsize() == 1




@pytest.mark.asyncio
async def test_no_retry_on_success_with_no_order_id(tmp_data_dir):
    """CR-01 regression: auto_buy success + undetected order_id must NOT cause a retry.

    When auto_buy returns True but confirmation detection returns None, should_retry
    must evaluate to False (only retry on auto_buy failure). Retrying here would
    re-click place-order and double-buy. Assert auto_buy called exactly once, and
    exactly one legacy purchased enqueue emitted (no double-buy, no double-enqueue).
    """
    plugin, _ = _make_plugin([True, True, True])
    plugin.config.checkout = _make_checkout_config(max_cart_retries=3, backoff_jitter=0.0)
    write_queue = asyncio.Queue()

    with (
        patch("core.orchestrator.get_item_order_state_sync", return_value=(False, None)),
        patch("core.orchestrator.get_place_order_marker_sync", return_value=None),
        patch("core.orchestrator.increment_checkout_attempts_sync"),
        patch(
            "core.confirmation.detect_order_confirmation",
            new=AsyncMock(return_value=None),
        ),
        patch("asyncio.sleep", new=AsyncMock()),
    ):
        await _try_auto_buy(plugin, "Widget", "https://fake.com/item", write_queue, None)

    assert plugin.auto_buy.await_count == 1, "Must not retry when auto_buy succeeded"
    assert write_queue.qsize() == 1
    item = await write_queue.get()
    assert item == ("purchased", "https://fake.com/item"), "Must enqueue exactly one legacy purchased"


@pytest.mark.asyncio
async def test_legacy_purchased_item_zero_auto_buy_calls(tmp_data_dir):
    """CR-02 regression: item purchased via legacy path (purchased=1, order_id=NULL)
    must cause auto_buy to be called 0 times (idempotency guard covers legacy state).
    """
    plugin, _ = _make_plugin([True])
    plugin.config.checkout = _make_checkout_config(max_cart_retries=3, backoff_jitter=0.0)
    write_queue = asyncio.Queue()

    with (
        patch("core.orchestrator.get_item_order_state_sync", return_value=(True, None)),
        patch("core.orchestrator.increment_checkout_attempts_sync") as mock_inc,
        patch("core.confirmation.detect_order_confirmation", new=AsyncMock()),
        patch("asyncio.sleep", new=AsyncMock()),
    ):
        await _try_auto_buy(plugin, "Widget", "https://fake.com/item", write_queue, None)

    plugin.auto_buy.assert_not_awaited()
    assert mock_inc.call_count == 0
    assert write_queue.empty()

@pytest.mark.asyncio
async def test_possibly_placed_aborts_retry(tmp_data_dir):
    """BF-02: marker set + order_id None -> _PossiblyPlaced aborts retry (no re-click)."""
    plugin, _ = _make_plugin([False, False, False])
    plugin.config.checkout = _make_checkout_config(max_cart_retries=3, backoff_jitter=0.0)
    write_queue = asyncio.Queue()

    with (
        patch("core.orchestrator.get_item_order_state_sync", return_value=(False, None)),
        patch(
            "core.orchestrator.get_place_order_marker_sync",
            return_value="2026-07-02T00:00:00+00:00",
        ),
        patch("core.orchestrator.increment_checkout_attempts_sync") as mock_inc,
        patch("core.confirmation.detect_order_confirmation", new=AsyncMock()),
        patch("asyncio.sleep", new=AsyncMock()),
    ):
        await _try_auto_buy(plugin, "Widget", "https://fake.com/item", write_queue, None)

    plugin.auto_buy.assert_not_awaited()
    assert mock_inc.call_count == 0
    assert write_queue.empty()


@pytest.mark.asyncio
async def test_possibly_placed_precedence_confirmed_order_wins(tmp_data_dir):
    """Pitfall 6: an existing non-null order_id short-circuits via _AlreadyConfirmed
    BEFORE the marker check is ever reached (sentinel != needs-manual-review)."""
    plugin, _ = _make_plugin([True])
    write_queue = asyncio.Queue()

    with (
        patch("core.orchestrator.get_item_order_state_sync", return_value=(True, "ORD-EXISTING")),
        patch(
            "core.orchestrator.get_place_order_marker_sync",
            return_value="2026-07-02T00:00:00+00:00",
        ) as mock_marker,
        patch("core.orchestrator.increment_checkout_attempts_sync") as mock_inc,
        patch("core.confirmation.detect_order_confirmation", new=AsyncMock()),
        patch("asyncio.sleep", new=AsyncMock()),
    ):
        await _try_auto_buy(plugin, "Widget", "https://fake.com/item", write_queue, None)

    plugin.auto_buy.assert_not_awaited()
    mock_marker.assert_not_called()
    assert mock_inc.call_count == 0
    assert write_queue.empty()


@pytest.mark.asyncio
async def test_no_retry_loop_in_orchestrator():
    """Structural: orchestrator must not contain `for attempt in range(` loops.

    The only permitted location for `for attempt in range(policy.max_attempts)` is
    core/retry.py (the single source of retry logic, REL-08).
    """
    import ast
    from pathlib import Path

    orchestrator_src = (Path(__file__).parent.parent / "core" / "orchestrator.py").read_text()
    tree = ast.parse(orchestrator_src)
    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.For):
            continue
        if not isinstance(node.iter, ast.Call):
            continue
        func = node.iter.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
        if name == "range" and isinstance(node.target, ast.Name) and node.target.id == "attempt":
            violations.append(f"orchestrator.py:{node.lineno}")
    assert not violations, f"for-attempt-in-range found in orchestrator: {violations}"
