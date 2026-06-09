---
phase: 12-stability-foundation
plan: 01
subsystem: testing
tags: [python, logger, pytest, importlib, yaml, core-paths]

requires:
  - phase: 11-path-migration
    provides: core.paths.config_path() re-reading SHOPBOT_DATA_DIR each call

provides:
  - logger._load_logging_level() reads from core.paths.config_path() at call time
  - TD-1 regression test guarding migrated-config logging_level behavior

affects: [12-02, 12-03, 12-04]

tech-stack:
  added: []
  patterns:
    - "Lazy import of core.paths inside _load_logging_level() mirrors the existing writeLog lazy-import pattern for log_dir"
    - "importlib.reload(logger) in finally block for safe module-state teardown in reload-based tests"

key-files:
  created:
    - tests/test_logger_config_path.py
  modified:
    - logger.py

key-decisions:
  - "Option A (lazy import inside _load_logging_level) chosen over Option B (delete _CONFIG_PATH) to retain the constant for tooling inspection"
  - "Test isolation via finally-block reload: both tests restore logger to original import-time state after each run to prevent _LOGGING_LEVEL bleed"
  - "_CONFIG_PATH constant kept in logger.py with updated comment; it is no longer used in the read path"

patterns-established:
  - "For reload-based logger tests: setenv BEFORE reload (Pitfall 1), restore via finally + delenv + reload"

requirements-completed: [STAB-02]

duration: 3min
completed: 2026-06-09
---

# Phase 12 Plan 01: Stability Foundation (TD-1 logger fix) Summary

**logger._load_logging_level() re-anchored to core.paths.config_path() with a dedicated reload-based regression test that guards the migrated-config logging_level behavior**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-06-09T04:54:14Z
- **Completed:** 2026-06-09T04:57:07Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Fixed TD-1: `_load_logging_level()` now lazily imports `config_path` from `core.paths` and opens `config_path()` instead of the stale repo-root `_CONFIG_PATH` constant
- Preserved the `_LOGGING_LEVEL = _load_logging_level()` cache-at-import invariant (unchanged)
- Added `tests/test_logger_config_path.py` with two tests: positive (level 2 honored) and negative (missing file falls back to 5)
- Full suite: 356 passed, 2 skipped (354 baseline + 2 new tests)

## Task Commits

1. **Task 1: Re-anchor logger logging_level read to core.paths.config_path()** - `d9846da` (fix)
2. **Task 2: Add TD-1 regression test for migrated-config logging_level** - `dee71e3` (test)

## Files Created/Modified

- `logger.py` - `_load_logging_level()` now uses `from core.paths import config_path` lazily; `_CONFIG_PATH` comment updated to note it is tooling-only
- `tests/test_logger_config_path.py` - two reload-based regression tests for TD-1

## Decisions Made

- Kept `_CONFIG_PATH` constant (Option A from RESEARCH) rather than deleting it, to preserve tooling inspection capability
- Test teardown via `finally` block with `monkeypatch.delenv` + `importlib.reload(logger)` to ensure `_LOGGING_LEVEL` is restored after each test and does not bleed into other test files

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- TD-1 closed; logger reads the migrated config correctly
- Regression test in place; a revert of the fix would cause `test_migrated_config_logging_level_honoured` to fail (it asserts level 2, which the old repo-root read cannot produce under a SHOPBOT_DATA_DIR override)
- Ready to proceed to Plan 12-02 (TD-2: SC1 guard rglob fix)

## Self-Check: PASSED

- `logger.py` modified: confirmed (contains `from core.paths import config_path`)
- `tests/test_logger_config_path.py` created: confirmed (2 tests)
- Task commit `d9846da` exists: confirmed
- Task commit `dee71e3` exists: confirmed
- Full suite 356 passed, 2 skipped: confirmed

---
*Phase: 12-stability-foundation*
*Completed: 2026-06-09*
