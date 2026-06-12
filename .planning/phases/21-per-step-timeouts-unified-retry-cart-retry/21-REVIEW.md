---
phase: 21-per-step-timeouts-unified-retry-cart-retry
reviewed: 2026-06-11T00:00:00Z
depth: standard
files_reviewed: 15
files_reviewed_list:
  - core/retry.py
  - core/orchestrator.py
  - core/plugin_base.py
  - models.py
  - plugins/shopbot_plugin_amazon.py
  - plugins/shopbot_plugin_bestbuy.py
  - tests/test_retry.py
  - tests/test_cart_retry.py
  - tests/test_no_retry_loops.py
  - tests/test_models.py
  - tests/test_orchestrator.py
  - tests/test_plugin_amazon.py
  - tests/test_plugin_bestbuy.py
  - tests/test_plugin_base.py
  - tests/test_checkout_form_fill.py
findings:
  critical: 2
  warning: 3
  info: 2
  total: 7
status: issues_found
---

# Phase 21: Code Review Report

**Reviewed:** 2026-06-11T00:00:00Z
**Depth:** standard
**Files Reviewed:** 15
**Status:** issues_found

## Summary

Phase 21 introduces per-step `asyncio.timeout` blocks in both plugin `auto_buy` methods, a unified `RetryPolicy`/`with_retry` backoff engine in `core/retry.py`, and cart-retry logic via `_try_auto_buy` + `_pre_attempt_check` in the orchestrator. The `core/retry.py` module itself is clean and the DB schema additions are correct. The no-retry-loop AST guard is non-vacuous and correctly exempts the `_` loop-variable poll loops in `captcha.py` and `stealth.py`.

Two BLOCKER defects exist, both on the safety-critical auto-buy money path. The first is an incorrect `should_retry` predicate that triggers a retry when a real order has already been placed. The second is an incomplete idempotency guard in `_pre_attempt_check` that fails to detect the legacy-purchased state. Together these create a confirmed double-buy vector in the `success=True, order_id=None` scenario.

## Critical Issues

### CR-01: should_retry retries on (success=True, order_id=None) -- double-buy vector

**File:** `core/orchestrator.py:276`
**Issue:** The `should_retry` lambda is `lambda r: not r[0] or r[1] is None`. When `_attempt_buy` returns `(True, None)` (order placed successfully, confirmation detection failed), the condition evaluates to `not True or True` = `True`, triggering another attempt. The next `on_attempt` call (`_pre_attempt_check`) reads the DB, but the write-queue enqueue only happens AFTER `with_retry` returns (by design, WR-02). At the time of the pre-check the DB still shows `purchased=0, order_id=NULL`. Nothing prevents a second `auto_buy()` call. The order is placed twice.

This is the exact scenario the cart-retry mechanism is intended to guard against. The `should_retry` predicate is inverted for the confirmed-but-undetected case.

**Fix:** Stop retrying once `success=True`, regardless of whether `order_id` was detected. Only retry on `success=False`. If obtaining a confirmed `order_id` is desired as a best-effort upgrade, that should be a separate non-retrying detection pass after `with_retry`, not a retry trigger.

```python
# BEFORE (line 276):
should_retry=lambda r: not r[0] or r[1] is None,

# AFTER: only retry on auto_buy failure
should_retry=lambda r: not r[0],
```

### CR-02: _pre_attempt_check ignores purchased=True (legacy path not idempotency-guarded)

**File:** `core/orchestrator.py:249-252`
**Issue:** `_pre_attempt_check` reads `get_item_order_state_sync` which returns `(purchased: bool, order_id: str | None)`, but discards the `purchased` flag (assigned to `_`) and raises `_AlreadyConfirmed` only when `order_id is not None`. An item purchased via the legacy path (`update_item_purchased_sync`, which sets `purchased=1` but leaves `order_id=NULL`) is invisible to this guard. If the write-queue drains the legacy write between attempts, a subsequent retry still calls `auto_buy()` because `existing_order_id is None` never fires. The comment on the function says "raises _AlreadyConfirmed when a prior confirmed order_id is found" which is accurate but undersells the gap: `purchased=True` with no `order_id` is also an already-bought state.

**Fix:** Also short-circuit when `purchased=True`.

```python
async def _pre_attempt_check(loop, link: str, platform: str) -> None:
    purchased, existing_order_id = await loop.run_in_executor(
        None, get_item_order_state_sync, link
    )
    if existing_order_id is not None:
        writeLog(
            f"[{platform}] prior confirmed order_id={existing_order_id} -- skipping retry",
            "INFO",
        )
        raise _AlreadyConfirmed(existing_order_id)
    if purchased:
        writeLog(
            f"[{platform}] item already purchased (legacy path) -- skipping retry",
            "INFO",
        )
        raise _AlreadyConfirmed("")   # or a separate sentinel
    await loop.run_in_executor(None, increment_checkout_attempts_sync, link)
```

Alternatively, introduce a second sentinel class `_AlreadyPurchased` to distinguish the two stop conditions in the caller, which currently only logs `order_id` from the exception.

## Warnings

### WR-01: login() is not wrapped in asyncio.timeout in either plugin auto_buy

**File:** `plugins/shopbot_plugin_amazon.py:384`, `plugins/shopbot_plugin_bestbuy.py:344`
**Issue:** Both `auto_buy` implementations call `await self.login()` without an enclosing `asyncio.timeout`. The `login()` method navigates pages, clicks buttons, and calls `_wait_user_action` (which has its own 300-second timeout). If the login page hangs before reaching `_wait_user_action`, the auto-buy coroutine can block indefinitely, holding the per-plugin poll task and preventing any further checks for that plugin. This is inconsistent with the stated design goal of per-step timeouts for every DOM stage.

**Fix:** Wrap both `login()` calls in `asyncio.timeout(step_timeout_secs)` or a separate longer timeout (e.g. `login_timeout_secs`). Note that doing so will increase the timeout block count, invalidating the AST count assertions in `test_amazon_auto_buy_has_six_timeout_blocks` and `test_bestbuy_auto_buy_has_eight_timeout_blocks`.

```python
self._checkout_stage = "login"
async with asyncio.timeout(step_timeout_secs):
    await self.login()
```

### WR-02: test_cart_retry.py has no @pytest.mark.asyncio but relies on asyncio_mode=auto implicit behavior

**File:** `tests/test_cart_retry.py` (all async test functions, e.g. line 54)
**Issue:** None of the async `test_` functions in `test_cart_retry.py` use `@pytest.mark.asyncio`. They work today because `pyproject.toml` sets `asyncio_mode = "auto"`, but the `_attempt_buy` tests at lines 54-88 are not marked at all, even informally. If the project ever scopes `asyncio_mode` to specific directories or switches to explicit mode (e.g. pytest-asyncio 0.24+ default), all of these tests silently skip or fail to execute. The existing tests in `test_retry.py` that DO use `@pytest.mark.asyncio` set the right precedent.

**Fix:** Add `@pytest.mark.asyncio` to the four `async def test_` functions in the `_attempt_buy` block (lines 54-88) for forward-compatibility, or document the auto-mode dependency explicitly at the module top.

### WR-03: no test covers the (success=True, order_id=None) retry behavior

**File:** `tests/test_cart_retry.py`
**Issue:** The most dangerous retry path -- `auto_buy()` returns True but confirmation detection returns None -- is not tested for retry semantics. `test_single_enqueue_on_success_legacy` (line 213) tests that a single enqueue happens, but does not test whether `auto_buy` is called a second time when `order_id=None`. Given CR-01 above, this is the case where the current code places a double order. A test asserting `plugin.auto_buy.await_count == 1` when `auto_buy=True` and `detect_order_confirmation=None` with `max_cart_retries=3` would have caught CR-01.

**Fix:** Add a test:

```python
async def test_no_retry_on_success_with_no_order_id(tmp_data_dir):
    """auto_buy success + undetected order_id must NOT cause a retry (no double-buy)."""
    plugin, _ = _make_plugin([True, True, True])
    plugin.config.checkout = _make_checkout_config(max_cart_retries=3)
    write_queue = asyncio.Queue()

    with (
        patch("core.orchestrator.get_item_order_state_sync", return_value=(False, None)),
        patch("core.orchestrator.increment_checkout_attempts_sync"),
        patch("core.confirmation.detect_order_confirmation", new=AsyncMock(return_value=None)),
        patch("asyncio.sleep", new=AsyncMock()),
    ):
        await _try_auto_buy(plugin, "Widget", "https://fake.com/item", write_queue, None)

    assert plugin.auto_buy.await_count == 1, "Must not retry when auto_buy succeeded"
    assert write_queue.qsize() == 1
```

## Info

### IN-01: Magic number 300 (wait_user_action timeout) is duplicated in both plugins

**File:** `plugins/shopbot_plugin_amazon.py:97`, `plugins/shopbot_plugin_bestbuy.py:59`
**Issue:** The 300-second unattended guard in `_wait_user_action` is duplicated verbatim in both plugins. Both implementations are identical except for the `play_notification_sound()` call in Amazon. A shared constant or base-class helper would reduce drift risk.

**Fix:** Define `_USER_ACTION_TIMEOUT_SECS = 300` at module level in each file, or move the method to `RetailerPlugin` base class (which would require addressing the `play_notification_sound()` call asymmetry).

### IN-02: _pre_attempt_check silently discards purchased flag (misleading variable name)

**File:** `core/orchestrator.py:249`
**Issue:** The purchased return value from `get_item_order_state_sync` is assigned to `_` (convention for "intentionally ignored"), but the docstring says the function checks DB state for idempotency. The discarded value is relevant to correctness (see CR-02), so using `_` actively misleads future readers into thinking the purchased flag was checked and found irrelevant.

**Fix:** Assign to a named variable even if the guard is not yet added, to signal the value exists:

```python
purchased, existing_order_id = await loop.run_in_executor(
    None, get_item_order_state_sync, link
)
```

---

_Reviewed: 2026-06-11T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
