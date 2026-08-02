# Phase 36: MAIN-03 Commit Disposition Record

Every local commit absent from PR #11's remote head at derivation time, with an explicit
include-or-exclude decision keyed by SHA. MAIN-03 is satisfied by **recording** a deliberate
decision per SHA, not by excluding any commit. The locked decision in 36-CONTEXT.md
("Merge Execution and Authority") is **include all**.

## Derivation

**Derived:** 2026-08-02T18:30:40Z, immediately after the no-op merge that absorbed PR #11's
remote-only commits (`a6bf2b6`), and before the `origin/master` conflict-resolution merge.

**Command (raw `git`, absolute path, never through `rtk`):**

```
/mingw64/bin/git log --oneline origin/chore/v4.0-milestone-close..HEAD
/mingw64/bin/git rev-list --count origin/chore/v4.0-milestone-close..HEAD
```

**Derived count: 21** (merge-inclusive). The non-merge count is 20; the single merge commit is
`a6bf2b6`, created by this plan's own task 1.

**Ranged against:** `origin/chore/v4.0-milestone-close` at
`e2f269530a9bee2d4bdd6df9effb40302bed14f4`, fetched 2026-08-02T18:27Z.

**Do not read a count from 36-CONTEXT.md.** That document records the include-all decision
against "8 commits", a number that was already stale when 36-01-SUMMARY.md re-derived it as 18.
The count moves every time a planning or execution commit lands on this branch. The binding
artifact is the SHA table below, not any count written elsewhere in the phase.

### Tooling note

Invoking bare `git` on this machine is rewritten by a shell hook into `rtk git`, and
`rtk git log <range>` **silently drops merge commits from range output**. Verified live during
this plan: `git log --oneline HEAD..origin/chore/v4.0-milestone-close` returned empty while
`git rev-list --left-right --count` reported 2 remote-only commits, and the absolute-path
invocation `/mingw64/bin/git` correctly listed `e2f2695` and `d9ad585`. Every command in this
record used the absolute path. Any later re-derivation must do the same or it will produce a
short list.

## Disposition Table

All 21 commits: **include**. Each SHA below was confirmed to be a real commit object with
`git cat-file -t <sha>` returning `commit`.

| SHA | Subject | Decision | Rationale |
|-----|---------|----------|-----------|
| `a6bf2b662f2d68480bf6ef04eb400782f77f1b3d` | chore(36): absorb remote-only merge commits from PR #11 head | include | This plan's own no-op merge. Content-empty (pre-merge and post-merge tree hashes both `00437c79`), and the mechanism that removes the divergence without a force-push. |
| `c208af70fcc1a337106b05ff3ae9d0f472c23bfe` | docs(36): commit pending GSD harness state from the 2026-08-01 UAT session | include | Pre-existing uncommitted harness bookkeeping left dirty by the prior session. Both paths are tracked on `origin/master`, so they sit on the merge surface and had to be committed before merging. |
| `1745f08eb54d73b468284670af4c52e469a7444c` | docs(36-01): flag MAIN-03 commit-count drift from 8 to 18 for plan 36-02 | include | Phase 36 planning artifact. Documentation only. |
| `c07fd3b05c55ffc7eab281f4bcc4d55f3135c51b` | docs(36-01): complete rollback-point and PR-disposition plan | include | Phase 36 execution artifact. Documentation only. |
| `c6189899abc62091ffea5f6688817bd0c94b7eb2` | docs(36-01): summarize rollback tag, PR #12 merge, PR #8 close | include | Phase 36 execution artifact (36-01-SUMMARY.md). Documentation only. |
| `c3215091b95e5261c57b812bedd4d142ca2d05aa` | docs(36-01): record PR #8 superseded close in phase 36 audit log | include | Phase 36 audit trail. Documentation only. |
| `d04c5cab464e2a2c863d9cdb2b87586abbd67a2a` | docs(36-01): record PR #12 merge in phase 36 audit log | include | Phase 36 audit trail. Documentation only. |
| `969b32267031bcf0b219c927c69afdbf85195cfb` | docs(36): open phase 36 merge audit log | include | Phase 36 audit trail. Documentation only. |
| `0e648de76ddfce6d8aa4380ae5b62200a5eeae52` | docs(36): close plan-checker findings on phase 36 plans | include | Phase 36 planning artifact. Documentation only. |
| `28280ec60936b07a9e80969c48339872c42259e2` | docs(36): create phase 36 mainline reconciliation plans | include | Phase 36 planning artifact. Documentation only. |
| `2317476ab48874f10387e566b136d33ff6355c37` | docs(36): add validation strategy | include | Phase 36 planning artifact (36-VALIDATION.md). Documentation only. |
| `9529dd1b12b8778f4075f817c0975739d5656829` | docs(36): research phase domain | include | Phase 36 planning artifact (36-RESEARCH.md). Documentation only. |
| `bb8eacee4956f0b5be8e346cdd3a07ee96a318b7` | docs(36): smart discuss context | include | Phase 36 planning artifact (36-CONTEXT.md). Documentation only. |
| `1463fb6c37e62cafb68c71584c72e256b9045239` | docs: create milestone v5.0 roadmap (15 phases, 36-50) | include | Milestone v5.0 planning trail. Named explicitly in 36-CONTEXT.md's original include-all set. Documentation only. |
| `4e4edae90715d2d53f74719cabfd90dd1a581491` | docs: define milestone v5.0 requirements (84 across 10 workstreams) | include | Milestone v5.0 planning trail. Named explicitly in 36-CONTEXT.md's original include-all set. Documentation only. |
| `7ffb8c5e73aa9fa71d67289011da63044a036c7b` | docs: research milestone v5.0 workstream H (plugin ecosystem) | include | Milestone v5.0 planning trail. Named explicitly in 36-CONTEXT.md's original include-all set. Documentation only. |
| `f00ef89fd805ed97697e814112350ee13ca68910` | docs: start milestone v5.0 Real Release and Plugin Ecosystem | include | Milestone v5.0 planning trail. Named explicitly in 36-CONTEXT.md's original include-all set. Documentation only. |
| `f883f13f6818a2a4ac949f9b46029b3dbd519c65` | docs: record 2026-08-01 UAT audit session in STATE.md | include | UAT audit record. Named explicitly in 36-CONTEXT.md's original include-all set. Documentation only. |
| `70f31c58b4bacd9fc96dc46aa9c3f5ef11533abc` | docs: record 2026-08-01 live UAT results across 11 phase artifacts | include | UAT audit record. Named explicitly in 36-CONTEXT.md's original include-all set. Documentation only. |
| `0cebc9edb3ed8e28ee5259376e8b2cfea15d3eef` | feat(cli): auto-select next free port when the dashboard port is busy | include | **The only code commit in the entire set.** Ships with 18 tests. Named explicitly in 36-CONTEXT.md's original include-all set. |
| `d485710795645addbc42c38c37521f27a0293c6c` | docs: plant SEED-003 — remote plugin manager + third-party disclaimer | include | Seed artifact. Named explicitly in 36-CONTEXT.md's original include-all set. Documentation only. (Subject reproduced verbatim from `git log` so this row stays greppable.) |

**Composition:** 20 documentation or audit commits, 1 code commit (`0cebc9e`), of which 1 is the
content-empty no-op merge (`a6bf2b6`). Zero exclusions.

## Standing Rule

The include decision above covers **every commit reachable from this branch tip at PR #11 push
time**, not only the 21 SHAs enumerated. That necessarily includes:

1. The commit that adds this very file, which cannot appear in a list derived before it exists.
2. The conflict-resolution merge commit created by plan 36-02 task 2.
3. The suite-result commit created by plan 36-02 task 3.
4. `36-02-SUMMARY.md` and any STATE.md or ROADMAP.md update committed before plan 36-03 pushes.

These are all phase 36 execution artifacts of the same kind already enumerated above, produced by
the same locked include-all decision. No commit created between this derivation and the PR #11
push is excluded, and none requires a separate decision. A reader auditing `git log master` should
expect **more** commits than this table lists, not fewer.

## Post-Merge Scope Exclusion

Phase 36 execution artifacts created **after** the PR #11 merge are **out of scope** for this
record. Specifically: `36-03-SUMMARY.md`, `36-04-SUMMARY.md`, `36-05-SUMMARY.md`, the later
appends to `36-MERGE-LOG.md`, and `36-CI-EVIDENCE.md`.

Those artifacts do not exist yet at derivation time, cannot reach `master` through PR #11, and
reach it instead through the separate docs-only PR that plan 36-05 task 3 opens (see
36-VALIDATION.md, "Evidence durability"). A reader comparing `git log master` against this table
immediately after PR #11 lands will not find them, and that absence is expected and correct, not
a dropped commit.

## Verification Status

Post-merge ancestry verification: pending (plan 03 task 2)

Plan 36-03 task 2 closes this by running `git merge-base --is-ancestor <sha> origin/master` for
every SHA in the table above and recording the result. Until then this record states an intended
disposition; it does not yet claim proven ancestry on `master`.
