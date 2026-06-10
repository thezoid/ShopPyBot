---
phase: 17-test-hardening
plan: 03
subsystem: testing
tags: [pytest, sqlite3, asyncio, coverage, price-monitoring, migration]

requires:
  - phase: 16-price-monitoring
    provides: initialize_db v3.0 migration, get_price_alert_state_sync, get_item_price_config_sync, _pct_from_target, _pct_drop_from_last, _evaluate_price_triggers, _check_and_buy get_price block

provides:
  - PR-01: v2.0-schema in-place DB migration fixture (criterion-3 required gap) -- models.py:48-81 ALTER branch now covered
  - PR-04: row-None sentinels for get_price_alert_state_sync (models.py:198) and get_item_price_config_sync (models.py:246)
  - PR-02: denominator guard tests for _pct_from_target and _pct_drop_from_last (orchestrator.py:70,77)
  - PR-03: _evaluate_price_triggers early-return tests for None row and (None,None) config (orchestrator.py:123,126)
  - AB-01: get_price error isolation test -- RuntimeError caught/logged, availability path still runs (orchestrator.py:209-210)
  - AB-02: get_price sequencing tests -- called when available=False, not called when check_availability raises (orchestrator.py:201-203)

affects: [17-04-plugin-abc, future-phase-regression]

tech-stack:
  added: []
  patterns:
    - "Raw sqlite3.connect(models.DB_PATH) under tmp_data_dir to build hand-crafted v2.0 schema fixtures for migration testing"
    - "AsyncMock side_effect=RuntimeError for get_price/check_availability error-path isolation tests"
    - "MagicMock dispatcher with AsyncMock notify for assert_not_awaited checks on early-return paths"

key-files:
  created: []
  modified:
    - tests/test_price_history.py
    - tests/test_price_alert.py

key-decisions:
  - "PR-03 uses tmp_data_dir + no update_item_price_config_sync call (fields default to NULL) for the (None,None) sub-case -- avoids patching, exercises real DB path"
  - "AB-01 asserts the write_queue received set_available to confirm availability path ran after get_price exception -- cleaner than spy on get_item_notification_state_sync"
  - "AB-02 sub-case A uses plugin.check_availability = AsyncMock(return_value=False) override on fake_plugin instance so get_price is a separate AsyncMock with trackable call_count"

patterns-established:
  - "Migration fixture pattern: raw sqlite3.connect(models.DB_PATH) builds pre-migration schema, PRAGMA table_info before and after to assert column changes, SELECT to assert data survival"

requirements-completed: [STAB-03]

duration: 8min
completed: 2026-06-10
---

# Phase 17 Plan 03: Price + get_price Integration Tests Summary

**Six deterministic tests cover the v2.0-DB in-place migration fixture, denominator guards, trigger early-returns, row-None sentinels, and get_price error isolation + sequencing -- models.py:48-81/198/246 and orchestrator.py:70/77/123/126/209-210 now CI-covered.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-06-10T00:00:00Z
- **Completed:** 2026-06-10T00:08:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- PR-01: the criterion-3 required fixture (hand-built v2.0 items table, migrate in place, legacy row survives, idempotent second run) is now in CI
- PR-02/03/AB-01/AB-02 close the remaining price-surface and get_price-sequencing gaps from 17-RESEARCH.md
- Full suite rose from 540 to 546 passed (2 skipped); no regressions

## Task Commits

1. **Task 1: PR-01 v2.0 migration fixture + PR-04 row-None sentinels** - `95b95e1` (test)
2. **Task 2: PR-02/03 trigger guards + AB-01/02 get_price integration** - `0cc8f8f` (test)

**Plan metadata:** (see final-commit below)

## Files Created/Modified

- `tests/test_price_history.py` - Added test_v2_schema_db_migrates_to_v3_in_place (PR-01) and test_price_config_and_alert_state_for_missing_item (PR-04)
- `tests/test_price_alert.py` - Added test_pct_helpers_guard_nonpositive_denominator (PR-02), test_evaluate_price_triggers_skips_when_no_config (PR-03), test_get_price_error_is_isolated_and_does_not_propagate (AB-01), test_get_price_invoked_alongside_check_availability_sequencing (AB-02)

## Decisions Made

- PR-03 uses a real DB path (initialize_db + add_items_sync without seeding config) rather than patching get_item_price_config_sync; ensures both the row-None branch and the (None,None) config branch are exercised through the actual executor call
- AB-01 confirms availability path via write_queue content (set_available tuple) rather than a spy on models functions -- simpler and more direct
- AB-02 overrides check_availability and get_price as separate AsyncMocks on the fake_plugin instance to get independent call_count tracking

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- STAB-03 criterion 3 (price comparison/threshold guards, price_history schema + v2.0 migration, dedup-state sentinels) fully covered
- STAB-03 criterion 4 integration half (get_price alongside check_availability) fully covered
- Ready for Phase 17 Plan 04 (AB-03/AB-04 plugin ABC additions)

## Self-Check

**Files:**
- tests/test_price_history.py: FOUND (11 tests)
- tests/test_price_alert.py: FOUND (21 tests)

**Commits:**
- 95b95e1: FOUND
- 0cc8f8f: FOUND

## Self-Check: PASSED

---
*Phase: 17-test-hardening*
*Completed: 2026-06-10*
