---
status: partial
phase: 21-per-step-timeouts-unified-retry-cart-retry
source: [21-VERIFICATION.md]
started: 2026-06-11
updated: 2026-06-11
---

## Current Test

[awaiting human testing]

## Tests

### 1. Live per-step timeout under a slow drop

expected: With a short `checkout.step_timeout_secs` and a throttled/slow DOM step, the step times out, the correct `self._checkout_stage` is logged, `auto_buy` returns False, the browser is not left mid-checkout, and the cart-retry budget limits re-submission. No half-submitted order, no orphaned browser state.
result: [pending]

### 2. [HIGH] Place-order-stage timeout double-buy edge case

expected: Verify the narrow residual risk surfaced in code review/verification: if the place-order DOM stage TIMES OUT (yielding (False, None)) but the order was actually placed at the retailer, the cart-retry re-reads the DB before the next attempt — if confirmation was captured (order_id set) it short-circuits (no re-buy), but if confirmation was NOT yet captured a retry could re-submit. Confirm behavior on a live test_mode buy where the place-order step is artificially slowed. If the risk is real, harden in Phase 22 (supervision) by treating a timeout at/after the place-order stage as possibly-placed (do not retry; fall to legacy purchased). Track as a Phase 22 consideration.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps

(none blocking — all automated checks passed; the two clear double-buy paths from code review are fixed with regression tests. Item 2 is a narrow residual edge requiring live verification + likely Phase 22 hardening. Deferred as UAT debt per autonomous-run policy.)
