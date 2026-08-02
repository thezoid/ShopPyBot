---
phase: 26
slug: read-only-api-endpoints
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-25
updated: 2026-06-25
---

# Phase 26 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (FastAPI TestClient — curl-equivalent) |
| **Config file** | pytest (project root); web tests in `tests/test_web_dashboard.py` |
| **Quick run command** | `rtk pytest tests/test_api_observability.py -q` |
| **Full suite command** | `rtk pytest -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run the new observability test file
- **After every plan wave:** Run `rtk pytest -q`
- **Before `/gsd:verify-work`:** Full suite green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------------|-----------|-------------------|--------|
| 01-1 | 26-01 | 1 | OBS-08 / SSE-03 | RED endpoint contracts | unit (TestClient) | `rtk pytest tests/test_api_observability.py -x` (expect RED) | ⬜ pending |
| 01-2 | 26-01 | 1 | SSE-03 | RED model contract | unit | `rtk pytest tests/test_models.py -k confirmed_orders` (expect RED) | ⬜ pending |
| 01-3 | 26-01 | 1 | SSE-03 | RED credential scrub (real registry) | unit | `rtk pytest tests/test_api_observability.py -k "credential or last_error or scrubbed"` (expect RED) | ⬜ pending |
| 02-1 | 26-02 | 2 | SSE-03 / OBS-08 | confirmed-orders query + log filter | unit | `rtk pytest tests/test_models.py -k confirmed_orders -x` | ⬜ pending |
| 02-2 | 26-02 | 2 | SSE-03 | async-safe history + price-history reads | unit (TestClient) | `rtk pytest tests/test_api_observability.py -k "history or price" -x` | ⬜ pending |
| 02-3 | 26-02 | 2 | OBS-08 / SSE-03 | /api/logs level/search/n + to_thread | unit (TestClient) | `rtk pytest tests/test_api_observability.py -k logs -x` | ⬜ pending |
| 03-1 | 26-03 | 2 | SSE-03 | last_error scrubbed to class name | unit | `rtk pytest tests/test_api_observability.py -k "last_error or scrubbed" -x` | ⬜ pending |
| 03-2 | 26-03 | 2 | SSE-03 | supervise() records scrubbed last_error | unit | `rtk pytest tests/ -k "orchestrator or supervise or health" -x` | ⬜ pending |
| 03-3 | 26-03 | 2 | SSE-03 | credential-leak guard end-to-end | unit (TestClient) | `rtk pytest tests/test_api_observability.py -k "credential or leak or scrubbed" -x` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

> Note: test file name reconciled to `tests/test_api_observability.py` (VALIDATION.md is the
> source of truth for test naming; RESEARCH/PATTERNS used `tests/test_web_api.py` — superseded).

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

All Wave 0 items are authored in Plan 26-01 (Wave 1 of execution). Implementation Plans 26-02 and
26-03 (Wave 2) turn them GREEN. Set `wave_0_complete: true` after Plan 26-01 lands RED.

*Existing pytest + TestClient infrastructure covers the rest.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live `curl` against a running uvicorn | OBS-08/SSE-03 | TestClient covers contract; live curl is an operator smoke check | `python main.py` web mode, then `curl localhost:8000/api/history` |

*TestClient tests are curl-equivalent and cover all four criteria automatically; the live curl is an optional operator smoke check (UAT debt per autonomous policy).*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** planner-approved 2026-06-25
