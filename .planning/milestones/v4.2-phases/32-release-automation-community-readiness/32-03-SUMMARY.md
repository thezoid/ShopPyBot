---
phase: 32-release-automation-community-readiness
plan: 03
subsystem: docs
tags: [security-policy, code-of-conduct, github-private-vulnerability-reporting, community-docs]

# Dependency graph
requires:
  - phase: 32-release-automation-community-readiness (32-01, 32-02)
    provides: release-please automation seed + accurate README, landed in the same phase before this final community-doc fix
provides:
  - SECURITY.md vulnerability disclosure routed exclusively through GitHub Private Vulnerability Reporting (advisories/new)
  - CODE_OF_CONDUCT.md enforcement-contact routed through the same PVR channel
  - Zero live occurrences of SECURITY_CONTACT_PLACEHOLDER@example.com in tracked non-.planning files
affects: [community-readiness, first-public-release-checklist]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Vulnerability/conduct-report intake delegated entirely to GitHub's built-in Private Vulnerability Reporting flow — no app-owned inbox, no published maintainer email"

key-files:
  created: []
  modified:
    - SECURITY.md
    - CODE_OF_CONDUCT.md

key-decisions:
  - "No email address substituted for the placeholder under any circumstance (D-RH-07 locked) — GitHub PVR (security/advisories/new) is the sole reporting channel for both vulnerability and conduct reports"
  - "Operator note added inline in SECURITY.md (not just SUMMARY): Private Vulnerability Reporting must be enabled once in repo Settings -> Security -> 'Private vulnerability reporting' for the advisories/new link to resolve; not toggled by this automation"
  - ".planning/ historical occurrences of the placeholder string (10 files) intentionally left untouched — they are the project's own decision audit trail, not live consumer-facing docs"

patterns-established: []

requirements-completed: [RH-07]

# Metrics
duration: 5min
completed: 2026-07-02
---

# Phase 32 Plan 03: Real Security Contact via GitHub Private Vulnerability Reporting Summary

**SECURITY.md and CODE_OF_CONDUCT.md now route all vulnerability and conduct reports exclusively through GitHub's Private Vulnerability Reporting flow (advisories/new) — zero placeholder occurrences, zero email addresses published, in tracked non-.planning files.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-07-02T21:43:00Z (approx)
- **Completed:** 2026-07-02T21:47:57Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- SECURITY.md's "Reporting a Vulnerability" section rewritten to a single supported channel (GitHub PVR at `security/advisories/new`), removing the dead placeholder-email item entirely, with an inline operator note about the one-time repo Settings toggle required for the link to work.
- CODE_OF_CONDUCT.md's Enforcement section rewritten to route conduct reports through the same PVR flow, replacing the placeholder-email line.
- Confirmed via `git grep "SECURITY_CONTACT_PLACEHOLDER@example.com" -- ':!.planning'` that zero occurrences remain in tracked non-`.planning` files (RH-07's success criterion), while the 10 historical `.planning/` files referencing the placeholder as audit trail were left untouched.
- Full pytest suite remains green at baseline: 889 passed, 2 skipped, no regressions from the docs-only change.

## Task Commits

Each task was committed atomically:

1. **Task 1: Replace the SECURITY.md contact with GitHub Private Vulnerability Reporting** - `fb464d0` (docs)
2. **Task 2: Replace the CODE_OF_CONDUCT.md contact and verify zero placeholders repo-wide** - `aef6139` (docs)

**Plan metadata:** committed separately after this SUMMARY.

## Files Created/Modified
- `SECURITY.md` - "Reporting a Vulnerability" section: removed the "Direct email" placeholder item; single-channel GitHub PVR instructions plus a one-time operator-enable note
- `CODE_OF_CONDUCT.md` - Enforcement section: replaced the placeholder-email contact with the same GitHub PVR flow

## Decisions Made
- No email address substituted for the placeholder anywhere (D-RH-07 locked decision) — GitHub Private Vulnerability Reporting (`https://github.com/thezoid/ShopPyBot/security/advisories/new`) is the sole channel for both security vulnerability and code-of-conduct reports.
- The PVR-enable operator note lives inline in SECURITY.md (in addition to this SUMMARY) so it's visible to anyone reading the live doc, not just phase history.
- `.planning/` historical occurrences of the placeholder (10 files: PLAN/SUMMARY/VERIFICATION/CONTEXT/REQUIREMENTS/ROADMAP records) were intentionally left untouched — rewriting them would falsify the project's own decision audit trail, per 32-RESEARCH.md Pitfall 5.

## Deviations from Plan

None - plan executed exactly as written. Both tasks followed the exact recommended replacement wording from 32-RESEARCH.md (lines 259-304).

## Issues Encountered

None. The `rtk` shell wrapper's grep fallback choked on an ERE-only pattern (`{2,}` quantifier) for the "no email published" acceptance check, producing a spurious tool error rather than a true negative; re-verified the same check directly with the Grep tool (PCRE-compatible) and confirmed zero email-shaped matches in both files. No code or doc change resulted — this was a verification-tooling quirk, not a defect in the edited files.

## Operator Action Item

**Private Vulnerability Reporting must be enabled once in repo Settings -> Security -> "Private vulnerability reporting"** for the `security/advisories/new` link in SECURITY.md and CODE_OF_CONDUCT.md to actually resolve to a working report form. This is a one-time GitHub repo setting; it is not toggled by this automation (per CONTEXT.md and 32-RESEARCH.md's explicit scoping — same category as the RH-02 Actions-permissions allowlist gate, both operator-gated repo Settings changes). Until enabled, the advisories/new URL will 404 for reporters.

## User Setup Required

None - no external service configuration required beyond the operator action item above (a one-time GitHub repo Settings toggle, not a code/env change).

## Next Phase Readiness

- Phase 32 (Release Automation & Community Readiness) is now fully complete: RH-02 (release-please seed), RH-03 (pyproject version reconcile to 2.0.0), RH-06 (README rewrite), and RH-07 (security contact) are all delivered.
- RH-07 marked complete in REQUIREMENTS.md via `requirements.mark-complete RH-07`.
- Outstanding operator-gated items carried forward as pre-existing debt (not introduced by this plan): the RH-02 Actions-permissions allowlist blocker (release-please-action will hit `startup_failure` until the operator widens the selected-actions policy) and the PVR-enable toggle documented above. Both are one-time GitHub Settings changes, not code gaps.
- Milestone v4.2 progresses to Phase 33 (Config Refactor) next.

---
*Phase: 32-release-automation-community-readiness*
*Completed: 2026-07-02*

## Self-Check: PASSED

- FOUND: SECURITY.md
- FOUND: CODE_OF_CONDUCT.md
- FOUND: .planning/phases/32-release-automation-community-readiness/32-03-SUMMARY.md
- FOUND: fb464d0 (Task 1 commit)
- FOUND: aef6139 (Task 2 commit)
