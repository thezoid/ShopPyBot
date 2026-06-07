---
phase: 10-optional-web-ui
plan: "02"
subsystem: web-ui
tags: [fastapi, web, optional-extra, api-routes, csrf, botservice, run_in_executor]
dependency_graph:
  requires:
    - phase: 10-01
      provides: [web/__init__.py create_app, web/security.py check_origin, web/log_reader.py read_recent_logs, web/routes/api.py router stub]
  provides:
    - "web/routes/api.py: filled with items + bot-control + status + logs routes over BotService"
  affects: [10-03, 10-04, 10-05]
tech_stack:
  added: []
  patterns: [run_in_executor for blocking svc.stop, origin-guard on all mutating routes, bool coercion on 5-tuple fields]
key_files:
  created: []
  modified:
    - web/routes/api.py
    - tests/test_web_controls.py
key_decisions:
  - "bot_stop uses asyncio.get_event_loop().run_in_executor(None, svc.stop) -- svc.stop() blocks 15s on thread.join; dispatching off event loop keeps uvicorn responsive (T-10-08)"
  - "svc.start() called with zero positional/keyword args (no CVV) -- web scope locked decision"
  - "bot_start guards already-running; bot_stop guards not-running; errors return {status:error, detail:...} at 200"
  - "auto_buy and purchased coerced via bool() when serializing 5-tuples to JSON"
  - "test_bot_stop_calls_svc_stop updated to set running=True before POST -- required to reach run_in_executor path past the not-running guard"
patterns-established:
  - "run_in_executor pattern: await asyncio.get_event_loop().run_in_executor(None, blocking_fn) for any sync call that blocks > ~100ms in an async route"
  - "State-guard pattern: read svc.get_status() at top of mutating route handlers to return early error before dispatching work"
requirements-completed: [GUI-02, GUI-04]
duration: 6min
completed: "2026-06-04"
---

# Phase 10 Plan 02: Items + Bot-Control + Status/Logs Routes Summary

**Seven FastAPI route handlers in web/routes/api.py thin-adapting BotService with CSRF origin-checks, running-state guards, and event-loop-safe async stop via run_in_executor**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-06-04T21:49:14Z
- **Completed:** 2026-06-04T21:55:31Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Items GET/POST/DELETE routes serialize BotService 5-tuples with bool() coercion; all mutating routes origin-checked
- bot_start/bot_stop routes add running-state guards and dispatch blocking stop() off the event loop via run_in_executor
- MOD-02 AST guard passes: no forbidden model/orchestrator imports in web/ package

## Task Commits

1. **Task 1+2: Items + bot-control + status + logs routes** - `c2b00dd` (feat)
2. **Task 2 test: bot_stop test aligned with running-state guard** - `8c2523a` (test)

## Files Created/Modified

- `web/routes/api.py` - Completed: bool coercion on items, asyncio import, run_in_executor for bot_stop, running-state guards for start/stop
- `tests/test_web_controls.py` - Updated test_bot_stop_calls_svc_stop to set running=True before POST

## Decisions Made

- bot_stop dispatches via `asyncio.get_event_loop().run_in_executor(None, svc.stop)` to prevent uvicorn event-loop stall (T-10-08 mitigated)
- svc.start() called with zero args (no CVV, no keyword) per locked web-scope decision
- Running-state guards return `{"status":"error","detail":"..."}` at HTTP 200 (not 4xx) for JS-friendly API consistency

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_bot_stop_calls_svc_stop incompatible with not-running guard**
- **Found during:** Task 2 (bot control routes)
- **Issue:** Test fixture had `get_status.return_value = {"running": False}` but the plan specified a guard returning early error when not running; test would never reach the svc.stop() call
- **Fix:** Added `mock_svc.get_status.return_value = {"running": True}` at the top of the test function, before the POST request
- **Files modified:** tests/test_web_controls.py
- **Verification:** `pytest tests/test_web_controls.py -v` exits 0; all 4 controls tests pass
- **Committed in:** 8c2523a

---

**Total deviations:** 1 auto-fixed (1 bug: test incompatible with guard logic)
**Impact on plan:** Test update required for correctness; no scope creep.

## Issues Encountered

- `test_web_add_item_parity` fails with `ModuleNotFoundError: No module named 'keyring'` -- pre-existing environment issue unrelated to this plan; `keyring` package not installed in this Python environment. Out of scope.
- `test_non_local_host_warning` same pre-existing keyring chain failure.

## Self-Check

Files exist:
- web/routes/api.py: FOUND (modified)
- tests/test_web_controls.py: FOUND (modified)

Commits exist:
- c2b00dd: FOUND (feat)
- 8c2523a: FOUND (test)

Tests: 8/9 passing (test_web_items.py + test_web_controls.py + test_web_mod02.py); 1 pre-existing failure (keyring not installed)

## Self-Check: PASSED

## Next Phase Readiness

- All seven API routes operational: GET/POST/DELETE /items, POST /bot/start, POST /bot/stop, GET /status, GET /logs
- MOD-02 guard green (no direct model/orchestrator imports in web/)
- SC2 parity test blocked by keyring env issue (pre-existing); route logic is correct per unit tests
- Plan 03 (dashboard JS polling integration) can proceed

---
*Phase: 10-optional-web-ui*
*Completed: 2026-06-04*
