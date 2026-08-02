---
phase: 36
slug: mainline-reconciliation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-02
---

# Phase 36 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3, config in `pyproject.toml` `[tool.pytest.ini_options]` |
| **Config file** | `pyproject.toml` (`testpaths = ["tests"]`, `asyncio_mode = "auto"`) |
| **Quick run command** | `.venv\Scripts\python.exe -m pytest --tb=short -x` |
| **Full suite command** | `.venv\Scripts\python.exe -m pytest` |
| **Estimated runtime** | ~90 seconds (939 tests on the merged tree, 755 on master today) |

**Phase-specific note.** The dominant verification surface for Phase 36 is not pytest. It is
git and GitHub state assertions: merge status, PR state, CI run conclusions. pytest is the one
code-level gate: the full suite must be green locally before the PR #11 push, and the merged
tree's CI run must reproduce that result. The automated-command column below therefore uses
`git` and `gh` commands, matching how this phase's success criteria are worded.

**Tooling constraint.** Use raw `git` for every ancestry, range, and rev-list query in this
phase. `rtk git log <range>` was observed dropping merge commits from range output during
scouting (it reported an empty range for `HEAD..origin/chore/v4.0-milestone-close`, which
actually contains `e2f2695` and `d9ad585`). Merge-ancestry reasoning is the core of this phase,
so a filtered log is a correctness hazard, not a formatting difference.

## Sampling Rate

- **Per merge in the sequence:** run that merge's assertion row below immediately after the
  merge lands, before starting the next merge.
- **Full local suite:** once before the PR #11 push (mandatory per CONTEXT.md), and once again
  against the final merged `master` tip checked out fresh, before declaring the phase done.
- **Phase gate:** the MAIN-07 open-PR diff plus a green `gh run view` for the final `master`
  HEAD. Both required before `/gsd:verify-work`.
- **Max feedback latency:** local suite ~90s; a CI run on `master` is the long pole at roughly
  8 to 12 minutes for both OS jobs.

## Per-Requirement Verification Map

Task-level rows are filled in by the planner once PLAN.md files exist. The requirement rows
below are the phase's binding assertions and do not depend on task decomposition.

| Req ID | Behavior | Type | Automated Command | Status |
|--------|----------|------|-------------------|--------|
| MAIN-01 | Merged `master` CI schedules and passes both OS jobs | infra | `gh run view <id> --json jobs --jq '.jobs[]｜{name,conclusion}'` expects 2+ entries, all `success`, and a non-empty job list | ⬜ pending |
| MAIN-02 | Merged `requirements.txt` holds the 3 union-critical pins, one line each | infra | on merged `master`: `httpx==0.28.1`, `cryptography==49.0.0`, `pydantic-settings[yaml]==2.14.2` each appear exactly once | ⬜ pending |
| MAIN-03 | Every local commit absent from PR #11's head carries a recorded include/exclude decision | infra | re-derive the SHA list fresh with raw `git log --oneline origin/chore/v4.0-milestone-close..HEAD`, then `git merge-base --is-ancestor <sha> master` per recorded SHA | ⬜ pending |
| MAIN-04 | `gitleaks.yml` and `release-please.yml` exist on `master` post-merge | infra | `git ls-tree origin/master -- .github/workflows/gitleaks.yml .github/workflows/release-please.yml` returns two non-empty lines | ⬜ pending |
| MAIN-05 | PR #12 merged | infra | `gh pr view 12 --json state --jq .state` == `MERGED` and `git merge-base --is-ancestor 3f27a2d origin/master` | ⬜ pending |
| MAIN-06 | PR #8 closed unmerged with a recorded reason | infra | `gh pr view 8 --json state --jq .state` == `CLOSED`, and its comments contain one naming `urllib3==2.7.0` and "superseded" | ⬜ pending |
| MAIN-07 | #8, #11, #12, #15-#20 all reach a non-open state, actions PRs serialized | infra | `gh pr list --state open --json number` returns none of 8, 11, 12, 15, 16, 17, 18, 19, 20 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

## Wave 0 Requirements

None. Existing test infrastructure (pytest, already configured in `pyproject.toml`) covers
everything this phase needs at the code level. The gaps this phase closes are GitHub-state gaps
(open PRs, unmerged conflicts, unproven CI on the merged tree), not test-coverage gaps.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None identified | | | |

Every assertion in this phase is reachable from the `git` and `gh` CLIs. The GitHub Actions
dependency is live, but it is pollable rather than human-observed, so it is not deferred as
operator UAT debt. This is an explicit departure from the milestone's usual live-check deferral
policy, recorded in CONTEXT.md.

## Known Blocking Conditions

These are not validation gaps. They are pre-identified conditions that will make an assertion
above fail for an environmental reason rather than a correctness reason, and the plan must
distinguish them.

| Condition | Effect | Distinguishing signal |
|-----------|--------|-----------------------|
| Branch protection on `master` requires `CodeQL`, `test (windows-latest)`, `test (ubuntu-latest)` with `strict: true` | Every PR must be up to date with `master` immediately before merging, so all nine merges serialize and each needs an update-branch step | `gh pr view <n> --json mergeStateStatus` returns `BEHIND` rather than `CLEAN` |
| GitHub Actions allowlist not widened for `gitleaks/gitleaks-action` and `googleapis/release-please-action` | Those two workflows fail on `master` after PR #11 lands | Failure is at action-resolution time, not test time. Does not block this phase (Phase 38 scope), but must be recorded rather than treated as a merge defect |
| Dependabot is repo-level paused | Dependabot may not rebase its own stale PRs after the big merge | `@dependabot rebase` comment produces no new commit within the poll window |

## Validation Sign-Off

- [ ] Every MAIN requirement row above has a recorded command result, not an assertion of intent
- [ ] Sampling continuity: an assertion runs after each merge, not only at phase end
- [ ] Wave 0 covers all MISSING references (N/A, no Wave 0 gaps)
- [ ] No watch-mode flags
- [ ] Full local suite green before the PR #11 push, and again on the final merged tip
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
