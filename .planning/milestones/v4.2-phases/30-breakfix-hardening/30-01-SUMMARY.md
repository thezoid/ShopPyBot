---
phase: 30-breakfix-hardening
plan: 01
subsystem: checkout-retry
tags: [sqlite, asyncio, retry-guard, idempotency, notifications, orchestrator]

# Dependency graph
requires:
  - phase: 21-per-step-timeouts-unified-retry-cart-retry
    provides: RetryPolicy/with_retry, _AlreadyConfirmed sentinel pattern, _pre_attempt_check/_try_auto_buy cart-retry wrapper
provides:
  - "place_order_attempted_at SQLite column + get_place_order_marker_sync/mark_place_order_attempted_sync accessors"
  - "_PossiblyPlaced sentinel exception aborting cart-retry when a place-order click may have fired but no order_id was confirmed"
  - "possibly_placed operator alert (fires once, orchestrator layer)"
  - "D-15 login-stage retry suppression via the should_retry predicate (login()/auto_buy() invoked exactly once on a verified-failed login)"
  - "login_failed operator alert (fires once, orchestrator layer)"
affects: [30-02, 30-03, 30-05, 30-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Sentinel-exception-driven retry abort (mirrors existing _AlreadyConfirmed): exception class -> raise in on_attempt hook -> catch in _try_auto_buy"
    - "should_retry predicate as the retry-suppression mechanism (not a post-hoc check) -- required so a non-retryable condition prevents re-invocation, not just re-alerts after the fact"

key-files:
  created: []
  modified:
    - models.py
    - core/orchestrator.py
    - tests/test_models.py
    - tests/test_orchestrator.py
    - tests/test_cart_retry.py

key-decisions:
  - "place_order_attempted_at is a new dedicated TEXT column, not an overload of checkout_attempts or the CONFIRMED-<ts> sentinel (D-02)"
  - "_PossiblyPlaced check sits in _pre_attempt_check AFTER the existing order_id/purchased branches so a confirmed sentinel order_id always short-circuits first (Pitfall 6 precedence)"
  - "D-15 loop suppression implemented via the should_retry closure (lambda r: not r[0] and plugin._checkout_stage != \"login\"), not a new exception or hand-rolled loop -- lowest-risk mechanism per research Open Question 2"
  - "possibly_placed and login_failed alerts both fire from the orchestrator layer only (plugins have no dispatcher reference) via the existing _build_event + dispatcher.notify pattern"

patterns-established:
  - "Sentinel-exception retry-abort: _PossiblyPlaced sibling to _AlreadyConfirmed"
  - "should_retry predicate inspects plugin._checkout_stage to suppress retry on a specific failure class without a new exception or loop"

requirements-completed: [BF-02, BF-03]

# Metrics
duration: 22min
completed: 2026-07-02
---

# Phase 30 Plan 01: Place-Order Double-Buy Guard + Login-Failure Short-Circuit Summary

**A SQLite write-ahead marker plus a `_PossiblyPlaced` sentinel exception makes the place-order stage non-retryable once clicked, and a `should_retry` predicate change makes a verified-failed login non-retryable inside the same `with_retry` loop -- both routed through the existing orchestrator-layer alert pattern (`possibly_placed`, `login_failed`).**

## Performance

- **Duration:** 22 min
- **Started:** 2026-07-02T15:48:00Z
- **Completed:** 2026-07-02T16:09:47Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments
- BF-02 (HIGH): a place-order-stage timeout can no longer cause a placed-but-unconfirmed double-buy on retry -- the DB marker + `_PossiblyPlaced` guard closes the milestone's one HIGH item.
- An attempted-but-unconfirmed order now fires exactly one `possibly_placed` operator alert and is skipped on future cycles instead of being silently dropped or re-attempted.
- BF-03: a verified-failed login (`plugin._checkout_stage == "login"`) short-circuits cart-retry INSIDE the retry loop itself (proven by a call-counter assertion, not just an alert) and fires exactly one `login_failed` alert.
- No new retry loop was introduced anywhere; `core/retry.py` (`RetryPolicy`/`with_retry`) is reused unmodified (D-05), and the AST guard (`test_no_retry_loops.py`) stays green.

## Task Commits

Each task was committed atomically (TDD RED -> GREEN per task):

1. **Task 1: Add BF-02 place-order marker column + accessors to models.py**
   - `ea9f414` (test) - failing round-trip/missing-link/idempotent-migration tests
   - `3942c5a` (feat) - idempotent column + `get_place_order_marker_sync`/`mark_place_order_attempted_sync`
2. **Task 2: Add `_PossiblyPlaced` guard + `possibly_placed` alert to the orchestrator (BF-02)**
   - `3d5e3e7` (test) - failing retry-abort, precedence, and alert-fires-once tests
   - `cbe013c` (feat) - `_PossiblyPlaced` exception, `_pre_attempt_check` branch, `_try_auto_buy` except clause + alert
3. **Task 3: Add BF-03 login-failure short-circuit + `login_failed` alert (D-15)**
   - `81c0c88` (test) - failing call-counter loop-suppression test + non-login regression guard
   - `e2ad0f9` (feat) - `should_retry` predicate extension + `login_failed` alert branch

**Plan metadata:** (this commit)

## Files Created/Modified
- `models.py` - `place_order_attempted_at` column (idempotent ALTER) + `get_place_order_marker_sync`/`mark_place_order_attempted_sync` accessors
- `core/orchestrator.py` - `_PossiblyPlaced` exception, `_pre_attempt_check` marker branch, `_try_auto_buy` except clause + `possibly_placed` alert, `should_retry` predicate extension + `login_failed` alert branch
- `tests/test_models.py` - marker column/round-trip/legacy-migration tests
- `tests/test_orchestrator.py` - `possibly_placed` alert-fires-once test; marker-patch additions to 7 pre-existing `_try_auto_buy`/`_check_and_buy` tests
- `tests/test_cart_retry.py` - `test_possibly_placed_aborts_retry`, precedence test, `test_login_failure_short_circuits_retry_and_alerts_once`, non-login regression test; marker-patch additions to 8 pre-existing tests

## Decisions Made
- D-02 marker mechanism: dedicated `place_order_attempted_at TEXT` column, not an overload of `checkout_attempts` or the confirmation sentinel (locked in CONTEXT.md, implemented as specified).
- D-15 mechanism selection: the `should_retry` closure extension (Research Open Question 2, Option A) was used over a new sentinel exception, since `plugin._checkout_stage` already crosses the plugin/orchestrator boundary safely and needed no new exception class -- smaller diff, reuses existing telemetry.
- Precedence for `_PossiblyPlaced` was placed after both existing `_AlreadyConfirmed` branches (order_id-present, legacy-purchased) so a confirmation sentinel never gets mis-read as "needs manual review" (Pitfall 6).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Patched `get_place_order_marker_sync` across 15 pre-existing cart-retry/orchestrator tests**
- **Found during:** Task 2 (running `pytest tests/test_cart_retry.py tests/test_orchestrator.py` after adding the `_pre_attempt_check` marker read)
- **Issue:** Adding the new `get_place_order_marker_sync` DB read to `_pre_attempt_check` (between the `purchased` branch and the `increment_checkout_attempts_sync` fallthrough) meant every pre-existing test that exercises the `(False, None)` order-state path now hit an unmocked, unpatched function -- against a real (uninitialized) SQLite DB in most cases, causing `sqlite3.OperationalError: no such table: items`.
- **Fix:** Added `patch("core.orchestrator.get_place_order_marker_sync", return_value=None)` alongside the existing `get_item_order_state_sync` patch in each affected test (8 in `tests/test_cart_retry.py`, 7 in `tests/test_orchestrator.py`). Tests where `get_item_order_state_sync` already returns a non-`(False, None)` tuple (i.e. `_AlreadyConfirmed` fires first) were left unpatched since the marker read is never reached for those cases (verified by `mock_marker.assert_not_called()` in the new precedence test).
- **Files modified:** `tests/test_cart_retry.py`, `tests/test_orchestrator.py`
- **Verification:** Full suite green (816 passed, 2 skipped) after the fix; `tests/test_cart_retry.py tests/test_orchestrator.py` alone: 49 passed.
- **Committed in:** `cbe013c` (Task 2 commit, same commit as the feature since the tests were pre-existing files being patched, not new failing-test commits)

---

**Total deviations:** 1 auto-fixed (1 bug fix, in-scope collateral from Task 2's necessary DB-read addition)
**Impact on plan:** Necessary to keep the existing test suite green after extending `_pre_attempt_check`; no scope creep -- every patched test was a direct, in-scope consequence of the plan's own Task 2 change.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- BF-02 and BF-03 are both code-complete and CI-green (`pytest tests/test_models.py tests/test_cart_retry.py tests/test_orchestrator.py tests/test_no_retry_loops.py -x -q`: 69 passed; full suite: 816 passed, 2 skipped).
- Live-environment proof of the double-buy edge and the login-failure edge remains operator debt per the v4.2 milestone rule (code-complete + CI-green is "done"; live-UAT is a separate deferred checklist item).
- `core/orchestrator.py`'s retry-guard/alert surface is now closed for this phase -- per the plan objective, no later Phase 30 plan needs to touch `_pre_attempt_check`/`_try_auto_buy` again.
- BF-01 (Amazon WAF auto-solve wiring) and any remaining BF-03 plugin-level `login()` conversions are scoped to other plans in this phase (per ROADMAP wave structure) and were not touched here.

---
*Phase: 30-breakfix-hardening*
*Completed: 2026-07-02*
