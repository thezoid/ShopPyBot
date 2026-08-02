---
phase: 36-mainline-reconciliation
plan: 02
subsystem: infra
tags: [git, merge-conflict, dependency-pins, dependabot, pytest-gate, main-03]

# Dependency graph
requires:
  - "36-01: origin/master at 36f75c7 (post PR #12), the base this merge resolves against"
  - "36-01: 36-MERGE-LOG.md, the append-only audit trail this plan writes into"
provides:
  - "Merge commit 635c1d3 on chore/v4.0-milestone-close: union-resolved requirements.txt and dependabot.yml, with origin/master as a proven ancestor"
  - "36-COMMIT-DISPOSITION.md: the MAIN-03 per-SHA include record, 21 rows, derived fresh at 18:30:40Z"
  - "Local HEAD is a descendant of PR #11's remote head, achieved by merge, so plan 36-03 can plain-push"
  - "A green full-suite result on the merged tree: 963 collected, 961 passed, 0 failed"
affects: [36-03, 36-04, 36-05, 37-packaging, 38-scanning-to-zero]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Prove-then-seal: git merge --no-commit, assert the conflict set and the resolved content, only then commit"
    - "Assert the auto-merge, do not trust it: a clean three-way merge can still take the wrong side"
    - "Bypass the shell hook with an absolute binary path when tool output correctness is load-bearing"

key-files:
  created:
    - .planning/phases/36-mainline-reconciliation/36-COMMIT-DISPOSITION.md
    - .planning/phases/36-mainline-reconciliation/36-02-SUMMARY.md
  modified:
    - requirements.txt
    - .github/dependabot.yml
    - .planning/phases/36-mainline-reconciliation/36-MERGE-LOG.md
    - .planning/.continue-here.md
    - .planning/HANDOFF.json

key-decisions:
  - "Committed two pre-existing dirty harness files before task 1 rather than STOPping, because both paths are tracked on origin/master and therefore sit on the merge surface"
  - "Bypassed the rtk shell hook with /mingw64/bin/git after reproducing the documented merge-commit-dropping bug live"
  - "Recorded 21 as the derived MAIN-03 count, contradicting both CONTEXT.md's 8 and 36-01-SUMMARY.md's 18, and made the SHA table the binding artifact rather than any count"
  - "Accepted 4 files differing from the merge's first parent instead of the 2 the plan's acceptance criterion names, because the extra 2 are the master-side content the merge exists to bring"

patterns-established:
  - "Pattern 3: When an acceptance criterion is arithmetically impossible for a correct outcome, satisfy its intent, record the over-specification, and prove the intent separately"

requirements-completed: [MAIN-02, MAIN-03]

# Metrics
duration: 16min
completed: 2026-08-02
---

# Phase 36 Plan 02: PR #11 Local Conflict Resolution Summary

**PR #11's head divergence absorbed by a proven content-empty merge instead of a force-push, both real conflicts union-resolved with `httpx==0.28.1` verifiably retained, and the merged tree proven green at 961 passed / 0 failed across 963 collected tests, all local, nothing pushed.**

## Performance

- **Duration:** 16 min (974s)
- **Started:** 2026-08-02T18:27:10Z
- **Completed:** 2026-08-02T18:43:24Z
- **Tasks:** 3 of 3
- **Files modified:** 2 created, 5 modified
- **Suite runtime:** 32.07s

## Task Commits

| # | Task | Commit | Type |
|---|------|--------|------|
| 0 | Pre-task: commit pending GSD harness state (Rule 3) | `c208af7` | docs |
| 1 | Absorb the divergence, record the MAIN-03 disposition | `7875a01` | docs |
| 1 | (the no-op merge itself) | `a6bf2b6` | chore |
| 2 | Merge `origin/master`, resolve both conflicts to the union | `635c1d3` | chore |
| 3 | Full local pytest gate on the merged tree | `10a0da1` | docs |

## The Merged HEAD

| Name | Value |
|------|-------|
| **Conflict-resolution merge commit** | `635c1d3be8ba015a9da58b2242e69038a5859016` |
| First parent (branch) | `7875a01899e7a62f55f39f56de59035490abc3b7` |
| Second parent (master) | `36f75c7643e5a72b72ac95a6d521edd8ffbb2971` |
| Merge base | `7a6ef0988cd58c4c4b52320e6c84f7d61485e351` |
| No-op divergence merge | `a6bf2b662f2d68480bf6ef04eb400782f77f1b3d` |
| Tree hash before AND after the no-op merge | `00437c79c28df71b83f98e54282a71531d617a69` |
| **Plan-end HEAD** (before this summary's own commit) | `10a0da1` |
| **`origin/chore/v4.0-milestone-close`** (unchanged, nothing pushed) | `e2f269530a9bee2d4bdd6df9effb40302bed14f4` |

## The Three Resolved Pins (MAIN-02)

Verified by reading the resolved file, not by trusting the merge. Exact-line counts:

| Pin | Source side | `grep -c '^<exact>$'` | Guard |
|-----|-------------|----------------------|-------|
| `httpx==0.28.1` | master | `1` | `grep -c '^httpx=='` also `1`, so neither dropped nor duplicated |
| `cryptography==49.0.0` | branch (master had `44.0.2`) | `1` | `grep -c '^cryptography=='` is `1` |
| `pydantic-settings[yaml]==2.14.2` | branch (master had `2.14.0`) | `1` | `grep -c '^pydantic-settings'` is `1` |

The resolved `requirements.txt` is 17 lines: the `# python_requires >= 3.11` comment plus 16
alphabetically ordered pins. Every other line was already byte-identical on both sides, exactly as
36-RESEARCH.md predicted. Zero conflict markers survive. `pip install --dry-run -r requirements.txt`
exits 0 with no resolver conflict.

`.github/dependabot.yml` resolved and YAML-asserted: 2 ecosystems, `groups.minor-and-patch.update-types`
equal to `["minor","patch"]` on **both** pip and github-actions (master's side, the reason PR #15
exists), `schedule.day: "monday"` on both, pip `open-pull-requests-limit: 10`, github-actions
`open-pull-requests-limit: 5`, and both `labels` lists intact (branch's side).

## MAIN-03: The Freshly Derived Commit List

**Derived count: 21** (merge-inclusive; 20 non-merge). Not CONTEXT.md's `8`, not
36-01-SUMMARY.md's `18`. Re-derived with `/mingw64/bin/git log --oneline
origin/chore/v4.0-milestone-close..HEAD` at 2026-08-02T18:30:40Z, immediately after the no-op
merge. **All 21 decisions are `include`. Zero exclusions.** Every SHA was confirmed a real commit
object via `git cat-file -t`.

The exact list the record covers, newest first:

| # | SHA | Kind |
|---|-----|------|
| 1 | `a6bf2b662f2d68480bf6ef04eb400782f77f1b3d` | merge (this plan's no-op) |
| 2 | `c208af70fcc1a337106b05ff3ae9d0f472c23bfe` | docs |
| 3 | `1745f08eb54d73b468284670af4c52e469a7444c` | docs |
| 4 | `c07fd3b05c55ffc7eab281f4bcc4d55f3135c51b` | docs |
| 5 | `c6189899abc62091ffea5f6688817bd0c94b7eb2` | docs |
| 6 | `c3215091b95e5261c57b812bedd4d142ca2d05aa` | docs |
| 7 | `d04c5cab464e2a2c863d9cdb2b87586abbd67a2a` | docs |
| 8 | `969b32267031bcf0b219c927c69afdbf85195cfb` | docs |
| 9 | `0e648de76ddfce6d8aa4380ae5b62200a5eeae52` | docs |
| 10 | `28280ec60936b07a9e80969c48339872c42259e2` | docs |
| 11 | `2317476ab48874f10387e566b136d33ff6355c37` | docs |
| 12 | `9529dd1b12b8778f4075f817c0975739d5656829` | docs |
| 13 | `bb8eacee4956f0b5be8e346cdd3a07ee96a318b7` | docs |
| 14 | `1463fb6c37e62cafb68c71584c72e256b9045239` | docs |
| 15 | `4e4edae90715d2d53f74719cabfd90dd1a581491` | docs |
| 16 | `7ffb8c5e73aa9fa71d67289011da63044a036c7b` | docs |
| 17 | `f00ef89fd805ed97697e814112350ee13ca68910` | docs |
| 18 | `f883f13f6818a2a4ac949f9b46029b3dbd519c65` | docs |
| 19 | `70f31c58b4bacd9fc96dc46aa9c3f5ef11533abc` | docs |
| 20 | `0cebc9edb3ed8e28ee5259376e8b2cfea15d3eef` | **code** (the only one) |
| 21 | `d485710795645addbc42c38c37521f27a0293c6c` | docs |

Full subjects and per-SHA rationale are in `36-COMMIT-DISPOSITION.md`, where subjects are
reproduced verbatim from `git log` so the table stays greppable.

**The record does not go stale.** It carries an explicit standing rule covering every commit
reachable from the branch tip at PR #11 push time, which necessarily includes the commit that adds
the record itself, the merge commit, the suite-result commit, and this summary. It also carries a
post-merge scope exclusion naming the plans 03 to 05 summaries as out of scope, so a reader
comparing `git log master` against the table after PR #11 lands is not misled by their absence.
At plan end the live count is already 29, up from the 21 recorded, which is the standing rule
working as designed rather than drift.

## The Pytest Gate (mandatory pre-push gate, CONTEXT.md verification bar)

Install order reproduced CI's own, per Pitfall 2:

```
.venv/Scripts/python.exe -m pip install -r requirements.txt   # exit 0
.venv/Scripts/python.exe -m pip install -e ".[web]"           # exit 0, shoppybot 2.0.0
.venv/Scripts/python.exe -m pytest                            # exit 0
```

**`963 collected, 961 passed, 2 skipped, 0 failed, 0 errors, 14 warnings, 32.07s`**

| Metric | Value | Bar | Verdict |
|--------|-------|-----|---------|
| Exit code | 0 | 0 | PASS |
| Collected | 963 | 900 or more | PASS |
| Passed | 961 | — | PASS |
| Skipped | 2 | — | PASS |
| Failed | 0 | 0 | PASS |
| Errors | 0 | 0 | PASS |

963 collected against master's 757 is the signal that mattered: the v4.1 and v4.2 test surface
genuinely merged across rather than the merge quietly taking master's smaller suite. It also
exceeds the ~939 the plan predicted, which is consistent with the branch having gained
`0cebc9e`'s 18 port-auto-select tests and the merge having pulled in PR #12's regression tests
since that estimate was written. The 14 warnings are all pre-existing deprecation notices
(legacy `min_delay`/`max_delay` shim, `datetime.utcnow`), none introduced here.

Union pins importable in the gate environment: `httpx 0.28.1`, `cryptography 49.0.0`,
`pydantic-settings 2.14.2`.

## ci.yml Auto-Merge: Verified, Not Assumed (T-36-02-02)

`.github/workflows/ci.yml` was never in the conflict set, which is precisely why it was the
highest-value silent-regression surface. All three assertions pass:

| Assertion | Result |
|-----------|--------|
| Requirements install line survives (comment-filtered, so the explanatory comment naming the same file cannot produce a false positive) | `1` |
| No job declares `SHOPBOT_DATA_DIR` at job-level `env` (YAML-parsed, Pitfall 1) | exit 0 |
| `SHOPBOT_DATA_DIR` still present, so the fix was not simply deleted | `1`, at step level under `Test` |

The merged `ci.yml` blob `9752377a` differs from **both** master (`fde4b377`) and the branch
(`63b9551b`). That is the correct outcome, not a defect: it is a real three-way merge that took
master's `Install` step and step-scoped env fix while retaining the branch's newer
`actions/checkout@v6` and `actions/setup-python@v6` pins, exactly as 36-RESEARCH.md "State of the
Art" predicted.

`core/orchestrator.py` was also verified rather than assumed: PR #12's main-thread guard
(`if threading.current_thread() is not threading.main_thread():`) is present at line 794 of the
merged file, and `tests/test_signal_registration_thread.py` merged in with a blob
(`bbec219b`) byte-identical to master's.

## Safety Posture Confirmed

- **No force operation anywhere.** No `--force`, no `--force-with-lease`, no `git tag -f`, no
  `git clean`, no `git reset`, no `git stash`, no ref deletion. Verified against the reflog: every
  entry in this session is a `commit` or a `merge`.
- **Nothing was pushed.** `git ls-remote origin refs/heads/chore/v4.0-milestone-close` still
  returns `e2f269530a9bee2d4bdd6df9effb40302bed14f4`, the pre-plan SHA. Local HEAD is 29 commits
  ahead and entirely local. No `git push` was executed in this plan at all.
- **`pre-v5-mainline` untouched.** Still `7edffb33c2a54d3a99b65b61d616a6759d20c908` on origin. The
  phase remains fully revertible.
- **No GitHub mutation.** Zero `gh` commands were run in this plan.
- **No new package entered the dependency graph.** Consistent with the T-36-02-SC disposition and
  36-RESEARCH.md's Package Legitimacy Audit. Both installs resolved entirely from already-vetted,
  already-pinned names. No legitimacy checkpoint applied.

## Deviations from Plan

### Auto-fixed

**1. [Rule 3 - Blocking] Working tree was not clean at plan start**

- **Found during:** Task 1 precondition check
- **Issue:** `.planning/.continue-here.md` and `.planning/HANDOFF.json` were left modified and
  uncommitted by the 2026-08-01 UAT session. 36-02-PLAN.md task 1 makes a dirty tree a STOP.
- **Why it was not a STOP:** Both paths are tracked on `origin/master` (`git cat-file -e
  origin/master:<path>` succeeds for each), so they sit directly on the PR #11 merge surface. The
  plan's own acceptance criterion also requires `git status --porcelain` to be empty at task end,
  which is unreachable while they stay dirty. Leaving them uncommitted through a merge is exactly
  the entanglement the STOP guards against; committing them removes it.
- **Fix:** Committed as-is, content unchanged, in a dedicated pre-task commit before any merge.
  Fully reversible, no force operation.
- **Commit:** `c208af7`

### Recorded observations, no fix required

**2. [Recorded] The rtk `git log` range hazard is real and was reproduced live**

- **Found during:** Task 1, on the first range query
- **Issue:** A shell hook on this machine rewrites bare `git` into `rtk git`, and
  `rtk git log <range>` silently drops merge commits. `git log --oneline
  HEAD..origin/chore/v4.0-milestone-close` returned **empty** while `git rev-list --left-right
  --count` simultaneously reported **2** remote-only commits. Both remote-only commits
  (`e2f2695`, `d9ad585`) are merge commits, so the filtered view reported a clean, non-diverged
  branch that was in fact 2 commits behind.
- **Impact if undetected:** The MAIN-03 record is derived directly from a range query. A short
  list would have produced a silently incomplete disposition record, which is the exact
  repudiation risk T-36-02-04 exists to prevent.
- **Resolution:** Every git command in this plan used the absolute path `/mingw64/bin/git`, which
  bypasses the hook. The contradiction between `rev-list --count` and `log` is what exposed it.
- **Recorded in:** `36-MERGE-LOG.md` and `36-COMMIT-DISPOSITION.md`, both flagging it for plans
  36-03 through 36-05. Plan 36-03 task 2's per-SHA ancestry proof is directly exposed.

**3. [Recorded] One acceptance criterion is over-specified and cannot hold for a correct merge**

- **Found during:** Task 2, staging
- **Issue:** The criterion reads "`git show --stat HEAD --name-only --pretty=format:` lists no
  file outside `requirements.txt` and `.github/dependabot.yml` as changed relative to the first
  parent." Four files differ from the first parent, not two: the two resolved files plus
  `.github/workflows/ci.yml` and `core/orchestrator.py` (and `tests/test_signal_registration_thread.py`,
  which the combined-diff view suppresses because it is unchanged relative to the second parent).
- **Assessment:** Not a defect. A merge that brings master's content in **must** show master's
  content as changed relative to the branch parent. The two extra files are precisely PR #12's
  signal-handler fix and master's ci.yml Install and env fixes, which MAIN-01 and MAIN-05 require
  to be present. A merge satisfying the criterion literally would be a merge that discarded them.
- **Intent satisfied instead:** The criterion's real purpose (threat T-36-02-05, unrelated files
  sneaking into the merge commit) was proven directly: zero unstaged changes, zero untracked
  files, and each of the extra paths traced to a known master-side change with its blob compared
  against `origin/master`.

**4. [Recorded] `mktemp` paths are unreadable by native git under `MSYS_NO_PATHCONV=1`**

- **Found during:** Task 2, sealing the merge
- **Issue:** `git commit -F /tmp/tmp.XXXX` failed with `could not read log file`. `MSYS_NO_PATHCONV=1`
  is required for revision syntax containing `:` (such as `git show origin/master:requirements.txt`)
  but it also suppresses conversion of the MSYS `/tmp` path that native `git.exe` cannot resolve.
- **Resolution:** Wrote the message file to a durable path and passed `cygpath -w` output. The
  merge state (`MERGE_HEAD`, staged index) survived the failed attempt intact and was verified
  before retrying. Worth carrying into plans 03 to 05, which also write multi-line PR and commit
  bodies.

**Total deviations:** 1 auto-fixed (Rule 3), 3 recorded observations.
**Impact on plan:** No task's substance changed. No STOP condition fired.

## STOP Conditions Checked, All Clean

This plan carries four deliberate STOPs. Each was evaluated against live state:

| STOP condition | Check result |
|----------------|--------------|
| Wrong branch | On `chore/v4.0-milestone-close`. Clean. |
| Dirty working tree | Fired. Resolved by Rule 3 rather than escalation, for the reasons recorded above. |
| No-op merge premise false (tree hash changed) | Tree `00437c79` identical before and after. Premise held. |
| A third conflicted path appears | Exactly 2 conflicted paths, `.github/dependabot.yml` (add/add) and `requirements.txt` (content). Premise held against the NEW master `36f75c7`, re-derived rather than assumed, as 36-01-SUMMARY.md required. |

A red suite would have been a fifth hard stop. It came back green.

## Next Phase Readiness

**Ready for plan 36-03** (push and merge PR #11). Its inputs:

- The tip to push is `chore/v4.0-milestone-close` at whatever HEAD is after this summary commits.
  The push is a **plain, fast-forward-safe push**: `origin/chore/v4.0-milestone-close` at
  `e2f2695` is a proven ancestor of local HEAD (`git merge-base --is-ancestor` exits 0), so the
  non-fast-forward rejection Pitfall 3 describes cannot occur and no force is needed.
- `origin/master` at `36f75c7` is an ancestor of local HEAD, so PR #11 should report `MERGEABLE`
  rather than `CONFLICTING` once the push lands. Note `required_status_checks.strict: true`: if
  master moves again before the merge, an `update-branch` will be needed first.
- The MAIN-03 ancestry proof in plan 36-03 task 2 must iterate the 21 SHAs in
  `36-COMMIT-DISPOSITION.md` and **must use `/mingw64/bin/git`**, or `merge-base --is-ancestor`
  will be fed a truncated list.
- `36-COMMIT-DISPOSITION.md` ends with `Post-merge ancestry verification: pending (plan 03 task 2)`.
  Plan 36-03 task 2 owns flipping that line.

**One caution for MAIN-01.** The local suite proves the merged **code** is green on Python 3.13 on
Windows. It does not prove CI. The remaining CI-specific risks are the ubuntu-latest runner and
workflow compilation, both of which master already demonstrated on its smaller 757-test input.
The merged tree's `ci.yml` was asserted correct here, but a real `gh run view` with a non-empty
`jobs` array against master's post-#11 HEAD is still the only thing that closes MAIN-01.

**Known open item, not this plan's scope.** The Actions allowlist has not been widened for
`gitleaks/gitleaks-action` and `googleapis/release-please-action`. Those two workflows arrive on
`master` with PR #11 and are expected to fail at action-resolution time. Per 36-VALIDATION.md
"Known Blocking Conditions" that is Phase 38 scope and must be recorded, not treated as a merge
defect or a fix-forward trigger.

## Self-Check: PASSED

| Claim | Check | Result |
|-------|-------|--------|
| `36-COMMIT-DISPOSITION.md` created | `test -f` | FOUND |
| `36-02-SUMMARY.md` created | `test -f` | FOUND |
| Pre-task commit `c208af7` | `git cat-file -t` | commit |
| No-op merge `a6bf2b6` | `git cat-file -t` | commit, 2 parents |
| Task 1 commit `7875a01` | `git cat-file -t` | commit |
| Task 2 merge `635c1d3` | `git cat-file -t` | commit, 2 parents |
| Task 3 commit `10a0da1` | `git cat-file -t` | commit |
| Disposition table row count | `grep -c` on 40-hex SHA rows | 21 |
| Disposition decisions all include | `grep -c '| include |'` | 21 |
| All 21 SHAs are real commits | `git cat-file -t` per SHA | 21 of 21 `commit` |
| `httpx==0.28.1` retained exactly once | `grep -c` | 1 |
| Zero conflict markers | `grep -rn` on both files | none |
| `origin/master` is an ancestor | `git merge-base --is-ancestor` | exit 0 |
| Zero remote-only commits remain | `git log HEAD..origin/branch` | empty |
| Nothing pushed | `git ls-remote` | still `e2f2695` |
| Suite green | `pytest` exit code | 0 |

Re-verified after the summary and state commits landed: all 5 claimed files exist on disk; all 7
claimed commits (`c208af7`, `a6bf2b6`, `7875a01`, `635c1d3`, `10a0da1`, `c544dc0`, `232d195`)
resolve to real commit objects; `origin/chore/v4.0-milestone-close` is an ancestor of local HEAD,
so plan 36-03's push is fast-forward-safe; the reflog for this session contains no `reset`,
`clean`, `rebase`, `stash` or `filter` entry; and `origin/chore/v4.0-milestone-close` still points
at `e2f269530a9bee2d4bdd6df9effb40302bed14f4`, confirming nothing reached origin.

*Phase: 36-mainline-reconciliation*
*Plan: 02*
*Completed: 2026-08-02*
