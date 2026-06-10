---
phase: 17-test-hardening
plan: "04"
subsystem: tests
tags: [testing, plugin-abc, ban-detection, proxy-cooldown, coverage]
dependency_graph:
  requires: [core/plugin_base.py, core/stealth.py]
  provides: [AB-03 coverage, AB-04 coverage]
  affects: [tests/test_plugin_base.py]
tech_stack:
  added: []
  patterns: [MagicMock sentinel, getattr-safety probe pattern]
key_files:
  created: []
  modified:
    - tests/test_plugin_base.py
decisions:
  - "MagicMock used for pool stub; plain object() sentinel for proxy to verify identity in assert_called_once_with"
  - "Sub-case 3 (no-proxy safe path) uses hasattr assertions before _handle_ban to prove attributes are truly absent, not just falsy"
  - "from unittest.mock import MagicMock added at module top alongside existing imports; no new packages installed"
metrics:
  duration: "4min"
  completed: "2026-06-10"
  tasks: 1
  files: 1
---

# Phase 17 Plan 04: Plugin ABC Tests (AB-03 + AB-04) Summary

Tests for STAB-03 criterion 4 unit half: requires_captcha/difficulty overrides (AB-03) and the ban-detection to proxy-cooldown bridge (AB-04, plugin_base.py:43-55, branch 53->55).

## What Was Built

Two new tests in `tests/test_plugin_base.py` covering the remaining plugin_base.py gap:

`test_requires_captcha_and_easy_difficulty_overrides` (AB-03): defines an inline `EasyCaptchaPlugin` subclass with `difficulty='easy'` and `requires_captcha=True`; asserts both class attrs reflect the overrides and `requires_proxy` still inherits `False`. Proves `__init_subclass__` accepts a valid difficulty override without raising and that additive class-attr overrides at subclass definition time stick on the class.

`test_handle_ban_records_failure_on_proxy_when_banned` (AB-04): covers plugin_base.py lines 43-55 with all three sub-cases:
1. Ban phrase + proxy/pool configured: `pool.record_failure(proxy)` called once, returns `True` (lines 53-54).
2. Benign text: early return `False` at line 49-50, `record_failure` not called.
3. No `_proxy`/`_pool` attributes set: `getattr` defaults to `None`, `if proxy and pool` guard short-circuits, returns `True` without exception (the 53->55 branch executed).

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | AB-03 metadata override + AB-04 _handle_ban bridge | de1e3ee | tests/test_plugin_base.py |

## Test Results

- Before: 546 passed, 2 skipped
- After: 548 passed, 2 skipped
- `tests/test_plugin_base.py`: 13 passed (up from 11)

## Deviations from Plan

None. Plan executed exactly as written. Single TDD task, RED/GREEN combined since both tests target genuinely uncovered lines (no pre-existing coverage of branch 53->55 or the requires_captcha+easy permutation).

## Known Stubs

None.

## Threat Flags

None. Test-only additions; no production code changed. No new attack surface.

## Self-Check: PASSED

- `tests/test_plugin_base.py` exists and contains both new test functions.
- Commit `de1e3ee` confirmed in git log.
- Full suite: 548 passed, 2 skipped (count rose as expected).
- `test_requires_captcha_and_easy_difficulty_overrides` and `test_handle_ban_records_failure_on_proxy_when_banned` both present and passing.
