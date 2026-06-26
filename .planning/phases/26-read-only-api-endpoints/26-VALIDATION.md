---
phase: 26
slug: read-only-api-endpoints
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-25
---

# Phase 26 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (FastAPI TestClient — curl-equivalent) |
| **Config file** | pytest (project root); web tests in `tests/test_web_dashboard.py` |
| **Quick run command** | `pytest tests/test_api_observability.py -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run the new observability test file
- **After every plan wave:** Run `pytest -q`
- **Before `/gsd:verify-work`:** Full suite green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------------|-----------|-------------------|--------|
| (populated during planning) | | | OBS-08 / SSE-03 | credential scrubbing | unit (TestClient) | `pytest tests/test_api_observability.py -q` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_api_observability.py` — NEW: TestClient tests, one per ROADMAP criterion:
  - `GET /api/history` envelope shape + empty-list case (criterion 1)
  - `GET /api/price-history/{link_b64}` Amazon series + non-Amazon/bad-b64 empty series (criterion 2)
  - `GET /api/logs?level=&search=&n=` AND-filtering + no-params backward compat (criterion 3)
  - credential-pattern assertion: `/api/status` JSON + `get_status()` payload contain no
    `@`/`password`/`token`/`key=`/`cvv` (case-insensitive); `last_error` is class-name only (criterion 4)
- [ ] `tests/test_models.py` — ADD: `get_confirmed_orders_sync` returns confirmed rows with
  order_id/confirmed_at/checkout_attempts; empty when none.

*Existing pytest + TestClient infrastructure covers the rest.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live `curl` against a running uvicorn | OBS-08/SSE-03 | TestClient covers contract; live curl is an operator smoke check | `python main.py` web mode, then `curl localhost:8000/api/history` |

*TestClient tests are curl-equivalent and cover all four criteria automatically; the live curl is an optional operator smoke check (UAT debt per autonomous policy).*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
