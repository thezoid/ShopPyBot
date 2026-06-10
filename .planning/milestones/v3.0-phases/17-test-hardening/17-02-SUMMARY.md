---
phase: 17-test-hardening
plan: "02"
subsystem: captcha
tags: [tests, captcha, coverage, security]
dependency_graph:
  requires: []
  provides: [CP-01, CP-02, CP-03, CP-04, CP-05]
  affects: [tests/test_captcha.py]
tech_stack:
  added: []
  patterns: [patch-requests-module, time-sleep-noop, caplog-secret-assertion]
key_files:
  created: []
  modified:
    - tests/test_captcha.py
decisions:
  - Import `core.captcha` module (not just `CaptchaSolver`) in CP-02 so `_MAX_POLLS` constant is referenced without hardcoding 20
  - CP-04 encodes the expected token dict with `json.dumps` inside the test to produce a valid JSON-string poll response matching the 2captcha AmazonTask contract
  - CP-05a and CP-05b combined in one test function per RESEARCH naming convention; each sub-case uses a fresh solver to avoid _solve_count cross-contamination
metrics:
  duration: 3min
  completed_date: "2026-06-10"
  tasks_completed: 2
  files_modified: 1
requirements_closed: [STAB-03]
---

# Phase 17 Plan 02: CAPTCHA Coverage Tests Summary

Five deterministic CAPTCHA error-path tests (CP-01..CP-05) covering poll-error raise, max-polls timeout, generic-ERROR balance gate, WAF happy path, non-JSON fallback, and WAF submit-error. `core/captcha.py` now at 100% statement coverage.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | CP-01/CP-02/CP-03 poll-error, max-polls timeout, generic-ERROR balance | 58b7111 | tests/test_captcha.py |
| 2 | CP-04/CP-05 WAF success, non-JSON fallback, submit-error raise | 9d126cc | tests/test_captcha.py |

## What Was Built

Five new test functions added to `tests/test_captcha.py`:

- `test_solve_recaptcha_poll_error_raises_runtimeerror` (CP-01): `ERROR_CAPTCHA_UNSOLVABLE` poll response raises `RuntimeError`; `_solve_count` is still 1 confirming the pre-network increment invariant (captcha.py:72).
- `test_solve_recaptcha_exceeds_max_polls_raises_timeout` (CP-02): 20 consecutive `CAPTCHA_NOT_READY` responses raise `TimeoutError`; `GET call_count` asserted equal to `_MAX_POLLS` (captcha.py:74).
- `test_balance_check_error_response_disables_solver` (CP-03): `ERROR_KEY_DOES_NOT_EXIST` text sets `balance_ok=False`; sentinel key never appears in any `caplog` record (captcha.py:89 + secret-safety invariant).
- `test_solve_amazon_waf_success_returns_decoded_dict` (CP-04): AmazonTask submit + poll + `json.loads` round-trip returns `{"captcha_voucher":"v","existing_token":"e"}`; `_solve_count` increments (captcha.py:179,201).
- `test_solve_amazon_waf_non_json_token_falls_back_and_submit_error_raises` (CP-05): plain-string token falls back to `{"captcha_voucher":..., "existing_token":""}` (captcha.py:202-203); status=0 submit raises `RuntimeError` (captcha.py:195-196).

## Coverage Results

```
Name              Stmts   Miss  Cover   Missing
-----------------------------------------------
core\captcha.py      95      0   100%
```

Target lines 72, 74, 89, 179, 195-196, 198-203 are all executed.

## Test Suite Results

- `tests/test_captcha.py`: 22 passed (was 17 before this plan)
- Full suite: 540 passed, 2 skipped (was 535 at plan baseline)

## Deviations from Plan

None. Plan executed exactly as written. All five tests implemented against the specified line targets with the required mock pattern (patch `core.captcha.requests`, patch `core.captcha.time.sleep` no-op, no live network).

## Known Stubs

None.

## Threat Flags

None. This plan adds test code only; no production code was changed. CP-03 actively asserts the existing secret-safety invariant (API key never logged on error paths).

## Self-Check: PASSED

- tests/test_captcha.py: FOUND
- Commit 58b7111: confirmed in git log
- Commit 9d126cc: confirmed in git log
- core/captcha.py 100% coverage: confirmed
- 540 passed, 2 skipped full suite: confirmed
