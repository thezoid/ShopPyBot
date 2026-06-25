---
phase: 25-design-system
plan: "01"
subsystem: test-scaffold
tags: [tdd, css, design-system, xss, security]
depends_on: []
provides: [test_design_system.py, test_web_dashboard.py additions]
affects: [web/static/components.css, web/static/tokens.css, web/static/vendor/]
tech_stack:
  added: []
  patterns: [file-grep test, HTMLParser subclass, re.DOTALL multiline scan]
key_files:
  created:
    - tests/test_design_system.py
  modified:
    - tests/test_web_dashboard.py
decisions:
  - "test_no_external_urls_in_static strips CSS comments before scanning to avoid false positive on the existing dashboard.css header comment `/* No @import url() */`"
  - "test_no_innerHTML_with_api_data uses re.DOTALL with non-greedy `.*?` to catch the multiline template-literal violation at line 255 (div.innerHTML = backtick on one line, ${cred.name} on the next) as well as line 241"
metrics:
  duration: "566s"
  completed: "2026-06-25"
  tasks: 2
  files: 2
requirements: [UI-01, UI-02, UI-03, UI-04]
---

# Phase 25 Plan 01: Wave 0 TDD Scaffold Summary

Wave 0 test scaffold encoding all Phase 25 acceptance criteria as executable assertions: CSS token coverage, zero hardcoded hex in components, FOUC script position, CSS link order, XSS regression guard, no external URLs in CSS, and uPlot vendor existence.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create tests/test_design_system.py (CSS static analysis + vendor existence) | 2d19b5e | tests/test_design_system.py |
| 2 | Add FOUC/link-order/XSS/external-URL/uPlot tests to test_web_dashboard.py | a30e053 | tests/test_web_dashboard.py |

## What Was Built

Two test modules containing 8 new test functions that encode the Phase 25 implementation requirements as executable assertions. All Wave 0 RED tests fail with the correct failure reason (missing files or assertion violations), confirming the tests are wired to real implementation artifacts.

**test_design_system.py (new, 3 tests - all RED):**
- `test_no_hardcoded_hex_in_components`: reads `web/static/components.css`, strips comments, asserts no hex literals or `rgb()` values
- `test_all_required_tokens_declared`: reads `web/static/tokens.css`, asserts all 27 required CSS custom properties from UI-SPEC are declared
- `test_uplot_vendor_files_exist`: asserts `web/static/vendor/uplot.iife.min.js` and `web/static/vendor/uplot.min.css` exist

**test_web_dashboard.py (5 tests added - 4 RED, 1 GREEN):**
- `test_fouc_script_first_in_head`: HTMLParser subclass verifies first `<head>` child is `<script>` containing `localStorage` (RED)
- `test_css_link_order_in_head`: asserts tokens/components/dashboard CSS links exist in correct order (RED)
- `test_no_innerHTML_with_api_data`: XSS CI gate using re.DOTALL, catches both current violations (`item.` line 241, `cred.` line 255) (RED)
- `test_no_external_urls_in_static`: strips CSS comments then checks no `url(http` or `@import url(` (GREEN - passes now and must stay green after split)
- `test_uplot_served`: asserts `/static/vendor/uplot.iife.min.js` returns 200 (RED)

**Final counts:** 18 collected total; 7 RED (Wave 0 scaffold, implementation missing); 11 GREEN (all pre-existing + test_no_external_urls_in_static). MC-4 test `test_banner_renders_when_non_local` confirmed still passing.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_no_external_urls_in_static false positive on comment text**
- **Found during:** Task 2 verification run
- **Issue:** Existing `dashboard.css` header contains `/* No CDN. No @import url(). No external fonts. */` - the literal string `@import url(` appears inside a CSS comment. The bare string check caused a false positive failure.
- **Fix:** Added `re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)` to strip block comments before scanning, consistent with the approach used in `test_no_hardcoded_hex_in_components`.
- **Files modified:** tests/test_web_dashboard.py
- **Commit:** a30e053 (included in Task 2 commit)

**2. [Rule 2 - Missing critical functionality] test_no_innerHTML_with_api_data uses re.DOTALL for multiline coverage**
- **Found during:** Task 2 implementation
- **Issue:** The plan's exact regex `innerHTML\s*=\s*.*\$\{(item\.|...)` without `re.DOTALL` would only catch the single-line violation at line 241 (`tr.innerHTML = \`...\${item.name}...\``). The violation at line 255 spans two lines (`div.innerHTML = \`` on line 255, `${cred.name}` on line 256) and would be missed.
- **Fix:** Changed to non-greedy `.*?` with `re.DOTALL` flag so both violations are caught. Acceptance criteria explicitly states both must be caught. Without this, the test would turn false-GREEN after Wave 2 fixes only the line-241 violation.
- **Files modified:** tests/test_web_dashboard.py
- **Commit:** a30e053 (included in Task 2 commit)

## TDD Gate Compliance

This plan is Wave 0 - all tests are RED (failing) by design. The RED gate is fulfilled. GREEN and REFACTOR gates belong to waves 1 and 2.

| Gate | Status | Evidence |
|------|--------|---------|
| RED | PASSED | 7 tests fail for correct reasons (missing files / assertion violations on existing code) |
| GREEN | N/A (Wave 0) | Implementation lands in waves 1-2 |
| REFACTOR | N/A (Wave 0) | Not applicable |

## Known Stubs

None. This plan creates test files only; no implementation stubs.

## Threat Flags

None. Test files do not introduce new network endpoints, auth paths, or file access patterns beyond reading local test fixtures.

## Self-Check: PASSED

- tests/test_design_system.py: FOUND
- tests/test_web_dashboard.py: FOUND (modified)
- Commit 2d19b5e: FOUND
- Commit a30e053: FOUND
- 7 RED tests confirmed failing for correct reasons
- 11 GREEN tests confirmed passing
- MC-4 test_banner_renders_when_non_local: PASSING
