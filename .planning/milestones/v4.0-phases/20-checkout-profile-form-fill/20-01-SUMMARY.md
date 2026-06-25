---
phase: 20-checkout-profile-form-fill
plan: "01"
subsystem: checkout-profile
tags: [credentials, pydantic, checkout, BUY-07]
dependency_graph:
  requires: []
  provides: [core/checkout_profile.py, CHECKOUT_PROFILE_KEYS, CheckoutProfile, load_checkout_profile]
  affects: [core/credentials.py]
tech_stack:
  added: []
  patterns: [pydantic BaseModel, deferred-import loader, EnvVarBackend fake-store test pattern]
key_files:
  created:
    - core/checkout_profile.py
    - tests/test_checkout_profile.py
  modified:
    - core/credentials.py
decisions:
  - CHECKOUT_PROFILE_KEYS lives in core/checkout_profile.py only; credentials.py holds a comment guard against merging (T-20-02)
  - get_store and writeLog imported lazily inside load_checkout_profile() to avoid circular imports
  - address_line2 is the only Optional field; _REQUIRED_CHECKOUT_KEYS derived by comprehension excluding it
  - Tests use EnvVarBackend + monkeypatch.setattr(creds_mod, "_store", store); no real keyring touched
metrics:
  duration: "~8min"
  completed: "2026-06-11T22:06:49Z"
  tasks_completed: 2
  files_changed: 3
---

# Phase 20 Plan 01: Checkout Profile Data Layer Summary

9-key CredentialStore address profile (CHECKOUT_PROFILE_KEYS) with CheckoutProfile pydantic model and load_checkout_profile() loader; isolation from SECRET_KEYS proven by test assertion.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | CHECKOUT_PROFILE_KEYS + CheckoutProfile + loader | d5ff5ab | core/checkout_profile.py, core/credentials.py |
| 2 | Profile model tests (round-trip, incomplete, optional, isolation) | aaeeff7 | tests/test_checkout_profile.py |

## Deviations from Plan

None - plan executed exactly as written.

## Decisions Made

- CHECKOUT_PROFILE_KEYS declared as module-level constant in core/checkout_profile.py only; a documentation comment added immediately after SECRET_KEYS in core/credentials.py names this rule explicitly
- Deferred imports inside load_checkout_profile() (get_store, writeLog) to mirror existing lazy-import discipline and prevent circular imports
- _REQUIRED_CHECKOUT_KEYS is a module-level list comprehension excluding CHECKOUT_ADDRESS_LINE2; avoids repeated inline filtering in the loader
- Test isolation via monkeypatch.delenv loop over all 9 CHECKOUT_PROFILE_KEYS before each test body prevents EnvVarBackend os.environ bleed between tests

## Known Stubs

None.

## Threat Flags

None. load_checkout_profile() logs the `missing` list (key NAMES only; T-20-01). No value is ever logged or included in return. CHECKOUT_PROFILE_KEYS kept isolated from SECRET_KEYS throughout (T-20-02).

## Self-Check: PASSED

- core/checkout_profile.py: EXISTS
- tests/test_checkout_profile.py: EXISTS
- Commits d5ff5ab and aaeeff7: EXIST
- 603 tests pass (2 skipped), 0 failures
