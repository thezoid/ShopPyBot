---
status: partial
phase: 13-anti-detection-layer-1-fingerprint-proxy
source: [13-VERIFICATION.md]
started: 2026-06-09
updated: 2026-06-09
---

## Current Test

[awaiting human testing]

## Tests

### 1. Fingerprint probe (ANTI-08)
expected: Running the bot against CreepJS / bot.sannysoft with a real browser shows `window.chrome` defined, `navigator.plugins` populated (3 entries), `navigator.languages` patched, plausible screen dimensions, and NO WebRTC real-IP leak.
result: [pending — requires a real browser + probe site]

### 2. Live proxy rotation + IP hiding (ANTI-04, ANTI-05)
expected: With two real proxy URLs configured and enabled, triggering proxy 1 retirement (3 consecutive ban signals) causes proxy 2 to be used on the next browser restart; outbound IP reflects the active proxy; WebRTC probe shows no real-IP UDP leak.
result: [pending — requires a real proxy server + banning endpoint]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
