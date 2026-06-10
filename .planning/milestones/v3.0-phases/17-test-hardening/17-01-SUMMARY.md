---
phase: 17-test-hardening
plan: 01
subsystem: testing
tags: [pytest, pytest-asyncio, proxy, nodriver, cdp, pydantic]

requires:
  - phase: 16-something
    provides: production code under test (config_schema.py, stealth.py, registry.py)

provides:
  - PX-01: ProxyConfig URL validator rejection test (config_schema.py:256-257)
  - PX-02: _on_request_paused CDP fetch handler task tracking test (stealth.py:303-307)
  - PX-03: ProxyPool empty-pool and pool-level methods test (stealth.py:222/231/243/257)
  - PX-04: plugins_for_items dedup + no-match routing test (registry.py:120/129-136)
  - PX-05: setup_for_items setup() failure isolation test (registry.py:158-159)
  - PX-06: teardown_all error isolation test (registry.py:169-170)

affects: [17-test-hardening, STAB-03]

tech-stack:
  added: []
  patterns:
    - "Use SimpleNamespace for lightweight CDP event fakes (no nodriver dep in test)"
    - "Two asyncio.sleep(0) ticks needed: first runs the task, second fires the done callback"
    - "nodriver CDP functions are generator factories not classes; verify via __qualname__"
    - "Swap _live_tasks state before/after handler invocation to assert add/discard lifecycle"

key-files:
  created: []
  modified:
    - tests/test_proxy_config.py
    - tests/test_stealth.py
    - tests/test_registry.py

key-decisions:
  - "Verify fetch.continue_request call by __qualname__ not isinstance (nodriver CDPs are generator factories)"
  - "Two asyncio.sleep(0) yields required to observe task completion and done-callback discard"
  - "Inject _all_plugins directly on registry instance to avoid plugin discovery overhead in isolation tests"

patterns-established:
  - "CDP handler capture: use tab.add_handler.call_args_list and match on event_type identity"
  - "Generator-based CDP assertion: check arg.__qualname__ not isinstance"
  - "Registry isolation test: assign _all_plugins directly, patch core.registry.writeLog with list capture"

requirements-completed: [STAB-03]

duration: 15min
completed: 2026-06-10
---

# Phase 17 Plan 01: Proxy Coverage Tests (PX-01..PX-06) Summary

**Six deterministic proxy-surface tests covering URL validation, CDP fetch-handler task lifecycle, ProxyPool empty-pool edges, and registry routing/lifecycle isolation -- bringing stealth.py to 99% and config_schema.py to 96% coverage on the new lines**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-06-10T01:22:00Z
- **Completed:** 2026-06-10T01:37:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added PX-01..PX-06 as named tests exactly matching the RESEARCH.md spec; all 6 pass
- Full suite rose from 529 to 535 passed (baseline 529, +6) with 2 skipped unchanged
- Targeted previously-uncovered lines now executed: config_schema.py:256-257, stealth.py:222/231/243/257/303-307, registry.py:120/129-136/158-159/169-170

## Task Commits

1. **Task 1: PX-01 proxy URL validator + PX-02 fetch-handler task tracking + PX-03 pool-level methods** - `178d37e` (test)
2. **Task 2: PX-04/PX-05/PX-06 registry routing dedup + setup/teardown isolation** - `1722ab8` (test)

## Files Created/Modified

- `tests/test_proxy_config.py` - Added test_proxyconfig_rejects_invalid_proxy_url (PX-01)
- `tests/test_stealth.py` - Added test_setup_proxy_auth_request_paused_continues (PX-02) and test_proxypool_empty_and_pool_level_methods (PX-03); added `import asyncio, SimpleNamespace, core.stealth as stealth_module`
- `tests/test_registry.py` - Added test_plugins_for_items_dedups_and_skips_unmatched (PX-04), test_setup_for_items_skips_plugin_on_setup_error (PX-05), test_teardown_all_logs_and_continues_on_error (PX-06)

## Decisions Made

- Verified `fetch.continue_request` call via `arg.__qualname__ == "continue_request"` rather than `isinstance` because nodriver CDP commands are generator factory functions, not classes -- `isinstance` raises `TypeError`.
- Used two `asyncio.sleep(0)` yields in PX-02: the first tick runs the created task, the second fires the done callback so `_live_tasks.discard` executes. One tick is not sufficient.
- For PX-04/PX-05/PX-06 injected `_all_plugins` directly onto the registry instance after constructing with an empty `tmp_path`, avoiding plugin-file scaffolding while still exercising the real routing and lifecycle code paths.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] PX-02 initial approach patched set.add -- not allowed on built-in types**
- **Found during:** Task 1 (test_setup_proxy_auth_request_paused_continues)
- **Issue:** `stealth_module._live_tasks.add = _tracking_add` raises `AttributeError: 'set' object attribute 'add' is read-only`
- **Fix:** Switched to snapshot-diff strategy: record `len(_live_tasks)` before and after handler invocation, then grab the added task via `next(iter(_live_tasks))`; await two event loop ticks for task completion and done-callback discard
- **Files modified:** tests/test_stealth.py
- **Verification:** Test passes; _live_tasks is empty after two asyncio.sleep(0) yields
- **Committed in:** 178d37e (Task 1 commit)

**2. [Rule 1 - Bug] PX-02 isinstance(arg, fetch.continue_request) raises TypeError**
- **Found during:** Task 1 (test_setup_proxy_auth_request_paused_continues)
- **Issue:** `fetch.continue_request` is a generator factory function, not a class; `isinstance` second arg must be a type
- **Fix:** Asserted `arg.__qualname__ == "continue_request"` instead of isinstance
- **Files modified:** tests/test_stealth.py
- **Verification:** Test passes; qualname correctly identifies the generator source
- **Committed in:** 178d37e (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 implementation bugs discovered during test writing)
**Impact on plan:** Both fixes necessary for test correctness. No scope creep; production code unchanged.

## Issues Encountered

- `asyncio.create_task` done callbacks require two event loop ticks (not one) to fire after the task completes in pytest-asyncio auto mode; documented as a reusable pattern.

## Threat Flags

None -- test-only additions, no production code modified, no new attack surface.

## Known Stubs

None.

## Self-Check: PASSED

- tests/test_proxy_config.py: FOUND
- tests/test_stealth.py: FOUND
- tests/test_registry.py: FOUND
- Commit 178d37e: FOUND
- Commit 1722ab8: FOUND

## Next Phase Readiness

- PX-01..PX-06 complete; STAB-03 criterion 1 mapped to named passing tests
- Ready for 17-02 (CAPTCHA tests CP-01..CP-05) and 17-03/17-04

---
*Phase: 17-test-hardening*
*Completed: 2026-06-10*
