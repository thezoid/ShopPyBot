# Phase 38: Scanning to Zero - Context

**Gathered:** 2026-08-03
**Status:** Ready for planning
**Mode:** Autonomous, with two decisions taken by the operator via checkpoint.

<domain>
## Phase Boundary

Every security scanner attached to the repo reports zero outstanding **real** findings, and the
checks that produce them are required to merge.

In scope: closing the remaining Dependabot alert, resolving or deliberately dismissing the code
scanning queue, adding a `permissions` block to `ci.yml`, removing the superseded
`codeql-analysis.yml`, making gitleaks a required check, enabling secret-scanning options,
deleting the stale `origin/dev` branch, and SHA-pinning third-party actions.

Out of scope: SCAN-08 (see the deferral below), anything about PR #21's FastAPI breakage, and the
release PR #23 token problem.
</domain>

<decisions>
## Implementation Decisions

### Operator decisions taken at checkpoint (2026-08-03)

**SCAN-08 is DEFERRED to milestone close, after Phase 50.** Requiring pull-request reviews and
enforcing protection on admins would immediately prevent the orchestrator from landing the
remaining 12 phases without a human approval click on every PR. The operator chose to keep the
autonomous run moving and apply the lockdown once the milestone's code is in. Phase 38 therefore
closes with SCAN-08 explicitly deferred and recorded, not silently skipped.

**SCAN-10: delete `origin/dev`, but tag it first.** Operator chose deletion over documentation.

Critical detail the plan must honour: `origin/dev` is 923 commits behind master but **1 commit
ahead** (`65ef2b9`, "fix sign in check", 2025-02-23). That commit is not reachable from master.
Tag it (suggested `archive/dev-final`) and push the tag BEFORE deleting the branch, so the commit
survives. Verify the tag resolves to `65ef2b9` and is an ancestor of nothing on master before the
delete. Never force-delete without the tag landing first.

### Live scanner state, measured 2026-08-03 (not assumed)

The requirement text was written earlier and several counts have moved. Where they differ, the
measured value wins and the plan records the correction.

| Requirement claim | Measured now |
|---|---|
| SCAN-01: 7 open Dependabot alerts | **1**. Six closed as a side effect of Phase 37's dependency work |
| SCAN-02: "the two" clear-text alerts | **7**: 5 `py/clear-text-logging-sensitive-data` plus 2 `py/clear-text-storage-sensitive-data` |
| SCAN-03: 3 production url-sanitization | **3**, exact match |
| SCAN-04: 19 test-file url-sanitization | **19**, exact match |
| SCAN-05: ci.yml permissions | 2 `actions/missing-workflow-permissions` alerts open |

Total open code scanning alerts: 31 (22 url-sanitization of which 19 are under `tests/`, 5
clear-text-logging, 2 clear-text-storage, 2 missing-workflow-permissions). Secret scanning: 0.

The one remaining Dependabot alert is `cryptography` in `requirements.txt`, high severity,
"PKCS#7 EnvelopedData decryption exposes a Bleichenbacher oracle". Current pin is
`cryptography==49.0.0`. The plan must establish whether a fixed version exists and, if not,
whether the vulnerable code path is reachable from this project before deciding between upgrade,
dismissal with justification, or acceptance.

### Verification bar

- A finding is "resolved" when the alert state is closed or dismissed with a recorded reason, not
  when a code change merely looks like it should have fixed it. Re-query the API after the change.
- SCAN-04's 19 test-file alerts are to be **dismissed deliberately** with a stated reason so the
  queue reflects real findings. Deliberate dismissal is the requirement's own wording; blanket
  suppression that also hides future production findings is not acceptable.
- Any code fix for SCAN-02 or SCAN-03 must be covered by a test, because these are security
  findings and a silent regression is the failure mode.

### Claude's Discretion

- Whether SCAN-04's dismissal happens via the code scanning API per alert or via a CodeQL config
  path filter, provided production findings remain visible.
- The exact dismissal reason strings, so long as they are specific rather than "false positive".
- Plan decomposition and task ordering.
- The archive tag name for `origin/dev`.
</decisions>

<code_context>
## Existing Code Insights

### Live GitHub state, measured
- Branch protection on master: required contexts `CodeQL`, `test (windows-latest)`,
  `test (ubuntu-latest)`; `strict: true`; `enforce_admins: false`; `required_pull_request_reviews:
  null`. SCAN-07 adds gitleaks to that list; SCAN-08 would change the last two and is deferred.
- PR check names observed on PR #24: `CodeQL`, `gitleaks`, `Analyze (python)`, `Analyze (actions)`,
  `test (ubuntu-latest)`, `test (windows-latest)`, `wheel (ubuntu-latest)`, `wheel (windows-latest)`.
- `origin/dev` at `65ef2b9`, last commit 2025-02-23, carries 4 workflows:
  `app_linuxBuild.yml`, `app_macBuild.yml`, `app_windowsBuild.yml`, `codeql-analysis.yml`.

### TRAP the plan must verify before acting

SCAN-06 removes `.github/workflows/codeql-analysis.yml` from master on the grounds that default
setup replaced it. **`CodeQL` is currently a REQUIRED status check.** If the removed workflow is
what produces the `CodeQL` context rather than the `Analyze (*)` contexts, deleting it would make
a required check that can never report, permanently blocking every future merge including this
phase's own PR.

The observed check list suggests `CodeQL` comes from default setup and `Analyze (python)` /
`Analyze (actions)` come from the workflow file, which would make removal safe. **Verify this
against a real run before deleting anything.** If it turns out `CodeQL` is produced by the
workflow, the required-checks list must be updated in the same change, or the deletion deferred.

### Integration points
- `.github/workflows/ci.yml` gains the `permissions` block (SCAN-05).
- `.github/workflows/gitleaks.yml` already exists and passes; SCAN-07 makes it required.
- `logger.py` is where the clear-text findings live (SCAN-02).
- SCAN-11 SHA-pinning touches every `uses:` across all workflows on master.
</code_context>

<specifics>
## Specific Ideas

- `origin/dev`'s tag must be pushed and verified before the branch delete, not after.
- SCAN-02's requirement text says "two"; there are seven. Fix all seven or record explicitly which
  are dismissed and why.
- SCAN-11's SHA pins should carry a trailing comment naming the tag they pin, so a future reader
  can tell `@a1b2c3d # v4` from an unexplained hash.
</specifics>

<deferred>
## Deferred Ideas

- **SCAN-08** (required reviews plus admin enforcement): deferred to milestone close by operator
  decision. Must be applied after Phase 50, and must not be quietly dropped.
- PR #23's release-please token problem: needs a GitHub App, explicitly not a PAT. The operator
  raised that a PAT on a public repo with `enforce_admins: false` would let a leaked secret bypass
  branch protection entirely. Correct call. Revisit at milestone close alongside SCAN-08.
- PR #21: the safe dependency half is worth taking; the FastAPI 0.141 half unregisters
  `/api/events` and kills the dashboard SSE channel. Split, do not merge whole.
</deferred>
