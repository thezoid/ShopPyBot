---
status: partial
phase: 20-checkout-profile-form-fill
source: [20-VERIFICATION.md]
started: 2026-06-11
updated: 2026-06-11
---

## Current Test

[awaiting human testing]

## Tests

### 1. Live BestBuy shipping form-fill

expected: On a real BestBuy `test_mode` checkout, the 7 shipping selectors fill correctly from the saved CheckoutProfile. Selectors are MEDIUM/LOW confidence — if any field is misfilled or a selector returns None (WARNING + abort), update the selector in `plugins/shopbot_plugin_bestbuy.py`.
result: [pending]

### 2. Live CVV entry

expected: On a real BestBuy/Amazon `test_mode` checkout, the runtime CVV (from getpass) is typed into the CVV field. BestBuy `#credit-card-cvv` is HIGH confidence; Amazon CVV field is context-dependent (skip-if-absent is by design) — confirm it appears and fills when present.
result: [pending]

### 3. CR-03 monitor_only default change — production confirm

expected: The `auto_buy` defense-in-depth monitor_only early-return now defaults `False` (triggers only on explicit `monitor_only=True`); `place_order_guarded` remains the True-default fail-safe. Before the first production live-buy, manually confirm a `--monitor-only` run still places no order (orchestrator gate is primary enforcement) and a normal run proceeds.
result: [pending]

### 4. Amazon shipping address form-fill scope

expected: Confirm whether Amazon's account-saved shipping address always pre-populates at checkout (in which case Amazon shipping form-fill is unnecessary and only CVV entry is needed, as currently implemented). If Amazon sometimes requires address entry, a follow-up is needed to add Amazon shipping form-fill.
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps

(none — all automated checks passed; these require a live retailer checkout. Shipping/CVV selectors are MEDIUM/LOW confidence; the CR-03 default change is a live-buy behavior nuance. Deferred as UAT debt per autonomous-run policy.)
