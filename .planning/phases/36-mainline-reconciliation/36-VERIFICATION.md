---
phase: 36-mainline-reconciliation
status: passed
verified: 2026-08-02
requirements_verified: [MAIN-01, MAIN-02, MAIN-03, MAIN-04, MAIN-05, MAIN-06, MAIN-07]
final_master_sha: a99b67de708fa75d2ce085824e6611485a173f22
---

# Phase 36: Verification

## Verdict: PASSED

All seven MAIN requirements verified by command output against live GitHub and git state, not by
inspection or assertion of intent. Every check below was run against `origin/master` itself
rather than the local tree.

## Goal Achievement

**Phase goal:** "`master` is the real ShopPyBot. Every v4.1 and v4.2 artifact is on the default
branch, and the suite those milestones claimed runs green in CI for the first time."

Achieved. `master` at `a99b67d` carries the full v4.1 plus v4.2 surface, and its CI runs 961
tests green on both `ubuntu-latest` and `windows-latest`.

## Requirement Results

| Req | Assertion | Result |
|-----|-----------|--------|
| MAIN-01 | CI run on master HEAD schedules a non-empty job list and passes both runners | **PASS**. Run `30763196475` on `a99b67d`: conclusion `success`, jobs length 2, both runner jobs `success`, 0 non-success. Also independently proven on `486e5648` (run `30762682210`) |
| MAIN-02 | PR #11's two conflicts resolved without dropping `httpx==0.28.1` | **PASS**. On `origin/master:requirements.txt`: `httpx==0.28.1` exactly once and the only `^httpx==` line; `cryptography==49.0.0` once; `pydantic-settings[yaml]==2.14.2` once |
| MAIN-03 | Local commits absent from PR #11's head triaged with a recorded decision, not swept in | **PASS**. 26 recorded commits, all 26 proven ancestors of `origin/master` via `git merge-base --is-ancestor`, 0 failures. Recorded in 36-COMMIT-DISPOSITION.md |
| MAIN-04 | PR #11 merged so `gitleaks.yml`, `release-please.yml` and every v4.1/v4.2 artifact exist on the default branch | **PASS**. `git ls-tree origin/master` returns both workflow files. Dashboard template also confirmed present |
| MAIN-05 | PR #12 merged | **PASS**. State `MERGED` at 18:08:41Z, head commit an ancestor of `origin/master` |
| MAIN-06 | Stale PR #8 closed rather than merged | **PASS**. State `CLOSED`, `mergedAt` null, comment thread contains a comment naming both `urllib3==2.7.0` and "Superseded", verified against the GitHub comments API |
| MAIN-07 | Dependabot PRs #15 through #20 resolved in a conflict-safe order accounting for the #19/#20 `ci.yml` collision | **PASS**. Open-PR list intersected against `[8,11,12,15,16,17,18,19,20]` returns empty. #17, #19, #20 merged; #15, #16, #18 closed by Dependabot as genuinely superseded. #19 and #20 serialized; their predicted collision materialised and was resolved by `@dependabot rebase`, never by hand-editing a Dependabot branch |

## Success Criteria from ROADMAP

| Criterion | Result |
|-----------|--------|
| A CI run on master schedules jobs and reports the full v4.1+v4.2 suite green on both runners | **MET**. 961 passed / 2 skipped on each runner. Note the criterion's premise that "81 consecutive runs have scheduled zero jobs" was already stale at planning time: master's CI was green on the smaller 755-test input before this phase began. Recorded as a planning correction in ROADMAP.md |
| `gitleaks.yml`, `release-please.yml`, the dashboard, and `httpx==0.28.1` all present on master at HEAD | **MET**. All four verified on `origin/master` |
| #8, #11, #12 and #15 through #20 all resolved, merged in an order that did not require re-resolving the #19/#20 `ci.yml` collision | **MET**. The collision was handled by Dependabot's own rebase after serialization, so no manual re-resolution occurred |
| Each local commit absent from PR #11's head carries a recorded include-or-exclude decision, and `git log master` matches it | **MET**. 26/26 ancestry-verified. The count in the criterion says 4; the true count at execution time was 26 and growing, which is recorded as a correction |

## Deviations from Plan

These are real and are recorded rather than smoothed over.

1. **Plans 03, 04 and 05 ran inline, not via `gsd-executor` subagents.** The harness auto-mode
   classifier denied the executor dispatch twice for the PR #11 merge. The operator was consulted
   and chose to grant permission and re-dispatch; the re-dispatch was denied as well. Execution
   moved into the orchestrator's main thread, which surfaced every mutation individually to the
   operator instead of running it unobserved. Consequence: no per-task commits for those plans,
   and wave 3's three artifacts landed in one commit.

2. **Plans 04 and 05 were executed by intent, not by their literal PR lists.** Dependabot
   self-closed #15, #16 and #18 as superseded during wave 3, and opened a new #21. The plans'
   mandatory direction check is what made this safe: it caught that merging #16 would have
   downgraded `cryptography` and reverted part of MAIN-02.

3. **PR #21 deliberately left open.** Out of MAIN-07's scope, and it carries a FastAPI
   `0.115.8 to 0.141.1` plus uvicorn `0.30.6 to 0.52.0` jump that crosses a recorded v4.1
   Phase 26 decision against upgrading FastAPI past 0.135 because of SSE sensitivity. Deferred
   to Phase 37 or 39 with a note to check the SSE tests. Reasoning in 36-04-SUMMARY.md.

4. **Plan 05 task 3 not executed.** The docs-only evidence PR onto master, added during plan
   revision to close the plan checker's Finding 3, was not run. See Outstanding below.

## Outstanding

| Item | Owner | Note |
|------|-------|------|
| Phase 36 evidence is not on the default branch | Phase 36 follow-up, before Phase 38 runs elsewhere | All artifacts are committed on `chore/v4.0-milestone-close`, which still exists on origin, so nothing is lost. A small docs-only PR moves them to master |
| release-please failing | Operator | Enable Settings, Actions, General, Workflow permissions, "Allow GitHub Actions to create and approve pull requests". Not the third-party allowlist, which is confirmed working |
| Dangling `release-please--branches--master--components--shoppybot` at `015ec66` | Phase 37/38 | Harmless side effect of the above |
| 7 Dependabot vulnerability alerts on master (2 high, 4 moderate, 1 low) | Phase 38 (SCAN) | Count recorded as of 2026-08-02 |
| PR #21 open | Phase 37 or 39 | Merge behind an SSE test check, not blind |

## Safety Record

- Master moved exactly 5 times, every one via `gh pr merge`. Zero direct pushes to master.
- Zero force operations across all five plans.
- Zero uses of `--admin`, `--squash`, `--rebase`, `--auto`, or `--delete-branch`.
- No revert commit on master.
- Branch protection byte-identical before and after: contexts `CodeQL`,
  `test (windows-latest)`, `test (ubuntu-latest)`, `strict: true`, `enforce_admins: false`.
- `pre-v5-mainline` tag intact at `e98ec83`, still a valid rollback point for the whole phase.
- Fix-forward budget: **0 of 3 consumed.** No fix-forward PR was ever needed.
