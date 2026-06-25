---
phase: 19-db-schema-confirmation-detection
plan: "01"
subsystem: models
tags: [db-migration, sqlite, confirmation, BUY-04]
dependency_graph:
  requires: []
  provides: [order_id-column, confirmed_at-column, checkout_attempts-column, update_item_confirmed_sync]
  affects: [models.py, tests/test_models.py]
tech_stack:
  added: []
  patterns: [idempotent-ALTER-TABLE, parameterized-UPDATE, PRAGMA-table_info-guard]
key_files:
  created: []
  modified:
    - models.py
    - tests/test_models.py
decisions:
  - "checkout_attempts added with NOT NULL DEFAULT 0; never incremented here (Phase 21 owns increment)"
  - "update_item_confirmed_sync uses bind order (order_id, confirmed_at, link) matching SET clause order"
  - "All three columns reuse existing PRAGMA snapshot built at lines 49-52; no second PRAGMA call"
metrics:
  duration: "~4 minutes"
  completed: "2026-06-11"
---

# Phase 19 Plan 01: DB Schema Confirmation Columns + Writer Summary

**One-liner:** Added order_id TEXT, confirmed_at TEXT, checkout_attempts INTEGER NOT NULL DEFAULT 0 to items table via idempotent PRAGMA-guarded ALTER, plus update_item_confirmed_sync parameterized writer (BUY-04).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing tests for confirmation columns + writer | 66455d6 | tests/test_models.py |
| 1+2 (GREEN) | Confirmation columns + update_item_confirmed_sync | 201ac0a | models.py |
| 3 | Migration idempotency + legacy-schema + writer tests | 66455d6 | tests/test_models.py |

## What Was Built

- Three idempotent column guards appended to `initialize_db()` after the Phase 16 price-column block (before price_history CREATE TABLE):
  - `order_id TEXT` (nullable, like target_price)
  - `confirmed_at TEXT` (nullable)
  - `checkout_attempts INTEGER NOT NULL DEFAULT 0` (mirrors price_alert_armed; Phase 21 arithmetic never hits NULL)
- `update_item_confirmed_sync(link, order_id, confirmed_at)` writer after `update_item_purchased_sync`, uses `get_db_connection()` context manager, single parameterized `UPDATE items SET purchased=1, order_id=?, confirmed_at=? WHERE link=?`
- Four new tests in `tests/test_models.py`: fresh-add assertion, v3.0-schema lossless migration, idempotent re-run, and writer round-trip

## Verification

- `pytest tests/test_models.py -x`: 6 passed
- `pytest` full suite: 576 passed, 2 skipped (was 572 before; net +4 new tests)
- `checkout_attempts` grep in models.py shows only the ALTER statement; no increment call site

## Scope Guard Confirmed

`checkout_attempts` is added with `NOT NULL DEFAULT 0` only. No increment call site exists in models.py or anywhere else added by this plan. Phase 21 owns the increment strategy.

## Deviations from Plan

None. Plan executed exactly as written. TDD RED/GREEN cycle followed: RED commit (66455d6) before GREEN commit (201ac0a). Task 3 tests were written together with Task 1 tests in the RED commit since they test the same models.py surface.

## TDD Gate Compliance

- RED gate: commit 66455d6 (`test(19-01): ...`) exists before GREEN
- GREEN gate: commit 201ac0a (`feat(19-01): ...`) exists after RED

## Threat Surface Scan

T-19-01 (Tampering): `update_item_confirmed_sync` uses parameterized UPDATE — all three values (order_id, confirmed_at, link) bound via `?` placeholders. No string interpolation.
T-19-02 (Tampering): `checkout_attempts INTEGER NOT NULL DEFAULT 0` ensures Phase 21 arithmetic never encounters NULL.
T-19-03 (Info Disclosure): No logging of order_id added in this plan.

No new threat surface beyond what the plan's threat model anticipated.

## Self-Check: PASSED

- models.py modified and committed: 201ac0a FOUND
- tests/test_models.py modified and committed: 66455d6 FOUND
- All 4 new tests pass (576 total, no regressions)
- checkout_attempts increment: not present (grep confirmed)
