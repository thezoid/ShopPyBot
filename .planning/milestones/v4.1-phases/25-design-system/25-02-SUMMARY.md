---
phase: 25
plan: "02"
subsystem: design-system
tags: [css, tokens, dark-mode, vendor, uplot]
dependency_graph:
  requires: ["25-01"]
  provides: ["tokens.css light+dark tokens", "components.css zero-hex rules", "uPlot 1.6.32 vendor"]
  affects: ["web/static/tokens.css", "web/static/components.css", "web/static/dashboard.css", "web/static/vendor/"]
tech_stack:
  added: ["uPlot 1.6.32 (vendored IIFE + CSS, MIT)"]
  patterns: ["CSS custom properties (var(--xxx))", "3-file CSS split (tokens/components/layout)", "GitHub-tag vendor download (no CDN)"]
key_files:
  created:
    - web/static/tokens.css
    - web/static/components.css
    - web/static/vendor/uplot.iife.min.js
    - web/static/vendor/uplot.min.css
  modified:
    - web/static/dashboard.css
decisions:
  - "tokens.css: only :root and [data-theme='dark'] selectors; all 14 light+dark color tokens plus spacing/typography declared"
  - "components.css: 172 lines; zero hardcoded hex; all color/spacing/type via var(--xxx); includes new .app-header and input :focus-visible"
  - "dashboard.css: reduced to 28 lines (@import + reset + body + layout); all hardcoded values replaced with var(--xxx)"
  - "uPlot downloaded from github.com/leeoniya/uPlot tag 1.6.32 dist/; renamed to lowercase; committed as static binary (51KB JS, 1.8KB CSS)"
metrics:
  duration: "~8 minutes"
  completed: "2026-06-25"
  tasks_completed: 3
  files_created: 4
  files_modified: 1
---

# Phase 25 Plan 02: CSS Design System Split Summary

One-liner: Split monolithic dashboard.css into tokens/components/layout 3-file design system with 14-token light+dark themes and uPlot 1.6.32 vendored locally.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create tokens.css + reduce dashboard.css to layout + @imports | 534bacf | web/static/tokens.css (created), web/static/dashboard.css (rewritten) |
| 2 | Create components.css with all component rules via var(--xxx) only | bfd1b57 | web/static/components.css (created) |
| 3 | Vendor uPlot 1.6.32 to web/static/vendor/ (lowercase, no CDN) | 6fde7e1 | web/static/vendor/uplot.iife.min.js, web/static/vendor/uplot.min.css |

## Verification Results

- `pytest tests/test_design_system.py -q`: 3/3 PASSED
- `pytest tests/test_web_dashboard.py::test_no_external_urls_in_static -q`: 1/1 PASSED
- Full suite (excluding Wave 2 pending tests): 745 passed, 2 skipped, 0 failures

Wave 2 tests that remain RED (expected -- require dashboard.html changes not in this plan):
- `test_fouc_script_first_in_head` -- FOUC inline script not yet in dashboard.html
- `test_css_link_order_in_head` -- split CSS links not yet in dashboard.html
- `test_no_innerHTML_with_api_data` -- XSS fix not yet applied to dashboard.html

## Deviations from Plan

None -- plan executed exactly as written. All three tasks match the PATTERNS.md specifications verbatim.

## Known Stubs

None. CSS files are fully wired design tokens. No placeholder values.

## Threat Flags

None. No new network endpoints, auth paths, or file access patterns introduced. uPlot vendored as committed binary with no runtime CDN fetch. No external URL references in any committed CSS file (verified by test_no_external_urls_in_static).

## Self-Check: PASSED

Files exist:
- FOUND: web/static/tokens.css
- FOUND: web/static/components.css
- FOUND: web/static/dashboard.css
- FOUND: web/static/vendor/uplot.iife.min.js
- FOUND: web/static/vendor/uplot.min.css

Commits exist:
- FOUND: 534bacf (tokens.css + dashboard.css refactor)
- FOUND: bfd1b57 (components.css)
- FOUND: 6fde7e1 (uPlot vendor)
