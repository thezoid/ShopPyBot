---
status: partial
phase: 19-db-schema-confirmation-detection
source: [19-VERIFICATION.md]
started: 2026-06-11
updated: 2026-06-11
---

## Current Test

[awaiting human testing]

## Tests

### 1. Amazon live confirmation detection

expected: On a real Amazon `test_mode` buy reaching `/gp/buy/thankyou`, `detect_order_confirmation` captures the real order number from the `orderID` URL query param (and/or the `#confirmedOrderId` DOM selector), NOT the `CONFIRMED-<ts>` sentinel.
result: [pending]

### 2. BestBuy live confirmation detection

expected: On a real BestBuy `test_mode` buy reaching `/checkout/r/thank-you`, the `.thank-you-order-number` selector (MEDIUM confidence) yields the real order number. If it does not, update the selector in `core/confirmation.py` `_PLATFORM_MAP`.
result: [pending]

### 3. Amazon payment-failure sentinel risk

expected: If Amazon reaches `/gp/buy/thankyou` on a FAILED payment with no order id, the bot writes a `CONFIRMED-<ts>` sentinel (distinguishable by the `CONFIRMED-` prefix) — Phase 21 retry must NOT treat a sentinel as a real confirmed idempotency key. Verify the failure path does not silently mark a non-order as purchased in a way that loses the item.
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps

(none — automated checks all passed; these require a live retailer checkout to the confirmation page, which cannot run on the Windows dev box. DOM selectors are MEDIUM/LOW confidence and need live verification. Deferred as UAT debt per autonomous-run policy.)
