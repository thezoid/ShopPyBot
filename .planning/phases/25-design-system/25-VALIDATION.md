---
phase: 25
slug: design-system
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-25
---

# Phase 25 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | pytest (project root); web tests in `tests/test_web_dashboard.py` |
| **Quick run command** | `pytest tests/test_web_dashboard.py tests/test_design_system.py -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick command on touched test files
- **After every plan wave:** Run `pytest -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| (populated during planning — planner maps each task to a test) | | | | | | | | | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_design_system.py` — NEW: static analysis of CSS (no hardcoded hex in component rules, token coverage, no external URLs / `@import url()` to CDN)
- [ ] `tests/test_web_dashboard.py` — ADD: FOUC inline-script is first child of `<head>`; tokens.css/components.css link order; XSS regression (no `innerHTML =` on API data; `<b>bold</b>` renders literal); uPlot served with no CDN reference
- [ ] MC-4 regression: existing `test_banner_renders_when_non_local` must still pass against the new template

*Existing pytest infrastructure covers the rest.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| No visible flash of wrong theme on reload | UI-02 | Visual/timing artifact not reliably assertable headless | Load dashboard with dark stored, hard-reload, confirm no light flash |
| Theme toggle visual correctness in both modes | UI-01/UI-02 | Pixel-level appearance | Toggle light/dark, confirm tokens apply across all four cards |

*Automated tests cover token presence, script position, and XSS safety; the two above are operator visual checks.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
