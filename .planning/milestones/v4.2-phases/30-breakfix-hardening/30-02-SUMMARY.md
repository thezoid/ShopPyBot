---
phase: 30-breakfix-hardening
plan: 02
subsystem: anti-detection
tags: [captcha, 2captcha, amazon, waf, asyncio, injection-safety]

# Dependency graph
requires:
  - phase: 14-anti-detection-layer-2-captcha-solving
    provides: CaptchaSolver (core/captcha.py) with solve_recaptcha wired + solve_amazon_waf already implemented/unit-tested but unwired
provides:
  - "Amazon WAF (gokuProps) branch in _solve_or_pause wired to CaptchaSolver.solve_amazon_waf via run_in_executor + asyncio.timeout(120), single attempt (D-06/D-07)"
  - "_inject_waf_token helper: json.dumps()-escaped, quote/backslash/newline rejection before tab.evaluate() injection (V5/CR-02)"
  - "Manual-pause fallback preserved on gokuProps decode failure, solver-unavailable/can_solve()-False, solve failure/timeout, and injection failure (D-08)"
affects: [30-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "WAF solve wiring mirrors the already-tested solve_recaptcha branch structurally (run_in_executor + asyncio.timeout(120) + except (TimeoutError, Exception))"
    - "Lambda-wrapped run_in_executor call site (lambda: solver.solve_amazon_waf(...)) keeps a literal solve_amazon_waf( call site in source for structural/source-grep verification while still running the blocking call off the event loop"

key-files:
  created: []
  modified:
    - plugins/shopbot_plugin_amazon.py
    - tests/test_captcha_plugin.py

key-decisions:
  - "Injection mechanism: document.cookie via tab.evaluate() (JS-eval path), not CDP tab.send(cdp_storage.set_cookies(...)) -- the plan explicitly permits either as best-effort per RESEARCH.md Assumption A1 (exact 2captcha AmazonTask payload shape is undocumented); JS-eval keeps the change scoped to the plugin file with no new CDP imports, and tests assert wiring, not live payload correctness"
  - "No redundant can_solve() re-check inside the WAF branch -- the existing top-of-function gate (solver is None or not solver.can_solve()) already covers D-08's solver-unavailable fallback before WAF detection is even reached, mirroring how the solve_recaptcha branch has no local re-check either"

patterns-established:
  - "Lambda-wrapped executor call preserves a literal call-site string for source-grep-style structural tests without changing the blocking-off-event-loop semantics"

requirements-completed: [BF-01]

# Metrics
duration: 12min
completed: 2026-07-02
---

# Phase 30 Plan 02: Amazon WAF Auto-Solve Wiring Summary

**The Amazon WAF gokuProps branch now calls the already-implemented `CaptchaSolver.solve_amazon_waf` once via `run_in_executor`/`asyncio.timeout(120)`, injects the escaped voucher/token as cookies on success, and falls back to the existing manual-pause on every non-success path.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-02T16:17:00Z
- **Completed:** 2026-07-02T16:29:13Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- BF-01 wired: Amazon WAF challenge detection now attempts one automated 2captcha `solve_amazon_waf` solve before falling back to manual pause, reducing unattended-run stalls when `captcha.enabled=true` with a funded balance.
- New `_inject_waf_token` helper reuses the exact `_inject_token` escaping invariant (reject quote/backslash/newline, `json.dumps()` escape) for the WAF voucher/token pair before any `tab.evaluate()` interpolation (V5/CR-02, T-30-01).
- Manual-pause fallback preserved on every non-success path: gokuProps decode failure, solver unavailable/`can_solve()` False, solve failure/timeout, and injection failure -- WAF solving never hard-fails the item (D-08).
- Single-attempt policy honored (D-07): no retry loop added; AST guard `test_no_retry_loops.py` stays green.
- Two pre-fix tests rewritten to assert the new solve-success and fallback behavior (Pitfall 1), plus 4 new fallback-path tests and 2 new injection-escaping tests.

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewire the WAF branch to solve_amazon_waf + add _inject_waf_token** - `e7115ca` (feat)
2. **Task 2: Rewrite the two pre-fix WAF tests + assert both paths** - `258d6d0` (test)

**Plan metadata:** (this commit)

## Files Created/Modified
- `plugins/shopbot_plugin_amazon.py` - `_solve_or_pause` WAF branch calls `solve_amazon_waf` once via `run_in_executor` under `asyncio.timeout(120)`; new `_inject_waf_token(tab, solution)` method with quote/backslash/newline rejection + `json.dumps()` escaping before `document.cookie` injection
- `tests/test_captcha_plugin.py` - rewrote `test_amazon_waf_detected_falls_to_manual_pause` to assert the solve-success path (call + inject, no pause); added `test_amazon_waf_solver_unavailable_falls_to_manual_pause`, `test_amazon_waf_solve_raises_falls_to_manual_pause`, `test_amazon_waf_gokuprops_decode_failure_falls_to_manual_pause`, `test_amazon_waf_injection_failure_falls_to_manual_pause`; inverted `test_amazon_source_does_not_call_solve_amazon_waf` -> `test_amazon_source_calls_solve_amazon_waf`; added `test_amazon_waf_inject_rejects_quote_backslash_newline` + `test_amazon_waf_inject_uses_json_dumps`

## Decisions Made
- Injection mechanism chosen: `document.cookie` set via `tab.evaluate()` (JS-eval path), not CDP `tab.send(cdp_storage.set_cookies(...))`. The plan explicitly permits either as best-effort since the exact 2captcha AmazonTask payload shape is undocumented (RESEARCH.md Assumption A1); JS-eval avoids introducing new CDP imports into the plugin and keeps the diff minimal. Live-challenge acceptance of this exact mechanism stays operator debt per the milestone rule.
- No redundant `can_solve()` re-check was added inside the WAF branch itself -- the function's existing top-level gate (`solver is None or not solver.can_solve()`) already satisfies D-08's "solver-unavailable -> manual pause, solve_amazon_waf NOT called" requirement before the WAF probe ever runs, exactly mirroring how the `solve_recaptcha` branch has no local re-check either.
- The blocking `solve_amazon_waf` call is wrapped in a `lambda: solver.solve_amazon_waf(...)` passed to `run_in_executor`, rather than passing the bound method directly (as `solve_recaptcha` does). This keeps a literal `solve_amazon_waf(` call-site string in the source so structural/source-grep verification (the inverted `test_amazon_source_calls_solve_amazon_waf` guard) checks the real call, not an incidental docstring match.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- BF-01 is code-complete and CI-green: `pytest tests/test_captcha_plugin.py -x -q` (29 passed), `pytest tests/ -q -k "cart_retry or retry or captcha or plugin or relaunch or models or orchestrator"` (361 passed), full suite `pytest -q` (822 passed, 2 skipped -- up from the 816-passed/2-skipped baseline after 30-01, +6 net new tests as expected).
- Live AWS-WAF challenge acceptance within the ~30s gokuProps freshness window remains operator debt per REQUIREMENTS.md Out-of-Scope -- the mocked unit tests assert wiring correctness, not live payload acceptance.
- Plan 30-04 (`depends_on: ["30-01", "30-02"]`) can now proceed -- it builds on this plan's Amazon plugin changes.
- Remaining Phase 30 work (BF-03 per-plugin `login() -> bool` conversions, ABC contract change, BestBuy WAF/marker parity) is scoped to plans 30-03, 30-04, 30-05, 30-06 and was not touched here.

## Self-Check: PASSED

- FOUND: plugins/shopbot_plugin_amazon.py
- FOUND: tests/test_captcha_plugin.py
- FOUND: .planning/phases/30-breakfix-hardening/30-02-SUMMARY.md
- FOUND: e7115ca (Task 1 commit)
- FOUND: 258d6d0 (Task 2 commit)
- pytest tests/test_captcha_plugin.py -x -q: 29 passed
- pytest tests/ -q -k "cart_retry or retry or captcha or plugin or relaunch or models or orchestrator": 361 passed
- pytest -q (full suite): 822 passed, 2 skipped

---
*Phase: 30-breakfix-hardening*
*Completed: 2026-07-02*
