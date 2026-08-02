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

## Recorded Values

| Name | Value | Source |
|------|-------|--------|
| BASE_SHA (phase rollback point) | `e98ec83ff9e47459902c3c0615fd428f5dd27caf` | `git rev-parse origin/master`, 2026-08-02T18:02:41Z, before any Phase 36 mutation |
| `pre-v5-mainline` tag object | `7edffb33c2a54d3a99b65b61d616a6759d20c908` | `git ls-remote origin refs/tags/pre-v5-mainline` |
