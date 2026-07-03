---
phase: 30-breakfix-hardening
plan: 05
subsystem: auth
tags: [python, asyncio, nodriver, plugin-abc, login-verification, amazon, bestbuy]

# Dependency graph
requires:
  - phase: 30-breakfix-hardening (plan 03)
    provides: "login() ABC contract change to bool + _verify_login_generic(tab, signin_url_fragment, form_selector) shared helper"
  - phase: 30-breakfix-hardening (plan 04)
    provides: "Amazon/BestBuy auto_buy() place-order marker write (BF-02) -- same files, unrelated code paths, lands after this plan in file history"
provides:
  - "BF-03 login()->bool conversion for the two live-tested plugins (Amazon, BestBuy) via the shared _verify_login_generic mechanism"
  - "auto_buy() abort-on-failed-login for Amazon and BestBuy, signaling _checkout_stage='login' before the call"
  - "BF-03 now applied uniformly across all 7 plugins (2 live-tested here + 5 community in 30-06 + ABC foundation in 30-03 + orchestrator short-circuit in 30-01)"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Tighter platform-specific verification signal where the live selector is confirmed: Amazon absence-of-#ap_email (already the generic signal, tightest available without a live account-landing selector); BestBuy redirect-off-/identity/signin (URL-only, honest available signal since the landing-page selector is unverified)"
    - "_checkout_stage='login' set immediately before login() regardless of where in the flow login() sits (Amazon: before any DOM interaction; BestBuy: mid-flow after add-to-cart/checkout-proceed) so the orchestrator's login_failed short-circuit (30-01) can distinguish this abort from other stage failures"

key-files:
  created: []
  modified:
    - plugins/shopbot_plugin_amazon.py
    - plugins/shopbot_plugin_bestbuy.py
    - tests/test_plugin_amazon.py
    - tests/test_plugin_bestbuy.py

key-decisions:
  - "Amazon's auto_buy sets _checkout_stage='login' and calls self.login() BEFORE any DOM interaction (navigate/quantity/buy-now) -- Amazon is the one plugin where login precedes checkout per RESEARCH.md Pitfall 3; this is unchanged ordering, only the abort-on-False behavior is new"
  - "BestBuy's auto_buy sets _checkout_stage='login' and calls self.login() mid-flow, AFTER add-to-cart and checkout-proceed have already executed -- D-15 implemented uniformly as 'return False immediately, abort all remaining stages' rather than 'no add-to-cart occurred', matching the pattern already established for the 5 community plugins in 30-06"
  - "save_session() moved to fire only after _verify_login_generic confirms success on both plugins -- a failed/ambiguous login never persists a session"
  - "Two pre-existing tests per plugin that patched login() with a falsy return_value=None (a leftover from the pre-BF-03 -> None contract) were updated to return_value=True so they continue to exercise their original target behavior (step-timeout / full-success-flow) rather than short-circuiting on the new login-abort path"

requirements-completed: [BF-03]

# Metrics
duration: 19min
completed: 2026-07-02
---

# Phase 30 Plan 05: Amazon + BestBuy Login Verification Summary

**Amazon and BestBuy `login()` now return `bool` via the shared `_verify_login_generic` mechanism (Amazon: absence of `#ap_email`; BestBuy: redirect off `/identity/signin`), and each `auto_buy` sets `_checkout_stage="login"` and aborts before place-order on a failed login -- BF-03 closes out with all 7 plugins now covered.**

## Performance

- **Duration:** 19 min
- **Started:** 2026-07-02T17:24:00Z
- **Completed:** 2026-07-02T17:43:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- `AmazonPlugin.login(self) -> bool`: every early return (missing `AMZ_EMAIL`/`AMZ_PASSWORD`, missing `#ap_email`, missing `#ap_password`, missing `#signInSubmit`) now returns `False`; the `except Exception` handler returns `False`; the success path calls `await self._verify_login_generic(tab, "/ap/signin", "#ap_email")` after "Signed in to Amazon" and only calls `save_session()` + returns `True` when verified
- `BestBuyPlugin.login(self) -> bool`: missing `BB_EMAIL`/`BB_PASSWORD` and the exception handler return `False`; the success path calls `await self._verify_login_generic(tab, "/identity/signin", "#fld-e")` -- the redirect-off-signin URL check is the tighter, honest signal since BestBuy's post-login landing-page selector is unverified -- and only calls `save_session()` + returns `True` when verified
- `AmazonPlugin.auto_buy` sets `self._checkout_stage = "login"` immediately before `await self.login()` (which already ran before any DOM interaction) and now aborts (`return False`) when `login()` returns `False`
- `BestBuyPlugin.auto_buy` sets `self._checkout_stage = "login"` immediately before `await self.login()` (which runs mid-flow, after add-to-cart/checkout-proceed) and aborts the remaining stages (address-fill/cvv-entry/place-order) when `login()` returns `False`
- 15 new tests across the two plugin test files: missing-credentials returns False, missing-DOM-field returns False (Amazon `#ap_email` case), exception returns False, verified success returns True with the correct `_verify_login_generic(tab, fragment, selector)` call args, unverified/ambiguous returns False, `save_session()` is called only after verification, `_checkout_stage` is `"login"` at the moment `login()` is invoked, and `auto_buy` never reaches `place_order_guarded` when `login()` fails
- BF-03 (D-11: one shared mechanism, D-12: tighter platform-specific signal for the live-tested pair, D-13: ambiguous == not-success, D-14: bool contract, D-15: abort-on-failure) is now applied uniformly to all 7 plugins across this plan + 30-03 (ABC foundation) + 30-06 (5 community plugins) + 30-01 (orchestrator login-failure short-circuit)

## Task Commits

Each task was committed atomically:

1. **Task 1: Amazon login() -> bool + verification + auto_buy abort** - `c2ddeed` (feat)
2. **Task 2: BestBuy login() -> bool + verification + auto_buy abort** - `5c07b75` (feat)

**Plan metadata:** (this commit)

_TDD note: the plan specified `tdd="true"` on both tasks; implementation was executed test-first in practice (login()/auto_buy() behavior changes were driven directly by the acceptance criteria and the existing 30-06 community-plugin test pattern) but each task landed as a single feat commit containing both the implementation and its tests, rather than separate RED/GREEN commits -- no separate `test(...)` commit exists per task._

## Files Created/Modified
- `plugins/shopbot_plugin_amazon.py` - `login()->bool` via `_verify_login_generic(tab, "/ap/signin", "#ap_email")`; `save_session()` moved after verification; `auto_buy` sets `_checkout_stage="login"` + aborts on `False`
- `plugins/shopbot_plugin_bestbuy.py` - `login()->bool` via `_verify_login_generic(tab, "/identity/signin", "#fld-e")`; `save_session()` moved after verification; `auto_buy` sets `_checkout_stage="login"` + aborts on `False`
- `tests/test_plugin_amazon.py` - 8 new login/auto_buy tests; 2 pre-existing step-timeout tests updated (`login` mock `return_value=None` -> `True`, since Amazon calls `login()` before the navigate stage and a falsy return now aborts before that stage is reached)
- `tests/test_plugin_bestbuy.py` - 7 new login/auto_buy tests; 1 pre-existing full-flow-success test updated (`login` mock `return_value=None` -> `True`)

## Decisions Made
- Amazon's tighter platform-specific signal (D-12) is the absence of `#ap_email` -- this is already the generic signal for Amazon since RESEARCH.md's per-platform table notes Amazon has no live-verified account-landing-page selector available; no separate "tighter" check was invented.
- BestBuy's tighter signal is URL-only (redirect off `/identity/signin`) rather than a DOM element check, for the same reason -- the post-login landing page selector is unverified, so the URL check is the honest available signal per RESEARCH.md.
- Implemented D-15 uniformly as "abort all remaining stages immediately" for both plugins despite their different `login()` call-site positions in `auto_buy` (Amazon: before DOM interaction; BestBuy: mid-flow) -- matches the precedent already set in 30-06 for the 5 community plugins, avoiding two different abort semantics in the codebase.

## Deviations from Plan

None - plan executed exactly as written. The two pre-existing test updates (Amazon step-timeout mocks, BestBuy full-flow-success mock) were anticipated by the plan's own `<read_first>` guidance (RESEARCH.md Pitfall 2/3 context) and are a direct, necessary consequence of the `login()->bool` contract change specified in the plan's `<action>` blocks -- not unplanned scope.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- BF-03 is now code-complete and CI-green across all 7 plugins: Amazon + BestBuy (this plan), Walmart/Target/GameStop/NewEgg/SquareEnix (30-06), the shared ABC mechanism (30-03), and the orchestrator-layer `login_failed` short-circuit (30-01).
- Phase 30 (Breakfix Hardening) is now fully complete: BF-01 (30-02), BF-02 (30-01 read-side + 30-04 write-side), BF-03 (30-01, 30-03, 30-05, 30-06).
- Full test suite: 878 passed, 2 skipped (was 863/2 baseline before this plan; +15 new tests, 0 regressions).
- Live-environment UAT for all three breakfixes remains tracked operator debt per the v4.2 "code-complete + CI-green" milestone rule.
- No blockers.

---
*Phase: 30-breakfix-hardening*
*Completed: 2026-07-02*

## Self-Check: PASSED
