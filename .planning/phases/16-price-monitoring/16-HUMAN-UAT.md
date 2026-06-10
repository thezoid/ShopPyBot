---
status: partial
phase: 16-price-monitoring
source: [16-VERIFICATION.md]
started: 2026-06-09
updated: 2026-06-09
---

## Current Test

[awaiting human testing]

## Tests

### 1. Live Amazon DOM price scrape (PRICE-02)
expected: Configure a real Amazon product URL in config.yml, start the bot, and confirm a row appears in price_history with a plausible integer-cents value — viewable via `shoppybot items price-history <name>`.
result: [pending — requires a running Chrome subprocess on a live Amazon page]

### 2. Live price-drop fan-out alert (PRICE-03, PRICE-04, PRICE-05)
expected: Set `target_price` above the current live price (or `price_drop_pct`), enable a notifier channel, run a poll cycle. Confirm exactly one `price_drop` notification is delivered with current/target/pct fields, `price_alert_armed` becomes 1, and a second cycle at the same price does NOT re-dispatch (dedup).
result: [pending — requires a real price + configured notifier channel]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
