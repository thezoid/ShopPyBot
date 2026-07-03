---
phase: 31-ci-security-infrastructure
plan: 03
subsystem: infra
tags: [dependabot, cryptography, pydantic-settings, jinja2, vulnerability-remediation]

# Dependency graph
requires:
  - phase: 31-ci-security-infrastructure (plan 02)
    provides: CodeQL workflow fix + ci.yml Node20 bump (established the pattern of verifying live action/package majors before pinning)
provides:
  - .github/dependabot.yml (pip + github-actions ecosystems, weekly, sane open-PR limits)
  - cryptography 44.0.2->49.0.0, pydantic-settings[yaml] 2.14.0->2.14.2, jinja2 3.1.4->3.1.6 (clears all 7 open Dependabot alerts)
affects: [32-release-automation-community-readiness]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single pip dependabot entry at directory / covers both requirements.txt and pyproject.toml (dual-manifest repo layout)"
    - "Dependabot alert manifest_path can mislabel which file actually pins a package (jinja2 alerts said requirements.txt, actual pin lives in pyproject.toml [web] extra) — always verify against a live grep before editing"

key-files:
  created:
    - .github/dependabot.yml
  modified:
    - requirements.txt
    - pyproject.toml

key-decisions:
  - "Exact-pin style (==) kept for all three bumps, matching the project's established requirements.txt convention"
  - "cryptography bumped to latest (49.0.0) rather than the minimum-patched floor (48.0.1) per research: removes the SECT-curve root-cause class entirely; codebase usage (Fernet/Scrypt only) has zero overlap with the deprecated/removed surface"
  - "jinja2 bump applied to pyproject.toml, not requirements.txt, despite the alert's manifest_path saying requirements.txt (Pitfall 5 — jinja2 is not declared in requirements.txt at all)"

patterns-established: []

requirements-completed: [RH-05]

# Metrics
duration: 8min
completed: 2026-07-02
---

# Phase 31 Plan 03: Dependabot Config + Vulnerability Remediation Summary

**Added .github/dependabot.yml (pip + github-actions) and bumped cryptography/pydantic-settings/jinja2 to their patched versions, clearing all 7 open Dependabot alerts with zero documented-dismissals and no pinned-constraint violations.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-07-02T19:59Z (following 31-02 completion)
- **Completed:** 2026-07-02T20:07Z
- **Tasks:** 2 completed
- **Files modified:** 3 (1 created, 2 modified)

## Accomplishments
- `.github/dependabot.yml` created at the correct path (repo-root `.github/`, sibling of `workflows/`): schema v2, two update entries (`pip` directory `/`, `github-actions` directory `/`), weekly Monday schedule, `open-pull-requests-limit` 10/5, dependency labels.
- `cryptography==44.0.2 -> 49.0.0` and `pydantic-settings[yaml]==2.14.0 -> 2.14.2` bumped in `requirements.txt`.
- `jinja2==3.1.4 -> 3.1.6` bumped in `pyproject.toml`'s `[project.optional-dependencies].web` list (the correct manifest per research Pitfall 5 — the alert's `manifest_path` mislabels it as `requirements.txt`).
- All three new versions installed into `.venv` (`pip install -r requirements.txt` then `pip install -e ".[web]"`); full pytest suite reran green at 889 passed, 2 skipped (baseline held, no regression from the cryptography 44->49 five-major-version jump).
- No locked pins touched: `fastapi==0.115.8`, `uvicorn[standard]==0.30.6`, `python-multipart==0.0.32` all verified unchanged via grep.
- Live `gh api .../dependabot/alerts?state=open` pulled post-bump (informational, pre-push): cross-referenced each alert's `vulnerable_version_range` against the new pinned versions — all 7 ranges are now cleared (`49.0.0` clears `<48.0.1`/`<46.0.6`/`<=46.0.4`; `2.14.2` clears `<2.14.2`; `3.1.6` clears `<=3.1.4`/`<=3.1.5`). Alerts still report `state: open` only because Dependabot has not yet re-scanned against the unpushed local commits — expected pre-push behavior, not a remediation gap.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create .github/dependabot.yml (pip + github-actions ecosystems)** - `cbf682b` (feat)
2. **Task 2: Apply the 3 version bumps and confirm the full suite stays green** - `b142cfa` (fix)

_No TDD tasks in this plan (config file + manifest version-pin edits, no test-first cycle applicable)._

## Files Created/Modified
- `.github/dependabot.yml` - schema v2, `pip` (directory `/`) + `github-actions` (directory `/`) ecosystems, weekly Monday schedule, open-PR limits 10/5, `dependencies`+`python`/`github-actions` labels.
- `requirements.txt` - `cryptography==44.0.2->49.0.0`, `pydantic-settings[yaml]==2.14.0->2.14.2`.
- `pyproject.toml` - `[project.optional-dependencies].web`: `jinja2==3.1.4->3.1.6`.

## Decisions Made
- Exact-pin (`==`) style kept for all three bumps rather than switching to a range — matches every other line in `requirements.txt` and this milestone's "preserve constraint style" spirit (resolves research Open Question #2).
- `cryptography` bumped to latest `49.0.0` rather than the minimum-patched floor `48.0.1` — removes the SECT-curve root-cause class (alert #6) outright rather than merely validating it; changelog audit + `grep` confirmed this codebase's usage (`Fernet`, `InvalidToken`, `hazmat.primitives.kdf.scrypt.Scrypt` in `core/credentials.py`/`core/session_store.py`) has zero overlap with any deprecated/removed cipher surface in 45.0.0-49.0.0.
- `jinja2` bump applied in `pyproject.toml`, not `requirements.txt`, despite all 3 jinja2 alerts reporting `manifest_path: "requirements.txt"` — verified live via grep that jinja2 is not declared in `requirements.txt` at all; it is pinned only in `pyproject.toml`'s `[web]` extra (research Pitfall 5).

## Deviations from Plan

None - plan executed exactly as written. Both tasks matched the plan's action blocks and acceptance criteria verbatim. The cryptography 44->49 jump (Pitfall 7's flagged risk) went green on the first full-suite run — no fallback to `cryptography==48.0.1` was needed.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- RH-05 local-verifiable half is complete: `.github/dependabot.yml` valid schema-v2 with both ecosystems, all 3 version bumps applied to the correct manifests, no locked pin touched, full suite green at 889 passed / 2 skipped (exceeds the >=887 baseline).
- Zero documented-dismissals required — research's prediction that all 7 alerts clear via exactly 3 bumps held; live post-bump alert-data cross-check (vulnerable_version_range vs. new pins) confirms all 7 are cleared.
- **CI-verification debt (post-push):** `gh api repos/thezoid/ShopPyBot/dependabot/alerts?state=open --paginate` returning empty is live-GitHub-verifiable only after this branch pushes and Dependabot re-scans the updated manifests — not actioned in this session (no `git push` performed, per CLAUDE.md approval gate). Track alongside the existing gitleaks-run (31-01) and CodeQL-green-run (31-02) CI debt.
- Phase 31 (CI & Security Infrastructure) is now fully code-complete across all 3 plans (RH-01, RH-04, RH-05). Phase 32 (Release Automation & Community Readiness) is unblocked per the sequencing note that Phase 31 must land before Phase 32.

---
*Phase: 31-ci-security-infrastructure*
*Completed: 2026-07-02*

## Self-Check: PASSED

- FOUND: .github/dependabot.yml
- FOUND: requirements.txt
- FOUND: pyproject.toml
- FOUND: .planning/phases/31-ci-security-infrastructure/31-03-SUMMARY.md
- FOUND: commit cbf682b
- FOUND: commit b142cfa
