---
status: partial
phase: 22-supervisor-browser-relaunch-server-safety
source: [22-VERIFICATION.md]
started: 2026-06-12
updated: 2026-06-12
---

## Current Test

[awaiting human testing]

## Tests

### 1. Live supervisor restart + browser relaunch after a real Chrome crash

expected: With the bot running multiple plugins, kill the Chrome process for ONE plugin. That plugin's supervisor detects the browser-dead exception, calls assign_proxy + relaunch() (teardown → setup with stealth re-applied → restore_session stub → login), and resumes polling. All OTHER plugins keep running uninterrupted. After exceeding the failure budget (alert_on_errors within ~600s) the plugin is parked and a `plugin_parked` notification fires.
result: [pending]

### 2. Live SIGTERM/SIGINT clean teardown on the target server OS

expected: Send SIGTERM (or Ctrl+C / SIGINT) to the running bot. Cooperative teardown runs: the write-queue is flushed (pending DB writes persisted), browsers are torn down via teardown_all, and no orphaned Chrome processes remain. Verify on the actual deployment OS (the signal bridge uses add_signal_handler on POSIX, signal.signal on Windows).
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps

(none blocking — all 6 success criteria verified with mocked browser-death exceptions and signals; 693 tests pass. These two require real OS-level process death / signal delivery with live Chrome, which cannot run on the dev box. Deferred as UAT debt per autonomous-run policy.)
