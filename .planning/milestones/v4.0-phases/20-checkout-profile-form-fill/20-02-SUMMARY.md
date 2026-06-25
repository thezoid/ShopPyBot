---
phase: 20-checkout-profile-form-fill
plan: "02"
subsystem: cli
tags: [cli, setup, checkout-profile, credentials, BUY-07]
dependency_graph:
  requires: [20-01]
  provides: [handle_setup_checkout_profile, _prompt_visible, setup --checkout-profile]
  affects: [core/cli/setup.py, core/cli/__init__.py]
tech_stack:
  added: []
  patterns: [Option B flag routing, sys.stdin.readline visible input, key-name-only output]
key_files:
  created:
    - tests/test_setup_checkout_profile.py
  modified:
    - core/cli/setup.py
    - core/cli/__init__.py
decisions:
  - "Option B (--checkout-profile flag) chosen over Option A (sub-subparser): safer, zero risk to existing setup tests; ExistingMagicMock guard uses `is True` identity check to prevent truthy MagicMock bleed"
  - "_prompt_visible uses sys.stdin.readline (ASYNC-03 compliant); no input() builtin"
  - "Confirmation prints key NAME only via `print(f'  Stored: {key}')` mirroring handle_setup line 80 (T-20-03)"
  - "getattr(args, 'checkout_profile', False) is True identity check prevents MagicMock args from triggering checkout-profile branch in existing setup tests"
metrics:
  duration: "~6 minutes"
  completed: "2026-06-11"
  tasks: 2
  files: 3
---

# Phase 20 Plan 02: Setup Checkout Profile CLI -- Summary

`setup --checkout-profile` CLI command that prompts 9 address keys with visible input, stores via CredentialStore, and prints key names only; 4 tests prove correctness and security properties.

## CLI Command Form

**Chosen form: Option B -- `shoppybot setup --checkout-profile`**

Option A (sub-subparser `setup checkout-profile`) was considered but skipped because the existing test fixtures use `MagicMock()` for args, and converting the setup parser to add_subparsers would have required restructuring those tests. Option B adds a simple `--checkout-profile` flag to the existing `setup_p` parser; `handle_setup` dispatches via an `is True` identity branch at the top of the function. Both invocation forms satisfy BUY-07.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Add _prompt_visible + handle_setup_checkout_profile, wire parser | 8076304 | core/cli/setup.py, core/cli/__init__.py |
| 2 | Tests: stores keys, name-only output, optional skip, no CVV | 78925b2 | tests/test_setup_checkout_profile.py |

## Verification Results

- `pytest tests/test_setup_checkout_profile.py -x`: 4 passed
- `pytest tests/test_cli_setup.py -x`: 6 passed (existing setup tests unbroken)
- `pytest` full suite: 607 passed, 2 skipped

## Success Criteria Check

- [x] `shoppybot setup --checkout-profile` prompts 9 CHECKOUT_PROFILE_KEYS with VISIBLE input (sys.stdin.readline)
- [x] CHECKOUT_ADDRESS_LINE2 optional: empty input skips store.set
- [x] Confirmation output prints key NAMES only, never values (T-20-03)
- [x] No card number or CVV is ever prompted or stored
- [x] Existing bare `setup` + `setup --migrate` paths unchanged
- [x] 4 tests pass: stores 9 keys, name-only output, optional line2, no CVV/CARD/PAN key
- [x] Full suite green (607 passed)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] MagicMock args truthy bleed into checkout_profile branch**

- Found during: Task 1 verification (running existing test_cli_setup.py after adding the branch)
- Issue: `getattr(args, "checkout_profile", False)` returns a truthy MagicMock when args is a plain MagicMock(); this triggered the checkout-profile branch in existing tests that didn't set checkout_profile explicitly
- Fix: Changed guard to `getattr(args, "checkout_profile", False) is True` (identity check); only `True` (the boolean) routes to checkout-profile handler; MagicMock attributes and None do not
- Files modified: core/cli/setup.py
- Commit: 8076304

### Design Decisions

**Option B chosen over Option A (documented)**

The plan allowed either sub-subparser (Option A) or flag (Option B). Option B was chosen because:
1. PATTERNS.md explicitly calls Option B "lower risk" and "confirmed by RESEARCH.md"
2. No restructuring of existing `setup_p` or its tests required
3. The `items`/`config` sub-subparser pattern is for genuinely multi-leaf groups; `setup` has only one alternative action

## Threat Mitigations Applied

| Threat | Mitigation | Evidence |
|--------|-----------|---------|
| T-20-03: stdout value disclosure | `print(f"  Stored: {key}")` -- key name only | test_setup_output_is_key_name_only asserts values absent |
| T-20-04: accidental card/CVV capture | Handler loops only CHECKOUT_PROFILE_KEYS (no CVV/CARD key) | test_setup_stores_no_card_or_cvv asserts no forbidden fragment |

## Known Stubs

None. The command stores and confirms all 9 keys; data flows from stdin through CredentialStore and is readable immediately via store.get().

## Self-Check: PASSED

| Item | Result |
|------|--------|
| core/cli/setup.py exists | FOUND |
| core/cli/__init__.py exists | FOUND |
| tests/test_setup_checkout_profile.py exists | FOUND |
| Commit 8076304 (feat Task 1) | FOUND |
| Commit 78925b2 (test Task 2) | FOUND |
