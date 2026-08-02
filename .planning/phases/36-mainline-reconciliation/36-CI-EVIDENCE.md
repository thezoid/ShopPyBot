# Phase 36: CI Evidence (MAIN-01)

Evidence that a real CI run on the post-merge `master` HEAD scheduled a non-empty job list and
passed on both runners. This is the artifact that disproves the milestone's founding premise,
that 81 consecutive runs on `master` scheduled zero jobs and produced no logs.

Recorded 2026-08-02 by the orchestrator running plan 36-03 inline. The plan was written for a
`gsd-executor` subagent, but the harness auto-mode classifier denied that dispatch twice, so
wave 3 was executed inline in the main thread with each mutation surfaced individually. The
assertions run are the plan's own, unchanged.

Fix-forward attempts used: 0 of 3

## MAIN-01 Result: PASS

| Field | Value |
|-------|-------|
| master SHA | `486e5648d3daece9603b84b0ae65a43a6c544aeb` |
| CI run id | `30762682210` |
| CI run URL | https://github.com/thezoid/ShopPyBot/actions/runs/30762682210 |
| Run conclusion | `success` |
| Jobs array length | **2** (non-empty, so the workflow compiled and scheduled) |
| `test (ubuntu-latest)` | `success`, 961 passed, 2 skipped, 14 warnings, 11.14s |
| `test (windows-latest)` | `success`, 961 passed, 2 skipped, 14 warnings, 22.19s |
| Non-success job count | 0 |

MAIN-01 was judged on all four required conditions, never on the run-level conclusion alone:
jobs array length of 2 or greater, every per-job conclusion `success`, both named runner jobs
present, and the conclusion not `startup_failure`. A run reporting a passing conclusion with an
empty jobs array is the historic bug and would have been recorded as a failure.

## Baseline Comparison

| Input | master SHA | Tests passed | Skipped |
|-------|-----------|--------------|---------|
| Pre-merge baseline | `e98ec83` | 755 | 2 |
| Post-#12 | `36f75c7` | 755 (unchanged, orchestrator fix only) | 2 |
| Post-#11 merged tree | `486e5648` | **961** | 2 |

Net gain: 206 tests now executing in CI that never had before. The CI count matches the local
pre-push run exactly (961 passed, 2 skipped of 963 collected), so the merged tree behaves
identically on the runners and on the development machine.

## Phase 38 Handoff: Non-Blocking Workflow Statuses

Per 36-CONTEXT.md "Verification Bar", the status of these workflows is recorded here but does
not block Phase 36. Phase 38 (SCAN-01 through SCAN-11) owns them.

| Workflow | Run id | Conclusion | Disposition |
|----------|--------|-----------|-------------|
| CI | 30762682210 | success | MAIN-01 evidence above |
| gitleaks | 30762682214 | **success** | No secrets found across the 263-commit merge surface. The Actions allowlist did NOT block this action, contrary to the expectation carried in 36-VALIDATION.md "Known Blocking Conditions" |
| CodeQL | (master `486e564`) | **success** | Passed on the merged tree |
| release-please | 30762682172 | **failure** | Operator-gated repo setting, NOT a merge defect. See below |

### release-please failure: classified

The failure is NOT the predicted Actions-allowlist problem. `googleapis/release-please-action@v5`
resolved and ran normally (release-please 17.6.0), built its release strategy, created the branch
`release-please--branches--master--components--shoppybot`, and successfully created a commit
`015ec66` on it. It failed only at the final step:

```
release-please failed: GitHub Actions is not permitted to create or approve pull requests.
https://docs.github.com/rest/pulls/pulls#create-a-pull-request
```

Cause: repository Settings, Actions, General, Workflow permissions, the checkbox
"Allow GitHub Actions to create and approve pull requests" is currently disabled. This is a
different setting from the third-party-action allowlist that the v4.2 audit flagged, and the
evidence here shows the allowlist is no longer blocking these actions.

Operator action required (Phase 37 or Phase 38 scope, not Phase 36): enable that checkbox, then
re-run the release-please workflow.

Side effect to be aware of: the branch
`release-please--branches--master--components--shoppybot` now exists on origin with commit
`015ec66`, created before the failure. It is harmless. Enabling the setting and re-running will
reuse it, or it can be deleted.

## Requirement Assertions Run

| Req | Assertion | Result |
|-----|-----------|--------|
| MAIN-01 | jobs length 2+, all conclusions success, both runners named | PASS |
| MAIN-02 | `httpx==0.28.1` exactly once, `^httpx==` exactly once, `cryptography==49.0.0` once, `pydantic-settings[yaml]==2.14.2` once, read from `origin/master` | PASS, 1/1/1/1 |
| MAIN-03 | every SHA in 36-COMMIT-DISPOSITION.md is an ancestor of `origin/master` | PASS, 26 real commits checked, 26 ancestors, 0 failures |
| MAIN-04 | `gitleaks.yml` and `release-please.yml` present on `origin/master` | PASS, 2 lines returned. Dashboard also confirmed present |
| MAIN-05 | PR #12 merged (wave 1) | PASS |
| MAIN-06 | PR #8 closed unmerged with a machine-verifiable reason (wave 1) | PASS |

## Safety Posture for Wave 3

- Push was a plain fast-forward: `e2f2695..d1c4cf2`, shown with `..` not `+`. No `--force`,
  no `--force-with-lease`.
- PR #11 merged with exactly `gh pr merge 11 --repo thezoid/ShopPyBot --merge --delete-branch=false`.
  No `--squash`, no `--rebase`, no `--admin`, no `--auto`.
- `master` HEAD has exactly 2 parents, proving a true merge commit preserved the 263-commit trail.
- PR #11's head branch `chore/v4.0-milestone-close` still exists on origin, not deleted.
- Branch protection read after the merge is unchanged: contexts `CodeQL`,
  `test (windows-latest)`, `test (ubuntu-latest)`, `strict: true`, `enforce_admins: false`.
- No revert commit exists on `master`.
- Zero fix-forward attempts were needed, so the phase-wide budget of 3 is fully intact for
  plans 04 and 05.

## Note for Plans 04 and 05

Dependabot is confirmed active. Immediately after the PR #11 merge, update runs were queued for
`actions/checkout`, `github/codeql-action`, `setuptools`, `cryptography`, and the pip group. This
supports wave 1's read that closing PR #8 lifted the 90-day inactivity pause. A stalled
`@dependabot rebase` in plan 04 or 05 should therefore be treated as a real anomaly rather than
as the expected consequence of a paused Dependabot.

GitHub also reported 7 open Dependabot vulnerability alerts on the default branch during the
push (2 high, 4 moderate, 1 low). That is SCAN scope for Phase 38, recorded here so the count at
this point in time is on record.
