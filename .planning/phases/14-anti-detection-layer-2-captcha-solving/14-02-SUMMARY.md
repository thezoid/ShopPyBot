---
phase: 14-anti-detection-layer-2-captcha-solving
plan: "02"
subsystem: captcha
tags: [captcha, registry, orchestrator, service, async, run_in_executor, tdd]

requires:
  - phase: 14-anti-detection-layer-2-captcha-solving plan 01
    provides: CaptchaSolver.from_config, check_balance_at_startup, can_solve, solve_recaptcha
  - phase: 13-anti-detection-layer-1-fingerprint-proxy
    provides: PluginRegistry.assign_proxy pattern, ProxyPool wiring in orchestrator

provides:
  - PluginRegistry.assign_solver(plugin) injecting solver onto each plugin before setup()
  - CaptchaSolver constructed fresh in async_main via _build_captcha_solver helper
  - Startup balance check via loop.run_in_executor (never blocking event loop)
  - BotService startup INFO log for captcha.enabled (cap + threshold; no key)
  - tests/test_captcha_wiring.py -- 16 wiring unit tests

affects: [14-03-captcha-plugin-integration, plan-03-captcha-plugin-integration]

tech-stack:
  added: []
  patterns:
    - _build_captcha_solver helper extracted from async_main (mirrors _build_proxy_pool) for 30-line function limit
    - assign_solver mirrors assign_proxy -- attribute injection pattern without ABC version bump
    - Python logging module (logging.getLogger) for BotService CAPTCHA log so caplog captures security assertions
    - run_in_executor for all blocking I/O (balance check HTTP) before TaskGroup starts

key-files:
  created:
    - tests/test_captcha_wiring.py
  modified:
    - core/registry.py
    - core/orchestrator.py
    - core/service.py

key-decisions:
  - "_build_captcha_solver extracted as a top-level helper in orchestrator.py (under 30 lines; mirrors _build_proxy_pool pattern added simultaneously)"
  - "BotService CAPTCHA startup log uses logging.getLogger(__name__) not writeLog -- writeLog writes stdout only; Python logging module enables caplog to capture security-assertion records (same decision as Plan 01 for captcha.py)"
  - "assign_solver unconditionally sets plugin._captcha_solver = self._captcha_solver (None when no solver); no extra guard clause needed -- mirroring assign_proxy's simple assignment style"
  - "balance check placed BEFORE PluginRegistry construction in async_main so plugins receive solver with balance_ok already set"

requirements-completed: [ANTI-06, ANTI-07]

duration: 8min
completed: "2026-06-09"
---

# Phase 14 Plan 02: Captcha Wiring Summary

**CaptchaSolver injected into plugins via PluginRegistry.assign_solver, built fresh per run in async_main with startup balance check off the event loop, and operator-visible INFO log in BotService (no key logged).**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-06-09T19:48:03Z
- **Completed:** 2026-06-09T19:56:15Z
- **Tasks:** 2 (Task 1: registry + orchestrator wiring; Task 2: BotService startup log)
- **Files modified:** 4

## Accomplishments

- PluginRegistry.assign_solver injects CaptchaSolver onto each plugin (or None when disabled), mirroring assign_proxy exactly
- async_main builds solver fresh per run via _build_captcha_solver helper; balance check runs via run_in_executor before TaskGroup starts (never blocks event loop)
- BotService logs "CAPTCHA solving: enabled, max_solves_per_run=N, low_balance_threshold=X.XX" on startup when captcha.enabled=True -- never the API key
- 16 new tests in tests/test_captcha_wiring.py; full suite 452 passed, 2 skipped (no regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: failing wiring tests** - `c7383eb` (test)
2. **Task 1+2 GREEN: registry + orchestrator + service implementation** - `5b3ec8f` (feat)

_Note: Tasks 1 and 2 GREEN committed together since BotService log (Task 2) completes the same test file started in Task 1 RED._

## Files Created/Modified

- `tests/test_captcha_wiring.py` - 16 wiring tests: assign_solver injection, disabled->None, balance check via executor, BotService log presence/absence/no-key-leakage
- `core/registry.py` - Added captcha_solver=None to __init__; added assign_solver() method (10 lines)
- `core/orchestrator.py` - Added _build_captcha_solver and _build_proxy_pool helpers; wired captcha_solver into PluginRegistry; balance check via run_in_executor; assign_solver call in _staggered_setup
- `core/service.py` - Added logging.getLogger(__name__) and CAPTCHA startup INFO log in BotService.__init__

## Decisions Made

- Extracted `_build_proxy_pool` from async_main (was inline) alongside new `_build_captcha_solver` to keep async_main under 30 lines (CLAUDE.md function length constraint).
- Used `logging.getLogger(__name__)` not `writeLog` for BotService CAPTCHA log -- writeLog writes stdout only; Python logging module enables caplog to capture security-assertion records in tests (same decision as Plan 01 for captcha.py).
- Balance check placed BEFORE PluginRegistry construction so plugins receive a solver with balance_ok already evaluated.
- assign_solver uses unconditional attribute assignment (`plugin._captcha_solver = self._captcha_solver`) -- cleaner than an if-guard, matches assign_proxy's simple style.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Orchestrator tests redesigned: build_dispatcher is imported locally inside async_main**
- **Found during:** Task 1 GREEN (first test run attempt)
- **Issue:** Tests initially tried to patch `core.orchestrator.build_dispatcher` but that attribute does not exist at module scope -- it is imported inside the `async_main` function body. Patching failed with AttributeError.
- **Fix:** Redesigned orchestrator tests to test the extracted `_build_captcha_solver` helper directly (unit-testable, no async_main mocking needed) plus two `@pytest.mark.asyncio` tests for balance-check executor dispatch and PluginRegistry kwarg passing, using the `_build_proxy_pool` / `_build_captcha_solver` patch targets instead.
- **Files modified:** tests/test_captcha_wiring.py
- **Verification:** All 16 tests pass; acceptance criteria confirmed via grep

---

**Total deviations:** 1 auto-fixed (Rule 1 -- test design bug)
**Impact on plan:** Test restructure was necessary for correctness. Implementation artifacts are unchanged. No scope creep.

## Issues Encountered

None beyond the test patching issue documented above.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. The only new trust boundary traversal is `BotService.__init__ -> logging output`, which is explicitly covered by T-14-log threat mitigation (caplog test asserts no key string present).

## Known Stubs

None in this plan. CaptchaSolver is fully wired; plugins will call `self._captcha_solver` in Plan 03.

## Self-Check: PASSED

All 5 expected files FOUND. Both task commits verified in git log:
- c7383eb (Task 1 RED)
- 5b3ec8f (Task 1+2 GREEN)

## Next Phase Readiness

- Plan 03 (plugin integration) can now call `self._captcha_solver.solve_recaptcha(sitekey, pageurl)` inside each plugin's CAPTCHA-handling path
- Disabled path (solver=None) is safe: plugins check `if self._captcha_solver is not None and self._captcha_solver.can_solve()` before calling solve
- PLUGIN_API_VERSION unchanged (still 2); no new abstract method on RetailerPlugin

---
*Phase: 14-anti-detection-layer-2-captcha-solving*
*Completed: 2026-06-09*
