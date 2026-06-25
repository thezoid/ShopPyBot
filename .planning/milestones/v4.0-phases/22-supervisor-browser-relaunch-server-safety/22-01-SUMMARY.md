---
phase: 22-supervisor-browser-relaunch-server-safety
plan: 01
subsystem: plugin-abc
tags: [nodriver, asyncio, browser-relaunch, stealth, tdd]

requires:
  - phase: 21-per-step-timeouts-unified-retry-cart-retry
    provides: RetryPolicy / compute_delay in core/retry.py used by supervise() (Plan 22-03)

provides:
  - Concrete async relaunch() method on RetailerPlugin ABC (teardown->setup->restore_session->login)
  - Concrete async restore_session() no-op default returning False (Phase 23 stub contract)
  - 6 tests covering REL-03: sequence order, login skip, teardown error swallow, stealth re-injection gate

affects:
  - 22-02 (supervisor plan imports plugin.relaunch())
  - 22-03 (supervise() calls plugin.relaunch() on browser-death)
  - 23 (replaces restore_session() stub with Fernet cookie restore)

tech-stack:
  added: []
  patterns:
    - "Additive concrete ABC method: docstring cites PLUGIN_API_VERSION stays 2 + phase note"
    - "TDD RED->GREEN with async side_effect closures on AsyncMock"
    - "teardown error swallow: try/except Exception + log WARNING using exc.__class__.__name__"

key-files:
  created:
    - tests/test_relaunch.py
  modified:
    - core/plugin_base.py
    - tests/test_plugin_base.py

key-decisions:
  - "proxy re-assignment (assign_proxy) is the supervisor's responsibility before calling relaunch(); relaunch() takes no registry reference (Open Question 1 resolution from RESEARCH)"
  - "setup() is the single stealth injection point; relaunch() never calls apply_stealth() directly"
  - "teardown errors are swallowed with WARNING log; browser may already be dead so teardown failure must not abort relaunch"
  - "AsyncMock side_effect must be async def functions (not lambdas returning coroutines) when the side effect is itself async"

requirements-completed: [REL-03]

duration: 8min
completed: 2026-06-12
---

# Phase 22 Plan 01: Supervisor Browser Relaunch Server Safety Summary

**Concrete relaunch() ABC method on RetailerPlugin with fixed teardown->setup->restore_session->login sequence and no-op restore_session() stub for Phase 23 Fernet cookie restore contract**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-06-12T04:35:26Z
- **Completed:** 2026-06-12T04:43:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added `relaunch()` as a concrete async method on the RetailerPlugin ABC: teardown errors are swallowed (browser may already be dead), `setup()` is called to re-inject stealth (CDP scripts are session-scoped per nodriver 0.50.3 verification), then `restore_session()` gates the `login()` call.
- Added `restore_session()` as a no-op concrete async method returning False; docstring marks Phase 23 (REL-04) as the replacement owner.
- 6 tests: sequence-order assertion, login-skip when restore returns True, teardown-error-swallowed, setup-awaited-once (stealth gate), restore_session returns False, PLUGIN_API_VERSION stays 2. Full suite 676 passed.

## Task Commits

1. **Task 1: Wave 0 RED tests** - `0b9d2d6` (test)
2. **Task 2: Implement relaunch() + restore_session()** - `6b4e88b` (feat)

## Files Created/Modified

- `core/plugin_base.py` - Added relaunch() and restore_session() concrete methods after teardown()
- `tests/test_relaunch.py` - Four new relaunch tests (sequence order, login skip, teardown error, stealth gate)
- `tests/test_plugin_base.py` - Added test_restore_session_noop_returns_false and test_plugin_api_version_unchanged

## Decisions Made

- Proxy re-assignment is the supervisor's responsibility before calling `relaunch()`; `relaunch()` takes no registry reference. This keeps the method self-contained and avoids circular dependencies between plugin_base and registry.
- `setup()` is the single stealth injection point. Calling `apply_stealth()` directly in `relaunch()` would duplicate injection logic and break single-responsibility.
- `exc.__class__.__name__` used in all log calls (never `str(exc)`) to prevent credential leakage in error text.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed AsyncMock side_effect closures in test helper**

- **Found during:** Task 2 verification (first GREEN run attempt)
- **Issue:** `_make_recording_plugin()` used `side_effect=lambda: _record("name")` where `_record` is an `async def`. The lambda returned a coroutine object that was never awaited, so `call_order` was never populated. Test failed with AssertionError on the order check.
- **Fix:** Replaced each lambda with a named `async def` side-effect function that appends to `call_order` directly and returns the appropriate value.
- **Files modified:** `tests/test_relaunch.py`
- **Verification:** All 6 new tests passed GREEN; full suite 676 passed.
- **Committed in:** `6b4e88b` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Minor test-helper fix; no production code change. No scope creep.

## Issues Encountered

None beyond the AsyncMock side_effect fix documented above.

## Known Stubs

`restore_session()` returns False unconditionally. This is an intentional Phase 22 stub. Phase 23 (REL-04) replaces it with Fernet cookie restore. The stub is the plan's deliverable, not a gap.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes introduced. relaunch() and restore_session() are in-process ABC methods only.

## Next Phase Readiness

- `relaunch()` is ready for `supervise()` to call (Plan 22-03).
- `restore_session()` stub fulfills the Phase 23 cross-phase contract.
- Full suite green; no regressions.

## Self-Check: PASSED

- `core/plugin_base.py` exists with `relaunch` and `restore_session`
- `tests/test_relaunch.py` exists with 4 tests
- `tests/test_plugin_base.py` contains test_restore_session_noop_returns_false and test_plugin_api_version_unchanged
- Commits `0b9d2d6` and `6b4e88b` confirmed in git log

---
*Phase: 22-supervisor-browser-relaunch-server-safety*
*Completed: 2026-06-12*
