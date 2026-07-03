---
phase: 33
slug: config-refactor
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-02
---

# Phase 33 — Validation Strategy

> Real code refactor of `core/config_schema.py` + `core/orchestrator.py` (`_get_plugin_sleep`) + 5 community plugins. Behavior-preservation for the 5 community plugins is the hard constraint and MUST be proven by test; the Amazon/BestBuy jitter activation (Option A) is a documented, test-updated behavior change.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml / pytest.ini (existing) |
| **Quick run command** | `.venv\Scripts\python.exe -m pytest tests/test_config_schema.py tests/test_orchestrator_jitter.py -q` |
| **Full suite command** | `.venv\Scripts\python.exe -m pytest -q` |
| **Estimated runtime** | ~50 seconds |

*Always use the venv python, never `rtk pytest`.*

---

## Sampling Rate

- **After every task commit (RED→GREEN):** run the two targeted config/jitter test files
- **After CFG-01 completes, before CFG-02:** full suite green (CFG-01 must land clean before CFG-02 builds on it)
- **Before verify:** full suite green (baseline 889 passed, 2 skipped, plus new tests)

---

## Per-Requirement Verification Map

| Requirement | Truth | Test Type | Automated Command | Notes |
|-------------|-------|-----------|-------------------|-------|
| CFG-01 | New-style config (delay_seconds/delay_jitter) loads | unit | test in test_config_schema.py asserts canonical fields parse | |
| CFG-01 | Legacy config (min_delay/max_delay) loads via shim | unit | test loads old-style YAML/dict → asserts delay_seconds==min_delay, delay_jitter==max_delay-min_delay | THE back-compat proof |
| CFG-01 | Community-plugin effective delay distribution preserved | unit | test asserts `_get_plugin_sleep` on a converted community config yields uniform(min,max) equivalent (delay_seconds+uniform(0,jitter)) | behavior-preserving (hard) |
| CFG-01 | Amazon/BestBuy jitter activation (Option A) | unit | UPDATE `tests/test_orchestrator_jitter.py::test_fallback_for_amazon_shaped_config` to assert 30-40s jittered range, not flat 30s | documented behavior change |
| CFG-02 | New undeclared plugin section loads + validates | unit | fixture/test plugin declares a new platforms.<key> section; AppConfig loads it with core/config_schema.py UNTOUCHED (assert via extra="allow" passthrough + get_platform_config helper) | zero core edits |
| CFG-02 | Existing 7 platforms keep strict validation | unit | invalid field on a KNOWN platform still raises; only NEW/unknown platform keys are permissive | extra="allow" must not weaken known-platform validation |
| all | No regression | full | `.venv\Scripts\python.exe -m pytest -q` green (>= 889 + new) | |

---

## Wave 0 Requirements

- [ ] `tests/test_config_schema.py` — new cases: legacy-shim load, new-style load, new undeclared-plugin section validation, known-platform strictness
- [ ] `tests/test_orchestrator_jitter.py` — updated `test_fallback_for_amazon_shaped_config` (jitter activation) + community-plugin distribution-preservation case
- [ ] Existing config-schema infrastructure otherwise covers the phase

---

## Manual-Only Verifications

| Behavior | Requirement | Why | Instructions |
|----------|-------------|-----|--------------|
| Live Amazon/BestBuy poll cadence now jittered (30-40s) | CFG-01 (Option A) | Timing observable only against a live run | Operator UAT: confirm Amazon/BestBuy availability polling is jittered, not flat 30s, and no detection/rate issues result |

---

## Validation Sign-Off

- [ ] Legacy + new config both load (shim proven)
- [ ] Community-plugin delay distribution preserved (test-proven)
- [ ] Amazon/BestBuy jitter-activation test updated + green
- [ ] New undeclared plugin section validates with core schema untouched
- [ ] Known-platform strict validation intact
- [ ] Full suite green (>= 889 + new)
- [ ] Operator-UAT item recorded (Amazon/BestBuy poll cadence change)
- [ ] `nyquist_compliant: true` set after execution

**Approval:** pending
