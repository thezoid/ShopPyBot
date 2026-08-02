---
phase: 36
slug: mainline-reconciliation
status: planned
nyquist_compliant: true
wave_0_complete: true
created: 2026-08-02
---

# Phase 36: Validation Strategy

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

The requirement rows below are the phase's binding assertions. The plan-level map that follows
them was filled in by the planner on 2026-08-02, once the five PLAN.md files existed.

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

## Plan-Level Assertion Map

Every task in every plan carries an `<acceptance_criteria>` block and an `<automated>` verify
command, so each row below names the task that owns the assertion, not just the plan.

| Req ID | Owning plan and task | Assertion asserted there |
|--------|---------------------|--------------------------|
| MAIN-01 | 36-03 task 3 (first proof), 36-05 task 1 (per ci.yml merge), 36-05 task 2 (final tip) | `gh run view <id> --json jobs` reports `.jobs | length` of 2 or greater with zero non-success conclusions, and both named runner jobs present |
| MAIN-02 | 36-02 task 2 (local resolution), 36-03 task 2 (on master), 36-04 task 3 and 36-05 task 2 (no later regression) | exactly one `^httpx==` line and it is `httpx==0.28.1`; one line each for `cryptography==49.0.0` and `pydantic-settings[yaml]==2.14.2` |
| MAIN-03 | 36-02 task 1 (record), 36-03 task 2 (ancestry proof), 36-05 task 2 (re-assert on the final tip) | SHA list re-derived with raw `git log`, one `include` row per SHA, then `git merge-base --is-ancestor <sha> origin/master` exits 0 for every row |
| MAIN-04 | 36-03 task 2, re-asserted 36-05 task 2 | `git ls-tree origin/master -- .github/workflows/gitleaks.yml .github/workflows/release-please.yml` returns 2 lines |
| MAIN-05 | 36-01 task 2 | `gh pr view 12 --json state` outputs MERGED and PR #12's head OID is an ancestor of origin/master |
| MAIN-06 | 36-01 task 3 | `gh pr view 8 --json state` outputs CLOSED with null `mergedAt`, and the issue comments contain one matching both `urllib3==2.7.0` and `superseded` |
| MAIN-07 | 36-04 tasks 1 to 3 (pip set), 36-05 task 1 (actions set), 36-05 task 2 (the nine-PR diff; PRs opened during the phase, including 36-05 task 3's docs PR, are out of MAIN-07 scope and are merged before phase end anyway) | `gh pr list --state open --json number` intersected against 8, 11, 12, 15, 16, 17, 18, 19, 20 has length 0, and every close carries a superseded comment |

**Full-suite gates.** 36-02 task 3 runs the mandatory pre-push gate on the merged tree.
36-05 task 2 runs the second mandatory gate against the final merged master tip via a
clean-tree-guarded detached checkout. Both require exit 0, 0 failed, 0 errors, and 900 or more
collected (master alone collects 757).

**Fix-forward cap.** A single `<fix_forward_protocol>` block, byte-identical in plans 03, 04 and
05, is the only sanctioned response to a red `master`. Three attempts total for the whole phase,
not three per plan. Because plans 03, 04 and 05 run as separate executor invocations with no
shared memory, the counter lives in `36-CI-EVIDENCE.md` and STEP F0 makes re-reading it mandatory
before every increment:

`sed -n 's/.*Fix-forward attempts used: \([0-9][0-9]*\).*/\1/p' .planning/phases/36-mainline-reconciliation/36-CI-EVIDENCE.md | tail -1`

POSIX BRE only, verified working in Git Bash on this machine at planning time; `grep -oP` is not
available here. A PowerShell `Select-String` equivalent is given inline for the case where bash
is unavailable. STEP F1 persists the increment BEFORE acting, so a mid-fix context loss cannot
hand an attempt back. Revert, force-push and `--admin` are prohibited in this state; a fourth
attempt is prohibited outright and the phase stops and escalates instead.

**Red-master recovery is wired in every plan that can produce one.** 36-03 task 3, all three
tasks of 36-04 (via the shared procedure's STEP 7), and 36-05 tasks 1 and 3 each name the
protocol explicitly, so no red-master state falls through to the executor's generic deviation
loop, which would not respect CONTEXT.md's locked never-revert policy or the shared cap.

**Evidence durability.** 36-05 task 3 lands the phase directory and the roadmap update on
`master` through a docs-only PR (path-scoped to `.planning/`, merged with `gh pr merge`, no
direct push to master). Without it every artifact after the PR #11 merge would exist only as a
local commit and Phase 38 would inherit nothing from a fresh clone. The one file that cannot make
that PR, `36-05-SUMMARY.md`, is named in both the PR body and `36-CI-EVIDENCE.md` rather than
left as a silent gap.

**Bounded waits.** Every poll in every plan has an interval, an iteration cap or `timeout`
wrapper, and a written action on timeout. There are no unbounded waits and no watch-mode flags in
any `<automated>` command.

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
- [x] Wave 0 covers all MISSING references (N/A, no Wave 0 gaps)
- [x] No watch-mode flags (verified across all five PLAN.md files at planning time)
- [ ] Full local suite green before the PR #11 push, and again on the final merged tip
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** plan-level map complete 2026-08-02. Requirement rows stay ⬜ pending until execution records a command result.
