---
phase: 08-credential-store
plan: "02"
subsystem: credentials
tags: [credential-store, keyring, encrypted-file, fernet, scrypt, cred-02, cred-03]
dependency_graph:
  requires:
    - core.credentials.CredentialStore (ABC) -- plan 08-01
    - core.credentials.SECRET_KEYS -- plan 08-01
    - core.credentials._DEFAULT_STORE_PATH -- plan 08-01
    - tests.conftest.isolated_keyring -- plan 08-01
  provides:
    - core.credentials.KeyringBackend
    - core.credentials._has_real_keyring
    - core.credentials.EncryptedFileBackend
    - core.credentials._derive_key
    - requirements.keyring==25.7.0
  affects:
    - core/credentials.py (KeyringBackend + EncryptedFileBackend + _derive_key added)
    - requirements.txt (keyring==25.7.0 pinned)
    - tests/test_credentials.py (6 xfail stubs un-xfailed and passing)
tech_stack:
  added:
    - keyring==25.7.0 (jaraco/keyring; OS secret service: Windows Credential Manager)
  patterns:
    - Fernet AES-128-CBC+HMAC over JSON dict (CRED-03 at-rest encryption)
    - scrypt KDF n=2**14/r=8/p=1 with fresh 16-byte salt per write (RFC 7914)
    - tempfile.mkstemp + fdopen-in-with + os.replace-outside (atomic write, Pitfall 6)
    - InvalidToken wrapped to user-facing ValueError naming SHOPBOT_STORE_PASSPHRASE (Pitfall 4)
    - _has_real_keyring() fail.Keyring/null.Keyring guard before backend selection (T-08-06)
    - SECRET_KEYS probe loop for KeyringBackend.list() (no enumerate API, Pitfall 5)
key_files:
  created: []
  modified:
    - core/credentials.py
    - requirements.txt
    - tests/test_credentials.py
decisions:
  - EncryptedFileBackend added in same commit as KeyringBackend (TDD RED was written first; GREEN covers both backends together since imports were consolidated)
  - os.unlink(tmp) in except block uses try/except OSError to avoid masking the original exception on Windows (belt-and-suspenders cleanup)
  - _NullKeyring import guarded with try/except ImportError inside _has_real_keyring() per RESEARCH Pattern 2 (null backend may not be present in all keyring versions)
  - Task 3 tests un-xfailed directly to green (EncryptedFileBackend was written in the Task 2 GREEN commit along with the scrypt/Fernet imports, which are prerequisites for both backends)
metrics:
  duration: "7min"
  completed: "2026-06-04"
  tasks: 2
  files: 3
---

# Phase 08 Plan 02: KeyringBackend + EncryptedFileBackend Summary

KeyringBackend (OS secret service via keyring==25.7.0) and EncryptedFileBackend (Fernet AES-128-CBC+HMAC, scrypt KDF, atomic write) implemented with full TDD coverage; keyring pinned in requirements.txt; 6 previously-xfailed CRED-02/CRED-03 tests now pass, full suite at 241 passed with no regressions.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 2 (RED) | Failing tests for KeyringBackend + _has_real_keyring | a3662a8 | tests/test_credentials.py |
| 2 (GREEN) | KeyringBackend + _has_real_keyring + keyring==25.7.0 | 8b26182 | core/credentials.py, requirements.txt |
| 3 (GREEN) | EncryptedFileBackend tests un-xfailed + passing | d9bdc04 | tests/test_credentials.py |

Note: Task 1 (keyring legitimacy checkpoint) was pre-cleared by the user before execution. Task 3 EncryptedFileBackend implementation landed in the Task 2 GREEN commit because scrypt/Fernet imports were consolidated; Task 3 commit un-xfails and verifies the tests.

## Verification Results

- `python -m pytest tests/test_credentials.py -k "keyring" -q`: 3 passed
- `python -m pytest tests/test_credentials.py -k "file or plaintext" -q`: 3 passed
- `python -m pytest tests/test_credentials.py -q`: 14 passed, 3 xfailed, 2 xpassed
- `python -m pytest -q` (full suite): 241 passed, 3 xfailed, 2 xpassed, 0 failures
- requirements.txt contains `keyring==25.7.0`: confirmed
- core/credentials.py contains `class KeyringBackend`, `def _has_real_keyring`, `class EncryptedFileBackend`, `def _derive_key`, `Scrypt(`, `os.replace(`, `tempfile.mkstemp`, `InvalidToken`: all confirmed
- No secret-value log lines in credentials.py: grep confirmed 0 matches

## Acceptance Criteria Met

- [x] requirements.txt contains `keyring==25.7.0`
- [x] core/credentials.py contains `class KeyringBackend` and `def _has_real_keyring`
- [x] `python -m pytest tests/test_credentials.py -k keyring -q` exits 0
- [x] No secret logged (grep returns nothing)
- [x] core/credentials.py contains `class EncryptedFileBackend`, `def _derive_key`, `Scrypt(`
- [x] core/credentials.py contains `os.replace(`, `tempfile.mkstemp`, `InvalidToken`
- [x] `python -m pytest tests/test_credentials.py -k "file or plaintext" -q` exits 0
- [x] test_encrypted_file_is_not_plaintext passes (raw bytes contain no plaintext secret)
- [x] test_file_backend_wrong_passphrase asserts ValueError message contains "SHOPBOT_STORE_PASSPHRASE"

## Deviations from Plan

**1. [Rule 2 - Missing critical functionality] Added os.unlink cleanup guard in EncryptedFileBackend._save**
- Found during: Task 3 implementation
- Issue: If os.unlink(tmp) itself fails (e.g. Windows PermissionError on the tmp file) after an exception during write, it would mask the original exception.
- Fix: Wrapped os.unlink(tmp) in its own try/except OSError so the original exception propagates cleanly.
- Files modified: core/credentials.py
- Commit: 8b26182

**2. [Structural note] EncryptedFileBackend implemented in Task 2 GREEN commit**
- The scrypt/Fernet/base64/json/tempfile imports were consolidated into one module-level import block in the Task 2 GREEN commit. Since EncryptedFileBackend depends on the same imports, it was implemented in the same commit. Task 3's commit is the TDD verification step (un-xfail tests confirm the implementation). This is within plan scope; no code functionality was deferred or skipped.

## Threat Model Coverage

| Threat ID | Status | Evidence |
|-----------|--------|---------|
| T-08-04 | Mitigated | test_encrypted_file_is_not_plaintext passes: raw bytes contain no plaintext |
| T-08-05 | Mitigated | scrypt n=2**14 in SCRYPT_N constant; documented in module docstring |
| T-08-06 | Mitigated | _has_real_keyring() returns False for fail.Keyring; test_has_real_keyring_fail passes |
| T-08-07 | Mitigated | tempfile.mkstemp + fdopen inside with + os.replace outside with; os.unlink on failure |
| T-08-08 | Mitigated | InvalidToken caught and re-raised as ValueError("...SHOPBOT_STORE_PASSPHRASE"); test_file_backend_wrong_passphrase asserts exact message |
| T-08-SC | Mitigated | keyring legitimacy pre-cleared by human approval; pinned to exact ==25.7.0 |

## Known Stubs

None. KeyringBackend and EncryptedFileBackend are fully implemented. The remaining xfail tests are for plan 08-03 (init_store auto-selection) and plan 08-04 (migrate_from_env).

## Threat Surface Scan

No new network endpoints or auth paths introduced. KeyringBackend hands secrets to Windows Credential Manager (OS trust boundary, documented in threat model T-08-SC). EncryptedFileBackend writes only to a user-specified tmp_path in tests; no new file access paths in production code beyond `_DEFAULT_STORE_PATH` (already established in plan 08-01). No threat flags beyond those already in the plan's threat register.

## Self-Check: PASSED

Files exist:
- core/credentials.py: FOUND (KeyringBackend + EncryptedFileBackend + _derive_key + _has_real_keyring)
- requirements.txt: FOUND (keyring==25.7.0 pinned)
- tests/test_credentials.py: FOUND (6 tests un-xfailed and passing)

Commits exist:
- a3662a8: FOUND (test RED)
- 8b26182: FOUND (feat GREEN -- KeyringBackend + imports)
- d9bdc04: FOUND (feat GREEN -- EncryptedFileBackend tests)

All 241 tests pass. No regressions from 235-test baseline.
