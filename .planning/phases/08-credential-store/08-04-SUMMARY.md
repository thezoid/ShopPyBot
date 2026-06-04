---
phase: 08-credential-store
plan: 04
subsystem: credentials
tags: [migration, security, credentials, cred-01, cred-07]
dependency_graph:
  requires: [08-01, 08-02, 08-03]
  provides: [CRED-01-complete, CRED-07]
  affects: [plugins, notifications, core/service]
tech_stack:
  added: []
  patterns:
    - "get_store().get(KEY) replacing all os.environ secret reads in consumers"
    - "migrate_from_env(store) -> list[str] key names only (T-08-14)"
    - "SC1 grep guard test scanning plugins/notifications/core for regressions"
key_files:
  created:
    - tests/test_no_env_secret_reads.py
  modified:
    - plugins/shopbot_plugin_amazon.py
    - plugins/shopbot_plugin_bestbuy.py
    - plugins/shopbot_plugin_walmart.py
    - plugins/shopbot_plugin_target.py
    - plugins/shopbot_plugin_gamestop.py
    - plugins/shopbot_plugin_squareenix.py
    - plugins/shopbot_plugin_newegg.py
    - notifications/discord_notifier.py
    - notifications/email_notifier.py
    - notifications/sms_notifier.py
    - notifications/__init__.py
    - core/credentials.py
    - core/service.py
    - tests/test_credentials.py
decisions:
  - "migrate_from_env placed in core/credentials.py alongside SECRET_KEYS and get_store (single responsibility)"
  - "DiscordNotifier: os.environ[key] KeyError replaced with ValueError on falsy get_store().get() (T-08-15)"
  - "--migrate exits via early return before BotService() construction (no bot startup on migrate path)"
  - "SC1 test exempts core/credentials.py entirely; config_schema.py TWILIO_* only (startup presence gate)"
metrics:
  duration: "~15min"
  completed: "2026-06-04"
  tasks_completed: 3
  files_modified: 14
---

# Phase 08 Plan 04: Consumer Migration + migrate_from_env + SC1 Guard Summary

All 16 `os.environ` secret reads across 7 plugins and 4 notification files replaced with `get_store().get(KEY)`; `migrate_from_env` and `--migrate` CLI flag implemented with key-name-only output; SC1 grep guard test added to prevent future regressions.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Migrate 7 plugins + 4 notification sites | 55ef3bc | 11 consumer files |
| 2 (RED) | Failing tests for migrate_from_env + --migrate | 3a2ccd0 | tests/test_credentials.py |
| 2 (GREEN) | Implement migrate_from_env + --migrate flag | fb46d15 | core/credentials.py, core/service.py |
| 3 | SC1 grep guard test | f72165d | tests/test_no_env_secret_reads.py |

## What Was Built

### Task 1: 16 migration sites across 11 consumer files

All 7 plugin `login()` methods now use:
```python
store = get_store()
email = store.get("X_EMAIL") or ""
password = store.get("X_PASSWORD") or ""
```

`notifications/discord_notifier.py`: `os.environ["DISCORD_WEBHOOK_URL"]` (bare key, raised `KeyError`) replaced with:
```python
url = get_store().get("DISCORD_WEBHOOK_URL")
if not url:
    raise ValueError("DISCORD_WEBHOOK_URL not configured")
self._webhook_url = url
```

`email_notifier.py`, `sms_notifier.py`, `notifications/__init__.py`: equivalent one-line swaps.

`import os` removed from all 11 files where it was the sole usage.

### Task 2: migrate_from_env + --migrate

`core/credentials.py` now exports:
```python
def migrate_from_env(store: CredentialStore) -> list[str]
```
Iterates `SECRET_KEYS`, reads `os.environ.get(key)`, calls `store.set(key, val)` for each truthy value, returns key names only (T-08-14: values never printed or returned).

`core/service.py main()` extended:
- `--migrate` argument added via argparse
- When `args.migrate`: calls `migrate_from_env(get_store())`, prints `Migrated: {key}` for each, returns before `BotService()` construction

### Task 3: SC1 grep guard

`tests/test_no_env_secret_reads.py::test_no_os_environ_secret_reads` scans all `.py` files under `plugins/`, `notifications/`, `core/`. For each non-comment line, asserts no `os.environ.get("KEY")` or `os.environ["KEY"]` pattern appears for any `SECRET_KEYS` name. Two documented exceptions:
- `core/credentials.py` - entirely exempted (canonical backend)
- `core/config_schema.py` - TWILIO_* only (SmsConfig startup presence gate, deliberate exception per RESEARCH Pitfall 7)

## Test Results

Full suite: **255 passed, 1 xpassed** (up from 227 baseline; xpassed is `test_no_plaintext_secrets_in_config_yml` which skips when `config.yml` absent -- vacuously passes).

New tests added: 4 (3 migrate tests + 1 SC1 guard).

## Deviations from Plan

None - plan executed exactly as written.

## Threat Mitigations Applied

| Threat | Mitigation | Status |
|--------|-----------|--------|
| T-08-13: missed consumer bypasses store | SC1 grep guard (test_no_env_secret_reads.py) | Closed |
| T-08-14: --migrate prints secret values | migrate_from_env returns NAMES only; test_main_migrate_flag asserts | Closed |
| T-08-15: DiscordNotifier KeyError on missing webhook | get_store().get() returns None; explicit ValueError guard | Closed |
| T-08-16: migrate_from_env logs secret value | only store.set + append key name; no print/log of val | Closed |

## Known Stubs

None.

## Threat Flags

None -- no new network endpoints, auth paths, file access patterns, or schema changes introduced.

## Self-Check: PASSED

- tests/test_no_env_secret_reads.py: EXISTS
- core/credentials.py contains "def migrate_from_env": CONFIRMED
- core/service.py contains "--migrate" and "migrate_from_env": CONFIRMED
- Commits 55ef3bc, 3a2ccd0, fb46d15, f72165d: ALL PRESENT
- Full suite 255 passed: CONFIRMED
