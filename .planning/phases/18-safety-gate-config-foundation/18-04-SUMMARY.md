---
phase: 18-safety-gate-config-foundation
plan: "04"
subsystem: testing
tags: [place_order_guarded, monitor_only, test_mode, safety-gate, BUY-02, pytest, asyncio]

requires:
  - phase: 18-02
    provides: place_order_guarded concrete async method on RetailerPlugin ABC

provides:
  - All 7 bundled plugins route their final place-order click through place_order_guarded
  - BestBuy unconditional-click gap (confirmed BUY-02 hole) is closed
  - Amazon ad-hoc test_mode if/else block replaced by guarded return
  - CI enforcement: grep assertion + 7-plugin monitor_only zero-write integration test
  - Orchestrator cross-check: fake_plugin monitor_only=True yields zero purchased writes

affects: [phases 19-24, any new plugin adding auto_buy]

tech-stack:
  added: []
  patterns:
    - "Plugin reroute: replace final place_order.click()+return True with return await self.place_order_guarded(place_order.click)"
    - "Safety gate CI: static grep assertion ensures place-order selectors only appear with place_order_guarded"
    - "7-plugin integration test: importlib loads real classes, calls guard directly, asserts False return and zero click invocations"

key-files:
  created:
    - tests/test_safety_gate.py
  modified:
    - plugins/shopbot_plugin_amazon.py
    - plugins/shopbot_plugin_bestbuy.py
    - plugins/shopbot_plugin_walmart.py
    - plugins/shopbot_plugin_target.py
    - plugins/shopbot_plugin_gamestop.py
    - plugins/shopbot_plugin_newegg.py
    - plugins/shopbot_plugin_squareenix.py
    - tests/test_plugin_bestbuy.py

key-decisions:
  - "Amazon pre-buy-now test_mode pause preserved; only the place-order if/else block (L412-425) was replaced"
  - "Amazon test_mode variable at L391 removed as now-unused after reroute"
  - "BestBuy test fixed: _make_config now accepts test_mode/monitor_only kwargs; returns-True test sets test_mode=False"
  - "7-plugin integration test calls place_order_guarded directly (not full auto_buy) to avoid needing a fake browser per plugin"

patterns-established:
  - "Plugin final-click reroute: one-liner return await self.place_order_guarded(place_order.click) replaces click+SUCCESS log+return True"
  - "CI grep gate: selector presence in source implies place_order_guarded presence (T-18-10)"

requirements-completed: [BUY-02]

duration: 18min
completed: "2026-06-11"
---

# Phase 18 Plan 04: Plugin place_order_guarded Reroute + CI Enforcement Summary

**All 7 bundled plugins now route their final place-order DOM click through place_order_guarded, closing BestBuy's confirmed unconditional-click gap and replacing Amazon's ad-hoc test_mode if/else; enforced by a static grep CI test and a 7-plugin monitor_only zero-write integration test.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-06-11T15:21:00Z
- **Completed:** 2026-06-11T15:39:00Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- Rerouted all 7 plugins (Amazon, BestBuy, Walmart, Target, GameStop, Newegg, SquareEnix) to call `return await self.place_order_guarded(place_order.click)` as their final place-order step
- Closed BestBuy's confirmed BUY-02 gap: the unconditional `await place_order.click()` that fired regardless of test_mode is gone
- Created `tests/test_safety_gate.py` with three tests: grep enforcement, 7-plugin monitor_only suppression, and orchestrator cross-check
- Full suite 570 passed, 2 skipped after both tasks

## Task Commits

1. **Task 1: Reroute final place-order click in all 7 plugins** - `f772479` (feat)
2. **Task 2: Create tests/test_safety_gate.py** - `963dbb4` (test)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `plugins/shopbot_plugin_amazon.py` - Replace 14-line test_mode if/else block with guarded return; remove now-unused test_mode variable; preserve pre-buy-now test_mode pause
- `plugins/shopbot_plugin_bestbuy.py` - Replace unconditional click+return True with guarded return (BUY-02 gap closed)
- `plugins/shopbot_plugin_walmart.py` - Replace click+return True with guarded return
- `plugins/shopbot_plugin_target.py` - Replace click+return True with guarded return
- `plugins/shopbot_plugin_gamestop.py` - Replace click+return True with guarded return
- `plugins/shopbot_plugin_newegg.py` - Replace click+return True with guarded return
- `plugins/shopbot_plugin_squareenix.py` - Replace click+return True with guarded return
- `tests/test_safety_gate.py` - New: grep enforcement + 7-plugin integration + orchestrator cross-check
- `tests/test_plugin_bestbuy.py` - Fix: _make_config now sets explicit test_mode/monitor_only; returns-True test uses test_mode=False

## Decisions Made

- The pre-buy-now test_mode pause in Amazon (checking the browser before clicking buy-now) was preserved unchanged; only the final place-order if/else block was replaced
- The Amazon test_mode variable assignment at the old L391 was removed since it was only referenced in the now-replaced if/else block
- The 7-plugin integration test calls `place_order_guarded` directly rather than driving a full `auto_buy` run; this avoids the need to set up a complete fake browser session for each of the 7 plugins while still exercising the exact guard method at every call site
- BestBuy's existing test `test_autobuy_returns_true_without_direct_db_write` was fixed: with `place_order_guarded` now gating the click, a MagicMock config (truthy test_mode) correctly suppressed the click; the test was updated to use `test_mode=False, monitor_only=False` to exercise the "allowed" live-mode path

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_plugin_bestbuy regression after reroute**
- **Found during:** Task 1 (per-plugin regression check)
- **Issue:** `test_autobuy_returns_true_without_direct_db_write` expected `auto_buy` to return True, but `_make_config()` returned a MagicMock where `cfg.debug.test_mode` is truthy, causing `place_order_guarded` to suppress the click and return False
- **Fix:** Added `test_mode` and `monitor_only` keyword args to `_make_config()`; updated the returns-True test to pass `test_mode=False, monitor_only=False`
- **Files modified:** `tests/test_plugin_bestbuy.py`
- **Verification:** 104 per-plugin tests passed; full suite 570 passed
- **Committed in:** f772479 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - regression in existing test)
**Impact on plan:** The fix is necessary for the test to accurately test the live-mode purchase path. No scope creep.

## Issues Encountered

None beyond the test regression documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- BUY-02 is fully satisfied: all 7 plugins route through place_order_guarded; CI enforces this with a static grep test and a 7-plugin integration test
- Phase 18 complete: all 4 plans executed (config schema, ABC guard, CLI wire-up, plugin reroute + tests)
- Phase 19 (Checkout Flow) can proceed: the safety gate foundation is in place; any new auto_buy plugin will inherit place_order_guarded automatically from the ABC

## Threat Flags

None - no new network endpoints, auth paths, file access patterns, or schema changes introduced.

---

*Phase: 18-safety-gate-config-foundation*
*Completed: 2026-06-11*
