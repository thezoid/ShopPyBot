---
phase: 04-async-orchestrator
plan: 02
subsystem: database
tags: [sqlite, wal, context-manager, concurrent, async-safe]
dependency_graph:
  requires: ["04-01"]
  provides: ["get_db_connection", "get_items_sync", "update_item_purchased_sync", "add_items_sync"]
  affects: ["models.py", "core/orchestrator.py (Plan 04-03 caller)"]
tech_stack:
  added: []
  patterns: ["contextlib.contextmanager", "WAL journal mode", "busy_timeout", "ThreadPoolExecutor stress proxy"]
key_files:
  created:
    - tests/test_models_wal.py
  modified:
    - models.py
    - .gitignore
decisions:
  - "Context manager commits on clean exit, rolls back on Exception, closes in finally -- no bare except (project rule)"
  - "Legacy names (get_items, update_item_purchased, add_items) are thin wrappers calling _sync bodies -- DRY: single source of truth"
  - "initialize_db routes through get_db_connection to get WAL PRAGMAs on schema creation too"
  - "Full 60-min soak is human-verify; stress proxy (20 items, 10 threads) demonstrates zero lock errors in CI"
metrics:
  duration: "3min"
  completed_date: "2026-06-03"
  tasks: 2
  files: 3
requirements_closed: [ASYNC-04, ASYNC-05]
---

# Phase 4 Plan 02: SQLite WAL + Context Manager Summary

One-liner: WAL journal mode with busy_timeout=5000 via a contextlib context manager, plus _sync function aliases for run_in_executor use by the Plan 04-03 write queue.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 RED | Failing WAL/context-manager/concurrent-write tests | 76be74a | tests/test_models_wal.py |
| 1 GREEN | WAL context manager + *_sync DB functions | c7e42ff | models.py |
| 2 | WAL sidecar gitignore entries | b73f5e9 | .gitignore |

## What Was Built

`get_db_connection()` is a `@contextlib.contextmanager` that applies the exact PRAGMA sequence on every connection open:

```
PRAGMA journal_mode=WAL
PRAGMA busy_timeout=5000
PRAGMA synchronous=NORMAL
```

The manager commits on clean yield exit, rolls back and re-raises on any `Exception`, and closes in `finally`. Three `_sync` functions (`get_items_sync`, `update_item_purchased_sync`, `add_items_sync`) implement the canonical bodies; the legacy names (`get_items`, `update_item_purchased`, `add_items`) are one-line wrappers preserving backward compatibility.

`initialize_db` also routes through `get_db_connection` so the schema creation connection gets WAL PRAGMAs too.

WAL sidecar files (`data/*.db-wal`, `data/*.db-shm`) are explicitly documented in `.gitignore` below the existing `data/*` catch-all.

## Test Results

- `tests/test_models.py`: 2 existing tests still green (backward-compatible names)
- `tests/test_models_wal.py`: 6 new tests all green
  - `test_wal_pragma_applied`: PRAGMA journal_mode returns 'wal'
  - `test_busy_timeout_applied`: PRAGMA busy_timeout returns 5000
  - `test_synchronous_normal_applied`: PRAGMA synchronous returns 1 (NORMAL)
  - `test_connection_closed_on_exit`: ProgrammingError raised on closed conn
  - `test_connection_closed_on_exception`: conn closed even when body raises
  - `test_concurrent_writes_no_lock`: 20 items / 10 threads / zero OperationalError
- Full suite: 53 passed

## Concurrent-Write Stress Proxy (SC-4)

The `test_concurrent_writes_no_lock` test seeds 20 distinct item links, fires `update_item_purchased_sync` for all 20 concurrently via `ThreadPoolExecutor(max_workers=10)`, and asserts:
1. Zero `sqlite3.OperationalError` (no 'database is locked')
2. All 20 rows have `purchased=1` after the run

This is the automated proxy for the 60-min soak. The full 60-min soak remains a **human-verify** step: run `python main.py` with `debug.test_mode=true` and two plugins active; monitor logs for `database is locked` over the soak period.

## Deviations from Plan

None. Plan executed exactly as written.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes introduced beyond what the plan's threat model covers (T-04-04 through T-04-07 all mitigated).

## Known Stubs

None.

## Self-Check: PASSED

- models.py exists: FOUND
- tests/test_models_wal.py exists: FOUND
- .gitignore contains db-wal: FOUND
- Commit 76be74a (RED): FOUND
- Commit c7e42ff (GREEN): FOUND
- Commit b73f5e9 (gitignore): FOUND
- 53 tests passing: CONFIRMED
