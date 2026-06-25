---
phase: 19-db-schema-confirmation-detection
plan: "04"
subsystem: orchestrator + plugins
tags: [confirmation, auto-buy, bots, sqlite, BUY-03, BUY-04]
dependency_graph:
  requires: [19-01, 19-02, 19-03]
  provides: [confirmation-path-wired, dispatch-confirmed-branch, last-tab-storage]
  affects: [core/orchestrator.py, plugins/shopbot_plugin_amazon.py, plugins/shopbot_plugin_bestbuy.py]
tech_stack:
  added: []
  patterns:
    - deferred inline import (detect_order_confirmation inside _try_auto_buy)
    - mutually exclusive confirmed/purchased branch (Pitfall 5)
    - getattr-safe _last_tab storage with or-chain fallback
key_files:
  modified:
    - core/orchestrator.py
    - plugins/shopbot_plugin_amazon.py
    - plugins/shopbot_plugin_bestbuy.py
    - tests/test_orchestrator.py
  created:
    - tests/test_amazon_plugin.py
    - tests/test_bestbuy_plugin.py
decisions:
  - _try_auto_buy uses deferred import of detect_order_confirmation inside function body (not module-level) to match existing pattern in _build_event
  - Fake plugin class named AmazonPlugin in orchestrator tests so platform map lookup resolves correctly
  - Task 3 tests co-located with Task 1 TDD cycle (added to test_orchestrator.py during RED/GREEN for Task 1)
metrics:
  duration: "~15min"
  completed: "2026-06-11"
  tasks: 3
  files: 6
---

# Phase 19 Plan 04: Confirmation Wiring Summary

Confirmation detection wired end-to-end: `_try_auto_buy` calls `detect_order_confirmation` after `auto_buy()` returns `True`, enqueues `("confirmed", link, order_id, ts)` on success or logs WARNING and falls back to legacy `("purchased", link)`. `_dispatch_write` routes the `confirmed` tag to `update_item_confirmed_sync`. Amazon and BestBuy plugins store `self._last_tab` before `place_order_guarded` and override `get_active_tab()`.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Wire _try_auto_buy + _dispatch_write confirmed branch | 4279796 | core/orchestrator.py, tests/test_orchestrator.py |
| 2 | _last_tab storage + get_active_tab() override in Amazon + BestBuy | 12b9c47 | plugins/shopbot_plugin_amazon.py, plugins/shopbot_plugin_bestbuy.py, tests/test_amazon_plugin.py, tests/test_bestbuy_plugin.py |
| 3 | Orchestrator confirmed/fallback/dispatch/no-double-buy tests | (in commit 4279796) | tests/test_orchestrator.py |

## Deviations from Plan

### Auto-fixed Issues

None.

### Adjustments

**1. [Rule 1 - Adjustment] _FakePlugin class name required AmazonPlugin for platform map**

- **Found during:** Task 1 GREEN phase
- **Issue:** `fake_plugin()` fixture returns a class named `_FakePlugin`; `_PLATFORM_MAP` only contains `"AmazonPlugin"` and `"BestBuyPlugin"`, so `detect_order_confirmation` returned `None` for `_FakePlugin`, triggering the fallback path even on a confirmation URL. This caused `test_orchestrator_confirmed_path` to assert `'purchased'` instead of `'confirmed'`.
- **Fix:** Created `_make_amazon_plugin()` helper in test_orchestrator.py that builds a class explicitly named `AmazonPlugin`. This is the correct approach per PATTERNS.md (monkeypatching class name context).
- **Files modified:** tests/test_orchestrator.py
- **Commit:** 4279796

## Known Stubs

None. All confirmation paths are fully wired. UAT debt for DOM selectors (`#confirmedOrderId`, `.thank-you-order-number`) is pre-existing from Plan 02 and documented in STATE.md deferred items.

## Threat Flags

No new security surface introduced. The `confirmed` dispatch path only routes `order_id` (not CVV) to `writeLog`. Mitigations T-19-08 through T-19-11 are all satisfied:

- T-19-08: purchased=1 written only via `confirmed` tag with a non-None order_id; fallback uses `purchased` with WARNING
- T-19-09: mutually exclusive if/else in _try_auto_buy; exactly one put per success (asserted by test_no_double_buy_single_put)
- T-19-10: write_queue.put() calls outside any timeout context (verified: no asyncio.timeout in orchestrator.py)
- T-19-11: confirmation log line uses order_id only; self._cvv not adjacent

## Test Results

- `pytest tests/test_orchestrator.py`: 23 passed
- `pytest tests/test_amazon_plugin.py tests/test_bestbuy_plugin.py tests/test_plugin_base.py`: 29 passed
- `pytest` full suite: 597 passed, 2 skipped (prior baseline: 585 + 2 skipped)

## Self-Check: PASSED

Files exist:
- core/orchestrator.py: FOUND (update_item_confirmed_sync imported, _try_auto_buy wired, _dispatch_write has confirmed branch)
- plugins/shopbot_plugin_amazon.py: FOUND (self._last_tab + get_active_tab override)
- plugins/shopbot_plugin_bestbuy.py: FOUND (self._last_tab + get_active_tab override)
- tests/test_orchestrator.py: FOUND (4 new tests)
- tests/test_amazon_plugin.py: FOUND (4 tests)
- tests/test_bestbuy_plugin.py: FOUND (4 tests)

Commits exist:
- 4279796: feat(19-04): wire confirmation detection into _try_auto_buy and _dispatch_write
- 12b9c47: feat(19-04): add _last_tab storage and get_active_tab() override to Amazon and BestBuy plugins
