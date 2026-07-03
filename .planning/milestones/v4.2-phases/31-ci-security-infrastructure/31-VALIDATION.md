---
phase: 31
slug: ci-security-infrastructure
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-02
---

# Phase 31 — Validation Strategy

> Per-phase validation contract. This is an infrastructure/CI phase — most "truths" are verified by a clean scan, a green CI run, or YAML validity, not by new unit tests. The existing pytest suite is the regression guard for the dependency bumps.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml / pytest.ini (existing) |
| **Quick run command** | `pytest -q -x` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~50 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest -q -x` (regression guard for dependency bumps)
- **After every plan wave:** Run `pytest -q` (full suite must stay green; baseline 887 passed, 2 skipped)
- **Before verify:** Full suite green + gitleaks clean + workflow YAML valid + dependabot.yml valid
- **Max feedback latency:** ~50 seconds

---

## Per-Task Verification Map

| Requirement | Secure Behavior | Test Type | Automated Command | CI/Manual |
|-------------|-----------------|-----------|-------------------|-----------|
| RH-01 | No real secret tracked; scan clean | scan | `gitleaks detect --source . --redact` exits 0 (0 real findings; test fixture allowlisted) | local + CI job |
| RH-01 | .gitignore excludes sensitive paths | assertion | `git check-ignore config.yml data/x.db` succeeds AND `git ls-files` shows none tracked | local |
| RH-04 | CodeQL workflow uses supported action versions | assertion | workflow YAML contains `checkout@v6`, `codeql-action/*@v4`, no `@v1`/`@v2` | local (YAML) |
| RH-04 | CodeQL run green | CI | `gh run list --workflow=codeql` shows success on pushed branch | CI (post-push) |
| RH-05 | dependabot.yml exists + valid | assertion | `.github/dependabot.yml` parses; has pip + github-actions ecosystems | local (YAML) |
| RH-05 | 7 alerts remediated | assertion | requirements.txt has cryptography==49.0.0, pydantic-settings==2.14.2; pyproject [web] has jinja2==3.1.6 | local + CI (queue drains post-push) |
| RH-05 | No regression from bumps | unit | `pytest -q` green (>= 887 passed) | local |

---

## Wave 0 Requirements

*Existing pytest infrastructure covers regression validation for the dependency bumps. No new test stubs required — RH-01/04/05 are verified by scan/CI/YAML assertions, not new unit tests.*

---

## Manual-Only / CI-Only Verifications

| Behavior | Requirement | Why Not Local-Unit | Instructions |
|----------|-------------|--------------------|--------------|
| CodeQL Actions run turns green | RH-04 | Runs on GitHub-hosted runner post-push | After push: `gh run list --workflow=codeql`, confirm latest = success |
| Dependabot open-alert queue drains to 0 | RH-05 | GitHub recomputes alerts against the default branch after merge | After push: `gh api /repos/thezoid/ShopPyBot/dependabot/alerts?state=open` returns empty |

*These are CI-verification debt in an autonomous session if the runner/gh is unavailable — recorded, not blocking (code-complete is the DoD).*

---

## Validation Sign-Off

- [ ] Dependency bumps applied and pytest green
- [ ] gitleaks clean (test fixture allowlisted, zero real findings)
- [ ] CodeQL + gitleaks workflow YAML valid, no retired action versions
- [ ] dependabot.yml valid (pip + github-actions)
- [ ] `nyquist_compliant: true` set after execution
- [ ] CI-only checks (CodeQL green, alert queue drained) confirmed post-push or logged as CI debt

**Approval:** pending
