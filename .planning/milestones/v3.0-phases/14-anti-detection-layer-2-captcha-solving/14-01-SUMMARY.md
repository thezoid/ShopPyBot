---
phase: 14-anti-detection-layer-2-captcha-solving
plan: "01"
subsystem: captcha
tags: [captcha, credentials, config, tdd, security]
dependency_graph:
  requires: [core/credentials.py, core/config_schema.py]
  provides: [core/captcha.py, CaptchaConfig, TWOCAPTCHA_API_KEY secret key]
  affects: [core/config_schema.py AppConfig, tests/test_credentials.py]
tech_stack:
  added: []
  patterns: [TDD RED-GREEN, from_config classmethod, logging module for caplog-testable output]
key_files:
  created:
    - core/captcha.py
    - tests/test_captcha.py
    - tests/test_captcha_config.py
  modified:
    - core/credentials.py
    - core/config_schema.py
    - sample.config.yml
    - tests/test_credentials.py
decisions:
  - Use Python logging module (not writeLog) in core/captcha.py so caplog captures security-assertion log records in tests
  - solve_count increments before network calls so cap is respected even if call raises
  - ERROR_ZERO_BALANCE treated as 0.0 inside _check_balance to simplify caller logic
metrics:
  duration: "~10min"
  completed: "2026-06-09T19:42:00Z"
  tasks_completed: 2
  files_changed: 7
---

# Phase 14 Plan 01: CAPTCHA Foundation Summary

**One-liner:** 2captcha v1 client (hand-rolled requests submit/poll/balance) with per-run solve cap, zero-balance gate, and API key exclusively in the credential store.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Register secret key + CaptchaConfig + test scaffolds | ad9660c | core/credentials.py, core/config_schema.py, sample.config.yml, tests/test_captcha_config.py, tests/test_captcha.py |
| 2 RED | CaptchaSolver failing unit tests | bfc070a | tests/test_captcha.py |
| 2 GREEN | CaptchaSolver implementation | 2967963 | core/captcha.py, tests/test_captcha.py (13 tests), tests/test_credentials.py (count fix) |

## Verification

- `python -c "from core.credentials import SECRET_KEYS; assert 'TWOCAPTCHA_API_KEY' in SECRET_KEYS"` exits 0
- `python -c "from core.config_schema import AppConfig, CaptchaConfig; c=AppConfig(); assert c.captcha.enabled is False"` exits 0
- `python -c "from core.config_schema import CaptchaConfig; assert 'api_key' not in CaptchaConfig.model_fields"` exits 0
- `python -m pytest tests/test_captcha.py tests/test_captcha_config.py -q` -- 17 passed
- `python -m pytest` -- 436 passed, 2 skipped (no regressions)

## Must-Haves Confirmed

- TWOCAPTCHA_API_KEY in SECRET_KEYS: yes (core/credentials.py line 73)
- CaptchaConfig has no api_key field: confirmed by test assertion
- AppConfig.captcha defaults to CaptchaConfig(enabled=False): confirmed
- from_config returns None when disabled or key missing: tested
- solve_recaptcha submits to in.php and polls res.php; raises on ERROR_ responses: tested
- check_balance_at_startup sets balance_ok=False on zero; WARNING when below threshold: tested
- can_solve returns False once solve_count reaches max_solves_per_run: tested
- API key never appears in any log record: caplog assertion in test_key_not_logged passes

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_secret_keys_canonical expected count 19, now 20**
- Found during: Task 2 full-suite run
- Issue: test hardcoded `assert len(SECRET_KEYS) == 19`; adding TWOCAPTCHA_API_KEY made it 20
- Fix: updated test docstring and assertion to expect 20; updated credentials.py comment
- Files modified: tests/test_credentials.py, core/credentials.py
- Commit: 2967963

**2. [Deviation - Logging approach] Use Python logging module instead of writeLog**
- Found during: Task 2 GREEN phase (3 tests failed because caplog doesn't capture writeLog stdout)
- Issue: plan requires "caplog-based test asserts the api_key value never appears in any captured log record"; writeLog writes to stdout, bypassing Python's logging system
- Fix: core/captcha.py uses `logging.getLogger(__name__)` instead of writeLog; caplog captures all records
- Files modified: core/captcha.py
- This is a new module with no prior pattern obligation; using the standard library is the correct approach

## TDD Gate Compliance

- RED gate: commit bfc070a -- `test(14-01): add failing CaptchaSolver unit tests (TDD RED)` -- 13 tests, all failing with ModuleNotFoundError
- GREEN gate: commit 2967963 -- `feat(14-01): implement CaptchaSolver 2captcha v1 client (TDD GREEN)` -- all 13 pass

## Known Stubs

- `solve_amazon_waf()` in core/captcha.py is a best-effort stub: it submits AmazonTask and polls, but the returned token's injection path into Amazon's page is site-specific and unverified (CONTEXT.md deferred decision). Plan 02/03 will call it only behind a manual-pause fallback.

## Self-Check: PASSED

All 6 expected files FOUND. All 3 task commits verified in git log:
- ad9660c (Task 1)
- bfc070a (Task 2 RED)
- 2967963 (Task 2 GREEN)
