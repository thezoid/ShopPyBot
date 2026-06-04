---
phase: 10
slug: optional-web-ui
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-04
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + fastapi.testclient.TestClient (web tests `pytest.importorskip("fastapi")`) |
| **Config file** | pyproject.toml (existing) |
| **Quick run command** | `pytest tests/test_web_*.py -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~35 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_web_*.py -q`
- **After every plan wave:** Run `pytest -q`
- **Before `/gsd:verify-work`:** Full suite green (282 baseline + new web tests; default `pip install .` run still green with web tests skipped)
- **Max feedback latency:** 35 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 1 | GUI-05 | [web] extra in pyproject; create_app(svc) factory + StaticFiles + Jinja2; handle_web serves it; CLI-04 stays green (fastapi only inside web/) | unit | `pytest tests/test_web_app.py tests/test_cli_no_fastapi.py -q` | ❌ W0 | ⬜ pending |
| 10-02-01 | 02 | 2 | GUI-06 | is_localhost() loopback detection; non-local --host prints stderr warning before serve + in-page banner; Origin/Host check on POSTs (403 on mismatch) | unit | `pytest tests/test_web_security.py -q` | ❌ W0 | ⬜ pending |
| 10-03-01 | 03 | 2 | GUI-02, GUI-04 | items list/add/remove + start/stop/status/logs routes via BotService only (MOD-02); web add/remove == CLI DB state (SC2 parity) | unit | `pytest tests/test_web_items.py tests/test_web_controls.py tests/test_web_mod02.py -q` | ❌ W0 | ⬜ pending |
| 10-04-01 | 04 | 3 | GUI-03 | credential routes show name+set/unset only; POST→CredentialStore.set; secret value absent from any response body, HTML, logs | unit | `pytest tests/test_web_credentials.py -q` | ❌ W0 | ⬜ pending |
| 10-05-01 | 05 | 3 | GUI-01 | config routes (test_mode, logging_level, notifier enables) mirror CLI allowlist; dashboard renders all 4 sections; UI = thin BotService adapter | unit | `pytest tests/test_web_config.py tests/test_web_dashboard.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Task IDs indicative — planner finalizes exact plan/task numbering.*

---

## Wave 0 Requirements

- [ ] `tests/test_web_app.py` — create_app factory + static/templates wiring + CLI-04 (fastapi absent) guard
- [ ] `tests/test_web_security.py` — is_localhost matrix, non-local warning, Origin/Host CSRF 403
- [ ] `tests/test_web_items.py`, `tests/test_web_controls.py` — routes via BotService; SC2 parity
- [ ] `tests/test_web_credentials.py` — no-secret-in-response guard (SC3)
- [ ] `tests/test_web_config.py`, `tests/test_web_dashboard.py` — config allowlist + dashboard render
- [ ] `tests/test_web_mod02.py` — AST guard: web/ doesn't import models/orchestrator/registry
- [ ] All web test modules begin with `pytest.importorskip("fastapi")` so default install runs skip them cleanly

*Existing pytest infrastructure covers framework; only new web test files + the [web] extra needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dashboard renders in a real browser without errors | GUI-01 / SC1 | TestClient asserts HTTP/HTML but not live browser rendering/JS polling | `pip install .[web]` then `shoppybot web`; open http://127.0.0.1:PORT; confirm all 4 sections render, status polls, no console errors |
| Live Start/Stop + log polling in browser | GUI-04 | JS polling + live BotService state can't be asserted headlessly | Click Start, observe status flip to Running and logs panel update without refresh; click Stop |

*Live-browser checks roll into Phase 11 verification matrix (Ubuntu + Windows).*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 35s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
