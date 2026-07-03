---
phase: 29-sse-client-wiring
plan: "03"
requirements: [SSE-01]
subsystem: web/templates
tags: [sse, eventsource, dashboard, client-wiring, observability]
dependency_graph:
  requires: ["29-02"]
  provides: ["SSE-01 full wiring"]
  affects: ["web/templates/dashboard.html"]
tech_stack:
  added: []
  patterns: ["EventSource feature-detect", "named addEventListener", "native reconnect", "one-shot backfill"]
key_files:
  modified: ["web/templates/dashboard.html"]
decisions:
  - "One-shot backfill (pollStatus/pollLogs) runs before the feature-detect branch so both SSE and polling paths get initial data"
  - "setIndicator uses textContent + CSS token classes only; no innerHTML, no hardcoded colors"
  - "onerror is indicator-only; no manual setTimeout/new EventSource reconnect loop (native retry:3000 handles reconnect)"
  - "SSE log events call appendLogLine only, never renderLogLines, to avoid clearing the buffer on each event"
metrics:
  duration: "~5 minutes"
  completed: "2026-06-27"
  tasks_completed: 2
  tasks_deferred: 1 (UAT checkpoint — recorded as debt below)
---

# Phase 29 Plan 03: SSE Client Wiring (EventSource Swap) Summary

Replace the two `setInterval` polls with a feature-detected `EventSource('/api/events')` connection driving live status and log updates, with a clean polling fallback and a Live/Reconnecting indicator.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add setIndicator(state) helper | 084bc5e | web/templates/dashboard.html |
| 2 | Replace setInterval polls with feature-detected EventSource wiring | 084bc5e | web/templates/dashboard.html |

## What Was Built

**setIndicator(state):** Pure helper reading `#sse-dot` and `#sse-label` via `getElementById`. For `'live'`: sets dot className to `'status-dot running'` and label textContent to `'Live'`. For anything else: `'status-dot reconnecting'` / `'Reconnecting'`. Uses textContent only (safe-DOM; T-29-06 mitigated).

**EventSource wiring block (replaces lines 583-586):**
- One-shot backfill: `pollStatus()` + `pollLogs()` run unconditionally for initial paint
- `if (typeof EventSource !== 'undefined')`: opens `new EventSource('/api/events')`
  - `es.addEventListener('status', ...)` calls `renderStatus(JSON.parse(e.data))`
  - `es.addEventListener('log', ...)` calls `appendLogLine(p.line)` + `maybeScrollToBottom()`
  - `es.onopen` calls `setIndicator('live')`
  - `es.onerror` calls `setIndicator('reconnecting')` (indicator only; native retry:3000 handles reconnect)
- `else` branch: `setInterval(pollStatus, POLL_MS)` + `setInterval(pollLogs, POLL_MS)` — existing Phase 28 polling behavior preserved; no JS error on this path

## Test Results

Full suite: **802 passed, 2 skipped** — all green.

W29 assertions now GREEN:
- W29-A1: `new EventSource('/api/events')` present
- W29-A2: `addEventListener('status'` present
- W29-A3: `addEventListener('log'` present
- W29-A4: `typeof EventSource` feature-detect present
- W29-A5: `renderStatus` present (from Plan 02)
- W29-A6: `_lastLogLine` no-dup guard present (from Plan 02)
- W29-A7: `id="sse-indicator"` element present (from Plan 02)
- W29-A11: `setInterval(pollStatus` and `setInterval(pollLogs` appear ONLY after `else` branch

Anti-pattern guards GREEN: `.onmessage` absent; no innerHTML in SSE path; no manual reconnect loop.

## Deviations from Plan

None — plan executed exactly as written. Both implementation tasks combined into one commit (single logical change to one file).

## Deferred UAT Debt (Task 3 — Operator UAT)

Per the autonomous live-UAT policy (MEMORY: defer live-environment checks as UAT debt), the 5 live SSE-01 criteria are recorded here as **Phase 29 UAT debt** and are NOT blocking plan completion.

| Criterion | Description | Verification Step |
|-----------|-------------|-------------------|
| 1 | One stream replaces two polls | DevTools Network: single persistent `text/event-stream` to `/api/events`; no repeating `/api/status` or `/api/logs` requests every 2s |
| 2 | Live health updates within 1-2s | Start/stop bot; status dot and health cards update without page refresh |
| 3 | No duplicate log lines at backfill/stream boundary | Reload page; confirm backfill appears, new lines append, no duplicates |
| 4 | Clean reconnect | Close + reopen tab; confirm one new `/api/events` stream, indicator returns to Live |
| 5 | Fallback path — no JS error | DevTools console: `window.EventSource = undefined` then reload; confirm polling resumes at 2s intervals with no console errors |

**How to verify:** `python main.py` then open `http://localhost:8000` in a browser with DevTools.

## Self-Check: PASSED

- `web/templates/dashboard.html` modified: confirmed (git diff shows 26 insertions)
- Commit 084bc5e: confirmed in git log
- 802 tests passed
