---
phase: 22-supervisor-browser-relaunch-server-safety
plan: "03"
subsystem: orchestrator
tags: [supervisor, reliability, taskgroup, crash-isolation, failure-budget, browser-relaunch]
dependency_graph:
  requires: [22-01, 22-02]
  provides: [supervise-wrapper, browser-dead-detection, failure-budget-park, async-main-wiring]
  affects: [core/orchestrator.py, tests/test_supervisor.py]
tech_stack:
  added: []
  patterns:
    - supervise() wrapper coroutine absorbing Exception before TaskGroup boundary
    - failure-budget deque with monotonic rolling window eviction
    - browser-dead exception classification helper
    - compute_delay reuse from core/retry.py (REL-08 single source)
key_files:
  created:
    - tests/test_supervisor.py
  modified:
    - core/orchestrator.py
decisions:
  - supervise() catches Exception (not BaseException) so CancelledError propagates for clean shutdown
  - _park_plugin() extracted as a small helper to keep supervise() under 30 lines
  - registry passed as optional param to supervise(); assign_proxy called in supervisor before plugin.relaunch()
  - _instant_sleep_ctx() contextmanager replaces core.orchestrator.asyncio.sleep with real asyncio.sleep(0) in tests to avoid AsyncMock non-yielding stall
  - _REAL_SLEEP captured at module import time to avoid recursion when _instant_sleep_ctx replaces asyncio.sleep
metrics:
  duration: "~21 minutes"
  completed: "2026-06-12"
  tasks: 3
  files: 2
---

# Phase 22 Plan 03: Supervisor Wrapper + Browser Relaunch Wiring Summary

Keystone plan: `supervise()` coroutine wraps `run_plugin` in a restart loop and absorbs all `Exception` subclasses before the `asyncio.TaskGroup` boundary. One plugin crash can never cancel siblings (REL-01). Browser-death triggers proxy re-assignment and `plugin.relaunch()`. A rolling 600s failure budget parks crash-looping plugins and notifies the operator (REL-02). Backoff reuses `compute_delay` from `core/retry.py` (REL-08). `async_main` now routes every plugin through `supervise()`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Wave 0 -- failing supervisor tests (RED) | 1869679 | tests/test_supervisor.py |
| 2 | Implement _is_browser_dead_exc + supervise() | 11464e2 | core/orchestrator.py, tests/test_supervisor.py |
| 3 | Wire async_main TaskGroup to supervise() | 056bbf9 | core/orchestrator.py |

## What Was Built

### core/orchestrator.py additions

**`_FAILURE_WINDOW_SECS = 600`** -- module constant for rolling budget window.

**`_is_browser_dead_exc(exc) -> bool`** -- classifies exception as browser-death:
- `ConnectionError`, `OSError` -> True
- `RuntimeError` with "WebSocket" in message -> True
- `websockets.exceptions.ConnectionClosed` (optional import) -> True
- All others -> False

**`_park_plugin(plugin, n_budget, dispatcher)`** -- extracted helper: logs park ERROR + dispatches `NotificationEvent(action="plugin_parked")` via dispatcher.

**`supervise(plugin, write_queue, poll_interval, dispatcher, cfg, registry=None)`** -- wraps `run_plugin` in a restart loop:
- Reads `cfg.checkout.alert_on_errors` (default 3) for budget N
- Constructs `RetryPolicy` from checkout backoff fields
- `while True`: calls `run_plugin`; on `asyncio.CancelledError` re-raises (clean shutdown); on `Exception`: records timestamp in `deque`, evicts entries older than 600s, logs crash
- If `len(failure_times) >= n_budget`: calls `_park_plugin` then `return` (clean task exit)
- If `_is_browser_dead_exc(exc)`: calls `registry.assign_proxy(plugin)` then `await plugin.relaunch()` (error logged as WARNING, not fatal)
- `await asyncio.sleep(compute_delay(attempt, policy))` before next iteration

**`async_main` change** -- line 617: `run_plugin(...)` replaced with `supervise(..., cfg=cfg, registry=registry)`.

### tests/test_supervisor.py (new, 6 tests)

| Test | Coverage |
|------|----------|
| `test_crash_one_plugin_others_survive` | REL-01: plugin A parks, plugin B keeps running |
| `test_supervise_propagates_cancelled` | REL-01: CancelledError exits supervise() |
| `test_failure_budget_parks_plugin` | REL-02: 3 failures -> park + dispatcher notified |
| `test_failure_budget_window_eviction` | REL-02: old failures evicted, 3rd budget not triggered |
| `test_browser_dead_triggers_relaunch` | REL-03: ConnectionError -> assign_proxy + relaunch; ValueError -> no relaunch |
| `test_is_browser_dead_exc_classification` | helper: True/False classification |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] asyncio.sleep mock recursion in tests**
- **Found during:** Task 2 test execution
- **Issue:** `patch("core.orchestrator.asyncio.sleep", new_callable=AsyncMock)` patches the real `asyncio.sleep` globally (since `_orch.asyncio` IS the `asyncio` module object). `AsyncMock` when awaited does not actually yield to the event loop, causing supervise() to spin without ever letting sibling tasks run. Test coroutines calling `asyncio.sleep(0)` also recursed when the patched `instant_sleep` called `asyncio.sleep(0)`.
- **Fix:** Introduced `_REAL_SLEEP = asyncio.sleep` at module import time (before any patching). Created `_instant_sleep_ctx()` contextmanager that replaces `_orch.asyncio.sleep` with `_instant_sleep` (which uses `_REAL_SLEEP` to avoid recursion). Tests use `asyncio.get_running_loop().create_future()` for blocking (cancellable) waits instead of `asyncio.sleep(999)`.
- **Files modified:** tests/test_supervisor.py
- **Commit:** 11464e2

**2. [Rule 2 - Missing Critical Functionality] _park_plugin extracted from supervise()**
- **Found during:** Task 2 implementation
- **Issue:** Inline park logic (log + dispatcher.notify) pushed supervise() toward 30-line limit and was a distinct concern (notification dispatch).
- **Fix:** Extracted `_park_plugin(plugin, n_budget, dispatcher)` as a small helper. Plan noted this as an option: "if supervise exceeds ~30 lines, extract the park-notification block into a small helper."
- **Files modified:** core/orchestrator.py
- **Commit:** 11464e2

## Known Stubs

None. `_is_browser_dead_exc` handles all three confirmed nodriver 0.50.3 exception types. `supervise()` is fully wired. `plugin.relaunch()` (from Plan 01) is called on browser-death.

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes introduced. `NotificationEvent(action="plugin_parked")` uses empty `item_name` and `item_url` (T-22-03: no item data in park notification). All log calls use `exc.__class__.__name__` (T-22-03: no credential leak via str(exc)).

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED (test) | 1869679 | test(22-03): failing supervisor tests committed first |
| GREEN (feat) | 11464e2 | feat(22-03): implementation; all 6 tests pass |
| REFACTOR | n/a | No separate refactor step needed |

## Verification

```
pytest tests/test_supervisor.py tests/test_orchestrator.py  # 34 passed
pytest                                                        # 686 passed, 2 skipped
```

- REL-01: `test_crash_one_plugin_others_survive` + `test_supervise_propagates_cancelled` green
- REL-02: `test_failure_budget_parks_plugin` + `test_failure_budget_window_eviction` green
- REL-03: `test_browser_dead_triggers_relaunch` green
- Existing `test_taskgroup_creates_per_plugin_tasks` still passes (poll-* naming preserved)
- Full suite: 686 passed, 2 skipped (added 6 new tests vs. prior 680+2)

## Self-Check: PASSED

- `core/orchestrator.py` exists and contains `supervise`, `_is_browser_dead_exc`, `_FAILURE_WINDOW_SECS`
- `tests/test_supervisor.py` exists with 6 tests
- Commits 1869679, 11464e2, 056bbf9 exist in git log
- Full test suite: 686 passed, 2 skipped
