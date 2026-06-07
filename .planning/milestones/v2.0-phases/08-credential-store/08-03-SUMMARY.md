---
phase: 08-credential-store
plan: "03"
subsystem: credentials
tags: [credential-store, backend-selection, init-store, botservice-wiring, cred-05, cred-06, no-plaintext]
dependency_graph:
  requires:
    - core.credentials.CredentialStore (ABC) -- plan 08-01
    - core.credentials.EnvVarBackend -- plan 08-01
    - core.credentials.KeyringBackend -- plan 08-02
    - core.credentials.EncryptedFileBackend -- plan 08-02
    - core.credentials._has_real_keyring -- plan 08-02
    - core.credentials._DEFAULT_STORE_PATH -- plan 08-01
    - core.credentials.init_store (stub) -- plan 08-01
    - core.service.BotService.__init__ -- plan 07-01
  provides:
    - core.credentials._build_store (selection logic, precedence config>keyring>file>env)
    - core.credentials._resolve_passphrase (SHOPBOT_STORE_PASSPHRASE env reader)
    - core.credentials._log_backend (startup log: backend name only, never secret)
    - core.service.BotService: init_store wired in __init__
    - tests.test_no_plaintext (CRED-06 no-plaintext-on-disk guard suite)
  affects:
    - core/credentials.py (stubs filled, writeLog import added)
    - core/service.py (init_store call added to BotService.__init__)
    - tests/test_credentials.py (5 xfail stubs un-xfailed; 5 new tests added)
    - tests/test_no_plaintext.py (created)
tech_stack:
  added:
    - keyring==25.7.0 (installed in venv; was missing despite being pinned in requirements.txt)
    - cryptography==44.0.2 (installed in venv; was missing)
  patterns:
    - Backend precedence: explicit config override > real keyring > encrypted-file (with passphrase) > env-var
    - _resolve_passphrase: env-only read at init time; never calls getpass in auto-detect path (Pitfall 3)
    - _log_backend: writeLog backend label only -- never a secret value (T-08-09 mitigated)
    - getpass only when backend='file' explicitly and no env passphrase (init-time, never async)
    - init_store(self._cfg) placed in BotService.__init__ before any thread launch (thread-safety)
key_files:
  created:
    - tests/test_no_plaintext.py
  modified:
    - core/credentials.py
    - core/service.py
    - tests/test_credentials.py
decisions:
  - _resolve_passphrase returns None when env var absent (not empty string); used for auto-detect branching
  - getpass.getpass deferred to backend='file' explicit path only; auto-detect probing never blocks I/O (Pitfall 3)
  - _log_backend helper extracted for single-responsibility (DRY across 4 backend selection branches)
  - test_botservice_initializes_store asserts creds._store is not None (not just isinstance) -- distinguishes init_store call from lazy fallback
  - keyring and cryptography installed into venv during execution (were missing despite requirements.txt pinning)
metrics:
  duration: "12min"
  completed: "2026-06-04"
  tasks: 3
  files: 4
---

# Phase 08 Plan 03: Backend Auto-Selection + BotService Wiring Summary

Backend auto-selection implemented in `_build_store` (config>keyring>file>env precedence), startup logs active backend name only via `_log_backend`, `init_store(self._cfg)` wired into `BotService.__init__`, and CRED-06 no-plaintext-on-disk guard suite created; 251 tests pass, no regressions.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 (RED) | Failing tests for _build_store selection + backend-name log | 370bac6 | tests/test_credentials.py |
| 1 (GREEN) | _build_store selection logic + _log_backend + _resolve_passphrase | a44473d | core/credentials.py, tests/test_credentials.py |
| 2 | Wire init_store into BotService.__init__ | 9676b5c | core/service.py, tests/test_credentials.py |
| 3 | CRED-06 no-plaintext-on-disk guard | 32b7ed3 | tests/test_no_plaintext.py |

## Verification Results

- `python -m pytest tests/test_credentials.py -k "select or override or startup_log or backend" -q`: 13 passed
- `python -m pytest tests/test_credentials.py -k "botservice or initializes" tests/test_service.py -q`: 14 passed
- `python -m pytest tests/test_no_plaintext.py -q`: 4 passed
- `python -m pytest tests/test_credentials.py tests/test_no_plaintext.py tests/test_service.py -q`: 37 passed, 1 xfailed, 1 xpassed
- `python -m pytest -q` (full suite): 251 passed, 1 xfailed, 1 xpassed, 0 failures
- `grep -nE "writeLog\(.*(get\(|os\.environ|password|token|_value)" core/credentials.py`: 0 matches (no secret-value log lines)
- `core/credentials.py` contains `def _build_store` and `backend active` log line: confirmed
- `core/service.py` contains `init_store(self._cfg)` inside `BotService.__init__`: confirmed

## Acceptance Criteria Met

- [x] Precedence config>keyring>file>env implemented and tested
- [x] Active backend NAME logged on startup; never a secret value (T-08-09 mitigated)
- [x] BotService initializes the store before the daemon thread launches
- [x] No SECRET_KEYS value appears plaintext in config.yml, logs, or SQLite (CRED-06)
- [x] Existing 241-test suite expanded to 251 tests -- all green

## Deviations from Plan

**1. [Rule 3 - Blocking] keyring and cryptography not installed in venv**
- Found during: Task 1 RED (import error)
- Issue: requirements.txt pins keyring==25.7.0 and cryptography==44.0.2, but neither was installed in the active venv (plan 08-02 tests ran in a different context)
- Fix: `pip install keyring==25.7.0` then `pip install cryptography==44.0.2` inside the project venv
- Files modified: none (venv packages; requirements.txt already correct)
- Commit: N/A (install-only; no code changes)

**2. [Rule 1 - Bug] test_startup_log_backend_name had bad monkeypatch.getfixturevalue reference**
- Found during: Task 1 GREEN test run
- Issue: Un-xfailed test had `val = monkeypatch.getfixturevalue` (MonkeyPatch has no such attribute)
- Fix: Removed the bad line; loop now uses `os.environ.get(env_key, "")` directly
- Files modified: tests/test_credentials.py
- Commit: a44473d (folded into GREEN commit)

**3. [Rule 1 - Bug] test_botservice_initializes_store initial version was vacuously passing**
- Found during: Task 2 (test passed before wiring because lazy fallback also returns EnvVarBackend)
- Issue: Original test checked `isinstance(store, EnvVarBackend)` via get_store() lazy fallback; passed even before init_store was called
- Fix: Strengthened test to assert `creds._store is not None` before any isinstance check; ensures init_store was actually called
- Files modified: tests/test_credentials.py
- Commit: 9676b5c

## Threat Model Coverage

| Threat ID | Status | Evidence |
|-----------|--------|---------|
| T-08-09 | Mitigated | _log_backend emits label only; grep confirms 0 secret-value log lines |
| T-08-10 | Mitigated | tests/test_no_plaintext.py 4 tests pass; all three disk sinks checked |
| T-08-11 | Mitigated | _build_store auto path uses _has_real_keyring() before choosing keyring |
| T-08-12 | Mitigated | getpass only in explicit 'file' path, never in auto-detect; _resolve_passphrase is env-only |

## Known Stubs

None. The remaining xfail stub is `test_migrate_from_env` (plan 08-04 scope).

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes introduced. init_store now runs at BotService construction time -- earlier than before (was never called). This is the intended behavior (thread-safety). No new file access paths beyond `_DEFAULT_STORE_PATH` established in plan 08-01. No threat flags.

## Self-Check: PASSED

Files exist:
- core/credentials.py: FOUND (contains _build_store, _log_backend, _resolve_passphrase, writeLog import)
- core/service.py: FOUND (contains init_store(self._cfg) in BotService.__init__)
- tests/test_credentials.py: FOUND (un-xfailed tests + new tests)
- tests/test_no_plaintext.py: FOUND (created)

Commits exist:
- 370bac6: FOUND (RED -- failing tests)
- a44473d: FOUND (GREEN -- _build_store)
- 9676b5c: FOUND (BotService wiring)
- 32b7ed3: FOUND (test_no_plaintext.py)

All 251 tests pass. No regressions from 241-test baseline.
