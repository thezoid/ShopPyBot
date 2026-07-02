---
phase: 32-release-automation-community-readiness
verified: 2026-07-02T22:15:00Z
status: human_needed
score: 5/5 must-haves verified (locally-verifiable scope)
overrides_applied: 1
overrides:
  - must_have: "SECURITY.md and CODE_OF_CONDUCT.md carry the operator-supplied real maintainer contact, with zero remaining SECURITY_CONTACT_PLACEHOLDER@example.com occurrences anywhere in the repo (RH-07)"
    reason: "Operator was unavailable at decision time. 32-CONTEXT.md resolved RH-07 to GitHub Private Vulnerability Reporting (github.com/thezoid/ShopPyBot/security/advisories/new) instead of a published personal/business email, as a privacy-safe default that satisfies the same disclosure-channel intent (a real, working, non-placeholder reporting path) without exposing a private address on a public repo. Also note: literal ROADMAP wording says 'zero occurrences anywhere in the repo' but 11 .planning/ historical files still reference the placeholder string intentionally (audit trail, plus REQUIREMENTS.md/ROADMAP.md must quote the string to define the requirement) — scoped correctly to tracked non-.planning files per 32-RESEARCH.md Pitfall 5 and this verification's own instructions."
    accepted_by: "autonomous-default (32-CONTEXT.md decision log — operator sign-off on PVR-vs-email choice still pending, see human_verification below)"
    accepted_at: "2026-07-02T00:00:00Z"
human_verification:
  - test: "Confirm the RH-07 channel choice: SECURITY.md and CODE_OF_CONDUCT.md route vulnerability/conduct reports through GitHub Private Vulnerability Reporting only (no published email), a default chosen autonomously because the operator was away during phase discussion."
    expected: "Operator either approves the PVR-only channel as final, or requests a maintainer email be added/substituted."
    why_human: "This is a policy/identity decision (what contact the public sees), not something verifiable from the codebase — CLAUDE.md requires explicit approval for decisions the AI made in the operator's absence."
  - test: "Enable GitHub Private Vulnerability Reporting: repo Settings -> Security -> Private vulnerability reporting."
    expected: "The advisories/new link in SECURITY.md and CODE_OF_CONDUCT.md resolves to a working report form instead of 404."
    why_human: "One-time repo Settings toggle; not something the executor/verifier can or should flip autonomously."
  - test: "Widen the Actions allowlist: repo Settings -> Actions -> General -> Actions permissions -> add googleapis/release-please-action@* (and ideally gitleaks/gitleaks-action@*, carried debt from Phase 31) to the selected-actions pattern list."
    expected: "The release-please workflow run on push to master stops failing with startup_failure and actually executes, eventually opening a release PR once conventional-commit history since the 2.0.0 seed warrants a release."
    why_human: "Repo Settings change gated behind operator approval; cannot be verified or performed from the local codebase."
---

# Phase 32: Release Automation & Community Readiness Verification Report

**Phase Goal:** The repo is ready to cut its first public release — version source of truth consistent (RH-03 -> pyproject 2.0.0), release-please automates changelog/tagging seeded at 2.0.0 (RH-02), README + security/community docs accurate (RH-06, RH-07).
**Verified:** 2026-07-02T22:15:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `pyproject.toml`'s canonical version is reconciled to `2.0.0`, and it is the sole version source in the repo (RH-03) | VERIFIED | `pyproject.toml` line 7: `version = "2.0.0"`. Repo-wide grep for `__version__`, `setup.py`, `setup.cfg`, `VERSION` found none in application code — only in `.planning/` historical docs, third-party `.venv` packages, and a gitignored, untracked `shoppybot.egg-info/` build artifact (`.gitignore:36` confirms `*.egg-info/` is ignored). `core/cli/setup.py` is a CLI subcommand module (no version string), not a packaging file. |
| 2 | release-please workflow + config exist, target `python` release-type, seeded from `2.0.0`; JSON/YAML parse cleanly (RH-02, local scope) | VERIFIED | `.release-please-manifest.json` = `{".":"2.0.0"}` (matches pyproject exactly). `release-please-config.json`: `release-type: "python"`, `packages: {".": {"package-name": "shoppybot"}}`. `.github/workflows/release-please.yml`: `googleapis/release-please-action@v5`, `permissions: contents: write, pull-requests: write` (no `actions:write`/`id-token:write`), `on: push: branches: [master]`. All three parsed successfully with Python `json`/`yaml` loaders. |
| 2b | release-please Actions run turns green + opens a release PR | UNCERTAIN (operator/CI debt) | Cannot run in this sandbox. 32-01-SUMMARY.md documents the repo's Actions permissions policy is `allowed_actions: selected` with an empty allowlist — `googleapis/release-please-action` (third-party) will hit `startup_failure` until the operator adds it to the allowlist (same root cause as the pre-existing Phase 31 `gitleaks/gitleaks-action` `startup_failure`). Tracked as human_verification item below, not a code gap. |
| 3 | README accurately documents the 7-platform ecosystem, web dashboard/observability, price monitoring, anti-detection, session persistence; states Python 3.11+ prereq; documents `pip install -e .[web]` / `shoppybot` install+run; badges resolve; real clone URL (RH-06) | VERIFIED | README.md: all 7 platform names present (Amazon, BestBuy, Walmart, Target, GameStop, NewEgg, Square Enix) and each has a corresponding `plugins/shopbot_plugin_*.py` file on disk (amazon, bestbuy, gamestop, newegg, squareenix, target, walmart — 7/7 confirmed). `pip install -e .[web]` (line 69), `shoppybot` entry point (line 101, cross-checked against `pyproject.toml` `[project.scripts] shoppybot = "core.service:main"`), `Python 3.11+` (line 37 + badge line 6), clone URL `https://github.com/thezoid/ShopPyBot.git` (line 54, real repo, no placeholder). Badges (lines 3-6) reference `ci.yml`, `codeql-analysis.yml`, `gitleaks.yml` — all 3 confirmed present in `.github/workflows/` — plus one static (non-workflow) Python-version badge. No license badge (correct — no `LICENSE` file exists at repo root, confirmed absent). Credential guidance (line 84) cross-links `SECURITY.md#credentials-and-secrets`, and that heading/content exists and matches (env-var/`.env` only model, no `config.yml` credentials). |
| 4 | `SECURITY.md`/`CODE_OF_CONDUCT.md` carry a real, working security-contact channel; zero placeholder occurrences in live docs (RH-07) | VERIFIED (override — see frontmatter) | `git grep -n "SECURITY_CONTACT_PLACEHOLDER@example.com" -- ':!.planning'` returns 0 matches (exit code 1 = no match). Neither `SECURITY.md` nor `CODE_OF_CONDUCT.md` contains any email-shaped string (regex scan: zero matches in both files). Both files route reports through `https://github.com/thezoid/ShopPyBot/security/advisories/new` (GitHub Private Vulnerability Reporting) with an inline operator note that PVR must be enabled once in Settings. **Deviation from literal ROADMAP wording** ("operator-supplied real maintainer contact") — CONTEXT.md documents this was resolved to a PVR-only channel (no email) because the operator was away at decision time; see override entry and human_verification item requesting operator sign-off on this choice. |
| 4b | Private Vulnerability Reporting is actually enabled and the advisories/new link resolves | UNCERTAIN (operator debt) | Cannot verify from the codebase — this is a one-time GitHub repo Settings toggle (Settings -> Security -> "Private vulnerability reporting"). Documented inline in SECURITY.md and tracked as a human_verification item below. |
| 5 | No regression — full pytest suite stays green after the version bump and docs-only edits | VERIFIED | `.venv\Scripts\python.exe -m pytest -q` → `889 passed, 2 skipped, 4 warnings in 47.19s` — matches the documented baseline exactly (no new failures, no new skips). |

**Score:** 5/5 locally-verifiable truths VERIFIED (1 via documented override). 2 items are operator/CI-verification debt (UNCERTAIN, routed to human_verification, not counted as failures per the phase's own CONTEXT.md scope boundary).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pyproject.toml` | `[project].version == "2.0.0"`, sole version source | VERIFIED | Line 7 confirms; no competing source found |
| `release-please-config.json` | manifest-mode config, `release-type: python`, package `.` | VERIFIED | Matches expected shape exactly, valid JSON |
| `.release-please-manifest.json` | `{".": "2.0.0"}` | VERIFIED | Exact match, valid JSON |
| `.github/workflows/release-please.yml` | `googleapis/release-please-action@v5`, least-privilege permissions, push->master | VERIFIED | Valid YAML; matches all documented shape requirements |
| `README.md` | Rewritten for 7-platform accuracy, working badges, real URLs | VERIFIED | Substantive rewrite confirmed (not a stub) — see Truth #3 evidence |
| `SECURITY.md` | Real reporting channel, zero placeholder | VERIFIED | PVR-only, operator note present, no debt markers |
| `CODE_OF_CONDUCT.md` | Real enforcement-contact channel, zero placeholder | VERIFIED | PVR-only, no debt markers |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `README.md` badges | `.github/workflows/{ci,codeql-analysis,gitleaks}.yml` | badge URL path | WIRED | All 3 target files exist on disk with matching filenames |
| `README.md` credential note | `SECURITY.md#credentials-and-secrets` | markdown anchor link | WIRED | Heading `## Credentials and Secrets` exists in SECURITY.md; content is consistent (env-var/`.env` model, no `config.yml` secrets) |
| `pyproject.toml` version | `.release-please-manifest.json["."]` | manual seed-match | WIRED | Both `2.0.0`, exact match |
| `release-please-config.json` packages["."] | `.release-please-manifest.json["."]` | release-please manifest-mode contract | WIRED | Package key `.` present in both files, consistent |
| `release-please.yml` | `googleapis/release-please-action@v5` | `uses:` step | WIRED (code-level) | Correct action ref + permissions + trigger; **execution** blocked on operator Actions allowlist (see human_verification) |
| `SECURITY.md` / `CODE_OF_CONDUCT.md` | GitHub PVR (`security/advisories/new`) | authored hyperlink | WIRED (code-level) | Correct, well-formed URL to the real repo; **functional resolution** (200 vs 404) blocked on operator enabling PVR (see human_verification) |

### Data-Flow Trace (Level 4)

Not applicable — this phase produces static config/docs artifacts (JSON/YAML/Markdown), not components rendering dynamic runtime data. Skipped.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| release-please manifest/config JSON is valid and matches expected shape | `python -c "json.load(...)"` | `manifest: {'.': '2.0.0'}`, `config: {release-type: python, packages: {'.': {package-name: shoppybot}}}` | PASS |
| release-please workflow YAML is valid and parses to expected structure | `python -c "yaml.safe_load(...)"` | Parsed cleanly; `push.branches: [master]`, `permissions: {contents: write, pull-requests: write}`, `uses: googleapis/release-please-action@v5` | PASS |
| Full test suite green after version bump + docs edits | `.venv\Scripts\python.exe -m pytest -q` | `889 passed, 2 skipped` | PASS |
| Zero placeholder occurrences in tracked non-.planning files | `git grep ... -- ':!.planning'` | exit 1 (no match) | PASS |
| All 7 platform plugins backing README claims actually exist | `ls plugins/shopbot_plugin_*.py` | 7/7 files present | PASS |

### Probe Execution

Step 7c: SKIPPED — no `scripts/*/tests/probe-*.sh` files exist in the repo and neither the PLAN nor SUMMARY files for this phase declare any probe scripts (this is a config/docs phase, verified by file assertion and JSON/YAML validity per 32-VALIDATION.md, not by runnable probes).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| RH-03 | 32-01 | pyproject canonical version reconciled to 2.0.0 | SATISFIED | Truth #1 |
| RH-02 | 32-01 | release-please config/manifest/workflow, python release-type, seeded 2.0.0 | SATISFIED (code-complete); Actions-run-green is operator/CI debt | Truth #2, #2b |
| RH-06 | 32-02 | README accuracy (platforms, install, badges, URL) | SATISFIED | Truth #3 |
| RH-07 | 32-03 | Real security contact, zero placeholder | SATISFIED via documented override (PVR instead of email) | Truth #4, #4b |

No orphaned requirements — REQUIREMENTS.md maps exactly RH-02/RH-03/RH-06/RH-07 to Phase 32, and all four are claimed across the three plans.

### Anti-Patterns Found

None. Scanned all 7 phase-modified files (`pyproject.toml`, `release-please-config.json`, `.release-please-manifest.json`, `.github/workflows/release-please.yml`, `README.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`) for `TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER` — zero matches in any file.

### Human Verification Required

### 1. Confirm RH-07 channel choice (PVR-only vs. email)

**Test:** Review that SECURITY.md and CODE_OF_CONDUCT.md route all reports through GitHub Private Vulnerability Reporting only, with no published email address — a default chosen autonomously in 32-CONTEXT.md because the operator was away during phase discussion.
**Expected:** Operator approves PVR-only as final, or requests a maintainer email be added.
**Why human:** Identity/policy decision made in the operator's absence; the project's CLAUDE.md requires explicit approval for such decisions.

### 2. Enable GitHub Private Vulnerability Reporting

**Test:** Repo Settings -> Security -> "Private vulnerability reporting" -> Enable.
**Expected:** `https://github.com/thezoid/ShopPyBot/security/advisories/new` (linked from both SECURITY.md and CODE_OF_CONDUCT.md) resolves to a working report form instead of 404.
**Why human:** One-time repo Settings toggle; the executor was explicitly instructed not to make this change autonomously, and the verifier cannot flip it either.

### 3. Widen the Actions allowlist for release-please (and carried gitleaks debt)

**Test:** Repo Settings -> Actions -> General -> Actions permissions -> add `googleapis/release-please-action@*` (and ideally `gitleaks/gitleaks-action@*`, pre-existing Phase 31 debt) to the selected-actions pattern list.
**Expected:** The `release-please` workflow stops failing with `startup_failure` on push to `master` and actually runs; it will propose a release PR once conventional-commit history since the `2.0.0` seed warrants a version bump (not necessarily immediately, and not re-proposing `2.0.0` itself).
**Why human:** Repo Settings change; cannot be performed or verified from the local codebase/sandbox.

### Gaps Summary

No code gaps. All locally-verifiable must-haves for RH-02/RH-03/RH-06/RH-07 are implemented, substantive, and internally consistent, and the full test suite is green at the documented baseline (889 passed, 2 skipped). Three items remain, all operator-side repo Settings actions or a policy sign-off, none requiring further code/doc changes:

1. Operator confirmation of the RH-07 PVR-only channel decision (made autonomously in the operator's absence — see override).
2. Enabling Private Vulnerability Reporting in repo Settings (documented inline in SECURITY.md).
3. Widening the Actions allowlist to unblock the release-please workflow run (and the pre-existing gitleaks `startup_failure` from Phase 31).

None of these block "code complete" for Phase 32; they are the documented bridge between code-complete and full CI-green, consistent with 32-CONTEXT.md's explicit scope boundary (actually cutting the first release stays operator-gated).

---

*Verified: 2026-07-02T22:15:00Z*
*Verifier: Claude (gsd-verifier)*
