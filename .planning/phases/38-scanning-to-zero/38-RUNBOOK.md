# PHASE 38 OPERATOR INDEX: "Scanning to Zero"

Restructured 2026-09-09. This file used to be a 2,710-line PowerShell translation of the same
procedure the six plans carry in POSIX: 185 PowerShell fences, 24 `& { ... }` guard blocks, 59
`throw`s. Every fix had to land twice, in two languages, and the execution gate kept catching the
half that did not. Runs 1 through 5 all failed on that seam.

It is now an INDEX. The six plans are the single implementation. This file sequences them, tells you
what a human has to look at or decide, and points at the plan and task that holds each command. It
does not restate a single command that lives in a plan. If you find one restated here, that is a
defect: delete it and point at the plan instead.

Read this whole file before Wave 1. It is short on purpose.

## 1. READ THIS FIRST

### The one gate

The six Phase 38 plans are UNVERIFIED. Nothing runs until the plan checker returns a written PASS.
That gate is Checkpoint 0 in section 4. It is the first thing you do, every time, including after a
`/clear`.

### The shell is Git Bash

Everything in the plans is POSIX. Confirm your shell before Checkpoint 0:

```sh
echo "$BASH_VERSION"; uname -s
```

  you should see: a bash version string and `MINGW64_NT-...`. If you get an error or a `pwsh` banner,
  you are in the wrong shell. The previous edition of this document told you to confirm
  `$PSVersionTable.PSVersion` and to run everything in pwsh 7. That instruction is withdrawn: the
  procedure is POSIX and you run Git Bash.

When you paste a multi-line fenced block, Git Bash shows a `>` continuation prompt until the block is
complete. That is not a hang. Do not press Ctrl-C; finish the paste.

### Anti-patterns, all of them measured on this box

These are hard-won. Several were discovered by an actual wrong answer, not by reasoning.

- **`rtk git status --porcelain` prints the 2-byte string `ok` on a clean tree.** Every emptiness test
  against it is inverted and can never pass. On a DIRTY tree it returns the porcelain lines with the
  trailing newline stripped, so do not line-count it either. Use `rtk proxy git status --porcelain`
  wherever EMPTINESS is the assertion. Sites expecting non-empty output are fine as they are.
  CORRECTION: the previous edition's conventions paragraph claimed this command is "verified
  byte-identical to raw and is safe". That claim is FALSE and was re-measured this pass.
- **`rtk git log` drops ALL merge commits and caps output at 50.** For a range whose commits are all
  merges it returns EMPTY, which reads as "the branches are in sync". That is a confident, plausible,
  wrong answer and it is worse than an error. Use `rtk proxy git log` for every range query, audit,
  release note, commit disposition, or anything you will assert as fact. `rtk git rev-list --count`,
  `rtk git merge-base --is-ancestor` and `rtk git log --merges` are verified accurate.
- **`rtk git diff` reformats output** (stat header, a literal `--- Changes ---` separator, two-space
  indented hunk lines), so `grep -c "^[+-][^+-]"` returns 0 regardless of the diff. Use
  `rtk proxy git diff` wherever the output feeds an acceptance criterion.
- **The `rtk gh` filter drops the HTTP status line.** Every plan block that asserts a status line uses
  `rtk proxy gh api -i`. Do not "simplify" one back to `rtk gh`.
- **Tests are `.venv/Scripts/python.exe -m pytest`, never `rtk pytest`.** The full suite also needs
  `pip install -e .[web]` and `pip install httpx`; httpx is undeclared in the repo. The plans install
  both conditionally, gated on `pytest --collect-only`.
- **`gitleaks` is NOT installed locally. Never run it on this box.** Its evidence comes only from
  GitHub Actions check runs.

### Shell variables do not persist across invocations

Nothing you set in one pasted block survives into the next. The plans are written for that: each
block derives what it consumes, and state that has to cross a block boundary is written to a file
under `${TMPDIR:-/tmp}` (the wave 2 pytest baseline, the wave 5 secret-scanning poll record). You are
therefore free to close the terminal between blocks.

Two values still need to be on paper, because you need them and no block re-derives them for you:
`PR_NUMBER` and `MERGED_MASTER` from wave 4, and `DOCSPR` from wave 6. Write them down.

### The guard-and-mutation rule

Every guard and the mutation it authorises live in ONE fenced block, submitted as ONE invocation.
`exit 1` only stops the invocation it runs in. A guard that exits in an earlier submission cannot
stop a mutation submitted in a later one.

Two consequences you own:

- Paste each fenced block whole. Never line by line, and never "just the interesting part".
- An automated driver must ABORT the entire sequence on a failure. Logging the failure and continuing
  to submit the remaining blocks reaches the mutation anyway.

### What was REMOVED from this document, and why

The previous edition carried a long treatment of two PowerShell-only hazards: that a bare top-level
`throw` does not stop a command submitted after it across a harness call boundary, and that guards
must therefore be wrapped in `& { ... }` together with their mutation so the shell parses them as one
unit. Both are gone.

They were removed, not forgotten. They were artifacts of translating POSIX into PowerShell. In POSIX
`set -e` plus an explicit `exit 1` gives the property natively, and the 24 `& { ... }` blocks are now
plain fenced blocks in the plans with their guards asserting on VALUES and exiting 1. The underlying
rule survives as "the guard-and-mutation rule" above, which is the language-independent half.

The appendix of "POSIX originals, for provenance only, DO NOT RUN" is also gone. Its premise, that
POSIX is not executable in the operator's environment, is refuted: the operator runs Git Bash.
Keeping it would reinstate the two-language split this restructure removes.

### Posture

A "NOT MET" outcome is allowed and is better than a zero reached by dismissal. SCAN-08 closes as a
recorded DEFERRAL, on purpose. If a count is nonzero because the analyser never re-ran, say so; do
not dismiss to reach zero.

### Everything irreversible in this phase

- 26 code scanning alert dismissals (wave 5). The dismissal event stays in the repository audit trail
  permanently and cannot be removed.
- 1 Dependabot dismissal (wave 4 hands it to wave 6; only `fix_started` is honest).
- Enabling `secret_scanning_validity_checks` (wave 5). This sends candidate secrets to their issuing
  providers and cannot be un-sent. Threat T-38-29. The configuration is reversible; the outbound
  provider calls are not. This is the ONLY action in the phase that leaves the repository boundary.
- Deletion of `.github/workflows/codeql-analysis.yml` (wave 3, gated on VERDICT-SCAN-06).
- Creation of remote tag `archive/dev-final` (wave 6).
- Deletion of remote branch `origin/dev` (wave 6). The only ref deletion in the phase.
- Creation of master's FIRST branch-protection object (wave 6), plus its DELETE on the failure path.
- 2 pull request merges to master (waves 4 and 6).

Locally reversible but disruptive: wave 2's remediation branch replaces the cryptography build inside
your `.venv`. Note the version you have before you run it. Measured 2026-09-09, that branch is
counterfactual and is not expected to run.

## 2. CURRENT STATE, measured 2026-09-09

Do not contradict any of this without evidence. Re-measure rather than assume.

- Repo `thezoid/ShopPyBot` is PUBLIC. master at `be613ee`. Branch `chore/v4.0-milestone-close`, 0
  behind master.
- **Code scanning is INERT.** `code-scanning/default-setup` reads `state: configured` but
  `languages: []` and `updated_at: null`. The newest analyses on `refs/heads/master` are 1581556190
  and 1581553416, both at `bd70601f`, 2026-08-06. Master is `be613ee`, eighteen commits later.
  The 31 open alerts (numbers 3 through 34, no #30) are a FROZEN SNAPSHOT. Alerts #3, #4, #5, #33 and
  #34 CANNOT close on their own while default setup is in this state, no matter what the code says.
- No `CodeQL` check-run exists on master or on PR #37.
- `branches/master/protection` returns **404 Branch not protected**. There are no required status
  checks. Ruleset `baseline-protection` (id 20218490) carries `deletion` and `non_fast_forward` only.
- Secret scanning enabled, 0 open. Non-provider patterns and validity checks both `disabled`.
- Dependabot 0 open. Alert #13 reads `state: fixed`, `fixed_at: 2026-09-07T04:02:21Z`,
  `first_patched_version.identifier: 50.0.0`. Master pins `cryptography==50.0.1` in BOTH
  `requirements.txt:3` and `pyproject.toml:16`. `50.0.0` is the advisory FLOOR, not the pin; anything
  that reads it as an exact target is proposing a downgrade.
- `origin/dev` at `65ef2b906ed4b6aca85ccf4e02e42deff80174e3`. No `archive/dev-final` tag exists yet.
- jq 1.8.1 installed. gitleaks NOT installed.

Two corrections to statements this document previously made, both refuted live this pass:

- **CodeQL is NOT a required status check on master.** The previous edition asserted it was, next to
  the SCAN-06 deletion. There are no required contexts at all. Do not act on the old claim: that
  priming is exactly what would talk an executor into keeping a producer-less CodeQL context in the
  wave 6 required set.
- **Master's required-context history is two periods, not one flat zero.** Period 1: THREE required
  contexts (`CodeQL`, both test legs, `strict: true`) while PR #23 was open, cited to
  `.planning/ROADMAP.md:159` (verified 2026-08-02) and `38-CONTEXT.md:84-88` (gathered 2026-08-03);
  PR #23 opened 2026-08-03T15:25:27Z, inside that period. Period 2: ZERO from 2026-09-06 onward,
  cited to the 404. The transition is attributed to privatization and is deliberately NOT timestamped
  (no audit-log access, the object is gone). Wave 6's FINAL GATE must write "the first master has
  carried since the pre-privatization object was destroyed". The phrasings "never held", "ever had"
  and a flat ZERO history are each an automatic NOT MET.

## 3. THE WAVE SEQUENCE

Tag legend: `[WALK AWAY]` start it and leave. `[WATCH]` stay and re-run or observe; it does not
block. `[DECIDE]` a judgement you must write down. `[BROWSER]` a click in the GitHub web UI.
`[SAY TO CLAUDE]` a prompt to paste into the session.

Total hands-on is about 6h45m, plus up to 35 minutes of waiting in wave 4, up to 15 minutes of
polling in wave 5, and an unbounded CI wait in wave 6. Do not start this after 6pm. Waves 4 through 6
contain every irreversible action in the phase; do not begin wave 4 without 3 clear hours.

Gate 0 is the plan-checker PASS. It is not a wave and it has no plan. See Checkpoint 0.

### Wave 1: `38-01-PLAN.md`. Baseline plus the two blocking verdicts. 45 min

- Does: the wave-0 hard gate (code scanning must answer HTTP 200 or the phase does not start), cuts
  `phase-38-scanning-to-zero` off master and carries the planning files over, records analysis
  provenance, inventories all three scanners, computes VERDICT-SCAN-06 and VERDICT-SCAN-01.
- Mutates GitHub: NO. Every API call is a read. The plan's verification item 6 proves it by searching
  the session transcript for `-X PATCH`, `-X POST`, `-X DELETE`, `-X PUT`.
- IRREVERSIBLE: nothing remote. Locally, `git checkout -B` force-resets any existing local
  `phase-38-scanning-to-zero` to origin/master and moves HEAD off the planning branch. It destroys a
  branch POINTER only, no commit. Recover with `rtk proxy git reflog`.
- Run: `/gsd:execute-phase 38 --wave 1`
- Commands: `38-01-PLAN.md` Task 1 (wave-0 gate, branch cut, inventory, provenance), Task 2
  (VERDICT-SCAN-06), Task 3 (VERDICT-SCAN-01, commit the baseline).
- Gate to start: a written plan-checker PASS.

### Wave 2: `38-02-PLAN.md`. Production fixes plus the invariant test. 95 min

- Does: replaces substring URL matching with `core/urls.host_matches` at both production call sites,
  verifies the cryptography pin against a floor derived from VERDICT-SCAN-01, and pins the
  secret-name-not-value invariant the wave 5 dismissals rest on. Two negative controls.
- Mutates GitHub: NO. Nothing in this wave reaches master; wave 4 lands it.
- IRREVERSIBLE: nothing. The remediation branch (only on a regressed or disagreeing pin) replaces
  cryptography inside your `.venv`; note your current version first.
- Run: `/gsd:execute-phase 38 --wave 2`
- Commands: `38-02-PLAN.md` Task 0 (preflight, eight guards), Task 1 (host_matches plus its negative
  control), Task 2 (cryptography pin), Task 3 (secret-name invariant plus its negative control),
  Task 4 (whole-wave proof and commit).
- Gate to start: wave 1 produced `38-SCAN-BASELINE.md` with both `## Alert Inventory` and
  `## VERDICT-SCAN-01`. Task 0 enforces it.
- `[WALK AWAY]` stretches: the four full pytest runs (Task 0 guard P8, Task 2 Step 2C on the
  remediation branch only, Task 4 guard V2, and the whole-plan verification). Everything else is
  seconds. No `[WATCH]` and no `[BROWSER]` anywhere in this wave.

### Wave 3: `38-03-PLAN.md`. ci.yml permissions, CodeQL removal, SHA pins, SCAN-08 deferral. 55 min

- Does: scopes `ci.yml` top-level permissions (SCAN-05), deletes `codeql-analysis.yml` if and only if
  VERDICT-SCAN-06 reads SAFE-TO-DELETE (SCAN-06), pins every action reference to a verified commit
  SHA (SCAN-11), records the SCAN-08 deferral with its apply-later commands (SCAN-08).
- Mutates GitHub: NO. Every API call in the plan is a GET. No web UI action is required.
- IRREVERSIBLE: nothing remote. The workflow deletion becomes irreversible only when wave 4 merges.
- Run: `/gsd:execute-phase 38 --wave 3`
- Commands: `38-03-PLAN.md` Task 0 (preflight), Task 1 (ci.yml permissions and the SCAN-06 gate),
  Task 2 (SHA pins), Task 3 (SCAN-08 deferral record and the commit).
- Gate to start: wave 1 produced a readable `## VERDICT-SCAN-06`. Task 0 enforces it. If Task 0 fails
  on the verdict, the fix is to run wave 1, not to hand-write a verdict.
- HARD RULE: the SCAN-08 apply text is text to STORE. It is a live protection mutation. Do not run
  any of it now, and do not respond to any outcome of the no-mutation check with a protection or
  ruleset write in either direction; a "revert" there would itself be the mutation the step exists to
  disprove.

### Wave 4: `38-04-PLAN.md`. Open the PR, get green, merge to master, re-query. 70 min plus up to 35 min waiting

- Does: opens pull request A, watches the checks, runs the merge gate, MERGES TO MASTER, cuts
  `phase-38-docs`, waits for the post-merge analysis, re-queries alerts 3/4/5 and the Dependabot
  queue.
- Mutates GitHub: **YES.** One push, one pull request, one merge to master.
- IRREVERSIBLE: the merge lands the deletion of `.github/workflows/codeql-analysis.yml` on master.
  Master's tip changes for everyone. Recovery is a revert commit through another pull request, not an
  undo. `gh pr merge` now lives INSIDE the gate block, so read the whole block before pasting it:
  pasting it merges to master when the guards pass.
- Run: `/gsd:execute-phase 38 --wave 4`
- Commands: `38-04-PLAN.md` Task 1 (recon, merge master in, push, PR create, the merge gate and the
  merge, `phase-38-docs`, remote acceptance reads), Task 2 (analyses poll and the SCAN-05/SCAN-03
  re-query), Task 3 (Dependabot 13 and the queue).
- Gate to start: wave 3 complete, 3 clear hours.
- Local IRREVERSIBLE: `checkout -B phase-38-docs` destroys an existing local `phase-38-docs` POINTER.
  No commit is lost; recover via `rtk proxy git reflog`.

### Wave 5: `38-05-PLAN.md`. 26 dismissals in seven reasoned groups, plus two ORDERED secret-scanning PATCHes. 50 min plus up to 15 min polling

- Does: dismisses the 19 test-fixture url-sanitization alerts as four distinct shapes with four
  distinct reason strings, dismisses the 7 clear-text alerts as three sub-cases, then enables secret
  scanning non-provider patterns, enumerates and polls, and only then enables validity checks.
- Mutates GitHub: **YES.** 26 alert PATCHes and 2 repository-settings PATCHes.
- IRREVERSIBLE: every dismissal (undo is a manual PATCH back to `state=open`, per alert, and the
  event stays in the audit trail permanently). And PATCH 2, validity checks, which sends candidate
  secrets to their issuing providers. That one cannot be recalled.
- Run: `/gsd:execute-phase 38 --wave 5`
- Commands: `38-05-PLAN.md` Task 1 (the 19, in four groups), Task 2 (the 7 clear-text), Task 3 (the
  two ordered settings PATCHes and the poll).
- Gate to start: wave 4 complete, and `tests/test_secret_names_not_values.py` is on master and green.
  Task 2 step 1 asserts the test half mechanically.
- The two PATCHes are two requests in a fixed order with an enumeration and a poll between them.
  Never bundled. The ordering is the point.
- No `[WALK AWAY]` anywhere in this wave. Its only `[WATCH]` is the poll, and the poll is what gates
  the irreversible half.

### Wave 6: `38-06-PLAN.md`. gitleaks required, archive-then-delete origin/dev, reason audit, FINAL GATE, docs PR. 70 min

- Does: CREATES master's first branch-protection object requiring `gitleaks` and both test legs
  (SCAN-07), archives `origin/dev` to a verified tag and deletes the branch (SCAN-10), audits the
  seven dismissal-reason groups, takes the closing measurement, writes the FINAL GATE table, opens
  and merges the documentation pull request.
- Mutates GitHub: **YES.** A protection PUT, a tag POST, a branch DELETE, a Dependabot PATCH, one
  pull request merge.
- IRREVERSIBLE: all of the above. See section 5 for the recovery per item.
- Run: `/gsd:execute-phase 38 --wave 6`
- Commands: `38-06-PLAN.md` Task 1 (the protection PUT and its guards, one invocation), Task 2 (the
  archive-then-delete, one invocation), Task 3 (closing measurement, reason audit, FINAL GATE, docs
  PR, post-merge addendum).
- Gate to start: waves 4 and 5 complete, both summaries exist, local branch is `phase-38-docs` with
  no source changes, `gh` has admin rights.
- **MASTER'S MERGE PATH IS LOCKED** from Task 1's PUT until the docs pull request merges. Master will
  carry three required contexts it has never been checked against, and if any one fails to report,
  EVERY merge to master is blocked, including hotfixes. The risk applies to every entry in the set,
  not only `gitleaks`, because a PUT chooses the whole set rather than appending to one.
  **Do not start wave 6 unless you can finish it.**

### The DEFER branch, if VERDICT-SCAN-06 reads DEFER

This changes what you SEE, not what any command asserts. The plans STOP on this shape with
instructions. Expect the stop; it is not a failure.

- Wave 3: `codeql-analysis.yml` is NOT deleted. A `## SCAN-06 deferred` section names the failed
  condition. SCAN-06 is carried forward as blocked. This is a permitted outcome.
- Wave 5: group C (#25, #26) must NOT be dismissed with the staleness string. The workflow still
  exists and the staleness premise is false; the string would write a factually false sentence into a
  permanent, non-editable audit trail. Re-run the `/instances` probe: an open instance carrying
  `/language:python` makes them LIVE and they move into group B's reasoning with a rewritten comment;
  otherwise record them as blocked-on-SCAN-06 and carry them forward as NOT MET. Do not dismiss to
  reach zero. Task 2's dismissed-count assertion expects 5, not 7, on this branch.
- Wave 6: the closing code-scanning count is expected to be **2** (#25 and #26). SCAN-02 reads NOT MET
  naming them by number; SCAN-06 reads DEFERRED; `codeql-analysis.yml` is expected PRESENT on master
  and a 200 there is correct; the SCAN-11 enumeration returns four files rather than three; the
  reason audit shows six comment groups plus #25/#26 still open. A bare `distinct_groups == 7` would
  pass here wrongly, which is why the audit asserts the exact group signature instead.

## 4. OPERATOR CHECKPOINTS

Everything a human must look at, decide, or click. This is the one thing this document still owns
outright. Where a decision has a mechanical half, the plan computes it and you accept the computed
value; you do not override it by hand.

### Checkpoint 0: the plan-checker gate. `[DECIDE]` 20 min. HARD GATE

Nothing below may run until this completes with a written PASS.

- [ ] Acknowledge the three blocking constraints in writing, before anything else.
  - [ ] `rtk git log` is lossy. For every range, audit, or completeness query in this phase I will
        use `rtk proxy git log ...`.
  - [ ] Single-platform probing produces confidently wrong results. Where a check-run producer or an
        alert state matters, I probe it against a real run, not against my expectation.
  - [ ] The six Phase 38 plans are UNVERIFIED. This checkpoint is the reason.

- [ ] Confirm the shell (section 1, "The shell is Git Bash").

- [ ] `[SAY TO CLAUDE]` Type exactly:

  > Re-run the Phase 38 plan checker against all six plans in `.planning/phases/38-scanning-to-zero/`. Your job is to FALSIFY, not to confirm. Primary claim to falsify: that all 7 clear-text CodeQL alerts genuinely trace to `SECRET_KEYS` at `core/credentials.py:47`, and that `SECRET_KEYS` really is a list of credential key NAMES rather than values. Dismissing a real credential leak as noise is the worst outcome available here. Also falsify: (2) does the `origin/dev` deletion tag and verify before deleting, with every failure path leaving the branch intact; (3) can SCAN-06's workflow removal, or the required-check set SCAN-07 creates from nothing, strand an unreportable required context and lock the repo out of merging. Note for that one that master has NO protection object and NO required contexts today, measured 2026-09-09, so SCAN-07 chooses a whole set rather than appending to one and the risk applies to every entry in it. Apply the anti-pattern check "plan names one call site when several exist": grep the whole package for the pattern, not just the line the plan names. Also check the measured-state corrections: SCAN-01 is 1 open Dependabot alert not 7; SCAN-02 is 7 clear-text alerts (5 `py/clear-text-logging-sensitive-data` plus 2 `py/clear-text-storage-sensitive-data`) not "the two"; SCAN-03 is exactly 3; SCAN-04 is exactly 19; SCAN-05 is 2 `actions/missing-workflow-permissions`; totals 31 code scanning, 0 secret scanning. And check whether the cryptography disposition is genuinely open: alert #13, high, PKCS#7 EnvelopedData Bleichenbacher oracle, GHSA-g6cj-pr64-35w5 / CVE-2026-69247, vulnerable range `>= 44.0.0, < 50.0.0`, `first_patched_version.identifier` `50.0.0`. Measured 2026-09-09 the alert reads `state: fixed`, `fixed_at: 2026-09-07T04:02:21Z`, the open Dependabot queue is 0, and master carries `cryptography==50.0.1` at `requirements.txt:3` and `pyproject.toml:16`. `50.0.0` is the advisory FLOOR, not the pin; treat anything that reads it as an exact target as a downgrade. Return a single-word verdict line: PASS or FAIL, plus the evidence for each falsification attempt.

- [ ] Read the verdict. Write it down here: `PLAN CHECKER VERDICT: ____________  (date/time: __________)`

- [ ] **HARD GATE.** Only a written PASS unlocks wave 1. On FAIL, stop the phase, fix the named plan,
      and re-run this checkpoint. Do not "proceed carefully". Phase 38 dismisses 26 alerts and deletes
      a remote branch; both are hard to undo.

- [ ] If the checker overturns the SCAN-06 expectation (that `CodeQL` comes from default setup and
      `Analyze (python)` / `Analyze (actions)` come from the workflow file), note it now. Wave 1
      re-measures it live, and the measurement wins over both the plan and the checker.

### Wave 1 checkpoints

- [ ] `[DECIDE]` Auth vs enablement. If the code-scanning read returns 403, that is repository
      POSTURE, not credentials. Do not re-authenticate and retry. You may run this for the record, but
      it does not change the decision:

```sh
rtk gh auth status
```

- [ ] `[SAY TO CLAUDE]` at the plan's read points: have Claude run each fenced block from
      `38-01-PLAN.md` and report what it printed. Do not restate the decision rules to it; the plan
      carries them.
- [ ] Expect to recognise, reading the terminal: a 40-character SHA for PLANSHA; roughly 31 inventory
      lines grouped by rule id; the reset unstaging `.continue-here.md` and nothing else; exactly one
      commit with subject `docs(38-01): ...`.
- [ ] `[DECIDE]` VERDICT-SCAN-06. The plan prints `COMPUTED: VERDICT-SCAN-06: ...` plus a
      `FAILED CONDITIONS:` string and a criterion requires the WRITTEN verdict to match the computed
      one. You accept the computed verdict; you do not override it. **If the live probes contradict
      the planning-time expectation, record DEFER: the measurement wins over the plan.**
- [ ] `[DECIDE]` VERDICT-SCAN-01. The enum is `UPGRADE to <version>` | `DISMISS` | `ACCEPT`. DISMISS
      is only permitted when no patched release exists AND the PKCS#7 API is provably absent.
      Remember `50.0.0` is a FLOOR, not a target.
- [ ] Note the IRREVERSIBLE (local only) branch-cut warning in section 3, wave 1.

### Wave 2 checkpoints

- [ ] `[DECIDE]` The cryptography branch. On a DISMISS or ACCEPT verdict, or when Task 2 Step 2A stops
      at "the pin guard did not print PIN-OK", you decide whether to take the remediation branch and
      write the choice down. Standing instruction: writing `50.0.0` over a `50.0.1` master already
      carries is a DOWNGRADE. The remediation branch exists for a regressed or disagreeing pin, not
      for tidiness.
- [ ] ESCALATION, failed negative control. If either control does not produce the required failures,
      the tests are not gates and wave 5's 26 dismissals lose their backing. STOP the phase. Do not
      retry until it passes. The plan's blocks restore the file automatically on every exit path, so a
      failed control leaves nothing broken on disk, but it still halts the wave.
- [ ] ESCALATION, moved alert set. If Task 0's SCAN-03 or SCAN-02 guard fires, the alert set moved.
      Stop and report. Do NOT adjust the expected string to make the guard pass; wave 5's dismissal
      groups derive from that same set.
- [ ] `[DECIDE]` Commit approval: files table, proposed message, explicit yes, BEFORE Task 4 Step 4B
      is run. Step 4B puts the scope check and `git commit` in one invocation, so once it runs there
      is no second gate.
- [ ] IRREVERSIBLE / locally disruptive: Task 2 Step 2C replaces cryptography in your `.venv`. Note
      the version you have first. Nothing outside the venv is touched, and this runs on the
      remediation branch only.

### Wave 3 checkpoints

- [ ] `[SAY TO CLAUDE]` Orientation read: "Read the `## VERDICT-SCAN-06` section of
      `38-SCAN-BASELINE.md` and tell me which verdict it records." This exists so you know which
      branch the wave is about to take. Task 1's gate re-derives it mechanically and is the authority.
- [ ] `[DECIDE]` Write it down before reading further: `VERDICT-SCAN-06 = ______`. On DEFER, expect
      the SCAN-06 deletion and its acceptance check to be skipped; see section 3's DEFER branch.
- [ ] `[DECIDE]` Acknowledge that the SCAN-08 apply commands are text to STORE and not to run. Tick
      this before pasting anything: the stored text is a live protection mutation.
- [ ] `[SAY TO CLAUDE]` Record the two deliberate non-changes so a later reader does not read them as
      oversights: (a) `dev` stays in the `on: push` / `on: pull_request` branch filters of `ci.yml`
      and `gitleaks.yml` even though wave 6 deletes the branch; leaving it is inert. (b) the
      checkout/setup-python v6-vs-v7 divergence is already closed on master by PRs #27 and #28;
      record it as a CLOSED observation. Do not helpfully "fix" the dev filters.
- [ ] The Actions-allowlist question is RECORDED here and PROVEN by wave 4's pull request. An
      allowlist rejection ends in `startup_failure` with zero jobs. Do not chase it in this wave.
- [ ] `[DECIDE]` Commit approval, and the optional split into a second `docs(38-03):` commit. The plan
      supplies both messages.

### Wave 4 checkpoints

- [ ] `[SAY TO CLAUDE]` Before anything: "Read `38-02-SUMMARY.md`, `38-03-SUMMARY.md` and the
      `## VERDICT-SCAN-06` section of `38-SCAN-BASELINE.md`, and report back the cryptography version,
      the three url-sanitization alert numbers, the two permissions alert numbers, the SCAN-06 verdict
      and the count of pinned references." This is how you get the values the PR body needs. The plan
      asserts the body CONTAINS them but cannot author them.
- [ ] `[DECIDE]` Author the PR body FIRST, at exactly `${TMPDIR:-/tmp}/pr-38-body.md`. It must be
      non-empty and carry one line each for SCAN-01, SCAN-03, SCAN-05, SCAN-06, SCAN-11 and SCAN-08,
      or the plan refuses to push. **The SCAN-01 line must state the version master pins TODAY and say
      plainly whether this branch changes either manifest. Do not write "moved from X to Y" for a
      change this branch does not contain.**
- [ ] `[WALK AWAY]` `gh pr checks --watch --interval 30`. `[WATCH]` the polling fallback if `--watch`
      does not terminate. **Neither is the gate.** The gate is the single pasted block, and a green
      `--watch` does not authorise a merge.
- [ ] `[DECIDE]` **READ BEFORE PASTING.** The merge gate and `gh pr merge` are ONE block. Pasting it
      merges to master when the guards pass. See the IRREVERSIBLE note in section 3, wave 4.
- [ ] On `startup_failure`: the guard prints the diagnostic command. Do NOT revert a pin to a floating
      tag to make it pass. Check the Actions allowlist (section 6 background items).
- [ ] `[WATCH]` Polling cadences, both human loops with no mechanical form: the analyses poll roughly
      every 60 seconds for up to 15 minutes; the Dependabot poll roughly every 2 minutes for up to 20
      minutes.
- [ ] **The stale analysis is the EXPECTED result, not a fallback.** (The previous edition claimed
      this risk "is handled at steps 19 through 22". It was not.) When the poll times out, record the
      newest analysis row with its `created_at` and the
      `default-setup: state=configured languages=[] updated_at=null` line. Then the four prohibitions:
      no `fixed` disposition for #3/#4/#5/#33/#34; no dismissal to clean the queue; no reviving
      `codeql-analysis.yml`; no writing a timeout up as a pass. Your action is a RECONFIGURATION of
      default setup to restore the `python` and `actions` languages. A bare workflow dispatch is not
      an equal alternative and cannot help while `languages` is `[]`.
- [ ] `[SAY TO CLAUDE]` "Read the `## Alert Inventory` section of `38-SCAN-BASELINE.md` for the
      pre-change state of alerts 3, 4, 5, 33, 34." That is the "before" half of the evidence and the
      plan does not produce it.
- [ ] `[SAY TO CLAUDE]` "Read the `## VERDICT-SCAN-01` section and the cryptography section of
      `38-02-SUMMARY.md`, and report whether the verdict was UPGRADE, DISMISS or ACCEPT." Task 3 step
      5 branches on that value but you supply it.
- [ ] `[DECIDE]` DEFER qualifier on the `codeql-analysis.yml` acceptance read: on SAFE-TO-DELETE the
      file must be GONE from master (404); on DEFER it is expected to still be PRESENT and a 200 is
      correct, not a failure.
- [ ] Write down: `PR_NUMBER = ______` and `MERGED_MASTER = ______`. The plan re-derives both from the
      API inside every block that needs them and deliberately depends on no shell variable, but you
      need them for the summary and for the wave 5 and wave 6 handoffs.
- [ ] `[SAY TO CLAUDE]` Write `38-04-SUMMARY.md`, minimum 40 lines, to the evidence list in the plan's
      `<output>`: PR number and merge SHA, the pre-merge check list, the `GATE PASSED:` / `MERGED:` /
      `MERGED MASTER SHA:` lines, the analysis rows with `results_count`, the `default-setup:` line,
      the three per-alert re-query lines, the ci.yml workflow-permissions lines, and every HTTP status
      line.

### Wave 5 checkpoints

- [ ] `[DECIDE]` Branch check before anything: read `## VERDICT-SCAN-06` and know which arm you are
      on. The plan gates on it twice mechanically. On DEFER the cost is two alerts carried NOT MET
      into wave 6. See section 3's DEFER branch. Read this, do not restate the fence.
- [ ] PROHIBITION, up front. Do NOT create `.github/codeql/codeql-config.yml`, do NOT add
      `paths-ignore`, and do NOT write `# lgtm` or `# nosec`. Blanket suppression also hides FUTURE
      production findings in the same files. The plan enforces this after the fact; you should not get
      there.
- [ ] `[SAY TO CLAUDE]` One read per shape. A check of one shape says nothing about the other three.

  > Read `tests/test_cli_items.py` lines 7 through 21, `tests/test_plugin_amazon.py` lines 60 through 64, `tests/test_registry.py` lines 67 through 80, `tests/test_security_md.py` lines 26 through 42, and `tests/conftest.py` lines 100 through 123 (the `tmp_plugins_dir` fixture). For each, tell me what the right operand of the flagged `in` expression actually is and where that value comes from.

  you should see FOUR DIFFERENT answers, not one. "The URL literal is defined in the same file" is
  true of only one of the four shapes, so do not use it as the test.

- [ ] `[DECIDE]` Spot-check ONE alert per shape, four in total. Open the cited file and line and read
      what the flagged `in` expression reads on each side. Expected findings:
  - G1 (#6 through #8), spot check `tests/test_cli_items.py:21`: the right operand is
    `capsys.readouterr().out`. The value searched for was placed on a `MagicMock` return value in the
    same test, and `core.service.BotService` is patched out.
  - G2 (#9 through #15), spot check `tests/test_plugin_amazon.py:63`: the right operand is
    `AmazonPlugin.domain_patterns`, a list literal in `plugins/shopbot_plugin_amazon.py`. The `in` is
    list membership, not a substring search, and there is no URL on either side.
  - G3 (#16 through #19), spot check `tests/test_registry.py:75`: the right operand is
    `domain_patterns` on a plugin the test itself wrote to `tmp_path` via `tmp_plugins_dir`, or the
    inline `OtherPlugin` source at `tests/test_registry.py:89`.
  - G4 (#20 through #24), spot check `tests/test_security_md.py:41`: the right operand is
    `_read_security_md()` at `tests/test_security_md.py:30`, which reads `SECURITY.md` out of this
    repository's own checkout.

  The one question every check answers is the same: does any attacker-controlled input reach the
  flagged expression? A request body, a CLI argument, an environment variable, or a network response
  would be. A value the test itself defines, a class attribute committed to this repository, and a
  document read out of this repository's own checkout are not.
  **HALT AND ESCALATE:** if a spot check shows attacker-controlled input reaching the expression, that
  shape is not a test-fixture false positive. Stop, dismiss NOTHING in that group, and report it as a
  blocking finding with the file, the line and the input path. Do NOT dismiss the rest of the group to
  get the open count to zero. The count is the evidence, not the goal. The plan's table is at
  `38-05-PLAN.md` Task 1 step 2.

- [ ] IRREVERSIBLE, on every dismissal block: it destroys the alerts' open state. Undo requires a
      manual PATCH back to `state=open`, per alert, and the dismissal event stays in the repository
      audit trail permanently and cannot be removed.
- [ ] `[WATCH]` The poll. You physically wait about 2 minutes between invocations and re-run the fence
      by hand. It does not block; you re-run it yourself. Budget 900 seconds. Do NOT add a foreground
      sleep: the harness blocks it, and the poll record file at `${TMPDIR:-/tmp}/scan-09-poll.txt` is
      what carries the state across the gaps.
- [ ] `[DECIDE]` If an alert appears during the poll: do NOT dismiss it to keep the count at zero. A
      live credential means ROTATION, which is your action and a blocking finding. Only a human may
      write the clearance file. Measured expectation: the tracked `config.yml` in history carries
      `bb_password`, `bb_cvv` and `amz_pwd` as PLACEHOLDER strings, so a hit on those key shapes is
      not a rotation event.
- [ ] `[DECIDE]` **IRREVERSIBLE, read before pasting.** PATCH 2 enables validity checks. This is the
      ONLY action in the phase that leaves the repository boundary. The configuration is reversible;
      the outbound provider calls are not. Two requests, not one, and in THIS order.
- [ ] `[SAY TO CLAUDE]` Write `38-05-SUMMARY.md` to the 20-item manifest in the plan's `<output>`.
      Every item is a string a criterion elsewhere greps for.
- [ ] `[DECIDE]` Commit approval on `phase-38-docs`: files table, proposed message, explicit yes.

### Wave 6 checkpoints

- [ ] **STAY AT THE KEYBOARD** during `gh pr checks $DOCSPR --watch`. This is the block's only
      sustained attention requirement and it is deliberately neither `[WALK AWAY]` nor `[WATCH]`:
      master's merge path is locked until that pull request merges or the revert is taken.
- [ ] `[SAY TO CLAUDE]` Five comprehension reads with no mechanical substitute: read
      `.github/workflows/gitleaks.yml` in full including the Actions-allowlist header comment; quote
      the gitleaks success line out of `38-04-SUMMARY.md`; state the SCAN-10 hard ordering back before
      anything in Task 2 runs; read `38-SCAN-BASELINE.md` in full plus the 38-04 and 38-05 summaries;
      and the three authoring prompts (SCAN-10 RESOLVED section, FINAL GATE section, the summary and
      its addendum).
- [ ] `[DECIDE]` SCAN-10 disposition. Write the decision down:
  - (a) `matches_planning_sha=False`: STOP and report. Someone pushed to a branch dormant for 17
    months and that needs a human look.
  - (b) `ancestor_exit` is `0`: the commit is already reachable from master, the archive tag is
    unnecessary, and the disposition changes. STOP. Record the reading, skip the tag, and do NOT
    delete the branch in this run. SCAN-10 closes as recorded-and-not-executed, which is a permitted
    outcome. Do NOT edit the guard to fall through and do NOT hand-write an unguarded delete: the
    block's third guard resolves a tag this path never created, so it cannot serve this branch.
  - (c) `ancestor_exit` nonzero: this is the proof the commit is not reachable from master, which is
    the entire reason the tag is required. Proceed.
- [ ] `[DECIDE]` Sign off in writing that the tag verification ran and is timestamped BEFORE the
      delete, and specifically that (b), the fetch, succeeded. Do NOT record this as "all four
      passed" as though the four were equal evidence: (a) is a write receipt, (c) and (d) are local
      consistency checks, (b) is the one that can fail because the archive is not real, and (e), the
      delete gate computed fresh inside the delete's own invocation, is the decisive one.
- [ ] `[DECIDE]` The judgement on any nonzero closing alert count, and the Dependabot-13 disposition.
      Only `fix_started` is honest; `inaccurate`, `not_used` and `tolerable_risk` are
      misrepresentations.
- [ ] Write down `DOCSPR = ______`. It is the one value the watch and the merge both need and no
      block re-derives it for you.
- [ ] Order matters: author `38-06-SUMMARY.md` with an empty `## Post-merge addendum` heading BEFORE
      the staging commit, or the phase's closing record never reaches the pull request it documents.
      Fill the addendum after the merge; that commit rests on `phase-38-docs`.
- [ ] **Exactly ONE pull request merges to master in wave 6.** Opening a second one to land the
      addendum would be an unauthorised change to the default branch taken after the phase's own
      closing gate. Landing the addendum on master is a separate operator decision, recorded before it
      is taken, as a normal follow-up outside this phase.

### After every wave

- [ ] Check the pending-push count. Push if more than 10 commits are stacked locally.

```sh
rtk git rev-list --count origin/master..HEAD
```

## 5. ROLLBACK INDEX

Per irreversible action: what the recovery is, and where its procedure lives.

- **Wave 1, local branch cut.** `git checkout -B` reset a local branch pointer. No commit is lost.
  Recover with `rtk proxy git reflog`. No plan procedure needed.
- **Wave 2, `.venv` cryptography upgrade.** Reinstall the version you noted before running it.
  Nothing outside the venv is touched.
- **Wave 3, `codeql-analysis.yml` deletion, before the wave 4 merge.**
  `git checkout HEAD -- .github/workflows/codeql-analysis.yml`. Procedure: `38-03-PLAN.md` Task 1,
  directly under the SCAN-06 gate.
- **Wave 4, the merge to master.** A revert commit through another pull request. There is no undo.
  Procedure: `38-04-PLAN.md` Task 1 step 5, the IRREVERSIBLE note.
- **Wave 5, alert dismissals.** A manual PATCH back to `state=open`, one per alert. The dismissal
  event itself stays in the audit trail permanently and cannot be removed. Procedure: `38-05-PLAN.md`
  Task 1 and Task 2 IRREVERSIBLE notes.
- **Wave 5, `secret_scanning_non_provider_patterns`.** PATCH the setting back to `disabled`.
- **Wave 5, `secret_scanning_validity_checks`.** The SETTING can be PATCHed back to `disabled`. The
  outbound provider calls cannot be recalled. There is no rollback for those.
- **Wave 6, the protection PUT.** A `DELETE` on `branches/master/protection`, PRE-BUILT into
  `${TMPDIR:-/tmp}/scan-07-revert.txt` by Task 1 step 2 before the PUT is taken. Read the file rather
  than hand-authoring the command under pressure while master is unmergeable. Procedure:
  `38-06-PLAN.md` Task 3, recovery path step 1, which also asserts the after-revert status VALUE (404
  is success, 200 is FATAL, anything else is UNVERIFIABLE) and re-asserts the ruleset is untouched.
- **Wave 6, the `archive/dev-final` tag.** It destroys nothing and can be deleted, but do NOT delete
  it after the branch delete: it is the only thing keeping the archived commit alive.
- **Wave 6, the `origin/dev` branch delete.** Recovery exists ONLY through the verified tag, and only
  until GitHub garbage-collects the object. This is why the tag is verified before the delete and
  re-verified after it. Procedure: `38-06-PLAN.md` Task 2.
- **Wave 6, the Dependabot alert PATCH.** PATCH back to `state=open`.
- **Wave 6, `.continue-here.md` removal.** Local only. `git checkout HEAD -- <path>`.
- **Wave 6, the docs merge.** A revert commit through another pull request.

## 6. KNOWN OPERATOR QUIRKS

- **The auto-mode classifier denies `gsd-executor` dispatch for plans that merge pull requests.** The
  workaround, proven across 9 merges, is to run those steps inline in the main thread. That applies to
  wave 4's push/PR/gate/merge sequence and to wave 6's docs PR sequence.
- **An inline run writes no per-plan STATE.md entry.** The orchestrator must update `.planning/STATE.md`
  by hand afterwards: the `## Current Position` block and the Phase 38 row, naming the pull request
  number and the merged master SHA.
- **`?? .planning/phases/38-scanning-to-zero/.continue-here.md` is expected** from wave 1 onward until
  wave 6 removes it. It is a deliberately untracked handoff file. It must NEVER be committed, and it
  must not be cleared by running `git add` on the phase directory: that lands a paused-run handoff on
  master. Wave 3's staging is scoped by name for exactly this reason.
- **RECORD ONLY, do not act on it during this phase:** `.planning/STATE.md` carries drift about
  master's SHA and status. No plan in Phase 38 authorises a STATE.md rewrite, so it is not a
  background task and specifically not an "anytime" one. Wave 3 stages `.planning/STATE.md` by name,
  so any unrelated edit sitting in the working tree at that moment is swept into the `ci(38-03)`
  commit and lands on master through wave 4's merge, inside a commit whose message says it scoped
  ci.yml permissions. The only STATE.md change this phase authorises is the
  `### Deferred to Milestone Close (v5.0)` section from `38-03-PLAN.md` Task 3.

### Background, `[BROWSER]`, do these in any spare moment

None of these block execution.

- [ ] **Repair `code-scanning/default-setup`.** This is the highest-value background item and it
      decides whether the FINAL GATE fires `NOT RE-ANALYSED` at all. Restore the `python` and
      `actions` languages so the analyser is live again, then confirm alerts 3/4/5/33/34 close on
      their own. A bare workflow dispatch is insufficient while `languages` is `[]`.
      URL: `https://github.com/thezoid/ShopPyBot/settings/security_analysis`
- [ ] **Enable Actions PR creation.** release-please currently fails at PR creation without it. This
      is a security-posture setting, deliberately left to you.
      URL: `https://github.com/thezoid/ShopPyBot/settings/actions`, section "Workflow permissions".
      Tick **Allow GitHub Actions to create and approve pull requests**, then **Save**.
      you should see: the checkbox stays ticked after the page reloads.
- [ ] **Check the Actions allowlist** while you are on that page. `gitleaks.yml` and
      `release-please.yml` both carry header comments saying their actions must be allowlisted. Same
      URL, section "Actions permissions". Confirm `gitleaks/gitleaks-action` and
      `googleapis/release-please-action` are covered by the allowed-actions patterns. SHA pins still
      match an owner/repo allowlist pattern, so wave 3's pinning should not change allowlist
      behaviour; wave 4's PR is where that gets proven.
- [ ] `[DECIDE]` **PR #23, the release-please token.** #23 merged 2026-09-07 and is no longer a
      blockage. The MECHANISM is durable and applies to every FUTURE release-please pull request:
      GitHub suppresses `pull_request`-triggered checks on a head pushed by `github-actions` with
      `GITHUB_TOKEN`, so `test (ubuntu-latest)`, `test (windows-latest)` and `gitleaks` never report
      on a freshly generated release-please head. From wave 6 onward master DOES have three required
      contexts, so the next release-please pull request will need the same close-and-reopen. **The
      durable fix is a GitHub App token. NOT a PAT, ever.** This is a public repo; an owner-identity
      token bypasses everything except the ruleset's `deletion` and `non_fast_forward` rules. No repo
      secrets exist today; do not create any as a workaround. Deferred alongside SCAN-08, and for a
      related reason: `enforce_admins: true` is what makes app-token automation safe to hold, so the
      two land together at milestone close after Phase 50.

      To re-measure #23 yourself, do NOT run a command from here: `38-06-PLAN.md` Task 3 already
      reads `pulls/23` and records the result as evidence. Run it there so there is one reading and
      one record, not two that can disagree.

- [ ] `[DECIDE]` **PR #25 split: DONE 2026-09-07, no action remains.**
      CORRECTION: the previous edition told you to expect "OPEN, untouched" here. That is FALSE and
      contradicted its own prose. Measured 2026-09-09: **#25 is `state=closed merged=false`, closed
      2026-08-17T02:43:40Z; #29 is `state=closed merged=false`, closed 2026-09-07T04:04:32Z.**
      `38-02-PLAN.md` Task 0 guard P6 asserts exactly that. The safe half landed as PR #31 (7 pins
      plus their pyproject mirrors) and PR #36 added the starlette bound. FastAPI stays at 0.115.8 and
      uvicorn[standard] at 0.30.6, now held by `ignore:` rules in `.github/dependabot.yml`.
      IRREVERSIBLE, still worth knowing: merging a future equivalent of #25 whole lands the FastAPI
      0.115-to-0.141 jump on master and unregisters `/api/events`. Recovery is a revert PR, not an
      undo. That bump belongs to a dedicated phase.
      No command here: the live read is `38-02-PLAN.md` Task 0 guard P6, which asserts both PR states
      rather than printing them for you to eyeball.

- [ ] `[DECIDE]` Whether to land the wave 6 closing-summary addendum on master as a follow-up pull
      request after the phase. Separate decision, recorded before it is taken.

## IF YOU HAVE TO STOP

Run this before you close the window. It captures where you are so the next session picks up without
re-deriving anything.

These reads deliberately overlap with reads the plans also perform, and that overlap is INTENTIONAL,
not the restatement this restructure removed. Every line here is read-only: none of it guards a
mutation, so none of it can drift away from a mutation it was protecting. It exists to snapshot a
session, not to execute the procedure. If you are tempted to add a line that writes anything, don't:
put it in the plan that owns the wave.

```sh
rtk proxy git status --porcelain
rtk proxy git rev-parse --abbrev-ref HEAD
rtk proxy git rev-parse HEAD
rtk git rev-list --count origin/master..HEAD
rtk proxy git log --oneline origin/master..HEAD
rtk proxy gh api "repos/thezoid/ShopPyBot/code-scanning/alerts?state=open&per_page=100" --jq 'length'
rtk proxy gh api "repos/thezoid/ShopPyBot/dependabot/alerts?state=open&per_page=100" --jq 'length'
rtk proxy gh api "repos/thezoid/ShopPyBot/secret-scanning/alerts?state=open&per_page=100" --jq 'length'
rtk proxy git ls-remote origin "refs/heads/dev" "refs/tags/archive/dev-final"
test -f "${TMPDIR:-/tmp}/scan-09-poll.txt" && tail -3 "${TMPDIR:-/tmp}/scan-09-poll.txt"
rtk gain
```

Then `[SAY TO CLAUDE]`:

> Write a pause handoff into `.planning/phases/38-scanning-to-zero/.continue-here.md`. Record: the last completed wave and plan task, the plan-checker verdict and when it was issued, the VERDICT-SCAN-06 and VERDICT-SCAN-01 values, whether the `origin/dev` archive tag has been pushed and verified, whether the branch has been deleted, which alert numbers have already been dismissed and with which of the seven reason strings, which of wave 5's two secret-scanning PATCHes have landed (non-provider patterns only, or both), whether `${TMPDIR:-/tmp}/scan-09-poll.txt` exists and what its last POLL line reads, whether master's required-checks list currently carries the unproven `gitleaks` context, and the current three closing alert counts from the commands above. State plainly what the very next step is and what gates it.

Uncommitted work: commit it on the current phase branch before stopping. Do not leave the tree dirty,
with one deliberate exception, the untracked `.continue-here.md` described in section 6.

Two resting states worth calling out explicitly:

- If the `origin/dev` tag is pushed but the branch is not yet deleted, SAY SO. That is a safe resting
  state. The reverse never is.
- If you are stopping between wave 6's protection PUT and the docs merge, SAY SO LOUDLY: master cannot
  be merged to until the docs PR lands or the revert is taken.
