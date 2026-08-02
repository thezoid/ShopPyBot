# Phase 36: Mainline Reconciliation - Research

**Researched:** 2026-08-02
**Domain:** Git merge mechanics, GitHub CLI/API operations, Dependabot lifecycle, GitHub Actions CI verification
**Confidence:** HIGH (nearly every claim below was verified live against the actual repo, not inferred from training data)

## Summary

This is not a code-architecture phase; it is a git/GitHub operations phase, and the research
was executed that way: every claim below was checked against the live repo (`thezoid/ShopPyBot`)
using `git merge-tree`, `gh api`, `gh run view`, and dry-run `pip install`, not just read from
docs. Two live findings materially change the risk picture the phase was scoped against, and
both are corrections to facts that were true when scouted but have since changed:

**Correction 1 — CI is not "never green."** The already-scouted fact that master has "81
consecutive CI runs that scheduled zero jobs" was true historically but is now stale. A `CI`
workflow run against current `origin/master` HEAD (`e98ec83`, timestamped **2026-08-02T03:49:42Z,
hours before this research session**) shows both `test (ubuntu-latest)` and `test
(windows-latest)` jobs completed with `conclusion: success`, running the real `Install` and
`Test` steps and reporting `755 passed, 2 skipped` across 757 collected tests. Master's ci.yml
(already fixed for the `runner`-context bug) is proven, today, to compile, schedule jobs, install
dependencies, and run pytest to green — end to end, on both runners. This shrinks Phase 36's real
risk surface: MAIN-01 is not "prove CI can run at all," it is "prove the *merged, larger* test
suite (branch has 92 test files / ~939 tests vs. master's 82 files / 755) stays green under a
ci.yml that is independently already proven correct on a smaller input."

**Correction 2 — a second, more dangerous variant of the MAIN-01 bug already existed and is
already fixed on master, but is invisible from the branch's own ci.yml.** Empirically reproducing
CI's `Install` step (`pip install -e .[web]` in a clean venv) proves that `pyproject.toml`'s
`[project.dependencies]` declares only `platformdirs==4.10.0` — every other runtime dependency,
**including `pytest` itself**, lives only in `requirements.txt`. `pip install -e .[web]` alone
installs 6 packages; `pytest --tb=short` afterward fails with `No module named pytest`. This is a
second, independent way for the branch's own `ci.yml` to fail even after the `runner`-context bug
is fixed (branch's Install step is `pip install -e .[web]` with **no** `requirements.txt`
install — confirmed by direct read). Master's ci.yml already carries the fix (`pip install -r
requirements.txt` before `pip install -e ".[web]"`, with an inline comment describing this exact
failure mode), and `git merge-tree --write-tree origin/master HEAD` confirms the merged tree takes
master's whole `Install` step verbatim, not just the `runner`-context env fix. **MAIN-01's
resolution is more complete than the original framing suggested — but only because the merge
takes master's version. Do not let the branch's own ci.yml discovery narrow the scope; the merged
tree already has both fixes.**

**Correction 3 — the PR #11 head branch has diverged from local HEAD via a stray, content-empty
merge commit.** `origin/chore/v4.0-milestone-close` (PR #11's head) currently has a commit
(`e2f2695`, "Merge branch 'master' into chore/v4.0-milestone-close", committer `GitHub
<noreply@github.com>`, dated 2026-08-01) that local HEAD does not have. `git merge-tree
--write-tree` proves this commit is content-identical to the branch tip before it (it merged in
an already-absorbed, ancient master ref and changed no files) — but its mere existence means a
plain `git push` of the resolved local branch will be rejected as non-fast-forward. The safe,
non-destructive fix (verified via a second `git merge-tree` dry run) is to merge
`origin/chore/v4.0-milestone-close` into local HEAD first — proven to be a zero-conflict,
content-identical no-op — before merging `origin/master` to resolve the two real conflicts. This
avoids any `--force-with-lease` push and the destructive-operation approval gate that would
trigger.

**Primary recommendation:** Treat MAIN-01 as verification work, not fix work (the fix already
exists on master and merges in automatically) — confirm it with `gh run view` after PR #11
lands. Do the PR #11 conflict resolution as: merge `origin/chore/v4.0-milestone-close` (no-op) →
merge `origin/master` (2 real conflicts) → resolve both files per the union rules below → run the
full local pytest suite → push (plain fast-forward-safe push, not force) → poll checks → `gh pr
merge 11 --merge`. Branch protection on `master` already requires `CodeQL`, `test
(windows-latest)`, and `test (ubuntu-latest)` to pass (verified live) — this was not anticipated
in CONTEXT.md's framing but does not block the plan: `enforce_admins` is `false`, so `--admin` is
available as a fallback, and the required checks are demonstrably achievable without it.

## Architectural Responsibility Map

This phase has no application-code tiers; the "architecture" is the set of systems whose state
must move in lockstep.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Conflict resolution (`requirements.txt`, `dependabot.yml`) | Local git workspace | — | Must happen before any push; GitHub has no server-side conflict editor suitable for scripted, reproducible resolution |
| Merge/close mutations (PR #8/#11/#12/#15-20) | GitHub REST/GraphQL API (via `gh` CLI) | — | `gh pr merge` / `gh pr close` are the only sanctioned mutation path per CONTEXT.md |
| CI execution and verification | GitHub Actions runners (`ubuntu-latest`, `windows-latest`) | GitHub Actions API (`gh run`) for polling | Runners produce the ground truth; `gh run` is the read path, never a substitute for actually letting the workflow execute |
| Dependabot PR rebase after base-branch changes | GitHub Dependabot service | `@dependabot rebase` comment command as manual trigger | Automatic rebase-on-base-change is the default; manual command is the fallback if it stalls |
| Pre-push safety gate | Local pytest (`.venv\Scripts\python.exe -m pytest`) | — | CONTEXT.md's own bar: full suite must pass locally on the resolved tree before any push reaches `master`'s protected branch |
| Branch protection enforcement | GitHub branch protection (already configured on `master`) | — | Pre-existing, not something this phase sets up (that's SCAN-08, Phase 38) — but its current rules constrain how merges must be sequenced |

## Package Legitimacy Audit

**Not applicable to this phase.** Phase 36 does not introduce any new package. It resolves a
merge conflict between two versions of `requirements.txt` that already exist in the repo's own
history — every package in both the master-side and branch-side versions
(`cryptography`, `httpx`, `pydantic-settings`, `keyring`, `nodriver`, `pygame`, `pytest`,
`pytest-asyncio`, `pyyaml`, `requests`, `selenium`, `urllib3`, `webdriver-manager`, `colorama`,
`platformdirs`) was already vetted and pinned in prior milestones. No `pip install <new-package>`
occurs in this phase's scope. The union-resolved file (see Code Examples) was dry-run installed
into a clean venv with `pip install --dry-run -r <union-file>` and resolved without conflict,
confirming the two sides' pins are mutually compatible — this is a compatibility check, not a
provenance check, and none was needed since no new package enters the dependency graph.

## Standard Stack

### Core (already present, verified live)

| Tool | Version | Purpose | Verification |
|------|---------|---------|---------------|
| git | 2.54.0.windows.1 | merge-tree dry runs, conflict resolution | `git --version` [VERIFIED: local shell] |
| gh CLI | 2.89.0 (2026-03-26) | PR merge/close, run polling, PR/branch state queries | `gh --version` [VERIFIED: local shell] |
| Python | 3.13.13 | local pytest gate; matches CI's `python-version: "3.13"` pin | `.venv\Scripts\python.exe --version` [VERIFIED: local shell] |
| pytest | 9.0.3 | full-suite pre-push gate | `pip show pytest` in local `.venv` [VERIFIED: local shell] |

No new tooling is required. `gh auth status` confirms an authenticated session with `repo` and
`workflow` scopes against `github.com` account `thezoid`, sufficient for every mutation this phase
needs (`gh pr merge`, `gh pr close`, `git push`).

### Alternatives Considered

| Instead of | Could use | Tradeoff |
|------------|-----------|----------|
| `git merge origin/master` into the branch, then push | Resolve conflicts via GitHub's web UI conflict editor | This is almost certainly how `e2f2695` (the stray commit, see Summary) was created. It is unscriptable, unauditable, and — as demonstrated by that exact commit's content — trivially produces a silently-wrong resolution (it reproduced the branch's own file content byte-for-byte, discarding nothing from master, because it happened to merge an already-absorbed old master ref). Do not use the web UI for this merge |
| `--force-with-lease` push to reconcile the stray-commit divergence | Merge `origin/chore/v4.0-milestone-close` into local HEAD first (verified no-op) | The merge-first approach was proven safe and conflict-free in this session (`git merge-tree --write-tree HEAD origin/chore/v4.0-milestone-close` produces a tree identical to `HEAD`'s own tree). It avoids a force-push entirely, so it does not trigger the global destructive-operation approval gate. Use it as the default; force-push is a fallback only if the executor prefers a cleaner (single-merge) history |

## Architecture Patterns

### PR #11 Conflict Resolution Sequence (verified safe, no force-push)

```
git fetch origin
git merge origin/chore/v4.0-milestone-close   # no-op: proven content-identical to HEAD's own tree
git merge origin/master                        # real conflicts: .github/dependabot.yml, requirements.txt
#   -> resolve both files per the Code Examples union content below
git add .github/dependabot.yml requirements.txt
git commit                                      # completes the merge commit
.venv\Scripts\python.exe -m pytest              # full local suite must be green before push
git push origin chore/v4.0-milestone-close      # plain push; fast-forward-safe once the no-op merge above lands
```

Why the first `git merge origin/chore/v4.0-milestone-close` step matters: without it, `git push`
after resolving conflicts will be rejected (`! [rejected] ... (non-fast-forward)`) because the
remote branch has a commit local history does not, even though that commit changes no files. This
step was verified in this session with `git merge-tree --write-tree HEAD
origin/chore/v4.0-milestone-close`, which returned a tree hash identical to `HEAD`'s own tree —
confirming zero conflict risk and zero content change.

### Merge Order Execution Pattern (per locked decision)

```
1. gh pr merge 12 --merge --delete-branch=false     # single commit, no overlap with #11
2. (PR #11 conflict resolution sequence above, now captures #12 automatically via origin/master)
3. gh pr merge 11 --merge --delete-branch=false      # after checks pass (see CI Polling below)
4. gh pr close 8 --comment "Superseded: master already carries urllib3==2.7.0 (was 1.26.5->1.26.18 in this PR)."
5. For each of #16, #17, #15 (pip set, in that order): wait for MERGEABLE, gh pr merge <n> --merge
6. For each of #18, #19, #20 (actions set, strictly serialized, all touch ci.yml): wait for
   MERGEABLE after the previous one lands, gh pr merge <n> --merge
```

Note on step 5: PR #16 (cryptography) is expected to auto-close as superseded once #11 lands,
since the branch already pins `49.0.0` — confirm via `gh pr view 16 --json state,mergeable`
rather than assuming; if GitHub does not auto-close it (it may instead show `mergeStateStatus:
CLEAN` with a 0-line diff), close it explicitly with the same superseded rationale as #8.

### CI Polling Pattern (verified command set)

```bash
# Find the run for a specific commit SHA (not just "latest") — the flag that matters:
gh run list --branch master --workflow "CI" --commit <sha> --json databaseId,status,conclusion

# Inspect job-level detail (this is how you distinguish "0 jobs scheduled" from "jobs ran and passed"):
gh run view <run-id> --json jobs,conclusion,status
#   jobs: []                          -> workflow failed to compile, 0 jobs scheduled (the historic bug)
#   jobs: [...conclusion: "success"]  -> real pass
#   jobs: [...conclusion: "failure"]  -> real failure, needs fix-forward

# Exit-code-friendly form for scripting / CI gates:
gh run view <run-id> --exit-status
```

`gh run list` and `gh run view` do not accept a workflow-name filter in the same call as
`--commit` in all `gh` versions reliably — verified in this session that `--branch <name>
--workflow "CI" --commit <sha>` filters correctly together on `gh` 2.89.0.
[VERIFIED: `gh run list` output against this repo]

A workflow that fails to *compile* (the historic `runner`-in-job-level-env bug) does not appear
in `gh run list` with `conclusion: failure` and `jobs: []` in every case — it can also simply not
appear as a run at all, or appear with `conclusion: startup_failure`. Check both `jobs: []` and
`conclusion` for `startup_failure` / `failure` combined with an empty `jobs` array as the signal.
[CITED: observed directly in this repo's own history — run `28146746372` (pre-fix, commit
`d9ad585`) returns `"conclusion":"failure","jobs":[]`]

### `gh pr merge` Flag Reference

[CITED: cli.github.com/manual/gh_pr_merge]

| Flag | Effect | Relevant here |
|------|--------|----------------|
| `-m, --merge` | Creates a merge commit | Required for PR #11 per locked decision (not squash, not rebase) |
| `--auto` | Enables GitHub's auto-merge: completes the merge automatically once required checks pass and the branch is up to date | Optional convenience; CONTEXT.md's verification bar wants an explicit, logged `gh run view` confirmation before merge, so prefer explicit poll-then-merge over `--auto` for auditability, but `--auto` is safe to use as a backstop if a session needs to end before checks finish |
| `-d, --delete-branch` | Deletes the head branch after merge | Do **not** use for PR #11 — its head is the local working branch (`chore/v4.0-milestone-close`); deleting it out from under the local checkout is destructive and unnecessary |
| `--admin` | Bypasses branch protection / required-checks requirements using administrator privileges | Not expected to be needed (see Common Pitfalls: required status checks) but is a legitimate fallback since `enforce_admins: false` on `master` |

### Branch Protection State on `master` (live, not anticipated in CONTEXT.md)

[VERIFIED: `gh api repos/thezoid/ShopPyBot/branches/master/protection`]

```json
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["CodeQL", "test (windows-latest)", "test (ubuntu-latest)"]
  },
  "enforce_admins": { "enabled": false },
  "allow_force_pushes": { "enabled": false }
}
```

`master` already requires `CodeQL`, `test (windows-latest)`, and `test (ubuntu-latest)` to report
success (or `skipped`, see Common Pitfalls) before a PR can merge through the normal path, and
`strict: true` means the branch must be up to date with `master` at merge time. `enforce_admins:
false` means the repo owner can override with `gh pr merge --admin` if a required check is stuck,
but given master's ci.yml is proven working end-to-end today, the expected path does not need it.
This directly affects PR #12 (currently `mergeStateStatus: BEHIND`) and the pip/actions PRs —
each needs to be up to date with the just-landed prior merge before `strict` mode will let it
merge normally, which is exactly why the locked merge order serializes them rather than merging
in parallel.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Waiting for a Dependabot PR to become mergeable after a base-branch change | A sleep-and-poll loop against raw diff content | `gh pr view <n> --json mergeStateStatus` polled until `CLEAN`, with `@dependabot rebase` as the manual nudge if it stalls | Dependabot's own rebase automation already handles conflict-free base-branch drift; re-deriving mergeability by diffing files yourself duplicates GitHub's own merge computation and can disagree with it |
| Determining whether a workflow run actually executed vs. failed to compile | Scraping the Actions web UI or guessing from `conclusion` alone | `gh run view <id> --json jobs` and checking whether the `jobs` array is empty | This is the exact, minimal signal that distinguishes the historic "0 jobs scheduled" bug from a real pass/fail, and it is a single documented JSON field |
| Verifying the merged `requirements.txt` union is self-consistent | Trusting the union table by inspection alone | `pip install --dry-run -r <file>` against a clean venv | Verified in this session: this catches resolver conflicts (e.g., an incompatible pin) before they reach CI, in seconds, with zero network side effects beyond metadata fetches |

**Key insight:** every "don't hand-roll" item above resolves to "ask the platform (`gh`, `pip`)
for its own opinion via a documented, scriptable command, rather than re-deriving the same
answer by reading file diffs by eye." This phase already tends to over-trust already-scouted
facts as ground truth (see Corrections 1-3 in the Summary) — the antidote is the same discipline
applied at execution time, not just at research time: re-run the verification commands
immediately before acting, not just once during planning.

## Common Pitfalls

### Pitfall 1: `runner` context in job-level `env:` fails the whole workflow to compile
**What goes wrong:** Referencing `${{ runner.temp }}` inside `jobs.<job_id>.env` (not
`jobs.<job_id>.steps[*].env`) makes GitHub Actions unable to compile the workflow at all — the
run either never appears or appears with `conclusion: failure` / `startup_failure` and `jobs: []`.
**Why it happens:** [CITED: docs.github.com/en/actions/learn-github-actions/contexts — the
context-availability table lists `runner` as available starting at
`jobs.<job_id>.steps.env`/`steps.if`/etc., not at `jobs.<job_id>.env`]. The `runner` context does
not exist yet at job-level env evaluation time.
**How to avoid:** Keep `SHOPBOT_DATA_DIR: ${{ runner.temp }}/shopbot` scoped to the `Test` step's
own `env:` block, exactly as master's fixed version already does (and the merged tree already
inherits automatically per `git merge-tree` verification).
**Warning signs:** A CI run for the branch that never appears in `gh run list`, or a run whose
`jobs` array is empty despite a `conclusion` of `failure`.
**Status for this phase:** Already resolved in the merged tree; this pitfall is a verification
target (confirm it stayed fixed), not a fix task.

### Pitfall 2: `pip install -e .[web]` does not install `requirements.txt`
**What goes wrong:** `pyproject.toml`'s `[project.dependencies]` declares only
`platformdirs==4.10.0`. An editable install with the `web` extra pulls in only `fastapi`,
`uvicorn[standard]`, `jinja2`, `python-multipart`, and their transitive deps — not `pytest`,
`cryptography`, `pydantic-settings`, `keyring`, `nodriver`, `pygame`, `requests`, `selenium`, or
`httpx`. The very next CI step (`pytest --tb=short`) then fails with `No module named pytest` /
`pytest: command not found`.
**Why it happens:** Empirically confirmed in this session: `pip install --quiet -e
"E:/repos/ShopPyBot[web]"` into a clean venv, followed by `pip list`, shows exactly 20 packages
installed, none of them `pytest`. Running `pytest --tb=short` in that venv immediately afterward
fails with `No module named pytest`.
**How to avoid:** Install `requirements.txt` first: `pip install -r requirements.txt` then `pip
install -e ".[web]"` — the exact order master's ci.yml already uses.
**Warning signs:** CI reports `jobs` scheduled (so Pitfall 1 is not the cause) but the `Test` step
fails immediately with a "command not found" or `ModuleNotFoundError` before any test collection
output appears.
**Status for this phase:** Already resolved on master's side and confirmed to flow into the
merged tree via `git merge-tree`. This is the pitfall the requirements.txt conflict resolution
must not accidentally undo — if the merge somehow drops the `Install` step's second line, this
regresses.

### Pitfall 3: A stray, content-empty merge commit on the PR head blocks a plain `git push`
**What goes wrong:** `origin/chore/v4.0-milestone-close` carries commit `e2f2695` (a "Merge
branch 'master' into chore/v4.0-milestone-close" authored via what its committer identity
(`GitHub <noreply@github.com>`) suggests was the GitHub web UI), which local `HEAD` does not have
as an ancestor. A plain `git push` after resolving PR #11's conflicts on top of local `HEAD` will
be rejected as non-fast-forward.
**Why it happens:** Someone merged an old, already-superseded `master` ref (`d9ad585`, from the
original June 2026 v4.0 close, not current `master`) into the branch via a path that did not go
through the same local clone. `git diff 32d1bbd0 e2f2695` (the branch tip immediately before that
commit, vs. the commit itself) returns **empty** — it changed no files.
**How to avoid:** Before resolving PR #11's real conflicts, run `git merge
origin/chore/v4.0-milestone-close` — this was verified in this session to be a genuine no-op
(`git merge-tree --write-tree HEAD origin/chore/v4.0-milestone-close` produces `HEAD`'s own tree
hash exactly), so it introduces no new conflicts and requires no force-push afterward.
**Warning signs:** `git push` failing with `(non-fast-forward)` despite having just resolved every
conflict `git merge-tree` reported.

### Pitfall 4: CodeQL shows `skipping` on file-scope-narrow PRs, not `pass` — this is fine
**What goes wrong:** Assuming a required check that shows `skipping` (observed live on PR #15,
which touches only `pyproject.toml`/`requirements.txt`, no `.py` files) is a blocker.
**Why it happens:** [CITED: docs.github.com/en/repositories/.../about-protected-branches — "A
required status check ... `success`, `skipped`, and `neutral`" all satisfy the requirement].
CodeQL's own path-based triggers skip runs when no analyzed-language files changed.
**How to avoid:** Do not add path filters or gate the merge on a manual "wait for CodeQL to turn
green" step for PRs that will never trigger it — `skipping` already counts.
**Warning signs:** A PR appears "stuck" on required checks in a status dashboard while `gh pr
merge` actually succeeds without `--admin` — that's expected, not a bug.

### Pitfall 5: Dependabot's repo-level pause state has (at least) two different mechanisms, and only one was directly verifiable
**What goes wrong:** Assuming "Dependabot is paused" (already-scouted fact) means the schedule-
driven version-update PRs (#15-20) cannot be rebased or that `@dependabot rebase` will be a
no-op.
**Why it happens:** `gh api repos/.../automated-security-fixes` — the one pause-adjacent
endpoint this session could directly query — returned `{"enabled": true, "paused": false}`, but
that field covers **security-alert-driven** Dependabot PRs, not the **schedule/version-update**
PRs `dependabot.yml` produces (which is what generated #15-20). GitHub's most common "paused"
mechanism for version updates is the documented 90-day-inactivity auto-pause [CITED:
docs.github.com/en/code-security/dependabot/working-with-dependabot/managing-pull-requests-for-dependency-updates
— rebasing stops after 30 days without a merge; separately, GitHub's changelog and community
docs describe pausing after ~90 days of no interaction], which **automatically resumes the moment
a human merges, closes, or comments on any Dependabot PR** — and Phase 36's own actions (closing
#8, merging #15-20) are exactly such interactions.
**How to avoid:** Don't spend phase budget trying to explicitly "unpause" Dependabot before
starting the merge sequence. If a PR fails to rebase automatically after its predecessor merges,
comment `@dependabot rebase` on it directly and poll `mergeStateStatus`; if that produces no
reaction/commit within a few minutes, this is real evidence of an active pause and is exactly the
operator item already tracked for Phase 38 (SCAN-01) — record it, do not block Phase 36 on it
unless a PR in the fixed merge order genuinely cannot land.
**Warning signs:** A Dependabot PR stays `DIRTY`/`BEHIND` for more than ~10 minutes after its
predecessor merges, with no new commit and no emoji reaction on an `@dependabot rebase` comment.

### Pitfall 6: `required_status_checks.strict: true` means "up to date," not just "checks green"
**What goes wrong:** Merging PR #12 (currently `MERGEABLE`/`BEHIND`) or the serialized pip/actions
PRs without first confirming they've absorbed the just-landed predecessor commit — `strict: true`
means GitHub will refuse the merge (or show it as blocked) if the PR's base is stale, even if the
PR's own last check run passed.
**How to avoid:** After each merge in the fixed order, poll `gh pr view <n> --json
mergeStateStatus` for the next PR in sequence and wait for `CLEAN` before merging it — this is
exactly the "waiting for Dependabot to rebase between each" step CONTEXT.md's merge-order
rationale already calls for; the live branch-protection check above is the concrete mechanism
that makes it necessary, not just a courtesy.

## Code Examples

### `requirements.txt` — target union content (derived from live diff + locked union rules)

```
# python_requires >= 3.11
colorama==0.4.6
cryptography==49.0.0
httpx==0.28.1
keyring==25.7.0
nodriver==0.50.3
platformdirs==4.10.0
pydantic==2.13.3
pydantic-settings[yaml]==2.14.2
pygame==2.6.1
pytest==9.0.3
pytest-asyncio==1.3.0
pyyaml==6.0.2
requests==2.33.1
selenium==4.43.0
urllib3==2.7.0
webdriver-manager==4.0.2
```

Verified: this exact content was constructed from `diff <(git show origin/master:requirements.txt)
<(git show HEAD:requirements.txt)`, applying MAIN-02's union rule (`httpx==0.28.1` from master;
`cryptography==49.0.0` and `pydantic-settings[yaml]==2.14.2` from branch; every other line
identical on both sides already). `pip install --dry-run -r <this file>` into a clean venv
resolved with **zero conflicts** — confirmed in this session.

### `.github/dependabot.yml` — target union content (derived from live diff + locked union rules)

```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 10
    labels:
      - "dependencies"
      - "python"
    groups:
      minor-and-patch:
        update-types:
          - "minor"
          - "patch"

  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 5
    labels:
      - "dependencies"
      - "github-actions"
    groups:
      minor-and-patch:
        update-types:
          - "minor"
          - "patch"
```

Verified: constructed from `diff <(git show origin/master:.github/dependabot.yml) <(git show
HEAD:.github/dependabot.yml)`, applying the locked union rule (master's `groups:` blocks for both
ecosystems retained — this is why PR #15 exists; branch's `labels:`, `day: "monday"`, and pip
`open-pull-requests-limit: 10` retained; `github-actions` limit stays at master's `5`, since
neither side's diff touched it).

### Confirming MAIN-01 is real, not just "0 jobs was avoided"

```bash
# After PR #11 merges, get the CI run for master's new HEAD:
NEW_SHA=$(git rev-parse origin/master)
gh run list --branch master --workflow "CI" --commit "$NEW_SHA" --json databaseId,conclusion
RUN_ID=$(gh run list --branch master --workflow "CI" --commit "$NEW_SHA" --json databaseId --jq '.[0].databaseId')
gh run view "$RUN_ID" --json jobs --jq '.jobs[] | {name, conclusion, steps: [.steps[] | select(.conclusion != "success") | .name]}'
# Expect: 2 jobs (test ubuntu-latest, test windows-latest), each conclusion "success",
# each with an empty list of non-success steps.
```

### Local pre-push gate (confirmed working, matches CI's own install order)

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pip install -e ".[web]"
.venv\Scripts\python.exe -m pytest
```

Verified locally: `.venv` already has `httpx==0.28.1`, `cryptography==49.0.0`,
`pydantic-settings==2.14.2`, `pytest==9.0.3`, `pytest-asyncio==1.3.0` installed and importable —
this matches what the union `requirements.txt` will produce, so the existing local `.venv` is
already representative of the merged tree's dependency surface. No separate `pip install httpx`
step is needed once the union `requirements.txt` lands (unlike the pre-Phase-36 state, where
`httpx` had to be installed manually because it was missing from the branch's own
`requirements.txt`).

## State of the Art

| Old approach (branch's current ci.yml) | Current approach (master's ci.yml, inherited by the merge) | Impact |
|---|---|---|
| `SHOPBOT_DATA_DIR: ${{ runner.temp }}/shopbot` in job-level `env:` | Same variable, moved to the `Test` step's own `env:` block | Workflow compiles; jobs schedule |
| `pip install -e .[web]` only | `pip install -r requirements.txt` then `pip install -e ".[web]"` | `pytest` (and every other runtime dep not in `pyproject.toml`) actually gets installed |
| `actions/checkout@v4`, `actions/setup-python@v5` (master) vs. `@v6`/`@v6` (branch) | Merge takes branch's newer pins (non-conflicting hunks) | Consistent with PR #19/#20 bumping toward `@v7` next — the merge doesn't fight that direction |

**Deprecated/outdated:** The already-scouted "81 zero-job runs" narrative for master itself is
outdated as of 2026-08-02T03:49:42Z — see Summary Correction 1. Treat it as historically accurate
context for *why* MAIN-01 exists, not as the current state to re-verify from scratch.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Dependabot auto-rebase / `@dependabot rebase` typically completes within a few minutes when active (no official SLA found; only community-sourced typical timing) | Architecture Patterns / CI Polling, Pitfall 5 | Plan's poll timeout could be set too short, causing a false "Dependabot is stuck" escalation; mitigate with a generous timeout (10-15 min) before treating a stall as evidence of the pause condition |
| A2 | The already-scouted "Dependabot is repo-level PAUSED" fact refers to the 90-day-inactivity auto-pause on version updates, not a manual admin toggle, and will very likely self-resolve the moment this phase closes or merges any Dependabot PR | Pitfall 5 | If actually a manual/permanent pause (e.g., disabled via repo Settings > Code security), PR #15-20 might never auto-rebase regardless of interaction, and would need an explicit re-enable (a Settings change, not a `gh` command) before they can be merged in sequence — this would block MAIN-07 and needs escalating to the operator rather than retried autonomously |
| A3 | GitHub's `skipped` = passing behavior for required status checks (confirmed via official docs for the general case) applies identically to this repo's classic branch-protection configuration, not just the newer rulesets API | Pitfall 4 | If this repo behaves differently, PR #15 (and any other PR where CodeQL skips) might need `--admin` to merge; low-cost fallback already documented |

## Open Questions

1. **Does the true current count of "local commits ahead of PR #11's head" still match the 8
   SHAs CONTEXT.md records by name?**
   - What we know: at CONTEXT.md's scouting time it was 8 (`d485710` through `1463fb6`). During
     this research session, local `HEAD` had already gained a 9th commit (`bb8eace`, "docs(36):
     smart discuss context" — the CONTEXT.md commit itself).
   - What's unclear: whether any further commits land locally between research and execution.
   - Recommendation: the plan should re-run `git log --oneline
     origin/chore/v4.0-milestone-close..HEAD` (after first merging the no-op `e2f2695` commit, per
     Pitfall 3) immediately before acting, and record whatever the actual SHA list is at execution
     time — not hardcode "8." MAIN-03's requirement is that the set be *deliberate*, not that it
     match a specific historical count.

2. **Is PR #16 (cryptography) actually auto-closed by GitHub once PR #11 lands, or does it need an
   explicit close?**
   - What we know: the branch already pins `cryptography==49.0.0`, identical to PR #16's target.
   - What's unclear: GitHub does not always auto-close a PR whose diff becomes empty after a
     merge elsewhere; it may instead show as `mergeStateStatus: CLEAN` with a 0-line diff, still
     open.
   - Recommendation: check `gh pr view 16 --json state,mergeable,additions,deletions` after PR #11
     lands; if still open with 0 net diff, close it explicitly with a superseded rationale exactly
     like PR #8, satisfying MAIN-07's "resolved state" bar either way.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| git | Merge conflict resolution, tagging | Yes | 2.54.0.windows.1 | — |
| gh CLI | PR merge/close, run polling | Yes | 2.89.0 | — |
| gh auth (thezoid account) | All GitHub mutations | Yes, active, `repo`+`workflow` scopes | — | — |
| Python 3.13 | Local pre-push pytest gate | Yes | 3.13.13 | — |
| Local `.venv` with project deps | Fast local verification without reinstalling | Yes, already has httpx/cryptography/pydantic-settings at the target union versions | — | — |
| Network access to github.com API | Every `gh` command in this research and the eventual plan | Yes, verified via multiple live `gh api`/`gh run`/`gh pr` calls this session | — | — |

No missing dependencies. This phase can execute with tools already present on this machine.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3, config in `pyproject.toml` `[tool.pytest.ini_options]` |
| Config file | `pyproject.toml` (testpaths = ["tests"], asyncio_mode = "auto") |
| Quick run command | `.venv\Scripts\python.exe -m pytest --tb=short -x` |
| Full suite command | `.venv\Scripts\python.exe -m pytest` (matches CI's `pytest --tb=short` exactly, modulo the explicit venv path) |

This phase's dominant verification surface is **not** pytest — it is git/GitHub state assertions
(merge status, PR state, CI run conclusions). pytest is the one code-level gate (the full suite
must stay green pre-push and the merged-tree CI run must reproduce that locally-proven result).
The requirement-to-verification map below uses `gh`/`git` commands as the "automated command"
column for that reason, matching how the phase's own success criteria are worded in CONTEXT.md.

### Phase Requirements → Verification Map
| Req ID | Behavior | Verification Type | Automated Command | Evidence Exists? |
|--------|----------|-----------|-------------------|-------------|
| MAIN-01 | Merged `master`'s CI actually schedules and passes both OS jobs | infra assertion | `gh run view <id> --json jobs --jq '.jobs[] | {name,conclusion}'` — expect 2 entries, both `success` | Pattern proven today against master's current (pre-merge) HEAD; re-run against post-merge HEAD |
| MAIN-02 | Merged `requirements.txt` contains exactly the 3 union-critical pins | infra assertion | `grep -E "^(httpx|cryptography|pydantic-settings)" requirements.txt` on `master` post-merge — expect `httpx==0.28.1`, `cryptography==49.0.0`, `pydantic-settings[yaml]==2.14.2`, one line each | Target content pre-computed and dry-run-installed this session; needs re-check against actual merged file |
| MAIN-03 | The full, current local-commit SHA list is recorded and each SHA's inclusion/exclusion is deliberate | infra assertion | `git log --oneline origin/chore/v4.0-milestone-close..HEAD` (after the Pitfall-3 no-op merge) then `git merge-base --is-ancestor <sha> master` per recorded SHA | Command verified working this session against the current (stale) 9-commit list — must be re-run fresh at execution time per Open Question 1 |
| MAIN-04 | `gitleaks.yml`, `release-please.yml` exist on `master` post-merge | infra assertion | `git ls-tree origin/master -- .github/workflows/gitleaks.yml .github/workflows/release-please.yml` — expect two non-empty lines | Confirmed absent pre-merge, confirmed present on branch; command verified this session |
| MAIN-05 | PR #12 merged into `master` | infra assertion | `gh pr view 12 --json state --jq .state` == `"MERGED"`; `git merge-base --is-ancestor 3f27a2d master` | PR #12 checks already all green live (CodeQL, both test jobs) — verified this session |
| MAIN-06 | PR #8 closed unmerged with a recorded superseded reason | infra assertion | `gh pr view 8 --json state --jq .state` == `"CLOSED"`; `gh api repos/thezoid/ShopPyBot/issues/8/comments` contains a comment mentioning `urllib3==2.7.0` and "superseded" | PR #8 state (`CONFLICTING`) confirmed live this session |
| MAIN-07 | #8, #11, #12, #15-20 all reach a resolved (non-open) state, actions PRs serialized | infra assertion | `gh pr list --state open --json number --jq '[.[].number] - [8,11,12,15,16,17,18,19,20] | length == (all open PRs not in this set)'` (practically: `gh pr list --state open --json number` returns none of these 9 numbers) | All 9 numbers confirmed as the current full open-PR set this session — good baseline for a before/after diff |

### Sampling Rate
- **Per merge in the sequence:** the relevant `gh pr view`/`gh run view` assertion above, immediately after that merge lands
- **Full local suite:** run once before the PR #11 push (mandatory per CONTEXT.md), and once again against the final merged `master` tip (checked out fresh) before declaring the phase done
- **Phase gate:** MAIN-07's PR-list diff plus a green `gh run view` for the final `master` HEAD, both required before `/gsd:verify-work`

### Wave 0 Gaps
None — existing test infrastructure (pytest, already-configured `pyproject.toml`) covers
everything this phase needs at the code level. The verification gaps this phase closes are
GitHub-state gaps (open PRs, unmerged conflicts, unproven CI), not test-coverage gaps.

## Security Domain

This phase touches no application code, no auth/session logic, and no new input-handling
surface, so most ASVS categories are not applicable. The two relevant concerns are operational:

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V1 Architecture (change management / least privilege) | Partial | `gh` mutations run under the already-authenticated `thezoid` account with `repo`+`workflow` scopes — no new token or elevated scope is needed; do not create a new PAT for this phase |
| V14 Configuration (dependency/config integrity) | Yes | The two conflict-resolved files (`requirements.txt`, `.github/dependabot.yml`) are exactly the surface SCAN-01 through SCAN-11 depend on later; verify no line was silently dropped (MAIN-02's `httpx` regression is the named example) rather than eyeballing the diff |
| Everything else (V2-V13) | No | No auth, session, access-control, input-validation, cryptography, or business-logic code changes occur in this phase |

### Known Risk Patterns for a Large Merge Operation

| Pattern | Category | Standard Mitigation |
|---------|----------|----------------------|
| Force-push silently discarding remote-only commits | Data/history loss | Verified in this session that the specific stray commit (`e2f2695`) is content-empty, and the recommended sequence avoids force-push entirely (merge it in as a no-op instead) — see Pitfall 3 |
| `--admin` merge bypass masking a real check failure | Process integrity | Reserve `--admin` for the specific, already-anticipated case (a required check stuck in a non-terminal state despite the underlying work being correct), never as a default; the plan should poll and confirm actual check conclusions before reaching for it |
| Conflict resolution silently dropping a security-relevant pin (e.g., `httpx`, which MAIN-02 exists specifically to protect) | Supply chain | The union-resolved file content in Code Examples was derived mechanically from a diff, not by memory, and dry-run-installed to confirm resolvability — repeat this dry-run against the actual resolved file at execution time before pushing |

## Sources

### Primary (HIGH confidence — live-verified against this repo)
- `git merge-tree --write-tree origin/master HEAD` — confirms exactly 2 conflicts (`dependabot.yml`, `requirements.txt`), `ci.yml` auto-merges clean
- `git merge-tree --write-tree HEAD origin/chore/v4.0-milestone-close` — confirms the stray-commit merge is a content-identical no-op
- `gh run view 30731291657 --json jobs` (and related `gh run list`/`gh api` calls) — confirms master's CI is green today, both OS jobs, 755 passed/2 skipped
- `gh api repos/thezoid/ShopPyBot/branches/master/protection` — confirms live required-status-checks config
- `gh pr list --repo thezoid/ShopPyBot --state open --json ...` — confirms all 9 open PRs' states match (or supersede) the already-scouted facts
- Local `pip install --dry-run -r <union requirements.txt>` — confirms the union resolution is installable with no resolver conflicts
- `.venv/Lib/site-packages/starlette/testclient.py` (installed package source) — confirms `httpx` is a hard, top-level import for `TestClient`

### Secondary (CITED — official docs)
- [GitHub Actions: Contexts — availability table](https://docs.github.com/en/actions/learn-github-actions/contexts) — `runner` context not available in job-level `env:`
- [GitHub CLI manual: gh pr merge](https://cli.github.com/manual/gh_pr_merge)
- [GitHub CLI manual: gh run view](https://cli.github.com/manual/gh_run_view)
- [GitHub CLI manual: gh run list](https://cli.github.com/manual/gh_run_list)
- [GitHub Docs: About protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches) — `success`, `skipped`, `neutral` all satisfy required status checks
- [GitHub Docs: Dependabot pull request comment commands](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-pull-request-comment-commands)
- [GitHub Docs: Managing pull requests for dependency updates](https://docs.github.com/en/code-security/dependabot/working-with-dependabot/managing-pull-requests-for-dependency-updates) — automatic rebase default, 30-day rebase cutoff

### Tertiary (LOW confidence — community-sourced, flagged in Assumptions Log)
- Community discussion on Dependabot's 90-day-inactivity auto-pause and what un-pauses it (GitHub community discussion #51668) — no official SLA found for rebase timing or a definitive statement on which specific "paused" flag the already-scouted fact refers to

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new tooling, everything verified present and working live
- Architecture (merge mechanics, CI polling, gh flags): HIGH — verified against this exact repo, not a generic example
- Pitfalls: HIGH for Pitfalls 1-4 and 6 (directly reproduced or confirmed via official docs); MEDIUM for Pitfall 5 (Dependabot pause mechanism genuinely ambiguous from available API surface)

**Research date:** 2026-08-02
**Valid until:** Short — this research contains live, timestamped facts (a specific CI run,
specific PR states, a specific branch-protection config) that can change the moment anyone
interacts with the repo. Re-verify the "live" facts (open PR list, branch protection, latest CI
run conclusion) immediately before planning tasks execute, not just before planning starts. Treat
anything not marked live-verified-this-session as valid for the standard ~30 days.
