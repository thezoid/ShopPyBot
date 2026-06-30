---
phase: 27
slug: sse-infrastructure
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-27
---

# Phase 27 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (FastAPI TestClient streaming; lifespan via `with TestClient(app) as c:`) |
| **Config file** | pytest (project root) |
| **Quick run command** | `pytest tests/test_sse.py -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~30 seconds (injectable fast poll/keepalive intervals — no real 1s/15s waits) |

---

## Sampling Rate

- **After every task commit:** Run `tests/test_sse.py` (and `tests/test_log_reader.py` for Plan 02 Task 1)
- **After every plan wave:** Run `pytest -q`
- **Before `/gsd:verify-work`:** Full suite green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------------|-----------|-------------------|--------|
| 27-01-T1 | 01 | 1 (Wave 0) | SSE-02 | RED spike: retry line, status frame, keepalive, running-flip, hub-empty-on-disconnect, no credential-pattern in frame | unit (TestClient stream) | `pytest tests/test_sse.py -q` | ⬜ pending (must be RED) |
| 27-01-T2 | 01 | 1 (Wave 0) | SSE-02 | RED spike: tail cursor + midnight-rollover reset | unit | `pytest tests/test_log_reader.py -q` | ⬜ pending (must be RED) |
| 27-02-T1 | 02 | 1 | SSE-02 | tail_log_lines cursor + rollover (no full re-read, Pitfall 6) | unit | `pytest tests/test_log_reader.py -q` | ⬜ pending → GREEN |
| 27-02-T2 | 02 | 1 | SSE-02 | SseHub bounded drop-oldest queues + _poll_loop sole-producer (no str(exc), survives read error) | unit (import + inline assert) | `python -c "import web.sse_hub ..."` | ⬜ pending |
| 27-03-T1 | 03 | 2 | SSE-02 | /api/events stream: retry line, idle keepalive, finally:unsubscribe (disconnect cleanup) | unit (TestClient stream) | `pytest tests/test_sse.py -q` | ⬜ pending |
| 27-03-T2 | 03 | 2 | SSE-02 | lifespan starts/cancels _poll_loop on uvicorn loop; SseHub in factory body; full spike GREEN; no credential leak | unit (TestClient stream) | `pytest tests/test_sse.py tests/test_web_dashboard.py tests/test_api_observability.py -q` | ⬜ pending → all GREEN |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Sampling continuity: no 3 consecutive code-producing tasks lack an automated verify. Plan 01 tasks are
the RED scaffold (intentionally failing); Plans 02–03 turn them GREEN.*

---

## Wave 0 Requirements

- [ ] `tests/test_sse.py` — NEW (Plan 01 Task 1): isolation tests (the "spike"), all with
      `with TestClient(app) as c:` so the lifespan/poll-loop actually starts. One test per ROADMAP
      criterion:
  - stream opens with `retry: 3000` (criterion 4)
  - a `data:` status frame arrives within the injected fast interval (criterion 1)
  - `: keep-alive` comment emitted on idle (criterion 1)
  - bot start/stop flips `status.running` in the stream (criterion 3)
  - disconnect: exiting the stream context leaves `SseHub` with zero queues (criterion 2 —
    asserted via the `finally` cleanup, not `is_disconnected()` which is unreliable in
    TestClient's in-process transport)
  - an `/api/events` data frame contains no credential-pattern strings (SSE-03 carryover)
- [ ] `tests/test_log_reader.py` — NEW (Plan 01 Task 2): `tail_log_lines(after_line)` cursor:
      returns only new lines + new cursor; handles `after_line > total` (rollover) by resetting to total.

*Wave 0 spike must also resolve RESEARCH open question A2 (httpx iter_text chunking) and adjust frame
assertions accordingly (assert on joined first-N chunks, not a single indexed chunk).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live `curl -N localhost:8000/api/events` | SSE-02 | TestClient covers the contract; live curl is an operator smoke check across a real socket (real-TCP disconnect detection that TestClient's in-process transport cannot exercise reliably — RESEARCH A3) | `python main.py` web mode, `curl -N localhost:8000/api/events`, start/stop bot, observe `retry:` line, `data:` status frames, `: keep-alive` on idle; Ctrl-C the curl and confirm the server-side generator exits |

*TestClient streaming tests are the automated gate for all four criteria; the live curl (real TCP
disconnect detection) is an operator smoke check (UAT debt per autonomous live-UAT policy).*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (tests/test_sse.py, tests/test_log_reader.py)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** planned (Plans 01–03 created 2026-06-27)
