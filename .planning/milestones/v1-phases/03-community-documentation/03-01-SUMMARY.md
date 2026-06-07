---
phase: 03-community-documentation
plan: "01"
subsystem: community-docs
tags: [security, contributing, code-of-conduct, governance, documentation]
dependency_graph:
  requires: []
  provides: [SECURITY.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md]
  affects: [plugins/PLUGIN_DEV.md (linked from CONTRIBUTING), README.md (disclaimer mirrored)]
tech_stack:
  added: []
  patterns: [Contributor Covenant, Conventional Commits, responsible-disclosure, coordinated-disclosure]
key_files:
  created:
    - SECURITY.md
    - CONTRIBUTING.md
    - CODE_OF_CONDUCT.md
  modified: []
decisions:
  - "Placeholder email SECURITY_CONTACT_PLACEHOLDER@example.com used in SECURITY.md and CODE_OF_CONDUCT.md; maintainer must replace before launch"
  - "CONTRIBUTING.md links to plugins/PLUGIN_DEV.md for all ABC/how-to detail; no duplication"
  - "Risk table seeds amazon.com at high/high and bestbuy.com at medium/medium; Phase 6 platforms append rows"
metrics:
  duration: "~8 minutes"
  completed: "2026-06-03T13:14:59Z"
  tasks_completed: 2
  tasks_total: 2
---

# Phase 3 Plan 01: Community Governance Documents Summary

**One-liner:** Three repo-root governance docs establishing responsible disclosure (7-day ack, 90-day window, private advisory channel), a per-platform risk table (amazon.com high/high, bestbuy.com medium/medium), and a plugin submission checklist requiring ABC compliance, pytest coverage, and mandatory anti-detection risk declarations.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write SECURITY.md | 31e8600 | SECURITY.md |
| 2 | Write CONTRIBUTING.md and CODE_OF_CONDUCT.md | 69146f0 | CONTRIBUTING.md, CODE_OF_CONDUCT.md |

## Acceptance Criteria Verified

All six SECURITY.md criteria: PASS
- Private advisory channel (GitHub + placeholder email): present
- Placeholder clearly marked SECURITY_CONTACT_PLACEHOLDER@example.com: present
- Explicitly forbids public-issue disclosure: present
- Risk table with amazon.com and bestbuy.com rows (low/medium/high scale): present
- 7-day ack and 90-day coordinated disclosure: present
- Legal scope consistent with README disclaimer: present
- No em dashes, no horizontal-rule lines: confirmed

All CONTRIBUTING.md criteria: PASS
- Fork/branch/implement/test/PR workflow: present
- Conventional Commits, PEP8/snake_case, no-new-deps-without-justification: present
- Link to plugins/PLUGIN_DEV.md: present; ABC how-to not duplicated
- Plugin checklist: RetailerPlugin ABC, shopbot_plugin_* naming, domain_patterns, pytest + green suite, risk declaration (level + rationale in PR and module docstring), no secrets committed: all present
- No em dashes, no horizontal-rule lines: confirmed

CODE_OF_CONDUCT.md: PASS
- Contributor Covenant reference and link: present
- Placeholder contact consistent with SECURITY.md: present
- No em dashes, no horizontal-rule lines: confirmed

## Deviations from Plan

None. Plan executed exactly as written.

## Known Stubs

SECURITY_CONTACT_PLACEHOLDER@example.com appears in SECURITY.md and CODE_OF_CONDUCT.md. This is intentional and documented in the plan. The maintainer must replace it with a real verified address before the repository goes public. It is not a data stub that blocks plan goals; the disclosure channel (GitHub private advisory) is fully functional without it.

## Threat Flags

No new security-relevant surface introduced. All threat mitigations from the plan's threat model are implemented:
- T-03-01: GitHub private advisory channel documented; public-issue disclosure explicitly forbidden.
- T-03-02: "No secrets/credentials committed; env vars only" reinforced in CONTRIBUTING.md plugin checklist.
- T-03-03: Placeholder contact is clearly marked; no real address invented.

## Self-Check: PASSED
