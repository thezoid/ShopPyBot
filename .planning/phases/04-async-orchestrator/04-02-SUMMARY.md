---
phase: 04-async-orchestrator
plan: 02
subsystem: sqlite-persistence
tags: [python, sqlite, wal, models, concurrency, context-manager]
requires: [04-01]
provides:
  - "WAL journal mode for data/shop_py_bot.db (persisted via CREATE TABLE write)"
  - "Per-connection busy_timeout=5000ms"
  - "Single _connect() context manager: commit-on-success, rollback-on-exception"
affects:
  - "main.py (transitive — already calls initialize_db/add_items/get_items; no signature change)"
tech_stack:
  added: []
  patterns:
    - "contextlib.contextmanager for connection lifecycle"
    - "Per-connection PRAGMA busy_timeout (Pitfall 3)"
    - "WAL set BEFORE CREATE TABLE write for persistence (Pitfall 2)"
    - "No module-scope connection cache (Pitfall 8: cross-thread safety)"
key_files:
  created: []
  modified:
    - "models.py — full rewrite (59 → 84 lines); WAL + busy_timeout + _connect"
    - "tests/test_models_wal.py — RED skeleton replaced with 5 GREEN tests"
decisions:
  - "BUSY_TIMEOUT_MS = 5000 exported at module scope so tests can assert without hardcoding"
  - "timeout=5.0 kwarg on sqlite3.connect as belt-and-suspenders alongside PRAGMA busy_timeout"
  - "os.makedirs(parentDir, exist_ok=True) inside initialize_db so fresh checkouts work"
  - "Static guard test counts raw sqlite3.connect calls and asserts exactly 1, all inside _connect"
metrics:
  duration: "~6 minutes"
  completed: "2026-05-14"
  tasks_completed: 2
  files_modified: 2
  commits: 2
---

# Phase 04 Plan 02: SQLite WAL + Context Managers Summary

One-liner: Routed all four SQLite operations through a single `_connect()` context manager with WAL journal mode and per-connection busy_timeout=5000ms, satisfying ASYNC-04.

## What Shipped

- `models.py` rewritten with `_connect()` context manager (contextlib.contextmanager). Single chokepoint for `sqlite3.connect()`; commits on success, rolls back on exception, always closes.
- `initialize_db()` sets `PRAGMA journal_mode = WAL` immediately followed by the `CREATE TABLE` write, persisting the mode in the SQLite file header.
- `BUSY_TIMEOUT_MS = 5000` module-level constant; applied via `PRAGMA busy_timeout = 5000` inside `_connect()` on every connection (per-connection, not init-only).
- All four public functions (`initialize_db`, `add_items`, `update_item_purchased`, `get_items`) unchanged in signature; reimplemented to use `with _connect() as conn:`.
- `tests/test_models_wal.py` flipped from RED ImportError to 5 passing GREEN tests:
  1. `test_journalModeIsWal` — opens a SECOND connection and reads journal_mode, proving persistence
  2. `test_busyTimeoutAppliedOnEveryConnect` — asserts busy_timeout == 5000 from a fresh `_connect()`
  3. `test_contextManagerCommitsOnSuccess` — round-trips a row through add_items + get_items
  4. `test_contextManagerRollsBackOnException` — proves uncommitted UPDATE is reverted when block raises
  5. `test_noRawConnectOutsideHelper` — AST static guard; exactly one `sqlite3.connect(` call, inside `_connect`

## Test Results

- `pytest tests/test_models_wal.py`: 5 passed
- `pytest tests/test_models.py` (baseline): 2 passed (no regression)
- No `.db-wal` files leaked into repo `data/` directory (tmpDbPath monkeypatch verified)

## Commits

| Hash | Type | Description |
|------|------|-------------|
| 098664a | feat | Rewrite models.py with WAL + busy_timeout + _connect context manager |
| a385930 | test | Replace RED skeleton with 5 GREEN tests for ASYNC-04 |

## TDD Gate Compliance

The plan extended a RED skeleton from Plan 04-01 rather than emitting its own RED commit. Verified RED state before implementing (ImportError on `_connect` from test_models_wal.py at HEAD~2). GREEN gate: commit `098664a` (feat) followed by commit `a385930` (test enrichment). Per Plan 04-01 SUMMARY, the RED commit lives at `ed68a0d`.

## Deviations from Plan

None. Plan executed exactly as written.

## Auth Gates

None.

## Deferred Issues

Pre-existing test-collection issues NOT caused by this plan (logged for visibility, out of scope per executor scope-boundary rule):

- `tests/test_orchestrator.py`, `tests/test_purchase_writer.py`, `tests/test_registry_stagger.py`: RED skeletons from Plan 04-01 — will turn GREEN in Wave 2 plans.
- `tests/test_utils.py`: ModuleNotFoundError on `pygame` — pre-existing environment gap, not introduced here.
- `tests/test_driver_setup.py`: 4 failures from missing `selenium` — pre-existing.
- `tests/test_plugin_shutdown.py::test_shutdownIsCoroutine`: RED skeleton for Wave 2 plugin shutdown work.

The plan's target tests (`tests/test_models.py` + `tests/test_models_wal.py`) are all green.

## Threat Flags

None. All threats in the plan's `<threat_model>` are mitigated and covered by the GREEN tests:
- T-04-02-DB-LOCKED → busy_timeout per-connection (test 2)
- T-04-02-PARTIAL-WRITE → rollback on exception (test 4)
- T-04-02-WAL-NOT-PERSISTED → second-connection read-back (test 1)
- T-04-02-CROSS-THREAD-CONN → no module cache; static guard (test 5)
- T-04-02-WAL-COMMIT-LEAK → .gitignore from Plan 04-01

## Known Stubs

None.

## Self-Check

- [x] `models.py` exists, contains `journal_mode`, `busy_timeout`, `_connect`, `BUSY_TIMEOUT_MS`
- [x] Exactly one `sqlite3.connect(` call in models.py, inside `_connect()` (verified by test 5)
- [x] `tests/test_models_wal.py` exists, 5 tests pass
- [x] Commit 098664a exists
- [x] Commit a385930 exists

## Self-Check: PASSED
