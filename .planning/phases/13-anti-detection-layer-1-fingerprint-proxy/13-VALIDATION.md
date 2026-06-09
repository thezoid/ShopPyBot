---
phase: 13
slug: anti-detection-layer-1-fingerprint-proxy
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-09
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (+ pytest-asyncio for async coroutines) |
| **Config file** | pytest.ini / pyproject.toml (existing) |
| **Quick run command** | `pytest -q <touched test file>` |
| **Full suite command** | `pytest` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run the task's targeted `pytest -q <file>`
- **After every plan wave:** Run `pytest`
- **Before `/gsd:verify-work`:** Full suite must be green (no new failures vs Phase 12 baseline of 359 passed, 2 skipped)
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 13-01-01 | 01 | 1 | ANTI-08 | — | stealth JS applied at startup | unit | `pytest -q tests/test_stealth.py` | ❌ W0 | ⬜ pending |

*Planner refines this map per task. Stealth JS injection, proxy rotation order, failure-threshold/cooldown logic, and config parsing are all unit-testable without a live browser (mock the nodriver tab/CDP).* 

---

## Wave 0 Requirements

- [ ] `tests/test_stealth.py` — stubs for stealth + proxy logic (ANTI-08, ANTI-04, ANTI-05)
- [ ] `pytest-asyncio` — required if not already installed, for async `apply_stealth`/proxy coroutines

*Planner confirms whether pytest-asyncio is already present; if so, no install task.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Fingerprint patches measurably reduce bot signals | ANTI-08 | Requires a real browser hitting a fingerprint probe (CreepJS / bot.sannysoft) | Launch bot, load probe page, confirm window.chrome/plugins/languages/screen patched and no WebRTC real-IP leak |
| Live proxy rotation on real ban signal | ANTI-04/ANTI-05 | Requires a real banning endpoint + live proxy pool | Enable proxy config, trigger 403/429, observe rotation + retirement |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
