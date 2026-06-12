---
phase: 22-supervisor-browser-relaunch-server-safety
plan: "04"
subsystem: orchestrator
tags: [signal-bridge, write-queue-flush, cooperative-teardown, SRV-02]
dependency_graph:
  requires: ["22-03"]
  provides: ["_register_signals", "_flush_write_queue", "async_main signal wiring"]
  affects: ["core/orchestrator.py", "tests/test_signal_bridge.py"]
tech_stack:
  added: ["signal (stdlib)"]
  patterns: ["loop.add_signal_handler POSIX / signal.signal Windows fallback", "manual queue drain before join", "call_soon_threadsafe cooperative cancel"]
key_files:
  created: ["tests/test_signal_bridge.py"]
  modified: ["core/orchestrator.py"]
decisions:
  - "signal module added to imports; no new external packages"
  - "NotImplementedError fallback to signal.signal mirrors Windows ProactorEventLoop behavior verified in RESEARCH"
  - "_flush_write_queue placed adjacent to _write_queue_drain for discoverability"
  - "_register_signals placed immediately before async_main; called first thing after loop and root_task captured"
  - "join timeout reduced from 10s to 5s -- manual drain removes the primary source of delay so 10s was unnecessary"
  - "teardown_all() remains the last teardown step so browsers are closed after writes complete (T-22-05)"
metrics:
  duration: "235s"
  completed_date: "2026-06-12"
  tasks: 3
  files: 2
---

# Phase 22 Plan 04: Signal Bridge + Write-Queue Flush Summary

Cross-platform SIGTERM/SIGINT signal bridge with write-queue pre-teardown flush; POSIX uses `loop.add_signal_handler`, Windows falls back to `signal.signal`, both paths cancel the root task via `loop.call_soon_threadsafe` (SRV-02).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Wave 0 -- failing signal-bridge + write-queue-flush tests (RED) | f7613ec | tests/test_signal_bridge.py |
| 2 | Implement _register_signals + _flush_write_queue helpers (GREEN) | e07dbc7 | core/orchestrator.py |
| 3 | Wire signal registration + manual flush into async_main | e95a2d1 | core/orchestrator.py |

## What Was Built

### _register_signals(loop, root_task)

Module-level sync function in `core/orchestrator.py`. Registers SIGTERM and SIGINT:
- POSIX: `loop.add_signal_handler(sig, _shutdown)` (runs handler in event loop)
- Windows ProactorEventLoop: catches `NotImplementedError`, falls back to `signal.signal(sig, _shutdown)`
- Both paths: `_shutdown` calls `loop.call_soon_threadsafe(root_task.cancel)`, propagating `CancelledError` into the TaskGroup for orderly shutdown (mirrors `BotService.stop()` pattern).

### _flush_write_queue(queue, loop)

Async helper that drains remaining items after the TaskGroup exits (the `_write_queue_drain` task was cancelled mid-item, leaving `unfinished_tasks > 0`). Uses `get_nowait()` loop: dispatches each item via `_dispatch_write`, logs `ERROR` on failure, always calls `task_done()` so `queue.join()` does not deadlock (T-22-06 mitigation).

### async_main integration

After `loop = asyncio.get_running_loop()`:
```python
root_task = asyncio.current_task()
_register_signals(loop, root_task)
```

Finally block updated to:
```python
await _flush_write_queue(write_queue, loop)
try:
    await asyncio.wait_for(write_queue.join(), timeout=5)
except asyncio.TimeoutError:
    writeLog("Write queue join timed out after manual flush", "WARNING")
await registry.teardown_all()
```

Browsers closed LAST so pending DB writes complete before Chrome is torn down.

## Tests Written

`tests/test_signal_bridge.py` (5 tests, all passing):

| Test | Coverage |
|------|---------|
| test_signal_bridge_posix_path | add_signal_handler called for SIGTERM+SIGINT; signal.signal NOT called |
| test_signal_bridge_windows_fallback | signal.signal used when add_signal_handler raises NotImplementedError |
| test_shutdown_handler_cancels_root_task | captured handler invokes loop.call_soon_threadsafe(root_task.cancel) |
| test_write_queue_flush_before_teardown | real Queue; both items dispatched; join() returns immediately |
| test_write_queue_flush_error_still_calls_task_done | error path logs ERROR; task_done still called; join does not hang |

## Verification

Full test suite: **691 passed, 2 skipped** (was 686+2 before this plan; 5 new tests added).

## Deviations from Plan

None -- plan executed exactly as written.

## Known Stubs

None -- no stub patterns introduced.

## Threat Flags

No new threat surface introduced beyond what the plan's threat model covers (T-22-04, T-22-05, T-22-06 all mitigated).

## Self-Check: PASSED

- tests/test_signal_bridge.py: EXISTS
- core/orchestrator.py contains `_register_signals` and `_flush_write_queue`: VERIFIED
- core/orchestrator.py contains `root_task = asyncio.current_task()` and `_register_signals(loop, root_task)`: VERIFIED
- core/orchestrator.py finally block uses `_flush_write_queue` and `timeout=5`: VERIFIED
- Commits f7613ec, e07dbc7, e95a2d1: EXIST
