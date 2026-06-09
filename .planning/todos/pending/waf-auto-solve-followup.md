---
id: waf-auto-solve-followup
created: 2026-06-09
status: pending
source: Phase 14 (Anti-Detection Layer 2 — CAPTCHA Solving)
relates_to: ANTI-06
priority: medium
---

# Follow-up: Amazon WAF CAPTCHA auto-solve wiring

## Context

Phase 14 delivered reCAPTCHA v2 auto-solving end-to-end via 2captcha. Amazon WAF
auto-solving was **deferred** by user decision (2026-06-09) because the token-injection
path is site-specific, undocumented, and rated LOW-confidence by Phase 14 research
(`window.gokuProps` has a ~30s freshness window; the returned `captcha_voucher`/
`existing_token` application path — cookie vs header vs POST body — requires live
Network-tab reverse-engineering against Amazon).

This phase ships a graceful manual-pause fallback for the WAF case (no silent skip),
and the `solve_amazon_waf(key, iv, context, pageurl)` API stub exists in `core/captcha.py`
as the future contract.

## What's needed to close this

1. Reverse-engineer the Amazon WAF token application path via live Network monitoring
   during a real manual WAF solve.
2. Extract `websiteKey`, `iv`, `context` from `window.gokuProps` (respect the freshness window).
3. Wire `solve_amazon_waf()` from the Amazon plugin's WAF-detection branch and apply
   the returned token by the verified injection path.
4. Add integration coverage; keep the manual-pause fallback when extraction/injection fails.

## Acceptance

- Enabling `captcha.enabled: true` produces an automated WAF solve on a real Amazon WAF
  challenge, with the existing manual pause as the documented fallback on failure.
- ANTI-06 can then be marked fully delivered (reCAPTCHA v2 + Amazon WAF).
