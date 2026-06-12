---
phase: 22-supervisor-browser-relaunch-server-safety
plan: "02"
subsystem: orchestrator
tags: [reliability, sqlite, asyncio, timeout, tdd]
dependency_graph:
  requires: []
  provides: [run_plugin-cfg-param, sqlite-read-isolation, per-item-timeout]
  affects: [core/orchestrator.py]
tech_stack:
  added: [sqlite3 (stdlib import added to orchestrator)]
  patterns: [asyncio.timeout context manager, sqlite3.OperationalError isolation, try/except at item loop level]
key_files:
  created: []
  modified:
    - core/orchestrator.py
    - tests/test_orchestrator.py
decisions:
  - "sqlite3.OperationalError only (not DatabaseError) caught in run_plugin items read; DatabaseError propagates per Pitfall 7"
  - "asyncio.timeout wraps only _check_and_buy call; write_queue.put stays inside _check_and_buy after result is known (outside timeout context)"
  - "cfg=None keyword default on run_plugin; item_timeout read via double-getattr chain (forward-compatible)"
  - "TDD test for timeout uses fake asyncio.timeout context manager that raises TimeoutError rather than real wall-clock sleep to avoid flakiness"
metrics:
  duration: "6min"
  completed: "2026-06-12"
  tasks: 2
  files: 2
---

# Phase 22 Plan 02: Read Isolation + Per-Item Timeout Summary

Hardened `run_plugin` in `core/orchestrator.py` with two independent reliability layers per REL-05 and REL-06: SQLite read isolation on the items-list read and a per-item `asyncio.timeout(item_timeout_secs)` ceiling around each check/buy cycle.

## What Was Built

`run_plugin` now accepts a `cfg=None` keyword parameter and reads `item_timeout_secs` via `getattr(getattr(cfg, "checkout", None), "item_timeout_secs", 120)`. The `get_items_sync` executor call is wrapped in `try/except sqlite3.OperationalError`: on transient lock the function logs a WARNING and continues to the next poll cycle. `sqlite3.DatabaseError` (corruption class) is NOT caught and propagates normally. Each item's `_check_and_buy` call is wrapped in `async with asyncio.timeout(item_timeout):` with the `TimeoutError` caught at the item loop level, logging a WARNING and continuing to the next item. `write_queue.put()` calls remain inside `_check_and_buy` after the availability result is known -- outside the timeout context so a timed-out item cannot orphan a pending DB write.

`import sqlite3` was added to module-level imports.

## Deviations from Plan

**1. [Rule 1 - Bug] TDD test for item timeout required fake asyncio.timeout, not real wall-clock sleep**

- Found during: Task 1 (RED phase confirmed), first GREEN run
- Issue: The original test used `asyncio.sleep(10)` inside `fake_check_and_buy` to trigger a real timeout, but the global `asyncio.sleep` patch intercepted it and raised `CancelledError` instead of `TimeoutError`, preventing `asyncio.timeout`'s context manager from firing correctly.
- Fix: Rewrote `test_item_timeout_continues_to_next` to patch `core.orchestrator.asyncio.timeout` with a fake async context manager that raises `TimeoutError` directly for the first (slow) item and acts as a no-op for the second (fast) item. This is deterministic and avoids real wall-clock dependency.
- Files modified: tests/test_orchestrator.py
- Commit: fc84b17 (folded into Task 2 commit; test updated before GREEN commit)

## TDD Gate Compliance

| Gate | Status | Commit |
|------|--------|--------|
| RED (test commit) | PASS -- 4 tests fail for correct reason (TypeError: unexpected keyword argument 'cfg') | e306cd9 |
| GREEN (implementation commit) | PASS -- 4 tests pass, full suite 680 passed 2 skipped | fc84b17 |

## Known Stubs

None. All implemented behavior is wired and functional. The `cfg` parameter defaults to `None` with getattr-safe reading -- forward-compatible for Plan 03 which wires `cfg` through `supervise()`.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes introduced.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| core/orchestrator.py exists | FOUND |
| tests/test_orchestrator.py exists | FOUND |
| 22-02-SUMMARY.md exists | FOUND |
| Commit e306cd9 (RED tests) | FOUND |
| Commit fc84b17 (GREEN implementation) | FOUND |
| Full suite: 680 passed, 2 skipped | VERIFIED |
