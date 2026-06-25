---
phase: 21-per-step-timeouts-unified-retry-cart-retry
plan: "04"
subsystem: orchestrator
tags: [cart-retry, idempotency, retry-policy, buy-safety, wr-02]
dependency_graph:
  requires: [21-01, 21-02, 21-03]
  provides: [cart-retry-loop, attempt-buy-helper, idempotency-short-circuit]
  affects: [core/orchestrator.py, tests/test_orchestrator.py]
tech_stack:
  added: []
  patterns: [with_retry+RetryPolicy from core/retry.py, _AlreadyConfirmed sentinel exception, on_attempt pre-read pattern]
key_files:
  created: [tests/test_cart_retry.py]
  modified: [core/orchestrator.py, tests/test_orchestrator.py]
decisions:
  - "_AlreadyConfirmed sentinel exception raised in on_attempt to abort with_retry loop cleanly; avoids out-of-band flag state"
  - "getattr(plugin.config, 'checkout', None) or CheckoutConfig() fallback keeps existing tests with config=None working without requiring fixture changes"
  - "_pre_attempt_check extracted as module-level coroutine so _try_auto_buy stays under 30 lines while on_attempt logic is readable and testable"
  - "enqueue stays in _enqueue_buy_result called after with_retry; preserves WR-02 exactly-one-enqueue invariant lexically outside the retry loop"
metrics:
  duration: "~20 min"
  completed: "2026-06-12"
  tasks: 1
  files: 3
requirements: [BUY-05, REL-08]
---

# Phase 21 Plan 04: Cart-Retry Loop Summary

Cart-retry loop wrapping `_attempt_buy` via `with_retry` + `RetryPolicy` from `CheckoutConfig`. Pre-attempt DB re-read raises `_AlreadyConfirmed` sentinel to abort with zero further `auto_buy` calls when an order is already confirmed; single enqueue stays outside the loop (WR-02).

## What Was Built

**`core/orchestrator.py`** -- four new/refactored helpers:

- `_attempt_buy(plugin, link) -> tuple[bool, str|None]`: retryable unit; calls `auto_buy` and `detect_order_confirmation`; no enqueue; returns `(False, None)` on auto_buy failure/exception and `(True, None)` on confirmation detection error.
- `_pre_attempt_check(loop, link, platform)`: called via `on_attempt` before each attempt; re-reads `get_item_order_state_sync`; raises `_AlreadyConfirmed(order_id)` if order already confirmed; otherwise calls `increment_checkout_attempts_sync`.
- `_enqueue_buy_result(...)`: single confirmed/legacy enqueue after the retry loop; keeps WR-02 lexically enforced.
- `_try_auto_buy` (refactored): 25-line cart-retry wrapper; builds `RetryPolicy(max_attempts=max_cart_retries+1, ...)`; catches `_AlreadyConfirmed` to exit cleanly; calls `_enqueue_buy_result` only on success.

**`tests/test_cart_retry.py`** -- 13 new tests:
- 4 unit tests for `_attempt_buy` (false/success/detection-error/exception paths)
- 9 integration tests for `_try_auto_buy` (no-double-buy, max-retries, 0-retries, attempt counter ordering, confirmed enqueue, legacy enqueue, backoff sleep, idempotency on second attempt, structural no-retry-loop assertion)

**`tests/test_orchestrator.py`** -- 5 existing `_try_auto_buy` tests patched with `get_item_order_state_sync` and `increment_checkout_attempts_sync` mocks (Rule 1 fix: tests now reach DB helpers that didn't exist before).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added config=None guard in _try_auto_buy**
- **Found during:** Task 1 verification (test_orchestrator.py test failures)
- **Issue:** `plugin.config.checkout` crashes when `config=None`; pre-existing `fake_plugin` fixture passes `config=None` by default
- **Fix:** `getattr(plugin.config, "checkout", None) or CheckoutConfig()` fallback so tests with no config work without requiring fixture changes
- **Files modified:** `core/orchestrator.py`
- **Commit:** a82a843

**2. [Rule 1 - Bug] Patched existing orchestrator tests that call _try_auto_buy directly**
- **Found during:** Task 1 verification
- **Issue:** 5 tests in `test_orchestrator.py` call `_try_auto_buy` without patching `get_item_order_state_sync` or `increment_checkout_attempts_sync`; the new cart-retry loop hits DB helpers that hit a non-existent SQLite table
- **Fix:** Added `patch("core.orchestrator.get_item_order_state_sync", return_value=(False, None))` and `patch("core.orchestrator.increment_checkout_attempts_sync")` to the 5 affected tests
- **Files modified:** `tests/test_orchestrator.py`
- **Commit:** a82a843

## Success Criteria Verification

- `_attempt_buy(plugin, link) -> (bool, str|None)` extracted: confirmed
- Cart-retry via `with_retry + RetryPolicy(max_attempts=max_cart_retries+1)`: confirmed
- `increment_checkout_attempts_sync` called once per attempt BEFORE `auto_buy`: confirmed (test_checkout_attempts_increments_before_each_attempt passes)
- Pre-existing confirmed `order_id` in DB exits with zero `auto_buy` calls: confirmed (test_confirmed_order_in_db_zero_auto_buy_calls passes)
- `max_cart_retries=0` yields exactly 1 attempt: confirmed
- All attempts fail: no enqueue: confirmed
- Single enqueue outside retry loop (WR-02): confirmed (test_single_enqueue_on_success_confirmed and test_single_enqueue_on_success_legacy pass)
- No `for attempt in range(` in orchestrator: confirmed (test_no_retry_loop_in_orchestrator + test_no_retry_loops.py pass)
- All functions under 30 lines: confirmed (AST check passed)
- Full suite: 668 passed, 2 skipped (was 655+2 before plan)

## Threat Mitigations Applied

| Threat ID | Applied |
|-----------|---------|
| T-21-08 (double-buy on misdetected order) | _pre_attempt_check re-reads order_id before each attempt; non-None exits with zero auto_buy calls |
| T-21-09 (runaway cart-retry) | with_retry bounded by RetryPolicy(max_attempts=max_cart_retries+1); ge=0 on CheckoutConfig.max_cart_retries |
| T-21-10 (duplicate enqueue) | write_queue.put() in _enqueue_buy_result, called after with_retry; lexically outside the loop |
| T-21-11 (CVV/secret in retry log) | exc.__class__.__name__ used in _attempt_buy; no str(exc), no self._cvv |

## Task Commits

| Task | Commit | Files |
|------|--------|-------|
| 1: Extract _attempt_buy + cart-retry wrapper | a82a843 | core/orchestrator.py, tests/test_orchestrator.py, tests/test_cart_retry.py |

## Self-Check: PASSED

- `E:\repos\ShopPyBot\core\orchestrator.py` exists: FOUND
- `E:\repos\ShopPyBot\tests\test_cart_retry.py` exists: FOUND
- Commit `a82a843` exists: FOUND
- 668 tests pass (full suite): PASSED
