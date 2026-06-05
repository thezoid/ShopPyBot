---
phase: 11-cross-platform-verification
plan: "03"
subsystem: core/paths + core/service
tags: [paths, migration, idempotent, xplat-01, creds-verbatim, no-secret-log]
dependency_graph:
  requires:
    - phase: 11-01
      provides: core/paths.py with data_dir/config_path/log_dir accessors
    - phase: 11-02
      provides: lazy writeLog seam in logger.py preventing circular import
  provides:
    - migrate_legacy_paths() in core/paths.py
    - _REPO_ROOT_OVERRIDE + _repo_root() test seam
    - core/service.py:main() calls migrate_legacy_paths() before BotService/AppConfig
    - tests/test_migration.py covering move, idempotency, verbatim creds, no-secret-log
  affects: [core/paths.py, core/service.py, tests/test_migration.py]
tech-stack:
  added: []
  patterns:
    - copy2-before-unlink idempotent migration guard (src.exists() and not dst.exists())
    - lazy import inside function body for circular-import avoidance (writeLog)
    - _REPO_ROOT_OVERRIDE module-level sentinel for test seam
key-files:
  created:
    - tests/test_migration.py
  modified:
    - core/paths.py
    - core/service.py
key-decisions:
  - "migrate_legacy_paths() lives in core/paths.py; called explicitly from core/service.py:main() before build_parser()"
  - "_REPO_ROOT_OVERRIDE: Path | None = None module-level sentinel monkeypatched in tests; _repo_root() reads it"
  - "lazy 'from logger import writeLog' inside function body preserves Plan 02 circular-import seam"
  - "_migrate_logs() split into separate helper to keep migrate_legacy_paths() under 30 lines (CLAUDE.md)"
  - "copy2 THEN unlink: if copy fails src is untouched; not dst.exists() guard makes second run no-op"
  - "creds.bin copied verbatim via shutil.copy2; never read, never logged; byte-identity verified in test"
metrics:
  duration: "7m"
  completed: "2026-06-05T03:13:04Z"
  tasks_completed: 3
  files_modified: 3
---

# Phase 11 Plan 03: Idempotent First-Run Migration + service.py Wiring Summary

One-liner: `migrate_legacy_paths()` in core/paths.py moves legacy `data/shop_py_bot.db`, `data/creds.bin`, `config.yml`, `logs/` to OS-standard locations once via copy2+unlink with idempotency guard; wired into `core/service.py:main()` before any config/DB/store access; creds.bin copied verbatim (Fernet-encrypted bytes); migration logs paths only, never secret values.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write tests/test_migration.py (RED) | c1049b7 | tests/test_migration.py |
| 2 | Implement migrate_legacy_paths() in core/paths.py (GREEN) | 806de6c | core/paths.py |
| 3 | Call migrate_legacy_paths() at top of core/service.py:main() | d4eef9b | core/service.py |

## What Was Built

`migrate_legacy_paths()` in `core/paths.py`:
- Builds `(src, dst)` pairs for `data/shop_py_bot.db`, `data/creds.bin`, `config.yml`
- For each: guard `src.exists() and not dst.exists()` ensures idempotency and no-overwrite
- `shutil.copy2(src, dst)` THEN `src.unlink()`: if copy fails, src is intact
- `_migrate_logs()` helper handles `logs/` dir via `shutil.copytree` + `shutil.rmtree`
- `from logger import writeLog` inside function body: lazy import preserves Plan 02's circular-import seam
- Logs `f"Migrated {src} -> {dst}"` only; never reads or logs `creds.bin` content

`_REPO_ROOT_OVERRIDE: Path | None = None` + `_repo_root()` in `core/paths.py`:
- Module-level sentinel monkeypatched in tests via `monkeypatch.setattr(core.paths, "_REPO_ROOT_OVERRIDE", tmp_path)`
- `_repo_root()` returns the override when set, else `Path(__file__).parent.parent`

`core/service.py:main()`:
- `from core.paths import migrate_legacy_paths` added to local imports
- `migrate_legacy_paths()` called immediately after imports, before `build_parser()` and any `BotService()` construction
- Guarantees new OS-standard paths are populated before `AppConfig` reads `_DEFAULT_YAML_PATH` (Pitfall 8)

`tests/test_migration.py`:
- `test_migration_moves_db`: legacy DB copied to `data_dir()` and src unlinked
- `test_migration_moves_creds_verbatim`: byte-identity check on `creds.bin` copy
- `test_migration_idempotent`: second call is a no-op; no exception raised
- `test_migration_skips_when_dst_exists`: dst unchanged, src not unlinked when dst pre-exists
- `test_migration_logs_paths_not_secrets`: monkeypatches `logger.writeLog`; asserts no creds bytes in any log message

## Test Results

- `test_migration.py`: 5/5 passed (GREEN after Task 2)
- `test_paths.py`: 6/6 passed (no regression)
- `test_service.py`: 13/13 passed (no regression)
- Full suite: **345 passed, 2 skipped** (341 baseline + 5 new migration tests; no failures)

## Deviations from Plan

None - plan executed exactly as written.

## Threat Mitigations Verified

| Threat ID | Status | Evidence |
|-----------|--------|----------|
| T-11-06 | Mitigated | creds.bin copied verbatim via copy2; test_migration_moves_creds_verbatim asserts byte-identity |
| T-11-07 | Mitigated | writeLog receives only f"Migrated {src} -> {dst}"; test_migration_logs_paths_not_secrets passes |
| T-11-08 | Mitigated | copy2-before-unlink + not dst.exists() guard; test_migration_idempotent + test_migration_skips_when_dst_exists pass |
| T-11-09 | Accepted | Paths from platformdirs (trusted) or user-controlled env var; pathlib normalizes; no untrusted network input |

## Known Stubs

None. Migration is fully functional.

## Threat Flags

None. No new network endpoints, auth paths, or schema changes introduced. Migration copies to `%LOCALAPPDATA%\shoppybot` (Windows) / `~/.local/share/shoppybot` (Linux), which are user-owned directories strictly more protected than the repo-relative `data/` directory (T-11-06 mitigated).

## Self-Check: PASSED
