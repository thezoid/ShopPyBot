---
phase: 07-modular-core-service
plan: "01"
subsystem: core
tags: [botservice, api-seam, async, models, tdd]
dependency_graph:
  requires: []
  provides: [core/service.py BotService, models.remove_item_sync]
  affects: [main.py shim (Plan 02), CLI Phase 9, web UI Phase 10]
tech_stack:
  added: []
  patterns: [background-thread-with-own-loop, delegation-to-models-sync]
key_files:
  created:
    - core/service.py
    - tests/test_service.py
  modified:
    - models.py
decisions:
  - "BotService uses a daemon thread with its own asyncio event loop for start/stop from any sync caller"
  - "stop() cancels the running task via loop.call_soon_threadsafe + joins thread (routes through async_main cancellation path so teardown_all runs)"
  - "run() = asyncio.run(async_main(cfg, cvv)) preserving identical behavior to v1 main.py"
  - "CVV is a parameter only; never logged or stored as attribute (T-07-01 closed)"
metrics:
  duration_seconds: 375
  completed: "2026-06-03"
  tasks_completed: 2
  files_changed: 3
---

# Phase 07 Plan 01: BotService API Summary

**One-liner:** BotService wraps registry+orchestrator+config+models behind a single importable class using a daemon-thread-with-own-loop for non-blocking start/stop from any sync caller.

## What Was Built

### Task 1: remove_item_sync (models.py)
Added `remove_item_sync(link)` next to the existing `*_sync` functions. Uses the `get_db_connection()` context manager with a parameterized `DELETE FROM items WHERE link=?`. No existing function body was modified.

### Task 2: BotService (core/service.py) + tests/test_service.py

`BotService` exposes eight methods:

| Method | Behavior |
|--------|----------|
| `get_config()` | Returns stored AppConfig; safe before start() |
| `get_status()` | Returns `{"running": bool}`; safe before start() |
| `list_items()` | Delegates to `get_items_sync()`; safe before start() |
| `add_item(name, link, auto_buy, quantity)` | Delegates to `add_items_sync` with `purchased=False` |
| `remove_item(link)` | Delegates to `remove_item_sync(link)` |
| `start(cvv=None)` | Launches `async_main` in a daemon thread with its own event loop; returns immediately |
| `stop()` | Cancels background task via `loop.call_soon_threadsafe(task.cancel)`; joins thread |
| `run(cvv=None)` | `asyncio.run(async_main(cfg, cvv))` -- blocking convenience for shim/CLI |

Module-level `main()` constructs `BotService()` and calls `.run()` (entry point `core.service:main`).

## Threat Mitigations Applied

| Threat ID | Status | Implementation |
|-----------|--------|---------------|
| T-07-01 | Closed | CVV is a method parameter; never stored as attribute or logged |
| T-07-02 | Closed | get_status/list_items return running flag and item tuples only -- no secrets |
| T-07-03 | Closed | stop() cancels the task so async_main's finally block runs teardown_all |
| T-07-04 | Closed | core/service.py contains no input() or getpass; confirmed by test_no_input.py |

## Tests Added (tests/test_service.py)

13 new tests covering:
- `get_config`, `list_items`, `get_status` callable without start
- `add_item` and `remove_item` delegation assertions
- `start` sets running=True; `stop` sets running=False
- `stop` triggers cancellation (teardown path)
- `run` calls `asyncio.run` with `async_main` result
- No `input()` call (AST check); no `getpass` token (string check)
- `main` is callable; `main()` constructs BotService and calls run

**Suite result: 227 passed, 0 failed (13 new tests, 214 pre-existing unmodified)**

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test Bug] Unawaited coroutine warning in run() test**
- Found during: Task 2 (GREEN phase)
- Issue: `patch("core.service.async_main", new=AsyncMock())` created a coroutine that was never awaited because `asyncio.run` was also patched
- Fix: Replaced with a plain sync function returning a sentinel object; asserted `asyncio.run` was called with that sentinel
- Files modified: tests/test_service.py
- Commit: 9bfa1b3

**2. [Rule 1 - Docstring] "getpass" token in module docstring triggered own test**
- Found during: Task 2 (GREEN phase)
- Issue: The docstring mentioned "getpass" in a negative context but the test used a simple `in` string check
- Fix: Rewrote the docstring sentence to avoid the token "getpass"
- Files modified: core/service.py
- Commit: 9bfa1b3

## Stub Tracking

None. All methods are fully implemented with real delegations. No placeholder returns or TODO markers.

## Self-Check

- [x] core/service.py exists and contains `class BotService`
- [x] models.py contains `def remove_item_sync`
- [x] tests/test_service.py exists and contains `BotService`
- [x] All 8 methods present: confirmed by API surface check
- [x] No input() in core/service.py: confirmed by test_no_input.py + grep
- [x] No getpass in core/service.py: confirmed by grep + test
- [x] Commits exist: 5dc4228 (models), 8d3cdcf (RED tests), 9bfa1b3 (GREEN impl)
- [x] Full suite green: 227 passed

## Self-Check: PASSED
