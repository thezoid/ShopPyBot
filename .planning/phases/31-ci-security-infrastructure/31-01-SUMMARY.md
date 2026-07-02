---
phase: 31-ci-security-infrastructure
plan: 01
subsystem: infra
tags: [gitleaks, secret-scanning, github-actions, ci, pytest]

# Dependency graph
requires: []
provides:
  - "Inline #gitleaks:allow suppression on the single confirmed test-fixture false positive (tests/test_captcha.py:381)"
  - "tests/test_no_tracked_secrets.py local pytest guard (no sensitive path tracked + .gitignore coverage assertion)"
  - ".github/workflows/gitleaks.yml full-history CI secret-scan job"
affects: [32-release-automation-and-community-readiness]

# Tech tracking
tech-stack:
  added: [gitleaks/gitleaks-action@v3, actions/checkout@v6]
  patterns: ["Fast local pytest guard mirrors tests/test_no_committed_sessions.py (git ls-files + skip-on-no-git)", "Fingerprint-precise inline #gitleaks:allow suppression instead of scope-widening .gitleaks.toml allowlist"]

key-files:
  created: [tests/test_no_tracked_secrets.py, .github/workflows/gitleaks.yml]
  modified: [tests/test_captcha.py]

key-decisions:
  - "Suppressed the one gitleaks finding (tests/test_captcha.py:381 sentinel_key) with an inline #gitleaks:allow comment, not a .gitleaks.toml path exemption -- avoids silently suppressing a future real leak under tests/"
  - "No local gitleaks binary run this session (not pre-installed); CI enforcement path (gitleaks-action@v3) is self-contained and does not need one -- workflow validated by YAML correctness + acceptance-criteria greps per plan's test_env_note"

patterns-established:
  - "RH-01 local-verifiable half: pytest guard + .gitignore assertion + suppressed false positive; full-history scan enforcement lives in CI, not locally"

requirements-completed: [RH-01]

# Metrics
duration: 6min
completed: 2026-07-02
---

# Phase 31 Plan 01: Secret-Scan Audit & Guard Summary

**Suppressed the one confirmed gitleaks test-fixture false positive inline, added a fast local pytest guard for tracked-secret paths, and wired a full-history gitleaks CI job (checkout@v6 + gitleaks-action@v3).**

## Performance

- **Duration:** 6 min
- **Started:** 2026-07-02T19:33:45Z
- **Completed:** 2026-07-02T19:39:00Z
- **Tasks:** 2 completed
- **Files modified:** 3

## Accomplishments
- `tests/test_captcha.py:381` sentinel_key line now carries `#gitleaks:allow`, suppressing the one confirmed false-positive finding from the research phase's live gitleaks scan (964 commits, 1 finding); string value unchanged (CP-03 test integrity preserved)
- New `tests/test_no_tracked_secrets.py` (2 tests) mirrors the existing `tests/test_no_committed_sessions.py` convention: asserts no sensitive path (`config.yml`, `data/`, `*.db`, `*creds.bin`, `*sessions/*.bin`) is git-tracked, and that `.gitignore` covers `config.yml` + `data/*`; both tests are skip-safe (git absent / .gitignore absent) and both ran GREEN (not skipped)
- New `.github/workflows/gitleaks.yml`: full-history secret scan (`fetch-depth: 0` + `gitleaks/gitleaks-action@v3`) on push/PR to `master`/`dev` plus `workflow_dispatch`; fails the job on any finding by default (not weakened); no `GITLEAKS_LICENSE` (personal-account public repo) and no extra `permissions:` block needed (repo default already `write`)

## Task Commits

Each task was committed atomically:

1. **Task 1: Suppress the test-fixture false positive and add the local no-tracked-secrets guard** - `99f81ac` (test)
2. **Task 2: Add the gitleaks CI secret-scan workflow** - `549250d` (feat)

**Plan metadata:** (pending — this commit)

## Files Created/Modified
- `tests/test_captcha.py` - Added inline `#gitleaks:allow` trailing comment on the `sentinel_key` fixture line (line 381); string value unchanged
- `tests/test_no_tracked_secrets.py` - New: `test_no_tracked_sensitive_paths()` (git ls-files against the sensitive path set) + `test_gitignore_covers_sensitive_paths()` (.gitignore content assertion)
- `.github/workflows/gitleaks.yml` - New: single `scan` job, `actions/checkout@v6` (`fetch-depth: 0`) + `gitleaks/gitleaks-action@v3`, triggers on push/PR to `[master, dev]` + `workflow_dispatch`

## Decisions Made
- Inline `#gitleaks:allow` (fingerprint-precise, single line) over a `.gitleaks.toml` `[[allowlists]]` path exemption for `tests/` -- a blanket tests/ exemption would silently suppress any future real secret accidentally committed to a test file (research Anti-Pattern, honored as-is)
- No local `gitleaks` binary execution this session (not pre-installed in this dev environment, consistent with research's Environment Availability finding); Task 2's verification instead relies on YAML validity (`yaml.safe_load`) + exact acceptance-criteria greps (`checkout@v6`, `gitleaks-action@v3`, `fetch-depth:\s*0`, absence of deprecated `gitleaks detect`, `workflow_dispatch` present) -- the CI job itself is the actual full-history enforcement mechanism and needs no local install to be correct

## Deviations from Plan

None - plan executed exactly as written. Both tasks matched their `<action>` and `<acceptance_criteria>` blocks with no auto-fixes required.

## Issues Encountered

The orchestrator-provided `rtk pytest`/`rtk` shell proxy resolved to a stray Python 3.14 user-site install (`C:\Users\brand\AppData\Roaming\Python\Python314`) whose installed `nodriver` package has a non-UTF-8-encoded `cdp/network.py`, causing 24 collection errors unrelated to this plan's changes (no file touched by this plan imports `nodriver`). Ran the full suite directly via the project's `.venv\Scripts\python.exe -m pytest` instead (the correct, CLAUDE.md-documented Python 3.13 virtualenv) and confirmed 889 passed, 2 skipped -- baseline 887 passed, 2 skipped, plus the 2 new tests in `tests/test_no_tracked_secrets.py`. This is a local dev-machine Python-install artifact, not a code gap; out of scope per deviation-rules SCOPE BOUNDARY (pre-existing, unrelated to files this plan modified).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

RH-01's local-verifiable half is complete: no sensitive path tracked, `.gitignore` demonstrably covers them, the one gitleaks false positive is suppressed, and the gitleaks CI job is in place and YAML-valid. CI-verification debt (per CONTEXT.md's live-CI boundary): the actual gitleaks Actions run reporting `leaks found: 0` is verifiable only after this branch is pushed and the workflow executes on GitHub's runners -- tracked as CI debt, not a code gap, consistent with the phase's non-destructive/live-CI-boundary policy. Phase 31 continues with RH-04 (CodeQL workflow fix) and RH-05 (dependabot + vulnerability remediation) in subsequent plans; Phase 31 must land before Phase 32 (release-please needs working CI security scanning first) per STATE.md sequencing notes.

---
*Phase: 31-ci-security-infrastructure*
*Completed: 2026-07-02*

## Self-Check: PASSED

- FOUND: tests/test_no_tracked_secrets.py
- FOUND: .github/workflows/gitleaks.yml
- FOUND: .planning/phases/31-ci-security-infrastructure/31-01-SUMMARY.md
- FOUND: commit 99f81ac (Task 1)
- FOUND: commit 549250d (Task 2)
