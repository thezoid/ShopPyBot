---
phase: 24-health-surface-server-safety
plan: "04"
subsystem: orchestrator
tags: [health, REL-07, supervise, run_plugin, health_degraded, orders_confirmed]
dependency_graph:
  requires: ["24-01"]
  provides: [orchestrator-health-writes, health_degraded-dispatch, orders-confirmed-counter]
  affects: [core/orchestrator.py, tests/test_supervisor.py, tests/test_orchestrator.py]
tech_stack:
  added: []
  patterns: [health=None kwarg convention, armed/disarmed dedup, threshold_correction override]
key_files:
  modified:
    - core/orchestrator.py
    - tests/test_supervisor.py
    - tests/test_orchestrator.py
decisions:
  - "health_degraded threshold = max(1, alert_on_errors-1) consecutive errors (threshold_correction override)"
  - "consecutive_errors in HealthRegistry is independent of failure_times deque; reset on healthy run"
  - "orders_confirmed placed in _try_auto_buy after _enqueue_buy_result (covers both confirmed and legacy paths)"
  - "health=None threaded via _check_and_buy -> _try_auto_buy same as dispatcher pattern"
metrics:
  duration: "~25 minutes"
  completed: "2026-06-12"
  tasks: 2
  files_changed: 3
---

# Phase 24 Plan 04: Orchestrator Health Wiring Summary

HealthRegistry fully wired through async_main->supervise->run_plugin->_try_auto_buy with heartbeat, items_checked, status transitions, orders_confirmed, and health_degraded armed-once dispatch.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Thread health=None through orchestrator; all hooks | e00b6aa | core/orchestrator.py, tests/test_orchestrator.py |
| 2 | health_degraded + status-transition + counter tests | 7061594 | tests/test_supervisor.py, tests/test_orchestrator.py |

## What Was Built

### core/orchestrator.py

Five `health=None` keyword params added: `async_main(health_registry=None)`, `supervise(..., health=None)`, `run_plugin(..., health=None)`, `_check_and_buy(..., health=None)`, `_try_auto_buy(..., health=None)`.

Hook sites:
- `supervise` healthy run: `set_status("running")`, `reset_errors()`, `disarm_degraded()`
- `supervise` exception: `record_error()`; fires `health_degraded` via dispatcher when `consecutive_errors >= max(1, n_budget-1)` AND not armed (distinct early-warning before park)
- `supervise` park: `set_status("parked")` before `_park_plugin`
- `supervise` browser-dead: `set_status("relaunching")` before `relaunch()`
- `run_plugin` per cycle: `heartbeat()` + `set_status("running")` after items fetch
- `run_plugin` per matched item: `inc_items_checked()`
- `_try_auto_buy` after `_enqueue_buy_result`: `inc_orders_confirmed(platform)` (both confirmed and legacy paths)

### tests/test_supervisor.py (4 new tests)

- `test_health_degraded_fires_once`: 2 crashes -> exactly 1 health_degraded in dispatcher
- `test_health_degraded_dedup`: 4 crashes with alert_on_errors=5 -> still exactly 1
- `test_health_degraded_rearms`: crash->healthy->crash with window eviction -> fires twice
- `test_health_degraded_distinct_from_parked`: health_degraded precedes plugin_parked in call list

### tests/test_orchestrator.py (2 new tests)

- `test_run_plugin_heartbeat_and_items_checked`: one cycle with matching item -> `last_heartbeat > 0` and `items_checked >= 1`
- `test_orders_confirmed_increments_on_confirmed_and_legacy`: confirmed path and legacy path each increment counter to 1

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Existing fake_check_and_buy mocks rejected new health= kwarg**
- Found during: Task 1 verification
- Issue: Two test helpers in test_orchestrator.py had `fake_check_and_buy(... dispatcher=None)` without `health=None`; failed with `TypeError: unexpected keyword argument 'health'`
- Fix: Added `health=None` to both mock signatures
- Files modified: tests/test_orchestrator.py
- Commit: e00b6aa (included in Task 1 commit)

**2. [Rule 1 - Bug] test_health_degraded_dedup would hang/park prematurely**
- Found during: Task 2 design
- Issue: Original design crashed 3 times with alert_on_errors=3, hitting park threshold; task never reached blocking step
- Fix: Changed to alert_on_errors=5 (threshold=4), crash 4 times then block before park at 5
- Commit: 7061594

**3. [Rule 1 - Bug] test_health_degraded_rearms needed failure_times window eviction**
- Found during: Task 2 design
- Issue: failure_times deque accumulates across episodes; second episode would park after 1 more crash (3 total in window)
- Fix: Added time.monotonic patching with t=700 for second episode to evict first episode's entries from the 600s window (mirrors existing test_failure_budget_window_eviction pattern)
- Commit: 7061594

## Test Results

Full suite: 748 passed, 2 skipped, 0 failures (baseline: 742 passed, 2 skipped)
New tests added: 6

## Self-Check

- [x] core/orchestrator.py modified with all 5 health=None params
- [x] Commits e00b6aa and 7061594 exist
- [x] Full suite: 0 failures
