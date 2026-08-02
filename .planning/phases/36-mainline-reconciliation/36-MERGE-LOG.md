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

| 2026-08-02T18:11:19Z | close-unmerged + comment | PR #8 `dependabot/pip/urllib3-1.26.18` (Bump urllib3 from 1.26.5 to 1.26.18) | `gh pr close 8 --repo thezoid/ShopPyBot --delete-branch=false --comment "Superseded and closed unmerged ... urllib3==2.7.0 ..."` | OK. State `CLOSED`, `mergedAt` `null` (raw JSON `{"mergedAt":null}`), `merged: false`, `closed_at` `2026-08-02T18:11:19Z`. Premise proven BEFORE the close: `git show origin/master:requirements.txt` yields exactly one `urllib3==` line and it is `urllib3==2.7.0`, which is ahead of this PR's 1.26.18 target, so merging would be a downgrade. Closing comment `https://github.com/thezoid/ShopPyBot/pull/8#issuecomment-5159680032` matches both required substrings; the GitHub comments API returns 1 comment satisfying `urllib3==2[.]7[.]0` AND `superseded` (case-insensitive). MAIN-06 satisfied. |

| 2026-08-02T18:29Z | commit (local, plan 36-02 pre-task hygiene) | `.planning/.continue-here.md`, `.planning/HANDOFF.json` | `git add` + `git commit` | OK. Working tree was NOT clean at plan 36-02 start: both files were left modified and uncommitted by the 2026-08-01 UAT session. Both paths are tracked on `origin/master` (`git cat-file -e origin/master:<path>` succeeds for each), so they sit on the PR #11 merge surface, and 36-02-PLAN.md task 1 requires an empty `git status --porcelain` at task end. Committed as-is, content unchanged, as commit `c208af70fcc1a337106b05ff3ae9d0f472c23bfe`. Deviation Rule 3 (blocking issue), fully reversible, no force operation. |
| 2026-08-02T18:30Z | merge (local, no-op) | `origin/chore/v4.0-milestone-close` at `e2f269530a9bee2d4bdd6df9effb40302bed14f4` into local `HEAD` | `git merge origin/chore/v4.0-milestone-close -m "chore(36): absorb remote-only merge commits from PR #11 head"` | OK, "Merge made by the 'ort' strategy", zero conflicts. **Content-empty no-op PROVEN, not assumed:** pre-merge `git rev-parse HEAD^{tree}` = `00437c79c28df71b83f98e54282a71531d617a69`; post-merge `git rev-parse HEAD^{tree}` = `00437c79c28df71b83f98e54282a71531d617a69`. IDENTICAL. A `git merge-tree --write-tree HEAD origin/chore/v4.0-milestone-close` dry run at the same HEAD returned the same hash beforehand. Merge commit `a6bf2b662f2d68480bf6ef04eb400782f77f1b3d`. Divergence before: 20 local-only / 2 remote-only (`e2f2695`, `d9ad585`). After: `git log --oneline HEAD..origin/chore/v4.0-milestone-close` is EMPTY and `git merge-base --is-ancestor origin/chore/v4.0-milestone-close HEAD` exits 0. No `--force`, no `--force-with-lease`, no push. |
| 2026-08-02T18:30:40Z | derive + write (local) | `36-COMMIT-DISPOSITION.md` (MAIN-03) | `git log --oneline origin/chore/v4.0-milestone-close..HEAD` (absolute-path git) | **Derived count: 21** merge-inclusive, 20 non-merge. NOT the 8 in 36-CONTEXT.md nor the 18 in 36-01-SUMMARY.md; re-derived fresh after the no-op merge, per the MAIN-03 assertion row. All 21 decisions are `include`, zero exclusions. Every SHA confirmed a real object (`git cat-file -t` returns `commit` for all 21). Composition: 20 docs/audit commits plus 1 code commit (`0cebc9e`, port auto-select), of which 1 is the content-empty no-op merge. Record carries the standing rule (covers commits created after derivation) and the post-merge scope exclusion (plans 03 to 05 summaries are out of scope). |

### Plan 36-02 re-derivation of the conflict premise against the NEW master (`36f75c7`)

36-01-SUMMARY.md required this to be re-run rather than assumed, because the two conflicts were
originally computed against `e98ec83`, before PR #12 landed. Re-run at 2026-08-02T18:28Z:

`git merge-tree --write-tree origin/master HEAD` reports **exactly two conflicted paths**, the
same two as at planning time:

| Path | Conflict type |
|------|---------------|
| `.github/dependabot.yml` | add/add |
| `requirements.txt` | content |

`.github/workflows/ci.yml` and `core/orchestrator.py` both report `Auto-merging` with no conflict.
`core/orchestrator.py` appears only because PR #12 touched it, and it merges clean. The premise
holds against the new master; no third conflicted path appeared, so no STOP condition fired.

### Tooling hazard CONFIRMED LIVE during plan 36-02 (upgrade from the note below)

The 36-VALIDATION.md tooling constraint was not merely precautionary. Reproduced directly:

| Invocation | `git log --oneline HEAD..origin/chore/v4.0-milestone-close` output |
|------------|---------------------------------------------------------------------|
| bare `git` (hook-rewritten to `rtk git`) | **EMPTY** (wrong) |
| `/mingw64/bin/git` (absolute path, hook bypassed) | `e2f2695`, `d9ad585` (correct) |

A shell hook on this machine rewrites bare `git` into `rtk git`, and `rtk git log <range>` drops
merge commits from range output. Both remote-only commits here ARE merge commits, so the filtered
view reported a clean, non-diverged branch that was in fact 2 commits behind. `git rev-list
--left-right --count` was correct under both invocations, which is what exposed the contradiction.

**Every git command in plan 36-02 used `/mingw64/bin/git`.** Plans 36-03 through 36-05 must do the
same for any ancestry, range, rev-list or log query. The MAIN-03 ancestry proof in plan 36-03
task 2 is directly exposed to this hazard.

### Observed master `urllib3` pin (recorded either way, per task 3)

`git show origin/master:requirements.txt | grep -E "^urllib3=="` returned `urllib3==2.7.0`, and
the exact-match count `grep -c "^urllib3==2.7.0$"` returned `1`. The superseded rationale is
therefore true as written, not assumed. Read against `origin/master` at `36f75c7` (post PR #12).

### Dependabot reacted to the PR #8 close within 8 seconds (Pitfall 5 evidence, good news)

`gh api repos/thezoid/ShopPyBot/issues/8/timeline` records two events in order:

| Event | Actor | Timestamp (UTC) |
|-------|-------|-----------------|
| `closed` | `thezoid` | 2026-08-02T18:11:19Z |
| `head_ref_deleted` | `dependabot[bot]` | 2026-08-02T18:11:27Z |

The head branch `dependabot/pip/urllib3-1.26.18` no longer exists on origin, but **this executor
did not delete it**. `--delete-branch=false` was passed and was honoured (independently confirmed
by PR #12, whose head `fix/signal-handler-main-thread` still exists on origin after the same flag
was used on `gh pr merge`). The deleting actor is `dependabot[bot]`, 8 seconds after the close,
which is Dependabot's normal self-cleanup on a closed Dependabot PR. PR #8's head SHA was
`8a915e6728e43d251cc26e094ccd456fc38a497f`; the PR record retains it.

This is the interaction 36-RESEARCH.md Pitfall 5 predicted would lift the 90-day-inactivity
version-update pause, and the 8-second reaction is direct live evidence that Dependabot is
**responsive on this repo right now**, not dormant. Plans 36-04 and 36-05 should treat a stalled
`@dependabot rebase` as a real anomaly rather than an assumed pause. Note the caveat: branch
cleanup and version-update rebasing are different Dependabot subsystems, so this is strong
evidence rather than proof.

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
| PR #8 head SHA (closed unmerged, branch since self-deleted by Dependabot) | `8a915e6728e43d251cc26e094ccd456fc38a497f` | `gh api repos/thezoid/ShopPyBot/pulls/8 --jq .head.sha` |
| PR #8 superseded comment | `https://github.com/thezoid/ShopPyBot/pull/8#issuecomment-5159680032` | `gh api repos/thezoid/ShopPyBot/issues/8/comments` |

## Tooling Note for Later Plans

36-01-PLAN.md task 3's acceptance-criteria command embeds `\\.` inside a jq regex. As invoked
through this harness's Bash tool on Windows, one backslash layer was consumed before jq saw it,
and jq rejected the expression with `invalid escape sequence "\."`. The assertion itself is fine;
only the escaping is fragile. Later plans should use a POSIX bracket class, which needs no
backslash and survives any number of quoting layers:

`gh api repos/thezoid/ShopPyBot/issues/8/comments --jq '[.[] | select((.body | test("urllib3==2[.]7[.]0")) and (.body | test("superseded";"i")))] | length'`

Also note `gh pr view <n> --json mergedAt --jq .mergedAt` prints an **empty line**, not the
literal text `null`, for an unmerged PR. Assert against `gh pr view <n> --json mergedAt` returning
`{"mergedAt":null}`, or against `gh api repos/.../pulls/<n> --jq .merged` returning `false`.
A `test "$(... --jq .mergedAt)" = null` comparison fails on a correctly closed PR.
