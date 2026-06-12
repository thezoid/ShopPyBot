---
phase: 21-per-step-timeouts-unified-retry-cart-retry
plan: "03"
subsystem: plugins
tags: [asyncio, timeout, checkout, amazon, bestbuy, BUY-06]

# Dependency graph
requires:
  - phase: 20-checkout-profile
    provides: "CheckoutConfig with step_timeout_secs field; _checkout_profile on plugin base"
provides:
  - "self._checkout_stage: str = '' default on RetailerPlugin ABC (BUY-06)"
  - "Amazon auto_buy: 6 per-stage asyncio.timeout(step_timeout_secs) blocks with _checkout_stage tracking"
  - "BestBuy auto_buy: 8 per-stage asyncio.timeout(step_timeout_secs) blocks with _checkout_stage tracking"
  - "Abort-on-timeout: stage name + exc class logged; auto_buy returns False (no re-submit)"
affects: [21-04-cart-retry, 22-supervisor]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-stage asyncio.timeout(step_timeout_secs) wrapping each DOM await block"
    - "_checkout_stage set BEFORE context manager so readable on TimeoutError"
    - "getattr-safe step_timeout_secs read (default 30) so config=None plugins don't crash"

key-files:
  created: []
  modified:
    - core/plugin_base.py
    - plugins/shopbot_plugin_amazon.py
    - plugins/shopbot_plugin_bestbuy.py
    - tests/test_plugin_base.py
    - tests/test_plugin_amazon.py
    - tests/test_plugin_bestbuy.py
    - tests/test_checkout_form_fill.py

key-decisions:
  - "Inline async with asyncio.timeout() per stage (no _step() helper wrapper) per Claude-discretion in CONTEXT.md"
  - "getattr-safe step_timeout_secs: getattr(getattr(config, 'checkout', None), 'step_timeout_secs', 30) so config=None produces valid int"
  - "login() and BestBuy missing-profile guard not wrapped: user-action gates, not DOM stages"
  - "No single outer timeout around auto_buy; per-item ceiling deferred to Phase 22"
  - "_make_config/_no_op_config test helpers updated to include checkout.step_timeout_secs=30"

requirements-completed: [BUY-06]

# Metrics
duration: 30min
completed: 2026-06-11
---

# Phase 21 Plan 03: Per-Step Timeouts + _checkout_stage Summary

**Six Amazon and eight BestBuy checkout DOM stages each wrapped in asyncio.timeout(step_timeout_secs) with _checkout_stage breadcrumb; TimeoutError returns False and logs the aborted stage name**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-06-11T22:00:00Z
- **Completed:** 2026-06-11T22:30:00Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Added `self._checkout_stage: str = ""` to `RetailerPlugin.__init__` so the attribute always exists before any `auto_buy` runs (Pitfall 5 guard)
- Wrapped all 6 Amazon checkout DOM stages and all 8 BestBuy DOM stages in per-stage `async with asyncio.timeout(step_timeout_secs)`; `_checkout_stage` assigned immediately before each block
- Exception handler in both plugins augmented to include `self._checkout_stage` in log message; `exc.__class__.__name__` used (never `str(exc)`, never `_cvv`) per T-21-07

## Task Commits

1. **Task 1: core/plugin_base.py + test_plugin_base.py** - `ab3e5e6` (feat)
2. **Task 2: Amazon + BestBuy per-step timeouts** - `515e3b4` (feat)

## Files Created/Modified

- `core/plugin_base.py` - Added `self._checkout_stage: str = ""` as fourth __init__ attr (BUY-06)
- `plugins/shopbot_plugin_amazon.py` - 6 per-stage asyncio.timeout blocks; _checkout_stage tracking; augmented except handler
- `plugins/shopbot_plugin_bestbuy.py` - 8 per-stage asyncio.timeout blocks; _checkout_stage tracking; augmented except handler
- `tests/test_plugin_base.py` - 4 new assertions: default "", str type, no AttributeError, API version unchanged
- `tests/test_plugin_amazon.py` - 4 new tests: stage count (6), timeout->False, stage+class logged on timeout, default ""
- `tests/test_plugin_bestbuy.py` - 4 new tests: stage count (8), timeout->False, stage+class logged on timeout, default ""
- `tests/test_checkout_form_fill.py` - Added `checkout.step_timeout_secs = 30` to `_no_op_config()` helper (Rule 1 fix)

## Decisions Made

- Inline `async with asyncio.timeout()` per stage rather than `_step()` helper: simpler, no extra abstraction, matches CONTEXT.md Claude-discretion guidance
- `getattr`-safe step_timeout_secs retrieval so `config=None` plugins degrade to default 30s rather than raising AttributeError
- Stage names match RESEARCH.md exactly: Amazon (navigate, quantity-select, buy-now, place-order-select, cvv-entry, place-order); BestBuy (navigate, add-to-cart, cart-navigate, quantity-select, checkout-proceed, address-fill, cvv-entry, place-order)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed TypeError in 3 existing test helpers caused by missing checkout mock attr**
- **Found during:** Task 2 (running full suite after plugin changes)
- **Issue:** `asyncio.timeout(MagicMock())` raises TypeError; `_make_config` and `_no_op_config` helpers created MagicMock configs without explicit `checkout.step_timeout_secs` integer, so the getattr chain returned a MagicMock object instead of an int
- **Fix:** Added `cfg.checkout.step_timeout_secs = 30` to `_make_config` in `test_plugin_amazon.py`, `test_plugin_bestbuy.py`, and `_no_op_config` in `test_checkout_form_fill.py`
- **Files modified:** tests/test_plugin_amazon.py, tests/test_plugin_bestbuy.py, tests/test_checkout_form_fill.py
- **Verification:** Full suite 655 passed, 2 skipped
- **Committed in:** 515e3b4 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Necessary correctness fix; no scope creep; all 3 affected helpers now consistently typed.

## Issues Encountered

None beyond the auto-fixed test helper issue above.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. All changes are internal to existing plugin methods. T-21-05, T-21-06, T-21-07 mitigations from the plan's threat model are all implemented:
- T-21-05 (DoS / hung stage): each stage has its own asyncio.timeout
- T-21-06 (half-submitted order): per-step (not outer) timeout; place-order is its own isolated stage
- T-21-07 (CVV in log): exc.__class__.__name__ only; test_no_cvv_in_logs.py green

## Next Phase Readiness

- Phase 21-04 (cart retry): `_checkout_stage` is accessible on the plugin instance after auto_buy returns False; orchestrator cart-retry wrapper can read it for logging
- Phase 22 (supervisor / per-item ceiling): `item_timeout_secs` field already in `CheckoutConfig`; per-step timeouts are independent and compose cleanly with an outer per-item ceiling

## Self-Check: PASSED

- `core/plugin_base.py` contains `self._checkout_stage`
- `plugins/shopbot_plugin_amazon.py` contains 6 `asyncio.timeout(step_timeout_secs)` blocks (verified via AST)
- `plugins/shopbot_plugin_bestbuy.py` contains 8 `asyncio.timeout(step_timeout_secs)` blocks (verified via AST)
- Commits ab3e5e6 and 515e3b4 verified in git log
- Full suite: 655 passed, 2 skipped

---
*Phase: 21-per-step-timeouts-unified-retry-cart-retry*
*Completed: 2026-06-11*
