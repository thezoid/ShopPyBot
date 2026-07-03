---
phase: 34
slug: feature-completion
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-02
---

# Phase 34 — Validation Strategy

> Feature phase: a logging-tag change (FC-01), a `/api/logs` param + log-filter UI (FC-01), and a pure analytics function + read-only endpoint + dashboard view (FC-02). The pure `compute_analytics` function is the highest-value unit-test surface; the tag mechanism + endpoint are integration-tested; the UI reuses existing components (no new visual test infra).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (needs `.[web]` + httpx for the API tests) |
| **Config file** | pyproject.toml / pytest.ini (existing) |
| **Quick run command** | `.venv\Scripts\python.exe -m pytest tests/test_analytics.py tests/test_api_observability.py -q` |
| **Full suite command** | `.venv\Scripts\python.exe -m pytest -q` |
| **Estimated runtime** | ~50 seconds |

*Always use the venv python, never `rtk pytest`. The web/API tests require `pip install -e .[web]` + httpx.*

---

## Sampling Rate

- **After every task commit (RED→GREEN):** run the targeted analytics/API/logger tests
- **After FC-01, before FC-02 UI:** full suite green (the tag format change must not break existing log/API tests)
- **Before verify:** full suite green (baseline 901 passed, 2 skipped + new tests)

---

## Per-Requirement Verification Map

| Requirement | Truth | Test Type | Automated Command | Notes |
|-------------|-------|-----------|-------------------|-------|
| FC-01 | Every newly-written line carries a `[plugin]` tag | unit | writeLog with set_log_plugin("amazon") → line contains `[amazon]`; with no plugin set → `[core]` sentinel | contextvar mechanism |
| FC-01 | Level parsing/color still works | unit | line still starts `[LEVEL]`; read_logs_filtered level filter + JS `/^\[(\w+)\]/` unaffected | format-compat guard |
| FC-01 | `/api/logs?plugin=X` returns only X's lines | integration | request with plugin param returns only `[X]`-tagged lines; absent=all; composes with level+search (AND) | update the 2 arity asserts in test_api_observability.py |
| FC-02 | success_rate correct vs fixture | unit | compute_analytics(fixture_rows, platform_of) → exact success_rate (confirmed/attempted) overall + per-plugin | pure function, exact assert |
| FC-02 | time_to_checkout correct vs fixture | unit | exact avg(confirmed_at − place_order_attempted_at) with known sample_size | pure function |
| FC-02 | No orders → no div-by-zero | unit | compute_analytics([], ...) returns safe zeros/None, not ZeroDivisionError | edge case |
| FC-02 | `/api/analytics` aggregate-only, no link leak | integration | response JSON contains metrics, NO `link`/credential fields | read-only boundary |
| all | No regression | full | `.venv\Scripts\python.exe -m pytest -q` green (>= 901 + new) | |

---

## Wave 0 Requirements

- [ ] `tests/test_analytics.py` (new) — compute_analytics fixture cases (success_rate, time_to_checkout, empty)
- [ ] `tests/test_api_observability.py` — updated arity asserts + `/api/logs` plugin-filter case + `/api/analytics` case
- [ ] logger tag test (writeLog contextvar → tag / sentinel)
- [ ] Existing web-test infra (`.[web]` + httpx) covers the endpoint tests

---

## Manual-Only Verifications

| Behavior | Requirement | Why | Instructions |
|----------|-------------|-----|--------------|
| Log-filter dropdown + analytics cards render correctly in the dashboard (both themes) | FC-01/FC-02 | Visual fidelity to the v4.1 design system is browser-observable | Operator: open dashboard, use the plugin filter, view analytics cards+table in light+dark themes |

---

## Validation Sign-Off

- [ ] Every newly-written log line tagged (contextvar + sentinel), level parsing intact
- [ ] `/api/logs` plugin filter returns only matching lines; existing arity asserts updated
- [ ] compute_analytics correct vs fixture (success_rate + time_to_checkout + empty), pure/testable
- [ ] `/api/analytics` aggregate-only (no link/credential leak)
- [ ] UI reuses existing components (near-zero new CSS); no Node/CDN
- [ ] Full suite green (>= 901 + new)
- [ ] `nyquist_compliant: true` set after execution

**Approval:** pending
