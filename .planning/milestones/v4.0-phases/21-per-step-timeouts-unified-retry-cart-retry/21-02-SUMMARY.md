---
phase: 21-per-step-timeouts-unified-retry-cart-retry
plan: "02"
subsystem: models
tags: [db, models, cart-retry, idempotency, BUY-05, REL-08]
dependency_graph:
  requires: [Phase 19 checkout_attempts/order_id/purchased columns]
  provides: [increment_checkout_attempts_sync, get_item_order_state_sync]
  affects: [core/orchestrator.py (Plan 03 cart-retry caller)]
tech_stack:
  added: []
  patterns: [parameterized SQLite UPDATE with relative increment, two-column SELECT tuple-return]
key_files:
  created: []
  modified:
    - models.py
    - tests/test_models.py
decisions:
  - "increment uses relative SQL (checkout_attempts + 1) not absolute SET; monotonic counter per BUY-05"
  - "get_item_order_state_sync mirrors get_item_notification_state_sync exactly (column names swapped)"
  - "missing-row path returns (False, None) without raising; safe for idempotency pre-check in orchestrator"
metrics:
  duration: "~7 minutes"
  completed: "2026-06-12"
  tasks_completed: 1
  tasks_total: 1
---

# Phase 21 Plan 02: DB Helpers for Cart-Retry Idempotency Summary

Two additive sync helpers in models.py giving the Plan 03 orchestrator its attempt counter and no-double-buy guard: `increment_checkout_attempts_sync` (relative +1 UPDATE) and `get_item_order_state_sync` (purchased + order_id tuple read).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| RED | Failing tests for both helpers | 0ae933a | tests/test_models.py |
| GREEN | Implement both helpers | e1b6e2e | models.py |

## Verification

- `pytest tests/test_models.py -x`: 10 passed (all new tests green)
- Full suite: 643 passed, 2 skipped
- grep confirms `checkout_attempts = checkout_attempts + 1` at models.py:115
- grep confirms `SELECT purchased, order_id FROM items WHERE link=?` at models.py:127
- No ALTER TABLE / schema change introduced

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None - both helpers are fully wired to the existing SQLite columns from Phase 19.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. Both helpers use parameterized queries matching T-21-03 mitigation requirement. No new threat surface.

## TDD Gate Compliance

- RED gate commit: `0ae933a` (test(21-02): add failing tests...)
- GREEN gate commit: `e1b6e2e` (feat(21-02): implement...)
- Gate sequence: RED -> GREEN confirmed in git log.

## Self-Check: PASSED

- models.py exists and contains both new functions
- tests/test_models.py contains all 4 new test cases
- Commit 0ae933a (RED) exists
- Commit e1b6e2e (GREEN) exists
- Full suite: 643 passed
