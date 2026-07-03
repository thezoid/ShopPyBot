---
phase: 35
slug: audit-fixes-doc-hygiene-cleanup
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-02
---

# Phase 35 — Validation Strategy

> Trailing cleanup: 3 small code fixes (AF-01/02/03) + 6 frontmatter reconciliations (DH-01/02/03). The AF fixes get unit/integration tests; the DH edits are verified by re-reading frontmatter + (ideally) re-running the milestone audit cross-reference.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (web/API tests need `.[web]` + httpx) |
| **Config file** | pyproject.toml / pytest.ini (existing) |
| **Quick run command** | `.venv\Scripts\python.exe -m pytest tests/test_health.py tests/test_cli_status.py tests/test_web_dashboard.py -q` |
| **Full suite command** | `.venv\Scripts\python.exe -m pytest -q` |
| **Estimated runtime** | ~50 seconds |

*Always use the venv python, never `rtk pytest`.*

---

## Sampling Rate

- **After each AF fix (RED→GREEN):** run the targeted test file(s)
- **After AF-02:** run the FULL suite (7 files touch last_heartbeat — catch any lockstep miss, esp. core/cli/status.py)
- **Before verify:** full suite green (baseline 932 passed, 2 skipped + new); DH frontmatter re-read

---

## Per-Requirement Verification Map

| Requirement | Truth | Test Type | Automated Command | Notes |
|-------------|-------|-----------|-------------------|-------|
| AF-01 | SSR remove works without JS (failed loadItems) | integration | POST /items/remove removes an item; test simulates failed fetch path, asserts SSR remove still functions | new zero-JS route + check_origin |
| AF-02 | raw last_heartbeat absent from get_status AND SSE frame | unit | assert "last_heartbeat" NOT in get_status() dict + SSE status frame; heartbeat_age_secs present | fix at core/health.py:91 |
| AF-02 | cli status still shows age (no "never" regression) | unit | core/cli/status.py reads heartbeat_age_secs, not raw field; test_cli_status green | LOCKSTEP fix — do not miss |
| AF-03 | escHtml gone | assertion | `grep -r "escHtml" web/` returns 0 | dead-code removal |
| DH-01 | v4.1 VALIDATION 25/26/27 = validated/wave_0_complete true | assertion | re-read frontmatter; matches actual passing suites (763/776/785 passed) | reflect reality only |
| DH-02 | audit reports OBS-01/02/03/04/06/09 VERIFIED | assertion | Phase 28 SUMMARY files carry requirements: per the research mapping; re-run milestone audit cross-ref (or grep the summaries) confirms the 6 OBS reqs report VERIFIED | 28-01/02/03/04 (+ 27/29 own reqs per spec wording) |
| DH-03 | v4.0 VALIDATION 18-24 nyquist_compliant true | assertion | re-read frontmatter; v4.0-MILESTONE-AUDIT explicitly recommends this flip (755 passed) | reflect reality only |
| all | No regression | full | `.venv\Scripts\python.exe -m pytest -q` green (>= 932 + new) | |

---

## Wave 0 Requirements

- [ ] `tests/test_web_dashboard.py` (or a routes test) — AF-01 failed-fetch SSR remove case
- [ ] `tests/test_health.py` / `test_service.py` — AF-02 raw-field-absent assertions (both surfaces)
- [ ] `tests/test_cli_status.py` — AF-02 lockstep (cli reads derived age)
- [ ] Existing infra otherwise covers AF-03 (grep) + DH (frontmatter re-read)

---

## Manual-Only Verifications

| Behavior | Requirement | Why | Instructions |
|----------|-------------|-----|--------------|
| SSR remove button renders + posts correctly in the browser (JS disabled) | AF-01 | Browser-observable graceful degradation | Operator (optional): disable JS, click remove, confirm item removed |

---

## Validation Sign-Off

- [ ] AF-01 SSR remove works on failed-fetch (test-proven)
- [ ] AF-02 raw last_heartbeat absent from both surfaces; cli lockstep fixed; full suite green
- [ ] AF-03 escHtml grep-0
- [ ] DH-01/02/03 frontmatter reconciled to ACTUAL passing status; audit cross-ref reports the 6 OBS reqs VERIFIED
- [ ] Full suite green (>= 932 + new)
- [ ] `nyquist_compliant: true` set after execution

**Approval:** pending
