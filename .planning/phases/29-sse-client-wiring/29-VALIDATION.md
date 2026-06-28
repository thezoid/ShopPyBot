---
phase: 29
slug: sse-client-wiring
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-27
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

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| (populated during planning) | | | SSE-01 | static template + unit | `pytest tests/test_sse_wiring.py -q` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_sse_wiring.py` — NEW: static assertions on `GET /` served HTML —
  `new EventSource('/api/events')` present; `addEventListener('status'` and
  `addEventListener('log'` present (NOT `.onmessage`); `typeof EventSource` feature-detect
  branch present; the existing `setInterval` polling retained (fallback); a `renderStatus(`
  function present (shared by SSE + poll); the Live/Reconnecting indicator element present;
  no-dup guard reference present in `appendLogLine`.
- [ ] XSS + hex guards stay green (`test_no_innerHTML_with_api_data`,
  `test_no_hardcoded_hex_in_components`); SSE infra tests (`test_sse.py`) + observability
  UI tests (`test_observability_ui.py`) stay green (no regression to the surfaces).

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

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies (or explicit manual-UAT)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
