---
phase: 17
slug: test-hardening
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-09
---

# Phase 17 — Validation Strategy

> Per-phase validation contract. This phase IS test hardening — the deliverables are tests; validation is that they (a) pass, (b) execute the previously-uncovered target lines/branches, and (c) the full suite stays green.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-asyncio (asyncio_mode=auto) + pytest-cov 7.1.0 |
| **Config file** | pyproject.toml (existing) |
| **Quick run command** | `python -m pytest -q <touched test file>` |
| **Full suite command** | `python -m pytest` |
| **Coverage check** | `python -m pytest --cov=core --cov=models --cov=plugins --cov=notifications --cov-report=term-missing` |
| **Estimated runtime** | ~40 seconds |

---

## Sampling Rate

- **After every task/plan:** run the touched `tests/test_*.py -q`
- **After the phase:** full `python -m pytest` + a `--cov` run; confirm the PR-01 migration path, captcha error branches, registry isolation branches, orchestrator price guards, and the `_handle_ban` 53→55 branch are now executed.
- **Before `/gsd:verify-work`:** full suite green; no new failures vs the 529-passed baseline (count rises with the ~19 new tests).

---

## Per-Plan Verification Map

| Plan | Wave | Requirement | Tests added | Automated Command |
|------|------|-------------|-------------|-------------------|
| 17-01 | 1 | STAB-03 (proxy) | PX-01..PX-06 | `python -m pytest -q tests/test_proxy_config.py tests/test_stealth.py tests/test_registry.py` |
| 17-02 | 1 | STAB-03 (captcha) | CP-01..CP-05 | `python -m pytest -q tests/test_captcha.py` |
| 17-03 | 1 | STAB-03 (price + get_price integration) | PR-01..PR-04, AB-01, AB-02 | `python -m pytest -q tests/test_price_history.py tests/test_price_alert.py` |
| 17-04 | 1 | STAB-03 (plugin ABC) | AB-03, AB-04 | `python -m pytest -q tests/test_plugin_base.py` |

*Plans touch disjoint test files. Planner refines into per-task rows.*

---

## Wave 0 Requirements

*All target test files already exist; this phase EXTENDS them. No scaffolding. No new deps (pytest-cov already installed).*

---

## Manual-Only Verifications

*None — this is a pure test-authoring phase. All new tests are deterministic and CI-runnable. (Live-environment manual checks for the v3.0 FEATURES themselves remain tracked in the per-phase HUMAN-UAT files for phases 12-16; they are not in scope here.)*

---

## Validation Sign-Off

- [ ] Each of the 4 STAB-03 criteria maps to named passing tests
- [ ] The v2.0-schema migration fixture test (PR-01) exists and passes
- [ ] Previously-uncovered target lines/branches are now executed (verified via --cov)
- [ ] Full `python -m pytest` green; no regressions
- [ ] No new dependency; no legacy/e2e tests added
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
