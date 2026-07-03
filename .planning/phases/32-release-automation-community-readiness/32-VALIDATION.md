---
phase: 32
slug: release-automation-community-readiness
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-02
---

# Phase 32 — Validation Strategy

> Release-automation + docs phase. Truths are verified by file assertions, config/YAML/JSON validity, and grep, not by new unit tests. The existing pytest suite is a no-regression guard (this phase touches no Python runtime code except the pyproject version line).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml / pytest.ini (existing) |
| **Quick run command** | `.venv\Scripts\python.exe -m pytest -q -x` |
| **Full suite command** | `.venv\Scripts\python.exe -m pytest -q` |
| **Estimated runtime** | ~50 seconds |

*Always use the venv python, never `rtk pytest` (resolves to a broken Python 3.14).*

---

## Sampling Rate

- **After the pyproject version bump:** `.venv\Scripts\python.exe -m pytest -q` (confirm `shoppybot` entry point + package still import; baseline 889 passed, 2 skipped)
- **After release-please/docs changes:** config/JSON/YAML validity + grep assertions (no test run needed for pure-docs edits)
- **Before verify:** all assertions below pass

---

## Per-Requirement Verification Map

| Requirement | Truth | Test Type | Automated Command | CI/Manual |
|-------------|-------|-----------|-------------------|-----------|
| RH-03 | Single version source == 2.0.0 | assertion | `pyproject.toml [project].version == "2.0.0"`; grep repo (excl .venv) shows no other version source | local |
| RH-02 | release-please config valid + seeded | assertion | `.release-please-manifest.json` == `{".":"2.0.0"}`; `release-please-config.json` has `release-type: python`; `release-please.yml` uses `googleapis/release-please-action@v5` + `permissions: contents/pull-requests write` | local (JSON/YAML parse) |
| RH-02 | release-please Actions run succeeds | CI | `gh run list --workflow=release-please` shows success | CI (post-push; gated on operator Actions-allowlist toggle) |
| RH-06 | README claims match reality | assertion | README contains: all 7 platform names; `pip install -e .[web]`; `shoppybot`; `Python 3.11`; real clone URL `github.com/thezoid/ShopPyBot`; no dead badges (each badge target workflow exists) | local (grep + cross-check) |
| RH-07 | Zero placeholder occurrences | assertion | `grep -r "SECURITY_CONTACT_PLACEHOLDER@example.com"` over tracked non-`.planning` files returns 0; SECURITY.md + CODE_OF_CONDUCT.md point to PVR flow, no email | local (grep) |
| all | No pytest regression | unit | `.venv\Scripts\python.exe -m pytest -q` green (>= 889 passed) | local |

---

## Wave 0 Requirements

*Existing pytest infrastructure covers regression. No new test stubs — RH-02/03/06/07 verified by assertion/grep/JSON-validity, not new unit tests.*

---

## Manual-Only / CI-Only Verifications

| Behavior | Requirement | Why | Instructions |
|----------|-------------|-----|--------------|
| release-please Actions run green + opens a release PR | RH-02 | Runs on GitHub post-push; blocked until operator allowlists `googleapis/release-please-action@*` in Settings → Actions → General | After push + allowlist: `gh run list --workflow=release-please` |
| Private Vulnerability Reporting live | RH-07 | Requires operator to enable PVR in Settings → Security & analysis (one-time) | Operator toggles; SECURITY.md link then resolves |
| gitleaks/CodeQL third-party actions run | RH-01/RH-04 (carried) | Same Actions-allowlist gate blocks `gitleaks/gitleaks-action` (already `startup_failure`) | Operator allowlist unblocks |

*Two operator action items (Actions allowlist + PVR enable) are the only things between code-complete and full CI-green. Recorded as operator debt, not code gaps.*

---

## Validation Sign-Off

- [ ] pyproject version == 2.0.0; no other version source
- [ ] release-please config + manifest + workflow valid and seeded at 2.0.0
- [ ] README accurate (7 platforms, install/run, prereq, real URL, no dead badges)
- [ ] Zero placeholder occurrences in tracked non-`.planning` files
- [ ] pytest green (>= 889 passed)
- [ ] Operator action items documented (Actions allowlist, PVR enable)
- [ ] `nyquist_compliant: true` set after execution

**Approval:** pending
