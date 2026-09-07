# PHASE 38 OPERATOR RUN-BOOK: "Scanning to Zero"

Generated 2026-08-04. Source of truth is the six PLAN files in this directory; this run-book is a follow-along for the operator.

### READ THIS FIRST

1. Starting position, to VERIFY rather than to assume: you are on the planning branch (`chore/v4.0-milestone-close` when this run-book was written), some commits ahead of `origin/master`, with a clean tree across the four carry-over paths. None of that is a standing fact about your box. The branch head moves with every remediation pass, so do not compare it against a written-down SHA; Block 1 step 2 derives it. The clean tree is a PRECONDITION that Block 1 step 2's gate establishes each time, and it was measurably false the last time this run-book was revised.
2. The ONE gate: the six Phase 38 plans are UNVERIFIED. Nothing below Block 0 runs until the plan checker returns a written PASS verdict.
3. Irreversible in this phase: 26 code scanning alert dismissals; 1 Dependabot dismissal; enabling `secret_scanning_validity_checks`, which sends candidate secrets to their issuing providers and cannot be un-sent (threat T-38-29); deletion of `.github/workflows/codeql-analysis.yml`; creation of remote tag `archive/dev-final`; deletion of remote branch `origin/dev`; up to 2 branch-protection PATCHes; 2 PR merges to master. Locally reversible but disruptive: Block 2 step 28 upgrades your `.venv` to cryptography 50.
4. A "NOT MET" outcome is allowed and is better than a zero reached by dismissal. SCAN-08 closes as a recorded DEFERRAL, on purpose.
5. `gitleaks` is NOT installed locally. Never run it on this box. Its evidence comes only from GitHub Actions check runs.

### TODAY'S PATH

Tag legend: `[WALK AWAY]` start it and leave. `[WATCH]` stay and re-run or observe; it does not block. `[DECIDE]` a judgement you must write down. `[BROWSER]` a click in the GitHub web UI. `[SAY TO CLAUDE]` a prompt to paste into this session verbatim; the text after the `>` is the prompt.

1. Block 0: plan-checker gate and blocking-constraint acknowledgement. 20 min. `[DECIDE]`
2. Block 1: the wave-0 hard gate (code scanning must answer HTTP 200 or the phase does not start), then 38-01, branch cut, three-scanner baseline, SCAN-06 verdict, cryptography verdict. 45 min. `[DECIDE]`
3. Block 2: 38-02, url host-match fix, cryptography pin, secret-name invariant test. 95 min. Six `[DECIDE]` points (steps 6, 21, 34, 35, 48, 49) plus two negative-control judgements (13/14, 40/41). The only genuine `[WALK AWAY]` stretches are the full pytest runs.
4. Block 3: 38-03, ci.yml permissions, CodeQL workflow removal, SHA pins, SCAN-08 deferral record. 55 min. `[DECIDE]`
5. Block 4: 38-04, open PR, green checks, merge to master, post-merge alert re-query. 70 min plus up to 35 min of waiting. Eleven `[DECIDE]` points (steps 3, 5, 8, 9, 10, 24, 25, 26, 33, 34, 35), including the step 9 HARD STOP and the step 10 merge to master. Only step 6's `--watch` is a genuine `[WALK AWAY]`; steps 7, 20, 21 and 31 are `[WATCH]`.
6. Block 5: 38-05, 26 dismissals written as seven distinct reason strings (four test-fixture shapes, three clear-text sub-cases), then two ORDERED secret-scanning PATCHes with an alert enumeration and a poll between them. 50 min hands-on plus up to 15 min of polling. Eleven `[DECIDE]` points (steps 0, 3, 4, 13, 14, 15, 18, 25, 27, 27.5, 32), which includes the two PATCH decisions at 25 and 27.5 and the commit at 32. Step 27 is the block's only `[WATCH]` and it is `[DECIDE]` as well: its poll is what gates the irreversible half. No `[WALK AWAY]` anywhere in the block.
7. Block 6: 38-06, gitleaks required check, archive-then-delete `origin/dev` as one guarded invocation, the seven-group dismissal-reason audit, FINAL GATE table, docs PR. 70 min. Thirteen `[DECIDE]` points (steps 2, 5, 11, 14, 15, 22, 23, 25.5, 26, 31, 32, 33, 37). No `[WATCH]` and no `[WALK AWAY]` anywhere in the block: step 31 is `[DECIDE]` and explicitly says STAY AT THE KEYBOARD. Master's merge path is locked from step 5 until step 33, and step 15 is the phase's only ref deletion.
8. Background: Actions "create and approve pull requests" setting. 2 min. `[BROWSER]`
9. Background: PR #23 GitHub App decision (not a PAT, ever). `[DECIDE]`
10. Background: PR #25 split, requirements.txt half only. `[DECIDE]`

Total hands-on is 6 hours 45 minutes by the block estimates above, plus up to 35 minutes of waiting in Block 4, up to 15 minutes of polling in Block 5, and an unbounded CI wait in Block 6. Do not start this after 6pm. Blocks 4 through 6 contain every irreversible action in the phase; do not begin Block 4 without 3 clear hours.

### Conventions used below

- Native binaries (`git`, `gh`) go through `rtk`. PowerShell cmdlets (`Select-String`, `Get-ChildItem`, `Test-Path`, `Out-File`, `Tee-Object`, `foreach`) do not and must not. The venv Python is invoked directly: `.venv\Scripts\python.exe`, never `rtk pytest`.
- Run everything in pwsh 7 (black icon, `pwsh`), not Windows PowerShell 5.1. Confirm with `$PSVersionTable.PSVersion` before Block 0. The `??` operator, BOM-free `-Encoding utf8`, and multi-line `ConvertFrom-Json` pipelines all depend on it. This box reports 7.6.3.
- `rtk proxy git log ...` is used for every range or audit query. Plain `rtk git log` drops merge commits and caps at 50 and will return EMPTY for an all-merge range, which reads as "in sync" and is wrong.
- `rtk git diff` reformats output (stat header, a literal `--- Changes ---` separator, and two-space-indented hunk lines). Never pattern-match or line-count its output. Use `rtk proxy git diff` whenever the output feeds an acceptance criterion. `rtk git status --porcelain` is verified byte-identical to raw and is safe.
- Tests are always `.venv\Scripts\python.exe -m pytest`, never `rtk pytest`.
- Where the source plan carried a POSIX-only command, the PowerShell equivalent is the primary and the original lives in the appendix at the end of this document, marked in line as `(POSIX original in appendix)`. Those appendix commands are provenance notes. DO NOT RUN THEM; `grep` does not exist in this environment.
- Shell variables such as `$PLANSHA`, `$MSHA`, `$DEVSHA`, `$targets`, `$g1` through `$g4`, `$clearText` persist only inside one terminal window. Do not close the window mid-block. Block 6 step 15 is written as one pasted block for exactly this reason: its guards and its delete must share a shell with the `$DEVSHA` that authorises them.

### BLOCK 0: STOP HERE. The plan-checker gate. `[DECIDE]` 20 min

Nothing below this block may run until this block completes with a written PASS.

- [ ] Acknowledge the three blocking constraints out loud, in writing, before anything else. Do not proceed until all three boxes are checked.
  - [ ] `rtk git log` is lossy. For every range, audit, or completeness query in this phase I will use `rtk proxy git log ...`.
  - [ ] Single-platform probing produces confidently wrong results. Where a check-run producer or an alert state matters, I probe it against a real run, not against my expectation.
  - [ ] The six Phase 38 plans are UNVERIFIED. This block is the reason.

- [ ] Confirm the shell. Everything below assumes pwsh 7.

```powershell
$PSVersionTable.PSVersion
```

  you should see: major version `7`. On `5` you are in Windows PowerShell; close it and open `pwsh`.

- [ ] `[SAY TO CLAUDE]` Type exactly:

  > Re-run the Phase 38 plan checker against all six plans in `.planning/phases/38-scanning-to-zero/`. Your job is to FALSIFY, not to confirm. Primary claim to falsify: that all 7 clear-text CodeQL alerts genuinely trace to `SECRET_KEYS` at `core/credentials.py:47`, and that `SECRET_KEYS` really is a list of credential key NAMES rather than values. Dismissing a real credential leak as noise is the worst outcome available here. Also falsify: (2) does the `origin/dev` deletion tag and verify before deleting, with every failure path leaving the branch intact; (3) can SCAN-06's workflow removal or SCAN-07's added required check strand an unreportable required check and lock the repo out of merging. Apply the anti-pattern check "plan names one call site when several exist": grep the whole package for the pattern, not just the line the plan names. Also check the measured-state corrections: SCAN-01 is 1 open Dependabot alert not 7; SCAN-02 is 7 clear-text alerts (5 `py/clear-text-logging-sensitive-data` plus 2 `py/clear-text-storage-sensitive-data`) not "the two"; SCAN-03 is exactly 3; SCAN-04 is exactly 19; SCAN-05 is 2 `actions/missing-workflow-permissions`; totals 31 code scanning, 0 secret scanning. And check whether the cryptography disposition is genuinely open: alert #13, high, PKCS#7 EnvelopedData Bleichenbacher oracle, current pin `cryptography==49.0.0`. Return a single-word verdict line: PASS or FAIL, plus the evidence for each falsification attempt.

- [ ] Read the verdict. Write it down here: `PLAN CHECKER VERDICT: ____________  (date/time: __________)`

- [ ] **HARD GATE.** Only a written PASS unlocks Block 1. On FAIL, stop the phase, fix the named plan, and re-run this block. Do not "proceed carefully". Phase 38 dismisses 26 alerts and deletes a remote branch; both are hard to undo.

- [ ] If the checker overturns the SCAN-06 expectation (that `CodeQL` comes from default setup and `Analyze (python)` / `Analyze (actions)` come from the workflow file), note it now. Block 1 still re-measures it live, and the measurement wins over both the plan and the checker.

### BLOCK 1: Plan 38-01. Baseline plus the two blocking verdicts. 45 min

Zero GitHub state is mutated in this entire block. Every API call is a read. Step 33 exists to prove that.

- [ ] WAVE 0 HARD GATE. `[DECIDE]` Nothing in this phase runs, including Block 1 step 1, until the code scanning alert list answers HTTP 200. Paste the WHOLE fenced block as ONE invocation. The `& { ... }` wrapper is load-bearing: a bare top-level `throw` does not stop a command submitted after it across a call boundary, so the guard has to share a parsed unit with what it guards.

```powershell
& {
  $resp   = (rtk proxy gh api -i "repos/thezoid/ShopPyBot/code-scanning/alerts?state=open&per_page=100" | Out-String)
  $status = ($resp -split '\r?\n')[0]
  "PRECONDITION status line: [$status]"
  if ($status -notmatch '^HTTP/\S+\s+200\b') { throw "HALT (wave-0 gate): the code scanning alert list returned '$status'. Record that line verbatim and STOP the phase. A non-200 is UNKNOWN, never zero." }
  "PRECONDITION ok"
}
```

  you should see: a `PRECONDITION status line:` whose bracketed value contains ` 200`, then `PRECONDITION ok`. Write the status line down; Block 5 and Block 6 both require it on record.
  if it fails: HALT the phase and record the status line verbatim. Diagnose it as an ENABLEMENT problem, not an auth problem: a 403 from `code-scanning/alerts` on this repository means code scanning is not available for the repository's current plan and visibility, and a 404 from `secret-scanning/alerts` means the feature is switched off. Re-authenticating, re-scoping a token, or retrying does not change either answer. The next step is an operator decision about repository posture, and CLAUDE.md forbids changing visibility without an explicit instruction. Do NOT proceed to Block 1 "carefully": every alert number, every dismissal and the whole baseline downstream of here would be derived from an unreadable endpoint.
  This gate asserts on the status VALUE, in the same invocation as what it gates. Do not replace it with an exit-code test and do not split it across two pastes.

<!-- POSTURE-PENDING: the branch-protection half of this gate (whether `branches/master` must read `protected: true` and what the required-contexts list must contain before the phase may start) cannot be written while the repository posture is undecided; re-derive that half, and whether it is a hard gate or a recorded non-requirement, once the operator settles the posture. The code-scanning 200 requirement above is unconditional and stands either way. -->

- [ ] Precheck: confirm `gh` is authenticated and can read all three scanners.

```powershell
rtk gh auth status
```

  you should see: account `thezoid` active, scopes including `repo` and `workflow`.
  if it fails: no active account, or a missing `repo` / `workflow` scope, is the AUTH case; fix it with `rtk proxy gh auth login`.
  A 403 from a code-scanning or secret-scanning endpoint is NOT the auth case and re-authenticating will not clear it. On this repository it means the feature is not enabled for the current plan and visibility; a 404 from secret scanning means it is switched off. Both are repository-posture decisions for the operator, not credential problems. In either case HALT, record the verbatim status line, and do not re-run the probe under different credentials hoping for a different answer. The wave-0 gate above is the check that decides this.

- [ ] Step 1. `[SAY TO CLAUDE]`

  > Read `.planning/phases/38-scanning-to-zero/38-CONTEXT.md` (the measured-state table in the decisions block) and `.planning/REQUIREMENTS.md` lines 60 through 74. Then state back to me the measured counts.

  you should see: Claude states 31 open code scanning alerts, 1 Dependabot alert (#13 cryptography), 0 secret scanning alerts.

- [ ] Step 2. Cut the working branch off `origin/master` and carry the planning-branch-only files onto it. FIRST, from the planning branch, confirm exactly what only exists here. `checkout -B` silently loses every planning-branch-only path that is not named explicitly, and the carry-over is more than the phase directory.

  GATE, before anything else in this step. `$PLANSHA` is the CURRENT COMMIT. Any Phase 38 edit that is not yet committed is not in `$PLANSHA`, so the `rtk git checkout $PLANSHA -- <path>` below would overwrite the working-tree files with the older committed content and silently discard the revisions. There is no error and no diff to notice. The gate covers ALL FOUR carry-over paths, not the phase directory alone: the restore overwrites every one of them, and uncommitted work in `.planning/ROADMAP.md`, `.planning/HANDOFF.json` or `37-VERIFICATION.md` is destroyed the same way and is NOT recoverable, because that content was never staged, so there is no stash entry and no dangling blob. `38-01-PLAN.md` Task 1 gates on the same four paths from one `set --` list; this is its pwsh equivalent and the two must cover the same set.

```powershell
rtk git status --porcelain -- .planning/phases/38-scanning-to-zero/ .planning/ROADMAP.md .planning/HANDOFF.json .planning/phases/37-distributable-artifact/37-VERIFICATION.md
```

  you should see: empty output.
  if it fails: HARD STOP. Any ` M` or `??` line here means the carry-over checkout would restore stale pre-remediation content over the revised content, in whichever of the four paths it names. Commit every Phase 38 plan revision, `38-RUNBOOK.md` itself, and any edit to `ROADMAP.md`, `HANDOFF.json` or `37-VERIFICATION.md` on the planning branch FIRST, then re-run this gate. Do not proceed "carefully"; the loss is silent. At the time this run-book was written the phase directory held five modified plan files and an untracked `38-RUNBOOK.md`, so expect this gate to fire on a first pass.

  Only once the gate is clean:

```powershell
$PLANSHA = (rtk proxy git rev-parse HEAD).Trim()
$PLANSHA
rtk proxy git ls-tree --name-only $PLANSHA -- .planning/phases/38-scanning-to-zero/38-RUNBOOK.md
rtk git fetch origin --prune --tags
rtk proxy git diff --name-status origin/master..HEAD
```

  you should see: `$PLANSHA` prints a 40-character hex SHA, which is the CURRENT commit on the planning branch and is derived here rather than expected: do not compare it against a written-down value. An earlier draft of this run-book hardcoded `910e31d`, which names a tree that predates this file's own remediation and does not contain `38-RUNBOOK.md` at all.
  you should see, from the `ls-tree`: exactly the line `.planning/phases/38-scanning-to-zero/38-RUNBOOK.md`. That is the check that the resolved tree actually contains this run-book. Empty output means it does not.
  you should see, from the name-status listing: exactly four things, the `.planning/phases/38-scanning-to-zero/` directory, `.planning/ROADMAP.md` (which carries Phase 38's plan list and all eight planning corrections), `.planning/HANDOFF.json`, and `.planning/phases/37-distributable-artifact/37-VERIFICATION.md`.
  if the `ls-tree` prints nothing: HARD STOP. `$PLANSHA` resolves to a tree without this run-book in it, so the carry-over would land plans without the document that narrates them. Commit `38-RUNBOOK.md` on the planning branch and re-run from the gate.
  if it lists anything more: name that path in the gate above AND in the next block rather than dropping it silently. The gate and the restore read the same list; a path restored outside that list is un-gated. Do not assume the four are the whole set; the listing wins.

  Then carry them over. Paste the WHOLE fenced block as ONE invocation: the wrapper is what makes the dirty-tree re-check, the branch cut and the restore a single parsed unit, so a failure aborts before anything is overwritten. A bare top-level `throw` cannot stop a command submitted after it across a call boundary.

```powershell
& {
  $ErrorActionPreference = 'Stop'
  $dirty = rtk git status --porcelain -- .planning/phases/38-scanning-to-zero/ .planning/ROADMAP.md .planning/HANDOFF.json .planning/phases/37-distributable-artifact/37-VERIFICATION.md
  if ($dirty) { throw "ABORT: uncommitted changes in a carry-over path:`n$($dirty -join "`n")`nCommit every phase 38 revision on the planning branch FIRST. Nothing was restored." }
  if ($PLANSHA -notmatch '^[0-9a-f]{40}$') { throw "ABORT: PLANSHA is not a 40-char sha ('$PLANSHA'). Re-run this step from the top; you closed the terminal between commands." }
  rtk git checkout -B phase-38-scanning-to-zero origin/master
  if ($LASTEXITCODE -ne 0) { throw "ABORT: git checkout -B exited $LASTEXITCODE. Still on the source branch; nothing was restored." }
  $branch = (rtk proxy git rev-parse --abbrev-ref HEAD).Trim()
  if ($branch -ne "phase-38-scanning-to-zero") { throw "ABORT: expected branch phase-38-scanning-to-zero, on '$branch'. Nothing was restored." }
  rtk git checkout $PLANSHA -- .planning/phases/38-scanning-to-zero/ .planning/ROADMAP.md .planning/HANDOFF.json .planning/phases/37-distributable-artifact/37-VERIFICATION.md
  rtk git add .planning/phases/38-scanning-to-zero/ .planning/ROADMAP.md .planning/HANDOFF.json .planning/phases/37-distributable-artifact/37-VERIFICATION.md
  rtk git add .planning/phases/38-scanning-to-zero/38-RUNBOOK.md
  rtk git reset .planning/phases/38-scanning-to-zero/.continue-here.md
  rtk git commit -m "docs(38-01): carry phase 38 plans and planning state onto the working branch"
}
```

  you should see: the checkout reports the new branch, the reset unstages `.continue-here.md` and nothing else, and the commit succeeds.
  The `$LASTEXITCODE` throw after `checkout -B` is not decoration. Without it a failed branch cut leaves you on the SOURCE branch and the very next line restores `$PLANSHA` over the source branch's own working tree. The branch-value assertion after it covers the second variant: `checkout -B` can report success and still leave HEAD somewhere unexpected, and the restore is only safe on the new branch. Both assert on VALUES read back in this same invocation.
  if pwsh shows a `>>` continuation prompt after the first line: that is correct behaviour, not a hang. Keep pasting until the closing brace.
  The second `rtk git add` names `38-RUNBOOK.md` explicitly rather than relying on the directory add to sweep it in. This file is this phase's operator run-book and belongs on master alongside the plans it narrates; naming it makes that intent legible and survives the case where it is still untracked in the phase directory. `38-01-PLAN.md` Task 1 carries the same explicit line.
  The `rtk git reset` line is required, not tidying. `.continue-here.md` is git-tracked inside the phase directory and carries `status: paused` / `task: 0` from the interrupted run that created these plans. Staging the directory wholesale would commit that stale handoff, and Block 4's merge would carry it onto master. Unstaging leaves the file in the working tree for local use while keeping it out of every commit on this branch; Block 6 step 27 then removes it from the tree before the docs PR.
  IRREVERSIBLE (local only): `git checkout -B` force-resets any existing local branch named `phase-38-scanning-to-zero` to `origin/master` and moves HEAD off `chore/v4.0-milestone-close`. It destroys that local branch pointer only, not any commit. Recover with `rtk proxy git reflog`. A clean tree across the four carry-over paths is a PRECONDITION of this step, not a standing fact about your box: it is what the gate above and the re-check inside the block establish, each time, before anything is overwritten. Do not run this with uncommitted work in any of those paths. The tree was measurably dirty at the time this run-book was last revised.
  if it fails: any `ABORT:` line leaves the tree untouched, which is the designed outcome. Fix what it names and re-run the whole block from the gate. Do not unwrap the block and do not run its lines individually.

- [ ] Step 3. Prove nothing on master is missing from the working branch.

```powershell
rtk git rev-list --count HEAD..origin/master
```

  you should see: exactly `0`.
  if it fails: master moved. Re-run step 2's fetch and checkout.

- [ ] Step 4. Prove the branch is master plus exactly one commit.

```powershell
rtk proxy git log --oneline origin/master..HEAD
```

  you should see: exactly one line, subject `docs(38-01): carry phase 38 plans and planning state onto the working branch`.
  Note: `rtk proxy` is required here. Plain `rtk git log` on a range can return empty and read as "in sync".

- [ ] Step 5. `[DECIDE]` Confirm every carried path survived, not just the plan files.

```powershell
rtk ls .planning/phases/38-scanning-to-zero/
rtk proxy git diff --name-status origin/master..HEAD
```

  you should see, from the `rtk ls`: `38-01-PLAN.md` through `38-06-PLAN.md`, plus `38-CONTEXT.md`, plus `38-RUNBOOK.md`, which step 2 carried over and staged by name. `rtk ls` also lists `.continue-here.md`, measured on this box; that is CORRECT and expected here. The file is still in the working tree by design, and the directory listing is not what the step 2 reset controls.
  you should see, from the `rtk proxy git diff --name-status`: `.planning/ROADMAP.md`, `.planning/HANDOFF.json` and `.planning/phases/37-distributable-artifact/37-VERIFICATION.md` alongside the phase directory, matching what step 2's pre-checkout listing showed, and `38-RUNBOOK.md` among the phase directory's entries. No `.continue-here.md` line appears in THIS output. That is the statement that matters: the step 2 reset kept the file out of the COMMIT, not out of the working tree, so the committed set is the only place its absence is evidence of anything.
  if it fails: any missing plan file, or any path from step 2's listing absent here, is a HARD STOP. Do not continue on a tree that cannot execute the rest of the phase. Report and go back to `$PLANSHA`.

- [ ] Step 6. Inventory every open code scanning alert. Sort on the JSON fields, not on the formatted string; sorting formatted strings orders alerts 10, 11, ..., 19, 3, 33, 34, 4, 5, 6, which is the one ordering that makes step 11's grouping harder.

```powershell
rtk proxy gh api "repos/thezoid/ShopPyBot/code-scanning/alerts?state=open&per_page=100" |
  ConvertFrom-Json |
  Sort-Object { $_.rule.id }, { $_.most_recent_instance.location.path }, { $_.most_recent_instance.location.start_line } |
  ForEach-Object { "{0} {1} {2} {3}:{4}" -f $_.number, $_.rule.id, $_.rule.security_severity_level, $_.most_recent_instance.location.path, $_.most_recent_instance.location.start_line }
```

  you should see: one line per open alert, roughly 31 lines, grouped by rule id. The LIVE count is what gets recorded, not the expectation.
  (POSIX original in appendix)
  if it fails: HALT. Do not proceed on a partial inventory and do not diagnose the failure before reading the status line. A 401, or a 403 whose body names a missing scope, is the AUTH case. A bare 403 from this endpoint on this repository is the ENABLEMENT case: code scanning is not available for the repository's current plan and visibility, and no credential change clears it. Re-run the read as `rtk proxy gh api -i "repos/thezoid/ShopPyBot/code-scanning/alerts?state=open&per_page=100" | Select-Object -First 1` to capture the status line verbatim, record it, and stop the phase; this is the wave-0 gate failing a second time, and the next move is the operator's posture decision, not another `gh auth login`. An empty or partial list under a non-200 is UNKNOWN, never a zero.

- [ ] Step 7. Inventory every open Dependabot alert.

```powershell
rtk proxy gh api "repos/thezoid/ShopPyBot/dependabot/alerts?state=open&per_page=100" |
  ConvertFrom-Json |
  ForEach-Object { "#{0} {1} {2} {3} range={4} patched={5} {6}" -f $_.number, $_.security_advisory.severity, $_.dependency.package.name, $_.dependency.manifest_path, $_.security_vulnerability.vulnerable_version_range, ($_.security_vulnerability.first_patched_version.identifier ?? "NONE"), $_.security_advisory.ghsa_id }
```

  you should see: one line, alert #13, `high`, `cryptography`, `requirements.txt`. The requirement text claims 7; measured is 1.

- [ ] Step 8. Count open secret scanning alerts.

```powershell
@(rtk proxy gh api "repos/thezoid/ShopPyBot/secret-scanning/alerts?state=open&per_page=100" | ConvertFrom-Json).Count
```

  you should see: `0`.

- [ ] Step 9. Capture the repository security and analysis block.

```powershell
rtk proxy gh api "repos/thezoid/ShopPyBot" | ConvertFrom-Json | Select-Object -ExpandProperty security_and_analysis | ConvertTo-Json -Depth 5
```

  you should see: a JSON object showing each scanner's enablement state. Expect `secret_scanning_non_provider_patterns` and `secret_scanning_validity_checks` disabled. Keep this output, Block 5 needs it as the "before".

- [ ] Step 10. Capture the current required status checks on master.

```powershell
rtk proxy gh api "repos/thezoid/ShopPyBot/branches/master/protection/required_status_checks"
```

  you should see: `strict: true`, contexts including `CodeQL`, `test (windows-latest)`, `test (ubuntu-latest)`. This is the list SCAN-06 could break and SCAN-07 will extend.

- [ ] Step 11. `[SAY TO CLAUDE]`

  > Create `.planning/phases/38-scanning-to-zero/38-SCAN-BASELINE.md` with a `## Alert Inventory` section (code scanning alerts grouped by rule id, from the step 6 output) and a `## Requirement Text Corrections` table with one row per SCAN-01 through SCAN-05 naming the measured value against the requirement text. Do NOT edit `.planning/REQUIREMENTS.md`; the drift stays visible there on purpose. Do not commit yet.

- [ ] Step 11 verify: the inventory total must equal the live count.

```powershell
@(rtk proxy gh api "repos/thezoid/ShopPyBot/code-scanning/alerts?state=open&per_page=100" | ConvertFrom-Json).Count
```

  you should see: the same number as the Alert Inventory total in the file.

- [ ] Step 12. Confirm the branch name.

```powershell
rtk proxy git rev-parse --abbrev-ref HEAD
```

  you should see: `phase-38-scanning-to-zero`.

- [ ] Step 13. `[SAY TO CLAUDE]`

  > Read the `### TRAP the plan must verify before acting` section of `38-CONTEXT.md`, and all 40 lines of `.github/workflows/codeql-analysis.yml`. Then name both candidate producers of the `CodeQL` context.

  you should see: Claude names default setup at `dynamic/github-code-scanning/codeql` and the file-based workflow at `.github/workflows/codeql-analysis.yml`. Both are named "CodeQL". That collision is the entire reason this task exists.

- [ ] Step 14. Probe 1 of 4: workflow inventory.

```powershell
rtk proxy gh api "repos/thezoid/ShopPyBot/actions/workflows?per_page=50" |
  ConvertFrom-Json |
  Select-Object -ExpandProperty workflows |
  ForEach-Object { "{0} | {1} | {2} | {3}" -f $_.id, $_.name, $_.path, $_.state }
```

  you should see: id `8840986` at `.github/workflows/codeql-analysis.yml` in state `disabled_manually`, and id `325304050` at `dynamic/github-code-scanning/codeql`.

- [ ] Step 15. Probe 2a: resolve master HEAD.

```powershell
$MSHA = (rtk proxy gh api "repos/thezoid/ShopPyBot/branches/master" | ConvertFrom-Json).commit.sha
$MSHA
```

  you should see: a 40-character SHA.

- [ ] Step 16. Probe 2b: check runs on master HEAD with the producing app slug.

```powershell
rtk proxy gh api "repos/thezoid/ShopPyBot/commits/$MSHA/check-runs?per_page=100" |
  ConvertFrom-Json |
  Select-Object -ExpandProperty check_runs |
  ForEach-Object { "{0} | app={1} | {2}" -f $_.name, $_.app.slug, $_.html_url }
```

  you should see: check name, app slug, and html_url per line. Keep the raw output; it goes into the verdict section verbatim.

- [ ] Step 17. Probe 3a: resolve merged PR 24's head SHA. This is where the `CodeQL` context actually reports.

```powershell
$PSHA = (rtk proxy gh api "repos/thezoid/ShopPyBot/pulls/24" | ConvertFrom-Json).head.sha
$PSHA
```

  you should see: a 40-character SHA.

- [ ] Step 18. Probe 3b, the decisive probe: check runs on PR 24's head.

```powershell
rtk proxy gh api "repos/thezoid/ShopPyBot/commits/$PSHA/check-runs?per_page=100" |
  ConvertFrom-Json |
  Select-Object -ExpandProperty check_runs |
  ForEach-Object { "{0} | app={1} | {2}" -f $_.name, $_.app.slug, $_.html_url }
```

  you should see: a line whose check name is exactly `CodeQL` with its `app=` value, plus lines for `Analyze (python)` and `Analyze (actions)`.
  if it fails: if no line is named exactly `CodeQL`, you cannot establish condition (a). Record DEFER in step 20.

- [ ] Step 19. Probe 4: for EACH `Analyze (python)` and `Analyze (actions)` from step 18, take the numeric run id out of its `html_url` (the value after `/actions/runs/`) and resolve which workflow produced it. Paste both ids into the list below and run the block once.

```powershell
foreach ($runId in @("<RUN_ID_A>","<RUN_ID_B>")) {
  rtk proxy gh api "repos/thezoid/ShopPyBot/actions/runs/$runId" |
    ConvertFrom-Json |
    ForEach-Object { "runid=$runId name={0} path={1} workflow_id={2}" -f $_.name, $_.path, $_.workflow_id }
}
```

  you should see: `path=dynamic/github-code-scanning/codeql` (default setup; run `30860216102` at planning time).
  if it fails: if ANY `Analyze (*)` resolves to `.github/workflows/codeql-analysis.yml`, condition (b) FAILS and the verdict is DEFER.

- [ ] Step 20. `[DECIDE]` `[SAY TO CLAUDE]`

  > Apply the three-condition decision rule and write a heading spelled literally `## VERDICT-SCAN-06` into `38-SCAN-BASELINE.md`. The line immediately after the heading must read literally `VERDICT-SCAN-06: SAFE-TO-DELETE` or `VERDICT-SCAN-06: DEFER`, with nothing else on that line, because Block 3 step 11 parses it with a regex. Record `VERDICT-SCAN-06: SAFE-TO-DELETE` only if ALL THREE hold: (a) the check named exactly `CodeQL` in probe 3 has `app.slug == github-advanced-security`; (b) every `Analyze (*)` resolves in probe 4 to a run whose `.path` is `dynamic/github-code-scanning/codeql`; (c) the workflow at `.github/workflows/codeql-analysis.yml` reports state `disabled_manually` in probe 1. Otherwise record `VERDICT-SCAN-06: DEFER` plus which of a/b/c failed and the raw evidence line that failed it. Under either verdict, paste probes 1 through 4 output verbatim in a fenced block. Delete nothing; the deletion is 38-03 Task 1 and it reads this verdict.

  you should see: the line immediately after the heading reads either `VERDICT-SCAN-06: SAFE-TO-DELETE` or `VERDICT-SCAN-06: DEFER`. There is no third option.
  YOUR CALL: if the live probes contradict the planning-time expectation, record DEFER. The measurement wins over the plan. 38-03's deletion then does not run, and SCAN-06 closes as deferred, which is a permitted outcome.

- [ ] Step 21. Verify exactly one verdict heading exists, and that the machine-readable verdict line parses.

```powershell
(Select-String -Path .planning\phases\38-scanning-to-zero\38-SCAN-BASELINE.md -Pattern "^## VERDICT-SCAN-06$").Count
Select-String -Path .planning\phases\38-scanning-to-zero\38-SCAN-BASELINE.md -Pattern "^VERDICT-SCAN-06: (SAFE-TO-DELETE|DEFER)$" |
  ForEach-Object { $_.Matches[0].Groups[1].Value }
```

  you should see: `1`, then exactly one word, `SAFE-TO-DELETE` or `DEFER`.
  if it fails: if the second command prints nothing, the verdict line is malformed and Block 3 step 11's guard will refuse to run. Fix the line now.

- [ ] Step 22. `[SAY TO CLAUDE]`

  > Read `requirements.txt` (15 lines), `pyproject.toml` lines 1 through 50 (dependencies and optional-dependencies), and `core/credentials.py` lines 25-35 and 215-270 (the only cryptography call sites). State the current pin and the requires-python floor.

  you should see: `cryptography==49.0.0` and `requires-python >=3.11`.

- [ ] Step 23. Read the advisory off alert #13 itself. Do not assume an upgrade exists.

```powershell
$a13 = rtk proxy gh api "repos/thezoid/ShopPyBot/dependabot/alerts/13" | ConvertFrom-Json
"pkg={0} manifest={1} range={2} patched={3} ghsa={4} cve={5}" -f $a13.dependency.package.name, $a13.dependency.manifest_path, $a13.security_vulnerability.vulnerable_version_range, ($a13.security_vulnerability.first_patched_version.identifier ?? "NONE"), $a13.security_advisory.ghsa_id, $a13.security_advisory.cve_id
```

  you should see: `pkg=cryptography manifest=requirements.txt ... ghsa=GHSA-g6cj-pr64-35w5 cve=CVE-2026-69247 patched=50.0.0`.
  if it fails: `patched=NONE` means no fixed release exists. That forbids UPGRADE and forces the DISMISS or ACCEPT branch in step 27.

- [ ] Step 24. Confirm the patched version is a real installable release, not an advisory-only claim.

```powershell
.venv\Scripts\python.exe -c "import json,urllib.request; d=json.load(urllib.request.urlopen('https://pypi.org/pypi/cryptography/json')); print('latest', d['info']['version'], 'requires_python', d['info']['requires_python']); [print(v, len(d['releases'].get(v,[])), 'files') for v in ['49.0.0','50.0.0']]"
```

  you should see: `50.0.0` with 46 distribution files and `requires_python !=3.9.0,!=3.9.1,>=3.9`.
  if it fails: a zero file count means the release is not real. Treat as no patched release.

- [ ] Step 25. Establish reachability. The advisory is specific to PKCS#7 EnvelopedData decryption.

```powershell
Get-ChildItem -Path core,plugins,notifications,web -Recurse -Filter *.py |
  Select-String -Pattern "pkcs7|PKCS7|EnvelopedData|smime|SMIME|load_pem_pkcs7|load_der_pkcs7"
Select-String -Path main.py,logger.py,models.py,utils.py,config.py -Pattern "pkcs7|PKCS7|EnvelopedData|smime|SMIME|load_pem_pkcs7|load_der_pkcs7"
```

  you should see: no matches from either command.
  (POSIX original in appendix)
  if it fails: ANY match means the vulnerable API is reachable and DISMISS is forbidden.

- [ ] Step 26. Enumerate every cryptography import that does exist. Scope the enumeration to the source directories; an unscoped `Get-ChildItem -Recurse` from the repo root walks every `.py` under `.venv\Lib\site-packages`, `_deprecated`, and `.claude\worktrees\` before the filter runs, which reads as a hang and produces phantom matches from the second `.planning/` tree that lives under `.claude\worktrees\gallant-ritchie-fa629c\`.

```powershell
Get-ChildItem -Path core,plugins,notifications,web,tests,scripts -Recurse -Filter *.py |
  Select-String -Pattern "from cryptography|import cryptography"
Select-String -Path main.py,logger.py,models.py,utils.py,config.py -Pattern "from cryptography|import cryptography"
```

  you should see: only `cryptography.fernet.Fernet`, `cryptography.fernet.InvalidToken`, and `cryptography.hazmat.primitives.kdf.scrypt.Scrypt`, at `core/credentials.py:29-30` and `core/session_store.py:24`.

- [ ] Step 27. `[DECIDE]` `[SAY TO CLAUDE]`

  > Write a `## VERDICT-SCAN-01` heading into `38-SCAN-BASELINE.md`. The line IMMEDIATELY following that heading is the machine-readable verdict and nothing else: one line, no leading whitespace, no trailing prose, matching `^VERDICT-SCAN-01: (UPGRADE to [0-9][0-9.]*|DISMISS|ACCEPT)$`, and the only line in the file that matches it. Write it exactly the way `VERDICT-SCAN-06` is written. Pick exactly one of three dispositions: `VERDICT-SCAN-01: UPGRADE to <version>` when a patched release exists and installs on requires-python >=3.11; `VERDICT-SCAN-01: DISMISS` when no patched release exists AND the vulnerable API is provably absent (state the exact `dismissed_reason` enum value to use); `VERDICT-SCAN-01: ACCEPT` when no patched release exists AND the vulnerable API is reachable (state the compensating control). BELOW that line, record the supporting evidence IN THIS ORDER: the current pin; the vulnerable range; the first patched version and whether it exists on PyPI with distribution files; the complete list of cryptography APIs this project imports with file:line, which must name both `core/credentials.py` and `core/session_store.py`; whether any PKCS#7 or EnvelopedData symbol appears anywhere plus the search result.

  you should see: the line immediately after the heading reads one of the three disposition strings and nothing else, with the evidence beneath it. Planning-time expectation is `UPGRADE to 50.0.0`, with unreachability recorded as the reason there was never live exposure, NOT as a reason to skip the upgrade.
  The heading alone is not evidence. 38-02 step 21, Block 4 steps 28 and 35, and `38-01-PLAN.md` Task 3's acceptance criterion all branch on the LINE. A heading with an empty section must fail step 31's check rather than pass it.
  YOUR CALL: DISMISS is only permitted when no patched release exists AND the PKCS#7 API is provably absent.

- [ ] Step 28. `[SAY TO CLAUDE]`

  > Add the scope note to `38-SCAN-BASELINE.md`: open PR #25 (the Dependabot minor-and-patch group) does NOT touch the cryptography pin, so 38-02's edit will not collide with it; and #25 is explicitly out of scope for this phase because it carries the FastAPI 0.115 to 0.141 jump that unregisters `/api/events`.

- [ ] Step 29. Stage the baseline.

```powershell
rtk git add .planning/phases/38-scanning-to-zero/38-SCAN-BASELINE.md
```

- [ ] Step 30. Commit the baseline. This is an approval point per project CLAUDE.md: files table, proposed message, explicit yes.

```powershell
rtk git commit -m "docs(38-01): record scanner baseline, SCAN-06 trap verdict, cryptography disposition"
```

  you should see: commit succeeds.

- [ ] Step 31. Verify the verdict heading and the commit subject.

```powershell
(Select-String -Path .planning\phases\38-scanning-to-zero\38-SCAN-BASELINE.md -Pattern "^## VERDICT-SCAN-01$").Count
(Select-String -Path .planning\phases\38-scanning-to-zero\38-SCAN-BASELINE.md -Pattern "^VERDICT-SCAN-01: (UPGRADE to [0-9][0-9.]*|DISMISS|ACCEPT)$").Count
rtk proxy git log -1 --format=%s
```

  you should see: `1`, then `1`, then a subject starting `docs(38-01):`.
  if the second count is not exactly `1`: the heading is present but the machine-readable verdict line is missing, malformed, or duplicated. The heading alone passes nothing: 38-02, Block 4 and `38-01-PLAN.md` Task 3's automated verify all key on the anchored line. Fix the line before continuing; this is the same shape as step 21's `VERDICT-SCAN-06` check and it is deliberately no longer satisfied by the heading.

- [ ] Step 32. Working tree clean apart from the deliberately untracked checkpoint file.

```powershell
rtk git status --porcelain
```

  you should see: no output other than a single `?? .planning/phases/38-scanning-to-zero/.continue-here.md` line. That one line is EXPECTED from step 2 onward and is not dirt: step 2's `rtk git reset` deliberately left the file in the working tree, untracked and unignored, so it stays available locally while being kept out of every commit on this branch. Anything else in this output is a real uncommitted change.
  It must never be committed. Do NOT resolve this line by `rtk git add`-ing the phase directory: that stages the stale `status: paused` handoff and Block 4's merge would carry it onto master. Block 6 step 27 is the only step that removes it, and it removes it from the tree rather than committing it.

- [ ] Step 33. `[DECIDE]` Prove zero GitHub state was changed. Search this block's session transcript for `-X PATCH`, `-X POST`, `-X DELETE`, `-X PUT`. There must be none.

  you should see: no mutating HTTP verb anywhere in Block 1.
  if it fails: something mutated state during a read-only block. Stop and identify it before Block 2.

- [ ] Step 34. `[SAY TO CLAUDE]`

  > Create `.planning/phases/38-scanning-to-zero/38-01-SUMMARY.md` containing both verdicts verbatim, the alert inventory totals per rule, and every place where the live measurement contradicted this plan's expected values.

  you should see: the file quotes both the `VERDICT-SCAN-06` and `VERDICT-SCAN-01` literals.

- [ ] Note: if any `gh api` response looked summarised or truncated at any point in this block, re-run it as `rtk proxy gh api ...` and use the raw JSON. A filtered body is never acceptable as evidence for an acceptance criterion.

### BLOCK 2: Plan 38-02. Production fixes plus the invariant test. 95 min

Six `[DECIDE]` points: steps 6, 21, 34, 35, 48, 49. Two negative-control judgements: steps 13/14 and steps 40/41. The only genuine `[WALK AWAY]` stretches are the full pytest runs. Nothing reaches master in this block. Block 4 lands it.

- [ ] Step 1. Gate check: 38-01 finished and the baseline exists with both sections.

```powershell
Test-Path .planning\phases\38-scanning-to-zero\38-SCAN-BASELINE.md
Select-String -Path .planning\phases\38-scanning-to-zero\38-SCAN-BASELINE.md -Pattern "^## Alert Inventory$|^## VERDICT-SCAN-01$"
```

  you should see: `True` and both headings.
  if it fails: go back to Block 1. Do not start Task 1 or Task 2 without it.

- [ ] Step 2. Confirm the branch.

```powershell
rtk proxy git rev-parse --abbrev-ref HEAD
```

  you should see: `phase-38-scanning-to-zero`.

- [ ] Step 3. Only if the suite errors on missing imports, install the web extra. Known from prior sessions, do not rediscover.

```powershell
.venv\Scripts\python.exe -m pip install -e ".[web]"
```

- [ ] Step 4. Only if the suite errors on missing imports, install httpx (undeclared in the repo).

```powershell
.venv\Scripts\python.exe -m pip install httpx
```

- [ ] Step 5. `[WALK AWAY]` Capture the BEFORE pytest count.

```powershell
.venv\Scripts\python.exe -m pytest --tb=short
```

  you should see: 969 passed, 2 skipped. Record the exact numbers for the summary.
  if it fails: run steps 3 and 4, then re-run.

- [ ] Step 6. `[DECIDE]` `[SAY TO CLAUDE]`

  > Read `main.py` lines 40-60, `core/cli/run.py` lines 1-50, `core/registry.py` lines 114-155 (the existing hostname-matching convention at :121, :137, :150), and the `## Alert Inventory` section of `38-SCAN-BASELINE.md`. Confirm alerts #3, #4, #5 are still open and still at `main.py:49-52` and `core/cli/run.py:29-36`. If they moved, stop and tell me.

  you should see: all three alerts confirmed at those locations.

- [ ] Step 7. `[SAY TO CLAUDE]`

  > Create `core/urls.py` with a single module-level function `host_matches(url: str | None, domain: str) -> bool`. Under 30 lines, docstring naming the CodeQL rule it satisfies. Parse with `urllib.parse.urlparse`, take `.hostname` or `""`, lowercase both sides, return True only when host equals domain exactly or ends with `"." + domain`. Wrap the parse so malformed input returns False rather than raising; `urlparse` raises ValueError on some malformed IPv6 literals.

- [ ] Step 8. `[SAY TO CLAUDE]`

  > Edit `main.py`. Add `from core.urls import host_matches` to the import block and change the `needs_bb_autobuy` generator so the condition reads `host_matches(item.link, "bestbuy.com") and item.auto_buy`. Matcher swap only. Do NOT touch the surrounding gate logic, the test_mode short circuit, or getpass handling.

- [ ] Step 9. `[SAY TO CLAUDE]`

  > Edit `core/cli/run.py`. Add `from core.urls import host_matches` and change the `needs_cvv` generator so the condition reads `(host_matches(item.link, "bestbuy.com") or host_matches(item.link, "amazon.com")) and item.auto_buy`. Do NOT touch the test_mode or monitor_only short circuits or getpass. The docstring at `core/cli/run.py:14-19` says the CVV gate mirrors `main.py:main()` logic; that mirroring must survive, so both sites change together or neither does.

- [ ] Step 10. `[SAY TO CLAUDE]`

  > Create `tests/test_url_host_match.py` covering every behavior case: www subdomain True, exact host True, mixed-case True, query-string spoof False, path-segment spoof False, `bestbuy.com.attacker.net` False, `notbestbuy.com` False, `""` and `None` False with no raise, `"not a url at all"` False with no raise, plus two integration cases. Use `pytest.mark.parametrize` for the pure cases. For integration, follow `tests/test_cli_run.py`'s mocking shape: MagicMock config with `debug=MagicMock(test_mode=False, monitor_only=False)` and `available=MagicMock(items=[MagicMock(link="https://evil.example/?ref=bestbuy.com", auto_buy=True)])`, patch `getpass.getpass`, assert it was never called, for both `main.main()` and `core.cli.run.handle_run()`.

- [ ] Step 11. Confirm no suppression was added anywhere: no `paths-ignore` entry, no CodeQL config file, no `# lgtm`, no `# nosec`. The fix is the host parse. Suppression is not a fix.

- [ ] Step 12. Targeted suite.

```powershell
.venv\Scripts\python.exe -m pytest tests/test_url_host_match.py tests/test_cli_run.py tests/test_main_wiring.py tests/test_cvv_threading.py tests/test_no_cvv_in_logs.py --tb=short -q
```

  you should see: all listed files pass.

- [ ] Step 13. NEGATIVE CONTROL part A. This is a judgement, not a tick: you must read the failure output and confirm the failures are the RIGHT failures. `[SAY TO CLAUDE]`

  > Temporarily revert `core/urls.py::host_matches` to `return domain in (url or "")`, then tell me to run the test file.

```powershell
.venv\Scripts\python.exe -m pytest tests/test_url_host_match.py --tb=short -q
```

  you should see: at least 3 cases FAIL, and the failures must be the spoof cases (query-string spoof, path-segment spoof, `bestbuy.com.attacker.net`), not import errors or collection errors. Paste the output into `38-02-SUMMARY.md`.
  if it fails to fail: the tests are not gates. Fix the tests before continuing.

- [ ] Step 14. NEGATIVE CONTROL part B. `[SAY TO CLAUDE]` Restore the real `host_matches` implementation.

```powershell
.venv\Scripts\python.exe -m pytest tests/test_url_host_match.py --tb=short -q
```

  you should see: all tests pass again. Record both outputs in the summary.

- [ ] Step 15. Acceptance: no substring URL test remains at either site.

```powershell
Select-String -Path main.py,core\cli\run.py -Pattern '"bestbuy\.com" in |"amazon\.com" in '
```

  you should see: no output.
  (POSIX original in appendix)

- [ ] Step 16. Acceptance: `main.py` routes through the helper.

```powershell
(Select-String -Path main.py -Pattern "host_matches").Count
```

  you should see: at least `2` (import plus call).

- [ ] Step 17. Acceptance: `core/cli/run.py` routes through the helper.

```powershell
(Select-String -Path core\cli\run.py -Pattern "host_matches").Count
```

  you should see: at least `3` (import plus two calls).

- [ ] Step 18. Acceptance: prove no suppression was used instead of a fix.

```powershell
Select-String -Path core\urls.py,main.py,core\cli\run.py -Pattern "lgtm|nosec|paths-ignore"
```

  you should see: no output.

- [ ] Step 19. `[WALK AWAY]` Full suite must be green and strictly above the baseline.

```powershell
.venv\Scripts\python.exe -m pytest --tb=short -q
```

  you should see: 0 failures, passed count strictly greater than 969.

- [ ] Step 20. `[SAY TO CLAUDE]`

  > Read the `## VERDICT-SCAN-01` section of `38-SCAN-BASELINE.md`, all 15 lines of `requirements.txt`, and `pyproject.toml` lines 14-24 including the comment stating pins match `requirements.txt` byte for byte. State the verdict value back to me.

- [ ] Step 21. `[DECIDE]` Branch on VERDICT-SCAN-01. Write the choice down. Do not proceed on a guess.
  - `UPGRADE to <version>` (expected `50.0.0`): steps 22 through 32.
  - `DISMISS`: skip to step 33.
  - `ACCEPT`: skip to step 34.

- [ ] Step 22. UPGRADE 1 of 4: build the throwaway probe venv BEFORE touching any manifest. 49 to 50 is a major bump and major bumps remove deprecated APIs.

```powershell
python -m venv "$env:TEMP\cryptoprobe"
```

  (POSIX original in appendix)

- [ ] Step 23. UPGRADE: upgrade pip inside the probe venv.

```powershell
& "$env:TEMP\cryptoprobe\Scripts\python.exe" -m pip install --quiet --upgrade pip
```

  you should see: exit 0, no output.

- [ ] Step 24. UPGRADE: install the target version in the probe venv. Substitute the verdict's target.

```powershell
& "$env:TEMP\cryptoprobe\Scripts\python.exe" -m pip install --quiet "cryptography==50.0.0"
```

  you should see: exit 0.
  if it fails: the wheel does not build or install on this Python. That invalidates UPGRADE. Go back to step 21.

- [ ] Step 25. UPGRADE: prove the three symbols this project actually uses still exist.

```powershell
& "$env:TEMP\cryptoprobe\Scripts\python.exe" -c "import cryptography; from cryptography.fernet import Fernet, InvalidToken; from cryptography.hazmat.primitives.kdf.scrypt import Scrypt; print(cryptography.__version__)"
```

  you should see: the target version printed, exit 0. Paste into the summary.
  if it fails: an ImportError here means the upgrade breaks the project. Stop and re-derive the verdict.

- [ ] Step 26. UPGRADE 2 of 4. `[SAY TO CLAUDE]`

  > Edit `requirements.txt` line 3 from `cryptography==49.0.0` to `cryptography==50.0.0`.

- [ ] Step 27. UPGRADE 3 of 4. `[SAY TO CLAUDE]`

  > Edit the matching entry in `pyproject.toml`'s `[project]` dependencies list to the IDENTICAL pin. The comment above that list says they match byte for byte, and the `wheel` CI job installs from the wheel alone, so a `pyproject.toml` left at 49.0.0 would ship a vulnerable wheel while `requirements.txt` looked fixed.

- [ ] Step 28. UPGRADE 4a: reinstall locally from the edited manifest.

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

  you should see: install completes, cryptography resolves to the new version.
  IRREVERSIBLE (local only, disruptive): this destroys the cryptography 49 install inside your `.venv` and replaces it with 50. Fully recoverable with `.venv\Scripts\python.exe -m pip install "cryptography==49.0.0"`. Nothing outside the venv is touched.

- [ ] Step 29. `[WALK AWAY]` UPGRADE 4b: full suite.

```powershell
.venv\Scripts\python.exe -m pytest --tb=short -q
```

  you should see: 0 failures, no credential or session test regressions.
  if it fails: a Fernet token written under 49 must still decrypt under 50. If a credential or session test fails, STOP and report. Do NOT delete the test.

- [ ] Step 30. UPGRADE acceptance, half 1.

```powershell
Select-String -Path requirements.txt -Pattern "^cryptography=="
```

  you should see: the target version.

- [ ] Step 31. UPGRADE acceptance, half 2.

```powershell
Select-String -Path pyproject.toml -Pattern "cryptography=="
```

  you should see: the same version string as step 30.

- [ ] Step 32. UPGRADE acceptance: the pin must equal the advisory's first patched version. Do not pin past it.

```powershell
rtk proxy gh api "repos/thezoid/ShopPyBot/dependabot/alerts/13" --jq ".security_vulnerability.first_patched_version.identifier"
```

  you should see: the version pinned in both manifests.

- [ ] Step 33. DISMISS branch only: make NO file edit.

```powershell
rtk proxy git diff --numstat -- requirements.txt pyproject.toml
```

  you should see: empty output. Record in the summary that the manifests are unchanged and that the dismissal executes in Block 4 Task 3 with the reason string the verdict names.

- [ ] Step 34. `[DECIDE]` ACCEPT branch only: make NO file edit.

```powershell
rtk proxy git diff --numstat -- requirements.txt pyproject.toml
```

  you should see: empty output. Record the compensating control the verdict names, note that Dependabot alert #13 remains open, and FLAG IN THE SUMMARY that SCAN-01 therefore closes as accepted risk rather than as zero findings. This changes the phase's headline claim and the plan requires it be surfaced to you explicitly.

- [ ] Step 35. `[DECIDE]` Explicit non-action: do NOT merge or rebase open PR #25 in this block. It carries the FastAPI 0.115 to 0.141 jump that unregisters `/api/events` and kills the dashboard SSE channel, proven by its own CI. It does not touch the cryptography line, so there is no collision to resolve.
  IRREVERSIBLE if violated: merging #25 whole lands the FastAPI bump on master and destroys the dashboard SSE channel there. Recovery is a revert commit through another PR, not an undo.

```powershell
rtk gh pr view 25 --repo thezoid/ShopPyBot --json state,title
```

  you should see: `OPEN`, untouched.

- [ ] Step 36. `[WALK AWAY]` Task 2 verify.

```powershell
.venv\Scripts\python.exe -m pytest --tb=short -q
```

  you should see: 0 failures.

- [ ] Step 37. `[SAY TO CLAUDE]`

  > Read `core/credentials.py` lines 44-80 (SECRET_KEYS) and 394-423 (migrate_from_env); `core/cli/setup.py` lines 100-130 (the three flagged print calls at :108, :122, :126); all 72 lines of `logger.py`, specifically `writeLog` at :49, its print at :65 and `logFile.write` at :72; and `tests/test_no_cvv_in_logs.py` lines 1-20 to see the existing AST-scanner style and avoid duplicating it. Note that `tests/test_cvv_threading.py` and `tests/test_no_cvv_in_logs.py` must NOT be modified.

- [ ] Step 38. `[SAY TO CLAUDE]`

  > Create `tests/test_secret_names_not_values.py`. Write it BEFORE anything else in this task and confirm it can fail. Do NOT modify `core/credentials.py`, `core/cli/setup.py`, or `logger.py`: nothing about them is broken; the test pins behaviour they already have. Structure: (1) a fake store class with `set(key, val)` recording into a dict and `get(key)` reading it back; (2) `test_migrate_from_env_returns_names_never_values`, monkeypatch `os.environ` with two SECRET_KEYS entries set to unique sentinels such as `SENTINEL_VALUE_A_9f3c` and `SENTINEL_VALUE_B_2b71`, call `core.credentials.migrate_from_env(fake_store)`, assert the return is exactly the two key names, every element is in SECRET_KEYS, and neither sentinel appears in `capsys.readouterr().out` or `.err`; (3) `test_migrate_from_env_warning_path_leaks_no_value`, make the fake store's `get` return None so the read-back failure branch at `core/credentials.py:411-416` fires, assert the WARNING line contains the key name and neither sentinel; (4) `test_writelog_file_output_contains_no_secret_value`, monkeypatch `SHOPBOT_DATA_DIR` at `tmp_path` so `core.paths.log_dir()` resolves inside the temp tree, run the same migration, read every file under the resolved log directory, assert sentinels absent and at least one key name present (CodeQL alert #31 is specifically the disk sink at `logger.py:72`); (5) `test_guard_is_not_vacuous`, call `writeLog("leak-probe SENTINEL_VALUE_C_7d10", "ERROR")` directly and assert the sentinel IS present in captured stdout. Do NOT import `core.cli.setup`'s interactive `handle_setup`; it calls getpass and `_prompt_backend`.

- [ ] Step 39. Run the new test file.

```powershell
.venv\Scripts\python.exe -m pytest tests/test_secret_names_not_values.py --tb=short -q
```

  you should see: all tests pass, including `test_guard_is_not_vacuous`, proving the capture and file-read machinery can observe a leak when one exists.

- [ ] Step 40. NEGATIVE CONTROL part A. This is a judgement, not a tick: read the failure output and confirm the failures are the RIGHT failures. `[SAY TO CLAUDE]`

  > Temporarily edit `core/credentials.py:411` to append `f"{key}={val}"` instead of `key`, then tell me to run the file.

```powershell
.venv\Scripts\python.exe -m pytest tests/test_secret_names_not_values.py --tb=short -q
```

  you should see: at least 2 tests FAIL, and the failures must be the sentinel-leak assertions, not import or fixture errors. Paste output into the summary.
  if it fails to fail: the invariant test is not a gate and the SCAN-02 dismissals in Block 5 have nothing behind them. Fix before continuing.

- [ ] Step 41. NEGATIVE CONTROL part B. `[SAY TO CLAUDE]` Revert the `core/credentials.py:411` edit.

```powershell
.venv\Scripts\python.exe -m pytest tests/test_secret_names_not_values.py --tb=short -q
```

  you should see: all tests pass again. Record both outputs in the summary.

- [ ] Step 42. Acceptance: prove the negative-control edit was fully reverted.

```powershell
rtk proxy git diff --numstat -- core/credentials.py
```

  you should see: empty output.

- [ ] Step 43. Acceptance: this task adds a test and changes no production file.

```powershell
rtk git status --porcelain core/credentials.py core/cli/setup.py logger.py
```

  you should see: empty output.

- [ ] Step 44. `[WALK AWAY]` Acceptance: full suite green.

```powershell
.venv\Scripts\python.exe -m pytest --tb=short -q
```

  you should see: 0 failures.

- [ ] Step 45. `[WALK AWAY]` Plan verification 1 of 5: final full-suite run.

```powershell
.venv\Scripts\python.exe -m pytest --tb=short -q
```

  you should see: 0 failures, more than 969 passed.

- [ ] Step 46. Plan verification 2 of 5.

```powershell
Select-String -Path main.py,core\cli\run.py -Pattern '"bestbuy\.com" in |"amazon\.com" in '
```

  you should see: no output.
  (POSIX original in appendix)

- [ ] Step 47. Plan verification 3 of 5. Skip the equality expectation if DISMISS or ACCEPT was taken.

```powershell
Select-String -Path requirements.txt,pyproject.toml -Pattern "cryptography=="
```

  you should see: the same version on both lines.

- [ ] Step 48. `[DECIDE]` Plan verification 4 of 5: confirm BOTH negative controls actually ran and both produced failures before being reverted (steps 13/14 for `host_matches`, steps 40/41 for the secret-name invariant). If either was skipped, the tests are not gates and Block 5's dismissals lose their backing.

  you should see: both before/after outputs captured in `38-02-SUMMARY.md`.

- [ ] Step 49. `[DECIDE]` Commit everything on `phase-38-scanning-to-zero` with conventional messages scoped `38-02`. Approval point: files table, proposed message, explicit yes. Nothing is pushed to master.

  you should see: 38-02-scoped commits on the phase branch; master untouched.

- [ ] Step 50. Plan verification 5 of 5.

```powershell
rtk git status --porcelain
```

  you should see: no output other than the single `?? .planning/phases/38-scanning-to-zero/.continue-here.md` line carried over from Block 1 step 2. That line is expected and is not uncommitted work; every other line is. It must never be committed, and `rtk git add` on the phase directory is not the way to clear it.

- [ ] Step 51. `[SAY TO CLAUDE]`

  > Write `.planning/phases/38-scanning-to-zero/38-02-SUMMARY.md`. It must include: before and after pytest counts, BOTH negative-control outputs, the clean-venv cryptography probe output, and the exact diff hunks for `main.py` and `core/cli/run.py`. Under DISMISS or ACCEPT, also state which branch was taken and why.

### BLOCK 3: Plan 38-03. Workflow tree hardening plus the SCAN-08 deferral record. 55 min

- [ ] Step 1. Gate check.

```powershell
rtk proxy git rev-parse --abbrev-ref HEAD
Test-Path .planning\phases\38-scanning-to-zero\38-SCAN-BASELINE.md
```

  you should see: `phase-38-scanning-to-zero` and `True`.
  if it fails: the baseline is missing, run Block 1 first. This plan cannot start.

- [ ] Step 2. `[DECIDE]` `[SAY TO CLAUDE]`

  > Read the `## VERDICT-SCAN-06` section of `38-SCAN-BASELINE.md` and tell me which verdict it records: SAFE-TO-DELETE or DEFER.

  you should see: one of the two. This is the branch decision for the whole block. Write it down.

- [ ] Step 3. `[SAY TO CLAUDE]`

  > Read `.github/workflows/ci.yml` in full, all 82 lines, before editing it. Tell me where the `on:` mapping ends and `jobs:` begins.

- [ ] Step 4. `[SAY TO CLAUDE]`

  > Read `.github/workflows/gitleaks.yml` lines 14 through 24 as the working example of a scoped permissions block: top-level `permissions: contents: read` plus a job-level override.

- [ ] Step 5. SCAN-05. `[SAY TO CLAUDE]`

  > Insert a top-level permissions block into `ci.yml`, between the `on:` block and `jobs:`. Exact content: `permissions:` newline two spaces `contents: read`. Do NOT add job-level blocks. Do NOT touch the `on:` triggers, the `env:` blocks, or the comment blocks. The comment blocks at `ci.yml:40-43` and `:77-79` explain a real failure mode (the `runner` context is invalid in job-level `env:`) and must survive verbatim. Those are the pre-insert line numbers; this three-line insertion shifts them to `:43-46` and `:80-82`, so do not re-check against the pre-insert numbers afterwards.

- [ ] Step 6. Verify ci.yml still parses.

```powershell
.venv\Scripts\python.exe -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('OK')"
```

  you should see: `OK`.
  if it fails: on `ModuleNotFoundError: yaml`, run `.venv\Scripts\python.exe -m pip install pyyaml` and retry. On a YAML error, the insert broke indentation; fix before continuing.

- [ ] Step 7. Acceptance: exactly one top-level permissions key.

```powershell
(Get-Content .github\workflows\ci.yml | Where-Object { $_ -notmatch "^\s*#" } | Select-String -Pattern "^permissions:").Count
```

  you should see: `1`.
  (POSIX original in appendix)

- [ ] Step 8. Acceptance: the read scope is present.

```powershell
(Get-Content .github\workflows\ci.yml | Where-Object { $_ -notmatch "^\s*#" } | Select-String -Pattern "contents: read").Count
```

  you should see: at least `1`.

- [ ] Step 9. Acceptance: key ordering.

```powershell
Select-String -Path .github\workflows\ci.yml -Pattern "^on:|^permissions:|^jobs:"
```

  you should see: strictly increasing line numbers in the order `on:`, `permissions:`, `jobs:`.

- [ ] Step 10. Acceptance: job parsing intact.

```powershell
.venv\Scripts\python.exe -c "import yaml; d=yaml.safe_load(open('.github/workflows/ci.yml')); print(sorted(d['jobs'].keys()))"
```

  you should see: `['test', 'wheel']`.

- [ ] Step 11. `[DECIDE]` **STOP. Write the verdict on this line before reading further: VERDICT-SCAN-06 = ____________**
  - If you wrote `DEFER`: do NOT run the command below. Skip to step 13 now. Step 12 does not apply either.
  - If you wrote `SAFE-TO-DELETE`: paste the WHOLE fenced block as ONE invocation. The `& { ... }` wrapper is load-bearing and must not be removed: it makes the guard and the `rtk git rm` one PARSED unit, so a `throw` aborts the entire script block and the removal is never reached unless the recorded verdict is literally `SAFE-TO-DELETE`. What the wrapper guarantees is atomicity across a submission boundary, not merely that a guard precedes the command. Without it every line is a separate top-level statement and a bare top-level `throw` terminates only the statement it is in: measured on this box with `rtk` and `Select-String` stubbed and the recorded verdict set to `DEFER`, feeding the unwrapped lines one at a time made the guard print `VERDICT-SCAN-06 = 'DEFER' - DO NOT DELETE` and the `rtk git rm` on the following line ran anyway. This is the same failure mode as Block 6 step 15 and it is fixed the same way.

```powershell
& {
  $b = ".planning\phases\38-scanning-to-zero\38-SCAN-BASELINE.md"
  $h = @(Select-String -Path $b -Pattern "^## VERDICT-SCAN-06$").Count
  $v = @(Select-String -Path $b -Pattern "^VERDICT-SCAN-06: (SAFE-TO-DELETE|DEFER)$" | ForEach-Object { $_.Matches[0].Groups[1].Value })
  "VERDICT read: [$($v -join ',')] headings=$h"
  if ($h -ne 1 -or $v.Count -ne 1) { throw "GATE FAIL: VERDICT-SCAN-06 missing or malformed, nothing deleted" }
  if ($v[0] -eq "DEFER") { throw "VERDICT-SCAN-06 = 'DEFER' - DO NOT DELETE. Skip to step 13." }
  if ($v[0] -ne "SAFE-TO-DELETE") { throw "GATE FAIL: VERDICT-SCAN-06 missing or malformed, nothing deleted" }
  rtk git rm .github/workflows/codeql-analysis.yml
}
```

  you should see: a `VERDICT read: [SAFE-TO-DELETE] headings=1` line, no `throw` output, then the removal is reported.
  The gate asserts on the verdict VALUE, never on an exit code, and it fails CLOSED on three separate shapes: a missing or unreadable baseline, a heading count other than one, and a verdict line that is missing, malformed or duplicated. Those all emit the literal `GATE FAIL: VERDICT-SCAN-06 missing or malformed, nothing deleted`, which is the same token `38-03-PLAN.md` Task 1's gate emits and its acceptance criteria check for. A recorded `DEFER` is a different, expected outcome and gets its own message.
  if pwsh shows a `>>` continuation prompt after the first line: that is correct behaviour, not a hang. Keep pasting. It is the shell holding the block until the closing brace arrives, which is exactly the atomicity this wrapper buys. A caller that submits the lines independently gets a hard parse error on the opening brace instead of a partial execution. That protects a caller that STOPS at the parse error. One that logs it and keeps submitting the remaining lines still reaches the mutation, because lines 2 through N are individually valid. An automated driver must abort the whole sequence on the opening-brace parse error.
  if it fails: a `throw` here leaves the file intact. That is the designed outcome, not an error to work around. Do not unwrap the block, and do not edit the guard to fall through; go to step 13.
  IRREVERSIBLE: this deletes a workflow file, and `CodeQL` is currently a REQUIRED status check on master. If that context is produced by this workflow rather than by default setup, deleting it creates a required check that can never report and permanently blocks every future merge, including this phase's own PR. It destroys the working-tree copy of the file. Recovery: `rtk git checkout HEAD -- .github/workflows/codeql-analysis.yml` before the commit, or `rtk proxy git revert <sha>` after; the file content itself is never lost from git history.

- [ ] Step 12. BRANCH A acceptance.

```powershell
Test-Path .github\workflows\codeql-analysis.yml
rtk git status --porcelain .github/workflows/codeql-analysis.yml
```

  you should see: `False`, then a staged deletion line.
  (POSIX original in appendix)

- [ ] Step 13. `[DECIDE]` SCAN-06 BRANCH B, only if VERDICT-SCAN-06 says DEFER. `[SAY TO CLAUDE]`

  > Do NOT delete. Leave `codeql-analysis.yml` exactly as it is. Add a `## SCAN-06 deferred` section to `38-SCAN-BASELINE.md` naming which of conditions a/b/c failed, and state that the required-checks context list must be corrected before the file can be removed. Record SCAN-06 as blocked and carry it forward.

  you should see: the file still exists and the `## SCAN-06 deferred` section names the failed condition. A deferral here is a permitted outcome, not a failure.

- [ ] Step 14. `[SAY TO CLAUDE]` Both branches:

  > Record the two deliberate non-changes in `38-SCAN-BASELINE.md`. (a) `dev` remains listed in the `on: push` and `on: pull_request` branch filters of `ci.yml` and `gitleaks.yml` even though Block 6 deletes the `dev` branch: leaving the filter is inert, removing it would widen the diff into a file Phase 39 also edits, and no SCAN requirement asks for it. (b) `ci.yml` uses `actions/checkout@v7` plus `actions/setup-python@v7` in the `test` job and `@v6` of both in the `wheel` job; recorded as an observation for Phase 39, not changed here.

  you should see: both recorded explicitly so a later reader does not read them as oversights.

- [ ] Step 15. `[SAY TO CLAUDE]`

  > Read the files Task 2 edits before touching them: `ci.yml` as edited by Task 1, `gitleaks.yml` all 30 lines including the header comment about the Actions allowlist, and `release-please.yml` all 28 lines.

- [ ] Step 16. SCAN-11 step 1: enumerate every action reference so nothing is pinned from memory.

```powershell
Get-ChildItem .github\workflows -Filter *.yml | Select-String -Pattern "uses:"
```

  you should see: the complete list of `owner/repo@tag` references. Expect 7 on the SAFE-TO-DELETE branch, 10 on the DEFER branch (`codeql-analysis.yml` adds three). Record the total; step 22 compares against it.

- [ ] Step 17. `[DECIDE]` SCAN-11 step 2: resolve each distinct `owner/repo@tag` to a commit SHA and prove that commit exists. The loop covers every distinct reference in one run; on the DEFER branch add step 19's three `codeql-analysis.yml` references to the same list.

```powershell
foreach ($r in "actions/checkout@v7","actions/setup-python@v7","actions/checkout@v6","actions/setup-python@v6","gitleaks/gitleaks-action@v3","googleapis/release-please-action@v5") { $aref,$tag = $r -split "@", 2; $repo = (($aref -split "/")[0..1]) -join "/"; $ref = rtk proxy gh api "repos/$repo/git/ref/tags/$tag" | ConvertFrom-Json; $sha = if ($ref.object.type -eq "tag") { (rtk proxy gh api $ref.object.url | ConvertFrom-Json).object.sha } else { $ref.object.sha }; $proof = (rtk proxy gh api "repos/$repo/commits/$sha" | ConvertFrom-Json).sha; "$r -> $sha proof=$proof match=$($sha -eq $proof)" }
```

  you should see: every line ends `match=True`.
  The two-stage parse is NOT optional either. An action reference can carry a SUBPATH: `github/codeql-action/init@v4` names repository `github/codeql-action` and the action inside it at `init`. Splitting only on `@` and using the whole left side as the repository requests `repos/github/codeql-action/init/git/ref/tags/v4`, which 404s, and the run reads as "the tag does not exist" rather than "the reference was parsed wrong". Taking the first TWO path segments as `owner/repo` handles both shapes and matches what step 24 already does when it re-proves the pins. The `-split "@", 2` limit protects the tag half if a reference ever carries a second `@`.
  The annotated-tag branch is NOT optional. Annotated tags return an object of type `tag`; taking `.object.sha` from those yields the tag object's SHA, not the commit's, which fails at run time.
  Cross-check values only, do NOT paste these in, re-resolve them: `actions/checkout@v7 -> 3d3c42e5aac5ba805825da76410c181273ba90b1`; `actions/setup-python@v7 -> 5fda3b95a4ea91299a34e894583c3862153e4b97`; `actions/checkout@v6 -> d23441a48e516b6c34aea4fa41551a30e30af803`; `actions/setup-python@v6 -> ece7cb06caefa5fff74198d8649806c4678c61a1`; `gitleaks/gitleaks-action@v3 -> e0c47f4f8be36e29cdc102c57e68cb5cbf0e8d1e`; `googleapis/release-please-action@v5 -> 45996ed1f6d02564a971a2fa1b5860e934307cf7`.
  if it fails: a 404 or a different SHA is a STOP. Do not guess and do not fall back to the plan's table.

- [ ] Step 18. SCAN-11 step 3. `[SAY TO CLAUDE]`

  > Rewrite each `uses:` reference in place, keeping the tag name in a trailing comment. Format is exactly one space, `#`, one space, then the tag name as it was written before. Example: `      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7`. Pin every reference in the file set including the GitHub-owned `actions/*` ones. Preserve the existing v6 and v7 divergence between the `test` and `wheel` jobs: pin each to the SHA of the tag it names today. Do NOT align them; aligning is a behaviour change dressed as a hardening change, and the `wheel` job was proven green on v6 exactly once, on PR 24.

- [ ] Step 19. DEFER branch only. `[SAY TO CLAUDE]`

  > Also pin the three references in `codeql-analysis.yml` (`actions/checkout@v7`, `github/codeql-action/init@v4`, `github/codeql-action/analyze@v4`) using the same resolve-then-prove procedure from step 17. Add them to step 17's list and re-run it; two of the three carry a subpath, so the repository is `github/codeql-action` and the tag is `v4` for both, which is exactly the case step 17's two-stage parse exists to handle. Both resolve to the same tag on the same repository, so expect two identical SHAs from the two lines.

- [ ] Step 20. `[SAY TO CLAUDE]`

  > Record, do not act on, this watch item: `gitleaks.yml` and `release-please.yml` both carry header comments saying their actions must be allowlisted under Settings, Actions, General. SHA pins still match an owner/repo allowlist pattern, so pinning should not change allowlist behaviour. Block 4's pull request is where that gets proven, because a startup failure there means zero jobs scheduled. Risk to watch, not a blocker here.

- [ ] Step 21. Verify every workflow file still parses.

```powershell
.venv\Scripts\python.exe -c "import yaml,glob; [yaml.safe_load(open(p)) for p in glob.glob('.github/workflows/*.yml')]; print('OK')"
```

  you should see: `OK`.

- [ ] Step 22. Acceptance: count of fully pinned `uses:` lines.

```powershell
$uses = Get-ChildItem .github\workflows -Filter *.yml | Select-String -Pattern "uses:"
"total   = " + $uses.Count
"pinned  = " + ($uses | Where-Object { $_.Line -match "@[0-9a-f]{40} # " }).Count
```

  you should see: `pinned` equals `total`, and `total` equals the number from step 16.
  (POSIX original in appendix)

- [ ] Step 23. Acceptance: no floating tag survives outside a trailing comment.

```powershell
($uses | Where-Object { $_.Line -match "@v[0-9]" }).Count
```

  you should see: `0`. The comment text contains `# v7`, but `@v[0-9]` only matches the reference itself, so this check is not self-invalidating.
  if it fails: re-run `$uses = ...` from step 22 first; `$uses` is a stale snapshot if you edited files since.

- [ ] Step 24. Acceptance: re-prove every pinned SHA is a real commit in the repo it names. The loop re-reads the files, so it covers every pin including the three `codeql-analysis.yml` ones on the DEFER branch. Paste all outputs into the summary.

```powershell
foreach ($u in (Get-ChildItem .github\workflows -Filter *.yml | Select-String -Pattern "uses:\s*(\S+)@([0-9a-f]{40})")) { $ref = $u.Matches[0].Groups[1].Value; $sha = $u.Matches[0].Groups[2].Value; $repo = (($ref -split "/")[0..1]) -join "/"; $proof = rtk proxy gh api "repos/$repo/commits/$sha" --jq ".sha"; "$ref@$sha proof=$proof match=$($sha -eq $proof)" }
```

  you should see: one line per pin, every line ending `match=True`, and the line count equal to the `total` from step 22.

- [ ] Step 25. Acceptance: step counts unchanged by the pinning edits.

```powershell
.venv\Scripts\python.exe -c "import yaml; d=yaml.safe_load(open('.github/workflows/ci.yml')); print(len(d['jobs']['test']['steps']), len(d['jobs']['wheel']['steps']))"
```

  you should see: `4 5`.

- [ ] Step 26. `[SAY TO CLAUDE]`

  > Read before editing: the `38-CONTEXT.md` operator decision paragraph on SCAN-08; `.planning/REQUIREMENTS.md` line 70 (the SCAN-08 bullet) and line 217 (its traceability row); `.planning/STATE.md` lines 95 through 140 (the Accumulated Context block, to place the new section consistently); and `.planning/ROADMAP.md` lines 193 through 206 (Phase 38 success criteria; criterion 2's "and the rule applies to administrators" clause is SCAN-08). There is no `ROADMAP.md` at the repository root; the file is at `.planning/ROADMAP.md`. Tell me the exact lines to change.

- [ ] Step 27. `[DECIDE]` HARD RULE: do NOT call the branch protection API anywhere in this block. No `required_pull_request_reviews` change, no `enforce_admins` change. Recording is the entire deliverable. The apply commands written in step 30 are text to store, not commands to run now.

- [ ] Step 28. `[SAY TO CLAUDE]`

  > Edit `.planning/REQUIREMENTS.md` line 70 so the SCAN-08 bullet reads as deferred rather than pending, keeping the original requirement text intact and appending the disposition. Example: `- [~] **SCAN-08**: Branch protection on master requires at least one review and applies to admins. DEFERRED to milestone close by operator decision 2026-08-03, see Phase 38.` Also change its traceability row at line 217 from `| SCAN-08 | Phase 38 | Pending |` to `| SCAN-08 | Phase 38 | Deferred to milestone close |`. Change no other requirement row. No em dashes, no horizontal rules.

- [ ] Step 29. `[SAY TO CLAUDE]`

  > Edit `.planning/STATE.md`: add a new section under Accumulated Context, immediately after `### Sequencing Invariants (v5.0 ...)`, titled `### Deferred to Milestone Close (v5.0)`. It must name SCAN-08, the reason, who decided and when, and where the executable detail lives. Four lines or fewer; STATE.md is read at the top of every planning session. No em dashes, no horizontal rules.

- [ ] Step 30. `[SAY TO CLAUDE]`

  > Edit `38-SCAN-BASELINE.md`: add a `## SCAN-08 DEFERRED` section holding the executable detail so milestone close is copy and paste. It must contain the current measured state (`enforce_admins.enabled = false`, `required_pull_request_reviews = null`), the two apply calls, and the two re-query calls with expected results `1` and `true`. STORE THIS TEXT, DO NOT RUN IT. Apply block: `echo '{"required_approving_review_count":1,"dismiss_stale_reviews":true}' | gh api -X PATCH repos/thezoid/ShopPyBot/branches/master/protection/required_pull_request_reviews --input -` and `gh api -X POST repos/thezoid/ShopPyBot/branches/master/protection/enforce_admins`. Prove block: `gh api repos/thezoid/ShopPyBot/branches/master/protection/required_pull_request_reviews --jq '.required_approving_review_count'` and `gh api repos/thezoid/ShopPyBot/branches/master/protection/enforce_admins --jq '.enabled'`. Note in the same section that PR #23's release-please token problem is deferred alongside it and for a related reason: it needs a GitHub App, deliberately not a PAT, because on a public repo with `enforce_admins: false` an owner-identity token would bypass branch protection entirely. Enabling `enforce_admins` is what makes that safer, so the two land together. No em dashes, no horizontal rules.

- [ ] Step 30.5. `[SAY TO CLAUDE]`

  > Edit `.planning/ROADMAP.md` line 201, Phase 38's success criterion 2, the one carrying the clause `and the rule applies to administrators`. Keep the existing sentence byte-identical and append the CANONICAL annotation, one space after its full stop. The text is canonical, not an example, and must be reproduced exactly: `The admin-enforcement clause DEFERRED to milestone close after Phase 50 by operator decision 2026-08-03 (SCAN-08); the apply procedure lives in 38-SCAN-BASELINE.md under "## SCAN-08 DEFERRED".` Do not paraphrase it and do not substitute a shorter parenthetical. Do not renumber the criteria, do not edit criteria 1, 3 or 4, and do not touch the Phase 38 planning-corrections block below them. No em dashes, no horizontal rules.

  you should see: criterion 2 no longer asserts a criterion this phase deliberately does not meet. Without this edit the phase closes with its own roadmap claiming admin enforcement it never applied.
  This is the same literal `38-03-PLAN.md` Task 3 mandates. It deliberately carries all three substrings the phase's checks look for, `admin-enforcement clause DEFERRED`, `SCAN-08` and `DEFERRED`, so step 31's `Select-String` below passes on it unchanged. A reworded annotation breaks that check silently.

- [ ] Step 31. Task 3 verify.

```powershell
(Select-String -Path .planning\REQUIREMENTS.md -Pattern "Deferred to milestone close").Count
(Select-String -Path .planning\phases\38-scanning-to-zero\38-SCAN-BASELINE.md -Pattern "^## SCAN-08 DEFERRED$").Count
(Select-String -Path .planning\ROADMAP.md -Pattern "admin-enforcement clause DEFERRED").Count
```

  you should see: at least `1`, then exactly `1`, then exactly `1`.

- [ ] Step 32. Acceptance: both SCAN-08 mentions carry the deferral wording.

```powershell
Select-String -Path .planning\REQUIREMENTS.md -Pattern "SCAN-08"
```

  you should see: the bullet and the traceability row both carrying `DEFERRED` or `Deferred`, and no other requirement id changed.

- [ ] Step 33. Acceptance: the REQUIREMENTS.md diff is minimal.

```powershell
rtk proxy git diff --numstat -- .planning/REQUIREMENTS.md
```

  you should see: exactly one line, `2       2       .planning/REQUIREMENTS.md`. Any other numbers mean more than two lines changed. `rtk proxy` is mandatory: plain `rtk git diff` reformats and indents hunk lines, so any `^[+-]` pattern matches only the literal `--- Changes ---` separator and passes vacuously no matter how far the file drifted.

- [ ] Step 34. Acceptance: the STATE.md heading landed exactly once.

```powershell
(Select-String -Path .planning\STATE.md -Pattern "^### Deferred to Milestone Close \(v5\.0\)$").Count
```

  you should see: `1`.

- [ ] Step 35. Acceptance: prove branch protection was NOT changed, part 1.

```powershell
rtk proxy gh api "repos/thezoid/ShopPyBot/branches/master/protection/enforce_admins" --jq ".enabled"
```

  you should see: `false`.
  if it fails: there are two different failures here and they have opposite responses. If the read does not SUCCEED, for example a 403 because branch protection is unavailable for the repository's current plan and visibility, or a 404, then the answer is UNKNOWN, not a violation. Record the verbatim status line, stop, and report; the no-mutation proof simply cannot be taken today. If the read succeeds and returns something other than `false`, the protection API was touched by this block, which step 27 forbids: record it and report it. In NEITHER case may you write to the protection API. Do not PATCH `enforce_admins`, do not PATCH `required_pull_request_reviews`, do not "revert" anything: a protection write is exactly what step 27's HARD RULE prohibits, and issuing one to make this acceptance check read the way you expected would be the very mutation this step exists to disprove. SCAN-08's apply commands are stored text, never commands to run here.

- [ ] Step 36. Acceptance: prove branch protection was NOT changed, part 2. Paste the WHOLE fenced block as ONE invocation; the guard and the read it judges have to be one parsed unit.

```powershell
& {
  $out  = (rtk proxy gh api "repos/thezoid/ShopPyBot/branches/master/protection" --jq ".required_pull_request_reviews" 2>&1 | Out-String)
  $code = $LASTEXITCODE
  $val  = $out.Trim()
  "required_pull_request_reviews=[$val] exit=$code"
  if ($code -ne 0) { throw "UNKNOWN, not a PASS: the protection read exited $code. Record this output verbatim. Do NOT write to the protection API." }
  if ($val -match '"status"\s*:\s*"4[0-9][0-9]"') { throw "UNKNOWN, not a PASS: the response body carries an HTTP error status, so this is a parsed error page and not a protection setting. Record it verbatim. Do NOT write to the protection API." }
  if ($val -ne "null") { throw "required_pull_request_reviews reads [$val], not null. Stop and report. Do NOT PATCH it back." }
  "PASS: required_pull_request_reviews is null, read with exit 0"
}
```

  you should see: `required_pull_request_reviews=[null] exit=0`, then `PASS: required_pull_request_reviews is null, read with exit 0`.
  What changed and why: the earlier form of this step piped the whole protection object through `ConvertFrom-Json` and coalesced a MISSING property to the string `null` with `??`. On a 403 that parses the error body, finds no `required_pull_request_reviews` property, prints exactly `null`, and satisfies "you should see: `null`" while `$LASTEXITCODE` is 1 and nobody reads it. That is a false green standing in for the only evidence this block honoured its own no-mutation rule. The read now asserts on the exit code AND on the body AND on the literal value, all inside one invocation.
  if it fails: a thrown `UNKNOWN` is not a violation and is not a pass. Record the output verbatim and report that the no-mutation proof is unavailable today. Do NOT respond to any outcome of this step with a write to the protection API; step 27 forbids it and a "revert" here would itself be the mutation.

- [ ] Step 37. Stage everything from this block.

```powershell
rtk git add .github/workflows .planning/REQUIREMENTS.md .planning/STATE.md .planning/ROADMAP.md .planning/phases/38-scanning-to-zero/38-SCAN-BASELINE.md
rtk git status --porcelain
```

  you should see: the workflow edits (plus the codeql deletion on branch A) and the four doc files staged, alongside the single untracked `?? .planning/phases/38-scanning-to-zero/.continue-here.md` line carried since Block 1 step 2. That line is expected and stays untracked. The `rtk git add` above names its paths explicitly for exactly that reason: never widen it to `.planning/phases/38-scanning-to-zero/` here, which would stage the stale paused-run handoff into this commit and land it on master at Block 4's merge.

- [ ] Step 38. `[DECIDE]` Commit. Approval point: files table, proposed message, explicit yes.

```powershell
rtk git commit -m "ci(38-03): scope ci.yml permissions, drop superseded CodeQL workflow, pin actions by SHA"
```

  you should see: commit created on `phase-38-scanning-to-zero`.

- [ ] Step 39. `[DECIDE]` Optional split: if the SCAN-08 doc edits are cleaner as their own commit, stage them separately and use this message instead of folding them into step 38.

```powershell
rtk git commit -m "docs(38-03): record SCAN-08 deferral to milestone close"
```

  you should see: two commits instead of one, both on the phase branch.

- [ ] Step 40. Acceptance: working tree clean apart from the deliberately untracked checkpoint file.

```powershell
rtk git status --porcelain
```

  you should see: no output other than the single `?? .planning/phases/38-scanning-to-zero/.continue-here.md` line. It is untracked and unignored on purpose since Block 1 step 2 and it must never be committed. `38-03-PLAN.md`'s own acceptance criterion scopes its clean-tree check to this plan's file set (`git status --porcelain -- .github/workflows .planning/REQUIREMENTS.md .planning/ROADMAP.md .planning/STATE.md .planning/phases/38-scanning-to-zero/38-SCAN-BASELINE.md`) for the same reason; run that scoped form if you want the criterion verbatim. Do NOT clear this line by `rtk git add`-ing the phase directory.

- [ ] Step 41. Acceptance: the branch carries only 38-02's and 38-03's commits.

```powershell
rtk proxy git log --oneline origin/master..HEAD
```

  you should see: the 38-02 and 38-03 commits and nothing else.
  Note: `rtk proxy` is mandatory here. Plain `rtk git log` on a range can silently return empty.

- [ ] Step 42. `[SAY TO CLAUDE]`

  > Write `.planning/phases/38-scanning-to-zero/38-03-SUMMARY.md`. It must include the full pinned reference table with each verification output, which VERDICT-SCAN-06 branch was taken, the two deliberate non-changes (the `dev` branch filter entries, the v6/v7 divergence), the Actions allowlist watch item, and SCAN-06 marked blocked if the DEFER branch was taken.

- [ ] Note: no GitHub web UI action is required by this block. The Actions allowlist question is a watch item proven by Block 4's pull request, not here.

### BLOCK 4: Plan 38-04. Open the PR, get green, merge, re-query the alerts. 70 min plus waits

Baseline master SHA for comparison is `bd70601f3fc79f5a26cf0e98d96b615f9c3320bd`.

- [ ] Step 1. `[SAY TO CLAUDE]`

  > Read `38-02-SUMMARY.md`, `38-03-SUMMARY.md`, and the `## VERDICT-SCAN-06` section of `38-SCAN-BASELINE.md`. Then tell me: the cryptography version moved from and to, the three url-sanitization alert numbers, the two permissions alert numbers, the SCAN-06 verdict, and the count of action references pinned.

- [ ] Step 2. Confirm the branch and that master has not moved underneath it.

```powershell
rtk git fetch origin --prune
rtk proxy git rev-parse --abbrev-ref HEAD
rtk proxy git log --oneline origin/master..HEAD
rtk git rev-list --count HEAD..origin/master
```

  you should see: the LAST command prints `0`. Branch protection has `strict: true`, so a nonzero count means the merge will be refused.

- [ ] Step 3. `[DECIDE]` ONLY IF step 2's count was nonzero: merge master in. Do NOT rebase; the branch may already be pushed.

```powershell
rtk git merge origin/master
rtk git rev-list --count HEAD..origin/master
.venv\Scripts\python.exe -m pytest --tb=short -q
```

  you should see: count now `0`, and the full suite passing locally before you push.

- [ ] Step 4. Push the branch.

```powershell
rtk git push -u origin phase-38-scanning-to-zero
```

  you should see: push succeeds, branch appears on origin.

- [ ] Step 5. `[DECIDE]` Author the PR body file first, then open the PR. The body needs one line each for SCAN-01 (version moved from and to), SCAN-03 (the three alert numbers), SCAN-05 (the two alert numbers), SCAN-06 (the verdict taken), SCAN-11 (count of references pinned), and SCAN-08 (recorded as deferred, no protection setting changed).

  `[SAY TO CLAUDE]`

  > Write the PR body to `$env:TEMP\pr-38-body.md` with one line each for SCAN-01, SCAN-03, SCAN-05, SCAN-06, SCAN-11, and SCAN-08-deferred, using the values from the two summaries.

```powershell
rtk proxy gh pr create --repo thezoid/ShopPyBot --base master --head phase-38-scanning-to-zero --title "chore(38): scanning to zero, part 1 of 2" --body-file "$env:TEMP\pr-38-body.md"
```

  you should see: the new PR URL. Record it into a variable now: `$PR = "<PR_NUMBER>"`. Record `PR_NUMBER = ______` on paper too. Every later command needs it, and `$PR` lives only in this terminal window.

- [ ] Step 6. `[WALK AWAY]` Watch the checks. `--watch` blocks until every check reaches a conclusion, so this one really is a start-it-and-leave step.

```powershell
rtk proxy gh pr checks $PR --repo thezoid/ShopPyBot --watch --interval 30
```

  you should see: every check reaching conclusion `success`, including `CodeQL`, `test (ubuntu-latest)`, `test (windows-latest)`, and `gitleaks`. Expect eight checks if SCAN-06 deleted the workflow file, because `Analyze (python)` and `Analyze (actions)` come from default setup and survive the deletion.
  Note: `gitleaks` runs only as a GitHub Action. It is not installed locally and must not be run locally.

- [ ] Step 7. `[WATCH]` Fallback only, if `--watch` does not terminate. This does not block; re-run it yourself.

```powershell
rtk proxy gh pr checks $PR --repo thezoid/ShopPyBot
```

  you should see: same bar as step 6, all checks success before merging.

- [ ] Step 8. `[DECIDE]` Failure shape 1: any job reporting `startup_failure` with zero steps means an action reference did not resolve or was rejected by the Actions allowlist. Re-check the SHA.

```powershell
rtk proxy gh api "repos/<owner>/<repo>/commits/<sha>"
```

  you should see: the pinned SHA resolves to a real commit on the action's repo.
  DO NOT revert a pin to a floating tag to make the check pass. Fix the pin or fix the allowlist.

- [ ] Step 9. `[DECIDE]` `[BROWSER]` Failure shape 2, HARD STOP: if `CodeQL` is missing entirely from the check list, the required context has no producer. That is the SCAN-06 trap firing and the SAFE-TO-DELETE verdict was wrong.
  Open `https://github.com/thezoid/ShopPyBot/pull/<PR_NUMBER>/checks` and read the check list yourself.
  you should see: either `CodeQL` present, or you stop the run, do NOT merge, and report. Re-derive the verdict from Block 1 steps 14 through 20.
  Write the outcome down here before moving on: `CodeQL PRESENT: ______`

- [ ] Step 10. `[DECIDE]` PRECONDITION: step 9's box is ticked and you wrote `CodeQL PRESENT: yes` next to it. If you did not personally see a check named exactly `CodeQL` in the step 6 output, do not run this command. Merge as a merge commit so release-please still sees each conventional commit.

```powershell
rtk proxy gh pr merge $PR --repo thezoid/ShopPyBot --merge
```

  you should see: the merge succeeds.
  IRREVERSIBLE: this merges the phase branch into master and lands the deletion of `.github/workflows/codeql-analysis.yml` on master. Nothing is destroyed from history, but master's tip changes for everyone. Recovery is a revert commit through another PR, not an undo.

- [ ] Step 11. Move onto merged master and create the docs branch.

```powershell
rtk git fetch origin --prune
rtk git checkout -B phase-38-docs origin/master
rtk proxy git rev-parse HEAD
```

  you should see: `phase-38-docs`, and a SHA that differs from `bd70601f3fc79f5a26cf0e98d96b615f9c3320bd`. RECORD THAT SHA: `MERGED_MASTER = ______`. Every Task 2 re-query is measured against it.
  IRREVERSIBLE (local only): `checkout -B` destroys an existing local `phase-38-docs` branch pointer if one exists. No commit is lost. Recover via `rtk proxy git reflog`.

- [ ] Step 12. Task 1 verify: PR is merged.

```powershell
rtk proxy gh pr list --repo thezoid/ShopPyBot --state merged --head phase-38-scanning-to-zero --json number,mergedAt --jq "length"
```

  you should see: a nonzero length.

- [ ] Step 13. Task 1 acceptance: state is MERGED.

```powershell
rtk proxy gh pr view $PR --repo thezoid/ShopPyBot --json state,mergedAt --jq ".state"
```

  you should see: `MERGED`.

- [ ] Step 14. Acceptance: master carries the patched cryptography pin, read from the remote not the working tree.

```powershell
rtk proxy gh api "repos/thezoid/ShopPyBot/contents/requirements.txt?ref=master" -H "Accept: application/vnd.github.raw" | Select-String "^cryptography=="
```

  you should see: the patched cryptography version line.
  (POSIX original in appendix)

- [ ] Step 15. Acceptance, SAFE-TO-DELETE branch only: the old workflow must be gone from master.

```powershell
rtk proxy gh api "repos/thezoid/ShopPyBot/contents/.github/workflows/codeql-analysis.yml?ref=master"
```

  you should see: HTTP 404. On the DEFER branch this step does not apply: the file is expected to still be present on master.

- [ ] Step 16. Acceptance: master moved off the baseline SHA.

```powershell
rtk proxy git rev-parse origin/master
```

  you should see: something other than `bd70601f3fc79f5a26cf0e98d96b615f9c3320bd`.

- [ ] Step 17. Acceptance: local tree on the docs branch.

```powershell
rtk proxy git rev-parse --abbrev-ref HEAD
```

  you should see: `phase-38-docs`.

- [ ] Step 18. `[SAY TO CLAUDE]`

  > Read the `## Alert Inventory` section of `38-SCAN-BASELINE.md` and give me the pre-change state for alerts 3, 4, 5, 33, 34. That is the "before" half of the evidence.

- [ ] Step 19. Capture the merged master SHA into a variable. Step 20 uses it; do not skip this step or step 20's filter returns nothing.

```powershell
$MSHA = (rtk proxy gh api "repos/thezoid/ShopPyBot/branches/master" | ConvertFrom-Json).commit.sha
$MSHA
```

  you should see: the SHA recorded in step 11.

- [ ] Step 20. `[WATCH]` Re-run this roughly every 60 seconds until both rows appear. Budget 15 minutes. This does not block; you must re-run it yourself. Alerts 3/4/5 need the python analysis; alerts 33/34 need the actions analysis.

```powershell
$short = $MSHA.Substring(0,8)
rtk proxy gh api "repos/thezoid/ShopPyBot/code-scanning/analyses?ref=refs/heads/master&per_page=10" |
  ConvertFrom-Json |
  Where-Object { $_.commit_sha -eq $MSHA } |
  ForEach-Object { "{0} {1} {2} results={3} {4}" -f $_.id, $short, $_.category, $_.results_count, $_.created_at }
```

  you should see: exactly two rows, one `/language:python` and one `/language:actions`. If you see fewer than two, the analysis for the merged SHA has not landed yet; keep polling. Filtering by `$MSHA` removes the eyeball comparison of an 8-character prefix, which is the comparison that decides whether the analysis you are looking at is the post-merge one.

- [ ] Step 21. `[WATCH]` Fallback only, if nothing appears after 15 minutes.

```powershell
rtk proxy gh api "repos/thezoid/ShopPyBot/actions/runs?per_page=10" |
  ConvertFrom-Json |
  Select-Object -ExpandProperty workflow_runs |
  ForEach-Object { "{0} {1} {2} {3} {4}" -f $_.name, $_.path, $_.head_sha.Substring(0,8), $_.status, $_.conclusion }
```

  you should see: a CodeQL default-setup run listed for the merged head SHA.

- [ ] Step 22. Read the `results_count` on the `/language:actions` analysis for the merged SHA from step 20's output. It must be `0`; it was `2` before the change. That number alone is the SCAN-05 proof.

  you should see: `results=0` on the `/language:actions` row for the merged SHA.

- [ ] Step 23. Re-query each alert individually. Do NOT use a filtered list query; ask by number so a missing alert is a 404 rather than a silent absence. `gh` writes `gh: No alert found for alert number N (HTTP 404)` to stderr on a miss, which is the signal to watch for.

```powershell
foreach ($n in 3,4,5,33,34) {
  $a = rtk proxy gh api "repos/thezoid/ShopPyBot/code-scanning/alerts/$n" | ConvertFrom-Json
  if ($a.status -eq "404") { "#$n MISSING (404) - investigate before continuing"; continue }
  "#{0} state={1} reason={2} fixed_at={3} rule={4}" -f $a.number, $a.state, ($a.dismissed_reason ?? "-"), ($a.fixed_at ?? "-"), $a.rule.id
}
```

  you should see: five lines, each `state=fixed` with a non-null `fixed_at`. Paste all five verbatim into the summary. A `MISSING (404)` line names the alert that 404'd; `gh` writes the error body to stdout, so `ConvertFrom-Json` succeeds and only the status check catches it.

- [ ] Step 23.5. SCAN-05 by observable CONDITION, not by alert number, with every read gated on its HTTP status line. Paste the WHOLE fenced block as ONE invocation: the merged SHA is re-derived inside it and every guard sits beside what it guards. This is the run-book's mirror of `38-04-PLAN.md` Task 2 step 4, and its two output lines are required verbatim by `38-04-SUMMARY.md`.

```powershell
& {
  $msha = ((@(rtk proxy gh api "repos/thezoid/ShopPyBot/branches/master" --jq .commit.sha) -join '')).Trim()
  if ($msha -notmatch '^[0-9a-f]{40}$') { throw "HALT: could not read the merged master SHA, got '$msha'. Record it verbatim and stop." }
  $resp   = (rtk proxy gh api -i "repos/thezoid/ShopPyBot/code-scanning/alerts?state=open&per_page=100" | Out-String)
  $status = ($resp -split '\r?\n')[0]
  if ($status -notmatch '^HTTP/\S+\s+200\b') { throw "HALT (re-query integrity): the code-scanning alert list returned '$status'. Record that status line verbatim in the summary. Anything other than 200 is UNKNOWN, not zero: do not record a fixed, closed or resolved disposition for any alert, do not hand anything to Block 5, and do not proceed." }
  $open = @(($resp -replace '(?s)^.*?\r?\n\r?\n','') | ConvertFrom-Json)
  "HTTP status: $status"
  "open alert records: $($open.Count)"
  $b64 = ((@(rtk proxy gh api "repos/thezoid/ShopPyBot/contents/.github/workflows/ci.yml?ref=$msha" --jq .content) -join '') -replace '\s','')
  if ($b64 -notmatch '^[A-Za-z0-9+/=]{40,}$') { throw "HALT: could not read ci.yml at $msha from the contents API. Record the raw response and stop; do not claim SCAN-05." }
  $ci = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($b64))
  if ($ci -notmatch '(?m)^permissions:') { throw "HALT: ci.yml at $msha carries no workflow-level permissions block. Block 3 did not land; do not claim SCAN-05." }
  $wp   = @($open | Where-Object { $_.rule.id -eq 'actions/missing-workflow-permissions' -and $_.most_recent_instance.location.path -eq '.github/workflows/ci.yml' })
  $live = @($wp | Where-Object { $_.most_recent_instance.category -notlike '.github/workflows/codeql-analysis.yml*' })
  "ci.yml workflow-permissions records still open: $($wp.Count), of which live: $($live.Count)"
  $wp | ForEach-Object { "  #{0} cat={1} {2}:{3}" -f $_.number, $_.most_recent_instance.category, $_.most_recent_instance.location.path, $_.most_recent_instance.location.start_line }
  if ($live.Count -ne 0) { throw "HALT: ci.yml still reproduces actions/missing-workflow-permissions under a live analysis category at $msha. The permissions block did not close it. Dismiss nothing; report with the lines above and stop." }
  "measured against master SHA $msha"
}
```

  you should see: an `HTTP status:` line containing ` 200`, then `ci.yml workflow-permissions records still open: 0, of which live: 0`, then `measured against master SHA <40-hex>`. Paste those lines into `38-04-SUMMARY.md` verbatim; the summary contract requires them as written.
  Any record counted in `$wp` but not in `$live` is a stale record from the retired workflow's category. Hand it to Block 5 step 15 with the staleness recorded; do NOT dismiss it here.
  if it fails: a thrown `HALT (re-query integrity):` is not a pass and is never recorded as `0`. Record the status line verbatim, treat the result as UNKNOWN, and stop. A `HALT:` on the ci.yml read or on the missing `permissions:` block means Block 3's edit is not on master; fix that before claiming SCAN-05.

<!-- POSTURE-PENDING: step 23's per-number re-query still names #33 and #34 for the ci.yml workflow-permissions findings, which is why this step checks SCAN-05 by condition instead; whether those two numbers are still the right records, and which ci.yml job each maps to, must be re-derived from a live 200 on code-scanning/alerts once the operator settles the repository posture, because re-enabling code scanning may renumber them. The condition check above is posture-independent and does not rely on any alert number. -->

- [ ] Step 24. `[DECIDE]` ONLY IF any of the five is still `state=open` after the merged-SHA analysis exists: fetch its instances.

```powershell
$n = "<N>"
rtk proxy gh api "repos/thezoid/ShopPyBot/code-scanning/alerts/$n/instances?per_page=10" |
  ConvertFrom-Json |
  ForEach-Object { "ref={0} sha={1} cat={2} state={3} loc={4}:{5}" -f $_.ref, $_.commit_sha.Substring(0,8), $_.category, $_.state, $_.location.path, $_.location.start_line }
```

  you should see: per open alert, whether its category begins `.github/workflows/codeql-analysis.yml` or is `/language:python` / `/language:actions` at the merged SHA.

- [ ] Step 25. `[DECIDE]` Branch A on step 24: if the only open instances carry a category beginning `.github/workflows/codeql-analysis.yml`, it is a stale instance from the workflow deleted in Block 3 and can never refresh. Hand it to Block 5 Task 2 for dismissal with the staleness recorded. Do NOT dismiss it here. This branch only applies if VERDICT-SCAN-06 was SAFE-TO-DELETE; on DEFER the workflow still exists and can in principle refresh those instances, so the staleness premise does not hold.

  you should see: the summary records the staleness and the explicit handoff; no dismissal command was run.

- [ ] Step 26. `[DECIDE]` Branch B on step 24: if an open instance carries category `/language:python` or `/language:actions` at the merged SHA, the fix did not work. Do NOT dismiss it. Report it as a genuine unresolved finding with the instance output attached, and STOP the phase.

- [ ] Step 27. Task 2 verify: count of open non-test url-sanitization and workflow-permissions alerts.

```powershell
& { $b = (rtk proxy gh api -i "repos/thezoid/ShopPyBot/code-scanning/alerts?state=open&per_page=100" | Out-String); $s = ($b -split '\r?\n')[0]; if ($s -notmatch '^HTTP/\S+\s+200\b') { throw "HALT (re-query integrity): $s" }; @(($b -replace '(?s)^.*?\r?\n\r?\n','') | ConvertFrom-Json | Where-Object { $_.rule.id -in @('py/incomplete-url-substring-sanitization','actions/missing-workflow-permissions') -and -not ($_.most_recent_instance.location.path -like 'tests/*') }).Count }
```

  you should see: `0`.
  This is `38-04-PLAN.md` Task 2's `<automated>` verify verbatim. Keep it byte-identical: the status guard is inside the same invocation as the count on purpose, because an unfiltered list read that 403s parses to an empty array and prints `0`, which is indistinguishable from a genuinely empty queue. A thrown `HALT (re-query integrity):` is not a pass and is never recorded as `0`.

- [ ] Step 28. `[SAY TO CLAUDE]`

  > Read the `## VERDICT-SCAN-01` section of `38-SCAN-BASELINE.md` and the cryptography section of `38-02-SUMMARY.md`. Tell me whether the verdict was UPGRADE, DISMISS or ACCEPT, and the exact patched version pinned.

- [ ] Step 29. Confirm the patched pin is genuinely on master.

```powershell
rtk proxy gh api "repos/thezoid/ShopPyBot/contents/requirements.txt?ref=master" -H "Accept: application/vnd.github.raw" | Select-String "^cryptography=="
```

  you should see: the patched cryptography version.

- [ ] Step 30. Same read against `pyproject.toml` on master.

```powershell
rtk proxy gh api "repos/thezoid/ShopPyBot/contents/pyproject.toml?ref=master" -H "Accept: application/vnd.github.raw" | Select-String "cryptography=="
```

  you should see: the SAME patched version as step 29.
  if it fails: a mismatch means the wheel job would ship a vulnerable wheel. Fix on a follow-up PR before closing SCAN-01.

- [ ] Step 31. `[WATCH]` Re-run this roughly every 2 minutes until the state changes. Budget 20 minutes. This does not block; you must re-run it yourself. The dependency graph refresh is driven by a push to the default branch and is not instant.

```powershell
$a = rtk proxy gh api "repos/thezoid/ShopPyBot/dependabot/alerts/13" | ConvertFrom-Json
"state={0} reason={1} fixed_at={2} range={3} patched={4}" -f $a.state, ($a.dismissed_reason ?? "-"), ($a.fixed_at ?? "-"), $a.security_vulnerability.vulnerable_version_range, $a.security_vulnerability.first_patched_version.identifier
```

  you should see: `state=fixed`.

- [ ] Step 32. Confirm the Dependabot queue as a whole. Read the status line, not just the count: an unreadable endpoint must halt with that status recorded, never be written up as an empty queue. Paste the WHOLE fenced block as ONE invocation.

```powershell
& {
  $resp   = (rtk proxy gh api -i "repos/thezoid/ShopPyBot/dependabot/alerts?state=open&per_page=100" | Out-String)
  $status = ($resp -split '\r?\n')[0]
  if ($status -notmatch '^HTTP/\S+\s+200\b') {
    throw "HALT (re-query integrity): the Dependabot alert list returned '$status'. Record that status line verbatim in the summary. Anything other than 200 is UNKNOWN, not an empty queue: do not record zero open Dependabot alerts and do not close SCAN-01."
  }
  $open = @(($resp -replace '(?s)^.*?\r?\n\r?\n','') | ConvertFrom-Json)
  "HTTP status: $status"
  "open Dependabot alerts: $($open.Count)"
  $open | ForEach-Object { "  #{0} {1} {2}" -f $_.number, $_.security_advisory.ghsa_id, $_.dependency.package.name }
}
```

  you should see: `open Dependabot alerts: 0` printed under an `HTTP status:` line containing ` 200`, or every alert still open itemised with its GHSA id and package. Paste the `open Dependabot alerts:` line into the summary exactly as printed; `38-04-PLAN.md` Task 3's acceptance criterion reads that line.
  if it fails: a thrown `HALT (re-query integrity):` is UNKNOWN, not zero. Record the status line verbatim and do not close SCAN-01 on it.

- [ ] Step 33. `[DECIDE]` ONLY IF alert 13 is still open after 20 minutes AND steps 29/30 proved master carries the patched pin: do NOT dismiss it here as a false positive. That would record a lie in the audit trail. Record in the summary that the fix is on master at `MERGED_MASTER` and the graph has not refreshed, and hand it to Block 6 Task 3's final gate for one more re-query.

  you should see: the summary states the master SHA carrying the fix and contains an explicit handoff to Block 6; no PATCH was issued.

- [ ] Step 34. `[DECIDE]` LAST RESORT, only if alert 13 is still open at Block 6 Task 3, NOT here.

```powershell
rtk proxy gh api -X PATCH repos/thezoid/ShopPyBot/dependabot/alerts/13 -f state=dismissed -f dismissed_reason=fix_started -f "dismissed_comment=Fixed on master at <SHA>: requirements.txt and pyproject.toml both pin cryptography==<version>, at or above the advisory's first patched version. Dependency graph had not re-scanned at the time of dismissal. The vulnerable PKCS#7 EnvelopedData path is not reachable from this project, which imports only Fernet, InvalidToken and Scrypt."
```

  you should see: on re-query, `state=dismissed` with `dismissed_reason=fix_started`.
  IRREVERSIBLE: dismisses Dependabot alert 13. It destroys the alert's open state. The state can be PATCHed back to `state=open`, but the dismissal event stays in the repository audit trail permanently and cannot be removed. `inaccurate`, `not_used` and `tolerable_risk` must not appear in any command this task runs; only `fix_started` matches reality.

- [ ] Step 35. `[DECIDE]` If VERDICT-SCAN-01 was DISMISS or ACCEPT rather than UPGRADE, execute the disposition the verdict specified with the reason string it named, then re-query to prove it took.

```powershell
rtk proxy gh api "repos/thezoid/ShopPyBot/dependabot/alerts/13" --jq ".state"
```

  you should see: something other than `open`, matching the verdict's disposition.
  IRREVERSIBLE: dismisses Dependabot alert 13. The state is PATCHable back to open; the dismissal event in the audit trail is not removable.

- [ ] Step 36. `[SAY TO CLAUDE]`

  > Write `.planning/phases/38-scanning-to-zero/38-04-SUMMARY.md`, minimum 40 lines: PR number and merge SHA, the full pre-merge check list with conclusions, the two analysis rows for the merged SHA with their `results_count`, the five per-alert re-query lines verbatim, and the Dependabot 13 disposition. Record every command's raw output; this is the phase's central evidence.

### BLOCK 5: Plan 38-05. Twenty-six dismissals in seven reasoned groups, plus two ORDERED secret-scanning PATCHes. 50 min plus up to 15 min of polling `[DECIDE]`

Gate: Block 4 complete, and `tests/test_secret_names_not_values.py` is on master and green. On the SAFE-TO-DELETE branch, `.github/workflows/codeql-analysis.yml` was also deleted from master, which is what makes the #25/#26 staleness claim true. On the DEFER branch that second fact does NOT hold; step 0 tells you what changes.

Two things about this block are not stylistic. First, the 19 SCAN-04 alerts are FOUR shapes, not one: each shape gets its own spot check and its own dismissal string, because a reviewer checking a comment against the cited line has to find the comment true at that line, and one string covering all 19 would be false at 16 of them. Seven distinct strings leave this block and Block 6 step 25.5 audits that they are still seven. Second, the two secret-scanning options are enabled in two requests in a fixed order with an enumeration and a wait between them, never bundled.

- [ ] PRECONDITION, fail closed. This is `38-05-PLAN.md` Task 1 step 0 and it runs before step 0's branch check. Nothing in this block runs until the code scanning alert list is readable. Paste the WHOLE fenced block as ONE invocation.

```powershell
& {
  $resp   = (rtk proxy gh api -i "repos/thezoid/ShopPyBot/code-scanning/alerts?state=open&per_page=100" | Out-String)
  $status = ($resp -split '\r?\n')[0]
  "PRECONDITION status line: [$status]"
  if ($status -notmatch '^HTTP/\S+\s+200\b') { throw "HALT: code scanning alert query did not return 200. Status line: [$status]" }
  "PRECONDITION ok"
}
```

  you should see: a `PRECONDITION status line:` whose bracketed value contains ` 200`, then `PRECONDITION ok`. Paste that status line into `38-05-SUMMARY.md`; `38-05-PLAN.md`'s acceptance criteria require it on record.
  if it fails: HALT the whole block. Do not run step 0, Task 1, Task 2 or Task 3, and do not record a single alert as closed. A non-200 is not an empty alert set: a 403, a 404, or an empty status line means code scanning is unavailable, not that the queue is clean. Treating an unreadable endpoint as a zero would write 26 permanent dismissals' worth of false evidence without issuing one PATCH.

- [ ] Step 0. `[DECIDE]` Branch check before anything in this block. Read `## VERDICT-SCAN-06` in `38-SCAN-BASELINE.md`.
  - SAFE-TO-DELETE: proceed as written.
  - DEFER: do NOT run step 19. Go from step 18 straight to step 20 and complete the block; steps 20 through 32 all still apply, including the secret-scanning enablement, which is independent of SCAN-06. Group C (#25, #26) must NOT be dismissed with the `$cc` staleness string; the workflow still exists and the staleness premise is false, and the string would write a factually false sentence into a permanent, non-editable GitHub audit trail. Re-run step 18's `/instances` probe, and if any open instance carries `/language:python`, treat #25 and #26 as LIVE and move them into Group B's reasoning with a rewritten comment. If they carry only the workflow-file category, record them as blocked-on-SCAN-06 and carry them forward as NOT MET. Do not dismiss to reach zero.

- [ ] Step 1. `[SAY TO CLAUDE]`

  > Read the `## Alert Inventory` section of `38-SCAN-BASELINE.md` and confirm the 19 SCAN-04 alert numbers and the 7 clear-text numbers match the plan's tables.

- [ ] Step 2. `[SAY TO CLAUDE]` One read per shape. A check of one shape says nothing about the other three.

  > Read `tests/test_cli_items.py` lines 7 through 21, `tests/test_plugin_amazon.py` lines 60 through 64, `tests/test_registry.py` lines 67 through 80, `tests/test_security_md.py` lines 26 through 42, and `tests/conftest.py` lines 100 through 123 (the `tmp_plugins_dir` fixture). For each, tell me what the right operand of the flagged `in` expression actually is and where that value comes from.

  you should see: four DIFFERENT answers, not one. Captured stdout; a production plugin class attribute; a plugin attribute the test itself wrote to `tmp_path`; and a repository document read off disk. "The URL literal is defined in the same file" is true of only one of the four shapes, so do not use it as the test.

- [ ] Step 3. `[DECIDE]` Re-derive the 19-alert target set live and split it into its four shape groups. Steps 5 through 5.3 each drive their loop from one of these variables, never from a literal range. Alert numbers are stable, but a post-merge analysis can add new ones.

```powershell
$alerts = @(rtk proxy gh api "repos/thezoid/ShopPyBot/code-scanning/alerts?state=open&per_page=100" |
  ConvertFrom-Json |
  Where-Object { $_.rule.id -eq "py/incomplete-url-substring-sanitization" -and $_.most_recent_instance.location.path.StartsWith("tests/") })
$alerts | ForEach-Object { "{0} {1}:{2}" -f $_.number, $_.most_recent_instance.location.path, $_.most_recent_instance.location.start_line }
$targets = @($alerts | ForEach-Object { $_.number })
"count = " + $targets.Count
$g1 = @($alerts | Where-Object { $_.most_recent_instance.location.path -like "tests/test_cli_*" } | ForEach-Object { $_.number })
$g2 = @($alerts | Where-Object { $_.most_recent_instance.location.path -like "tests/test_plugin_*" } | ForEach-Object { $_.number })
$g3 = @($alerts | Where-Object { $_.most_recent_instance.location.path -eq "tests/test_registry.py" } | ForEach-Object { $_.number })
$g4 = @($alerts | Where-Object { $_.most_recent_instance.location.path -eq "tests/test_security_md.py" } | ForEach-Object { $_.number })
"G1=[{0}] G2=[{1}] G3=[{2}] G4=[{3}]" -f ($g1 -join ","), ($g2 -join ","), ($g3 -join ","), ($g4 -join ",")
"grouped = " + ($g1.Count + $g2.Count + $g3.Count + $g4.Count)
```

  you should see: `count = 19`; `G1=[6,7,8] G2=[9,10,11,12,13,14,15] G3=[16,17,18,19] G4=[20,21,22,23,24]`; and `grouped = 19`.
  HARD GATE: if `grouped` is less than `count`, a live path matched none of the four patterns. STOP. That is a FIFTH shape and no reason string has been written for it. Do not widen a pattern to swallow it.
  HARD GATE: if `count` is not `19`, or `$targets` contains any number outside 6..24, STOP and inspect every difference before any dismissal. Do not edit the loops to match.
  YOUR CALL: a number present live but absent from the plan's table must be inspected and then placed in the group whose SHAPE it actually matches. Fewer than 19 means recording which closed on their own and why.

- [ ] Step 4. `[DECIDE]` Spot-check ONE alert per shape, four in total. `[SAY TO CLAUDE]`

  > Open the cited file and line for one alert from each of `$g1`, `$g2`, `$g3` and `$g4` and quote the source line to me. For each, name what the right operand of the flagged `in` expression is and where that value comes from.

  you should see, one finding per shape:
  - G1 (`#6` through `#8`), spot check `tests/test_cli_items.py:21`: the right operand is `capsys.readouterr().out`. The value searched for was placed on a `MagicMock` return value in the same test, and `core.service.BotService` is patched out.
  - G2 (`#9` through `#15`), spot check `tests/test_plugin_amazon.py:63`: the right operand is `AmazonPlugin.domain_patterns`, a list literal in `plugins/shopbot_plugin_amazon.py`. The `in` is list membership, not a substring search, and there is no URL on either side.
  - G3 (`#16` through `#19`), spot check `tests/test_registry.py:75`: the right operand is `domain_patterns` on a plugin the test itself wrote to `tmp_path` via `tmp_plugins_dir` in `tests/conftest.py`, or the inline `OtherPlugin` source at `tests/test_registry.py:89`.
  - G4 (`#20` through `#24`), spot check `tests/test_security_md.py:41`: the right operand is `_read_security_md()` at `tests/test_security_md.py:30`, which reads `SECURITY.md` out of this repository's own checkout.
  The one question every check answers is the same: does any attacker-controlled input reach the flagged expression? A request body, a CLI argument, an environment variable, or a network response would be attacker-controlled. A value the test itself defines, a class attribute committed to this repository, and a document read out of this repository's own checkout are not.
  HALT AND ESCALATE: if a spot check shows attacker-controlled input reaching the expression, that shape is not a test-fixture false positive. Stop the task, dismiss NOTHING in that group, and report it as a blocking finding with the file, the line, and the input path you found. Do NOT dismiss the rest of the group to get the open count to zero. The count is the evidence, not the goal.

- [ ] Step 5. Group 1 of 4, captured stdout. Reason `used in tests`, with the string written for THIS shape. The loop is driven by `$g1` from step 3, so it can only ever touch alerts you inspected.

```powershell
$c1 = "Test fixture, and no URL is being sanitized here. The right operand of the flagged 'in' is capsys.readouterr().out, the stdout captured from a CLI invocation inside the test. The string being searched for is one the test itself placed on a MagicMock return value, and core.service.BotService is patched out, so nothing attacker-controlled reaches this expression. Phase 38 (SCAN-03) routed exactly two production sites through core/urls.host_matches, which parses the host and compares exact-or-dot-suffix: the needs_bb_autobuy gate in main.py and the needs_cvv gate in core/cli/run.py. Known deliberate non-change: core/registry.py:123, :144 and :152 still substring-match plugin domain_patterns against the parsed host, so a suffix-confusion host such as bestbuy.com.attacker.net still routes to the BestBuy plugin. Dismissed per alert rather than via a tests/ path filter, so a future finding in these files still surfaces."
foreach ($n in $g1) {
  $r = rtk proxy gh api -X PATCH "repos/thezoid/ShopPyBot/code-scanning/alerts/$n" -f state=dismissed -f "dismissed_reason=used in tests" -f "dismissed_comment=$c1" | ConvertFrom-Json
  "#{0} -> {1} / {2}" -f $r.number, $r.state, $r.dismissed_reason
}
```

  you should see: three lines of the form `#N -> dismissed / used in tests`, for `#6`, `#7`, `#8`.
  IRREVERSIBLE: PATCH-dismisses every code scanning alert in `$g1`. It destroys their open state. Undo requires a manual PATCH back to `state=open`, per alert, and the dismissal event stays in the repository audit trail permanently and cannot be removed.
  (POSIX original in appendix)

- [ ] Step 5.1. Group 2 of 4, production plugin class attribute. DISTINCT string, same reason enum.

```powershell
$c2 = "Test fixture, and not a substring check at all. The right operand of the flagged 'in' is the plugin class attribute domain_patterns (AmazonPlugin.domain_patterns, WalmartPlugin.domain_patterns, and so on), a list of string literals declared in plugins/shopbot_plugin_*.py. The 'in' is list membership against that list, so the assertion is that the plugin declares its retailer domain. There is no URL on either side of the expression and no attacker-controlled input reaches it. Phase 38 (SCAN-03) routed exactly two production sites through core/urls.host_matches, which parses the host and compares exact-or-dot-suffix: the needs_bb_autobuy gate in main.py and the needs_cvv gate in core/cli/run.py. Known deliberate non-change: core/registry.py:123, :144 and :152 still substring-match plugin domain_patterns against the parsed host, so a suffix-confusion host such as bestbuy.com.attacker.net still routes to the BestBuy plugin. Dismissed per alert rather than via a tests/ path filter, so a future finding in these files still surfaces."
foreach ($n in $g2) {
  $r = rtk proxy gh api -X PATCH "repos/thezoid/ShopPyBot/code-scanning/alerts/$n" -f state=dismissed -f "dismissed_reason=used in tests" -f "dismissed_comment=$c2" | ConvertFrom-Json
  "#{0} -> {1} / {2}" -f $r.number, $r.state, $r.dismissed_reason
}
```

  you should see: seven lines, `#9` through `#15`, each `dismissed / used in tests`.
  IRREVERSIBLE: PATCH-dismisses every alert in `$g2`. It destroys their open state; the dismissal event in the audit trail is permanent.

- [ ] Step 5.2. Group 3 of 4, test-built plugin attribute. DISTINCT string.

```powershell
$c3 = "Test fixture, and not a substring check at all. The right operand of the flagged 'in' is domain_patterns on a plugin instance the test itself created: the tmp_plugins_dir fixture in tests/conftest.py writes shopbot_plugin_fake.py with domain_patterns = ['fake.com'] into tmp_path, and tests/test_registry.py:89 writes an OtherPlugin with ['other.com'] the same way. The 'in' is list membership against a list built from source the test wrote, so no attacker-controlled input reaches it. Phase 38 (SCAN-03) routed exactly two production sites through core/urls.host_matches, which parses the host and compares exact-or-dot-suffix: the needs_bb_autobuy gate in main.py and the needs_cvv gate in core/cli/run.py. Known deliberate non-change: core/registry.py:123, :144 and :152 still substring-match plugin domain_patterns against the parsed host, so a suffix-confusion host such as bestbuy.com.attacker.net still routes to the BestBuy plugin. Dismissed per alert rather than via a tests/ path filter, so a future finding in these files still surfaces."
foreach ($n in $g3) {
  $r = rtk proxy gh api -X PATCH "repos/thezoid/ShopPyBot/code-scanning/alerts/$n" -f state=dismissed -f "dismissed_reason=used in tests" -f "dismissed_comment=$c3" | ConvertFrom-Json
  "#{0} -> {1} / {2}" -f $r.number, $r.state, $r.dismissed_reason
}
```

  you should see: four lines, `#16` through `#19`, each `dismissed / used in tests`.
  IRREVERSIBLE: PATCH-dismisses every alert in `$g3`. It destroys their open state; the dismissal event in the audit trail is permanent.

- [ ] Step 5.3. Group 4 of 4, repository document read from disk. DISTINCT string.

```powershell
$c4 = "Test fixture, and no URL is being sanitized here. The right operand of the flagged 'in' is _read_security_md() at tests/test_security_md.py:30, which reads SECURITY.md out of this repository's own checkout. The assertion is that the document contains a row for each supported retailer, so the value searched is a repo-controlled document rather than a URL under validation, and no attacker-controlled input reaches it. Phase 38 (SCAN-03) routed exactly two production sites through core/urls.host_matches, which parses the host and compares exact-or-dot-suffix: the needs_bb_autobuy gate in main.py and the needs_cvv gate in core/cli/run.py. Known deliberate non-change: core/registry.py:123, :144 and :152 still substring-match plugin domain_patterns against the parsed host, so a suffix-confusion host such as bestbuy.com.attacker.net still routes to the BestBuy plugin. Dismissed per alert rather than via a tests/ path filter, so a future finding in these files still surfaces."
foreach ($n in $g4) {
  $r = rtk proxy gh api -X PATCH "repos/thezoid/ShopPyBot/code-scanning/alerts/$n" -f state=dismissed -f "dismissed_reason=used in tests" -f "dismissed_comment=$c4" | ConvertFrom-Json
  "#{0} -> {1} / {2}" -f $r.number, $r.state, $r.dismissed_reason
}
```

  you should see: five lines, `#20` through `#24`, each `dismissed / used in tests`. Across steps 5 through 5.3 that is 19 lines and FOUR distinct comment strings.
  IRREVERSIBLE: PATCH-dismisses every alert in `$g4`. It destroys their open state; the dismissal event in the audit trail is permanent.

- [ ] Step 6. Hard prohibition, no command: do NOT create `.github/codeql/codeql-config.yml`, do NOT add `paths-ignore`, do NOT add `# lgtm` or `# nosec` to any test file. The operator decision is per-alert dismissal, not blanket suppression, because blanket suppression would also hide future production findings in those files.

- [ ] Step 7. Re-query all 19 by number with a fresh GET, driven by the same live variables step 3 built. The PATCH response is not the evidence. Ask by number so a missing alert is a 404 rather than a silent absence; `gh` writes the error body to stdout, so `ConvertFrom-Json` succeeds and only the status check catches it.

```powershell
foreach ($n in @($g1 + $g2 + $g3 + $g4)) {
  $a = rtk proxy gh api "repos/thezoid/ShopPyBot/code-scanning/alerts/$n" | ConvertFrom-Json
  if ($a.status -eq "404") { "#$n MISSING (404) - investigate before continuing"; continue }
  "#{0} state={1} reason={2} at={3}" -f $a.number, $a.state, $a.dismissed_reason, $a.dismissed_at
}
```

  you should see: all 19 showing `state=dismissed`, `reason=used in tests`, non-null `dismissed_at`, and no `MISSING (404)` line. Paste all 19 lines verbatim into the summary.

- [ ] Step 8. Task 1 verify: no open code scanning alert may point into `tests/`.

```powershell
@(rtk proxy gh api "repos/thezoid/ShopPyBot/code-scanning/alerts?state=open&per_page=100" |
  ConvertFrom-Json |
  Where-Object { $_.most_recent_instance.location.path.StartsWith("tests/") }).Count
```

  you should see: `0`.

- [ ] Step 9. Acceptance: no CodeQL config directory was introduced on master.

```powershell
rtk proxy gh api "repos/thezoid/ShopPyBot/contents/.github/codeql?ref=master"
```

  you should see: HTTP 404.

- [ ] Step 10. Acceptance: no suppression mechanism exists.

```powershell
Get-ChildItem -Path tests,.github -Recurse -File | Select-String -Pattern "lgtm|nosec|paths-ignore"
```

  you should see: no output.
  (POSIX original in appendix)

- [ ] Step 11. `[SAY TO CLAUDE]`

  > Record in the summary the FOUR spot-checked alert numbers, one per shape, each with its source line quoted and a sentence naming what the flagged `in` reads on both sides and why that value is repo-controlled rather than attacker-controlled. Reproduce all four dismissal strings in full and confirm they are distinct from each other. Add this caveat: these dismissals persist only while each alert recurs at the same location. If a test file is later edited such that CodeQL emits a NEW alert number for the same expression, that alert appears open and needs the same treatment. That is the intended cost of not using a path filter.

- [ ] Step 12. `[SAY TO CLAUDE]`

  > Read `core/credentials.py` lines 44-80 and 398-423, `core/cli/setup.py` lines 104-127, `logger.py` lines 49-72, and the `38-02-SUMMARY.md` section on `tests/test_secret_names_not_values.py` and its negative control. Confirm to me that `SECRET_KEYS` at `core/credentials.py:47` is a list of 20 credential key NAMES, and that the WARNING f-string at `credentials.py:414` interpolates only the key name.

  you should see: both confirmed. This is the primary claim the plan checker was asked to falsify. If it does not hold, stop Task 2 entirely.

- [ ] Step 13. `[DECIDE]` Confirm the guard test exists on master before any clear-text dismissal.

```powershell
rtk proxy gh api "repos/thezoid/ShopPyBot/contents/tests/test_secret_names_not_values.py?ref=master" --jq ".size"
```

  you should see: a nonzero size.
  if it fails: STOP. Do not dismiss anything in Task 2.

- [ ] Step 14. `[DECIDE]` Run the guard test locally. A dismissal with no test behind it is exactly the failure mode called out.

```powershell
.venv\Scripts\python.exe -m pytest tests/test_secret_names_not_values.py -q
```

  you should see: pass.
  if it fails: STOP. Do not dismiss.

- [ ] Step 15. `[DECIDE]` Re-derive the live clear-text alert set and split it into the three groups BY PATH. This is the overview read only: steps 16, 17, 18 and 19 each re-derive their own group inside their own fence and assert it there, so nothing that mutates depends on these variables surviving a call boundary.

<!-- POSTURE-PENDING: the expected sets `27 28 29`, `31 32` and `25 26` asserted in steps 16, 17, 18 and 19 are the numbers measured while code scanning was enabled. If code scanning was re-enabled after any period of being off, re-derive all three sets from a live 200 and update those four assertions before running the fences, because a re-enable may renumber alerts. Do not weaken an assertion to make a fence pass. -->

```powershell
$clearText = @(rtk proxy gh api "repos/thezoid/ShopPyBot/code-scanning/alerts?state=open&per_page=100" |
  ConvertFrom-Json |
  Where-Object { $_.rule.id -in @("py/clear-text-logging-sensitive-data","py/clear-text-storage-sensitive-data") })
$clearText | ForEach-Object { "{0} {1} {2}:{3}" -f $_.number, $_.rule.id, $_.most_recent_instance.location.path, $_.most_recent_instance.location.start_line }
"clear-text alert records: " + $clearText.Count
$groupA = @($clearText | Where-Object { $_.most_recent_instance.location.path -eq "core/cli/setup.py" } | ForEach-Object { $_.number } | Sort-Object)
$groupB = @($clearText | Where-Object { $_.most_recent_instance.location.path -eq "logger.py" -and $_.most_recent_instance.location.start_line -in @(65,72) } | ForEach-Object { $_.number } | Sort-Object)
$groupC = @($clearText | Where-Object { $_.most_recent_instance.location.path -eq "logger.py" -and $_.most_recent_instance.location.start_line -in @(43,50) } | ForEach-Object { $_.number } | Sort-Object)
"GA=[$($groupA -join ' ')]  GB=[$($groupB -join ' ')]  GC=[$($groupC -join ' ')]"
```

  you should see: exactly 7 numbers: 25, 26, 27, 28, 29, 31, 32, then `clear-text alert records: 7` and `GA=[27 28 29]  GB=[31 32]  GC=[25 26]`. Paste both of those lines into `38-05-SUMMARY.md` exactly as printed; `38-05-PLAN.md` Task 2's acceptance criteria read them by those names. Every value in them is derived from this query BY PATH, never typed in: group A is everything at `core/cli/setup.py`, group B is `logger.py:65` and `:72` (the live `print` and `logFile.write` lines inside `writeLog`), group C is `logger.py:43` and `:50` (the same finding recorded at its pre-Phase-37 line numbers). The alert numbers are the expectation the derivation is checked against, never the selector. Alert #30 is absent by design; it is not open at baseline, which is why the phase's inventory of 3 + 19 + 7 + 2 = 31 alerts spans numbers 3 through 34.
  Seven is a count of open alert RECORDS, not a count of findings the current master analysis still reports. Five of the seven are live on master; #25 and #26 are already `state=fixed` under the default-setup analysis and remain open records only because the retired workflow analysis left open instances behind. Step 18 is what distinguishes the two. Do not skip it.
  if it fails: any deviation must be investigated before dismissing. Do not adjust the loops to match. This step is an overview and is NOT the gate: steps 16, 17, 18 and 19 each re-derive their own group inside their own `& { ... }` and assert it there, so a wrong set here stops those fences even if this print is skipped or scrolled past.

- [ ] Step 16. Group A: the three `core/cli/setup.py` alerts, reason `false positive`, with their own comment string.

```powershell
& {
  $ctp = @(rtk proxy gh api "repos/thezoid/ShopPyBot/code-scanning/alerts?state=open&per_page=100" |
    ConvertFrom-Json |
    Where-Object { $_.rule.id -in @("py/clear-text-logging-sensitive-data","py/clear-text-storage-sensitive-data") })
  $ga = @($ctp | Where-Object { $_.most_recent_instance.location.path -eq "core/cli/setup.py" } | ForEach-Object { $_.number } | Sort-Object)
  $gaSet = ($ga -join ' ')
  "GA=[$gaSet]"
  if ($gaSet -ne "27 28 29") { throw "HALT: group A derived [$gaSet], the interfaces table expects [27 28 29]. An empty derivation is the code-scanning 403 and would make the PATCH loop below iterate zero times, dismissing nothing while printing nothing; a different derivation is a renumber and would dismiss the wrong alerts. Do not PATCH." }
  $ca = "False positive. CodeQL's taint source is SECRET_KEYS at core/credentials.py:47, a module-level list of 20 credential key NAMES, not values. The flagged expressions print a key name (setup.py:108 in the --migrate branch, :126 in the interactive branch) or a prefix derived from a key name via key.split('_')[0] (setup.py:122, interactive branch). No SECRET_KEYS value reaches a print or a log call on either of the two code paths that write one: interactively via _prompt_secret (setup.py:15-25, called at :123) straight into store.set() at :125, and under --migrate via os.environ.get straight into store.set() at core/credentials.py:406-409. The invariant is pinned by tests/test_secret_names_not_values.py, which fails if any value reaches stdout or the log file."
  foreach ($n in $ga) {
    $r = rtk proxy gh api -X PATCH "repos/thezoid/ShopPyBot/code-scanning/alerts/$n" -f state=dismissed -f "dismissed_reason=false positive" -f "dismissed_comment=$ca" | ConvertFrom-Json
    "#{0} -> {1}" -f $r.number, $r.state
  }
}
```

  you should see: `GA=[27 28 29]`, then `#27 -> dismissed`, `#28 -> dismissed`, `#29 -> dismissed`.
  if a guard throws: nothing is PATCHed, which is the designed outcome. `GA=[]` means the query returned no clear-text alerts at all, which on a private repository is the code-scanning 403 and not an empty finding set; any other value means the alerts renumbered. Re-derive and reconcile before dismissing anything. Do not unwrap the block, do not delete the assertion, and do not edit the expected set to match what was derived.
  IRREVERSIBLE: PATCH-dismisses the Group A alerts. It destroys their open state. Recoverable only by a manual PATCH back to `state=open`; the dismissal event in the audit trail is permanent.

- [ ] Step 17. Group B: the two live `logger.py` alerts, with a DISTINCT comment string. That string carries the shared-sink caveat deliberately, because the caveat is the honest limit of this dismissal and it has to live where a future reader of the alert will see it, not only in a summary file. Paste the WHOLE fenced block as ONE invocation: the caveat claims a measurable property of `logger.py`, so the measurement and the two guards that judge it sit in the same parsed unit as the PATCH loop they gate. `$cb` asserts a LOCATION, not a CodeQL fingerprinting algorithm; the `SINK` and `CALLERS` values printed below are the measurement behind it.

```powershell
& {
  $ctp = @(rtk proxy gh api "repos/thezoid/ShopPyBot/code-scanning/alerts?state=open&per_page=100" |
    ConvertFrom-Json |
    Where-Object { $_.rule.id -in @("py/clear-text-logging-sensitive-data","py/clear-text-storage-sensitive-data") })
  $gb = @($ctp | Where-Object { $_.most_recent_instance.location.path -eq "logger.py" -and $_.most_recent_instance.location.start_line -in @(65,72) } | ForEach-Object { $_.number } | Sort-Object)
  $gbSet = ($gb -join ' ')
  "GB=[$gbSet]"
  if ($gbSet -ne "31 32") { throw "HALT: group B derived [$gbSet], the interfaces table expects [31 32]. An empty derivation is the code-scanning 403 and would make the PATCH loop below iterate zero times, dismissing nothing while printing nothing; a different derivation is a renumber and would dismiss the wrong alerts. Do not PATCH." }
  $lg = Get-Content logger.py
  $sink = if ($lg[48] -match '^def writeLog' -and $lg[64] -match 'print\(' -and $lg[71] -match 'logFile\.write') { "OK" } else { "MISMATCH" }
  $callers = @(Get-ChildItem -Path core,plugins,notifications,web,tests,scripts -Recurse -Filter *.py | Select-String -Pattern "writeLog\(").Count + @(Select-String -Path main.py,models.py,utils.py,config.py -Pattern "writeLog\(").Count
  "SINK=$sink writeLog call sites outside logger.py: $callers"
  if ($sink -ne "OK") { throw "HALT: logger.py:49/:65/:72 are not the writeLog definition and its two sink lines. CB's shared-sink caveat would be false; do not PATCH." }
  if ($callers -lt 2) { throw "HALT: only $callers writeLog call sites outside logger.py. CB's shared-sink caveat would be false; do not PATCH." }
  $cb = "False positive. Same source as the setup.py alerts: SECRET_KEYS at core/credentials.py:47. The flow reaches logger.writeLog through core/credentials.py:414, an f-string that interpolates the key NAME into a WARNING message when a backend read-back fails. No secret value is on this path. Pinned by tests/test_secret_names_not_values.py, which asserts sentinel values reach neither stdout (logger.py:65) nor the log file (logger.py:72), and includes a positive control proving the assertion is not vacuous. Shared-sink caveat, stated deliberately and measured at dismissal time: these two alerts are located at logger.py:65 and :72, the print and logFile.write lines inside writeLog (defined at logger.py:49), which is the sink every logging caller in this repository reaches, not a location unique to the credentials flow. A future genuine secret leak arriving at those same lines through a different caller would therefore present at an already-dismissed location rather than as a new finding. That is exactly why this dismissal is backed by tests/test_secret_names_not_values.py, which fails on regression, rather than by this comment alone."
  foreach ($n in $gb) {
    $r = rtk proxy gh api -X PATCH "repos/thezoid/ShopPyBot/code-scanning/alerts/$n" -f state=dismissed -f "dismissed_reason=false positive" -f "dismissed_comment=$cb" | ConvertFrom-Json
    "#{0} -> {1}" -f $r.number, $r.state
  }
}
```

  you should see: `GB=[31 32]`, then `SINK=OK writeLog call sites outside logger.py: <n>` with `<n>` at least 2, then `#31 -> dismissed`, `#32 -> dismissed`. Paste the `SINK=` line into `38-05-SUMMARY.md`; it is the evidence behind `$cb`'s shared-sink caveat and `38-05-PLAN.md` Task 2 requires it on record.
  if a guard throws: nothing is PATCHed, which is the designed outcome. `SINK=MISMATCH` means `logger.py:49`, `:65` and `:72` are no longer the `writeLog` definition and its two sink lines, so the caveat's stated locations would be false; fewer than two external call sites means the sink is not shared and the caveat overstates it. Re-derive the line numbers and rewrite `$cb` before dismissing anything. Do not unwrap the block or delete a guard to get past it.
  IRREVERSIBLE: PATCH-dismisses the Group B alerts. It destroys their open state. Recoverable only by a manual PATCH back to `state=open`; the dismissal event in the audit trail is permanent.

- [ ] Step 18. `[DECIDE]` BEFORE Group C, prove the staleness claim for #25 and #26 with the instances endpoint rather than asserting it. This runs AHEAD of the group C PATCH so the evidence exists before the mutation.

```powershell
& {
  $ctp = @(rtk proxy gh api "repos/thezoid/ShopPyBot/code-scanning/alerts?state=open&per_page=100" |
    ConvertFrom-Json |
    Where-Object { $_.rule.id -in @("py/clear-text-logging-sensitive-data","py/clear-text-storage-sensitive-data") })
  $gc = @($ctp | Where-Object { $_.most_recent_instance.location.path -eq "logger.py" -and $_.most_recent_instance.location.start_line -in @(43,50) } | ForEach-Object { $_.number } | Sort-Object)
  $gcSet = ($gc -join ' ')
  "GC=[$gcSet]"
  if ($gcSet -ne "25 26") { throw "HALT: group C derived [$gcSet], the interfaces table expects [25 26]. An empty derivation is the code-scanning 403 and would make the loop below print nothing, and nothing printed reads as 'no live instance found', which is exactly the staleness proof step 19 depends on; a different derivation is a renumber and would prove staleness for the wrong alerts. Do not run step 19." }
  foreach ($n in $gc) {
    rtk proxy gh api "repos/thezoid/ShopPyBot/code-scanning/alerts/$n/instances?per_page=10" |
      ConvertFrom-Json |
      ForEach-Object { "#$n ref={0} sha={1} cat={2} state={3}" -f $_.ref, $_.commit_sha.Substring(0,8), $_.category, $_.state }
  }
}
```

  you should see: `GC=[25 26]` from the in-fence derivation, then every instance with `state=open` carrying a category beginning `.github/workflows/codeql-analysis.yml`, and the instance carrying the bare `/language:python` default-setup category reading `state=fixed`. Paste this output into the summary.
  YOUR CALL: if any open instance carries `/language:python`, the alert is LIVE not stale. Move it into Group B's reasoning, rewrite the comment, and record the change. Do not run step 19 on it.
  DEFER BRANCH: if VERDICT-SCAN-06 was DEFER, skip step 19 and go to step 20. Step 19's comment string is factually false on that branch.

- [ ] Step 19. Group C: the two stale alerts, with the staleness-specific comment. SAFE-TO-DELETE branch only, and only after step 18 confirms staleness.

```powershell
& {
  $v = (Select-String -Path .planning\phases\38-scanning-to-zero\38-SCAN-BASELINE.md -Pattern "^VERDICT-SCAN-06: (SAFE-TO-DELETE|DEFER)$" | ForEach-Object { $_.Matches[0].Groups[1].Value })
  if ($v -ne "SAFE-TO-DELETE") { throw "VERDICT-SCAN-06 = '$v' - the staleness comment asserts a deletion that did not happen. DO NOT DISMISS. Go to step 20." }
  $ctp = @(rtk proxy gh api "repos/thezoid/ShopPyBot/code-scanning/alerts?state=open&per_page=100" |
    ConvertFrom-Json |
    Where-Object { $_.rule.id -in @("py/clear-text-logging-sensitive-data","py/clear-text-storage-sensitive-data") })
  $gc = @($ctp | Where-Object { $_.most_recent_instance.location.path -eq "logger.py" -and $_.most_recent_instance.location.start_line -in @(43,50) } | ForEach-Object { $_.number } | Sort-Object)
  $gcSet = ($gc -join ' ')
  "GC=[$gcSet]"
  if ($gcSet -ne "25 26") { throw "HALT: group C derived [$gcSet], the interfaces table expects [25 26]. An empty derivation is the code-scanning 403 and would make both loops below iterate zero times, reporting a clean liveInst of 0 and dismissing nothing; a different derivation is a renumber and would dismiss the wrong alerts. Do not PATCH." }
  $liveInst = @($gc | ForEach-Object { $n = $_; rtk proxy gh api "repos/thezoid/ShopPyBot/code-scanning/alerts/$n/instances?per_page=10" | ConvertFrom-Json | Where-Object { $_.state -eq "open" -and $_.category -notlike ".github/workflows/codeql-analysis.yml*" } }).Count
  "open instances NOT from the retired codeql-analysis.yml workflow: $liveInst"
  if ($liveInst -ne 0) { throw "HALT: $liveInst open instance(s) on group C come from a live analysis. They are not stale and the staleness comment would be false; do not PATCH." }
  $cc = "False positive, and stale. Same underlying SECRET_KEYS finding as #31 and #32, recorded at pre-Phase-37 line numbers (logger.py:50 and :43, now :72 and :65 after the FC-01 ContextVar block was inserted). The default-setup instance at master 36f75c76 is already state=fixed; the remaining open instances all carry category .github/workflows/codeql-analysis.yml:analyze, at master 4123059b and at refs/pull/12/merge and refs/pull/13/merge. That workflow was disabled_manually and was deleted in Phase 38 (SCAN-06), so nothing can ever refresh those instances and the alert cannot close by itself."
  foreach ($n in $gc) {
    $r = rtk proxy gh api -X PATCH "repos/thezoid/ShopPyBot/code-scanning/alerts/$n" -f state=dismissed -f "dismissed_reason=false positive" -f "dismissed_comment=$cc" | ConvertFrom-Json
    "#{0} -> {1}" -f $r.number, $r.state
  }
}
```

  you should see: `GC=[25 26]` from the in-fence derivation, then `open instances NOT from the retired codeql-analysis.yml workflow: 0`, then `#25 -> dismissed`, `#26 -> dismissed`. That is SEVEN distinct strings written across steps 5, 5.1, 5.2, 5.3, 16, 17 and 19. Paste the `open instances NOT from...` line into the summary; it is the machine-checkable form of step 18's staleness proof and it is measured inside the same invocation as the PATCH it authorises, so it cannot be skipped by a call boundary.
  The `& { ... }` wrapper is load-bearing for the same reason it is at Block 3 step 11 and Block 6 step 15: this is the phase's third branch-conditional irreversible mutation, and prose alone (step 0, step 18's DEFER note, the IRREVERSIBLE line below) cannot stop a paste. The guard reads the recorded SCAN-06 verdict and throws on DEFER, and the wrapper makes that throw abort the PATCH loop rather than merely printing ahead of it. If pwsh shows a `>>` continuation prompt, that is the shell holding the block, not a hang. A caller that submits the lines independently gets a parse error on the opening brace; a caller that logs that error and keeps going still reaches the PATCH, so an automated driver must abort the whole sequence on it.
  IRREVERSIBLE: PATCH-dismisses the Group C alerts. It destroys their open state and writes `$cc` permanently into the repository audit trail, where it cannot be edited. Must not run before the step 18 staleness proof, and must not run at all on the DEFER branch, because `$cc` asserts a deletion that did not happen.

- [ ] Step 20. Re-query all 7 clear-text alerts by number.

```powershell
& {
  $rules = @("py/clear-text-logging-sensitive-data","py/clear-text-storage-sensitive-data")
  $ct = @(@("open","dismissed","fixed") | ForEach-Object {
      rtk proxy gh api "repos/thezoid/ShopPyBot/code-scanning/alerts?per_page=100&state=$_" | ConvertFrom-Json
    } | Where-Object { $_.rule.id -in $rules })
  $nums = @($ct | ForEach-Object { $_.number } | Sort-Object -Unique)
  $set = ($nums -join ' ')
  "clear-text alert records across open+dismissed+fixed: $($nums.Count)  [$set]"
  if ($set -ne "25 26 27 28 29 31 32") { throw "HALT: re-query derived [$set], expected '25 26 27 28 29 31 32'. An empty or short set means a 403, an unreadable body, or a renumbering, NOT that the dismissals landed. Record nothing and do not mark Task 2 verified." }
  foreach ($n in $nums) {
    $a = rtk proxy gh api "repos/thezoid/ShopPyBot/code-scanning/alerts/$n" | ConvertFrom-Json
    "#{0} state={1} reason={2} at={3}" -f $a.number, $a.state, $a.dismissed_reason, $a.dismissed_at
  }
}
```

  you should see: the record line reading `7  [25 26 27 28 29 31 32]`, then all 7 showing `state=dismissed` with `reason=false positive`. On the DEFER branch, #25 and #26 will still read `state=open`; that is the recorded blocked-on-SCAN-06 outcome, not a failure. Paste the record line and all 7 alert lines into the summary.
  This fence derives its own set rather than consuming `$clearText` from step 15, because shell variables do not survive a call boundary: an empty `$clearText` would make the loop print nothing at all, and silence here reads as "nothing left to verify" when it actually means the verification never ran. It queries `open`, `dismissed` and `fixed` explicitly rather than relying on the list endpoint's default, because by this point the alerts this step exists to check have been dismissed and a bare `state=open` query would correctly return none of them. The set assertion and the loop are in one `& { ... }` so the throw aborts the read rather than printing ahead of it.
  if it fails: a HALT here does not mean the dismissals failed. It means this verification cannot see them. Re-check that code scanning returns a 200 before concluding anything about Task 2.

- [ ] Step 21. Task 2 verify: no open alert of either clear-text rule remains.

```powershell
@(rtk proxy gh api "repos/thezoid/ShopPyBot/code-scanning/alerts?state=open&per_page=100" |
  ConvertFrom-Json |
  Where-Object { $_.rule.id -in @("py/clear-text-logging-sensitive-data","py/clear-text-storage-sensitive-data") }).Count
```

  you should see: `0` on the SAFE-TO-DELETE branch, `2` on the DEFER branch with #25 and #26 itemised as blocked-on-SCAN-06.

- [ ] Step 22. `[SAY TO CLAUDE]`

  > Record the SCAN-02 correction in the summary explicitly: the requirement says "the two" clear-text alerts in `logger.py`, but there are seven, and three of them are in `core/cli/setup.py` which SCAN-02 never mentions. All seven accounted for, none left open (or, on the DEFER branch, #25 and #26 recorded as blocked with the reason), none silently ignored. Reproduce all three clear-text dismissal strings in full and confirm they are distinct from each other. Also record the #31 and #32 shared-sink caveat in the summary in its own right, as a measured LOCATION claim and not as a claim about CodeQL's fingerprinting algorithm: those two alerts are located at `logger.py:65` and `:72`, the `print` and `logFile.write` lines inside `writeLog` (defined at `logger.py:49`), which is the sink every logging caller in this repository reaches rather than a location unique to the credentials flow, so a future genuine leak arriving at those same lines through a different caller would present at an already-dismissed location rather than as a new finding, and `tests/test_secret_names_not_values.py` is the mitigation that catches such a regression. Paste step 17's `SINK=` line as the measurement behind it.

  you should see: a single reused string across all seven does NOT satisfy acceptance, and the shared-sink caveat appears in BOTH the `$cb` dismissal comment and the summary, with step 17's `SINK=` measurement alongside it in the summary.

- [ ] Step 23. `[SAY TO CLAUDE]`

  > Read the recorded `security_and_analysis` block from Block 1 in `38-SCAN-BASELINE.md`.

  you should see: `non_provider_patterns` disabled, `validity_checks` disabled, the other three enabled.

- [ ] Step 24. Read current settings so the before state is on record.

```powershell
rtk proxy gh api "repos/thezoid/ShopPyBot" | ConvertFrom-Json | Select-Object -ExpandProperty security_and_analysis | ConvertTo-Json -Depth 5
```

  you should see: the before-state JSON. Capture it for the summary.

- [ ] Step 25. `[DECIDE]` PATCH 1 of 2: enable non-provider patterns ONLY. TWO requests, not one, and in THIS order.
  Why not bundled: `PATCH /repos/{owner}/{repo}` leaves any `security_and_analysis` property omitted from the body at its current value, so a single-key body reverts nothing and there is no technical need to bundle. The order is the whole point. Validity checks transmit candidate secrets to their issuing providers and an outbound transmission cannot be un-sent. Non-provider patterns is a broader, lower-precision detector that can surface candidates nobody has looked at yet, including on historical commits. Enabling it first and enumerating what it finds means step 27.5 is switched on against a known, reviewed candidate set rather than an unknown one. Bundling forfeits that, and it is the only ordering choice in this block that is irreversible if taken wrong.
  The payload is written with `WriteAllText` and an explicit BOM-free encoder rather than `Out-File -Encoding utf8`, so it parses correctly regardless of which PowerShell you are in.

```powershell
[System.IO.File]::WriteAllText("$env:TEMP\ss-nonprovider.json", '{"security_and_analysis":{"secret_scanning_non_provider_patterns":{"status":"enabled"}}}', (New-Object System.Text.UTF8Encoding($false)))
rtk proxy gh api -X PATCH repos/thezoid/ShopPyBot --input "$env:TEMP\ss-nonprovider.json"
Get-Date -Format "yyyy-MM-dd HH:mm:ss"
```

  you should see: the repository object returned without error, then the wall-clock time PATCH 1 returned. WRITE IT DOWN: `PATCH1_AT = ______`. Step 27's poll record is measured from it and step 31 requires it.
  Reversible: this setting can be turned back off and nothing leaves the repository boundary at this step. The irreversible half is step 27.5, which is exactly why the two are not sent together.
  (POSIX original in appendix)

- [ ] Step 26. Intermediate re-query. This is the evidence that the two PATCHes ran in the required order; it cannot be reconstructed after step 27.5.

```powershell
rtk proxy gh api "repos/thezoid/ShopPyBot" | ConvertFrom-Json | Select-Object -ExpandProperty security_and_analysis | ConvertTo-Json -Depth 5
```

  you should see: `secret_scanning_non_provider_patterns` now `enabled`; `secret_scanning`, `secret_scanning_push_protection` and `dependabot_security_updates` still `enabled`, which is the proof that omitting a key from a `PATCH /repos` body leaves it alone rather than reverting it; and `secret_scanning_validity_checks` STILL `disabled`, because it has not been sent yet. Paste this whole block into the summary.
  if it fails: if `secret_scanning_validity_checks` already reads `enabled` here, the two PATCHes were bundled and the ordering guarantee is gone. Record that plainly in the summary. Do not describe it as ordered.

- [ ] Step 27. `[WATCH]` `[DECIDE]` Enumerate what non-provider patterns surfaced, BEFORE any secret leaves the repository. POLL, do not read once. Enabling non-provider patterns kicks off a backfill scan over the repository and its history, and that scan is not finished when PATCH 1 returns, so a zero observed immediately is not evidence of a zero; recording it as one hands step 27.5 the unknown candidate set that splitting the PATCH exists to prevent. Re-run this at 2 minute intervals, writing down the count and the wall-clock time at every poll. This does not block; you re-run it yourself.

```powershell
$hits = @(rtk proxy gh api "repos/thezoid/ShopPyBot/secret-scanning/alerts?state=open&per_page=100" | ConvertFrom-Json)
"{0}  count = {1}" -f (Get-Date -Format "HH:mm:ss"), $hits.Count
$hits | ForEach-Object { "#{0} {1} {2} {3}" -f $_.number, $_.secret_type_display_name, $_.validity, $_.locations_url }
```

  you should see: a timestamped count on every run. The baseline before PATCH 1 is `0`.
  STOP CONDITION, whichever comes first: two consecutive polls return the IDENTICAL count, including two consecutive zeros; or 15 minutes have elapsed since `PATCH1_AT`. One zero with no confirming second poll does NOT satisfy this step and does NOT unlock step 27.5.
  if the 15 minute budget expires with the count still changing between polls: do not wait longer and do not pretend it settled. Record that it was still moving, treat the last observed set as the candidate set, and state in the summary that PATCH 2 was enabled against an unsettled scan.
  YOUR CALL if any alert appears: do NOT dismiss it to keep the count at zero. That is the exact behaviour this phase exists to stop. Record each one with its type and location. If it is a live credential, rotation is required and that is an operator action: report it as a blocking finding and STOP HERE, before step 27.5. Do not enable validity checks over an unrotated live credential. If it is a test fixture or a documentation example, record it and hand it to the phase verifier with the evidence so a human sees it before it is closed.
  (POSIX original in appendix)

- [ ] Step 27.5. `[DECIDE]` PATCH 2 of 2: enable validity checks ONLY, and only now, against the candidate set step 27 just recorded. Do not run this until step 27's stop condition has actually been met.

```powershell
[System.IO.File]::WriteAllText("$env:TEMP\ss-validity.json", '{"security_and_analysis":{"secret_scanning_validity_checks":{"status":"enabled"}}}', (New-Object System.Text.UTF8Encoding($false)))
rtk proxy gh api -X PATCH repos/thezoid/ShopPyBot --input "$env:TEMP\ss-validity.json"
```

  you should see: the repository object returned without error.
  IRREVERSIBLE in effect: enabling `secret_scanning_validity_checks` starts sending candidate secrets to their issuing providers for a liveness answer. This is the only action in the phase that leaves the repository boundary. The setting can be turned back off, so the configuration is recoverable, but the outbound provider calls already made cannot be recalled. Accepted deliberately as threat T-38-29, which is why step 27's poll gates it.
  (POSIX original in appendix)

- [ ] Step 27.6. Re-query and assert the end state.

```powershell
rtk proxy gh api "repos/thezoid/ShopPyBot" | ConvertFrom-Json | Select-Object -ExpandProperty security_and_analysis | ConvertTo-Json -Depth 5
```

  you should see: all five reading `enabled`: `secret_scanning`, `secret_scanning_push_protection`, `secret_scanning_non_provider_patterns`, `secret_scanning_validity_checks`, `dependabot_security_updates`. Paste it alongside the step 24 before state and the step 26 intermediate state, three blocks in the summary, not two.

- [ ] Step 28. `[SAY TO CLAUDE]`

  > Record in the summary that validity checks are now on, since they send candidate secrets to the issuing provider to ask whether they are live: a new outbound interaction for the repository (threat T-38-29, disposition accept). Record alongside it the candidate set that was on record when it was turned on: `PATCH1_AT`, the count at every 2 minute poll with its wall-clock time, the final count, the elapsed time from PATCH 1 to the final poll, and which stop condition ended the polling, two consecutive identical counts or the 15 minute budget expiring.

- [ ] Step 29. Task 3 verify.

```powershell
$s = (rtk proxy gh api "repos/thezoid/ShopPyBot" | ConvertFrom-Json).security_and_analysis
"{0},{1}" -f $s.secret_scanning_non_provider_patterns.status, $s.secret_scanning_validity_checks.status
```

  you should see: `enabled,enabled`.

- [ ] Step 30. Record the open secret scanning alert count as an acceptance artifact.

```powershell
@(rtk proxy gh api "repos/thezoid/ShopPyBot/secret-scanning/alerts?state=open&per_page=100" | ConvertFrom-Json).Count
```

  you should see: `0`. If greater than 0, every alert is listed with type and validity in the summary, and none was dismissed by this block.

- [ ] Step 31. `[SAY TO CLAUDE]`

  > Write `.planning/phases/38-scanning-to-zero/38-05-SUMMARY.md`, minimum 50 lines, containing: all 26 re-query lines verbatim; all SEVEN dismissal reason strings in full, the four shape strings from steps 5 through 5.3 and the three sub-case strings from steps 16, 17 and 19; the `/instances` evidence for #25 and #26; the #31 and #32 shared-sink caveat with step 17's `SINK=OK writeLog call sites outside logger.py: <n>` measurement beside it; the PRECONDITION status line; the `clear-text alert records:` and `GA=[...] GB=[...] GC=[...]` lines from step 15; the four spot-checked alerts, one per shape, with their source lines quoted; the SCAN-02 two-vs-seven correction; the before, intermediate and after `security_and_analysis` blocks; and the full poll record from step 28. State which of the 31 alerts left the queue by dismissal and which left by source fix (#3, #4, #5 via `core/urls.host_matches` in SCAN-03; #33 and #34 via workflow permissions in SCAN-05). Do not blur the two routes into a single zero.

- [ ] Step 32. `[DECIDE]` Commit the summary on `phase-38-docs`. Approval point: files table, proposed message, explicit yes.

```powershell
rtk git add .planning/phases/38-scanning-to-zero/38-05-SUMMARY.md
rtk git commit -m "docs(38-05): record per-alert dismissals and secret scanning enablement"
```

  you should see: the commit lands on `phase-38-docs`.

### BLOCK 6: Plan 38-06. gitleaks required, archive-then-delete origin/dev, reason audit, FINAL GATE. 70 min `[DECIDE]`

Gate: Blocks 4 and 5 complete, both summaries exist, local branch is `phase-38-docs` with no source changes, `gh` has admin rights on the repo.

Master's merge path is locked from step 5 until step 33. Step 5 adds `gitleaks` to master's required contexts, and until step 33 proves it can report on a real PR, every merge to master is blocked, including hotfixes. Do not start Block 6 unless you can finish it.

Step 15 is the only irreversible destruction of a ref in this phase. It is written as ONE pasted block on purpose and wrapped in `& { ... }` so that it is one PARSED unit as well as one pasted one: every guard, the freshly re-read delete gate, and the delete itself live in the same invocation, so no guard can be skipped by a call boundary and `$DEVSHA` cannot be empty when the delete runs. Do not unwrap it. Measured on this box, the same guards without the wrapper let the delete run anyway when the lines are submitted one at a time.

- [ ] Step 1. `[SAY TO CLAUDE]`

  > Open `.github/workflows/gitleaks.yml` and read all 30 lines including the header comment about the Actions allowlist. Confirm the job name at line 19 is exactly `name: gitleaks`.

  you should see: `name: gitleaks`, lowercase, no suffix. A required context is matched by exact string; `Gitleaks` or `gitleaks / scan` would never match.

- [ ] Step 2. `[DECIDE]` `[SAY TO CLAUDE]`

  > Open `38-04-SUMMARY.md` and find the pre-merge check list. Confirm `gitleaks` appears with conclusion `success` on a real pull_request event against master, and quote me that line.

  you should see: the quoted success line.
  if it does not: STOP the whole block. Do not add the requirement. Report which evidence failed. Remember gitleaks cannot be run locally on this box, so Actions is the only source of this evidence.

- [ ] Step 3. Second piece of gitleaks evidence: it also ran on the merged master commit.

```powershell
$MSHA = (rtk proxy gh api "repos/thezoid/ShopPyBot/branches/master" | ConvertFrom-Json).commit.sha
rtk proxy gh api "repos/thezoid/ShopPyBot/commits/$MSHA/check-runs?per_page=100" |
  ConvertFrom-Json |
  Select-Object -ExpandProperty check_runs |
  Where-Object { $_.name -eq "gitleaks" } |
  ForEach-Object { "name={0} app={1} conclusion={2}" -f $_.name, $_.app.slug, $_.conclusion }
```

  you should see: exactly one line containing `conclusion=success`.
  if it fails: nothing printed, or a non-success conclusion, means STOP. Do not add the requirement.

- [ ] Step 4. Read the current required checks so the BEFORE state is recorded, and build the revert payload NOW, before step 5 takes the risk. Step 32 just runs `rsc-revert.json`; it must never be hand-authored under pressure while master is unmergeable.

```powershell
$before = rtk proxy gh api "repos/thezoid/ShopPyBot/branches/master/protection/required_status_checks" | ConvertFrom-Json
$before | ConvertTo-Json -Depth 5 | Out-File -FilePath "$env:TEMP\rsc-before.json" -Encoding utf8
[System.IO.File]::WriteAllText("$env:TEMP\rsc-revert.json", ([pscustomobject]@{ strict = $before.strict; checks = @($before.checks | ForEach-Object { [pscustomobject]@{ context = $_.context; app_id = $_.app_id } }) } | ConvertTo-Json -Depth 5), (New-Object System.Text.UTF8Encoding($false)))
Get-Content "$env:TEMP\rsc-revert.json"
```

  you should see: `strict: true` and exactly three checks: `CodeQL` (app_id null), `test (windows-latest)` 15368, `test (ubuntu-latest)` 15368. These exact values were confirmed live against the API. `rsc-revert.json` is now ready before step 5 takes the risk. Keep both files.
  if it fails: if `rsc-revert.json` does not contain exactly three checks, do NOT run step 5. You would have no revert path.

- [ ] Step 5. `[DECIDE]` PATCH the `required_status_checks` SUB-RESOURCE only, never `/protection` itself. Build the body from what step 4 actually returned plus the one new `gitleaks` entry. Do NOT paste the literal below if step 4 showed a different existing set.

```powershell
[System.IO.File]::WriteAllText("$env:TEMP\rsc-after.json", '{"strict":true,"checks":[{"context":"CodeQL","app_id":null},{"context":"test (windows-latest)","app_id":15368},{"context":"test (ubuntu-latest)","app_id":15368},{"context":"gitleaks","app_id":15368}]}', (New-Object System.Text.UTF8Encoding($false)))
rtk proxy gh api -X PATCH repos/thezoid/ShopPyBot/branches/master/protection/required_status_checks --input "$env:TEMP\rsc-after.json"
```

  you should see: 200 with the four-entry checks array echoed back.
  This uses `checks`, NOT `contexts`. Sending `contexts` drops the existing `app_id` bindings (15368 for the test legs, `null` for CodeQL) and lets any app satisfy a named context. That is a weakening dressed as a hardening. Never send `contexts`.
  IRREVERSIBLE: mutates master branch protection. It destroys the previous three-entry required-contexts configuration. Adding a context that cannot report blocks every future merge until reverted. Recovery is the step 32 revert using `$env:TEMP\rsc-revert.json`, built in step 4; the revert is itself another protection mutation.
  (POSIX original in appendix)

- [ ] Step 6. Re-query the sub-resource.

```powershell
$r = rtk proxy gh api "repos/thezoid/ShopPyBot/branches/master/protection/required_status_checks" | ConvertFrom-Json
$r.strict
$r.checks | ForEach-Object { "{0} app_id={1}" -f $_.context, $_.app_id }
```

  you should see: `True`, then four lines: `CodeQL app_id=`, `test (windows-latest) app_id=15368`, `test (ubuntu-latest) app_id=15368`, `gitleaks app_id=15368`. Nothing dropped.
  if it fails: anything dropped means the PATCH used the wrong shape. Restore from `rsc-revert.json` immediately.

- [ ] Step 7. Confirm nothing else moved. SCAN-08 is DEFERRED and this task must not accidentally implement part of it.

```powershell
& {
  $out  = (rtk proxy gh api "repos/thezoid/ShopPyBot/branches/master/protection" --jq ".required_pull_request_reviews" 2>&1 | Out-String)
  $code = $LASTEXITCODE
  $val  = $out.Trim()
  "required_pull_request_reviews=[$val] exit=$code"
  if ($code -ne 0) { throw "UNKNOWN, not a PASS: the protection read exited $code. Record this output verbatim. Do NOT write to the protection API." }
  if ($val -match '"status"\s*:\s*"4[0-9][0-9]"') { throw "UNKNOWN, not a PASS: the response body carries an HTTP error status, so this is a parsed error page and not a protection setting. Record it verbatim. Do NOT write to the protection API." }
  if ($val -ne "null") { throw "required_pull_request_reviews reads [$val], not null. SCAN-08 was partially implemented; stop and report. Do NOT PATCH it back." }
  "PASS: required_pull_request_reviews is null, read with exit 0"
}
rtk proxy gh api "repos/thezoid/ShopPyBot/branches/master/protection/enforce_admins" --jq ".enabled"
rtk proxy gh api "repos/thezoid/ShopPyBot/branches/master/protection" --jq ".allow_force_pushes.enabled, .allow_deletions.enabled"
```

  you should see: `required_pull_request_reviews=[null] exit=0` and `PASS: ...`, then `false`, then `false`, `false`. All unchanged.
  This is the same guarded read as Block 3 step 36 and it is here for the same reason: piping the protection object through `ConvertFrom-Json` and coalescing a MISSING property with `??` prints exactly `null` when the API answers 403, which reads as the expected PASS while the exit code says the read failed and nobody looks at it. Assert the exit code, the body and the literal value, in one invocation.
  if it fails: a thrown `UNKNOWN` means the protection API could not be read, which is not evidence that SCAN-08 stayed deferred and is also not evidence that it did not. Record the output verbatim and report. Do NOT respond by writing to the protection API in either direction.

- [ ] Step 8. Task 1 verify.

```powershell
(rtk proxy gh api "repos/thezoid/ShopPyBot/branches/master/protection/required_status_checks" | ConvertFrom-Json).checks.context | Sort-Object
```

  you should see: `CodeQL`, `gitleaks`, `test (ubuntu-latest)`, `test (windows-latest)`. Nothing dropped.
  (POSIX original in appendix)

- [ ] Step 9. `[SAY TO CLAUDE]`

  > Read the SCAN-10 operator decision paragraph in `38-CONTEXT.md` and read `38-SCAN-BASELINE.md`. State the hard ordering back to me before I run anything in Task 2.

  you should see: delete `origin/dev`, but tag it first; the tag must be pushed AND verified BEFORE the branch delete; the delete itself must be conditioned, in the same shell, on a freshly re-read tag sha equalling a freshly re-read live branch sha; never force-delete without the tag landing first; every failure path leaves the branch intact.

- [ ] Step 10. Re-measure. Do not trust the planning-time SHA. Every value here is read-only and every one of them is a guard input for step 15.

```powershell
rtk git fetch origin --prune --tags
$DEVSHA = (rtk proxy gh api "repos/thezoid/ShopPyBot/branches/dev" | ConvertFrom-Json).commit.sha
"DEVSHA=$DEVSHA"
"is_40_hex=" + ($DEVSHA -match "^[0-9a-f]{40}$")
"matches_planning_sha=" + ($DEVSHA -eq "65ef2b906ed4b6aca85ccf4e02e42deff80174e3")
rtk git rev-list --count "origin/master..$DEVSHA"
rtk git rev-list --count "$DEVSHA..origin/master"
rtk git merge-base --is-ancestor $DEVSHA origin/master
"ancestor_exit=$LASTEXITCODE"
```

  you should see: `is_40_hex=True`; `matches_planning_sha=True`; ahead count `1`; behind count around `923`; `ancestor_exit` NONZERO.
  if `is_40_hex=False`: STOP. An empty or short `DEVSHA` makes `rev-list --count "origin/master..$DEVSHA"` silently degrade into a range that measures nothing while still exiting cleanly, which reads as a passing safety check. Step 15 re-checks this guard before the delete, but do not proceed to step 12 on a bad value.
  Do not close this terminal window before step 16. `$DEVSHA` lives only here, and step 15 refuses to run without it.
  (POSIX original in appendix)

- [ ] Step 11. `[DECIDE]` Decision gate on step 10. Write the decision down.
  - (a) `matches_planning_sha=False`: STOP and report. Someone pushed to a branch dormant for 17 months and that needs a human look.
  - (b) `ancestor_exit` is `0`: the commit is already reachable from master, so the archive tag is unnecessary and the disposition changes. STOP HERE. Record the reading, skip step 12, and do NOT delete the branch in this run. This run-book has no block for that path and deliberately does not add one: step 15 cannot serve it, because its third guard resolves `archive/dev-final`, the tag branch (b) just skipped creating, so step 15 would throw `TAG MISMATCH` on a branch that is genuinely safe to delete. Deleting a ref outside step 15's guarded invocation is an operator decision taken with a written record, not a run-book step, and no plan in this phase authorises one. SCAN-10 closes as recorded-and-not-executed on this path, which is a permitted outcome. Do NOT edit step 15's guards to fall through and do NOT hand-write an unguarded delete.
  - (c) `ancestor_exit` nonzero: this is the proof the commit is not reachable from master, which is the entire reason the tag is required. Proceed to step 12.

- [ ] Step 12. Create the lightweight tag on the remote. A lightweight tag is sufficient: it is a ref pointing at the commit, which is exactly what keeps the object alive.

```powershell
rtk proxy gh api -X POST repos/thezoid/ShopPyBot/git/refs -f ref=refs/tags/archive/dev-final -f "sha=$DEVSHA"
```

  you should see: 201 with ref `refs/tags/archive/dev-final` pointing at `$DEVSHA`.
  IRREVERSIBLE: creates a permanent remote ref on a public repository. It destroys nothing. The tag can be deleted with `rtk proxy gh api -X DELETE repos/thezoid/ShopPyBot/git/refs/tags/archive/dev-final`, but do NOT delete it after step 15; it is the only thing keeping the archived commit alive.

- [ ] Step 13. Verify the tag BEFORE touching the branch. Capture every output verbatim and timestamp it; these go into `38-SCAN-BASELINE.md` and the summary BEFORE the delete command. The `rtk proxy git tag -d` line is not housekeeping: without it, a leftover local ref from a partly completed earlier run would let check (c) pass with nothing on the remote.

```powershell
rtk proxy gh api "repos/thezoid/ShopPyBot/git/ref/tags/archive/dev-final" --jq ".object.type, .object.sha"
rtk proxy git tag -d archive/dev-final 2>$null
rtk git fetch origin "refs/tags/archive/dev-final:refs/tags/archive/dev-final" --no-tags
rtk proxy git rev-parse archive/dev-final
rtk proxy git cat-file -t $DEVSHA
```

  you should see, and what each one actually proves, stated honestly rather than counted:
  - (a) the API read returns `commit` and a sha equal to `$DEVSHA`. This is the WEAKEST check. It echoes back the sha step 12's POST supplied, so treat it as a write-succeeded receipt, not as independent evidence that the archive is real.
  - (b) the fetch succeeds, proving the tag ref exists on the remote and is reachable by a clean clone rather than being an API artifact. Meaningful only because the stale local tag was deleted on the line immediately before it.
  - (c) `rev-parse` prints `$DEVSHA`. This reads a LOCAL ref. It is a consistency check on (b), not a second opinion.
  - (d) `cat-file -t` prints `commit`, proving the object is present locally.
  Of these four, (b) is the only one that can fail because the archive is not real. (a) is a receipt and (c) and (d) are local consistency. The check that actually authorises the delete is (e), and it lives inside step 15's block, computed fresh there.
  if it fails: a failed (b) means the tag is not on the remote. STOP. The branch stays.

- [ ] Step 14. `[DECIDE]` Gate. Sign off in writing that (a) through (d) ran and are timestamped before the delete, and specifically that (b) succeeded. Do NOT record this as "all four passed" as though the four were equal evidence: (b) is the one that can fail because the archive is not real, (a) is a write receipt, and (c) and (d) are local consistency checks on it. The decisive check is (e), the delete gate, and step 15 computes it fresh inside the same block as the delete so it cannot be skipped by a call boundary. If (b) failed, STOP; the branch stays.

- [ ] Step 15. `[DECIDE]` Only now, delete the branch. Paste this WHOLE block as ONE invocation. `$ErrorActionPreference = "Stop"` covers CMDLET errors only. Measured on this box (pwsh 7.6.3) `$PSNativeCommandUseErrorActionPreference` reads `False` by default, so without the second line a failing `rtk`, `gh` or `git` call would NOT terminate this block; the second line turns native command failures into terminating errors too. The pair is close to the source plan's `set -euo pipefail`, not identical to it, and neither line is what makes the delete safe. The decisive gates below are enforced by explicit `throw` on the VALUES that came back, not by exit codes.

  The `& { ... }` wrapper is load-bearing and must not be removed. Without it every line of this block is a separate top-level statement, and a bare top-level `throw` only terminates the statement it is in. Measured on this box against the exact unwrapped guards: feeding the block one line at a time makes BOTH sha guards print their message and the `rtk proxy gh api -X DELETE` on the following line still runs, followed by the success line, with the block ending clean. That is the same "a guard cannot stop a command submitted after it across a call boundary" failure `38-06-PLAN.md`'s acceptance criteria call out, and it is why the POSIX original could use `exit 1` and this translation cannot. The `& { }` makes the guards and the delete ONE parsed unit: a shell fed line by line holds every line as incomplete input until the closing brace arrives and then runs the whole thing as one scope, where a `throw` aborts the entire script block and the delete is never reached; a caller that submits the lines independently gets a hard parse error on the opening brace instead of a partial execution. That protects a caller that STOPS at the parse error. One that logs it and keeps submitting the remaining lines still reaches the mutation, because lines 2 through N are individually valid. An automated driver must abort the whole sequence on the opening-brace parse error. Verified both ways with the delete stubbed out.

```powershell
& {
  $ErrorActionPreference = "Stop"
  $PSNativeCommandUseErrorActionPreference = $true
  if ($DEVSHA -notmatch "^[0-9a-f]{40}$") { throw "DEVSHA is not a 40-char sha ('$DEVSHA') - refusing to continue. Re-run step 10." }
  if ($DEVSHA -ne "65ef2b906ed4b6aca85ccf4e02e42deff80174e3") { throw "dev head moved since planning - stop for a human" }
  $tagged = rtk proxy git rev-parse archive/dev-final
  if ($tagged -ne $DEVSHA) { throw "TAG MISMATCH ($tagged vs $DEVSHA) - DO NOT DELETE" }
  if ((rtk proxy git cat-file -t $DEVSHA) -ne "commit") { throw "ARCHIVED OBJECT IS NOT A COMMIT - DO NOT DELETE" }
  $TAGSHA = (rtk proxy gh api "repos/thezoid/ShopPyBot/git/ref/tags/archive/dev-final" | ConvertFrom-Json).object.sha
  $LIVESHA = (rtk proxy gh api "repos/thezoid/ShopPyBot/branches/dev" | ConvertFrom-Json).commit.sha
  "e: tag_sha=$TAGSHA live_branch_sha=$LIVESHA"
  if ($TAGSHA -notmatch "^[0-9a-f]{40}$") { throw "tag sha is not a 40-char sha - DO NOT DELETE" }
  if ($TAGSHA -ne $LIVESHA) { throw "archive tag does not point at the live dev head - NOT DELETING" }
  rtk proxy gh api -X DELETE repos/thezoid/ShopPyBot/git/refs/heads/dev
  "deleted refs/heads/dev at $LIVESHA, archived as refs/tags/archive/dev-final"
}
```

  you should see: no `throw` output; the `e:` line printing two IDENTICAL 40-character shas; then 204 No Content and the confirmation line. The `e:` line is the last thing printed before the delete and it is what goes into the record immediately above the delete command.
  `$DEVSHA` is read from step 10's scope, which `& { }` can see. `$TAGSHA` and `$LIVESHA` are set INSIDE the wrapper and do not survive it; nothing after this step reads them. Step 16 uses `$DEVSHA` and its own `$POSTSHA`, so the scoping costs nothing.
  if pwsh shows a `>>` continuation prompt after the first line: that is correct behaviour, not a hang. Keep pasting. It is the shell holding the block until the closing brace, which is exactly the atomicity this wrapper buys.
  (e) is the only check taken after the tag exists that compares two independently fetched REMOTE values, which is why the delete is conditioned on it rather than on step 13's outputs.
  The planning-sha `throw` on the second guard line duplicates step 10's `matches_planning_sha` reading and step 11(a)'s decision on purpose. Step 11(a) is a human call and a human can tick past it; this line cannot be ticked past. Keep both: the step 10 measurement and the step 11(a) decision still happen, and this is the machine backstop for the case where a branch dormant for 17 months moved and nobody noticed.
  if it fails: any `throw` leaves the branch intact. That is the designed outcome, not an error to work around. Do not edit a guard to fall through, and do not re-run the block with a guard removed.
  IRREVERSIBLE: deletes remote branch `origin/dev`. It destroys the only branch ref pointing at commit `65ef2b906ed4b6aca85ccf4e02e42deff80174e3` ("fix sign in check", 2025-02-23), which is unreachable from master. Recovery exists ONLY through the `archive/dev-final` tag verified in step 13 and re-verified by gate (e) above. A deleted branch whose commit was never tagged is unrecoverable once GitHub garbage-collects the unreferenced object.
  (POSIX original in appendix)

- [ ] Step 16. Re-query both sides. The `refs/heads/dev` criterion is SCOPED to that one refspec on purpose: this phase deletes exactly one ref and an unscoped `ls-remote origin` lists every head on the remote. The last command is deliberately NOT scoped, but it is scoped to tags: `38-06-PLAN.md`'s acceptance asks to see `archive/dev-final` sitting alongside the pre-existing tags, and no scoped-to-one-refspec query can show that.

```powershell
& {
  $bs = (((rtk proxy gh api -i "repos/thezoid/ShopPyBot/branches/dev" 2>&1 | Out-String) -split '\r?\n')[0]).Trim()
  "branch_query_status=[$bs] (404 expected)"
  if ($bs -match '^HTTP/\S+\s+200\b') { throw "FATAL: branches/dev still resolves after the delete" }
  if ($bs -notmatch '^HTTP/\S+\s+404\b') { throw "FATAL: branches/dev answered neither 200 nor 404 ([$bs]); the delete is UNVERIFIED, do not record SCAN-10 as done" }
}
$POSTSHA = (rtk proxy gh api "repos/thezoid/ShopPyBot/git/ref/tags/archive/dev-final" | ConvertFrom-Json).object.sha
"post_delete_tag_sha=$POSTSHA matches_DEVSHA=" + ($POSTSHA -eq $DEVSHA)
rtk git fetch origin --prune
$devrefs = @(rtk proxy git ls-remote origin "refs/heads/dev")
"refs/heads/dev lines = " + $devrefs.Count
rtk proxy git ls-remote origin "refs/tags/archive/dev-final"
rtk proxy git ls-remote --tags origin
rtk proxy git rev-parse archive/dev-final
rtk proxy git cat-file -t $DEVSHA
```

  you should see: `branch_query_status=[HTTP/2.0 404 Not Found] (404 expected)` with no `FATAL:` after it; `matches_DEVSHA=True`; `refs/heads/dev lines = 0`; and exactly one line for the scoped tag ref. Paste the `branch_query_status=` line into the SCAN-10 record: `38-06-PLAN.md` Task 2's acceptance criterion asks for that line showing ` 404`, and states plainly that a bare nonzero exit code does not satisfy it. The earlier form of this step recorded `branch_query_exit=$LASTEXITCODE`, which cannot distinguish a deleted branch from a network failure or an expired token; all three exit nonzero and only one of them means the delete took.
  you should see from the last two commands: `rev-parse` prints `$DEVSHA` and `cat-file` prints `commit`, AFTER the delete. That is what `38-06-PLAN.md`'s criterion asks for: proof the object survived the branch deletion rather than proof it existed before it. The same two commands run at step 13 (c) and (d) and inside step 15's guards, but only before the delete, so they cannot satisfy this criterion on their own.
  you should see from the final command: four distinct tag names, `archive/dev-final`, `pre-v5-mainline`, `v2.0` and `v4.2`, which is the `38-06-PLAN.md` acceptance criterion. Expect SEVEN lines, not four. `pre-v5-mainline`, `v2.0` and `v4.2` are annotated tags, so each prints its tag-object line plus a peeled `^{}` line; `archive/dev-final` is lightweight (step 12 pointed a ref straight at the commit) so it prints one line only, and that line's sha must equal `$DEVSHA`.
  The `--tags` flag MUST come before `origin`. Written the other way round, `rtk proxy git ls-remote origin --tags`, git reads `--tags` as a ref PATTERN, matches nothing, prints nothing and exits `0`. Measured on this box. An empty listing with a clean exit reads as "the tags are gone", which is a confident wrong answer of exactly the kind this run-book keeps flagging.
  if it fails: a nonzero `refs/heads/dev lines` means the ref is still on the remote and the delete did not take. A `matches_DEVSHA=False` means the tag no longer resolves to the archived sha; stop and report before anything else in this block. Any of the three pre-existing tags missing from the final listing means something deleted a tag that was not in scope for this phase; stop and report.

- [ ] Step 17. `[SAY TO CLAUDE]`

  > Append a `## SCAN-10 RESOLVED` section to `38-SCAN-BASELINE.md` holding the archived SHA, the tag name, the ahead and behind counts, the `ancestor_exit` value, and the (a) through (e) verification outputs IN ORDER, with the step 15 delete command shown after them. The `e:` line must show `tag_sha` and `live_branch_sha` equal and must be the last output shown before the delete. State plainly which checks are load-bearing: (b) and (e) are the two that can fail if the archive is not real, (a) is a write receipt, (c) and (d) are local consistency. Note that the 4 workflows the branch carried (`app_linuxBuild.yml`, `app_macBuild.yml`, `app_windowsBuild.yml`, `codeql-analysis.yml`) are preserved inside the tagged tree and are no longer reachable from any branch, and that the Actions workflow list may keep showing stale disabled entries for a while, which is cosmetic and not a finding.

  you should see: a `## SCAN-10 RESOLVED` section with the archived sha, the tag, both counts, `ancestor_exit`, and outputs (a) through (e) with the delete command last.

- [ ] Step 18. Constraint, do nothing: do NOT edit `.github/workflows/ci.yml` or `gitleaks.yml` to drop `dev` from their branch filters. That non-change was decided and recorded in Block 3. `gitleaks.yml` triggers on branches `[master, dev]`; deleting `dev` does not affect the master half, which is the half that matters for a required check on master.

```powershell
rtk git status --porcelain .github/workflows/ci.yml .github/workflows/gitleaks.yml
```

  you should see: empty output.

- [ ] Step 19. Task 2 verify.

```powershell
(rtk proxy git ls-remote origin "refs/tags/archive/dev-final" | Select-String "refs/tags/archive/dev-final").Count
```

  you should see: `1`.

- [ ] Step 20. `[SAY TO CLAUDE]`

  > Read `38-SCAN-BASELINE.md` in full, from the opening baseline through every section appended by later plans, plus `38-04-SUMMARY.md` and `38-05-SUMMARY.md`.

- [ ] Step 21. All three scanners, measured now from the API. Do not copy numbers forward from earlier summaries.

```powershell
foreach ($ep in "code-scanning/alerts?state=open&per_page=100","dependabot/alerts?state=open&per_page=100","secret-scanning/alerts?state=open&per_page=100") {
  $resp   = (rtk proxy gh api -i "repos/thezoid/ShopPyBot/$ep" 2>&1 | Out-String)
  $status = (($resp -split '\r?\n')[0]).Trim()
  if ($status -match '^HTTP/\S+\s+200\b') {
    $n = @(($resp -replace '(?s)^.*?\r?\n\r?\n','') | ConvertFrom-Json).Count
    "SCANNER $ep status=[$status] open=$n"
  } else {
    "SCANNER $ep status=[$status] open=UNVERIFIABLE"
  }
}
```

  you should see: three `SCANNER ... status=[...] open=0` lines, each status containing ` 200`. On the DEFER branch the first count is expected to be `2` (#25 and #26, blocked on SCAN-06), which is itemised per step 22 and closes SCAN-02 as NOT MET rather than being dismissed away.
  Paste all three lines verbatim into `38-06-SUMMARY.md` and into the FINAL GATE evidence. `38-06-PLAN.md` Task 3 step 1 requires the status line BESIDE every count, in exactly this shape, and its acceptance criteria read it.
  if any line reads `open=UNVERIFIABLE`: record its status line verbatim and give every FINAL GATE row that depends on that scanner the state `UNVERIFIABLE (HTTP <status>)`. Never write `MET`, and never write an open count of `0`, for a queue that did not answer `200`. From the count alone an unreadable endpoint and an empty queue are the same value, which is precisely what this step exists to prevent: the earlier form of this step piped an unchecked body through `ConvertFrom-Json` and printed `0` for a 403.

- [ ] Step 22. `[DECIDE]` If any count is nonzero, list every remaining alert with its number, rule, and location, and state whether it is a genuine new finding or a leftover. Do NOT dismiss anything here to reach zero. A nonzero count with an honest explanation is a better outcome than a zero reached by dismissal. This phase's main output is dismissals, and a dismissal is indistinguishable from a fix in the alert count, which is exactly why this rule exists.

- [ ] Step 23. `[DECIDE]` If Dependabot alert 13 was handed forward by Block 4 as pending a graph refresh, re-query it now and apply the disposition that plan specified, including the `fix_started` fallback with the master SHA in the comment. Re-query again afterwards.

```powershell
rtk proxy gh api "repos/thezoid/ShopPyBot/dependabot/alerts/13" --jq ".state"
```

  you should see: before and after states recorded; the final state matches the disposition Block 4 Task 3 specified.
  IRREVERSIBLE: mutating an alert state destroys its current state and is not cleanly reversible; the state can be PATCHed back but the event stays in the audit trail. Only `fix_started` is honest here; `inaccurate`, `not_used` and `tolerable_risk` misrepresent what happened.

- [ ] Step 24. Repository and protection state.

```powershell
rtk proxy gh api "repos/thezoid/ShopPyBot" | ConvertFrom-Json | Select-Object -ExpandProperty security_and_analysis | ConvertTo-Json -Depth 5
$r = rtk proxy gh api "repos/thezoid/ShopPyBot/branches/master/protection/required_status_checks" | ConvertFrom-Json
$r.strict
($r.checks.context | Sort-Object) -join ", "
rtk proxy gh api "repos/thezoid/ShopPyBot/branches/master/protection/enforce_admins" --jq ".enabled"
rtk proxy gh api "repos/thezoid/ShopPyBot/actions/workflows?per_page=50" | ConvertFrom-Json | Select-Object -ExpandProperty workflows | ForEach-Object { "{0} | {1} | {2}" -f $_.name, $_.path, $_.state }
rtk proxy gh api "repos/thezoid/ShopPyBot/contents/.github/workflows?ref=master" --jq ".[].name"
rtk proxy git ls-remote origin | Select-String "refs/heads/"
```

  you should see: `strict` true with four contexts including `gitleaks`; `enforce_admins` false; the contents listing on master showing no `codeql-analysis.yml` on the SAFE-TO-DELETE branch only, on DEFER the file is expected to be present and SCAN-06's FINAL GATE row reads DEFERRED; and a head listing with no `refs/heads/dev`.
  DO NOT ACT ON THE HEAD LISTING. It is RECORDED, not acted on. This phase deletes exactly one ref, `refs/heads/dev`, in step 15. Every other head on the remote stays, including `gh-pages`, BOTH `release-please--branches--master--components--shoppybot*` heads, and the Dependabot head. Two of those carry open pull requests. Nothing in this run-book deletes anything from this listing.

- [ ] Step 25. SCAN-11 checked against master, not the working tree, and the file list DERIVED at run time rather than hardcoded. Both halves matter. A hardcoded three-file list silently skips whatever else is on the default branch: on the DEFER branch `codeql-analysis.yml` survives on master carrying three `uses:` lines, and a hardcoded loop would report SCAN-11 MET while tag-pinned actions sit on master. A `Test-Path` on `.github\workflows\` would not save it either, because that probes the LOCAL working tree, which is the exact thing this step exists not to trust: the branch you are standing on can carry a file master does not, or lack one master has. Enumerate master over the API first, then check what the enumeration returned. `38-06-PLAN.md` Task 3 step 5 carries the same requirement.

```powershell
$wf = @(rtk proxy gh api "repos/thezoid/ShopPyBot/contents/.github/workflows?ref=master" --jq '.[] | select(.type=="file") | .name')
"ref=master workflows enumerated ({0}): {1}" -f $wf.Count, ($wf -join " ")
foreach ($f in $wf) {
  "--- master:$f"
  rtk proxy gh api "repos/thezoid/ShopPyBot/contents/.github/workflows/${f}?ref=master" -H "Accept: application/vnd.github.raw" | Select-String "uses:"
}
```

  The braces in `${f}` are REQUIRED, not style. Measured on this box (pwsh 7.6.3): with `$f = "ci.yml"`, the string `"x/$f?ref=master"` interpolates to `x/=master`, because `?` is a legal character in a PowerShell variable name, so the parser reads the name as `f?ref`, finds it undefined, and substitutes empty. Both the filename and the `?ref` query string vanish silently, with no error. `"x/${f}?ref=master"` interpolates to `x/ci.yml?ref=master`. Unbraced, every iteration would request the same nonexistent path `contents/.github/workflows/=master`, 404 on all of them, and print no `uses:` line for any file, which reads as "every pin verified" against an expectation phrased only in terms of the lines that do print. This hazard applies wherever a `$var` is immediately followed by `?` in a double-quoted string; it does not apply to `$MSHA/check-runs?per_page=100` or `alerts/$n/instances?per_page=10`, where a `/` ends the name first.

  you should see: the enumeration line first, naming every workflow file present on master; then every printed `uses:` line showing a 40-character hex SHA and a trailing `# <tag>` comment, across every file in `$wf`. Expect three files on the SAFE-TO-DELETE branch and four on DEFER, but the enumeration is what decides, not that expectation.
  RECORD THE ENUMERATED FILE LIST alongside the results, per `38-06-PLAN.md` Task 3 step 5, so a later reader can see which files were in scope rather than having to trust that the loop covered them all.
  if any file yields an unpinned line: SCAN-11's FINAL GATE row reads NOT MET naming that file and line. Do NOT drop the file from the list to reach a pass; the point of deriving the list is that it cannot be trimmed to fit the answer.
  (POSIX original in appendix)

- [ ] Step 25.5. `[DECIDE]` Evidence the dismissal REASONS, not just the states. The FINAL GATE cannot otherwise catch a dismissal that carries a true-sounding but wrong explanation. All 26 dismissed alerts must resolve into exactly SEVEN groups: Block 5 steps 5 through 5.3 wrote four shape-specific strings `$c1` through `$c4`, and steps 16, 17 and 19 wrote three sub-case strings `$ca`, `$cb` and `$cc`.

```powershell
$dismissed = @(6..24) + @(25,26,27,28,29,31,32)
$rows = foreach ($n in $dismissed) {
  $a = rtk proxy gh api "repos/thezoid/ShopPyBot/code-scanning/alerts/$n" | ConvertFrom-Json
  $c = [string]$a.dismissed_comment
  [pscustomobject]@{
    number = $a.number
    state  = $a.state
    reason = $a.dismissed_reason
    len    = $c.Length
    mid    = $(if ($c.Length -ge 128) { $c.Substring(88, 40) } else { "TOO-SHORT" })
  }
}
$rows | ForEach-Object { "#{0} state={1} reason={2} len={3} mid={4}" -f $_.number, $_.state, $_.reason, $_.len, $_.mid }
$groups = @($rows | Group-Object len, mid)
"distinct groups = " + $groups.Count
$groups | ForEach-Object { "{0} -> {1}" -f $_.Name, ((($_.Group | ForEach-Object { $_.number }) | Sort-Object) -join ",") }
```

  you should see: `distinct groups = 7`, with memberships reading exactly `6,7,8` / `9,10,11,12,13,14,15` / `16,17,18,19` / `20,21,22,23,24` / `27,28,29` / `31,32` / `25,26`. Reason is `used in tests` for the first four groups and `false positive` for the last three.
  Expected pairs, measured directly from the seven strings as Block 5 steps 5 through 5.3, 16, 17 and 19 now write them, and identical to the table in `38-06-PLAN.md` Task 3 step 4a. `len=` is the character count of the comment and `mid=` is `dismissed_comment[88:128]`, the 40 characters starting at offset 88. The square brackets delimit the window and are not part of it:

  | String | Group | `len=` | `mid=` |
  |--------|-------|--------|--------|
  | `$c1` | `6`, `7`, `8` | 926 | `[is capsys.readouterr().out, the stdout c]` |
  | `$c2` | `9` through `15` | 1042 | `[ the plugin class attribute domain_patte]` |
  | `$c3` | `16` through `19` | 1049 | `[ domain_patterns on a plugin instance th]` |
  | `$c4` | `20` through `24` | 981 | `[is _read_security_md() at tests/test_sec]` |
  | `$ca` | `27`, `28`, `29` | 765 | `[-level list of 20 credential key NAMES, ]` |
  | `$cb` | `31`, `32` | 1143 | `[7. The flow reaches logger.writeLog thro]` |
  | `$cc` | `25`, `26` | 594 | `[at pre-Phase-37 line numbers (logger.py:]` |

  The `$c2`, `$c3` and `$ca` windows each begin with one character that is easy to lose when pasting: a leading space for `$c2` and `$c3`, a leading hyphen for `$ca` (it lands mid-word inside `module-level`). Preserve them. All seven `len=` values are distinct on their own, so length alone is currently sufficient to separate the groups; do not rely on that, check the pair.
  These expected values are computed from Block 5's current text. If a later edit rewords any of the seven strings, both columns move. Recompute them from Block 5 rather than treating the table as fixed, and if an observed pair disagrees with this table, verify against Block 5 before concluding an alert carries the wrong comment.
  Why offset 88: `$c1` and `$c4` share an opening sentence and so do `$c2` and `$c3`. `$c1` and `$c4` are byte-identical for their first 91 characters and `$c2` and `$c3` for their first 89, so no 60-character head can separate the four test-fixture groups. Offset 88 is the last character of the `$c2` and `$c3` common prefix and the 40-character window separates them from offset 89 onward, reading `the plugin class attribute` for `$c2` against `domain_patterns on a plugin instance` for `$c3`. The same holds for `$c1` against `$c4` from offset 91. Do not substitute a base64 prefix: the first 12 base64 characters cover only 9 input bytes, which collapses `$c1` through `$c4` onto `VGVzdCBmaXh0` and `$ca`, `$cb`, `$cc` onto `RmFsc2UgcG9z`, giving two groups instead of seven and no signal. The grouping evidence is the `len=` plus `mid=` pair; it must be identical within each group and different across all seven.
  if it fails: fewer than seven groups is a FAILURE, not a pass. If any alert carries a neighbouring group's string, the dismissal is wrong even though its state is correct: re-PATCH that alert with the string its own group was assigned in Block 5 and record the correction. NEVER re-PATCH toward a shared string, and in particular do NOT collapse `6` through `24` onto one comment. That string was split into four deliberately, because one string covering all 19 is false at 16 of them, and re-merging them reintroduces exactly the defect this phase removed.
  DEFER BRANCH: `#25` and `#26` are not dismissed there, so the expected shape is six comment groups plus a `len=0 mid=TOO-SHORT` pair carrying `state=open` for those two numbers. Record that; do not dismiss them here to reach seven.
  (POSIX original in appendix)

- [ ] Step 25.6. MEASURE pull request #23 now. Its state is NOT dictated by this run-book and must not be copied forward from any earlier document. Paste the WHOLE fenced block as ONE invocation so the status guard sits with the values it guards. This is `38-06-PLAN.md` Task 3 step 3a.

```powershell
& {
  $measured = (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd")
  $st = (((rtk proxy gh api -i "repos/thezoid/ShopPyBot/pulls/23" 2>&1 | Out-String) -split '\r?\n')[0]).Trim()
  "pr23 status=[$st] measured=$measured"
  if ($st -notmatch '^HTTP/\S+\s+200\b') { throw "pr23 UNVERIFIABLE: pulls/23 did not return 200. Record the status line and make no mergeability claim." }
  $p = rtk proxy gh api "repos/thezoid/ShopPyBot/pulls/23" | ConvertFrom-Json
  "pr23 head={0} mergeable={1} mergeable_state={2}" -f $p.head.sha, $p.mergeable, $p.mergeable_state
  rtk proxy gh api "repos/thezoid/ShopPyBot/commits/$($p.head.sha)/check-runs?per_page=100" |
    ConvertFrom-Json |
    Select-Object -ExpandProperty check_runs |
    ForEach-Object { "pr23 check: {0} app={1} conclusion={2}" -f $_.name, $_.app.slug, $_.conclusion }
  "pr23 measured=$measured"
}
```

  you should see: `pr23 status=[...]` with ` 200`, then `pr23 head=... mergeable=... mergeable_state=...`, then one `pr23 check:` line per check run at that head, then `pr23 measured=<date>`. Paste all of them verbatim into `38-06-SUMMARY.md` and into the FINAL GATE record; step 26 writes the #23 paragraph from THIS output and from nowhere else.
  `mergeable` is computed asynchronously and a first read can return `null`. A `null` is not `false`: re-run the block once, and if it is still `null` record it as `null` with its date rather than inferring a verdict from it.
  if it fails: a thrown `pr23 UNVERIFIABLE` means no mergeability claim may be written at all. Record the status line and say so in the FINAL GATE record.

- [ ] Step 26. `[DECIDE]` `[SAY TO CLAUDE]`

  > Append a `## FINAL GATE` section to `38-SCAN-BASELINE.md` with one row per requirement, SCAN-01 through SCAN-11, columns Req, Claim, Evidence, State. Fill State with MET, DEFERRED, NOT MET, or `UNVERIFIABLE (HTTP <status>)` plus the reason. Be willing to write NOT MET; this document is what the phase verifier reads. `UNVERIFIABLE (HTTP <status>)` is mandatory, not a courtesy, for any row whose evidence command did not return 200: on a 403 or a 404 the body still parses and a count still comes back, so a failed read and a clean result are indistinguishable from the value alone. No row may read MET on the strength of a non-200, and no non-200 may be written down as an open count of 0. SCAN-04's row must cite the step 25.5 seven-group reason audit, not just the alert states. SCAN-08's row must read DEFERRED and cite the four files that record it: the REQUIREMENTS.md row, the STATE.md section, the ROADMAP.md criterion-2 annotation, and the stored apply commands in this baseline. On the DEFER branch, SCAN-06's row reads DEFERRED and SCAN-02's row reads NOT MET with #25 and #26 named.
  > Record under the table the state of pull request #23 (release-please, head branch `release-please--branches--master--components--shoppybot`), keeping the durable MECHANISM and the contingent CONSEQUENCE as two separate statements. They have different evidence and different shelf lives, and collapsing them is how a stale conclusion gets merged to master. The MECHANISM: #23's branch is pushed by the `github-actions` app using `GITHUB_TOKEN`, and GitHub does not trigger `pull_request` workflow runs on a head pushed with that token. That is a property of how the branch is pushed, not of this phase, and it does not expire on its own. The CONSEQUENCE: write it from step 25.6's output and from nowhere else, recording verbatim the head sha, the `mergeable` value, the `mergeable_state` value, the `pr23 check:` list, and the UTC date all of them were read. Do NOT write "already permanently unmergeable": measured 2026-09-06, `pulls/23` read `mergeable: true, mergeable_state: clean`, so that phrasing was false at that reading and `38-06-PLAN.md` Task 3 now makes its absence an acceptance criterion. If step 25.6 read `clean`, record `clean` with its date; if it read `blocked`, record `blocked` with its date and name the contexts that blocked it. Record all of this so a later reader does not read #23 as damage caused by Phase 38, and so the gitleaks requirement is not reverted on its account. The correct fix for #23 is a release-please token change, out of scope here.

  you should see: exactly one `## FINAL GATE` heading, a table with a row per SCAN-01 through SCAN-11 each carrying MET, DEFERRED, NOT MET, or `UNVERIFIABLE (HTTP <status>)`, and the #23 paragraph beneath it carrying the head sha, the measured mergeability with its date, and the actual check-context list from step 25.6.
  you should NOT see: the string `already permanently unmergeable` anywhere in the record. `38-06-PLAN.md` Task 3 forbids it by name, so a record containing it fails that plan's own acceptance criterion.

<!-- POSTURE-PENDING: how many of master's required contexts #23 cannot satisfy, and whether SCAN-07 adds a further unsatisfiable context to it, cannot be derived while branch protection reads protected:false and required_status_checks is unreadable; re-derive both the count and any "SCAN-07 adds a further unsatisfiable context" sentence from a live required_status_checks read once the operator settles the repository posture. The mechanism sentence and step 25.6's measured values are the posture-independent halves and stand either way. -->

- [ ] Step 26.5. `[SAY TO CLAUDE]` Author the closing summary NOW, before the stage at step 27, so it lands with the docs PR instead of ending its life as an uncommitted file in a dirty tree.

  > Create `.planning/phases/38-scanning-to-zero/38-06-SUMMARY.md`. It must include the before and after `checks` arrays from steps 4 and 6; the (a) through (e) tag verification outputs from steps 13 and 15 in order, with the step 15 delete command shown after them and the `e:` line immediately above it; the `branch_query_status=[...] (404 expected)` line from step 16; the step 25.5 reason-audit output with its seven group memberships; the three `SCANNER <endpoint> status=[...] open=<count>` lines from step 21, each count beside its own status line and never separated from it; step 25.6's four `pr23` evidence lines verbatim; and the full `## FINAL GATE` table from step 26. Leave a clearly marked `## Post-merge addendum` heading at the end, empty for now; step 36 fills it in.

  you should see: the file exists with every section except the addendum populated.

- [ ] Step 27. Stage the phase documentation. Remove the stale paused-run handoff FIRST; a bare `rtk git add` on the phase directory would commit it to master for the first time.

```powershell
rtk git rm -f --ignore-unmatch .planning/phases/38-scanning-to-zero/.continue-here.md
if (Test-Path .planning\phases\38-scanning-to-zero\.continue-here.md) { Remove-Item -Force .planning\phases\38-scanning-to-zero\.continue-here.md }
rtk git status --short .planning/phases/38-scanning-to-zero/
rtk git add .planning/phases/38-scanning-to-zero/
rtk git status --porcelain
```

  you should see: the `--short` listing containing NO `.continue-here.md` entry at all, neither an untracked `??` line nor a staged addition; a staged deletion `D` appears only in the already-committed case. Then only `.planning/` paths staged, including `38-06-SUMMARY.md`. Waves 4, 5 and 6 wrote summaries onto `phase-38-docs`, which has no source changes.
  Why both commands: `.continue-here.md` carries `status: paused` and `task: 0` from the interrupted run that created these plans. Block 1 step 2's `rtk git reset` kept it out of every commit on the working branch, so it is not on master and is not tracked on `phase-38-docs`: it is sitting UNTRACKED in the working tree where `checkout -B` left it, which is exactly why it is dangerous here. `--ignore-unmatch` makes `git rm` a no-op on a path it does not track; a bare `rtk git rm -f` errors with `did not match any files` and aborts the step. The `Remove-Item` is what actually clears the untracked file out of the tree.
  IRREVERSIBLE (local only): deletes `.continue-here.md` from the working tree. It destroys a stale paused-run handoff superseded by this run-book and by the phase summaries. If it turned out to be tracked, `rtk proxy git checkout HEAD -- .planning/phases/38-scanning-to-zero/.continue-here.md` restores it before the commit.
  (POSIX original in appendix)

- [ ] Step 28. Commit. Approval point per project policy.

```powershell
rtk git commit -m "docs(38): record phase 38 scanner closing state and per-wave summaries"
```

  you should see: a commit on `phase-38-docs` touching only `.planning/` paths.

- [ ] Step 29. Push.

```powershell
rtk git push -u origin phase-38-docs
```

  you should see: `origin/phase-38-docs` updated and tracking set.

- [ ] Step 30. Open the documentation PR. Author the body file first.

  `[SAY TO CLAUDE]`

  > Write the docs PR body to `$env:TEMP\pr-38-docs-body.md`, summarising the FINAL GATE table state per requirement.

```powershell
rtk proxy gh pr create --repo thezoid/ShopPyBot --base master --head phase-38-docs --title "docs(38): scanning to zero, phase records" --body-file "$env:TEMP\pr-38-docs-body.md"
```

  you should see: the PR created against master. Record it into a variable now: `$DOCSPR = "<PR_NUMBER>"`. Record `DOCS_PR = ______` on paper too. Steps 31 and 33 both need it, and `$DOCSPR` lives only in this terminal window.
  This pull request is also the first live exercise of the gitleaks requirement added in step 5.

- [ ] Step 31. `[DECIDE]` STAY AT THE KEYBOARD. Do not leave this step. From step 5 until step 33 merges, master carries a required `gitleaks` context that has never been exercised on a PR; if it does not report, every merge to master is blocked, including hotfixes. Watch until `gitleaks` reaches a conclusion, then continue or execute step 32.

```powershell
rtk proxy gh pr checks $DOCSPR --repo thezoid/ShopPyBot --watch --interval 30
```

  you should see: all required checks reporting, with `gitleaks` at conclusion `success`.

- [ ] Step 32. `[DECIDE]` Failure branch: if step 31 hangs waiting for a `gitleaks` context that never reports, step 2's gate was wrong. Revert the required-checks change IMMEDIATELY, before doing anything else, using the `rsc-revert.json` built in step 4. Do not hand-author it now.

```powershell
Get-Content "$env:TEMP\rsc-revert.json"
rtk proxy gh api -X PATCH repos/thezoid/ShopPyBot/branches/master/protection/required_status_checks --input "$env:TEMP\rsc-revert.json"
```

  you should see: `required_status_checks.checks` back to the exact three-entry array from step 4, and the hang reported rather than worked around.
  IRREVERSIBLE: changing branch protection back is still a protection mutation. It destroys the four-entry configuration added in step 5 and restores the three-entry one; both states are re-creatable from the saved JSON files.

- [ ] Step 33. `[DECIDE]` Merge the documentation PR.

```powershell
rtk proxy gh pr merge $DOCSPR --repo thezoid/ShopPyBot --merge
```

  you should see: state MERGED, and its check list including `gitleaks` at conclusion `success`, proving the new requirement is satisfiable. Master's merge path is unlocked from here.
  IRREVERSIBLE: merges to master. Nothing is destroyed; recovery is a revert commit through another PR.

- [ ] Step 34. Task 3 verify: closing code-scanning count, with its status line beside it.

```powershell
& {
  $resp   = (rtk proxy gh api -i "repos/thezoid/ShopPyBot/code-scanning/alerts?state=open&per_page=100" 2>&1 | Out-String)
  $status = (($resp -split '\r?\n')[0]).Trim()
  if ($status -notmatch '^HTTP/\S+\s+200\b') { "SCANNER code-scanning/alerts status=[$status] open=UNVERIFIABLE"; return }
  "SCANNER code-scanning/alerts status=[$status] open=$(@(($resp -replace '(?s)^.*?\r?\n\r?\n','') | ConvertFrom-Json).Count)"
}
```

  you should see: `SCANNER code-scanning/alerts status=[... 200 ...] open=0`, or a nonzero count itemised per step 22.
  if it prints `open=UNVERIFIABLE`: record the status line verbatim and carry it into the addendum as UNVERIFIABLE. Do not write `0`; the count and the status line travel together here for the same reason they do at step 21.

- [ ] Step 35. Final post-merge assertion that SCAN-08 stayed deferred through the whole phase.

```powershell
rtk proxy gh api "repos/thezoid/ShopPyBot/branches/master/protection/enforce_admins" --jq ".enabled"
```

  you should see: `false`.

- [ ] Step 36. `[SAY TO CLAUDE]` Fill in the addendum left open at step 26.5.

  > Fill the `## Post-merge addendum` section of `.planning/phases/38-scanning-to-zero/38-06-SUMMARY.md` with the docs PR number and merge state from step 33, the step 34 closing code-scanning count, and the step 35 `enforce_admins` reading. Do not restate anything already recorded above it.

  you should see: the addendum populated and no other section rewritten.

- [ ] Step 37. Commit the closing summary on the branch and STOP. The phase's own closing record must not end its life uncommitted, and it must not reach master through an unauthorised second pull request.

```powershell
rtk git add .planning/phases/38-scanning-to-zero/38-06-SUMMARY.md
rtk git commit -m "docs(38-06): record phase 38 closing summary"
rtk git push
```

  you should see: the commit lands on `phase-38-docs`, the push updates `origin/phase-38-docs`, and `rtk git status --porcelain` afterwards shows no output other than an untracked `.continue-here.md` line if you wrote a new pause handoff. That single line is expected and must never be committed.
  This step does NOT open a pull request and does NOT merge anything. Step 33 merged the one documentation pull request this phase authorises, and the revert path was declared finished there; no plan in Phase 38 authorises a second merge to master, so opening and merging one here would be an unauthorised change to the default branch taken after the phase's own closing gate. The addendum commit rests on `phase-38-docs`.
  `[DECIDE]` Landing the addendum on master is an OPERATOR decision, taken separately and recorded before it is taken. If the operator decides to take it, it is a normal follow-up pull request opened outside this run-book, under whatever review the repository requires at that time; it is not a step of Phase 38.

- [ ] Post-block: check the pending-push count. If more than 10 commits are stacked locally, push before you lose them.

```powershell
rtk git rev-list --count origin/master..HEAD
```

### BACKGROUND / ANYTIME

None of these block Phase 38 execution. Do them in any spare moment.

- [ ] `[BROWSER]` Enable Actions PR creation. release-please currently fails at PR creation without it. This is a security-posture setting, deliberately left to you.
  URL: `https://github.com/thezoid/ShopPyBot/settings/actions`
  Section: "Workflow permissions". Tick the checkbox labelled **Allow GitHub Actions to create and approve pull requests**, then click **Save**.
  you should see: the checkbox stays ticked after the page reloads.

- [ ] `[BROWSER]` Check the Actions allowlist while you are on that page. `gitleaks.yml` and `release-please.yml` both carry header comments saying their actions must be allowlisted.
  Same URL, section "Actions permissions". Confirm `gitleaks/gitleaks-action` and `googleapis/release-please-action` are covered by the allowed-actions patterns.
  Note: SHA pins still match an owner/repo allowlist pattern, so Block 3's pinning should not change allowlist behaviour. Block 4's PR is where that gets proven.

- [ ] `[DECIDE]` PR #23 (`chore(master): release shoppybot 2.1.0`) cannot merge. GitHub suppresses pull_request-triggered checks on PRs opened by `GITHUB_TOKEN`, so `test (ubuntu-latest)` and `test (windows-latest)` never report and branch protection can never be satisfied. The fix is a GitHub App token.
  NOT a PAT, ever. This is a public repo with `enforce_admins: false`, so an owner-identity token bypasses branch protection entirely. No repo secrets exist today; do not create any as a workaround.
  This is deferred alongside SCAN-08 and for a related reason: enabling `enforce_admins` is what makes app-token automation safe, so the two land together at milestone close after Phase 50.

```powershell
rtk gh pr view 23 --repo thezoid/ShopPyBot --json state,title,mergeStateStatus
```

- [ ] `[DECIDE]` PR #25 (Dependabot pip group) must be SPLIT, never merged whole. Its `requirements.txt` half is 8 safe upgrades. Its `pyproject.toml` half bumps FastAPI 0.115.8 to 0.141.1, which unregisters `/api/events` and kills the dashboard SSE channel, proven by that PR's own CI failing on both runners. Take the requirements half onto a fresh branch; leave the FastAPI bump for a dedicated phase.

```powershell
rtk gh pr view 25 --repo thezoid/ShopPyBot --json state,title,files
```

- [ ] RECORD ONLY, do not act on it during this phase: `.planning/STATE.md` says master is at `a99b67d` with status completed. Reality at phase start: `origin/master` was `bd70601`, branch `chore/v4.0-milestone-close` was 4 commits ahead (planning docs only) and 1 behind master. That drift is real and worth fixing, but no plan in Phase 38 authorises a STATE.md rewrite, so it is NOT a background task and specifically NOT an "anytime" one.
  Why the timing matters: Block 3 step 37 stages `.planning/STATE.md` by name, so any unrelated edit sitting in the working tree when that step runs is swept into the `ci(38-03)` commit and lands on master through Block 4's merge, inside a commit whose message says it scoped ci.yml permissions. The only STATE.md change this phase authorises is 38-03 Task 3's `### Deferred to Milestone Close (v5.0)` section, which Block 3 step 29 makes deliberately and step 34 verifies.
  If the operator wants the drift corrected, it is a separate change made after Phase 38 closes, on its own branch, in its own commit.

- [ ] Harness note, for whoever drives execution: the auto-mode classifier denies `gsd-executor` dispatch for plans that merge PRs. The workaround proven across 9 merges is to run those steps inline in the main thread. The orchestrator must then update STATE.md itself. That applies to Block 4 steps 5 through 11 and Block 6 steps 30 through 33.

### IF YOU HAVE TO STOP

Run this before you close the window. It captures exactly where you are so the next session picks up without re-deriving anything.

```powershell
rtk git status --porcelain
rtk proxy git rev-parse --abbrev-ref HEAD
rtk proxy git rev-parse HEAD
rtk git rev-list --count origin/master..HEAD
rtk proxy git log --oneline origin/master..HEAD
@(rtk proxy gh api "repos/thezoid/ShopPyBot/code-scanning/alerts?state=open&per_page=100" | ConvertFrom-Json).Count
@(rtk proxy gh api "repos/thezoid/ShopPyBot/dependabot/alerts?state=open&per_page=100" | ConvertFrom-Json).Count
@(rtk proxy gh api "repos/thezoid/ShopPyBot/secret-scanning/alerts?state=open&per_page=100" | ConvertFrom-Json).Count
rtk proxy git ls-remote origin "refs/heads/dev" "refs/tags/archive/dev-final"
rtk gain
```

Then `[SAY TO CLAUDE]`:

> Write a pause handoff into `.planning/phases/38-scanning-to-zero/.continue-here.md`. Record: the last completed run-book block and step number, the plan-checker verdict and when it was issued, the VERDICT-SCAN-06 and VERDICT-SCAN-01 values, whether the `origin/dev` archive tag has been pushed and verified, whether the branch has been deleted, which alert numbers have already been dismissed and with which of the seven reason strings, which of Block 5's two secret-scanning PATCHes have landed (non-provider patterns only, or both) and whether the step 27 poll reached its stop condition, whether master's required-checks list currently carries the unproven `gitleaks` context (Block 6 steps 5 through 33), and the current three closing alert counts from the commands above. State plainly what the very next step is and what gates it.

Uncommitted work: commit it on the current phase branch before stopping. Do not leave the tree dirty, with one deliberate exception: `?? .planning/phases/38-scanning-to-zero/.continue-here.md` is expected from Block 1 step 2 until Block 6 step 27 removes it, and the pause handoff below writes to that same untracked file. It stays untracked and must never be committed; never clear it by `rtk git add`-ing the phase directory, which would land the paused-run handoff on master. If the `origin/dev` tag is pushed but the branch is not yet deleted, say so explicitly in the handoff. That is a safe resting state; the reverse never is. If you are stopping between Block 6 step 5 and step 33, say so loudly: master cannot be merged to until step 33 lands or step 32 reverts.

### Appendix: POSIX originals, for provenance only, DO NOT RUN

These are the commands as the source plans wrote them, kept so a reader can trace each PowerShell rewrite back to its origin. `grep`, `base64 -d`, `test -e` and POSIX `for` loops do not exist in this environment. Nothing in this appendix is executable here.

1. Block 1 step 6, alert inventory:
   `gh api "..." --jq '[.[] | {n: .number, rule: .rule.id, sev: .rule.security_severity_level, path: .most_recent_instance.location.path, line: .most_recent_instance.location.start_line}] | sort_by(.rule,.path,.line) | .[] | "\(.n) \(.rule) \(.sev) \(.path):\(.line)"'`

2. Block 1 step 25, PKCS#7 reachability:
   `grep -rn "pkcs7\|PKCS7\|EnvelopedData\|smime\|SMIME\|load_pem_pkcs7\|load_der_pkcs7" --include=*.py core plugins notifications web main.py logger.py models.py utils.py config.py` (record the grep exit status; `rg` and `grep -oP` are unavailable on this box)

3. Block 2 step 15, substring URL test:
   `grep -n "bestbuy.com\" in \|amazon.com\" in " main.py core/cli/run.py`

4. Block 2 step 22, probe venv:
   `python -m venv "$TEMP/cryptoprobe"`

5. Block 2 step 46, plan verification 2 of 5:
   `grep -rn "\"bestbuy.com\" in \|\"amazon.com\" in " main.py core/cli/run.py`

6. Block 3 step 7, one top-level permissions key:
   `grep -v "^ *#" .github/workflows/ci.yml | grep -c "^permissions:"`

7. Block 3 step 12, branch A acceptance:
   `test -e .github/workflows/codeql-analysis.yml`

8. Block 3 step 22, pinned uses count:
   `grep -rn "uses:" .github/workflows/ | grep -c "@[0-9a-f]\{40\} # "`

9. Block 4 step 14, cryptography pin on master:
   `gh api "...?ref=master" --jq '.content' | base64 -d | grep -n "^cryptography=="`

10. Block 5 steps 3 and 5 through 5.3, the 19 test-file dismissals in four shape groups. The source plan derives the groups live with `awk` over an `ALERTS` variable, then runs four loops:
    `ALERTS=$(gh api ".../code-scanning/alerts?state=open&per_page=100" --jq '[.[] | select(.rule.id=="py/incomplete-url-substring-sanitization") | select(.most_recent_instance.location.path | startswith("tests/")) | "\(.number) \(.most_recent_instance.location.path):\(.most_recent_instance.location.start_line)"] | .[]')`
    then `G1=$(printf '%s\n' "$ALERTS" | awk '$2 ~ /^tests\/test_cli_/ {print $1}')` and the same for `test_plugin_`, `test_registry\.py`, `test_security_md\.py`; then `for N in $G1; do gh api -X PATCH ".../alerts/$N" -f state=dismissed -f dismissed_reason="used in tests" -f dismissed_comment="$C1" --jq '"#\(.number) -> \(.state) / \(.dismissed_reason)"'; done`, once per group with `$C2`, `$C3`, `$C4`. `awk` and `printf '%s\n'` do not exist here; the PowerShell rewrite filters the parsed objects instead.

11. Block 5 step 10, suppression scan:
    `grep -rn "lgtm\|nosec\|paths-ignore" tests/ .github/`

12. Block 5 steps 25, 27 and 27.5, secret scanning enablement as TWO ordered requests:
    PATCH 1: `echo '{"security_and_analysis":{"secret_scanning_non_provider_patterns":{"status":"enabled"}}}' | gh api -X PATCH repos/thezoid/ShopPyBot --input -`
    enumeration between them, polled: `gh api ".../secret-scanning/alerts?state=open&per_page=100" --jq '[.[] | "#\(.number) \(.secret_type_display_name) \(.validity) \(.locations_url)"] | .[]'`
    PATCH 2: `echo '{"security_and_analysis":{"secret_scanning_validity_checks":{"status":"enabled"}}}' | gh api -X PATCH repos/thezoid/ShopPyBot --input -`
    The single bundled body an earlier draft of this run-book carried is NOT the source plan's command and must not be used; the ordering is the point.

13. Block 6 step 5, required status checks PATCH:
    `echo '{"strict":true,"checks":[...]}' | gh api -X PATCH repos/thezoid/ShopPyBot/branches/master/protection/required_status_checks --input -`

14. Block 6 step 8, Task 1 verify:
    `gh api "..." --jq "[.checks[].context] | sort | join(\",\")"`

15. Block 6 steps 10 through 16, dev branch re-measure, tag, verify, delete gate, delete and re-query. The source plan runs all of it as ONE `sh` invocation opening `set -euo pipefail`, because its execution harness carries no shell state between separate calls and an empty `DEVSHA` would make `git rev-list --count "origin/master..$DEVSHA"` degrade to `origin/master..HEAD` and exit `0`, reading as a passing safety check while measuring nothing. Key lines, in order:
    `DEVSHA=$(gh api repos/thezoid/ShopPyBot/branches/dev --jq .commit.sha)`; `[ ${#DEVSHA} -eq 40 ] || { echo "FATAL: DEVSHA is not a 40-char sha, refusing to continue"; exit 1; }`; the planning-SHA equality guard; `AHEAD=$(git rev-list --count "origin/master..$DEVSHA")`; `git merge-base --is-ancestor "$DEVSHA" origin/master || ANCESTOR_EXIT=$?`; `gh api -X POST repos/thezoid/ShopPyBot/git/refs -f ref=refs/tags/archive/dev-final -f sha="$DEVSHA"`; `git tag -d archive/dev-final 2>/dev/null || true`; the tag fetch; `LOCALTAG=$(git rev-parse archive/dev-final)`; `OBJTYPE=$(git cat-file -t "$DEVSHA")`; then the delete gate `TAGSHA=$(gh api .../git/ref/tags/archive/dev-final --jq .object.sha)` and `LIVESHA=$(gh api .../branches/dev --jq .commit.sha)` with `[ "$TAGSHA" = "$LIVESHA" ] || { echo "FATAL: archive tag does not point at the live dev head, NOT deleting"; exit 1; }` immediately before `gh api -X DELETE repos/thezoid/ShopPyBot/git/refs/heads/dev`; and afterwards `[ -z "$(git ls-remote origin "refs/heads/dev")" ] || { echo "FATAL: refs/heads/dev is still on the remote"; exit 1; }`. Full text in `38-06-PLAN.md` Task 2. `set -euo pipefail`, `${#VAR}`, `[ ... ]` and `$(...)` do not exist in PowerShell; step 15's `$ErrorActionPreference = "Stop"` plus `throw` guards inside one pasted block is the equivalent, and it keeps the guards and the delete in the same invocation for the same reason.

16. Block 6 step 25, SCAN-11 against master. The source plan derives the file list at run time from the
    contents API rather than naming files, and wraps the whole thing in a `REF` loop so another ref can
    be added without editing the inner loop:
    `for REF in master; do WFS=$(gh api "repos/thezoid/ShopPyBot/contents/.github/workflows?ref=$REF" --jq '.[] | select(.type=="file") | .name'); echo "ref=$REF workflows: $(echo $WFS | tr '\n' ' ')"; for F in $WFS; do echo "--- $REF:$F"; gh api "repos/thezoid/ShopPyBot/contents/.github/workflows/$F?ref=$REF" --jq '.content' | base64 -d | grep -n "uses:"; done; done`
    Full text in `38-06-PLAN.md` Task 3 step 5, which also requires the enumerated file list be recorded
    alongside the results. `tr`, `base64 -d` and `grep` do not exist here; the PowerShell rewrite keeps
    the same enumerate-then-check order, uses the raw-content Accept header instead of decoding
    `.content`, and drops the `REF` loop because master is the only ref in scope for this phase. An
    earlier draft of this run-book hardcoded `for F in ci.yml gitleaks.yml release-please.yml` and then
    added `codeql-analysis.yml` from a local `Test-Path`; that is not the source plan's command and must
    not be used, because a local probe cannot tell you what is on master.

17. Block 6 step 25.5, the seven-group dismissal-reason audit:
    `for N in 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 31 32; do gh api ".../code-scanning/alerts/$N" --jq '"#\(.number) reason=\(.dismissed_reason) len=\(.dismissed_comment | length) mid=\(.dismissed_comment[88:128]) head=\(.dismissed_comment[0:60])"'; done`
    `head=` is for reading, not for grouping; the grouping evidence is the `len=` plus `mid=` pair.

18. Block 6 step 27, stale paused-run handoff removal:
    `git rm -f --ignore-unmatch .planning/phases/38-scanning-to-zero/.continue-here.md` then `rm -f .planning/phases/38-scanning-to-zero/.continue-here.md` then `git status --short .planning/phases/38-scanning-to-zero/`
