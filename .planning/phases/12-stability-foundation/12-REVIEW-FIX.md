---
phase: 12-stability-foundation
fixed_at: 2026-06-09T00:00:00Z
review_path: .planning/phases/12-stability-foundation/12-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 12: Code Review Fix Report

**Fixed at:** 2026-06-09
**Source review:** .planning/phases/12-stability-foundation/12-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 3 (WR-01, WR-02, WR-03) + 1 Info (IN-01, applied)
- Fixed: 4
- Skipped: 0

## Fixed Issues

### WR-01: Dead exported variable `_CONFIG_PATH` removed

**Files modified:** `logger.py`
**Commit:** 47261a0
**Applied fix:** Removed the three-line `_CONFIG_PATH` declaration block (comment + constant) from logger.py lines 8-10. Grep confirmed no production code or tests import it.

### WR-02: Platform toggle assertion OR-to-AND correction

**Files modified:** `tests/test_web_dashboard.py`
**Commit:** cdddb95
**Applied fix:** Changed `or` to `and` in the platform-name loop assertion at line 132, and added an error message string. The test now correctly fails if any platform name appears in either `name=` or `data-key=` form in the SSR HTML.

### WR-03: Fallback candidate path added to `_load_logging_level`

**Files modified:** `logger.py`
**Commit:** ecd8ede
**Applied fix:** Replaced the single-path open in `_load_logging_level()` with a two-candidate loop: (1) the migrated AppData `config_path()`, (2) the legacy repo-root `config.yml`. On first boot before `migrate_legacy_paths()` runs, the migrated path does not exist yet; the fallback preserves the user's configured log level for that session. Change is contained to the single function with no behavior change once migration is complete.

### IN-01: Separator guard scan extended to `web/` directory

**Files modified:** `tests/test_paths.py`
**Commit:** a4a331e
**Applied fix:** Added `list((repo_root / "web").rglob("*.py"))` to the `src_files` collection in `test_no_hardcoded_separators`. Any future file added under `web/` is now covered by the guard.

## Skipped Issues

None.

## Test Results

`pytest`: 359 passed, 2 skipped (identical to pre-fix baseline). WR-02 test continues to pass against the real HTML, confirming no platform toggles are present in the SSR output.

---

_Fixed: 2026-06-09_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
