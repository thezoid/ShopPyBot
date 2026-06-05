---
status: partial
phase: 11-cross-platform-verification
source: [11-VERIFICATION.md]
started: 2026-06-05T00:00:00Z
updated: 2026-06-05T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Ubuntu desktop live CLI smoke — keyring backend
expected: With a real Secret Service running, `shoppybot` CLI commands run and `_build_store` auto-selects the keyring backend.
result: [pending]

### 2. Ubuntu headless live CLI smoke — encrypted-file backend
expected: Without D-Bus/Secret Service, CLI commands run and auto-selection falls back to the encrypted-file backend (no hang).
result: [pending]

### 3. Keyring secret persistence across restart (Windows) — Phase 8 deferred
expected: A secret stored via the OS keyring on Windows survives a full process restart and is readable on next run.
result: [pending]

### 4. Encrypted-file secret persistence across restart (Ubuntu headless) — Phase 8 deferred
expected: A secret stored in the encrypted-file backend on headless Ubuntu survives a process restart and decrypts on next run.
result: [pending]

### 5. Masked TTY input on setup — Windows PowerShell + Ubuntu — Phase 9 deferred
expected: `setup` masks secret entry (no echo), name-only confirm, on both Windows PowerShell and an Ubuntu terminal.
result: [pending]

### 6. Web dashboard live behavior + non-local warning — Phase 10 deferred
expected: Dashboard renders, live Start/Stop works, log polling updates, and binding `--host 0.0.0.0` prints the security warning banner.
result: [pending]

## Summary

total: 6
passed: 0
issues: 0
pending: 6
skipped: 0
blocked: 0

## Gaps
