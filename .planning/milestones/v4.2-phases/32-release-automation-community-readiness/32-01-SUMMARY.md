---
phase: 32-release-automation-community-readiness
plan: 01
subsystem: infra
tags: [release-please, github-actions, pyproject, versioning, semver]

# Dependency graph
requires:
  - phase: 31-ci-security-infrastructure
    provides: working CodeQL + dependabot CI security scanning that release-please lands alongside
provides:
  - pyproject.toml version reconciled to 2.0.0 (sole version source of truth, RH-03)
  - release-please-config.json (manifest mode, release-type python, package "." = shoppybot)
  - .release-please-manifest.json seeded at 2.0.0, matching pyproject exactly
  - .github/workflows/release-please.yml (googleapis/release-please-action@v5, least-privilege permissions)
affects: [32-02, 32-03, release-milestone]

# Tech tracking
tech-stack:
  added: [googleapis/release-please-action@v5]
  patterns: [manifest-mode release-please seeding for an existing repo (seed = baseline, not a pending tag)]

key-files:
  created: [release-please-config.json, .release-please-manifest.json, .github/workflows/release-please.yml]
  modified: [pyproject.toml]

key-decisions:
  - "Manifest-mode release-please with no extra-files entry — python release-type updates pyproject.toml natively"
  - "Workflow permissions scoped to exactly contents:write + pull-requests:write, no actions:write/id-token:write"
  - "Seeded manifest at 2.0.0 = baseline only; release-please will propose the NEXT bump from commit history, it does not re-tag 2.0.0"

patterns-established:
  - "release-please manifest seeding: set .release-please-manifest.json to the just-reconciled canonical version so release-please treats it as already-released"

requirements-completed: [RH-03, RH-02]

# Metrics
duration: ~10min
completed: 2026-07-02
---

# Phase 32 Plan 01: Release Automation Seed Summary

**pyproject version reconciled to 2.0.0 and release-please manifest-mode automation (config + seeded manifest + workflow) landed, ready to compute the next release from conventional-commit history once the operator opens the Actions allowlist.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-07-02T21:08:00Z (approx)
- **Completed:** 2026-07-02T21:19:00Z
- **Tasks:** 3
- **Files modified:** 4 (1 modified, 3 created)

## Accomplishments
- `pyproject.toml [project].version` bumped `0.1.0` → `2.0.0`; confirmed the sole version source in the repo (no `__version__`, no `setup.py`/`setup.cfg`/`VERSION`).
- `release-please-config.json` + `.release-please-manifest.json` created, manifest-mode, seeded at `2.0.0` to match pyproject exactly — single source of truth honored (T-32-02 mitigation verified).
- `.github/workflows/release-please.yml` created: `googleapis/release-please-action@v5`, triggers on push to `master` only, `permissions: contents: write` + `pull-requests: write` only (T-32-01 mitigation verified — no `actions:write`/`id-token:write`).
- Full pytest suite green after the version bump: 889 passed, 2 skipped (no regression).

## Task Commits

Each task was committed atomically:

1. **Task 1: Reconcile pyproject version to 2.0.0 (RH-03) and prove no regression** - `3a380bf` (chore)
2. **Task 2: Create release-please config + manifest seeded at 2.0.0 (RH-02)** - `082a25a` (feat)
3. **Task 3: Create the release-please workflow (RH-02)** - `43fe044` (feat)

**Plan metadata:** (this commit, docs: complete plan — see final commit below)

## Files Created/Modified
- `pyproject.toml` - `[project].version` changed `0.1.0` → `2.0.0`; no other line touched
- `release-please-config.json` - manifest-mode config: `release-type: python`, package `.` named `shoppybot`, no `extra-files`
- `.release-please-manifest.json` - seeded `{".": "2.0.0"}`, matching pyproject
- `.github/workflows/release-please.yml` - release-please Action workflow, push→master, least-privilege permissions, no `release-type` input (manifest mode)

## Decisions Made
- No `extra-files` entry in `release-please-config.json` — the python release-type's built-in `pyproject-toml.ts` updater already targets `pyproject.toml` because it has a `[project].version` key; a redundant `extra-files` entry risks a double-write (per 32-RESEARCH.md Anti-Patterns).
- `release-type` is not passed as an action `with:` input on the workflow — it lives only in `release-please-config.json`; the action auto-discovers the root-level config/manifest filenames in manifest mode (mixing legacy single-package mode with manifest mode would conflict).
- Workflow trigger scoped to `push: branches: [master]` only (not `dev`) — `master` is the repo's confirmed default/release branch.

## Deviations from Plan

None - plan executed exactly as written. All three tasks matched the exact file shapes specified in 32-RESEARCH.md lines 207-257 verbatim; no Rule 1-4 auto-fixes were needed.

## Issues Encountered

None.

## Operator Action Items (CI-verification debt — NOT blockers, surfaced per plan `<verification>` section)

1. **Actions allowlist blocks third-party actions.** This repo's Actions permissions policy is `allowed_actions: selected` with an empty `patterns_allowed` list — only GitHub-owned actions can currently execute. `googleapis/release-please-action` is third-party and will hit `conclusion: startup_failure` with zero jobs created on every push to `master` until the operator adds a pattern. Same root cause as the pre-existing Phase 31 `gitleaks/gitleaks-action` `startup_failure`. **Fix (operator, one-time):** Settings → Actions → General → Actions permissions → add `googleapis/release-please-action@*` (and ideally `gitleaks/gitleaks-action@*`) to the selected-actions pattern list. Prefer this narrow pattern allowlist over "Allow all actions and reusable workflows" (least-privilege). This automation call is NOT made by this executor per the plan's explicit scope boundary and the run instructions (`Do NOT call gh api to change any repo settings`).
2. **Seed ≠ tag.** Seeding `.release-please-manifest.json` at `2.0.0` makes release-please treat `2.0.0` as the already-released baseline; it does NOT create a `v2.0.0` tag/release itself. Once the Actions allowlist is opened and commits land on `master`, release-please's first proposed release PR will target whatever the NEXT semver bump is per conventional-commit history since this seed (e.g. `2.0.1`/`2.1.0`/`3.0.0` depending on commit types) — not `2.0.0` again. If the operator wants the literal first tagged release to be `v2.0.0`, they must cut that manually/out-of-band; release-please will never propose re-tagging the seed value. This matches CONTEXT.md's explicit scope boundary: actually cutting/publishing the first GitHub release stays operator-gated.

## Next Phase Readiness
- RH-03 and RH-02 are both code-complete; release-please automation is fully wired and will function correctly the moment the operator opens the Actions allowlist — no further code changes are needed for either requirement.
- Remaining Phase 32 requirements (RH-06 README refresh, RH-07 security contact) are unblocked and can proceed in the next plan; they do not depend on anything landed in this plan beyond the now-correct `2.0.0` version number this plan established.
- No blockers for 32-02/32-03.

---
*Phase: 32-release-automation-community-readiness*
*Completed: 2026-07-02*

## Self-Check: PASSED

All 5 created/modified files found on disk; all 3 task commits (3a380bf, 082a25a, 43fe044) found in git log.
