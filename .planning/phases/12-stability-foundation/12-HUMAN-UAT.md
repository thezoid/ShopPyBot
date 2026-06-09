---
status: partial
phase: 12-stability-foundation
source: [12-VERIFICATION.md]
started: 2026-06-09
updated: 2026-06-09
---

## Current Test

[awaiting human testing]

## Tests

### 1. MC-1 — Keyring restart survival (Windows)
expected: After `shoppybot setup` stores credentials, exiting and restarting in a new PowerShell session does NOT re-prompt for credentials (keyring persists across restart).
result: [pending]

### 2. MC-2 — Masked-TTY passphrase prompt (Windows)
expected: During `shoppybot setup` credential entry, the passphrase input is masked (no echo to terminal).
result: [pending]

### 3. MC-3 — Web dashboard live render (Ubuntu)
expected: On an Ubuntu host, the web dashboard renders, Start/Stop state transitions work, and log polling updates live.
result: [pending — pending Ubuntu access]

### 4. MC-4 — `0.0.0.0` bind banner live render
expected: When bound to `0.0.0.0`, the dashboard shows the "reachable beyond localhost" warning banner in a real browser. (Jinja2 conditional is already CI-asserted by tests/test_web_dashboard.py.)
result: [pending]

### 5. Ubuntu variants of MC-1, MC-2, MC-4
expected: All four checks pass on a real Ubuntu host; update the "pending Ubuntu access" cells in docs/PLATFORMS.md with results.
result: [pending — pending Ubuntu access]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
