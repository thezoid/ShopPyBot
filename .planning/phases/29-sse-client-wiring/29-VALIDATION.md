---
phase: 29
slug: sse-client-wiring
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-27
validated: 2026-06-27
---

# Phase 29 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (TestClient static-template assertions; live SSE behavior is manual UAT) |
| **Config file** | pytest (project root) |
| **Quick run command** | `pytest tests/test_sse_wiring.py -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- After every task commit: run the touched test file
- After every wave: `pytest -q`
- Before verify: full suite green
- Max feedback latency: 30s

---

## Per-Task Verification Map

| Requirement (sub-truth) | Plans | Wave | Test Type | Automated Test | Status |
|-------------------------|-------|------|-----------|----------------|--------|
| SSE-01: EventSource('/api/events') constructed | 29-01/02 | 0 | static template | `test_eventsource_constructed` | ✅ green |
| SSE-01: named `status` listener | 29-01/02 | 0 | static template | `test_named_status_listener` | ✅ green |
| SSE-01: named `log` listener | 29-01/02 | 0 | static template | `test_named_log_listener` | ✅ green |
| SSE-01: no `.onmessage` for named events | 29-02 | 0 | anti-pattern guard | `test_no_onmessage_for_named_events` | ✅ green |
| SSE-01: feature-detect branch | 29-02/03 | 0 | static template | `test_feature_detect_present` | ✅ green |
| SSE-01: shared `renderStatus` | 29-02 | 0 | static template | `test_render_status_extracted` | ✅ green |
| SSE-01: `_lastLogLine` no-dup guard | 29-02/03 | 0 | static template | `test_no_dup_guard_present` | ✅ green |
| SSE-01: Live/Reconnecting indicator | 29-02/03 | 0 | static template | `test_indicator_element_present` | ✅ green |
| SSE-01: setInterval only in fallback else | 29-02/03 | 0 | static template | `test_setinterval_only_in_fallback` | ✅ green |
| XSS guard (no regression) | 29-01..03 | 0 | regression | `test_no_innerHTML_with_api_data` | ✅ green |
| Design tokens (no regression) | 29-01..03 | 0 | regression | `test_no_hardcoded_hex_in_components` | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Combined regression run: 53 passed (test_sse_wiring + dashboard + observability + design + security + sse), per 29-VERIFICATION.md.*

---

## Wave 0 Requirements

- [x] `tests/test_sse_wiring.py` — NEW: static assertions on `GET /` served HTML —
  `new EventSource('/api/events')` present; `addEventListener('status'` and
  `addEventListener('log'` present (NOT `.onmessage`); `typeof EventSource` feature-detect
  branch present; the existing `setInterval` polling retained (fallback); a `renderStatus(`
  function present (shared by SSE + poll); the Live/Reconnecting indicator element present;
  no-dup guard reference present in `appendLogLine`. → 9 tests PASS.
- [x] XSS + hex guards stay green (`test_no_innerHTML_with_api_data`,
  `test_no_hardcoded_hex_in_components`); SSE infra tests (`test_sse.py`) + observability
  UI tests (`test_observability_ui.py`) stay green (no regression to the surfaces). → 53 passed combined.

*AUTOMATED: static-template wiring assertions, fallback-branch presence, guards. MANUAL UAT:
the 5 live criteria (DevTools shows one text/event-stream replacing two polls; health/log
update within 1-2s; no duplicate lines; clean reconnect on tab close/reopen; polling
fallback in a no-EventSource environment).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| One text/event-stream replaces the two polls | SSE-01 | DevTools network inspection | Open dashboard, DevTools Network: confirm one `/api/events` stream, no repeating `/api/status`+`/api/logs` polls |
| Live health/log updates within 1-2s | SSE-01 | Live timing | Start/stop the bot; watch cards + log viewer update without refresh |
| No duplicate log lines | SSE-01 | Live stream | Let logs flow; confirm each line appears once |
| Clean reconnect on tab close/reopen | SSE-01 | Browser lifecycle | Close + reopen tab; confirm live updates resume, indicator returns to "Live" |
| Polling fallback (no EventSource) | SSE-01 | Requires an env without EventSource | Stub `window.EventSource=undefined`; confirm polling resumes, no JS error |

*Static wiring is automated; the 5 live behaviors are operator UAT (deferred as UAT debt per
the autonomous live-UAT policy).*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (or explicit manual-UAT)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none — all automatable wiring covered)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** validated 2026-06-27

---

## Validation Audit 2026-06-27

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |

State A audit. VALIDATION.md was plan-time template (Per-Task Map unpopulated). Cross-referenced
SSE-01 sub-truths against `29-VERIFICATION.md` (9/9 verified) and the live `tests/test_sse_wiring.py`
suite (9 functions, all green; 53 passed in combined regression run). Every automatable static-wiring
behavior has a green test; the `.onmessage` anti-pattern is guarded. No MISSING gaps → auditor not
spawned, no new test files generated. The 5 outstanding items are inherent live-SSE UAT (one stream
replaces two polls, live 1-2s updates, no-dup at backfill boundary, clean reconnect, polling fallback)
— deferred as UAT debt per the autonomous live-UAT policy; not exercisable by synchronous TestClient.
