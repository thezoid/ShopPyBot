---
phase: 25-design-system
plan: "03"
subsystem: web/templates
tags: [fouc, theme-toggle, xss-fix, design-system, dashboard]
dependency_graph:
  requires: ["25-01", "25-02"]
  provides: ["UI-02", "UI-03", "UI-04"]
  affects: ["web/templates/dashboard.html"]
tech_stack:
  added: []
  patterns:
    - "FOUC-prevention inline script first in <head>"
    - "createElement/textContent DOM construction (XSS-safe)"
    - "theme toggle via dataset.theme + localStorage"
key_files:
  modified:
    - web/templates/dashboard.html
decisions:
  - "escHtml() helper added but unused in Phase 25 — defined for future SVG interpolation cases"
  - "Static empty-state tbody.innerHTML preserved (no API data interpolation; Pitfall 7 compliance)"
metrics:
  duration: 412s
  completed: "2026-06-25"
  tasks_completed: 3
  files_modified: 1
requirements: [UI-02, UI-03, UI-04]
---

# Phase 25 Plan 03: Dashboard HTML Wiring Summary

One-liner: Wired FOUC-prevention inline script, split-CSS links, sticky app-header with theme toggle, and XSS-safe DOM construction (createElement/textContent) into dashboard.html; all Wave 0 RED tests turned GREEN.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add FOUC script, split-CSS + uPlot links, sticky header, uPlot vendor script | b3b05cc | web/templates/dashboard.html |
| 2 | Fix XSS: rebuild loadItems() and loadCredentials() with createElement/textContent | c4b9b89 | web/templates/dashboard.html |
| 3 | Wire theme-toggle JS handler | c60efc7 | web/templates/dashboard.html |

## What Was Built

Task 1 rewrote the `<head>` block so the FOUC-prevention IIFE is the literal first child (before `<meta charset>`). It reads `localStorage.getItem('theme')`, applies `'dark'` or `'light'` to `document.documentElement.dataset.theme`, or falls back to `matchMedia('(prefers-color-scheme: dark)')`. Four CSS `<link>` elements follow in mandated order: `tokens.css`, `components.css`, `dashboard.css`, `vendor/uplot.min.css`. A `<header class="app-header">` with app-name span, empty `#header-uptime` span, and `#theme-toggle` button (sun glyph, aria-label "Switch to dark mode") was inserted before `.container`. The uPlot vendor script `<script src="/static/vendor/uplot.iife.min.js">` was added at the end of `<body>`. The `{% if is_non_local %}` banner block was preserved verbatim.

Task 2 replaced both `innerHTML` XSS vectors. `loadItems()` now builds each row via a `makeCell(text)` helper (`createElement('td')` + `textContent`) for name, link, auto_buy, and quantity; the Remove button is built with `createElement('button')` and wired via `addEventListener('click', ...)` with no `onclick` attribute. `loadCredentials()` builds the entire credential row with `createElement` for the name span, status span, form div, password input, save button, and feedback span; `cred.name` is assigned only via `textContent` and `input.id`. The `escHtml(str)` helper was added for future unavoidable SVG interpolation. The static empty-state `tbody.innerHTML` (no API data) was preserved per Pitfall 7.

Task 3 added a `addEventListener('click', ...)` on `#theme-toggle` that reads the current `document.documentElement.dataset.theme` (defaulting to `'light'`), flips it to the opposite value, sets `document.documentElement.dataset.theme = next`, calls `localStorage.setItem('theme', next)`, updates `aria-label` to "Switch to light mode" / "Switch to dark mode", and sets the glyph to `☾` (dark) or `☀` (light).

## Verification Results

- `pytest tests/test_web_dashboard.py tests/test_design_system.py -q`: 18 passed
- `pytest tests/test_web_dashboard.py::test_banner_renders_when_non_local -q`: PASSED (MC-4)
- `pytest -q` full suite: 763 passed, 2 skipped, 0 failures

## Deviations from Plan

None — plan executed exactly as written. All three tasks implemented per the PATTERNS.md verbatim patterns.

## Known Stubs

None. `#header-uptime` span is intentionally empty in Phase 25; it will be populated by OBS-09 in Phase 28 (documented in UI-SPEC Header Bar Contract).

## Threat Flags

No new security surface introduced. All threat mitigations from the threat register were applied:
- T-25-01: loadItems() XSS closed via createElement/textContent + addEventListener
- T-25-05: loadCredentials() XSS closed via createElement/textContent throughout
- T-25-07: MC-4 banner preserved verbatim; test_banner_renders_when_non_local passes

## Self-Check: PASSED

- [x] web/templates/dashboard.html exists and modified
- [x] b3b05cc commit exists
- [x] c4b9b89 commit exists
- [x] c60efc7 commit exists
- [x] Full suite 763 passed with no regressions
