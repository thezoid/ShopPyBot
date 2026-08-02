---
phase: 30-breakfix-hardening
plan: 06
subsystem: auth
tags: [python, asyncio, nodriver, plugin-abc, login-verification, community-plugins]

# Dependency graph
requires:
  - phase: 30-breakfix-hardening (plan 03)
    provides: "login() ABC contract change to bool + _verify_login_generic(tab, signin_url_fragment, form_selector) shared helper"
provides:
  - "BF-03 login()->bool conversion for the 5 community plugins (Walmart, Target, GameStop, NewEgg, SquareEnix) via the shared _verify_login_generic mechanism"
  - "auto_buy() abort-on-failed-login for all 5 community plugins, signaling _checkout_stage='login' before the call"
affects: [30-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "generic-signal-only login verification for unverified-selector community plugins (D-12) -- no platform-specific override, selector tuning stays operator debt"
    - "_checkout_stage='login' set immediately before login() so the orchestrator's login_failed short-circuit (30-01) can distinguish this abort from other stage failures"

key-files:
  created: []
  modified:
    - plugins/shopbot_plugin_walmart.py
    - plugins/shopbot_plugin_target.py
    - plugins/shopbot_plugin_gamestop.py
    - plugins/shopbot_plugin_newegg.py
    - plugins/shopbot_plugin_squareenix.py
    - tests/test_plugin_walmart.py
    - tests/test_plugin_target.py
    - tests/test_plugin_gamestop.py
    - tests/test_plugin_newegg.py
    - tests/test_plugin_squareenix.py

key-decisions:
  - "All 5 community plugins use the generic _verify_login_generic signal only (D-12) -- no platform-specific override, since their login selectors carry pre-existing TODO markers and are unverified against live sites (selector tuning stays operator debt)"
  - "D-15 implemented uniformly as 'return False immediately after login() returns False, aborting all remaining stages' rather than 'no add-to-cart occurred' -- all 5 community plugins call login() mid-flow (after add-to-cart + checkout-proceed), matching RESEARCH.md Pitfall 3"
  - "No save_session() calls added to any of the 5 community plugins -- none called it before this plan, and adding session persistence was out of this plan's scope (only Amazon/BestBuy call save_session() today)"

requirements-completed: [BF-03]

# Metrics
duration: 10min
completed: 2026-07-02
---

# Phase 30 Plan 06: Community Plugin Login Verification Summary

**All 5 community plugins (Walmart, Target, GameStop, NewEgg, SquareEnix) `login()` now returns `bool` via the shared `_verify_login_generic` signal, and each `auto_buy` sets `_checkout_stage="login"` and aborts before place-order on a failed login -- BF-03 now applies uniformly across all 7 plugins.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-07-02T17:15:58Z
- **Completed:** 2026-07-02T17:21:21Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- `login(self) -> bool` conversion for Walmart, Target, GameStop, NewEgg, SquareEnix: missing platform creds return `False`, any exception in the `except Exception` handler returns `False`, and the success path calls `await self._verify_login_generic(tab, signin_url_fragment, form_selector)` per the plan's per-platform table before returning `True`
- Each plugin's `auto_buy` sets `self._checkout_stage = "login"` immediately before `await self.login()` and returns `False` (abort remaining stages, including place-order) when `login()` returns `False`
- 30 new tests across the 5 plugin test files (6 per plugin): missing-credentials returns False, exception returns False, verified success returns True with the correct `_verify_login_generic(tab, fragment, selector)` call args, unverified/ambiguous returns False, `_checkout_stage` is `"login"` at the moment `login()` is invoked, and `auto_buy` never reaches `place_order_guarded` when `login()` fails
- BF-03 (D-11: one shared mechanism, D-12: generic signal for the 5 unverified-selector plugins, D-13: ambiguous == not-success, D-14: bool contract, D-15: abort-on-failure) is now applied uniformly to all 7 plugins across this plan + 30-03 (ABC foundation) + 30-05 (Amazon/BestBuy, tracked separately)

## Task Commits

Each task was committed atomically (TDD RED -> GREEN per task):

1. **Task 1: Walmart + Target + GameStop login() -> bool + auto_buy abort**
   - `20a934b` (test) - failing tests for the 3 plugins' login()/auto_buy conversion
   - `6904f89` (feat) - login()->bool + auto_buy abort implementation, all tests green
2. **Task 2: NewEgg + SquareEnix login() -> bool + auto_buy abort**
   - `0c0df61` (test) - failing tests for the 2 plugins' login()/auto_buy conversion
   - `3681f9b` (feat) - login()->bool + auto_buy abort implementation, all tests green

**Plan metadata:** (this commit)

_TDD tasks: RED (failing tests) -> GREEN (implementation, tests pass) per task; no REFACTOR commit needed (implementation matched the plan's action spec on the first pass)._

## Files Created/Modified
- `plugins/shopbot_plugin_walmart.py` - `login()->bool` via `_verify_login_generic(tab, "/account/login", "#email")`; `auto_buy` sets `_checkout_stage="login"` + aborts on `False`
- `plugins/shopbot_plugin_target.py` - `login()->bool` via `_verify_login_generic(tab, "/account/signin", '[data-test="accountNav-signIn"] input[type="email"]')`; `auto_buy` aborts on failed login
- `plugins/shopbot_plugin_gamestop.py` - `login()->bool` via `_verify_login_generic(tab, "/login", "input#login-form-email")`; `auto_buy` aborts on failed login
- `plugins/shopbot_plugin_newegg.py` - `login()->bool` via `_verify_login_generic(tab, "/identity/signin", "#labeled-input-signEmail")`; `auto_buy` aborts on failed login
- `plugins/shopbot_plugin_squareenix.py` - `login()->bool` via `_verify_login_generic(tab, "/account/login", '[type="email"]')`; `auto_buy` aborts on failed login
- `tests/test_plugin_walmart.py` - 6 new login/auto_buy tests
- `tests/test_plugin_target.py` - 6 new login/auto_buy tests
- `tests/test_plugin_gamestop.py` - 6 new login/auto_buy tests
- `tests/test_plugin_newegg.py` - 6 new login/auto_buy tests
- `tests/test_plugin_squareenix.py` - 6 new login/auto_buy tests

## Decisions Made
- Used the generic signal only (D-12) for all 5 plugins -- no attempt to guess a "tighter" per-platform post-login landing-page selector, since RESEARCH.md explicitly scopes live selector verification for these 5 as operator debt and D-12 already guarantees ambiguous == not-success via the generic mechanism.
- Did not add `save_session()` calls to any of the 5 plugins -- the plan's action text ("move any `save_session()` after verification") is conditional on an existing call; none of the 5 community plugins called `save_session()` before this plan (only Amazon/BestBuy do), so adding it would be new functionality outside this plan's scope.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- BF-03's shared verification mechanism now covers all 5 community plugins; combined with 30-03 (ABC foundation) and 30-05 (Amazon/BestBuy, executed separately since it also depends on 30-04), BF-03 is applied uniformly to all 7 plugins per D-11.
- Full test suite: 863 passed, 2 skipped (was 833 passed baseline before this plan; +30 new tests, 0 regressions).
- Per-retailer live login-selector accuracy for these 5 plugins remains tracked operator debt (selector-TODO bucket) -- the generic verification mechanism ships now and still guarantees ambiguous -> not-success regardless of live selector accuracy.
- No blockers.

---
*Phase: 30-breakfix-hardening*
*Completed: 2026-07-02*

## Self-Check: PASSED
