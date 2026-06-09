---
status: partial
phase: 14-anti-detection-layer-2-captcha-solving
source: [14-VERIFICATION.md]
started: 2026-06-09
updated: 2026-06-09
---

## Current Test

[awaiting human testing]

## Tests

### 1. End-to-end reCAPTCHA v2 auto-solve (ANTI-06)
expected: With `captcha.enabled: true` and a live funded 2captcha account (TWOCAPTCHA_API_KEY in CredentialStore), hitting a real reCAPTCHA v2 page resolves the CAPTCHA without manual intervention; no API key appears in logs.
result: [pending — requires a real reCAPTCHA page + funded 2captcha account]

### 2. Zero-balance guard (ANTI-07)
expected: With a zero-balance 2captcha account, the bot logs a WARNING and falls back to manual pause with NO paid solve request.
result: [pending — requires a real zero-balance account]

### 3. Low-balance warning (ANTI-07)
expected: With balance below the threshold ($1.00 default), the bot logs a WARNING, `balance_ok` stays True, and the solver remains usable.
result: [pending — requires a real low-balance account]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
