---
phase: 25
slug: design-system
status: planned
nyquist_compliant: true
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
| 25-01-T1 | 01 | 0 | UI-01 | T-25-02 | CSS static analysis tests authored (token coverage, zero hex, vendor existence) | unit (file grep) | `pytest tests/test_design_system.py -q` | NEW | ⬜ pending |
| 25-01-T2 | 01 | 0 | UI-02/UI-03/UI-04 | T-25-01 | Template tests authored (FOUC first, link order, innerHTML regex, no external URL, uPlot served) | unit (HTTP + file grep) | `pytest tests/test_web_dashboard.py -q -k "fouc or css_link or innerHTML or external_urls or uplot_served"` | ADD | ⬜ pending |
| 25-02-T1 | 02 | 1 | UI-01 | T-25-04 | tokens.css declares all tokens; dashboard.css reduced to @imports + layout | unit (file grep) | `pytest tests/test_design_system.py::test_all_required_tokens_declared -q` | NEW | ⬜ pending |
| 25-02-T2 | 02 | 1 | UI-01 | T-25-04 | components.css zero hardcoded hex; all rules var(--xxx) | unit (file grep) | `pytest tests/test_design_system.py::test_no_hardcoded_hex_in_components -q` | NEW | ⬜ pending |
| 25-02-T3 | 02 | 1 | UI-01 | T-25-03 | uPlot 1.6.32 vendored lowercase, no CDN | unit (file exists) | `pytest tests/test_design_system.py::test_uplot_vendor_files_exist -q` | NEW | ⬜ pending |
| 25-03-T1 | 03 | 2 | UI-02/UI-04 | T-25-07 | FOUC script first in head; CSS+uPlot links ordered; sticky header; banner verbatim | unit (HTML parse) | `pytest tests/test_web_dashboard.py -q -k "fouc or css_link or banner"` | ADD | ⬜ pending |
| 25-03-T2 | 03 | 2 | UI-03 | T-25-01/T-25-05 | loadItems/loadCredentials safe DOM; no innerHTML on API data | unit (file grep) | `pytest tests/test_web_dashboard.py::test_no_innerHTML_with_api_data -q` | ADD | ⬜ pending |
| 25-03-T3 | 03 | 2 | UI-02 | T-25-06 | theme toggle flips data-theme, persists localStorage, updates aria-label/glyph | unit (suite green) | `pytest tests/test_web_dashboard.py tests/test_design_system.py -q` | ADD | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_design_system.py` — NEW: static analysis of CSS (no hardcoded hex in component rules, token coverage, no external URLs / `@import url()` to CDN, uPlot vendor existence) — **Plan 25-01 Task 1**
- [ ] `tests/test_web_dashboard.py` — ADD: FOUC inline-script is first child of `<head>`; tokens.css/components.css/dashboard.css link order; XSS regression (no `innerHTML =` on API data); no external URL in CSS; uPlot served — **Plan 25-01 Task 2**
- [ ] MC-4 regression: existing `test_banner_renders_when_non_local` must still pass against the new template — **verified by Plan 25-03 Task 1**

*Existing pytest infrastructure covers the rest.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| No visible flash of wrong theme on reload | UI-02 | Visual/timing artifact not reliably assertable headless | Load dashboard with dark stored, hard-reload, confirm no light flash |
| Theme toggle visual correctness in both modes | UI-01/UI-02 | Pixel-level appearance | Toggle light/dark, confirm tokens apply across all four cards |

*Automated tests cover token presence, script position, and XSS safety; the two above are operator visual checks (deferred to UAT debt per the autonomous-run policy).*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** planned
