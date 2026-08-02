# Phase 36: Mainline Reconciliation - Context

**Gathered:** 2026-08-02
**Status:** Ready for planning
**Mode:** Smart discuss (autonomous)

<domain>
## Phase Boundary

Make `master` the real ShopPyBot. Every v4.1 and v4.2 artifact reaches the default
branch, the nine open pull requests reach a resolved state, and the v4.1+v4.2 test
suite produces its first genuinely green CI run on `master`.

In scope: resolving PR #11's two file conflicts, merging PRs #11, #12 and #15 through
#20, closing PR #8 with a recorded reason, triaging the local commits absent from PR
#11's head, and confirming a real `ci.yml` run schedules jobs and passes on both
runners.

Out of scope: branch protection and required status checks (Phase 38), wheel
packaging correctness (Phase 37), gitleaks and release-please workflow green runs
(Phase 38), and any new feature code.

</domain>

<decisions>
## Implementation Decisions

### Merge Execution and Authority

- GitHub mutations are executed autonomously: `gh pr merge`, `gh pr close`, and pushes
  to PR head branches. The phase is unachievable without them.
- PR #11 lands as a **merge commit**, not a squash and not a rebase. The 263 commits
  are real per-plan history from four milestones and the project deliberately built
  that atomic-commit trail; squashing destroys it.
- All 8 local commits currently unpushed on `chore/v4.0-milestone-close` are pushed to
  PR #11's head branch and included in the merge. This is the MAIN-03 recorded
  decision: include all. The 8 are `d485710` (SEED-003), `0cebc9e` (feat(cli) port
  auto-select, the only code commit), `70f31c5` and `f883f13` (UAT audit records), and
  `f00ef89`, `7ffb8c5`, `4e4edae`, `1463fb6` (the v5.0 planning trail).
- Note: the ROADMAP says "4 local commits". That count was written before the four
  v5.0 planning commits existed. The correct current count is 8, and the plan must
  record the decision against 8, not 4.
- Before any merge, tag `origin/master` as `pre-v5-mainline` and push the tag. This is
  the rollback point for the entire phase.

### Conflict Resolution and PR Disposition

- `requirements.txt`: union resolution, newest pin wins, `httpx` retained.
  Result must contain `httpx==0.28.1` (from master, MAIN-02 requires it),
  `cryptography==49.0.0` (from branch), `pydantic-settings[yaml]==2.14.2` (from
  branch). Every other line is identical on both sides.
- `.github/dependabot.yml`: union resolution. Keep master's `groups:` blocks for both
  ecosystems, since PR #15 exists because of them. Keep the branch's `labels:`,
  `day: "monday"`, and pip `open-pull-requests-limit: 10`.
- PR #8 (urllib3 1.26.5 to 1.26.18, open since 2023) is closed unmerged with a comment
  recording that it is superseded because `master` already carries `urllib3==2.7.0`.
  This satisfies MAIN-06.
- Merge order is fixed: **#12, then #11, then the pip set (#16, #17, #15), then the
  github-actions set (#18, #19, #20) one at a time, waiting for Dependabot to rebase
  between each.** Rationale: #12 is a single non-overlapping commit and merging it
  first means PR #11's conflict resolution captures it in the same merge; the pip and
  actions sets touch disjoint files so they cannot collide with each other; #18, #19
  and #20 all edit `ci.yml` so they must be strictly serialized, which is what MAIN-07
  asks for.
- PR #16 (cryptography 44.0.2 to 49.0.0) is expected to self-close as superseded once
  #11 lands, because the branch already pins 49.0.0. That still counts as resolved for
  success criterion 3, but the plan must confirm the closure rather than assume it.

### Verification Bar

- Success criterion 1 is met when `ci.yml` reports the full suite green on both
  `ubuntu-latest` and `windows-latest` against `master` HEAD, confirmed by polling
  `gh run view` and observing that jobs were actually scheduled and logs produced.
  The 81 prior zero-job runs are the thing being disproved.
- `gitleaks.yml`, `release-please.yml` and CodeQL run status is recorded in the phase
  artifacts but does not block phase completion. Phase 38 owns those, and the Actions
  allowlist for third-party actions is a known open operator item.
- If `master` goes red after PR #11 merges, the response is **fix forward** via a
  follow-up PR, not revert. Reverting a 263-commit merge costs more than it recovers.
  Hard cap of 3 fix-forward attempts, then stop and escalate rather than grind.
- Branch protection and required status checks are **not** set in this phase. Setting
  them before the first green run would block the fix-forward PRs this phase may need.
  Phase 38 (SCAN-08 through SCAN-11) owns them.
- Before pushing the resolved merge, run the full pytest suite locally against the
  merged tree. Local environment needs `pip install -e .[web]` plus `httpx`, invoked
  as `.venv\Scripts\python.exe -m pytest`. A bad conflict resolution must be caught
  before it reaches `master`.

### Claude's Discretion

- Exact commit message wording for the merge and any fix-forward commits.
- Whether to resolve PR #11's conflicts by merging `origin/master` into the branch or
  by an equivalent mechanism, provided the resolved file contents match the union
  rules recorded above.
- Poll interval and timeout when waiting on GitHub Actions runs and Dependabot
  rebases.
- Plan decomposition, task ordering within plans, and where verification checkpoints
  sit.

</decisions>

<code_context>
## Existing Code Insights

### Verified Facts (scouted 2026-08-02, before planning)

- `origin/master` HEAD is `e98ec83`. It already carries PR #13 (`4123059`, the
  `SHOPBOT_DATA_DIR` step-scope fix) and PR #14 (`e98ec83`, dependabot groups).
- **MAIN-01 is already satisfied on master.** The branch still has the broken
  job-level `SHOPBOT_DATA_DIR` line, but `git merge-tree --write-tree origin/master
  HEAD` produces a tree whose `.github/workflows/ci.yml` contains only master's
  step-level fixed version. The merge takes the fix automatically. MAIN-01 needs
  confirmation in the merged result, not new work.
- PR #11 head is `chore/v4.0-milestone-close` (the current local working branch),
  state `CONFLICTING` / `DIRTY`. `git merge-tree` reports exactly two conflicts:
  `.github/dependabot.yml` (add/add) and `requirements.txt` (content). `ci.yml`
  auto-merges cleanly and correctly.
- PR #12 head is `fix/signal-handler-main-thread`, single commit `3f27a2d`, state
  `MERGEABLE` / `BEHIND`. Verified **not** an ancestor of the PR #11 branch, so it is
  genuinely separate work.
- The local branch is 8 commits ahead of `origin/chore/v4.0-milestone-close` and 0
  behind it.
- PR file scopes confirmed via `gh pr view --json files`: #17 touches only
  `pyproject.toml`; #15 touches `pyproject.toml` and `requirements.txt`; #18, #19 and
  #20 each touch `.github/workflows/ci.yml`.

### Established Patterns

- Planning artifacts live under `.planning/phases/NN-slug/` and are committed with
  `docs(NN): ...` messages.
- The project's git convention is conventional commits with atomic per-task commits,
  which is the reason merge-commit was chosen over squash for PR #11.

### Integration Points

- `.github/workflows/ci.yml` is the single workflow whose green run defines this
  phase's success.
- `requirements.txt` and `.github/dependabot.yml` are the only two files needing
  manual conflict resolution.

</code_context>

<specifics>
## Specific Ideas

- The tag name for the rollback point is `pre-v5-mainline`.
- The PR #8 closing comment must state the concrete reason (superseded, master already
  at `urllib3==2.7.0`), not a bare close.
- The MAIN-03 include-or-exclude record must be written against all 8 commits by SHA,
  so a reader can check `git log master` against the recorded decision rather than
  inferring it.

</specifics>

<deferred>
## Deferred Ideas

- Branch protection and required status checks: Phase 38 (SCAN-08 through SCAN-11).
- Actions allowlist widening for `gitleaks/gitleaks-action` and
  `googleapis/release-please-action`: known open operator item, surfaces in Phase 38.
- Dependabot repo-level unpause: recorded in STATE.md as an operator action, gated on
  this phase landing, actioned in Phase 38 (SCAN-01).

</deferred>
