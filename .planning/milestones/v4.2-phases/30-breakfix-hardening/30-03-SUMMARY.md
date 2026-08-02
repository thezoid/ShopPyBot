---
phase: 30-breakfix-hardening
plan: 03
subsystem: auth
tags: [python, asyncio, nodriver, plugin-abc, login-verification]

# Dependency graph
requires:
  - phase: 30-breakfix-hardening (plans 01, 02)
    provides: BF-02 place-order marker guard + BF-01 WAF auto-solve wiring (unrelated code paths, same file family)
provides:
  - "login() ABC contract change to bool (D-14), with a fail-safe True default"
  - "_verify_login_generic(tab, signin_url_fragment, form_selector) -> bool shared helper (D-11/D-12/D-13)"
  - "relaunch() return-value check on login() (D-15 second half)"
affects: [30-04, 30-05, 30-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "getattr-safe, never-raise, explicit-bool concrete ABC methods (mirrors place_order_guarded)"
    - "ambiguous-signal == not-success (D-13) applied via try/except catch-all returning False"

key-files:
  created: []
  modified:
    - core/plugin_base.py
    - tests/test_plugin_base.py
    - tests/test_relaunch.py

key-decisions:
  - "login() ABC default returns True (login-less plugin is trivially logged in, D-14) -- every real plugin overrides and can now report failure"
  - "_verify_login_generic is the single shared BF-03 verification mechanism (D-11) -- no per-plugin duplication; plugins 30-04/30-05/30-06 call it directly"
  - "relaunch() captures login_ok and logs ERROR on failure; no dispatcher plumbing added (relaunch() has never had orchestrator access) -- the D-15 operator alert surfaces from the orchestrator's existing login_failed short-circuit (30-01) on the next monitoring cycle"

requirements-completed: [BF-03]

# Metrics
duration: 10min
completed: 2026-07-02
---

# Phase 30 Plan 03: BF-03 ABC Foundation Summary

**`login()` ABC contract changed to `bool` with a fail-safe `True` no-op default, plus a shared `_verify_login_generic` helper and a `relaunch()` return-value check -- the foundation every plugin's login-verification conversion (30-04/30-05/30-06) builds on.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-07-02T16:31:00Z
- **Completed:** 2026-07-02T16:41:02Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- `RetailerPlugin.login()` ABC now returns `bool` (was `-> None`); no-op default returns `True` (D-14), documented as a login-less plugin being trivially "logged in"
- New concrete `_verify_login_generic(self, tab, signin_url_fragment, form_selector) -> bool` on the ABC: `False` if the URL still contains the sign-in fragment, `False` if the form selector is still present, `True` only when the URL has moved off sign-in AND the form is gone, `False` on any exception (never raises) -- this is D-11's single shared mechanism for all 7 plugins
- `relaunch()` now captures `login_ok = await self.login()` and logs an ERROR ("relaunch: re-login failed; NOT authenticated") when it is `False`, instead of silently proceeding as if the session were authenticated (D-15 second half)
- `PLUGIN_API_VERSION` stays `2` (additive contract change, consistent with the v4.0 `place_order_guarded` precedent)

## Task Commits

Each task was committed atomically:

1. **Task 1: Change login() ABC to -> bool + add _verify_login_generic** - `a085eef` (feat)
2. **Task 2: Make relaunch() honor a failed re-login** - `6c0e24c` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified
- `core/plugin_base.py` - `login()` ABC returns `bool` (True default); new `_verify_login_generic` helper; `relaunch()` captures and checks `login()`'s return value
- `tests/test_plugin_base.py` - rewrote `test_login_noop` (was asserting `None`, now asserts `True`); added 5 new `_verify_login_generic` cases (url-still-signin, form-still-present, url-changed+form-absent, generic exception, attribute-error-on-tab)
- `tests/test_relaunch.py` - added `test_relaunch_logs_error_on_failed_relogin` and `test_relaunch_no_error_log_on_successful_relogin`

## Decisions Made
- `_verify_login_generic` wraps the entire check (URL read + form select) in one try/except so any failure mode -- missing `tab.target`, CDP error during `tab.select`, malformed tab object -- collapses to the same `False` fail-safe outcome (D-13), matching the plan's `<interfaces>` contract exactly.
- Kept the relaunch() ERROR log message text stable ("re-login failed; NOT authenticated") since it's the only observable signal at this call site per RESEARCH.md's explicit "No dispatcher plumbing needed here" guidance -- the D-15 operator alert itself is already wired at the orchestrator layer in plan 30-01 via the `login_failed` short-circuit on `plugin._checkout_stage`.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The shared BF-03 verification mechanism (`_verify_login_generic`) and the `login() -> bool` contract are live on the ABC, ready for all 7 plugin conversions.
- Full test suite: 829 passed, 2 skipped (was 822 passed baseline before this plan; +7 new tests, 0 regressions).
- Plans 30-04 (Amazon), 30-05 (BestBuy, depends on 30-03+30-04), and 30-06 (5 community plugins, depends on 30-03) can now call `self._verify_login_generic(tab, signin_url_fragment, form_selector)` directly from each plugin's `login()`.
- No blockers.

---
*Phase: 30-breakfix-hardening*
*Completed: 2026-07-02*

## Self-Check: PASSED
