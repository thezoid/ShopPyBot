# Phase 36 Merge Audit Log

Append-only audit trail of every `git` and GitHub mutation performed during Phase 36
(Mainline Reconciliation). One row per mutation. Plans 36-01 through 36-05 each append
their own rows; nothing in this file is edited or removed once written.

**Tooling constraint.** Every command in this phase was run with raw `git` and raw `gh`,
never through `rtk`. Reason (36-VALIDATION.md "Tooling constraint"): `rtk git log <range>`
was observed silently dropping merge commits from range output during scouting, and
merge-ancestry reasoning is this phase's core correctness surface.

**Force operations are prohibited phase-wide.** No `git push --force`, no
`--force-with-lease`, no `git tag -f`, no `git push origin :refs/...`, no `git clean`.
No `gh pr merge --admin` except the single named condition reserved by plan 36-03.

**Branch protection baseline on `master`** (read 2026-08-02T18:03:21Z, before any mutation;
this phase must not change it, Phase 38 owns it):
`strict: true`, contexts `["CodeQL", "test (windows-latest)", "test (ubuntu-latest)"]`,
`enforce_admins: false`, `allow_force_pushes: false`.

## Mutation Log

| Timestamp (UTC) | Action | Target | Command | Result |
|-----------------|--------|--------|---------|--------|
| 2026-08-02T18:02:41Z | create-annotated-tag + push | `refs/tags/pre-v5-mainline` at `e98ec83ff9e47459902c3c0615fd428f5dd27caf` | `git tag -a pre-v5-mainline e98ec83ff9e47459902c3c0615fd428f5dd27caf -m "Phase 36 rollback point: ..."` then `git push origin refs/tags/pre-v5-mainline` | OK. Pre-check `git ls-remote --tags origin refs/tags/pre-v5-mainline` returned empty (no existing rollback point to clobber). Tag object `7edffb33c2a54d3a99b65b61d616a6759d20c908`, peels to commit `e98ec83ff9e47459902c3c0615fd428f5dd27caf`. `git cat-file -t` = `tag` (annotated). `git merge-base --is-ancestor pre-v5-mainline origin/master` exit 0. ACTUAL BASE_SHA matches the planning-time expectation exactly. |
| 2026-08-02T18:04:50Z | update-branch | PR #12 head `fix/signal-handler-main-thread` | `gh pr update-branch 12 --repo thezoid/ShopPyBot` | OK, no conflict. Required because `required_status_checks.strict: true` left PR #12 at `BEHIND`. Head OID advanced `3f27a2dff279852ced3f8712b56f582173946a3b` to `b1d7b8f5aef3b8767236eb5ba02b60ec97894695` (an update merge commit, "Merge branch 'master' into fix/signal-handler-main-thread"). PR #12 is authored by `thezoid` (human), so `gh pr update-branch` was correct and `@dependabot rebase` was not applicable. |
| 2026-08-02T18:07:13Z | poll (read-only, no mutation) | PR #12 `mergeStateStatus` | `gh pr view 12 --repo thezoid/ShopPyBot --json mergeStateStatus --jq .mergeStateStatus`, 30s interval, cap 30 iterations | Reached `CLEAN` on iteration 4 of 30, well inside the 15-minute budget. Terminal check buckets, all `pass`, none `skipping`: `CodeQL`, `test (ubuntu-latest)`, `test (windows-latest)` (the three required contexts), plus `Analyze (actions)`, `Analyze (python)`, `.github/dependabot.yml`. Pitfall 4's skipped-satisfies-protection allowance was not needed. |
| 2026-08-02T18:08:39Z | merge-pr | PR #12 into `master` | `gh pr merge 12 --repo thezoid/ShopPyBot --merge --delete-branch=false` | OK. State `MERGED`, `mergedAt` `2026-08-02T18:08:41Z`. Merge commit `36f75c7643e5a72b72ac95a6d521edd8ffbb2971`. `origin/master` advanced `e98ec83ff9e47459902c3c0615fd428f5dd27caf` to `36f75c7643e5a72b72ac95a6d521edd8ffbb2971`. Ancestry proven for BOTH the pre-update head `3f27a2d` (the SHA MAIN-05 asserts) and the post-update head `b1d7b8f`, each `git merge-base --is-ancestor <sha> origin/master` exit 0. No `--admin`, no `--squash`, no `--rebase`, no `--auto`. Head branch deliberately retained. MAIN-05 satisfied. |

### Deviation from planning-time expectation (recorded, not papered over)

36-01-PLAN.md's `<verified_state>` described PR #12 as touching `core/orchestrator.py`. The live
`gh pr view 12 --json files` read at execution time showed **two** files: `core/orchestrator.py`
(+12/-0, MODIFIED) and `tests/test_signal_registration_thread.py` (+127/-0, ADDED). The head OID
`3f27a2d...` and head branch matched the expectation exactly, so this is an under-description in
the planning note rather than a changed premise. Merged as planned; recorded here because plans
02 and 03 reason about which files reached `master` in this phase.

## Recorded Values

| Name | Value | Source |
|------|-------|--------|
| BASE_SHA (phase rollback point) | `e98ec83ff9e47459902c3c0615fd428f5dd27caf` | `git rev-parse origin/master`, 2026-08-02T18:02:41Z, before any Phase 36 mutation |
| `pre-v5-mainline` tag object | `7edffb33c2a54d3a99b65b61d616a6759d20c908` | `git ls-remote origin refs/tags/pre-v5-mainline` |
| PR #12 head OID (pre-update, the SHA MAIN-05 asserts) | `3f27a2dff279852ced3f8712b56f582173946a3b` | `gh pr view 12 --json headRefOid`, read before `update-branch` |
| PR #12 head OID (post-update, actually merged) | `b1d7b8f5aef3b8767236eb5ba02b60ec97894695` | `gh pr view 12 --json headRefOid`, read after `update-branch` |
| PR #12 merge commit | `36f75c7643e5a72b72ac95a6d521edd8ffbb2971` | `gh pr view 12 --json mergeCommit` |
| `origin/master` after PR #12 (base for plan 36-02's conflict resolution) | `36f75c7643e5a72b72ac95a6d521edd8ffbb2971` | `git rev-parse origin/master`, 2026-08-02T18:08:5xZ |
