---
phase: 03-community-documentation
plan: 04
subsystem: documentation
tags: [documentation, github, templates, DOCS-05]
requires: [CONTRIBUTING.md, SECURITY.md]
provides:
  - .github/PULL_REQUEST_TEMPLATE.md
  - PR checklist enforcing ABC compliance, naming, tests, risk docs, secret hygiene
affects: []
tech_stack:
  added: []
  patterns:
    - GitHub PR template at .github/PULL_REQUEST_TEMPLATE.md
    - Substring-locked tests in tests/test_docs.py for documentation drift
key_files:
  created:
    - .github/PULL_REQUEST_TEMPLATE.md
  modified:
    - tests/test_docs.py
decisions:
  - Use relative links (../CONTRIBUTING.md, ../SECURITY.md) so they resolve from .github/
  - Use HTML comments for hidden hints to PR authors (GitHub renders them invisible)
  - Lowercase "anti-detection" to match grep-style substring tests verbatim
metrics:
  duration_minutes: 4
  tasks_completed: 2
  files_created: 1
  files_modified: 1
  tests_added: 11
  completed: 2026-05-14
---

# Phase 3 Plan 04: PR Template Summary

Shipped .github/PULL_REQUEST_TEMPLATE.md satisfying DOCS-05: a checklist-driven PR template that enforces ABC compliance, naming convention, test presence, anti-detection risk disclosure, and secret hygiene, with forward-links to CONTRIBUTING.md and SECURITY.md.

## What Was Built

- `.github/PULL_REQUEST_TEMPLATE.md` (59 lines): Pre-filled PR body with sections
  - Summary (why-not-just-what prompt)
  - Type of change (six commit-convention checkboxes)
  - For plugin contributions (conditional block with HTML-comment hint)
    - ABC Compliance (RetailerPlugin subclass, check_availability, auto_buy, domain_pattern: list[str], one class per file)
    - Naming convention (shopbot_plugin_<platform>.py + <Platform>Plugin class name)
    - Tests (test_plugins_<platform>.py, build_driver mocking, pytest clean)
    - Risk documentation (anti-detection in docstring, SECURITY.md row update)
  - Security and credentials (no secrets/PII/CVVs, no config.yml with real values, SECURITY.md disclosure flow)
  - Manual test plan
- 11 new substring tests in `tests/test_docs.py` under "DOCS-05 (Plan 03-04): PR template"

## Commits

| Hash    | Type | Description                                          |
| ------- | ---- | ---------------------------------------------------- |
| e5931f0 | test | RED tests for PR template (DOCS-05)                  |
| a40d453 | feat | Add PR template enforcing DOCS-05 checklist          |

## Verification

- `rtk pytest tests/test_docs.py -q` -> 74 passed (including all 11 new DOCS-05 tests)
- `rtk grep -c "ABC Compliance" .github/PULL_REQUEST_TEMPLATE.md` -> 1 match
- `rtk grep -n "—" .github/PULL_REQUEST_TEMPLATE.md` -> 0 matches (no em dashes)
- No horizontal-rule lines in template body (verified by test_pr_template_no_horizontal_rule)

## Deviations from Plan

None substantive. One micro-adjustment during GREEN:

1. **Casing fix for "anti-detection"**: The plan interface block showed "Anti-detection risk declared..." (capitalized), but the substring test asserted lowercase "anti-detection". Changed the template to lowercase "anti-detection risk declared..." so the literal substring matches. This is a wording-only tweak, no semantic change.

## Pre-existing Out-of-Scope Failures

Full `pytest -q` shows pre-existing failures unrelated to this plan (missing `pygame` and `selenium` in the worktree's environment, sqlite path errors in test_models). Not introduced by this plan; not in scope to fix here. Tracked elsewhere.

## Requirements Satisfied

- DOCS-05: PR template enforces ABC compliance, naming, tests, risk docs, secret hygiene; links CONTRIBUTING.md and SECURITY.md

## Self-Check: PASSED

- FOUND: .github/PULL_REQUEST_TEMPLATE.md
- FOUND: tests/test_docs.py (extended, not overwritten)
- FOUND commit e5931f0 (RED tests)
- FOUND commit a40d453 (GREEN template)
- All 11 new DOCS-05 substring tests pass
- No em dashes, no horizontal rules in template body
