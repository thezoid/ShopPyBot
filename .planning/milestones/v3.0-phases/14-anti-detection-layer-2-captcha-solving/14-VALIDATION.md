---
phase: 14
slug: anti-detection-layer-2-captcha-solving
status: approved
nyquist_compliant: true
wave_0_complete: true
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
| 14-01-01 | 01 | 1 | ANTI-06, ANTI-07 | T-14-key | CaptchaConfig has no api_key; key only in CredentialStore | unit | `python -m pytest tests/test_captcha_config.py -q` | ✅ | ⬜ pending |
| 14-01-02 | 01 | 1 | ANTI-06, ANTI-07 | T-14-key/cost | key never logged; max_solves cap; timeout(120) | unit | `python -m pytest tests/test_captcha.py -q` | ✅ | ⬜ pending |
| 14-02-01 | 02 | 2 | ANTI-06, ANTI-07 | T-14-cost | startup balance check; low-warn; zero→skip | unit | `python -m pytest tests/test_captcha_wiring.py -q` | ✅ | ⬜ pending |
| 14-02-02 | 02 | 2 | ANTI-06, ANTI-07 | — | assign_solver mirrors assign_proxy; fresh per run | unit | `python -m pytest tests/test_captcha_wiring.py -q` | ✅ | ⬜ pending |
| 14-03-01 | 03 | 3 | ANTI-06, ANTI-07 | T-14-token | reCAPTCHA solve under timeout; empty-sitekey→manual | unit | `python -m pytest tests/test_captcha_plugin.py -q` | ✅ | ⬜ pending |
| 14-03-02 | 03 | 3 | ANTI-06, ANTI-07 | — | WAF→graceful manual pause; no silent skip | unit | `python -m pytest tests/test_captcha_plugin.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `TWOCAPTCHA_API_KEY` added to `SECRET_KEYS` (covered by task 14-01-01)
- [x] Test files (`test_captcha_config.py`, `test_captcha.py`, `test_captcha_wiring.py`, `test_captcha_plugin.py`) created as each plan's first task

*pytest-asyncio already installed — no install task. `requests==2.33.1` already pinned — no new dep.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live reCAPTCHA v2 solve end-to-end | ANTI-06 | Requires a real reCAPTCHA page + funded 2captcha account | Enable captcha, hit a reCAPTCHA page, confirm token solved+injected and flow continues |
| Amazon WAF CAPTCHA path | ANTI-07 | WAF token injection site-specific/unverified | Confirm graceful fallback to manual pause on Amazon WAF |
| Low/zero balance behavior, live account | ANTI-06 | Requires real 2captcha account states | Confirm low-balance WARNING + zero-balance skip→manual pause with a real key |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-09
