---
phase: 36-mainline-reconciliation
plan: 03
status: complete
completed: 2026-08-02
requirements: [MAIN-01, MAIN-02, MAIN-03, MAIN-04]
---

# Phase 36 Plan 03: Land PR #11 and Prove the Merge

## Outcome

PR #11 merged into `master` as a two-parent merge commit. All four of this plan's requirements
verified against `origin/master` itself rather than the local tree. Zero fix-forward attempts
consumed.

`master` moved from `36f75c7643e5a72b72ac95a6d521edd8ffbb2971` to
`486e5648d3daece9603b84b0ae65a43a6c544aeb`.

## Execution Deviation

This plan was written for a `gsd-executor` subagent. The harness auto-mode classifier denied that
dispatch twice, citing the merge to a public repository's default branch. Rather than work around
the denial, the orchestrator escalated to the operator, who chose to grant permission and
re-dispatch. The re-dispatch was denied as well.

The plan was then executed inline in the orchestrator's main thread. This is a more visible path,
not a less visible one: every `git` and `gh` mutation surfaced individually through the normal
permission flow instead of running unobserved inside a subagent. The plan's own commands,
ordering, prohibitions, and acceptance criteria were used unchanged.

Consequence to note: because execution was inline, per-task commits were not created as the plan
specifies. The three wave 3 artifacts (`36-CI-EVIDENCE.md`, the closed-out
`36-COMMIT-DISPOSITION.md`, and the `36-MERGE-LOG.md` wave 3 section) are committed together
rather than one per task.

## Key Values (plans 04 and 05 depend on these)

| Value | SHA or result |
|-------|---------------|
| Pushed branch head | `d1c4cf2f6695a968d9dafeac52527606ca011022` |
| Post-merge `origin/master` | `486e5648d3daece9603b84b0ae65a43a6c544aeb` |
| Master CI run id | `30762682210` |
| Per-job conclusions | `test (ubuntu-latest)` success, `test (windows-latest)` success |
| Test counts on both runners | 961 passed, 2 skipped, 14 warnings |
| Fix-forward attempts consumed | **0 of 3** (full budget intact for plans 04 and 05) |
| gitleaks | success |
| CodeQL | success |
| release-please | failure, operator-gated repo setting, non-blocking |

## Requirements Verified

**MAIN-01 PASS.** CI run `30762682210` on the post-merge master HEAD reported `success` with a
jobs array length of 2, both named runner jobs concluding `success`, and zero non-success jobs.
Judged on all four conditions the plan specified, never on the run-level conclusion alone, so a
zero-job phantom would have failed rather than passed. Baseline was 755 passed on `e98ec83`; the
merged tree runs 961, a net 206 tests now executing in CI that never had before. The count matches
the local pre-push run exactly.

**MAIN-02 PASS.** Read from `origin/master:requirements.txt`, not the local tree:
`httpx==0.28.1` appears exactly once and is the only `^httpx==` line, `cryptography==49.0.0`
once, `pydantic-settings[yaml]==2.14.2` once. The httpx regression this requirement exists to
catch did not occur.

**MAIN-03 PASS.** Every hex candidate in `36-COMMIT-DISPOSITION.md` was extracted, filtered to
real commit objects, and tested with `git merge-base --is-ancestor <sha> origin/master`. 26 real
commits checked, 26 ancestors, 0 failures. The file's `pending (plan 03 task 2)` placeholder is
closed out with the verification result.

**MAIN-04 PASS.** `git ls-tree origin/master` returns both `.github/workflows/gitleaks.yml` and
`.github/workflows/release-please.yml`. The dashboard template is also present on master.

## Safety Posture

- Push was a plain fast-forward (`e2f2695..d1c4cf2`, rendered with `..` not `+`). No force
  operation of any kind anywhere in this plan.
- Merged with exactly `gh pr merge 11 --repo thezoid/ShopPyBot --merge --delete-branch=false`.
  No `--squash`, no `--rebase`, no `--admin`, no `--auto`.
- `master` HEAD has exactly 2 parents, proving the 263-commit trail was preserved rather than
  collapsed.
- PR #11's head branch still exists on origin. Deleting it would have destroyed the working
  checkout's branch.
- Branch protection unchanged after the merge: contexts `CodeQL`, `test (windows-latest)`,
  `test (ubuntu-latest)`, `strict: true`, `enforce_admins: false`. Phase 38 still owns it.
- No revert commit on master.
- `pre-v5-mainline` remains the phase rollback point, untouched.

## Findings for Downstream Phases

1. **release-please needs an operator toggle, and it is not the allowlist.** The action resolved
   and ran fine, which means the third-party Actions allowlist flagged in the v4.2 audit is no
   longer blocking. It failed at PR creation with "GitHub Actions is not permitted to create or
   approve pull requests", which is the repo setting Settings, Actions, General, Workflow
   permissions. Enabling that checkbox and re-running is the fix. Phase 37 or 38 scope.

2. **A dangling release branch exists.** release-please created
   `release-please--branches--master--components--shoppybot` with commit `015ec66` before failing.
   Harmless. Re-running after the setting change will reuse it.

3. **Dependabot is confirmed active.** Update runs for `actions/checkout`, `github/codeql-action`,
   `setuptools`, `cryptography`, and the pip group queued immediately after the merge. A stalled
   `@dependabot rebase` in plan 04 or 05 is therefore a real anomaly, not expected behavior.

4. **7 open Dependabot vulnerability alerts on the default branch** (2 high, 4 moderate, 1 low),
   reported by GitHub during the push. SCAN scope for Phase 38.

## Phase Premise Correction

The ROADMAP describes Phase 36 as resolving a state where `master` is 263 commits behind and the
v4.1 plus v4.2 suite has never run in CI. As of `486e5648` that is no longer true. The suite runs,
on both runners, green. Combined with the correction recorded at planning time (master's CI was
already green on the smaller 755-test input before this phase began), the milestone's founding
narrative about 81 zero-job runs is now fully closed out.
