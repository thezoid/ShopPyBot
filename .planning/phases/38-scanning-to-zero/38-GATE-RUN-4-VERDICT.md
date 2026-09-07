**VERDICT: FAIL**

Rule triggered: 8 confirmed blocking findings (each survived both adversarial verifiers). Independently re-measured just now: `repos/thezoid/ShopPyBot` is `private`, `code-scanning/alerts` returns 403 "Code scanning is not enabled", `branches/master.protected` is `false`, and `pulls/23` is `mergeable_state: clean`. The three environmental premises the phase is built on are all false today.

## Root cause

One state change explains 6 of the 8 blockers. The repo was public with GHAS and branch protection when the plans were measured (2026-08-03/04). It is now private on a Free personal plan (`updated_at` 2026-08-10). On that plan: code scanning off, secret scanning off, branch protection unavailable. Dependabot still works, which is why alert #13 checks out and masks the problem. Every plan in the phase asserts the old state; no plan reads visibility or protection availability before acting; the run-book's only 403 guard (`38-RUNBOOK.md:78`) misdiagnoses it as an auth failure and sends the executor into a dead end.

Phase 38 cannot execute at all in the current repository state. It dies at 38-01 wave 1, not at 38-05.

## Blocking findings (remediation list, most severe first)

**1. DI-01 / ML-1 / WF-01 — environment state, not a plan defect**
- **Breaks:** all 26 code-scanning dismissals, both secret-scanning PATCHes, the SCAN-07 required-checks PATCH, the SCAN-08 deferral record, and 38-01's baseline inventory.
- **Scenario:** 38-01 Task 1's inventory GET 403s in wave 1. If forced past it, `38-05-PLAN.md:242` errors instead of returning `0`; `:455` returns `,` (two nulls) with exit 0, a silent false pass; `38-RUNBOOK.md:1804` parses the 403 error body into `rsc-revert.json` as `{"strict":null,"checks":[{"context":null,"app_id":null}]}`.
- **Files:** `38-05-PLAN.md:80-127, 196-198, 242, 393, 455`; `38-06-PLAN.md:129-152`; `38-03-PLAN.md:294-320, 376-380`; `38-RUNBOOK.md:1804-1817, 1839-1841, 2185`.
- **Fix:** Operator decision, not an executor one. Either restore the measured-at-planning state (make public / upgrade plan, then re-enable code scanning and protection) and re-derive every alert number, protection value and check name from live 200s, or re-scope SCAN-01/03/04/07/08 to "unavailable on current plan and visibility" as the recorded measured reason. Add to 38-01 Task 1, as the phase's first gate: `gh api repos/thezoid/ShopPyBot/code-scanning/alerts?state=open` must return 200 and `branches/master --jq .protected` must return `true`, else HALT and report the HTTP status. CLAUDE.md forbids flipping visibility without your explicit instruction, so the executor must stop here regardless.

**2. WF-02 — the no-mutation proof reads green when the API is unreadable**
- **Breaks:** the only evidence 38-03 honored its own "touch no protection setting" rule.
- **Scenario:** `38-RUNBOOK.md:1038` run verbatim prints exactly `null`, which `:1040` declares the PASS, because `??` coalesces a missing property of the parsed 403 body. `$LASTEXITCODE` is 1 and is never read. Step 35's failure text at `:1033` then says "anything other than `false` means the protection API was touched. Revert it" — pointing the operator at a protection write that `:972` forbids.
- **Files:** `38-RUNBOOK.md:1035-1040`; duplicate at `38-RUNBOOK.md:1840`; `38-03-PLAN.md:376-380`.
- **Fix:** Assert exit code, not a coalesced property. Use `--jq .required_pull_request_reviews`, require exit 0, treat any non-zero exit or a body containing `"status":"403"` as UNKNOWN and STOP. Rewrite `:1033` to name the 403 case and forbid any protection write as the response. Fix `:1840` in the same pass.

**3. F1 — dirty-tree gate is narrower than the carry-over it guards; silent unrecoverable data loss**
- **Breaks:** uncommitted `.planning/ROADMAP.md` and `.planning/HANDOFF.json`.
- **Scenario:** `38-01-PLAN.md:111` gates on the phase dir only; `:123` restores four paths. With ROADMAP.md dirty, the gate passes, `checkout -B` aborts with exit 1, and — no `set -e` — the next line's `git checkout $PLANSHA -- .planning/ROADMAP.md` silently replaces it. Verified unrecoverable: no stash, no dangling blob, never staged. Both verifiers reproduced it in throwaway repos, in bash and pwsh. A second variant showed `checkout -B` can *succeed* and the restore still clobbers, so `set -e` alone does not close it. Correction to the finding: the follow-on commit does not land on the wrong branch, it reports "nothing to commit" — no stray commit, no signal at all.
- **Files:** `38-01-PLAN.md:105-130`; `38-RUNBOOK.md:91, 111-118, 123`.
- **Fix:** Widen the gate to all four carry-over paths (or the whole tree) **and** add `set -e` / wrap the run-book block in `& { $ErrorActionPreference='Stop'; ... }` with an explicit `if ($LASTEXITCODE -ne 0) { throw }` after `checkout -B`. The tree is dirty right now (` M .planning/STATE.md`), and `38-RUNBOOK.md:123`'s "your tree is clean per the environment check" is already false.

**4. DI-04 — Task 2 dismisses 7 alerts from hardcoded numbers with no live binding**
- **Breaks:** 7 permanent dismissal comments.
- **Scenario:** `:285` re-derives the live set and prints it; `:288` says "Expect 7 alert records" with no consequent; `:305`/`:311`/`:328` are literal `for N in 27 28 29` / `31 32` / `25 26`. Nothing compares them, no acceptance criterion at `:343-359` requires equality. Task 1 twenty lines earlier drives every loop from live variables with three explicit stop conditions (`:149-163`). On renumbering the executor PATCHes closed or nonexistent records with permanent comments while the live alerts stay open. (Alert numbers are not reused, so a *different* finding taking #31 is not the realistic case; the reachable case is renumbering.) The run-book already implements the correct pattern at `:1559-1573` — but `38-RUNBOOK.md:3` names the plans as source of truth and `38-05-PLAN.md` is `autonomous: true`, so an executor gets the literals.
- **Files:** `38-05-PLAN.md:305, 311, 328`.
- **Fix:** Port run-book step 15's derivation into Task 2: build the groups by path from the step-2 query, assert they equal {27,28,29} / {31,32} / {25,26}, abort otherwise, and run the PATCH loops in the same parsed unit as the assertion.

**5. DI-03 — CA writes a false clause onto alert #27**
- **Breaks:** one permanent dismissal comment.
- **Scenario:** `38-05-PLAN.md:304` says "Secret values are read by getpass and passed straight to store.set()". `:305` applies it to #27, which the plan's own table at `:103` maps to `core/cli/setup.py:108` — the `--migrate` branch, where values come from `os.environ.get` at `core/credentials.py:406` and getpass is never called. A reviewer opening `:108` finds neither getpass nor store.set. The conclusion ("never reach a print or a log call") is true; the mechanism is not. `38-02-PLAN.md:411` already draws the distinction CA collapses. A second non-getpass write path exists at `setup.py:65-90` (`_prompt_visible` → `store.set` at `:85`), so it is two counterexamples, not one.
- **Files:** `38-05-PLAN.md:304`; byte-identical `$ca` at `38-RUNBOOK.md:1580`; pinned by len=508 in `38-06-PLAN.md`'s step-4a table.
- **Fix:** Replace the clause with a both-branches version (interactive via `_prompt_secret` at `setup.py:15-25`, called `:123`; `--migrate` via `credentials.py:406-409`), or split CA into a #27 string and a #28/#29 string. Must be changed in all three places or 38-06's length check breaks.

**6. ML-3 — the phase merges a measurably false statement about PR #23 to master**
- **Breaks:** the FINAL GATE record, under an acceptance criterion.
- **Scenario:** `38-06-PLAN.md:419-426` dictates recording that #23 "is already permanently unmergeable" and that "SCAN-07 adds a fourth unsatisfiable context"; `:580-582` makes it an acceptance criterion; `38-RUNBOOK.md:2093` repeats it; Task 3 step 6 merges the file to master. Measured now: `mergeable: true, mergeable_state: clean`, and there is no required-contexts list to add a fourth to. There is no re-measure step anywhere in 38-06. The mechanism half is true and verified (check-runs on `f2b8d96` are only `CodeQL`, `Analyze (python)`, `Analyze (actions)` — a `GITHUB_TOKEN`-pushed head never gets `pull_request` runs); the conclusion is not.
- **Files:** `38-06-PLAN.md:419-426, 580-582`; `38-RUNBOOK.md:2093`.
- **Fix:** Re-measure `.mergeable, .mergeable_state` at execution and record the value with its date. State the durable mechanism separately from the contingent consequence. Same pass should reconcile `38-CONTEXT.md:84-88`, `38-RUNBOOK.md:200`, `HANDOFF.json:48`, `37-VERIFICATION.md:123`, all of which assert a public repo.

## Refuted findings worth knowing

None were refuted — all 8 blocking findings survived both lenses. What the verifiers *corrected* is worth carrying:

- **The `for N in $G1` loops never fire.** DI-01's second verifier walked 38-05 literally: step 1's derivation 403s, so `$G1..$G4` are empty and the PATCH loops iterate zero times. Zero dismissals, not 19 wrong ones. Worse, step 1's "if it contains fewer, record which closed on their own" invites recording a false zero for 19 untouched alerts.
- **The poisoned revert file is one null entry, not an empty array.** `$null | ForEach-Object` runs once, so `rsc-revert.json` becomes `{"strict":null,"checks":[{"context":null,"app_id":null}]}`. The run-book's "must contain exactly three checks" guard at `:1811` does still fire on it — that is a real operator stop, and the only thing standing between a 403 and a blind protection PATCH.
- **F1's blast radius is smaller than written but the signal is worse.** No bogus commit lands; `git commit` says "nothing to commit". Nothing at all flags the loss until the end-of-task branch check, after the fact.
- **DI-04's "no stop-on-mismatch" is overstated.** Group C does have a pre-mutation gate at `:314-323`. Groups A and B do not, and they PATCH first.

## Advisory findings

**dismissal-integrity**
- DI-05: `G1..G4` assigned in step 1's fence, consumed in later fences; shell state does not persist across harness calls, so the 19 dismissals can silently no-op. `38-05-PLAN.md:149-233`.
- DI-06: CB asserts a CodeQL `primaryLocationLineHash` fingerprinting claim that no step ever measures. `38-05-PLAN.md:310`.

**dev-branch-delete** (dimension PASS)
- DEV-01: 38-06's guard-asymmetry justification maps `[ "$AHEAD" -eq 1 ]` to run-book step 11(b)/(c), but those are two branches of one `ancestor_exit` reading; no AHEAD gate exists. `38-06-PLAN.md:336-340`.
- DEV-02: step 11(b) routes to an unwritten, unwrapped branch delete; step 15 cannot serve that path because its third guard resolves the tag that 11(b) just skipped. Fails closed, but the block is missing. `38-RUNBOOK.md:1882`.

**merge-lockout**
- ML-4: the pre-built revert restores the producer-less `CodeQL` context, so running it leaves master just as blocked. `38-RUNBOOK.md:1801-1811, 2155-2163`.
- ML-5: 38-04 blames a missing `CodeQL` check on the SCAN-06 file deletion; the file workflow's job is `name: Analyze` and never produced a check named `CodeQL`. `38-04-PLAN.md:128-130`.
- ML-6: four passages record the repo as public as load-bearing rationale; it is private. `38-03-PLAN.md:317-319`, `38-RUNBOOK.md:1892, 2226`, `38-04-PLAN.md:327`.

**workflow-mutations**
- WF-03: the ROADMAP diff bound `grep -c "^[+-][^+-]"` returns 0 under the mandatory rtk hook, so it passes no matter what changed. `38-03-PLAN.md:371`.
- WF-04: ROADMAP.md:210 says "three files"; the plan authorizes and edits four, and no plan may fix line 210.
- WF-05: plan and run-book mandate different literal ROADMAP annotation strings; the run-book's `Select-String` check is keyed to its own. `38-RUNBOOK.md:988` vs `38-03-PLAN.md:331-333`.
- WF-06: step 19's tag resolver splits `owner/repo/path@tag` on `@` and 404s on the two `codeql-action` subpath refs. `38-RUNBOOK.md:916-918`.
- WF-07: pinning `gitleaks-action` does not pin the gitleaks binary it downloads at run time; `GITLEAKS_VERSION` is unset. `.github/workflows/gitleaks.yml:28`.

**38-01/38-02**
- F3: VERDICT-SCAN-01 has no machine-checkable contract and fails open; every check tests only the `##` heading, and the declared `key_link` pattern matches the heading. `38-01-PLAN.md:375, 379-381`.
- F4: the negative control demands "at least two tests FAIL" from a mutation that can only break one. `38-02-PLAN.md:382-384`.
- F5: the run-book's hardcoded expected `$PLANSHA` (`910e31d`) predates the remediation and names a tree where 38-RUNBOOK.md does not exist. `38-RUNBOOK.md:106`.

**coherence**
- COH-02: ROADMAP.md:210 "three files" vs four (same as WF-04).
- COH-03: 38-03 and 38-04 assign alerts #33/#34 to opposite ci.yml jobs. `38-03-PLAN.md:112` vs `38-04-PLAN.md:76-77`.
- COH-04: five assertions that `git status --porcelain` is empty are false because the phase deliberately leaves `.continue-here.md` untracked and unignored; run-book step 40 contradicts 38-03's own written carve-out. Risk: an executor "fixes" it by `git add`ing the phase dir and lands `.continue-here.md` on master.
- COH-05: run-book BACKGROUND instructs an unauthorized STATE.md rewrite, timed "anytime", that step 37's `git add` would sweep into the ci(38-03) commit. `38-RUNBOOK.md:2241`.
- COH-06: run-book Block 6 step 37 opens and merges a second PR to master that no plan authorizes, after the revert path has been declared finished. `38-RUNBOOK.md:2196-2205`.
- COH-07: same AHEAD/ANCESTOR_EXIT mismapping as DEV-01, from the coherence side.

## Coverage honesty

- **Unverified blocking findings: none.** No dimension exceeded its verify cap; all 8 went through both lenses.
- **Dimensions returning nothing: none.** All six produced results. `dev-branch-delete` and `coherence` returned PASS/no-blockers on their merits, not by omission.
- **Not checked, and you should know it:**
  - No mutation was ever attempted. Every 403 above is from a GET on the same gated feature. The exact HTTP failure mode of the two `PATCH /repos` secret-scanning calls and the `PATCH .../code-scanning/alerts/$N` calls is inferred, not measured. It does not change the outcome — the verifies at `:455` and `:242` fail against the null regardless.
  - GHSA-g6cj-pr64-35w5's `first_patched_version` was never fetched. No network call was made for it. 38-02 reads it live rather than hardcoding, which is the correct structure, so this is deliberately left to execution.
  - The `.continue-here.md:67` claim of "3 blocks wrapped and proven unreachable across 27 failure runs" was not audited. Only step 15's wrapper was independently guard-tested (three injected failure states, delete stubbed, all threw). Block 3 step 11 and Block 5 step 1620 were not.
  - Whether GitHub reuses code-scanning alert numbers after a disable/re-enable cycle could not be tested (every endpoint 403s). DI-04's worst-case framing rests on that; its mechanism does not.
  - `38-01-PLAN.md:321` calls `core/credentials.py:215-270` "the only cryptography call sites"; `core/session_store.py` also constructs Fernet at `:59` and `:89`. Task 3's expected-values text does name session_store, so the artifact will be correct — annotation only.
  - Run-book Block 2 step 6 cites `main.py:50-53` / `core/cli/run.py:30-37` where source says 49-52 / 29-36. Both ranges contain the real alert lines. Noted, not filed.

## Remediation checklist

Ordered. Items 1 and 2 are operator decisions and block everything after them.

1. **Decide the repository posture.** Restore public + GHAS + branch protection, or accept private-Free and re-scope SCAN-01/03/04/07/08. Do not flip visibility on my say-so. Nothing else in this list matters until this is settled. *(DI-01, ML-1, WF-01)*
2. **Re-measure every planning-time GitHub fact from live 200s** and rewrite them: alert numbers 3-34 and the 31-alert total, the required-contexts list and `app_id`s, `enforce_admins`/`required_pull_request_reviews`, `.visibility`, and `pulls/23.mergeable_state`. Sources to correct: `38-CONTEXT.md:86-92, 130`, `ROADMAP.md:220`, `.continue-here.md:103`, `HANDOFF.json:48`, `37-VERIFICATION.md:123`, `38-04-PLAN.md:60-67`. *(ML-6, ML-3)*
3. **Add the wave-0 hard gate to 38-01 Task 1:** code-scanning alerts must return 200 and `branches/master.protected` must be `true`, else HALT with the HTTP status recorded. Rewrite `38-RUNBOOK.md:78` and `:166` so a 403 is not diagnosed as auth. *(DI-01, ML-1)*
4. **Fix the F1 gate:** widen `38-01-PLAN.md:111` to all four carry-over paths, add `set -e`, wrap the run-book equivalent at `:111-118` in `& { $ErrorActionPreference='Stop'; ... }` with an explicit `$LASTEXITCODE` throw after `checkout -B`. *(F1)*
5. **Fix WF-02's false-green:** rewrite `38-RUNBOOK.md:1038` and `:1840` to assert exit 0 on a `--jq` read and STOP on any 403; rewrite `:1033`'s failure text to name the 403 case and forbid a protection write. *(WF-02)*
6. **Bind 38-05 Task 2 to live data:** derive the three groups by path from the step-2 query, assert equality with the table, abort on mismatch, run PATCHes in the same parsed unit. *(DI-04)*
7. **Correct the CA clause** in `38-05-PLAN.md:304`, `38-RUNBOOK.md:1580`, and 38-06's step-4a length/mid table together. *(DI-03)*
8. **Replace 38-06's dictated #23 statement** with a measured one, in `38-06-PLAN.md:419-426`, its acceptance criterion at `:580-582`, and `38-RUNBOOK.md:2093`. *(ML-3)*
9. **Sweep the advisories** while the files are open — DI-05, F3, F4, F5, WF-03, WF-05, COH-03, COH-04 are all cheap and several (COH-04, WF-03, F5) can each produce a wrong outcome on their own.

**No plan in Phase 38 may execute until a subsequent gate run returns PASS.** That includes 38-01, which is read-only recon but will 403 in wave 1 and cannot produce the SCAN-06 or cryptography verdicts three later plans gate on.

Third FAIL, third time on irreversible operations. The plans themselves are in materially better shape than run 2 — the per-alert reasoning, the string coherence, and the branch-delete guards all hold up under byte-level and injected-failure testing. What killed this run is that the repository moved out from under the plans a month ago and nothing in the phase looks.

It is past 11pm Eastern. This is a stop-and-decide list, not a tonight list. The visibility decision at item 1 will still be the same decision in the morning.