---
phase: 29-sse-client-wiring
verified: 2026-06-27T00:00:00Z
status: human_needed
score: 9/9 must-haves verified
overrides_applied: 0
human_verification:
  - test: "One stream replaces two polls"
    expected: "DevTools Network shows a single persistent text/event-stream to /api/events; no repeating /api/status or /api/logs requests every 2s while SSE is connected"
    why_human: "Requires a live browser with DevTools open against a running server; TestClient is synchronous HTTP with no real EventSource"
    result: "PASS - Verified 2026-08-01 via live browser UAT session. Over ~12 seconds with the indicator reading 'Live', the network log recorded exactly ONE request (/api/analytics) and zero repeating /api/status or /api/logs. EventSource readyState 1, _sseFallbackTimer null. The 30s /api/analytics poll is CORRECT and expected, not a regression: it is registered above the EventSource feature-detect deliberately because there is no 'analytics' SSE event type (the producer broadcasts only status and log), so without it the analytics cards would freeze for the life of every SSE session."
  - test: "Live health updates within 1-2s"
    expected: "Start/Stop Bot causes status dot, label, and health cards to update without page refresh within ~1-2 seconds"
    why_human: "Timing behavior requires a real browser with a connected SSE stream; cannot be asserted via static template inspection"
    result: "FAIL - Verified 2026-08-01 via live browser UAT session. Clicking Start Bot sends POST /api/bot/start which returns HTTP 200, but the status label stays 'Stopped', the dot stays status-dot stopped, and no health cards ever appear, because core/orchestrator.py _register_signals calls signal.signal() off the main thread (BotService.start runs async_main in a daemon thread), raising 'ValueError: signal only works in main thread of the main interpreter' and killing the bot loop at async_main's fifth statement before plugin setup while the endpoint still returns 200. Fixed in PR #12 (branch fix/signal-handler-main-thread)."
  - test: "No duplicate log lines at backfill/stream boundary"
    expected: "Reload page; backfilled log lines appear once; as bot runs, new SSE log lines append with no line duplicated at the boundary"
    why_human: "Requires live SSE stream delivering actual log events after a pollLogs() backfill; untestable with TestClient"
  - test: "Clean reconnect after tab close/reopen"
    expected: "Closing and reopening http://localhost:8000 shows one new /api/events stream in DevTools; indicator returns to Live; live updates resume"
    why_human: "Browser session lifecycle and native EventSource reconnect behavior; not exercisable in-process"
    result: "PASS - Verified 2026-08-01 via live browser UAT session. A fresh tab produced the full cold-start burst (/api/status, /api/logs?n=500, /api/analytics, /api/items, /api/credentials, /api/config, /api/history, one /api/price-history per item) plus exactly ONE new /api/events, and the indicator returned to 'Live'."
  - test: "Polling fallback with no JS error"
    expected: "DevTools console: run window.EventSource = undefined then reload; Network tab shows /api/status and /api/logs polling every 2s; Console shows zero JS errors"
    why_human: "Requires runtime browser JS execution to override EventSource and observe console output"
    result: "BLOCKED - Verified 2026-08-01 via live browser UAT session. Requires shadowing window.EventSource BEFORE the inline script's feature-detect runs, which needs a DevTools source breakpoint the browser agent cannot set. Drift: the stated recipe ('run window.EventSource = undefined then reload') CANNOT work, because reloading creates a fresh window that restores EventSource."
---

# Phase 29: SSE Client Wiring Verification Report

**Phase Goal:** The dashboard replaces its 2s polling with a single persistent EventSource('/api/events'); health cards + log panel update live; polling fallback where EventSource is unavailable; a Live/Reconnecting indicator shows connection state.
**Verified:** 2026-06-27
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `new EventSource('/api/events')` present in served HTML | VERIFIED | dashboard.html line 603; test_eventsource_constructed GREEN |
| 2 | Named `addEventListener('status'` and `addEventListener('log'` present | VERIFIED | dashboard.html lines 604, 607; W29-A2/A3 tests GREEN |
| 3 | SSE handlers JSON.parse-wrapped in try/catch | VERIFIED | dashboard.html lines 605, 608 — both event handlers wrap JSON.parse in try/catch with silent catch to keep stream alive |
| 4 | `onopen` calls `setIndicator('live')`; `onerror` calls `setIndicator('reconnecting')` | VERIFIED | dashboard.html lines 610-611 |
| 5 | `typeof EventSource !== 'undefined'` feature-detect with else-branch polling fallback | VERIFIED | dashboard.html lines 602-615; W29-A4 GREEN; W29-A11 GREEN (setInterval only inside else) |
| 6 | SSE branch does NOT start setInterval | VERIFIED | W29-A11 asserts both setInterval(pollStatus and setInterval(pollLogs appear only after the else token; test GREEN |
| 7 | `renderStatus` shared renderer; `pollStatus` delegates to it | VERIFIED | dashboard.html lines 326-344 (renderStatus), 359-377 (pollStatus calls renderStatus) |
| 8 | `_lastLogLine` no-dup guard in appendLogLine; reset in renderLogLines | VERIFIED | dashboard.html line 486 (var _lastLogLine = ''), line 501 (early return), line 525 (_lastLogLine = '' reset on repaint) |
| 9 | `setIndicator` + `#sse-indicator` element; `.status-dot.reconnecting` uses var(--color-status-warn) | VERIFIED | dashboard.html lines 33-36 (element), 347-357 (setIndicator); components.css line 67 |

**Score:** 9/9 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `web/templates/dashboard.html` | EventSource block, named listeners, onopen/onerror, feature-detect, renderStatus, _lastLogLine, setIndicator, #sse-indicator | VERIFIED | All present; substantive implementation, fully wired |
| `web/static/components.css` | `.status-dot.reconnecting { background: var(--color-status-warn); }` | VERIFIED | Line 67; zero hardcoded hex |
| `tests/test_sse_wiring.py` | 9 test functions covering W29-A1..A7, A11, onmessage guard | VERIFIED | 8 tests GREEN (all pass post-Plan 03); 1 was always-green anti-pattern guard |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| SSE 'status' listener | renderStatus(data) | `es.addEventListener('status', function(e) { try { renderStatus(JSON.parse(e.data)); }` | VERIFIED | dashboard.html line 604-606 |
| SSE 'log' listener | appendLogLine(line) | `es.addEventListener('log', function(e) { ... appendLogLine(p.line); maybeScrollToBottom(); }` | VERIFIED | dashboard.html lines 607-609 |
| onopen/onerror | #sse-indicator (setIndicator) | `es.onopen = function() { setIndicator('live'); }; es.onerror = function() { setIndicator('reconnecting'); };` | VERIFIED | dashboard.html lines 610-611 |
| pollStatus | renderStatus | `renderStatus(data)` called inside try block | VERIFIED | dashboard.html line 363 |
| typeof EventSource else-branch | setInterval(pollStatus/pollLogs) | both setInterval calls exclusively inside else | VERIFIED | dashboard.html lines 613-614; W29-A11 test passes |

### Data-Flow Trace (Level 4)

SSE path is event-driven, not state-fetched — the EventSource connection delivers server-pushed frames that flow directly into `renderStatus` and `appendLogLine`. No disconnected props or hollow data sources. The one-shot backfill (`pollStatus()` + `pollLogs()` at lines 598-599) runs unconditionally before the feature-detect branch and populates the DOM from live API calls. Level 4 is FLOWING for the static surface; live stream data-flow requires human UAT (items 1-5 below).

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All W29 SSE wiring assertions GREEN | `python -m pytest tests/test_sse_wiring.py -q` | 8 passed | PASS |
| Regression guards (dashboard, observability, design, security, sse) | `python -m pytest tests/test_sse_wiring.py tests/test_web_dashboard.py tests/test_observability_ui.py tests/test_design_system.py tests/test_web_security.py tests/test_sse.py -q` | 53 passed | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| SSE-01 | 29-01, 29-02, 29-03 | Dashboard receives live status + log updates over single SSE stream, replacing 2s polling | SATISFIED (automated surface); NEEDS HUMAN (live behavior) | All 9 static assertions GREEN; 5 live criteria deferred to human UAT per plan design |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | - | No TBD/FIXME/XXX/placeholder patterns found in phase-modified files | - | - |

The `.onmessage` anti-pattern (Pitfall 1) is explicitly guarded by `test_no_onmessage_for_named_events` and confirmed absent from dashboard.html. No manual reconnect loop in onerror (Pitfall 2 — confirmed). No `renderLogLines` called on SSE log events (Pitfall 4 — confirmed, only `appendLogLine` used).

### Human Verification Required

The 5 live SSE-01 criteria cannot be exercised by TestClient (synchronous in-process HTTP, no real browser EventSource). These were explicitly planned as operator UAT in Plan 03 Task 3. Run `python main.py` then open `http://localhost:8000` in a browser.

> **Drift noted 2026-08-01 (live browser UAT session):** the launcher above is wrong. `python main.py` starts no HTTP server; the correct launcher is `shoppybot web`.

#### 1. One Stream Replaces Two Polls

**Test:** DevTools Network tab while SSE is connected.
**Expected:** Single persistent `text/event-stream` to `/api/events`; no repeating `/api/status` or `/api/logs` requests every 2 seconds.
**Why human:** Requires real browser EventSource; TestClient is synchronous.
**Result (29-HV-1):** PASS - Verified 2026-08-01 via live browser UAT session. Over ~12 seconds with the indicator reading "Live", the network log recorded exactly ONE request: `/api/analytics`. Zero repeating `/api/status` or `/api/logs`. EventSource `readyState` 1, `_sseFallbackTimer` null. The 30s `/api/analytics` poll is CORRECT and expected, not a regression: it is registered above the EventSource feature-detect deliberately because there is no `analytics` SSE event type (the producer broadcasts only `status` and `log`), so without it the analytics cards would freeze for the life of every SSE session.

#### 2. Live Health Updates Within 1-2s

**Test:** Click Start Bot, then Stop Bot.
**Expected:** Status dot, label, and health cards update within ~1-2 seconds without a page refresh.
**Why human:** Requires real SSE stream delivering server-pushed status frames.
**Result (29-HV-2):** FAIL - Verified 2026-08-01 via live browser UAT session. Clicking Start Bot sends `POST /api/bot/start` which returns HTTP 200, but the status label stays "Stopped", the dot stays `status-dot stopped`, and no health cards ever appear. Root cause: `core/orchestrator.py` `_register_signals` calls `signal.signal()` off the main thread, which raises `ValueError: signal only works in main thread of the main interpreter`; `BotService.start` runs `async_main` in a daemon thread, so the bot loop dies at `async_main`'s fifth statement, before plugin setup, while the endpoint still returns 200. Fixed in PR #12 (branch `fix/signal-handler-main-thread`). This is the single real product defect found by the whole UAT sweep.

#### 3. No Duplicate Log Lines at Backfill/Stream Boundary

**Test:** Reload page; observe log viewer as bot runs.
**Expected:** Backfilled lines appear once; subsequent SSE log events append without duplicating the last backfilled line.
**Why human:** Requires live SSE log events after pollLogs() backfill completes.

#### 4. Clean Reconnect After Tab Close/Reopen

**Test:** Close the browser tab; reopen `http://localhost:8000`.
**Expected:** DevTools shows one new `/api/events` stream; indicator returns to "Live"; live updates resume.
**Why human:** Browser session lifecycle and native EventSource auto-reconnect are unexercisable in-process.
**Result (29-HV-4):** PASS - Verified 2026-08-01 via live browser UAT session. A fresh tab produced the full cold-start burst (`/api/status`, `/api/logs?n=500`, `/api/analytics`, `/api/items`, `/api/credentials`, `/api/config`, `/api/history`, one `/api/price-history` per item) plus exactly ONE new `/api/events`, and the indicator returned to "Live".

#### 5. Polling Fallback — No JS Error

**Test:** DevTools console: run `window.EventSource = undefined` then reload.
**Expected:** Network shows `/api/status` and `/api/logs` polling every 2s; Console shows zero JavaScript errors.
**Why human:** Requires runtime JS environment to override the EventSource global.
**Result (29-HV-5):** BLOCKED - Verified 2026-08-01 via live browser UAT session. Requires shadowing `window.EventSource` BEFORE the inline script's feature-detect runs, which needs a DevTools source breakpoint that the browser agent cannot set. Drift: the stated recipe ("run `window.EventSource = undefined` then reload") CANNOT work, because reloading creates a fresh window that restores `EventSource`.

### Gaps Summary

No automated gaps. All 9 static-surface truths are VERIFIED. The 5 human UAT items are inherent live-behavior checks that the phase plan explicitly deferred as operator UAT debt — they are not failures. Status is `human_needed` because those items exist, not because any automated check failed.

### Live UAT Results — Verified 2026-08-01 via live browser UAT session

Recorded from a human-plus-browser-agent session run against a live dashboard and the live GitHub API on 2026-08-01. Transcribed results only; no items were re-run during transcription.

| Item | Test | Verdict | Notes |
|------|------|---------|-------|
| 29-HV-1 | One stream replaces two polls | PASS | ~12s at indicator "Live": exactly ONE request (`/api/analytics`), zero repeating `/api/status` or `/api/logs`; EventSource `readyState` 1, `_sseFallbackTimer` null. The 30s `/api/analytics` poll is correct and expected, not a regression (no `analytics` SSE event type exists, so the cards would otherwise freeze for the life of every SSE session). |
| 29-HV-2 | Live health updates within 1-2s | FAIL | `POST /api/bot/start` returns 200 but status stays "Stopped" with no health cards, because `core/orchestrator.py` `_register_signals` calls `signal.signal()` off the main thread (daemon-thread `async_main`), raising `ValueError: signal only works in main thread of the main interpreter`. Fixed in PR #12 (`fix/signal-handler-main-thread`). Single real product defect from the whole UAT sweep. |
| 29-HV-3 | No duplicate log lines at backfill/stream boundary | (no verdict recorded) | Not covered by the 2026-08-01 session. |
| 29-HV-4 | Clean reconnect after tab close/reopen | PASS | Fresh tab showed the full cold-start burst plus exactly ONE new `/api/events`; indicator returned to "Live". |
| 29-HV-5 | Polling fallback, no JS error | BLOCKED | Needs `window.EventSource` shadowed before the inline feature-detect runs, requiring a DevTools source breakpoint the browser agent cannot set. |

**Doc drift found during the session:**
- Section preamble launcher is wrong: `python main.py` starts no HTTP server; the correct launcher is `shoppybot web`.
- 29-HV-5 recipe is unworkable as written: `window.EventSource = undefined` then reload cannot work, because reloading creates a fresh window that restores `EventSource`.

---

_Verified: 2026-06-27_
_Verifier: Claude (gsd-verifier)_
