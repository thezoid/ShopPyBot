---
phase: 11-cross-platform-verification
plan: "02"
subsystem: core/paths
tags: [paths, platformdirs, cross-platform, xplat-01, models, logger, credentials, config-schema]
dependency_graph:
  requires:
    - phase: 11-01
      provides: core/paths.py with data_dir/config_path/log_dir and SHOPBOT_DATA_DIR env-override seam
  provides:
    - models.DB_PATH anchored to data_dir() under OS-standard user dir (CWD-relative bug fixed)
    - core/credentials._DEFAULT_STORE_PATH anchored to data_dir() / "creds.bin"
    - core/config_schema._DEFAULT_YAML_PATH anchored to config_path()
    - logger.py log dir resolved via lazy core.paths.log_dir inside writeLog (no circular import)
    - tests/conftest.tmp_data_dir extended with SHOPBOT_DATA_DIR setenv
  affects: [core/paths, core/service, tests/conftest]
tech-stack:
  added: []
  patterns:
    - lazy-import inside function body to break circular dependency (logger.py -> core.paths)
    - dual monkeypatch seam: raw attribute + env override both redirected in tmp_data_dir fixture
key-files:
  created: []
  modified:
    - models.py
    - core/config_schema.py
    - core/credentials.py
    - logger.py
    - tests/conftest.py
key-decisions:
  - "logger.py imports core.paths.log_dir lazily inside writeLog writeTofile branch only; no module-top import; avoids circular import because Plan 03 core/paths.py will import writeLog from logger"
  - "models.DB_PATH uses str(_paths_data_dir() / 'shop_py_bot.db') to preserve existing str-type contract with sqlite3.connect and monkeypatch seam"
  - "tmp_data_dir fixture sets SHOPBOT_DATA_DIR before monkeypatching models.DB_PATH so both seams agree on the same temp dir"
  - "logger.py _CONFIG_PATH (line 10) left unchanged per plan scope lock: it reads config.yml repo-relative for logging level; degrades gracefully to level 5 on miss; not part of XPLAT-01 anchor scope"
patterns-established:
  - "lazy import inside function body for circular-dependency break"
  - "dual-seam fixture: setenv + setattr in tandem for consistent path redirection"
requirements-completed: [XPLAT-01]
duration: 8min
completed: "2026-06-05"
---

# Phase 11 Plan 02: Consumer Re-anchor through core/paths.py Summary

**Four legacy path anchors (models DB, creds.bin, config.yml, log dir) re-routed through core/paths.py; CWD-relative DB bug fixed; logger lazy-imports log_dir inside writeLog to avoid circular import; full 341-test suite stays green.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-06-04T23:00:00Z
- **Completed:** 2026-06-04T23:08:00Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- `models.DB_PATH` now resolves to `C:\Users\<user>\AppData\Local\shoppybot\shop_py_bot.db` (or OS equivalent) regardless of launch directory; the CWD-relative `os.path.join('data', ...)` bug is eliminated.
- `core/credentials._DEFAULT_STORE_PATH` and `core/config_schema._DEFAULT_YAML_PATH` both route through `core/paths.py`; the `cfg.credentials.data_dir` config override is preserved untouched.
- `logger.py` resolves the log directory via a lazy `from core.paths import log_dir` import inside `writeLog`'s `writeTofile` branch, breaking the anticipated circular import that Plan 03 would create when `core/paths.py` imports `writeLog`.
- `tests/conftest.tmp_data_dir` now sets `SHOPBOT_DATA_DIR` env var alongside the existing `models.DB_PATH` setattr, keeping both path seams consistent for the 341-test suite.

## Task Commits

1. **Task 1: Re-anchor models.py DB_PATH and config_schema/credentials defaults** - `49b2e67` (feat)
2. **Task 2: Re-anchor logger.py log dir via lazy core.paths import inside writeLog** - `fd5f48c` (feat)
3. **Task 3: Extend tmp_data_dir fixture and run full suite to confirm 341 stay green** - `29b2074` (test)

## Files Created/Modified

- `models.py` - DB_PATH re-anchored to `_paths_data_dir() / "shop_py_bot.db"` (absolute, not CWD-relative)
- `core/config_schema.py` - `_DEFAULT_YAML_PATH` re-anchored to `_paths_config_path()`
- `core/credentials.py` - `_DEFAULT_STORE_PATH` re-anchored to `_paths_data_dir() / "creds.bin"`
- `logger.py` - writeTofile branch replaces `_scriptdir`/`os.path.join` with lazy `core.paths.log_dir` + pathlib
- `tests/conftest.py` - `tmp_data_dir` extended with `monkeypatch.setenv("SHOPBOT_DATA_DIR", str(tmp_path))`

## Decisions Made

- Logger lazy import is the correct seam: `core/paths.py` (Plan 03) will import `writeLog` from `logger.py` for migration logging. Any module-top `from core.paths import ...` in `logger.py` would create a circular import at import time. Lazy import inside the function body resolves this cleanly.
- `logger.py _CONFIG_PATH` (line 10 repo-relative config read for logging level) is left unchanged. This is outside XPLAT-01 scope: it degrades gracefully to level 5 when config.yml is absent, and changing it would require a separate seam. Tracked as a follow-up for Plan 03/04 if needed.
- `models.DB_PATH` is kept as `str(...)` not `Path(...)` to preserve the existing type contract: `sqlite3.connect(DB_PATH)` and `monkeypatch.setattr(models, "DB_PATH", str(...))` both expect a string.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `rtk pytest` uses a different Python binary that lacks `keyring` in its path, causing false failures. All verification used `python -m pytest` directly, which passes cleanly. Pre-existing environment issue unrelated to this plan's changes.

## Observed Follow-up (not a blocker)

`logger.py:10` reads `_CONFIG_PATH = Path(__file__).parent / "config.yml"` (repo-root relative) for the debug logging level. This is intentionally out of scope for Plan 02 (the plan's locked scope covers only the four anchors). It degrades gracefully to level 5 on miss. Plan 03 or a subsequent plan can re-anchor this if needed.

## Next Phase Readiness

- All four consumers route through `core/paths.py`; Plan 03 (`migrate_legacy_paths`) can now safely import `writeLog` from `logger.py` without circular import risk.
- The `SHOPBOT_DATA_DIR` env override seam is active in both `models.DB_PATH` (via conftest) and all `core/paths` functions, enabling clean CI and test isolation.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes introduced.
T-11-03 (creds.bin relocation): `_DEFAULT_STORE_PATH` now points at OS-standard user dir; no file is moved in this plan (Plan 03 migrates). creds.bin remains Fernet-encrypted.
T-11-04 (circular import): lazy import inside `writeLog` verified by `import logger; logger.writeLog(...)` smoke -- no ImportError.
T-11-05 (hardcoded separator regression): `test_no_hardcoded_separators` passes; all re-anchors use pathlib `/` operator only.

## Self-Check: PASSED
