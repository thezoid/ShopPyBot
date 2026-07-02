---
phase: 30-breakfix-hardening
plan: 04
subsystem: checkout-retry
tags: [sqlite, asyncio, idempotency, amazon, bestbuy, run_in_executor]

# Dependency graph
requires:
  - phase: 30-breakfix-hardening
    provides: "plan 30-01: place_order_attempted_at column + mark_place_order_attempted_sync/get_place_order_marker_sync accessors + _PossiblyPlaced retry guard (read side)"
provides:
  - "Amazon auto_buy() write-ahead marker: mark_place_order_attempted_sync called via run_in_executor immediately before place_order_guarded at the place-order stage"
  - "BestBuy auto_buy() parity write-ahead marker: identical pattern at BestBuy's place-order stage"
  - "First plugin->models.py direct-write import edge in the codebase"
affects: [30-05, 30-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Direct synchronous DB write from inside a plugin via run_in_executor, called from an inline `from models import ...` at the exact click-dispatch instant -- not routed through write_queue (crash-durability requires the write complete before the click, not just be enqueued)"

key-files:
  created: []
  modified:
    - plugins/shopbot_plugin_amazon.py
    - plugins/shopbot_plugin_bestbuy.py
    - tests/test_plugin_amazon.py
    - tests/test_plugin_bestbuy.py

key-decisions:
  - "Marker write import (`from models import mark_place_order_attempted_sync`) is inline at the point of use inside auto_buy(), not a top-level module import -- keeps the new plugin->models dependency edge narrow and localized, matching RESEARCH.md Pattern 1's exact example"
  - "BestBuy parity write (Task 2) included rather than deferred -- RESEARCH.md found the byte-identical swallowed-TimeoutError shape at bestbuy:389-396 and recommended closing the now-known symmetric exposure rather than leaving it open"
  - "write_queue source-grep test tightened to skip comment lines -- the new explanatory comments name write_queue by identifier without calling it, which the original literal substring check would have false-flagged"

requirements-completed: [BF-02]

# Metrics
duration: 5min
completed: 2026-07-02
---

# Phase 30 Plan 04: Amazon + BestBuy Place-Order Marker Write Summary

**Amazon and BestBuy `auto_buy()` now durably write `place_order_attempted_at` via an awaited `run_in_executor` call immediately before `place_order_guarded`, closing the write side of the BF-02 double-buy guard whose read side (`_PossiblyPlaced`) shipped in plan 30-01.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-07-02T16:57:06Z
- **Completed:** 2026-07-02T17:01:33Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Amazon's `auto_buy()` now calls `mark_place_order_attempted_sync` (via `run_in_executor`, awaited) immediately before `place_order_guarded(place_order.click)` at the place-order stage -- the exact root-cause site of the swallowed `TimeoutError` (amazon:460-469 pre-fix).
- BestBuy's `auto_buy()` gets the identical parity write at its own place-order stage (bestbuy:389-396 pre-fix), closing a symmetric exposure surfaced by research but not originally scoped in CONTEXT.md.
- Neither write is routed through `write_queue` -- both are direct, awaited, synchronous writes that durably commit before the click fires (D-01).
- Combined with the 30-01 read-side guard (`_PossiblyPlaced` + `_pre_attempt_check`), an injected place-order-stage timeout now latches non-retryable for both live-tested plugins.

## Task Commits

Each task was committed atomically (TDD RED -> GREEN per task):

1. **Task 1: Amazon place-order marker write**
   - `6495e31` (test) - failing marker-before-click ordering test
   - `790e798` (feat) - `mark_place_order_attempted_sync` call via `run_in_executor` before `place_order_guarded`
2. **Task 2 (ISOLATED/DROPPABLE): BestBuy place-order marker write (parity)**
   - `378f973` (test) - failing marker-before-click ordering test (`test_bestbuy_place_order_latched`)
   - `cb37a20` (feat) - identical marker write at BestBuy's place-order stage

**Plan metadata:** (this commit)

## Files Created/Modified
- `plugins/shopbot_plugin_amazon.py` - `from datetime import datetime, timezone` added to imports; inline `from models import mark_place_order_attempted_sync` + `run_in_executor` write inserted immediately before `place_order_guarded` in the place-order stage
- `plugins/shopbot_plugin_bestbuy.py` - identical addition at BestBuy's place-order stage (parity)
- `tests/test_plugin_amazon.py` - `test_amazon_marks_place_order_before_click` (ordering), `test_amazon_place_order_marker_not_via_write_queue` (source-grep, comment-aware)
- `tests/test_plugin_bestbuy.py` - `test_bestbuy_place_order_latched` (ordering), `test_bestbuy_place_order_marker_not_via_write_queue` (source-grep, comment-aware)

## Decisions Made
- Followed RESEARCH.md Pattern 1 exactly: the `models` import is inline inside `auto_buy()` at the point of use rather than a top-level module import, since this is deliberately the first and only plugin->models write edge and should stay narrow/localized.
- Included the BestBuy parity task (Task 2) per RESEARCH.md's Open Question 1 recommendation -- the guard mechanism built in 30-01 is platform-agnostic, and BestBuy has the byte-for-byte identical vulnerable shape, so the marginal cost of closing it now was small relative to leaving a known exposure open.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Tightened write_queue source-grep test to ignore comment lines**
- **Found during:** Task 1 (running `pytest tests/test_plugin_amazon.py` after the GREEN implementation)
- **Issue:** The initial `test_amazon_place_order_marker_not_via_write_queue` test did a literal substring check for `"write_queue" not in source`. The new explanatory code comment ("Not routed through write_queue...") mentions the identifier by name without calling it, which the literal check false-flagged as a violation.
- **Fix:** Rewrote the test to check non-comment lines only (mirrors the existing `test_no_input_call_in_amazon_source` pattern already in the same file), so it correctly asserts no *code* reference to `write_queue` while allowing explanatory comments.
- **Files modified:** `tests/test_plugin_amazon.py` (same fix pattern applied proactively to `tests/test_plugin_bestbuy.py`'s equivalent test before it could hit the same false positive)
- **Verification:** `pytest tests/test_plugin_amazon.py tests/test_plugin_bestbuy.py -x -q` -- 45 passed
- **Committed in:** `790e798` (Task 1 feat commit, test fix bundled with the implementation it was blocking)

---

**Total deviations:** 1 auto-fixed (1 bug fix, in-scope collateral from the task's own new test)
**Impact on plan:** Necessary to keep the new test correct and non-flaky; no scope creep -- the fix only touches the test file the task itself introduced.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- BF-02 write side is complete for both live-tested plugins (Amazon Task 1, BestBuy Task 2 parity); combined with 30-01's read-side guard, the milestone's one HIGH item is code-complete and CI-green.
- Live-environment proof of the double-buy edge remains operator debt per the v4.2 milestone rule (code-complete + CI-green is "done"; live-UAT is a separate deferred checklist item).
- Full suite: 833 passed, 2 skipped (up from the 829/2 baseline -- 4 new tests, no regressions).
- Remaining Phase 30 plans (30-05, 30-06) proceed with BF-03 per-plugin `login()` bool conversions using the 30-03 ABC foundation; this plan did not touch `login()` on either plugin.

---
*Phase: 30-breakfix-hardening*
*Completed: 2026-07-02*

## Self-Check: PASSED

- All 4 modified source/test files present on disk.
- All 4 task commit hashes (6495e31, 790e798, 378f973, cb37a20) found in git log.
- `mark_place_order_attempted_sync` present in both plugin files (2 occurrences each: import + call).
- `write_queue` occurrences in both plugin files are comment-only (no code call sites).
- `pytest tests/test_plugin_amazon.py tests/test_plugin_bestbuy.py -x -q`: 45 passed.
- `pytest -q` (full suite): 833 passed, 2 skipped (baseline 829/2 + 4 new tests, no regressions).
