---
phase: 23-encrypted-session-persistence
plan: "01"
subsystem: core
tags: [session-store, fernet, encryption, cookies, rel-04]
dependency_graph:
  requires: [core/credentials.py (_derive_key, SALT_LEN, _resolve_passphrase), core/paths.py (data_dir)]
  provides: [core/session_store.py (SessionStore, build_session_store)]
  affects: []
tech_stack:
  added: []
  patterns: [Fernet AES-128-CBC+HMAC over JSON, scrypt KDF reuse, atomic tempfile+os.replace write]
key_files:
  created: [core/session_store.py, tests/test_session_store.py]
  modified: []
decisions:
  - "SessionStore mirrors EncryptedFileBackend._save/_load exactly: [salt][Fernet token] layout, tempfile+os.replace atomic write (Windows-safe)"
  - "restore() returns None (not raises ValueError) on InvalidToken/missing/corrupt -- silent login fallback is the REL-04 contract"
  - "_derive_key and SALT_LEN imported from core.credentials (single source of truth); scrypt params not redeclared"
  - "build_session_store() factory centralizes _resolve_passphrase() so callers never duplicate env-var resolution"
metrics:
  duration: "5 minutes"
  completed: "2026-06-12"
  tasks_completed: 2
  files_created: 2
  files_modified: 0
requirements: [REL-04]
---

# Phase 23 Plan 01: SessionStore Encrypted Cookie Persistence Summary

**One-liner:** Fernet-encrypted per-platform cookie persistence with scrypt KDF reuse, atomic write, and silent-None failure contract.

## What Was Built

`core/session_store.py` exposes `SessionStore` with `save(platform, cookies: list[dict])` and `restore(platform) -> list[dict] | None`. File layout: `data/sessions/<platform>.bin` = `[16-byte salt][Fernet token of JSON cookie list]`, mirroring `EncryptedFileBackend` from `core/credentials.py`.

Key behaviors:
- Encryption: Fernet with scrypt-derived key (`_derive_key` + `SALT_LEN` imported, not redeclared)
- Atomic write: `tempfile.mkstemp` + `os.fdopen` in `with` block + `os.replace` outside (Windows-safe, Pitfall 6 ordering)
- No-passphrase path: `save()` is no-op, `restore()` returns `None` immediately; no plaintext ever written
- Failure contract: `restore()` returns `None` on missing file, corrupt data, or `InvalidToken` (wrong passphrase); never raises
- Error logging: `exc.__class__.__name__` only; passphrase and cookie values never logged
- `build_session_store()` factory resolves `SHOPBOT_STORE_PASSPHRASE` from env via `_resolve_passphrase()`

`tests/test_session_store.py` covers all 6 REL-04 behaviors with plain sync pytest functions.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | SessionStore save/restore (Fernet-encrypted cookie list) | e148292 | core/session_store.py |
| 2 | SessionStore unit tests (round-trip, no-plaintext, restore-safety, disabled) | 27c4f38 | tests/test_session_store.py |

## Verification

- `pytest tests/test_session_store.py -x`: 6 passed
- Full suite: 643 passed, 10 skipped (0 new failures)
- `python -c "from core.session_store import SessionStore, build_session_store"`: import OK
- No `pickle` import in `core/session_store.py`
- `from core.credentials import SALT_LEN, _derive_key, _resolve_passphrase` at line 26 (not redeclared)
- `os.replace` present at line 66 (atomic write confirmed)

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None. SessionStore is fully implemented with no deferred functionality.

## Threat Flags

No new threat surface beyond what is documented in the plan's threat model. All T-23-0x mitigations implemented:
- T-23-01: File is Fernet-encrypted; `test_no_plaintext_file` asserts not JSON-parseable and no sentinel bytes
- T-23-02: `InvalidToken` caught; `test_restore_corrupt_data` confirms None return
- T-23-03: Wrong-passphrase -> None; `test_restore_wrong_passphrase` confirms no raise
- T-23-04: Log only `exc.__class__.__name__`; no passphrase or cookie value in log path

## Self-Check: PASSED

- FOUND: core/session_store.py
- FOUND: tests/test_session_store.py
- FOUND: commit e148292 (feat)
- FOUND: commit 27c4f38 (test)
- OK: no pickle import
- OK: _derive_key, SALT_LEN imported from core.credentials (line 26)
- OK: os.replace present (line 66)
