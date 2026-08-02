---
phase: 31-ci-security-infrastructure
plan: 02
subsystem: infra
tags: [github-actions, codeql, ci, sast, node24-migration]

# Dependency graph
requires:
  - phase: 31-ci-security-infrastructure (plan 01)
    provides: gitleaks secret-scan CI job and RH-01 audit baseline (established the pattern of bumping to Node24-era action majors)
provides:
  - Fixed CodeQL workflow (checkout@v6, codeql-action/init@v4 + analyze@v4, build-mode none, category input, autobuild removed)
  - ci.yml test job bumped off Node20-based actions (checkout@v6, setup-python@v6)
affects: [32-release-automation-community-readiness]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CodeQL build-mode matrix (language + build-mode include list) replaces the separate autobuild step for interpreted languages"
    - "GitHub Actions Node24 migration: checkout@v6, setup-python@v6, codeql-action@v4 are the current supported majors (v4/v5 predecessors are Node20, EOL 2026-09-16)"

key-files:
  created: []
  modified:
    - .github/workflows/codeql-analysis.yml
    - .github/workflows/ci.yml

key-decisions:
  - "checkout@v6 + codeql-action@v4 used (not the CONTEXT.md placeholder v4/v3) per live-verified research: those majors are the current Node24 releases, not stale defaults"
  - "Folded ci.yml's checkout@v4->v6 and setup-python@v5->v6 into this plan (orchestrator-directed) since leaving a second Node20 exposure ticking next to the CodeQL fix contradicts the phase goal"
  - "Autobuild step removed entirely rather than kept alongside build-mode -- Python is interpreted, and autobuild is being phased out generally"

patterns-established: []

requirements-completed: [RH-04]

# Metrics
duration: 5min
completed: 2026-07-02
---

# Phase 31 Plan 02: CodeQL Workflow Fix + Node20 Adjacent Bump Summary

**Rewrote the non-functional CodeQL workflow (four retired Node16 action refs) to checkout@v6 + codeql-action/{init,analyze}@v4 with build-mode: none, and closed the adjacent Node20 exposure in ci.yml.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-07-02T15:47Z (following 31-01 completion)
- **Completed:** 2026-07-02T15:51Z
- **Tasks:** 2 completed
- **Files modified:** 2

## Accomplishments
- `codeql-analysis.yml` rewritten to the researched minimal diff: `checkout@v2->v6`, `codeql-action/{init,analyze}@v1->v4`, matrix restructured to `include: [{language: python, build-mode: none}]`, `autobuild` step removed entirely, `category` input added to the analyze step.
- `ci.yml` bumped off Node20-based actions (`checkout@v4->v6`, `setup-python@v5->v6`) as a folded-in adjacent fix, per the orchestrator's resolved Open Question #1 in 31-RESEARCH.md.
- Full pytest suite verified green after the change (regression sanity check, not the primary gate for a YAML-only plan).

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite codeql-analysis.yml to supported action versions with build-mode none** - `39ccd8e` (fix)
2. **Task 2: Bump ci.yml off Node20 actions (folded-in adjacent exposure)** - `73a6fb2` (fix)

_No TDD tasks in this plan (pure YAML config edits, no test-first cycle applicable)._

## Files Created/Modified
- `.github/workflows/codeql-analysis.yml` - CodeQL SAST workflow: checkout@v6, codeql-action/init@v4 (languages + build-mode inputs), codeql-action/analyze@v4 (category input), autobuild step removed, matrix restructured to an `include` list.
- `.github/workflows/ci.yml` - Test job: `actions/checkout@v4->v6`, `actions/setup-python@v5->v6`; env block, install step, and test step (`pytest --tb=short`) untouched.

## Decisions Made
- Used `checkout@v6` and `codeql-action@v4` (verified live during research as the current Node24-era majors), not the stale `v4`/`v3` placeholders originally proposed in 31-CONTEXT.md.
- Folded the `ci.yml` Node20 bump into this plan rather than deferring it, per 31-RESEARCH.md Open Question #1's recommendation and the orchestrator's direction — avoids leaving a second Node20 time bomb (hard removal 2026-09-16) adjacent to the CodeQL fix.
- Removed the `autobuild` step entirely instead of keeping it alongside `build-mode: none` — redundant for interpreted Python and being phased out in the current official starter-workflow pattern.

## Deviations from Plan

None - plan executed exactly as written. Both tasks matched the plan's action blocks and acceptance criteria verbatim; no auto-fixes, no blocking issues, no architectural questions arose.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- RH-04 local-verifiable half is complete: no retired action versions remain in either workflow file (grep-verified), YAML parses valid, `build-mode: none` configured for interpreted Python, `category` input present, autobuild removed.
- **CI-verification debt (post-push):** the CodeQL Actions run turning green (`gh run list --workflow=codeql-analysis.yml`) is live-GitHub-verifiable only after this branch is pushed — not actioned in this session per the autonomous live-CI deferral policy (no `git push` performed; per CLAUDE.md gate, push requires explicit user approval). Track alongside the existing gitleaks-run CI debt from 31-01.
- Phase 31's remaining plan (31-03, RH-05: dependabot.yml + vuln remediation) is unblocked and can proceed next.

---
*Phase: 31-ci-security-infrastructure*
*Completed: 2026-07-02*

## Self-Check: PASSED

- FOUND: .github/workflows/codeql-analysis.yml
- FOUND: .github/workflows/ci.yml
- FOUND: .planning/phases/31-ci-security-infrastructure/31-02-SUMMARY.md
- FOUND: commit 39ccd8e
- FOUND: commit 73a6fb2
