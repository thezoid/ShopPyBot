---
phase: 24-health-surface-server-safety
plan: "03"
subsystem: api
tags: [health, botservice, json, fastapi, monitoring]

requires:
  - phase: 24-health-surface-server-safety/24-01
    provides: HealthRegistry with get_snapshot() returning JSON-safe per-plugin dicts

provides:
  - BotService.get_status() returning locked {running, uptime_secs, plugins} shape
  - BotService._health_registry (HealthRegistry) created in __init__, safe before start()
  - BotService._start_time wired into start() and run() lifecycle
  - async_main called with health_registry=self._health_registry at both call sites
  - JSON-serializable guarantee on get_status() output
  - /status endpoint richer-shape contract test

affects:
  - 24-04 (orchestrator wires health_registry it receives into supervise/run_plugin)
  - 24-05 (CLI status subcommand reads BotService.get_status())
  - web/routes/api.py (get_status shape now richer; flows through unchanged)

tech-stack:
  added: []
  patterns:
    - "HealthRegistry instance owned by BotService.__init__; single source of truth for plugin health"
    - "_start_time set on start/run entry, cleared in finally blocks; uptime computed in get_status"
    - "get_status() is cheap/non-blocking: in-memory reads only, safe from FastAPI request handlers"

key-files:
  created: []
  modified:
    - core/service.py
    - tests/test_service.py
    - tests/test_web_controls.py

key-decisions:
  - "HealthRegistry created in __init__ (not start()) so get_status() is always callable without a running bot"
  - "uptime_secs is 0.0 when _start_time is None or _running is False; no negative or stale values"
  - "health_registry passed as keyword arg with default None to async_main; existing call sites unaffected"
  - "Existing lifecycle test noops updated to accept **kwargs to handle new health_registry keyword arg"

patterns-established:
  - "BotService is the stable API seam: all health reads go through get_status(), never direct registry access from web/CLI"
  - "_start_time reset in finally blocks on both start() and run() paths"

requirements-completed: [REL-07]

duration: 8min
completed: 2026-06-12
---

# Phase 24 Plan 03: Health Surface - BotService get_status() Expansion Summary

**BotService.get_status() now returns a locked {running, uptime_secs, plugins} shape backed by a HealthRegistry instance wired into async_main at both call sites**

## Performance

- **Duration:** 8 min
- **Started:** 2026-06-12T16:31:00Z
- **Completed:** 2026-06-12T16:37:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Expanded get_status() from `{"running": bool}` to the full REL-07 locked shape including uptime_secs and plugins snapshot
- Wired HealthRegistry instance into both async_main call sites (start() daemon thread and run() blocking path)
- Added _start_time lifecycle tracking with cleanup in finally blocks
- Full suite: 742 passed, 2 skipped, 0 failures (4 new tests added)

## Task Commits

1. **Task 1: Expand get_status() + _start_time + HealthRegistry + async_main wiring** - `04a3627` (feat)
2. **Task 2: /status richer-shape JSON-serializable assertion** - `f9c4d49` (test)

**Plan metadata:** (pending final commit)

## Files Created/Modified

- `core/service.py` - Added `import time`, `import HealthRegistry`; `_start_time` and `_health_registry` fields; expanded `get_status()`; `_start_time` lifecycle in start/run; `health_registry=` kwarg at both async_main calls
- `tests/test_service.py` - Added `test_get_status_shape_before_start`, `test_get_status_shape_with_registry`, `test_get_status_is_json_serializable`; updated existing noops to `**kwargs`
- `tests/test_web_controls.py` - Added `test_status_endpoint_richer_shape` verifying uptime_secs and plugins flow through /api/status unchanged

## Decisions Made

- HealthRegistry created in `__init__` (not `start()`) so `get_status()` is safe before the bot starts - matches Pitfall 5 from RESEARCH
- `health_registry=None` default on `async_main` (Plan 04 change) means both call sites can pass the kwarg without breaking any other caller
- Existing lifecycle test noops `_noop(cfg, cvv)` updated to `_noop(cfg, cvv, **kwargs)` to accept the new keyword argument (Rule 1 auto-fix)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated existing lifecycle test noops to accept **kwargs**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** Existing tests `_noop(cfg, cvv)`, `_mock_main(cfg, cvv)`, `_fake_async_main(cfg, cvv)` would raise `TypeError` when called with the new `health_registry=` keyword arg
- **Fix:** Added `**kwargs` to all three noop/mock signatures in test_service.py
- **Files modified:** tests/test_service.py
- **Verification:** All 16 test_service.py tests pass
- **Committed in:** 04a3627 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug prevention)
**Impact on plan:** Required to prevent TypeError on existing tests after adding health_registry kwarg. No scope creep.

## Issues Encountered

None - implementation proceeded as specified in PATTERNS.md.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 04 can now accept `health_registry=None` in `async_main` signature and thread it through `supervise`/`run_plugin`
- Plan 05 (CLI status) can call `BotService().get_status()` and receive the full shape
- /status endpoint unchanged; richer shape flows through JSONResponse without modification

## Self-Check: PASSED

- core/service.py exists with _health_registry, _start_time, expanded get_status()
- tests/test_service.py: 16 tests pass
- tests/test_web_controls.py: 5 tests pass
- Full suite: 742 passed, 2 skipped, 0 failures
- Verification command output: `{"running": false, "uptime_secs": 0.0, "plugins": {}}`

---
*Phase: 24-health-surface-server-safety*
*Completed: 2026-06-12*
