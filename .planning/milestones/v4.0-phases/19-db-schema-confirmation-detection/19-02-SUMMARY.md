---
phase: 19-db-schema-confirmation-detection
plan: "02"
subsystem: core/confirmation
tags: [confirmation-detection, nodriver, url-matching, order-id, BUY-03]
dependency_graph:
  requires: []
  provides: [detect_order_confirmation, _extract_order_id, _PLATFORM_MAP, _SETTLE_SECS]
  affects: []
tech_stack:
  added: []
  patterns: [deferred-writeLog-import, url-first-dom-backup, FakeTab-unit-test]
key_files:
  created:
    - core/confirmation.py
    - tests/test_confirmation.py
  modified: []
decisions:
  - "writeLog imported inside function bodies (deferred) to avoid circular import with logger.py"
  - "Settle via await tab.sleep(_SETTLE_SECS) not await tab; sleep triggers browser.update_targets()"
  - "Amazon orderID URL query param parsed before any DOM select (URL-first wins)"
  - "CONFIRMED-<ts> sentinel returned when URL matches but no id extractable (BUY-03)"
  - "Selector exceptions logged with exc.__class__.__name__ only (T-19-05 info disclosure mitigation)"
metrics:
  duration_minutes: 8
  completed_date: "2026-06-11"
  tasks_completed: 2
  files_created: 2
  files_modified: 0
---

# Phase 19 Plan 02: Confirmation Detection Module Summary

**One-liner:** URL-first order confirmation detector with Amazon `orderID` query-param extraction, DOM fallback, and `CONFIRMED-<ts>` sentinel via nodriver `tab.sleep()` settle pattern.

## What Was Built

`core/confirmation.py` -- a pure detector module with no plugin or models coupling. It applies a 3s settle delay (`await tab.sleep(_SETTLE_SECS)`), reads `tab.target.url` (refreshed by the sleep's `browser.update_targets()` call), matches a per-platform URL fragment, then extracts an order id via URL query param (Amazon `orderID`) or DOM selector. Returns a `CONFIRMED-<ts>` sentinel when the URL matches but no id is extractable.

`tests/test_confirmation.py` -- six FakeTab-driven unit tests covering every branch: Amazon URL-param hit, Amazon DOM hit, BestBuy DOM hit, sentinel on URL-match-no-id, None on URL mismatch, None on unknown platform.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create core/confirmation.py | 3269abe | core/confirmation.py |
| 2 | Add FakeTab/FakeElement unit tests | 03fc6b3 | tests/test_confirmation.py |

## Verification

- `pytest tests/test_confirmation.py -x`: 6 passed
- `pytest` full suite: 582 passed, 2 skipped, 2 warnings (pre-existing warnings unrelated to this plan)

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

The following selector strings are MEDIUM confidence UAT debt per RESEARCH.md and are annotated in the source:

| File | Selector | Reason |
|------|----------|--------|
| core/confirmation.py | `#confirmedOrderId` (Amazon) | Unverified training knowledge; UAT required against live Amazon checkout page |
| core/confirmation.py | `.thank-you-order-number` (BestBuy) | Unverified training knowledge; UAT required against live BestBuy checkout page |

These stubs do NOT prevent the plan goal from being achieved: the `CONFIRMED-<ts>` sentinel ensures `purchased` is still written even when the DOM selector returns no element. UAT will resolve selector confidence in a future live test run.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced in this plan. `core/confirmation.py` reads DOM/URL from the existing nodriver tab only. T-19-04 and T-19-05 mitigations are implemented:

- T-19-04 (Tampering): `order_id` treated as opaque stored string, `.strip()` normalized, never eval'd.
- T-19-05 (Info Disclosure): selector errors logged with `exc.__class__.__name__` only; never `str(exc)`.
- T-19-06 (DoS): per-selector `timeout=5` bounds DOM wait; settle is fixed `_SETTLE_SECS = 3.0`.

## Self-Check: PASSED

- core/confirmation.py: FOUND
- tests/test_confirmation.py: FOUND
- Commit 3269abe: FOUND (feat 19-02 confirmation.py)
- Commit 03fc6b3: FOUND (test 19-02 unit tests)
