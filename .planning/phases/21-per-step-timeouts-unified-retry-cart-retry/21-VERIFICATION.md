---
phase: 21-per-step-timeouts-unified-retry-cart-retry
verified: 2026-06-11T00:00:00Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Trigger a real slow drop where one DOM step (e.g. cart-navigate) hangs for longer than step_timeout_secs"
    expected: "asyncio.timeout fires; auto_buy returns False; stage is logged in the except Exception block; _attempt_buy returns (False, None); with_retry retries up to max_cart_retries; item is not immediately re-submitted outside the retry budget; no half-submitted or duplicate order"
    why_human: "Cannot test asyncio.timeout behavior under real slow network or unresponsive DOM without a live browser; the timeout fires TimeoutError which auto_buy catches and logs, returning False -- correct behavior requires live verification to confirm the browser is not left in a partial-checkout state"
---

# Phase 21: Per-Step Timeouts, Unified Retry, Cart Retry — Verification Report

**Phase Goal:** Checkout attempts are bounded in time and retries, and all retry/backoff logic flows through one shared RetryPolicy so supervisor restarts and cart retries cannot compound into a runaway loop.
**Verified:** 2026-06-11T00:00:00Z
**Status:** human_needed (all 5 must-haves verified; one UAT debt item deferred to live testing)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | REL-08: `core/retry.py` defines single `RetryPolicy` dataclass + `with_retry` + `compute_delay`; AST guard in `tests/test_no_retry_loops.py` asserts no `for attempt in range(` outside `core/retry.py`; non-vacuous and not false-flagging poll loops | VERIFIED | `core/retry.py` lines 20-71; test file lines 26-88; poll loops exempt by `_` variable name, not whitelist; non-vacuous guard at line 38 asserts file existence |
| 2 | BUY-06: each Amazon (6) + BestBuy (8) DOM stage under its own `asyncio.timeout(step_timeout_secs)`; NO single outer timeout; NO per-item ceiling | VERIFIED | Amazon: 6 `async with asyncio.timeout(step_timeout_secs)` blocks at lines 394, 407, 431, 440, 450, 459; BestBuy: 8 blocks at lines 297, 301, 310, 317, 336, 359, 380, 388; no outer timeout in `orchestrator.py` |
| 3 | BUY-06: `self._checkout_stage` tracks progress; on timeout (`TimeoutError`) stage is logged and item not immediately re-submitted outside retry budget | VERIFIED | Stage set before each block in both plugins; `except Exception as exc` in `auto_buy` logs `self._checkout_stage!r`; `TimeoutError` is caught (Python 3.13: `TimeoutError` is subclass of `Exception`); `auto_buy` returns `False`; `_attempt_buy` returns `(False, None)`; `should_retry=lambda r: not r[0]` returns `True`; retry budget governs re-submission |
| 4 | BUY-05: cart-retry re-reads DB order state before each attempt via `_pre_attempt_check`; `checkout_attempts` increments once per attempt; bounded by `max_cart_retries` (total = 1 + max_cart_retries) | VERIFIED | `_pre_attempt_check` (orchestrator.py lines 242-265) calls `get_item_order_state_sync` then `increment_checkout_attempts_sync`; `RetryPolicy(max_attempts=cfg.max_cart_retries + 1, ...)`; test `test_retries_up_to_max_then_stops` confirms count=3 for max_cart_retries=2 |
| 5 | BUY-05 NO-DOUBLE-BUY: `should_retry` retries ONLY on `auto_buy=False`; `_pre_attempt_check` short-circuits on `purchased=True` OR `order_id not None`; exactly one write-queue enqueue per buy (WR-02); regression tests `test_no_retry_on_success_with_no_order_id` and `test_legacy_purchased_item_zero_auto_buy_calls` exist and pass | VERIFIED | `should_retry=lambda r: not r[0]` (orchestrator.py line 283); `_pre_attempt_check` checks `existing_order_id is not None` AND `purchased is True`, both raise `_AlreadyConfirmed`; `_enqueue_buy_result` called OUTSIDE `with_retry`; both regression tests present and pass (28/28 green) |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `core/retry.py` | `RetryPolicy`, `compute_delay`, `with_retry` | VERIFIED | 71 lines; all three exports present; no plugin/models imports; docstring notes P22 reuse |
| `tests/test_no_retry_loops.py` | AST guard for REL-08 | VERIFIED | Non-vacuous (asserts file existence); correctly excludes `_` poll loops in captcha.py/stealth.py by structural predicate, not whitelist |
| `tests/test_retry.py` | RetryPolicy/compute_delay/with_retry unit tests | VERIFIED | 12 tests; covers determinism, jitter bounds, attempt count, sleep sequencing, CancelledError propagation |
| `tests/test_cart_retry.py` | Cart-retry + no-double-buy tests | VERIFIED | 16 tests including CR-01 regression `test_no_retry_on_success_with_no_order_id` and CR-02 regression `test_legacy_purchased_item_zero_auto_buy_calls`; all pass |
| `plugins/shopbot_plugin_amazon.py` | 6 per-step timeouts in `auto_buy` | VERIFIED | Lines 394, 407, 431, 440, 450, 459; `login()` intentionally un-timed with documented comment at line 384 |
| `plugins/shopbot_plugin_bestbuy.py` | 8 per-step timeouts in `auto_buy` | VERIFIED | Lines 297, 301, 310, 317, 336, 359, 380, 388; `login()` intentionally un-timed with documented comment at line 344 |
| `core/orchestrator.py` | `_try_auto_buy`, `_pre_attempt_check`, `_attempt_buy` using `with_retry` | VERIFIED | All three functions present; `with_retry` imported and used; no bare retry loop |
| `models.py` | `get_item_order_state_sync`, `increment_checkout_attempts_sync` | VERIFIED | Both functions present; `get_item_order_state_sync` returns `(bool, str|None)` covering both legacy and confirmed states |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `_try_auto_buy` | `core/retry.with_retry` | direct import + call | WIRED | `from core.retry import RetryPolicy, with_retry`; `RetryPolicy(max_attempts=cfg.max_cart_retries + 1, ...)` constructed per call |
| `_try_auto_buy` | `_pre_attempt_check` | `on_attempt=lambda _: _pre_attempt_check(loop, link, platform)` | WIRED | orchestrator.py line 284 |
| `_attempt_buy` result | `should_retry` predicate | `lambda r: not r[0]` | WIRED | Only retries on `success=False`; confirmed `(True, None)` does NOT retry (CR-01 fix) |
| `_pre_attempt_check` | `get_item_order_state_sync` + `increment_checkout_attempts_sync` | `await loop.run_in_executor` | WIRED | Both DB reads are present; `purchased=True` guard raises `_AlreadyConfirmed` (CR-02 fix) |
| `auto_buy` per-step timeout | `_checkout_stage` attribute | `self._checkout_stage = "stage-name"` before each block | WIRED | `plugin._checkout_stage` read in orchestrator.py line 291 for warning log on cart-retry exhaustion |
| P22 supervisor reuse | `RetryPolicy` + `compute_delay` | "no plugin or models imports" constraint in module docstring | WIRED (design contract) | `core/retry.py` imports only `asyncio` and `random`; confirmed zero plugin/models imports |

### Data-Flow Trace (Level 4)

Not applicable — no dynamic data rendering. All artifacts are orchestration logic and test modules.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 28 Phase 21 tests pass | `python -m pytest tests/test_retry.py tests/test_cart_retry.py tests/test_no_retry_loops.py -v` | 28 passed in 1.30s | PASS |
| AST guard non-vacuous: core/retry.py exists | included in above run | `test_no_for_attempt_in_range_outside_retry` PASSED | PASS |
| CR-01 regression: auto_buy success + no order_id does not retry | included in above run | `test_no_retry_on_success_with_no_order_id` PASSED (await_count==1) | PASS |
| CR-02 regression: legacy purchased=True blocks auto_buy | included in above run | `test_legacy_purchased_item_zero_auto_buy_calls` PASSED (not_awaited) | PASS |

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|---------|
| BUY-05 | Cart retry with idempotency guard, checkout_attempts increment, max_cart_retries bound | SATISFIED | `_try_auto_buy` + `_pre_attempt_check`; `get_item_order_state_sync` re-read; `increment_checkout_attempts_sync`; `RetryPolicy(max_attempts=cfg.max_cart_retries + 1)` |
| BUY-06 | Per-step time budget with stage tracking; clean abort on slow step | SATISFIED | 6+8 `asyncio.timeout` blocks; `_checkout_stage` set before each; timeout causes `False` return from `auto_buy`, not crash |
| REL-08 | Single `RetryPolicy` implementation shared by cart-retry and future supervisor | SATISFIED | `core/retry.py` is the sole locus; no `for attempt in range(` outside it; P22 reuse documented and architecturally enforced by zero-import constraint |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `plugins/shopbot_plugin_bestbuy.py` | 313 | `# TODO: verify ".a-dropdown-prompt" is correct for BestBuy cart` | INFO | Open Question 2 from plan; carries forward from `bestbuy_bot.py`; documented with rationale and UAT note — not an unresolved debt marker (has explanation, not tracking number, but not a correctness blocker for Phase 21 scope) |

No `TBD`, `FIXME`, or `XXX` markers found in Phase 21 modified files.

### Human Verification Required

#### 1. Live Per-Step Timeout Behavior Under a Real Slow Drop

**Test:** Configure `step_timeout_secs: 5` in `checkout.step_timeout_secs`. Navigate to a BestBuy or Amazon item page with a network throttle or proxy that causes a single DOM step (e.g. `cart-navigate`) to hang past 5 seconds. Trigger an `auto_buy` attempt.

**Expected:** The per-step `asyncio.timeout` fires `TimeoutError`; the `except Exception` block logs the failed `_checkout_stage`; `auto_buy` returns `False`; `_attempt_buy` returns `(False, None)`; the retry loop retries up to `max_cart_retries` times (not immediately re-submitting beyond budget); the browser is not left mid-checkout with an orphaned session.

**Why human:** Requires a live browser instance, real network conditions or controlled throttle, and visual inspection that the browser is not left in a partial-checkout state (e.g. item in cart but order page never submitted). Cannot verify browser cleanup behavior programmatically without running nodriver against a real retail endpoint.

### Gaps Summary

No gaps. All 5 must-haves are verified with direct codebase evidence. The two BLOCKER defects from the code review (CR-01 double-buy predicate, CR-02 legacy-purchased idempotency gap) were both fixed in the review-fix iteration and confirmed by passing regression tests.

The one UAT item above is live-environment behavior that cannot be tested without a real browser — it is deferred as UAT debt per the autonomous-defer policy, not a gap.

---

_Verified: 2026-06-11T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
