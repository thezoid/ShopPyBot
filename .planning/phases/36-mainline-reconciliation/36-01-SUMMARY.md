---
phase: 36-mainline-reconciliation
plan: 01
subsystem: infra
tags: [git, github, gh-cli, branch-protection, dependabot, merge-audit]

# Dependency graph
requires: []
provides:
  - "Annotated pre-v5-mainline tag on origin at e98ec83, the rollback point for all of phase 36"
  - "PR #12 (signal-handler main-thread fix) merged to master as merge commit 36f75c7 (MAIN-05)"
  - "PR #8 closed unmerged with a machine-verifiable superseded reason (MAIN-06)"
  - "36-MERGE-LOG.md: the append-only phase audit trail every later plan writes into"
  - "Live evidence that Dependabot is responsive on this repo (8-second reaction to the PR #8 close)"
affects: [36-02, 36-03, 36-04, 36-05, 38-scanning-to-zero]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Append-only merge audit log: one row per GitHub mutation, actual observed SHAs only"
    - "Prove-then-act: assert the premise of a destructive/irreversible action before taking it"
    - "Bounded poll with a written timeout action, run as a background invocation"

key-files:
  created:
    - .planning/phases/36-mainline-reconciliation/36-MERGE-LOG.md
    - .planning/phases/36-mainline-reconciliation/36-01-SUMMARY.md
  modified: []

key-decisions:
  - "Recorded PR #12's post-update head b1d7b8f alongside the pre-update head 3f27a2d, since strict-mode update-branch moves the head and MAIN-05's assertion names the pre-update SHA"
  - "Did not treat Dependabot's self-deletion of PR #8's head branch as a violation of --delete-branch=false; the timeline names dependabot[bot] as the actor 8 seconds after the close"
  - "Recorded two brittle assertion commands (jq backslash escaping, mergedAt null rendering) in 36-MERGE-LOG.md for plans 02 through 05 rather than silently working around them"

patterns-established:
  - "Pattern 1: Every phase-36 mutation is preceded by a fresh re-derivation of its inputs and followed by an audit-log row naming actual SHAs, never planning-time expectations"
  - "Pattern 2: Guard irreversible ref writes with an existence pre-check whose failure path is STOP, never overwrite"

requirements-completed: [MAIN-05, MAIN-06]

# Metrics
duration: 13min
completed: 2026-08-02
---

# Phase 36 Plan 01: Rollback Point and Independent PR Dispositions Summary

**Annotated `pre-v5-mainline` rollback tag pushed at `e98ec83`, PR #12's signal-handler fix merged to `master` as merge commit `36f75c7` through the normal protected path, and stale 2023 PR #8 closed unmerged with a grep-verifiable superseded reason, all recorded in a new append-only phase audit log.**

## Performance

- **Duration:** 13 min (763s)
- **Started:** 2026-08-02T18:01:54Z
- **Completed:** 2026-08-02T18:14:37Z
- **Tasks:** 3 of 3
- **Files modified:** 2 created, 0 modified (plus 3 live GitHub mutations)

## Accomplishments

- **Rollback point established.** Annotated tag `pre-v5-mainline` (tag object `7edffb33`) pushed to origin, peeling to `e98ec83ff9e47459902c3c0615fd428f5dd27caf`. The pre-check for an existing tag returned empty, so nothing was clobbered. The whole of phase 36 is now revertible to a single named ref.
- **MAIN-05 satisfied.** PR #12 merged as a real merge commit, not a squash or rebase, and not with `--admin`. All three required contexts went green on the updated head before the merge.
- **MAIN-06 satisfied.** PR #8 closed unmerged with a comment the GitHub comments API can be grepped against, and the superseded premise was proven from `origin/master` before the close rather than asserted from the plan.
- **Audit trail opened.** `36-MERGE-LOG.md` now carries 5 timestamped rows and a Recorded Values table that plans 02 through 05 read their input SHAs from.
- **Dependabot responsiveness proven live.** An unexpected but genuinely useful finding, detailed below.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create and push the pre-v5-mainline rollback tag** - `969b322` (docs)
2. **Task 2: Merge PR #12 (signal-handler fix, MAIN-05)** - `d04c5ca` (docs)
3. **Task 3: Close PR #8 unmerged with a recorded superseded reason (MAIN-06)** - `c321509` (docs)

All three task commits carry documentation only. The substantive work of this plan is the three
live GitHub mutations, which are not local commits; the commits are their audit record.

## Actual Observed Values (plans 02 and 03 verify ancestry against these)

| Name | Value |
|------|-------|
| **BASE_SHA** (rollback point, `origin/master` pre-phase) | `e98ec83ff9e47459902c3c0615fd428f5dd27caf` |
| `pre-v5-mainline` tag object | `7edffb33c2a54d3a99b65b61d616a6759d20c908` |
| **PR #12 head OID, pre-update** (the SHA MAIN-05 asserts) | `3f27a2dff279852ced3f8712b56f582173946a3b` |
| **PR #12 head OID, post-update** (what actually merged) | `b1d7b8f5aef3b8767236eb5ba02b60ec97894695` |
| PR #12 merge commit | `36f75c7643e5a72b72ac95a6d521edd8ffbb2971` |
| **`origin/master` after PR #12** (base for plan 36-02) | `36f75c7643e5a72b72ac95a6d521edd8ffbb2971` |
| PR #8 head SHA (closed unmerged) | `8a915e6728e43d251cc26e094ccd456fc38a497f` |
| PR #8 superseded comment | `https://github.com/thezoid/ShopPyBot/pull/8#issuecomment-5159680032` |

Every planning-time expectation in the plan's `<verified_state>` block was re-derived fresh and
matched: `origin/master` was still `e98ec83`, PR #12's head was still `3f27a2d` on branch
`fix/signal-handler-main-thread`, and master's `urllib3` pin was still `2.7.0`. One
under-description was found (see Deviations).

## Files Created/Modified

- `.planning/phases/36-mainline-reconciliation/36-MERGE-LOG.md` - Created. Append-only audit trail: header stating the raw-git/gh tooling constraint and the phase-wide force-operation prohibition, the pre-mutation branch-protection baseline, 5 mutation rows, a Recorded Values table, and a Tooling Note flagging two brittle assertion commands for later plans.
- `.planning/phases/36-mainline-reconciliation/36-01-SUMMARY.md` - Created. This file.

## Live GitHub Mutations (the actual deliverable)

| Time (UTC) | Mutation | Result |
|-----------|----------|--------|
| 18:02:41 | `git push origin refs/tags/pre-v5-mainline` | Tag on origin, annotated, peels to `e98ec83` |
| 18:04:50 | `gh pr update-branch 12` | No conflict; head `3f27a2d` to `b1d7b8f` |
| 18:08:39 | `gh pr merge 12 --merge --delete-branch=false` | `MERGED`, `mergedAt` 18:08:41Z |
| 18:11:19 | `gh pr close 8 --delete-branch=false --comment "..."` | `CLOSED`, `merged: false` |

## Decisions Made

- **Recorded both PR #12 head OIDs.** `required_status_checks.strict: true` forced an
  `update-branch` before the merge, which advances the head. MAIN-05's assertion in
  36-VALIDATION.md names `3f27a2d`, the pre-update SHA. Both were verified as ancestors of
  `origin/master` so the requirement holds under either reading, and both are recorded so a
  later reader is not confused by a head OID that no longer matches the PR's first commit.
- **Did not use `--admin`, and did not need to.** All six checks on PR #12 reached bucket `pass`,
  including all three required contexts. Pitfall 4's "`skipped` and `neutral` also satisfy
  protection" allowance was available but never exercised.
- **Left the `fix/signal-handler-main-thread` branch on origin.** `--delete-branch=false` as the
  plan specified. It still exists on origin, which is what proved the flag was honoured when
  PR #8's branch later vanished.
- **Flagged two brittle assertion commands rather than quietly fixing them.** Documented in
  36-MERGE-LOG.md so plans 02 through 05 do not rediscover them.

## Deviations from Plan

### Observations recorded, no auto-fix required

**1. [Recorded] PR #12 touches 2 files, not the 1 the plan named**

- **Found during:** Task 2, on the mandatory fresh re-derivation of PR #12's live state
- **Issue:** 36-01-PLAN.md's `<verified_state>` describes PR #12 as touching `core/orchestrator.py`.
  The live `gh pr view 12 --json files` returned `core/orchestrator.py` (+12/-0, MODIFIED) **and**
  `tests/test_signal_registration_thread.py` (+127/-0, ADDED).
- **Assessment:** An under-description in the planning note, not a changed premise. The head OID,
  head branch, author, base branch and mergeable state all matched exactly, and a fix arriving
  with its own regression test is the expected shape for this repo. Merged as planned.
- **Recorded in:** `36-MERGE-LOG.md`, "Deviation from planning-time expectation"
- **Committed in:** `d04c5ca`

**2. [Recorded] Dependabot deleted PR #8's head branch 8 seconds after the close**

- **Found during:** Task 3 post-close verification
- **Issue:** `refs/heads/dependabot/pip/urllib3-1.26.18` was absent from origin immediately after
  the close, while every other Dependabot branch (#15 through #20) was present. The plan says
  explicitly "Do NOT delete the head branch", so this needed to be resolved rather than assumed.
- **Resolution:** `gh api repos/thezoid/ShopPyBot/issues/8/timeline` shows `closed` by `thezoid`
  at 18:11:19Z, then `head_ref_deleted` by **`dependabot[bot]`** at 18:11:27Z. This executor did
  not delete it. `--delete-branch=false` was passed and was honoured, independently corroborated
  by PR #12's head branch still existing on origin after the same flag was used on `gh pr merge`.
  Dependabot self-cleans its own branch when one of its PRs is closed.
- **Verification:** Timeline actor attribution plus the surviving PR #12 head branch
- **Committed in:** `c321509`

**3. [Recorded] Two acceptance-criteria commands are brittle as literally written**

- **Found during:** Task 3 verification
- **Issue (a):** The jq regex `test("urllib3==2\\.7\\.0")` lost a backslash layer through this
  harness's Bash tool on Windows; jq rejected it with `invalid escape sequence "\."`. The
  assertion is correct, only the escaping is fragile.
- **Issue (b):** `gh pr view 8 --json mergedAt --jq .mergedAt` prints an **empty line**, not the
  literal text `null`. A `test "$(...)" = null` comparison therefore fails on a correctly closed
  PR.
- **Fix:** Re-asserted both with robust equivalents: a POSIX bracket class
  (`test("urllib3==2[.]7[.]0")`, needs no backslash and survives any quoting depth) returning `1`,
  and `gh pr view 8 --json mergedAt` returning `{"mergedAt":null}` plus
  `gh api repos/.../pulls/8 --jq .merged` returning `false`. Both underlying assertions pass.
- **Recorded in:** `36-MERGE-LOG.md`, "Tooling Note for Later Plans"
- **Committed in:** `c321509`

**Total deviations:** 0 auto-fixed, 3 recorded observations.
**Impact on plan:** None. No task's action changed, no STOP condition was triggered, no scope
crept. All three items are information later plans need, which is why they are in the audit log
rather than only here.

## Issues Encountered

None blocking. The three items above were investigated and resolved during their own tasks.

Worth naming explicitly: **no STOP condition fired.** The plan carries four deliberate STOPs
(pre-existing rollback tag, unexpected `update-branch` conflict, poll timeout, false supersede
premise). Each was checked and each came back clean: no tag on origin, `update-branch` reported
no conflict, `mergeStateStatus` hit `CLEAN` on poll iteration 4 of a 30-iteration budget, and
`origin/master` really does pin `urllib3==2.7.0`.

## Safety Posture Confirmed

- **No force operation anywhere.** No `git push --force`, no `--force-with-lease`, no `git tag -f`,
  no `git push origin :refs/...`, no `git clean`, no `git reset`, no `git stash`.
- **No direct push to `master`.** `origin/master` moved exactly once, via `gh pr merge`.
  The only ref this executor pushed directly is `refs/tags/pre-v5-mainline`.
- **No `--admin`, `--squash`, `--rebase`, or `--auto`.** The merge command was exactly
  `gh pr merge 12 --repo thezoid/ShopPyBot --merge --delete-branch=false`.
- **Branch protection byte-for-byte unchanged.** Read at 18:03:21Z before any mutation and again
  after all three tasks; identical both times:
  `strict: true`, contexts `["CodeQL", "test (windows-latest)", "test (ubuntu-latest)"]`,
  `enforce_admins: false`, `allow_force_pushes: false`. Phase 38 still owns these.
- **No package manager ran.** Consistent with the plan's T-36-01-SC disposition.

## Next Phase Readiness

**Ready for plan 36-02** (PR #11 conflict resolution). Its base is `origin/master` at
`36f75c7643e5a72b72ac95a6d521edd8ffbb2971`, not the `e98ec83` recorded at planning time. Plan
36-02 must re-derive `git merge-tree` against `36f75c7`; the two known conflicts
(`.github/dependabot.yml` add/add, `requirements.txt` content) were computed against `e98ec83`,
and PR #12 touched only `core/orchestrator.py` and a new test file, so neither conflict file was
disturbed. Re-derivation should confirm the same two conflicts, but it must be re-run, not assumed.

**Good news for plans 36-04 and 36-05.** Dependabot reacted to the PR #8 close in 8 seconds. That
is the interaction 36-RESEARCH.md Pitfall 5 predicted would lift the 90-day-inactivity
version-update pause, and it is live evidence Dependabot is not dormant on this repo. Those plans
should treat a stalled `@dependabot rebase` as a real anomaly worth investigating rather than an
assumed pause. Caveat: branch cleanup and version-update rebasing are different Dependabot
subsystems, so this is strong evidence, not proof.

**Merge order intact.** #12 landed before #11 exactly as the locked order requires, so PR #11's
conflict resolution will absorb the signal-handler fix in the same merge.

**One concern for plan 36-03's MAIN-01 verification.** PR #12's CI ran green on both runners in
about 32 seconds, but that is master's ~757-test suite, not the merged tree's ~939. It confirms
`ci.yml` compiles and schedules jobs on master today; it is not evidence the v4.1+v4.2 suite
passes. MAIN-01's real proof still lands in plan 36-03, against master's post-#11 HEAD.

## Self-Check: PASSED

Every artifact and commit claimed above was verified to exist on disk and in git history.

| Claim | Check | Result |
|-------|-------|--------|
| `36-MERGE-LOG.md` created | `test -f` | FOUND |
| `36-01-SUMMARY.md` created | `test -f` | FOUND |
| Task 1 commit `969b322` | `git log --oneline --all` | FOUND |
| Task 2 commit `d04c5ca` | `git log --oneline --all` | FOUND |
| Task 3 commit `c321509` | `git log --oneline --all` | FOUND |
| Summary commit `c618989` | `git log --oneline --all` | FOUND |
| Audit log names the tag | `grep -c pre-v5-mainline` | 2 |
| Summary records BASE_SHA | `grep -c e98ec83ff9e4...` | 2 |
| Summary records post-#12 master | `grep -c 36f75c7643e5...` | 3 |
| Summary records PR #12 head OID | `grep -c 3f27a2dff279...` | 1 |

Live GitHub state re-verified after all three tasks: `pre-v5-mainline` returns exactly 1 line from
`git ls-remote` and is an ancestor of `origin/master`; PR #12 is `MERGED`; PR #8 is `CLOSED` with
`merged=false`; branch protection on `master` is unchanged; `36-MERGE-LOG.md` carries 5 mutation
rows against a required minimum of 3.

*Phase: 36-mainline-reconciliation*
*Plan: 01*
*Completed: 2026-08-02*
