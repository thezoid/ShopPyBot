**VERDICT: FAIL**

Rule triggered: 14 confirmed blocking findings (each survived both an independent refute pass and an independent reproduce pass). Zero unaudited dimensions; zero unverified blocking findings. FAIL rests on confirmed blocking alone.

This is gate run 5 and the fifth consecutive FAIL. The failure mode has changed: runs 1 through 4 failed on defects present in the original plans. Run 5 fails on defects the remediation passes themselves introduced or left half-landed — a fix that reached one artifact and not its mirror, an acceptance criterion tightened in the plan while the operator path was left split, one false claim about PR #23 replaced by a different false claim. Spot-verified two load-bearing claims directly: `38-05-PLAN.md` contains 0 occurrences of `VERDICT-SCAN-06|SAFE-TO-DELETE|DEFER`, and `38-RUNBOOK.md` step 4's `& { }` ends at "REVERT FILE READY:" with the `PUT` living in step 5's separate fence. Both confirmed.

---

## 1. Blocking findings

Ordered by irreversibility of the damage, then by how easily an executor reaches it.

### B1 — DI-03 · dismissal-integrity · unguarded outbound transmission of candidate secrets
**Breaks:** PATCH 2 (`secret_scanning_validity_checks: enabled`) is a bare, unguarded block in both plan and run-book. It is the only action in the phase that leaves the repository boundary and the only one that cannot be un-sent. Nothing reads the current settings, nothing asserts the step-4 poll happened, and step 4's "if it is a live credential, stop" has no mechanical form. Worse, step 4 asks the executor to read `.validity` to judge liveness — a field that reads `unknown` until the very setting PATCH 2 enables.
**Scenario:** PATCH 1 turns on non-provider patterns, which backfills over history. `config.yml` was committed to this public repo (commits `2e8f689`, `c692580`) with keys `amz_pwd`, `bb_password`, `bb_cvv`. Alerts surface. The executor (`autonomous: true`) records them, cannot evaluate liveness, and submits step 5 in the next invocation. Real personal credentials are transmitted to their issuing providers.
**Where:** `38-05-PLAN.md` Task 3 step 5; `38-RUNBOOK.md:1965-1972`.
**Fix:** One `& { }` containing: re-read `.security_and_analysis`, throw unless non-provider is `enabled` and validity still `disabled`; re-enumerate `secret-scanning/alerts?state=open` and throw unless the count is literally `0`; only then PATCH. Do not use "equals the recorded candidate count" — 0 equals 0 defeats it.

### B2 — DI-01 · dismissal-integrity · group C dismissal has no VERDICT-SCAN-06 gate (plan side)
**Breaks:** `38-05-PLAN.md`'s group C fence writes `CC`, asserting in the past tense that `codeql-analysis.yml` "was deleted in Phase 38 (SCAN-06)". The run-book has the gate (`:1852` throws unless SAFE-TO-DELETE); the plan has none. Verified: 0 occurrences of `VERDICT-SCAN-06`, `DEFER`, or `SAFE-TO-DELETE` anywhere in the file.
**Scenario:** 38-01 measures DEFER (condition b fails on frozen PR-24 check runs). 38-03's DEFER arm prints and continues — it does not exit. 38-04 tolerates it (`under the SAFE-TO-DELETE branch` qualifiers). 38-05's two guards both pass under DEFER: `GC="25 26"` unchanged, and `LIVE` filters *out* the `codeql-analysis.yml` categories, so it cannot see the file's existence either way. Two permanent, public dismissal comments assert a deletion that did not happen.
**Where:** `38-05-PLAN.md:471-480`, string at `:478`; also `:115` states the deletion unconditionally.
**Fix:** As the first line inside that same fence, read `## VERDICT-SCAN-06` from `38-SCAN-BASELINE.md` using 38-03's own `grep -A1 … | sed -n '2p'` shape plus the duplicate-heading check, and `exit 1` on anything but SAFE-TO-DELETE. Reword `:115` to "on the SAFE-TO-DELETE branch."

*(XDOC-02 is this same defect found independently by the coherence dimension. One fix closes both.)*

### B3 — DI-02 · dismissal-integrity · 19 dismissals in the run-book have no guards at all
**Breaks:** Run-book steps 5, 5.1, 5.2, 5.3 are four bare `foreach ($n in $gN) { PATCH }` blocks with no `& { }`, no re-derivation, no set assertion, no count guard, no empty-group guard. The plan they mirror puts all of that in one fence. Guard census: Task 1 region has one `& {` and one `throw`, both in the precondition; Task 2 region has 8 and 13.
**Scenario A (silent no-op):** step 3's derivation does not check HTTP status and pipes straight to `ConvertFrom-Json`; a 403 yields empty-but-defined `$g1..$g4`. All four loops iterate zero times, print nothing, leave `$?` True. Measured on this box: `foreach` over an empty or undefined variable is 0 iterations, no error. Four checkboxes get ticked, 19 alerts recorded as dismissed, zero PATCHes issued.
**Scenario B (drift):** a post-merge analysis adds a `tests/test_cli_*` finding; it lands in `$g1`; C1's very specific claims about `capsys.readouterr().out` and a patched `core.service.BotService` get written permanently onto an alert nobody opened.
**Where:** `38-RUNBOOK.md:1596-1677`.
**Fix:** Rewrite 5 through 5.3 in the shape steps 16/17/19 already use: open `& {`, re-derive the group from a fresh path-filtered query, `throw` on set mismatch (`"6 7 8"`, `"9 10 11 12 13 14 15"`, `"16 17 18 19"`, `"20 21 22 23 24"`), then PATCH — all in one brace. Convert the count-19 and 6..24 HARD GATEs from prose to `throw`.

### B4 — ML-02 · merge-lockout · stored SCAN-08 procedure wipes or unbinds SCAN-07's checks
**Breaks:** Two defects in the block 38-03 commits verbatim into `38-SCAN-BASELINE.md` for milestone close. (a) On the ordinary success path it projects `.required_status_checks.contexts`, not `.checks` — dropping every `app_id: 15368` binding. Reproduced with jq 1.8.1: emitted body has `grep -c app_id` = 0. The phase forbids this in three other places ("a weakening dressed as a hardening. Never send `contexts`"). (b) On a non-200 pre-read that yields empty stdout, `RSC` resolves to `null` and the guard passes on `. == null`, emitting `{"required_status_checks": null}` — deleting the gitleaks gate SCAN-07 exists to create. The two read-backs only check `enforce_admins` and review count, so the wipe is invisible.
**Scenario:** milestone close, months from now, operator pastes the stored block. Required checks silently lose their app binding (any app may then report a context by that name) or vanish entirely.
**Where:** `38-03-PLAN.md:407-424`; propagated by `38-RUNBOOK.md:1065`.
**Fix:** Read and pass through `.required_status_checks.checks` unchanged; replace `|| echo '{}'` with a status-value guard that hard-fails on anything but 200; add a third read-back asserting `[.checks[].context] | sort` equals the three contexts with every entry at `app_id=15368`.

### B5 — ML-03 / XDOC-01 · merge-lockout + coherence · SCAN-07 guards and PUT split across two invocations
**Breaks:** `38-06-PLAN.md:203-206` requires the producer guards, before-state guard, revert-file guard and the `PUT` in one parsed unit, and `:356-359` makes a split submission `NOT MET` "even when the resulting protection object looks correct." The run-book's step 4 `& { }` (2058–2101) contains every guard and no mutation; the `PUT` is alone in step 5's fence at 2112, gated only by prose. Verified directly. Concatenating both fences does not fix it — a `throw` inside the block terminates the block, and the two statements after it still run.
**Scenario:** step 4 throws `FATAL:` (a producer `in_progress`, gitleaks `startup_failure`, or — worse — the `200` before-state branch). A driver logs it and submits the next checkbox. The `PUT` lands with no producer evidence and, on the `200` branch, overwrites an existing protection object with no revert file on disk; step 32's recovery is a `DELETE`, leaving master less protected than it started.
**Where:** `38-RUNBOOK.md:2053` (header asserts a property the block does not have), `:2110-2113`.
**Fix:** Move lines 2111-2112 inside step 4's `& { }`, after the `REVERT FILE READY:` line. Nothing in step 5 reads a variable step 4 lacks. Keep `[DECIDE]` as a read-before-paste checkbox above the combined block.

### B6 — INERT-01 · inert scanning · 38-04 deadlocks the phase with a false halt cause
**Breaks:** 38-04 Task 2 step 4 builds `$live` by filtering on `most_recent_instance.category -notlike '.github/workflows/codeql-analysis.yml*'`. Alerts #33/#34 carry `/language:actions` at commit `bd70601f` — stale, but not that category. So `$live.Count` = 2 and the block throws: "still reproduces … at $msha. The permissions block did not close it." Both halves false: no analysis exists at `$msha`, and the same block verified `permissions:` present four lines earlier. The filter tests category, never `commit_sha` against `$msha`.
**Scenario:** deterministic. Phase halts in wave 4. 38-04 Task 3, all of 38-05 (26 dismissals), all of 38-06 (gitleaks required check, dev archive, FINAL GATE) never execute.
**Where:** `38-04-PLAN.md:388`; mirror `38-RUNBOOK.md:1445`.
**Fix:** Make it three-way inside the same `& { }`: add `$stale = @($wp | ? { $_.most_recent_instance.commit_sha -ne $msha })`; if `$wp.Count -eq 0` SCAN-05 proven; elseif `$stale.Count -eq $wp.Count` throw an UNKNOWN halt naming the stale sha and `created_at` and hand to 38-06; else the existing halt, which is true only in that branch. **Do not** simply add the SHA test to `$live` — that converts this stall into a false pass.

### B7 — INERT-02 · inert scanning · the run-book forwards the stale-analysis risk to steps that do not handle it
**Breaks:** `38-RUNBOOK.md:1250` says the SCAN-05 evidence risk "is handled at steps 19 through 22." It is not. Step 20's only guidance is "keep polling" (unbounded). Step 21's entire outcome line is an expectation that cannot come true. Step 22 demands a `results_count` from an empty listing. Steps 24-26 are gated on "after the merged-SHA analysis exists" and so gate out. Greps over all 2,710 lines: `timeout`/`timed out`/`Expect this poll`/`has not analysed`/`stale analysis` = 0 hits; `operator action` = 1 hit, about credential rotation.
**Scenario:** the operator reaches step 21 with no defined branch and no recorded operator action, then hits B6's halt with the wrong stated cause and is sent back to "fix" a Block 3 edit that already landed.
**Where:** `38-RUNBOOK.md:1250`, `:1398-1407`, `:1457-1474`.
**Fix:** Port `38-04-PLAN.md:327-344` into step 21 as the **expected** outcome, not a fallback: the newest-analysis row with `created_at`, the four prohibitions, and the explicit handoff to Block 6 with "default setup has not analysed master since 2026-08-06" recorded as an operator action. Correct `:1250` to point at it.

### B8 — ML-01 / INERT-03 · merge-lockout + inert · ROADMAP criterion 2 still demands a producer-less CodeQL merge gate
**Breaks:** `.planning/ROADMAP.md:201` requires master to be unmergeable without "gitleaks, CodeQL, and the test matrix." 38-03's mandated annotation defers only the admin clause, and `38-03-PLAN.md:448` justifies that scope with a false statement ("the gitleaks, CodeQL and test-matrix half lands in this phase"). It does not: `38-06-PLAN.md:182` excludes CodeQL and `:331` makes a four-entry set an automatic NOT MET. `38-RUNBOOK.md:1073` then records "criterion 2 no longer asserts a criterion this phase deliberately does not meet" — false after the edit. `38-03-PLAN.md:21` is a `must_haves.truths` entry asserting the CodeQL required check "still has a producer," directly contradicted by 38-06's table.
**Scenario:** no in-phase lockout — three guards prevent it. The harm is durable: the phase merges to master a criterion instructing a future reader (most likely the milestone-close operator, who is also setting `enforce_admins: true`) to add a required context nothing emits. That would be unbypassable even by the owner.
**Where:** `.planning/ROADMAP.md:201`; `38-03-PLAN.md:21`, `:448`, `:465-467`; `38-RUNBOOK.md:1073`.
**Fix:** Extend the appended annotation **in place** on line 201 (do not add a corrections bullet — `38-03-PLAN.md:510` binds the diff to 1 added / 1 removed line) to also defer the CodeQL clause, citing `languages: []`, `updated_at: null`, last analysis 2026-08-06 at `bd70601`. Correct `:448`, `:21`, and `38-RUNBOOK.md:1071`+`:1073`. `38-RUNBOOK.md:1071` must carry the identical canonical string or the two documents disagree.

### B9 — XDOC-03 · coherence · mandated false history about PR #23 merged to master
**Breaks:** `38-06-PLAN.md:715-720` mandates recording that master had **zero** required contexts "at every reading since," that #23 was "never held by branch protection," and that SCAN-07 creates "the first required contexts master has ever had." `:965` makes the ZERO count an acceptance criterion "for the period #23 was open." Measured: #23 opened 2026-08-03T15:25:27Z, merged 2026-09-07. `ROADMAP.md:159` (verified live 2026-08-02) and `38-CONTEXT.md:87-88` (gathered 2026-08-03) both record three required contexts with `strict: true`. `38-06-PLAN.md:683-686` records #23's head carrying neither test leg — i.e. held. `38-06-PLAN.md:178` contradicts `:723` inside the same file. This is the second consecutive gate run at which this paragraph has carried a measurably false claim (run 4's ML-3 was its predecessor).
**Scenario:** the executor cannot write the true record without failing `:965`. The false history is dictated by `[SAY TO CLAUDE]` at `38-RUNBOOK.md:2441` into `38-SCAN-BASELINE.md` and merged to master.
**Where:** `38-06-PLAN.md:715-720`, `:723`, `:965`, `:967`; `38-RUNBOOK.md:2119`, `:2441`, `:2595`.
**Fix:** Record two periods bounded by dated readings — three required contexts at the 2026-08-02 and 2026-08-03 readings while #23 was open; `404` at every reading from 2026-09-06 onward; transition attributed to privatization and not independently timestamped. Replace "ever had" with "since the pre-privatization object was destroyed" at all four sites. Rewrite `:965` to demand the two-period record.

### B10 — RS-01 · recon/source · `rtk git status --porcelain` prints `ok` on a clean tree
**Breaks:** Measured on this box (rtk 0.37.2, pwsh 7.6.3), reproduced in the project repo and a scratch repo: `rtk git status --porcelain -- <paths>` returns the 4-byte string `ok` when raw git returns nothing. `ok` is truthy. `38-RUNBOOK.md:35` records the opposite as verified fact. The plan's bash gate uses `$( )`, which the hook does not rewrite, so it is correct — the pwsh mirror is not.
**Scenario:** Block 0 step 2, the phase's first mutating step, throws `ABORT: uncommitted changes in a carry-over path: ok` on a clean tree. The run-book is unpassable at its opening move. Fails closed, but the operator is stopped at step one and told a falsehood.
**Where:** `38-RUNBOOK.md:35`, `:126`, `:129`, `:153`, `:793`, `:796`, `:2290`, `:2293`; criteria at `38-01-PLAN.md:503`, `:537`, `38-02-PLAN.md:462`, `:500`, `38-03-PLAN.md:238`, `:549`.
**Fix:** Use `rtk proxy git status --porcelain` at every site whose output is tested for **emptiness** (the list above). Delete the false claim at `:35` and replace with the measured behaviour. Sites expecting non-empty output (`:454`, `:842`, `:1149`, `:1173`, `:2459`) are correct and must not be touched.

### B11 — RS-02 · recon/source · `.planning/STATE.md` silently dropped by the carry-over
**Breaks:** `rtk proxy git diff --name-status origin/master..HEAD` returns `M .planning/STATE.md`, divergent via commit `400458d`. `38-01-PLAN.md:120-123` names four paths and omits it. The divergence is committed, so the porcelain gate cannot fire. The post-commit criterion at `:267-270` is evaluated on the **new** branch, where `origin/master..HEAD` can only enumerate what the carry-over commit wrote — it is a tautology, yet it is labelled "proving the carry-over dropped nothing."
**Scenario:** reproduced end-to-end in a throwaway repo: the block completes exit 0, silently, and **all seven acceptance criteria pass** while STATE.md's gate-run-4 record is gone. 38-03 then successfully edits the truncated file (its anchor survives on master) and 38-04 merges it. Recoverable only from the `chore/v4.0-milestone-close` ref, which nothing surfaces.
**Where:** `38-01-PLAN.md:120-123`, `:186`; `38-RUNBOOK.md:144`.
**Fix:** Add `.planning/STATE.md` to the `set --` list (gate and restore read the same list). Move the `git diff --name-status` confirmation **above** the fenced block, capture it to a file, and make the post-commit criterion a diff of the captured pre-checkout listing against the post-commit one. Refresh `:186` and `38-RUNBOOK.md:144` off that measurement.

---

## 2. Refuted findings worth knowing

Findings the verifiers killed or narrowed, where the correction changes what the remediation must do.

- **DI-03's proposed fix was itself broken.** "Throw unless the open alert count equals the reviewed candidate count the operator recorded (0 by default)" passes trivially when an unpolled executor reads 0 — 0 equals 0. The guard must be `count == 0` literally, or a written clearance token read inside the same brace. Corrected in B1.
- **INERT-01's obvious fix creates a false pass.** Adding the SHA test to `$live` alone makes `live: 0` read as *SCAN-05 proven* with no analysis behind it — converting a safe stall into the exact failure this gate exists to prevent. The three-way branch is mandatory. Corrected in B6.
- **ML-03's first named trigger does not produce harm.** A `test (windows-latest)` at `in_progress` is excluded from `$SET_P` and throws, but it *is* reporting and will complete; requiring it blocks nothing. The reproducing states are `startup_failure` and — stronger, and not in the original finding — a `200` before-state, where the `PUT` overwrites an existing protection object with no revert file captured.
- **ML-02's Path A trigger is much narrower than claimed.** `gh` writes HTTP error bodies to **stdout**, so a 403/404 makes `PRE` malformed and `jq --argjson` dies (exit 2). The null-wipe needs empty stdout (transport/auth failure, empty-bodied 5xx). Path B — the ordinary success path dropping every `app_id` — needs no adverse state at all and is the load-bearing half.
- **DI-02's "false in both directions" is half right.** "The loop can only touch alerts you inspected" is an upper-bound claim; a zero-iteration loop does not falsify it. The drift direction is the valid half. Also note step 4 spot-checks one alert per shape, so "alerts you inspected" is already 4 of 19 by design.
- **The dismissal reasoning itself survived per-alert checking.** All 26 cited source lines were opened, not four. All seven strings are byte-identical between plan and run-book; all 21 len/mid values in the two audit tables match what a parser computes from 38-05's current text. `#25`/`#26`'s staleness premise is independently true on `/instances`. There is no real credential exposure hiding behind the seven clear-text dismissals. **The substance is sound; every blocking defect is in the guard structure around it.**
- **The `origin/dev` delete is now correct on both paths and could not be broken.** Twelve fixture cases against a stubbed binary produced no mutation on any failure shape, including annotated-tag, empty `$DEVSHA`, trailing-CR, and every 404. The predicted "third mechanism" does not exist. The only surviving items there are two advisories.
- **XDOC-03's severity is arguable.** The false text lands in markdown a later commit can edit — not irreversible like a dismissal comment. It stays blocking because `:965` makes writing it an acceptance criterion and because it is the second run in a row this paragraph shipped a false claim about #23.

---

## 3. Advisory findings

**dismissal-integrity**
- DI-04 — Task 1 guards total count and non-emptiness but never per-group set equality; groups A/B/C get the stronger form and the 19 do not. `38-05-PLAN.md:242-274`.
- DI-05 — 38-05 never records that code scanning is inert; the C1–C4 closing clause ("so a future finding in these files still surfaces") overstates what the mechanism buys with `languages: []`. `38-05-PLAN.md:30-46`, `:253/:258/:265/:272`.

**dev-branch-delete**
- DBD-02 — the archive-tag POST is the only SCAN-10 mutation with no `& { }`, no throw, and no `if it fails:` clause; the POSIX original got abort-on-failure free from `set -euo pipefail`. `38-RUNBOOK.md:2194-2201`.
- DBD-03 — the post-delete `refs/heads/dev lines = 0` check fails open (a nonzero exit with empty stdout reads as the success value); backstopped by the status-value check, so it cannot alone cause a false record. `38-RUNBOOK.md:2267-2268`, `38-06-PLAN.md:445`.

**merge-lockout**
- ML-04 — three surviving assertions that CodeQL "is currently a REQUIRED status check," one inside an IRREVERSIBLE warning at a `[DECIDE]` gate, refuted by a live `404`; exactly the priming needed to talk an executor into keeping CodeQL in the PUT. `38-RUNBOOK.md:944`, `38-01-PLAN.md:38-41`, `38-CONTEXT.md:97`.

**inert scanning**
- INERT-04 — 38-04 Task 2's acceptance criteria are unsatisfiable: bullet 1 blesses the timeout, bullets 2/5/6 require outcomes only a fresh analysis produces. `38-04-PLAN.md:412`, `:416-437`.
- INERT-05 — the operator remedy offers a manual dispatch as an equal alternative to reconfiguration; with `languages: []` a dispatch cannot produce the needed categories, and 38-04 never records the `languages: []` reading at all. `38-04-PLAN.md:327-344`.
- INERT-06 — 38-01's baseline reads neither `analyses` nor `default-setup`, so `38-SCAN-BASELINE.md` presents 31 alerts as a live pre-change measurement with no provenance; the before/after delta becomes a count of the phase's own dismissals. `38-01-PLAN.md:205-222`.
- INERT-07 — the FINAL GATE vocabulary cannot express "fix landed, never re-analysed"; SCAN-03/SCAN-05 must read `NOT MET`, indistinguishable from "the fix failed," while the dismissal-resolved rows read `MET`. `38-06-PLAN.md:660-680`.
- INERT-08 — run-book step 23 expects #33/#34 to reach `state=fixed` on their own, which no dismissal or code change can produce. `38-RUNBOOK.md:1423`; source claims at `38-03-PLAN.md:125`, `:161`.

**recon / source changes**
- RS-04 — 38-02 names five clear-text alerts; there are seven, #25/#26 are never mentioned, and #31 is assigned the wrong rule. `38-02-PLAN.md:407-408`, `:31`.
- RS-05 — `grep -c "host_matches" core/cli/run.py >= 3` fails against the exact prescribed edit (both calls on one line; measured 2). `38-02-PLAN.md:248-249`.
- RS-06 — the VERDICT-SCAN-06 verify is still heading-only, so 38-01 can complete with an empty verdict section; only 38-03 catches it, after 38-02 has committed source. `38-01-PLAN.md:351`, `:25`.
- RS-07 — the cryptography-import grep is unscoped and sweeps `.venv/` (261 hits vs 3 project hits), while the criterion says to record "every line found in the tree." `38-01-PLAN.md:408`, `:490-491`.
- RS-08 — the pin guard hardcodes the `50.0.0` floor instead of deriving it from VERDICT-SCAN-01, so nothing mechanically couples the task to the verdict it claims to be gated on. `38-02-PLAN.md:353`.

**cross-document coherence**
- XDOC-04 — master has four pre-existing tags, not three; `shoppybot-v2.1.0` (created by the release this same plan records at `:706`) is missing from the list and from the "any of the three missing means something deleted a tag" check. `38-06-PLAN.md:129`, `:554`; `38-RUNBOOK.md:2277`, `:2279`.
- XDOC-05 — ROADMAP says 38-04 performs "no Dependabot re-query"; 38-04 Task 3 is a Dependabot re-query with a 20-minute poll. `.planning/ROADMAP.md:211`.
- XDOC-06 — ROADMAP says master pins `cryptography==50.0.0`; both manifests pin `50.0.1`. `.planning/ROADMAP.md:218`.
- XDOC-07 — the PR body and an operator readback must state "the cryptography version moved from and to," but 38-02 Task 2 was remediated into a no-op that edits neither manifest. `38-04-PLAN.md:177-180`; `38-RUNBOOK.md:1197`, `:1231`.
- XDOC-08 — 38-06 twice cites its own interfaces block as the record of the pre-privatization posture; the block contains no such record (it was rewritten to the 2026-09-08 `404` state). `38-06-PLAN.md:178-179`, `:199-201`.

---

## 4. Coverage honesty — what this run did NOT check

- **Zero unverified blocking findings.** Every blocking finding reported went through both adversarial verifiers; none was dropped for cap. There is no `unverified_blocking` id to name.
- **Zero unaudited dimensions.** All six returned a verdict; all six returned FAIL. No dimension returned nothing.
- **No mutation was ever executed.** Every finding about what a PATCH, PUT, DELETE, or merge *would* do is inference from the guard text plus fixture replay against stubbed binaries, not from performing the operation. The 26 dismissals, the branch delete, the protection PUT and the validity-checks PATCH have never run.
- **GitHub API semantics taken on documentation, not measurement:** whether `validity` returns `unknown` while checks are disabled (INERT/DI-03 mechanism 2 — mechanism 1 alone reproduces DI-03, so this does not carry the finding); whether `dismissed_comment` is genuinely uneditable after a PATCH ("permanently uneditable" is quoted from `38-RUNBOOK.md:1873`, not verified); whether GitHub's non-provider patterns detector actually fires on the historical `config.yml` key shapes.
- **The exact date master's pre-privatization protection object died is not measurable.** No audit-log access; the object is gone. B9's fix must bound two periods by dated *readings*, not assert a transition timestamp.
- **`38-SCAN-BASELINE.md` does not exist on disk.** Every claim about what 38-03/38-04/38-05 read from it is a claim about a file 38-01 will produce at run time. The DEFER branch is reachable irrespective of today's probe results.
- **Today's SAFE-TO-DELETE measurement is not a guarantee.** All three of 38-01's conditions hold as of this session (PR 24 head `db481cc` carries `CodeQL` from `github-advanced-security`; both `Analyze (*)` resolve to `dynamic/github-code-scanning/codeql`; workflow `8840986` is `disabled_manually`). Condition (c) is a mutable live setting. B2 is latent today and live the moment anyone re-enables that workflow.
- **Two things checked and deliberately not filed:** 38-02 Task 1's "three production sites" vs the comments' "exactly two" (both true under different senses — three alerts across two gates); and the run-book's step-28 note calling three `dependabot.yml` `ignore:` entries "two ignore rules" with partly wrong PR attribution (scope note in a repo doc, substance correct).
- **Not covered by any dimension's brief:** end-to-end execution rehearsal of an entire block, cross-phase interaction with Phase 39+, and whether `38-06`'s FINAL GATE table is itself internally consistent beyond the rows the six dimensions touched.

---

## 5. The inert-scanner question, answered plainly

**Code scanning is configured but dead.** `code-scanning/default-setup` reads `{"state":"configured","languages":[],"updated_at":null}`. The newest analyses on `refs/heads/master` are `/language:python` and `/language:actions`, both at `bd70601f`, both 2026-08-06. Master is `be613ee` — eighteen commits and seven merged PRs later, with zero analyses produced. Nothing in the six plans reconfigures or dispatches default setup; grep for `revive|re-enable|force an analysis|workflow_dispatch` across the run-book returns zero.

**Phase 38 cannot be meaningfully executed in this state. Default setup must be repaired first.**

Concretely, in the inert state:

- The 26 dismissals in 38-05 are the **only** state change the phase can produce. Alerts #3, #4, #5 (SCAN-03, fixed by `core.urls.host_matches`) and #33, #34 (SCAN-05, fixed by the `permissions:` block) cannot move from `open`, because their state is a property of an analysis snapshot at `bd70601f`, not of master's tree. The phase's headline claim — 31 open alerts driven toward zero by a mix of fixes and justified dismissals — degrades to "26 dismissals, and five alerts we cannot verify."
- The before/after delta the phase reports becomes an exact count of its own dismissals, and 38-01's baseline (INERT-06) records no analysis provenance that would let a later reader notice.

**No step produces a FALSE PASS as currently written.** I looked specifically and could not construct one. Every path where inertness could read as success is closed: the 26 dismissals each carry a path-derived set assertion in the same invocation as their PATCH; the `#25`/`#26` staleness premise is independently true; and dismissing #3/#4/#5/#33/#34 to reach zero is forbidden explicitly in 38-04 step 2, 38-05's objective, and 38-06 step 1. 38-06 step 22's nonzero-count catch-all ("Do NOT dismiss anything here to reach zero") backstops the end.

**What happens instead is a stall, with a false stated cause.** The phase deadlocks at 38-04 Task 2 step 4 (B6) before any dismissal and before the FINAL GATE, throwing "The permissions block did not close it" — which is false, and which sends the operator back to re-fix a Block 3 edit that already landed (B7 leaves no correct branch to take). Waves 5 and 6 never run.

**Two steps become false-pass hazards only if B6 is fixed carelessly.** Adding the `commit_sha` test to `$live` alone makes `live: 0` read as SCAN-05 *proven* against no analysis. And in run-book step 23.5, if #33/#34's category were the retired workflow's rather than `/language:actions`, `$live` would read 0 and the note at `:1451` would route both SCAN-05 alerts to Block 5 for **dismissal**. Both are one careless edit away.

**Sequencing:** repair default setup (a `PATCH` to `code-scanning/default-setup` restoring `python` and `actions` — a bare dispatch is insufficient while `languages` is empty), let it analyze master at `be613ee`, confirm #3/#4/#5/#33/#34 close on their own, **then** run the phase. That is an operator action, correctly outside the plans, and it should be the first line of the remediation checklist. If the operator declines to repair it, the phase must be re-planned with SCAN-03 and SCAN-05 explicitly carried as UNKNOWN-blocked-on-analyzer, which requires INERT-04, INERT-07 and INERT-08 fixed as well as INERT-01 and INERT-02.

---

## 6. Remediation checklist

**No plan may execute until a later gate run passes.** Not 38-01, despite being read-only recon — its output (`VERDICT-SCAN-06`, `VERDICT-SCAN-01`, the baseline inventory) is the input three later plans gate on, and RS-02, RS-06 and INERT-06 are defects in exactly that output. Nothing runs.

Ordered so each item is independently verifiable and earlier items unblock later ones.

**Phase 0 — operator action, before any plan edit**
1. [ ] Repair `code-scanning/default-setup`: restore `python` and `actions` languages, confirm an analysis lands on master at `be613ee`, and confirm #3/#4/#5/#33/#34 close on their own. Record the analysis id, sha and `created_at`. If declining, say so explicitly — items 14, 20, 21, 22 change scope.

**Phase 1 — irreversible-mutation guards (highest consequence first)**
2. [ ] **B1/DI-03** — make PATCH 2 self-guarding in one `& { }`: re-read `.security_and_analysis`, throw unless non-provider `enabled` and validity still `disabled`; re-enumerate open secret-scanning alerts and throw unless the count is literally `0`; then PATCH. Fix step 4's liveness test, which asks for a field that reads `unknown`.
3. [ ] **B2/DI-01+XDOC-02** — add the `VERDICT-SCAN-06` read + `exit 1` as the first line inside `38-05-PLAN.md:471-480`, using 38-03's `grep -A1 … | sed -n '2p'` shape plus the duplicate-heading check. Reword `:115`. Add the DEFER shape (2 open, #25/#26 itemised as blocked-on-SCAN-06) to Task 2's acceptance criteria and to `38-06-PLAN.md:948-951`.
4. [ ] **B3/DI-02** — rewrite `38-RUNBOOK.md` steps 5, 5.1, 5.2, 5.3 in the step-16/17/19 shape: `& {`, re-derive by path, `throw` on set mismatch, then PATCH. Convert step 3's two prose HARD GATEs to `throw`s. Add a status check to step 3's derivation so a 403 cannot yield empty-but-defined groups.
5. [ ] **B5/ML-03+XDOC-01** — move `38-RUNBOOK.md:2111-2112` inside step 4's `& { }` after `REVERT FILE READY:`. Keep `[DECIDE]` as a pre-paste checkbox.
6. [ ] **B4/ML-02** — in `38-03-PLAN.md:407-424`: read `.checks` not `.contexts`; replace `|| echo '{}'` with a hard-fail on non-200; add the third read-back asserting the three contexts at `app_id=15368`.
7. [ ] **DBD-02** — wrap the archive-tag POST in `& { $ErrorActionPreference="Stop"; $PSNativeCommandUseErrorActionPreference=$true; … }` and add an `if it fails:` clause naming HTTP 422 `Reference already exists`.
8. [ ] **DBD-03** — capture `$LASTEXITCODE` after the post-delete `ls-remote` and throw on nonzero, or delete the line and let the status-value check stand alone.

**Phase 2 — tooling and gate correctness (blocks execution at step one)**
9. [ ] **B10/RS-01** — swap to `rtk proxy git status --porcelain` at every emptiness-tested site (`38-RUNBOOK.md:126`, `:129`, `:153`, `:793`, `:796`, `:2290`, `:2293`; `38-01-PLAN.md:503`, `:537`; `38-02-PLAN.md:462`, `:500`; `38-03-PLAN.md:238`, `:549`). Replace the false claim at `:35` with the measured behaviour. Leave the non-empty-expecting sites alone.
10. [ ] **B11/RS-02** — add `.planning/STATE.md` to the `set --` list; move the name-status confirmation above the fenced block and capture it to a file; make the post-commit criterion a diff of captured-vs-actual. Refresh `38-01-PLAN.md:186` and `38-RUNBOOK.md:144`.
11. [ ] **RS-06** — change the SCAN-06 verify to `grep -cE "^VERDICT-SCAN-06: (SAFE-TO-DELETE|DEFER)$"` = 1 and set the key_link pattern to `VERDICT-SCAN-06: `.
12. [ ] **RS-07** — scope the cryptography-import grep to the project paths; state the expected result is 3 lines.
13. [ ] **RS-05** — lower the run.py threshold to 2, or switch both criteria to `grep -o … | wc -l`.
14. [ ] **RS-08** — derive the pin floor from VERDICT-SCAN-01 and hard-fail on empty.

**Phase 3 — inert-scanner handling (skip 15–16 only if item 1 is done and verified)**
15. [ ] **B6/INERT-01** — three-way branch in `38-04-PLAN.md:388` and `38-RUNBOOK.md:1445`. Do **not** patch `$live` alone.
16. [ ] **B7/INERT-02** — port `38-04-PLAN.md:327-344` into run-book step 21 as the expected outcome; correct `:1250`; add the analysis-absent branch to step 24's gate.
17. [ ] **INERT-04** — make 38-04 Task 2's bullets 2, 5 and 6 conditional on the analysis existing; print the newest-analysis `commit_sha` alongside the count in both `<automated>` verifies.
18. [ ] **INERT-05** — record `languages: []` / `updated_at: null` in step 2's measured-state paragraph; name reconfiguration as required and a bare dispatch as insufficient.
19. [ ] **INERT-06** — add `default-setup` and `analyses` reads to 38-01 Task 1; require an `## Analysis Provenance` section in the baseline; add it to the acceptance criteria.
20. [ ] **INERT-07** — add `NOT RE-ANALYSED` to the FINAL GATE vocabulary with its trigger condition and its operator action.
21. [ ] **INERT-08** — qualify the "closes both instances at once" claims in `38-03-PLAN.md:125`/`:161`/`38-04-PLAN.md:129`; rewrite run-book step 23's expected output.
22. [ ] **DI-05** — soften C1–C4's closing clause to a mechanism claim; add the measured default-setup state to Task 1's summary requirements.

**Phase 4 — record integrity (what ships to master)**
23. [ ] **B8/ML-01+INERT-03** — extend the criterion-2 annotation in place to defer the CodeQL clause; correct `38-03-PLAN.md:448` and `:21`, and `38-RUNBOOK.md:1071`+`:1073`. Respect the 1-added/1-removed numstat bound.
24. [ ] **B9/XDOC-03** — replace the flat-ZERO #23 record with the two-period record at all six sites; rewrite acceptance criterion `38-06-PLAN.md:965`.
25. [ ] **ML-04** — rewrite the three "CodeQL is currently a REQUIRED status check" assertions to the measured state, especially `38-RUNBOOK.md:944` inside the IRREVERSIBLE warning.
26. [ ] **DI-04** — add the four per-group set assertions beside the existing count guard in `38-05-PLAN.md:242-274`.
27. [ ] **RS-04** — correct 38-02's clear-text enumeration to seven alerts across two rules, including #25/#26 and #31's rule.
28. [ ] **XDOC-04** — add `shoppybot-v2.1.0` to the tag lists; change the run-book expectation to five names / eight lines and "the four pre-existing tags."
29. [ ] **XDOC-05, XDOC-06** — correct ROADMAP:211 (read-back, not "no re-query") and ROADMAP:218 (`50.0.1`, PR #32). 38-03 Task 3 already owns ROADMAP edits.
30. [ ] **XDOC-07** — rewrite the SCAN-01 PR-body line and the `:1197` readback to reflect that this branch changes no manifest.
31. [ ] **XDOC-08** — repoint both pre-privatization-posture citations at `38-CONTEXT.md:87-88`, or add that row to 38-06's interfaces table labelled historical.

**Phase 5 — before requesting gate run 6**
32. [ ] Re-derive the seven dismissal strings and the fourteen len/mid values after every edit to `38-05-PLAN.md`; they are byte-identical and table-checked today, and item 3 touches that file.
33. [ ] Confirm plan and run-book agree on which guards are mandatory. Today the run-book is stronger on group C (B2) and the plan is stronger on Task 1 (B3) and on SCAN-07 contiguity (B5). Fixing one side of any of those leaves the other path open.
34. [ ] Re-measure the three SAFE-TO-DELETE conditions immediately before execution. Condition (c) is a live mutable setting and B2's fix must be in place regardless of what it reads.