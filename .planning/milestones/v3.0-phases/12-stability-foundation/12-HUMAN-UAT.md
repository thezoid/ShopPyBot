---
status: partial
phase: 12-stability-foundation
source: [12-VERIFICATION.md]
started: 2026-06-09
updated: 2026-08-01
---

## Current Test

[awaiting human testing]

## Tests

### 1. MC-1 — Keyring restart survival (Windows)
expected: After `shoppybot setup` stores credentials, exiting and restarting in a new PowerShell session does NOT re-prompt for credentials (keyring persists across restart).
result: [pending — terminal/TTY check, out of scope for the browser agent; remains one of only two items runnable with no extra prerequisites. Reviewed 2026-08-01 via live browser UAT session.]

### 2. MC-2 — Masked-TTY passphrase prompt (Windows)
expected: During `shoppybot setup` credential entry, the passphrase input is masked (no echo to terminal).
result: [pending — terminal/TTY check, out of scope for the browser agent; remains one of only two items runnable with no extra prerequisites. Reviewed 2026-08-01 via live browser UAT session.]

### 3. MC-3 — Web dashboard live render (Ubuntu)
expected: On an Ubuntu host, the web dashboard renders, Start/Stop state transitions work, and log polling updates live.
result: [pending — pending Ubuntu access. Spec drift noted 2026-08-01 via live browser UAT session: this item describes the log panel as polling-driven, but the dashboard moved to SSE (EventSource on /api/events) in v4.1, with polling only as a fallback.]

### 4. MC-4 — `0.0.0.0` bind banner live render
expected: When bound to `0.0.0.0`, the dashboard shows the "reachable beyond localhost" warning banner in a real browser. (Jinja2 conditional is already CI-asserted by tests/test_web_dashboard.py.)
result: [pending — BLOCKED on a restart with `--host 0.0.0.0`, which has not been done. Partially verified 2026-08-01 via live browser UAT session: on a loopback bind the `.banner-warning` element is confirmed ABSENT from the DOM (correct current-state behavior); the positive-render half remains unverified.]

### 5. Ubuntu variants of MC-1, MC-2, MC-4
expected: All four checks pass on a real Ubuntu host; update the "pending Ubuntu access" cells in docs/PLATFORMS.md with results.
result: [pending — pending Ubuntu access; unchanged as of 2026-08-01]

## UAT Session Results — 2026-08-01

Verified 2026-08-01 via live browser UAT session (human plus browser agent, against the live dashboard and the live GitHub API). Findings recorded, not re-run:

- MC-1 — still pending. Terminal/TTY check, out of scope for a browser agent. Together with MC-2 it remains one of only two items runnable with no extra prerequisites.
- MC-2 — still pending. Terminal/TTY check, out of scope for a browser agent. Together with MC-1 it remains one of only two items runnable with no extra prerequisites.
- MC-3 — still pending on Ubuntu access. Drift: the item describes the log panel as polling-driven, but the dashboard moved to SSE (EventSource on /api/events) in v4.1, with polling only as a fallback.
- MC-4 — still BLOCKED / pending. Partially verified: on a loopback bind the `.banner-warning` element is confirmed ABSENT from the DOM (correct current-state behavior). The full render check needs a restart with `--host 0.0.0.0`, which has not been done.
- Item 5 (Ubuntu variants) — unchanged, still blocked on Ubuntu access.

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
