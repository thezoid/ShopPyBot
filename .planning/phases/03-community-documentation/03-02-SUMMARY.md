---
phase: 03-community-documentation
plan: 02
subsystem: documentation
tags: [documentation, security, disclosure]
requires: []
provides:
  - SECURITY.md responsible disclosure policy
  - Per-platform TOS/legal/anti-detection risk register
  - Credential hygiene guidance
affects:
  - SECURITY.md
  - tests/test_docs.py
tech-stack:
  added: []
  patterns: [TDD RED/GREEN]
key-files:
  created:
    - SECURITY.md
  modified:
    - tests/test_docs.py
decisions:
  - "Use literal `<TODO: set security contact>` placeholder rather than guessing an email"
  - "Anti-detection difficulty disclosed in SECURITY.md, not duplicated in CONTRIBUTING.md"
metrics:
  duration: ~10 min
  completed: 2026-05-14
---

# Phase 3 Plan 2: SECURITY.md Summary

Shipped SECURITY.md covering DOCS-03: responsible disclosure policy, per-platform TOS/legal risk register with anti-detection difficulty, and credential hygiene guidance referencing Phase 1 SEC-01 (env vars) and SEC-02 (getpass for CVV).

## What Was Built

- `SECURITY.md` (102 lines) at repo root with five sections: Responsible Disclosure, Supported Versions, Reporting Bugs vs Security Issues, Known TOS and Legal Risks per Platform, Credential Hygiene, Out of Scope.
- Responsible disclosure offers two private channels: literal `<TODO: set security contact>` email placeholder and GitHub Security Advisories link (`/security/advisories/new` on the upstream repo).
- Per-platform risk table enumerates all seven platforms (Amazon, BestBuy, Walmart, Target, GameStop, Square Enix, NewEgg) with TOS risk and anti-detection difficulty. Walmart called out for PerimeterX / HUMAN Security; Target called out for Akamai Bot Manager.
- Credential Hygiene section reinforces: env-var-only credentials, getpass for CVV, gitignored `config.yml`, no `from config import config`, rotate any leaked secret.
- 10 new tests in `tests/test_docs.py` under a `DOCS-03 (Plan 03-02): SECURITY.md` section header. All pass.

## Tasks Completed

| Task | Name                                  | Commit  | Files                          |
| ---- | ------------------------------------- | ------- | ------------------------------ |
| 1    | RED tests for SECURITY.md             | fd2d561 | tests/test_docs.py             |
| 2    | Ship SECURITY.md (GREEN)              | aa1e9cd | SECURITY.md                    |

## Verification

- `rtk pytest tests/test_docs.py -q`: 46 passed, 0 failed (10 new DOCS-03 tests green).
- `rtk grep -c "Responsible Disclosure" SECURITY.md`: 2 matches.
- `rtk grep -c "PerimeterX" SECURITY.md`: 1 match.
- `rtk grep -n "—" SECURITY.md`: 0 matches (no em dashes).
- No horizontal-rule lines (`---`/`***`/`___`) in body content.

## Deviations from Plan

None. Plan executed exactly as written. The `<TODO: set security contact>` placeholder decision was already locked by the planner.

## Deferred / Out of Scope

Pre-existing test collection failures in `tests/test_utils.py` (missing `pygame`) and `tests/test_driver_setup.py` (missing `selenium`), plus `tests/test_models.py` sqlite write errors. These are environment issues unrelated to DOCS-03 and predate this plan. Not fixed (scope boundary).

## TDD Gate Compliance

- RED gate: `test(03-02): RED tests for SECURITY.md (DOCS-03)` (fd2d561) confirmed 10 failures.
- GREEN gate: `feat(03-02): add SECURITY.md (DOCS-03)` (aa1e9cd) made all 10 pass.
- REFACTOR: not needed.

## Self-Check: PASSED

- FOUND: SECURITY.md
- FOUND: tests/test_docs.py (DOCS-03 section appended without overwriting prior content)
- FOUND commit fd2d561
- FOUND commit aa1e9cd
