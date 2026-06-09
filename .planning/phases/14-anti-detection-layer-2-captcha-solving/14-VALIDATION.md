---
phase: 14
slug: anti-detection-layer-2-captcha-solving
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-09
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-asyncio (asyncio_mode=auto, installed) |
| **Config file** | pyproject.toml (existing) |
| **Quick run command** | `python -m pytest -q <touched test file>` |
| **Full suite command** | `python -m pytest` |
| **Estimated runtime** | ~35 seconds |

---

## Sampling Rate

- **After every task commit:** Run the task's targeted `pytest -q <file>`
- **After every plan wave:** Run `python -m pytest`
- **Before `/gsd:verify-work`:** Full suite green (no new failures vs Phase 13 baseline of 419 passed, 2 skipped)
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 14-01-01 | 01 | 1 | ANTI-06, ANTI-07 | T-14-key | API key only in CredentialStore; never logged | unit | `python -m pytest tests/test_captcha.py -q` | ❌ W0 | ⬜ pending |

*Planner refines this map per task. The 2captcha client (submit/poll/balance), max_solves cap, low/zero-balance branches, and the 120s timeout are all unit-testable by mocking `requests` — NO live API calls in CI.*

---

## Wave 0 Requirements

- [ ] `tests/test_captcha.py` — solver unit tests (mock requests submit/poll/getbalance)
- [ ] `TWOCAPTCHA_API_KEY` added to `SECRET_KEYS` (CredentialStore) — required before solver can read the key

*pytest-asyncio already installed — no install task.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live reCAPTCHA v2 solve end-to-end | ANTI-06 | Requires a real reCAPTCHA page + funded 2captcha account | Enable captcha, hit a reCAPTCHA-protected page, confirm token solved + injected and flow continues |
| Amazon WAF CAPTCHA path | ANTI-07 | WAF token injection is site-specific/unverified | Confirm graceful fallback to manual pause on Amazon WAF (solve path deferred) |
| Low/zero balance behavior against live account | ANTI-06 | Requires real 2captcha account states | Confirm low-balance WARNING and zero-balance skip→manual pause with a real key |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
