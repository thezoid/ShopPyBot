---
phase: 08-credential-store
plan: "01"
subsystem: credentials
tags: [credential-store, abc, env-var-backend, config-schema, test-scaffold]
dependency_graph:
  requires: []
  provides:
    - core.credentials.CredentialStore (ABC)
    - core.credentials.EnvVarBackend
    - core.credentials.SECRET_KEYS (19 keys)
    - core.credentials.get_store
    - core.credentials.init_store
    - core.config_schema.CredentialsConfig
    - tests.conftest.reset_credential_store
    - tests.conftest.isolated_keyring
  affects:
    - core/config_schema.py (AppConfig gains credentials field)
    - tests/conftest.py (two new fixtures)
tech_stack:
  added: []
  patterns:
    - ABC with abstractmethod for pluggable backends
    - Module-level singleton with threading.Lock (thread-safe lazy init)
    - TYPE_CHECKING guard to avoid circular import (credentials <-> config_schema)
    - xfail stubs with named functions for downstream plan un-xfailing
    - keyring import guard (try/except) for pre-install conftest compatibility
key_files:
  created:
    - core/credentials.py
    - tests/test_credentials.py
  modified:
    - core/config_schema.py
    - tests/conftest.py
decisions:
  - _DEFAULT_STORE_PATH uses Path(__file__).parent.parent/data/creds.bin to match project data/ convention (consistent with data/shop_py_bot.db)
  - get_store() lazy-falls-back to EnvVarBackend (not raise) so monkeypatch.setenv tests need no modification
  - _build_store stub returns EnvVarBackend; selection logic (auto-detect keyring->file->env) deferred to plan 08-03
  - isolated_keyring fixture skips (not fails) when keyring not installed so CI stays green through plan 08-01
  - SmsConfig.require_creds_if_enabled: DELIBERATE os.environ exception documented in code (RESEARCH Pitfall 7)
metrics:
  duration: "8min"
  completed: "2026-06-04"
  tasks: 3
  files: 4
---

# Phase 08 Plan 01: Credential Store Contract Summary

CredentialStore ABC, EnvVarBackend (identity-preserving fallback over os.environ), 19-key SECRET_KEYS list, and get_store/init_store module accessors established; CredentialsConfig wired into AppConfig; Wave 0 test scaffold with 8 real CRED-01/CRED-04 tests passing and 6 xfail stubs for plans 08-02/03/04.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 (RED) | Wave 0 test scaffold + conftest fixtures | 77c4573 | tests/test_credentials.py, tests/conftest.py |
| 2 (GREEN) | CredentialStore ABC + EnvVarBackend + SECRET_KEYS + accessors | 0e2f482 | core/credentials.py |
| 3 (GREEN) | CredentialsConfig sub-model wired into AppConfig | dddb2e5 | core/config_schema.py |

## Verification Results

- `python -m pytest tests/test_credentials.py tests/test_config_schema.py -q`: 22 passed, 2 skipped, 6 xfailed, 2 xpassed
- `python -m pytest -q` (full suite): 235 passed, 2 skipped, 6 xfailed, 2 xpassed, 0 failures
- `python -c "from core.credentials import CredentialStore, EnvVarBackend, SECRET_KEYS, get_store, init_store"`: exits 0
- `len(SECRET_KEYS) == 19` and both boundary keys confirmed
- `AppConfig().credentials.backend == "auto"`: confirmed
- No secret-value log lines in credentials.py (grep confirmed 0 matches)

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

`core/credentials._build_store()`: always returns EnvVarBackend in plan 08-01. Auto-detection logic (keyring -> encrypted-file -> env-var precedence) is implemented in plan 08-03. This is an intentional, documented stub -- the symbol exists for plan 03 to flesh out.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries introduced in this plan. CredentialsConfig holds no secret fields (backend selector + data_dir only). EnvVarBackend reads os.environ -- same trust boundary as before. No threat flags.

## Self-Check: PASSED

Files exist:
- core/credentials.py: FOUND
- tests/test_credentials.py: FOUND
- core/config_schema.py: modified (CredentialsConfig added)
- tests/conftest.py: modified (fixtures added)

Commits exist:
- 77c4573: FOUND (test scaffold)
- 0e2f482: FOUND (credentials.py)
- dddb2e5: FOUND (CredentialsConfig)

All 235 tests pass. No regressions.
