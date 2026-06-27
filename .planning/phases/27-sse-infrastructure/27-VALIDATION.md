---
phase: 27
slug: sse-infrastructure
status: draft
nyquist_compliant: false
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

- **After every task commit:** Run `tests/test_sse.py`
- **After every plan wave:** Run `pytest -q`
- **Before `/gsd:verify-work`:** Full suite green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------------|-----------|-------------------|--------|
| (populated during planning) | | | SSE-02 | no credential-pattern in SSE frame | unit (TestClient stream) | `pytest tests/test_sse.py -q` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_sse.py` — NEW: isolation tests (the "spike"), all with `with TestClient(app) as c:`
      so the lifespan/poll-loop actually starts. One test per ROADMAP criterion:
  - stream opens with `retry: 3000` (criterion 4)
  - a `data:` status frame arrives within the injected fast interval (criterion 1)
  - `: keep-alive` comment emitted on idle (criterion 1)
  - bot start/stop flips `status.running` in the stream (criterion 3)
  - disconnect: exiting the stream context leaves `SseHub` with zero queues (criterion 2 —
    asserted via the `finally` cleanup, not `is_disconnected()` which is unreliable in
    TestClient's in-process transport)
  - an `/api/events` data frame contains no credential-pattern strings (SSE-03 carryover)
- [ ] Possibly `tests/test_log_reader.py` (or add to existing) — `tail_log_lines(after_line)`
      cursor: returns only new lines + new cursor; handles `after_line > total` (rollover) by
      resetting to 0.

*Wave 0 spike must also resolve RESEARCH open question A2 (httpx iter_text chunking) and
adjust frame assertions accordingly.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live `curl -N localhost:8000/api/events` | SSE-02 | TestClient covers the contract; live curl is an operator smoke check across a real socket | `python main.py` web mode, `curl -N localhost:8000/api/events`, start/stop bot, observe frames |

*TestClient streaming tests are the automated gate for all four criteria; the live curl
(real TCP disconnect detection) is an operator smoke check (UAT debt per autonomous policy).*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
