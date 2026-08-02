---
phase: 35-audit-fixes-doc-hygiene-cleanup
plan: 01
subsystem: ui
tags: [fastapi, jinja2, csrf, ssr, zero-node, dead-code-removal]

# Dependency graph
requires: []
provides:
  - "Zero-JS POST /items/remove route (CSRF-guarded via check_origin), reused by the SSR remove form"
  - "SSR items-table remove control that functions independent of the JS loadItems() render path"
  - "Dead escHtml() helper removed from dashboard.html, with a permanent grep-0 regression guard"
affects: [dashboard-frontend, web-routes]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Zero-JS mutation route: POST route on the unprefixed pages router accepting form-encoded data, guarded by the existing check_origin CSRF Depends, returning a 303 RedirectResponse (POST/Redirect/GET)"

key-files:
  created: []
  modified:
    - web/routes/pages.py
    - web/templates/dashboard.html
    - tests/test_web_items.py
    - tests/test_web_security.py
    - tests/test_web_dashboard.py

key-decisions:
  - "POST /items/remove lives on web/routes/pages.py (unprefixed router), not web/routes/api.py (JSON-only), since it is an HTML-form target, not a JSON endpoint"
  - "303 See Other (not 302) used for the POST-then-GET redirect, guaranteeing a GET on redirect"
  - "Empty/missing link is a silent no-op (never reaches svc.remove_item), matching the input-validation posture of the existing DELETE route"

patterns-established:
  - "Zero-JS mutation route pattern: form-encoded POST + check_origin Depends + 303 redirect, for any future feature needing graceful degradation when JS fails"

requirements-completed: [AF-01, AF-03]

# Metrics
duration: 5min
completed: 2026-07-02
---

# Phase 35 Plan 01: AF-01 SSR Remove Graceful Degradation + AF-03 Dead escHtml Removal Summary

**Zero-JS `POST /items/remove` route (CSRF-guarded, form-encoded) wired to the SSR items-table remove button, plus removal of the dead `escHtml()` helper with a permanent grep-0 regression guard.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-07-02T22:27:00-04:00
- **Completed:** 2026-07-02T22:32:27-04:00
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments
- Added `POST /items/remove` to `web/routes/pages.py`: form-encoded, `Depends(check_origin)` CSRF-guarded, no-ops on empty link, calls `request.app.state.svc.remove_item(link)`, 303-redirects to `/`.
- Replaced the dead `.btn-remove` button in the SSR items-table with a real `<form method="post" action="/items/remove">` containing a hidden `link` input, so the remove control works even when the JS `loadItems()` fetch path fails or never runs.
- Deleted the dead `escHtml()` helper (0 call sites, confirmed via grep) and added a permanent regression test.

## Task Commits

Each task was committed atomically (Task 1 followed TDD RED -> GREEN):

1. **Task 1 RED: failing tests for POST /items/remove** - `b9454d7` (test)
2. **Task 1 GREEN: add zero-JS POST /items/remove route** - `8f704ff` (feat)
3. **Task 2: wire SSR remove button to HTML form POST** - `9794a10` (feat)
4. **Task 3: delete dead escHtml() helper** - `5e94f68` (chore)

_Note: Task 1 used the TDD RED/GREEN cycle per its `tdd="true"` frontmatter; Tasks 2/3 are plain `auto` tasks._

## Files Created/Modified
- `web/routes/pages.py` - New `POST /items/remove` route (CSRF-guarded, form-encoded, 303 redirect)
- `web/templates/dashboard.html` - SSR remove button replaced with a form POST; `escHtml()` deleted
- `tests/test_web_items.py` - Functional test (remove + redirect) and empty-link no-op test
- `tests/test_web_security.py` - Cross-origin 403 CSRF test for the new route
- `tests/test_web_dashboard.py` - SSR-form assertion test; escHtml grep-0 regression test

## Decisions Made
- Route placed on `web/routes/pages.py` (unprefixed router) rather than `web/routes/api.py`, matching the plan's interface contract and the codebase's JSON-vs-HTML router split.
- 303 status code used for the redirect (not 302), per the plan's explicit HTTP-spec rationale.
- No changes made to `loadItems()` itself — out of scope per the plan (a separate, unrequested robustness fix per RESEARCH.md Pitfall 1).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- AF-01 and AF-03 are closed; the v4.1 audit's UI-03 warning and the dead escHtml() finding are both resolved.
- Full test suite green: 937 passed, 2 skipped (baseline 932 + 5 new AF-01/AF-03 tests), no regressions.
- Remaining Phase 35 scope (AF-02 last_heartbeat leak, DH-01/02/03 frontmatter reconciliation) is unblocked and independent of this plan's changes.

---
*Phase: 35-audit-fixes-doc-hygiene-cleanup*
*Completed: 2026-07-02*

## Self-Check: PASSED

All created/modified files found on disk; all 4 task commit hashes (b9454d7, 8f704ff, 9794a10, 5e94f68) found in git log.
