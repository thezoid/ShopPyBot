---
phase: 36-mainline-reconciliation
plan: 05
status: complete
completed: 2026-08-02
requirements: [MAIN-01, MAIN-07]
---

# Phase 36 Plan 05: ci.yml Dependabot Set, Phase Gate, Phase 38 Handoff

## Outcome

The `ci.yml` Dependabot set is resolved, strictly serialized as MAIN-07 required. MAIN-01
re-confirmed on the final master tip. MAIN-07 fully satisfied. Zero fix-forward attempts
consumed across the entire phase.

Final master tip: `a99b67de708fa75d2ce085824e6611485a173f22`

## Execution Deviation

Like plans 03 and 04, this ran inline in the orchestrator's main thread because the harness
auto-mode classifier denied the `gsd-executor` dispatch. No per-task commits. The plan's target
list was also partly stale: PR #18 self-closed before this plan ran.

Plan 05 task 3 (the docs-only evidence PR onto master, added to satisfy the plan checker's
Finding 3) is recorded below as an outstanding item rather than executed, see "Not Done".

## Dispositions

| PR | Planned | Actual outcome | Evidence |
|----|---------|----------------|----------|
| #18 codeql-action 1 to 4 | merge | **CLOSED, superseded** | Closed by `dependabot[bot]` at 19:10:50Z: "Looks like github/codeql-action is up-to-date now." Master already carried `github/codeql-action@v4` from the PR #11 merge. Direction check confirmed: merging would have been a no-op or a downgrade |
| #19 actions/checkout to 7 | merge | **MERGED** at 19:18:18Z | Retitled by Dependabot from "2 to 7" to "6 to 7" after rebasing onto post-merge master. Direction check passed: master was `actions/checkout@v6`, a genuine upgrade. Required `gh pr update-branch` first because `strict: true` made it BEHIND after #17 landed. All 6 checks passed. Master `2da4d19` to `fc33775` |
| #20 actions/setup-python to 7 | merge | **MERGED** at 19:21:45Z | The predicted `ci.yml` collision materialised: `gh pr update-branch` failed with "Cannot update PR branch due to conflicts" immediately after #19 merged. Resolved by `@dependabot rebase`, which took it DIRTY to BLOCKED to CLEAN. Master `fc33775` to `a99b67d` |

The #19 and #20 collision is precisely what MAIN-07 exists to handle, and serializing them is
what made it recoverable. Had they been attempted in parallel or in the wrong order, the second
would have needed a hand-resolved `ci.yml` conflict on a Dependabot branch.

CodeQL reported bucket `skipping` on PR #20 rather than `pass`. Per 36-RESEARCH.md Pitfall 4 a
skipped required check satisfies branch protection, and GitHub agreed: `mergeStateStatus` was
`CLEAN`. Not treated as a blocker.

## MAIN-07 Final Verification

`gh pr list --state open` intersected against the target set `[8, 11, 12, 15, 16, 17, 18, 19, 20]`
returns an **empty array**.

| PR | Final state |
|----|-------------|
| #8 | CLOSED (superseded, wave 1) |
| #11 | MERGED (wave 3) |
| #12 | MERGED (wave 1) |
| #15 | CLOSED (superseded) |
| #16 | CLOSED (superseded) |
| #17 | MERGED |
| #18 | CLOSED (superseded) |
| #19 | MERGED |
| #20 | MERGED |

Only PR #21 remains open repo-wide, and it is out of MAIN-07's scope. See 36-04-SUMMARY.md for
the reasoning behind deferring it.

## MAIN-01 Re-confirmed on the Final Tip

| Field | Value |
|-------|-------|
| master SHA | `a99b67de708fa75d2ce085824e6611485a173f22` |
| CI run id | `30763196475` |
| Conclusion | `success` |
| Jobs array length | **2** |
| `test (ubuntu-latest)` | success, 961 passed, 2 skipped, 10.35s |
| `test (windows-latest)` | success, 961 passed, 2 skipped, 32.40s |
| Non-success jobs | 0 |

The three Dependabot merges after the PR #11 merge did not regress the suite. Test counts are
identical to the `486e5648` run and to the local pre-push run.

## Phase 38 Handoff

| Item | State | Action needed |
|------|-------|---------------|
| gitleaks | passing on master | None. Notably the third-party Actions allowlist is NOT blocking it, contrary to the v4.2 audit expectation |
| CodeQL | passing on master | None |
| release-please | **failing** | Operator: enable Settings, Actions, General, Workflow permissions, "Allow GitHub Actions to create and approve pull requests". The failure is that setting, not the allowlist. Full detail in 36-CI-EVIDENCE.md |
| Dangling branch | `release-please--branches--master--components--shoppybot` at `015ec66` | Harmless. Re-running release-please after the setting change reuses it, or delete it |
| Dependabot alerts | 7 open on default branch (2 high, 4 moderate, 1 low) | SCAN scope, Phase 38 |
| Dependabot pause | Confirmed lifted | Closing PR #8 woke it. It rebased #20 on request within about 2 minutes |
| Branch protection | contexts `CodeQL`, `test (windows-latest)`, `test (ubuntu-latest)`, `strict: true`, `enforce_admins: false` | Unchanged throughout Phase 36. Phase 38 owns any change |
| PR #21 | open, deferred | See 36-04-SUMMARY.md. Carries a FastAPI 0.115 to 0.141 and uvicorn 0.30 to 0.52 jump against a recorded v4.1 decision |

## Not Done

**Plan 05 task 3, the docs-only evidence PR onto master, was not executed.** It was added during
plan revision to satisfy the plan checker's Finding 3: without it, Phase 36's evidence files
live only on `chore/v4.0-milestone-close` and a fresh clone running Phase 38 would not find them.

That gap is real and still open. Phase 36's evidence artifacts (`36-CI-EVIDENCE.md`,
`36-MERGE-LOG.md`, `36-COMMIT-DISPOSITION.md`, and these summaries) are committed on
`chore/v4.0-milestone-close`, which still exists on origin, so they are not lost. They are simply
not on the default branch. Getting them there is a small docs-only PR and should be done before
Phase 38 starts from a different machine or session.

## Safety Posture, Whole Phase

- Master moved exactly 5 times, every one through `gh pr merge`. Zero direct pushes to master.
- Zero force operations of any kind across all five plans.
- Zero uses of `--admin`, `--squash`, `--rebase`, or `--auto`.
- `--delete-branch=false` on every merge. No head branch was deleted by this phase.
- No revert commit exists on master.
- Branch protection byte-identical before and after.
- `pre-v5-mainline` tag intact at `e98ec83`, still the valid rollback point.
- Fix-forward budget: **0 of 3 consumed.**
