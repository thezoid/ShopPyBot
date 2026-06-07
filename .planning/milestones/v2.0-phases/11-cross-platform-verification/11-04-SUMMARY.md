---
phase: 11
plan: "04"
subsystem: tests
tags: [smoke, backend-selection, xplat-02, env-independent, credentials]
dependency_graph:
  requires: [11-01, 11-02, 11-03]
  provides: [tests/test_smoke.py, tests/test_backend_selection.py]
  affects: [ci-matrix-plan-05]
tech_stack:
  added: []
  patterns: [subprocess-smoke, mock-patch-return_value, reset_credential_store-fixture]
key_files:
  created:
    - tests/test_smoke.py
    - tests/test_backend_selection.py
  modified: []
decisions:
  - "items list smoke pre-initializes DB via initialize_db() before main() call -- mirrors real usage; BotService.__init__ does not call initialize_db() (that is main.py's job)"
  - "config show smoke writes a minimal config.yml to tmp_path and pre-initializes DB so BotService() completes without a missing-table error"
  - "subprocess inline -c scripts set SHOPBOT_DATA_DIR via os.environ before any import to ensure core.paths.data_dir() resolves to the temp dir at import time"
  - "PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring short-circuits _has_real_keyring() to False; SHOPBOT_STORE_PASSPHRASE=x selects EncryptedFileBackend (no interactive prompt)"
  - "SDL_AUDIODRIVER=dummy prevents pygame.mixer.init() failure on headless CI"
  - "run subcommand never invoked except via --help per RESEARCH Pitfall 7"
metrics:
  duration: "8m"
  completed: "2026-06-05T03:24:48Z"
  tasks_completed: 2
  files_modified: 2
---

# Phase 11 Plan 04: Env-Independent Smoke + Backend-Selection Tests Summary

One-liner: env-independent pytest smoke proves import and safe CLI commands exit 0, and backend-selection tests prove _build_store auto-picks keyring/file/env via a mocked `_has_real_keyring()` -- the automated half of the XPLAT-02 verification matrix.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | tests/test_backend_selection.py -- mocked _has_real_keyring drives selection | e97c8e4 | tests/test_backend_selection.py |
| 2 | tests/test_smoke.py -- env-independent import + CLI smoke | d9e2675 | tests/test_smoke.py |

## What Was Built

`tests/test_backend_selection.py` (3 tests): proves backend auto-selection logic via `unittest.mock.patch("core.credentials._has_real_keyring", return_value=...)`.
- `test_auto_selects_keyring_when_available`: patch True -> `KeyringBackend` selected
- `test_auto_selects_file_when_no_keyring`: patch False + `SHOPBOT_STORE_PASSPHRASE` set -> `EncryptedFileBackend` selected
- `test_auto_falls_back_to_env`: patch False + no passphrase -> `EnvVarBackend` selected
All three use `reset_credential_store` + `tmp_config_yml` fixtures for singleton isolation.

`tests/test_smoke.py` (4 tests): env-independent import and CLI smoke.
- `test_import_smoke`: verifies `core.service`, `core.paths`, `models`, `logger` import without exception
- `test_help_smoke`: subprocess `python -m core.service --help` exits 0
- `test_items_list_smoke`: subprocess `main(['items', 'list'])` exits 0 with DB pre-initialized in temp dir
- `test_config_show_smoke`: subprocess `main(['config', 'show'])` exits 0 with minimal config.yml in temp dir

All subprocess invocations use: `SHOPBOT_DATA_DIR=<tmp>`, `SHOPBOT_STORE_PASSPHRASE=x`, `PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring`, `SDL_AUDIODRIVER=dummy`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] items list requires initialize_db() before first query**
- **Found during:** Task 2 smoke test verification
- **Issue:** `items list` calls `svc.list_items()` -> `get_items_sync()` which queries the `items` table. On a fresh temp dir the DB file does not exist and `sqlite3.OperationalError: no such table: items` is raised. `BotService.__init__` only calls `init_store()` (credential store), not `initialize_db()` -- that is `main.py`'s responsibility.
- **Fix:** The subprocess smoke pre-calls `models.initialize_db()` before `main(['items', 'list'])`. Same for `config show`. This mirrors real usage (main.py always calls `initialize_db()` before `BotService.run()`). The smoke still proves the CLI dispatch and DB query path execute without error.
- **Files modified:** tests/test_smoke.py (initial write; no separate commit needed)
- **Commit:** d9e2675

## Test Results

- `test_backend_selection.py`: 3/3 passed
- `test_smoke.py`: 4/4 passed
- Full suite after Task 2: 352 passed, 2 skipped (354 total collected), 0 failures

## Known Stubs

None. Both test files are fully functional and assert correct behavior.

## Threat Flags

None. No new network endpoints, auth paths, or trust boundaries introduced. The subprocess smoke captures output but never asserts on secret values (T-11-10 mitigated). The `run` subcommand is never invoked without `--help` (T-11-11 mitigated).

## Self-Check: PASSED
