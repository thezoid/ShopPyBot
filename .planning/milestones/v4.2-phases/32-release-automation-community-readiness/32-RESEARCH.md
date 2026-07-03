# Phase 32: Release Automation & Community Readiness - Research

**Researched:** 2026-07-02
**Domain:** GitHub release automation (release-please, Python release-type), package versioning source-of-truth, README/community-doc accuracy audit
**Confidence:** HIGH

## Summary

This phase has four requirements, all infra/docs, no application code changes. RH-03 (version reconcile) is trivial: `pyproject.toml` is the **only** version source in the repo (verified by grep — no `__version__`, no `setup.cfg`, no `setup.py`, no `VERSION` file exist anywhere outside `.venv`). Bump `version = "0.1.0"` → `"2.0.0"` and there is nothing else to reconcile.

RH-02 (release-please) is a manifest-driven GitHub Action setup: `release-please-config.json` (release-type `python`, package at `.`), `.release-please-manifest.json` (seeded `{".": "2.0.0"}`), and `.github/workflows/release-please.yml` invoking `googleapis/release-please-action@v5`. Verified via the release-please source (`src/strategies/python.ts`, `src/updaters/python/pyproject-toml.ts`) that the python release-type natively updates `pyproject.toml`'s `version` field on release — no `extra-files` config needed since the file already has a `[project]` table. **Critical pitfall discovered during research (not assumed):** this repo's Actions policy is `allowed_actions: selected` with `github_owned_allowed: true` and `patterns_allowed: []` — meaning **only GitHub-owned actions can currently execute**. This is not a theoretical risk: the existing `gitleaks.yml` workflow (Phase 31, `gitleaks/gitleaks-action@v3`, third-party) has run and failed with `conclusion: "startup_failure"` on the most recent push (run 28619876909), confirming third-party actions are actively blocked today. `googleapis/release-please-action` is equally third-party and **will hit the identical `startup_failure`** unless the operator changes repo Settings → Actions → General → Actions permissions (either "Allow all actions and reusable workflows," or add `googleapis/release-please-action@*` — and ideally `gitleaks/gitleaks-action@*`, `github/codeql-action@*` — to the selected-actions pattern allowlist). This phase should land the automation regardless (per CONTEXT.md scope: cutting the first release is out of scope), but the planner must surface this operator blocker clearly, distinct from the already-known PR-creation-permission toggle (which research confirms is **already enabled**: `can_approve_pull_request_reviews: true`, `default_workflow_permissions: write`).

RH-06 (README) requires a substantial rewrite. The current README describes a pre-refactor, two-platform (Amazon/BestBuy), CLI-only, `python main.py` / `pip install -r requirements.txt` project with a placeholder clone URL (`yourusername`) and three badges pointing to workflow files (`app_linuxBuild.yml`, `app_macBuild.yml`, `app_windowsBuild.yml`) that **do not exist** in `.github/workflows/` (only `ci.yml`, `codeql-analysis.yml`, `gitleaks.yml` exist today) — all three badges are dead links. It omits the 7-platform ecosystem (confirmed: 7 plugin files exist), the web dashboard, price monitoring, anti-detection, and encrypted session persistence entirely, and its "edit config.yml with your account details" instruction directly contradicts the current (correct) credential model (env vars / credential store only, verified in `sample.config.yml` and `SECURITY.md`).

RH-07 (security contact) is narrow: exactly 2 live occurrences of `SECURITY_CONTACT_PLACEHOLDER@example.com` exist in the repo outside `.planning/` (SECURITY.md:21, CODE_OF_CONDUCT.md:20). Per CONTEXT.md's locked decision, replace both with GitHub Private Vulnerability Reporting language pointing to `https://github.com/thezoid/ShopPyBot/security/advisories/new` — no email substitution.

**Primary recommendation:** Do RH-03 first (single-line pyproject bump), then RH-02 (config/manifest/workflow, flagging the Actions-permissions blocker as explicit operator debt), then RH-07 (two-file text swap, mechanical), then RH-06 (README rewrite, the only content-heavy task) last since it can reference the now-correct version/badges.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Version source of truth | Package Metadata (`pyproject.toml`) | — | Single `[project].version` field; no other file declares a version anywhere in the tracked source tree |
| Changelog generation / semver bump | CI/CD Automation (GitHub Actions: release-please) | Package Metadata (pyproject.toml gets rewritten by the release PR) | release-please owns commit parsing + CHANGELOG.md + tag creation; app code never computes its own version |
| Release PR creation | CI/CD Automation (release-please-action) | GitHub platform (repo Settings: Actions permissions + PR-creation permission) | Two independent repo-level gates must both be open: Actions-permissions allowlist (currently blocking third-party actions) and workflow PR-creation permission (already enabled) |
| Vulnerability disclosure intake | GitHub platform (Security Advisories / Private Vulnerability Reporting) | Documentation (SECURITY.md instructs reporters where to go) | No app-owned inbox; GitHub's built-in private-report flow is the entire mechanism, activated by a one-time repo Settings toggle (operator-gated, out of phase scope) |
| Contributor-facing accuracy | Documentation (README.md, CODE_OF_CONDUCT.md) | Package Metadata (badges reference workflow files; install instructions reference pyproject extras) | README correctness depends on both prose accuracy and live links into `.github/workflows/` and `pyproject.toml` |

## Standard Stack

### Core
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|---------------|
| `googleapis/release-please-action` | `v5` (latest: v5.0.0, released per GitHub Releases page) | Runs release-please inside GitHub Actions: opens/updates the release PR, tags releases, maintains CHANGELOG.md | Official Google tooling; this repo already standardized on Node24-generation actions in Phase 31 (`actions/checkout@v6`, `actions/setup-python@v6`, `github/codeql-action@v4`) — v5 (Node24) is the version-generation-consistent choice over the older v4 line |
| release-please `release-type: "python"` | n/a (config value, not a package) | Tells release-please which file-update strategy to run (pyproject.toml, setup.cfg/py if present, `__init__.py` if a matching package dir exists) | Only release-type that understands Python packaging conventions; verified via `src/strategies/python.ts` source read |

### Supporting
| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| `release-please-config.json` | schema `release-please/main/schemas/config.json` | Declares `release-type` + package path(s) | Always required for manifest-mode release-please |
| `.release-please-manifest.json` | n/a | Tracks "current released version" per package path; seeding this file is how you bootstrap release-please onto an existing repo without it trying to tag from `0.0.0` | Required for manifest-mode; this is the RH-02 "seed at 2.0.0" mechanism |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| release-please (Google) | `python-semantic-release` | Also conventional-commit-driven, more Python-native (PyPI-publish focused), but CONTEXT.md already locked release-please by name — not evaluated further |
| Manifest-mode config | Legacy single-package `.yml`-only release-please config (pre-manifest) | Deprecated pattern; googleapis' own current docs are manifest-first. Not used. |

**Installation:** None — release-please runs entirely inside GitHub Actions. No local npm/pip install; the "Zero-Node" constraint from STATE.md is not violated (confirmed by CONTEXT.md's own reasoning, and re-verified here: nothing in `package.json` or local dev tooling is required).

**Version verification:** `googleapis/release-please-action` release history verified live via `WebFetch` of `https://github.com/googleapis/release-please-action/releases`: v5.0.0 (22 Apr), v4.4.1 (13 Apr), v4.4.0, v4.3.0, v4.2.0 listed in descending order — v5.0.0 is the current latest major, confirmed not a pre-release/draft in the fetched listing. `[CITED: github.com/googleapis/release-please-action/releases]`

## Package Legitimacy Audit

This phase installs **no** pip/npm packages. The only new external dependency is a GitHub Action reference (`googleapis/release-please-action`), which is not a package-registry artifact and is not in scope for `slopcheck`/`npm view`/`pip index` verification. Ecosystem-appropriate diligence performed instead:

| Reference | Type | Publisher | Evidence | Disposition |
|-----------|------|-----------|----------|-------------|
| `googleapis/release-please-action` | GitHub Action | `googleapis` GitHub org (Google's official OSS org; also publishes `release-please` itself, `google-github-actions/*`) | Confirmed via `gh api repos/googleapis/release-please/contents/...` — live, actively maintained source tree with `src/strategies/python.ts`, `src/updaters/python/pyproject-toml.ts` present and current; release history fetched live | Approved — no `[SLOP]`/`[SUS]` signal; single-source risk mitigated by this being the same org CONTEXT.md explicitly named |

**Packages removed due to slopcheck [SLOP] verdict:** none (no packages installed)
**Packages flagged as suspicious [SUS]:** none

**Note for planner:** because this phase installs no PyPI/npm packages, do not gate any task behind `checkpoint:human-verify` for package legitimacy. The one operator-gated checkpoint this phase genuinely needs is the **Actions-permissions allowlist change** (see Common Pitfalls) — a repo Settings change, not a package-trust decision.

## Architecture Patterns

### System Architecture Diagram

```
Developer commits (conventional-commit format: type(scope): desc)
        │
        ▼
   push to master ──────────────────────────────────────────┐
        │                                                     │
        ▼                                                     ▼
.github/workflows/release-please.yml            .github/workflows/{ci,codeql-analysis,gitleaks}.yml
        │  (BLOCKED today — see Pitfall 1:              (gitleaks BLOCKED today — same cause)
        │   third-party action not in allowlist)
        ▼
googleapis/release-please-action@v5
        │  reads release-please-config.json (release-type: python, path: ".")
        │  reads .release-please-manifest.json (seeded ".": "2.0.0")
        │  parses conventional-commit history since the 2.0.0 anchor
        ▼
  computes next semver bump ──► opens/updates a "release PR"
        │                              (updates pyproject.toml version,
        │                               generates/updates CHANGELOG.md)
        ▼
  [OUT OF SCOPE THIS PHASE] operator reviews + merges release PR
        │
        ▼
  release-please tags the release + publishes GitHub Release notes
```

### Recommended Project Structure
```
.
├── pyproject.toml                       # version: "2.0.0" (RH-03) — sole version source
├── release-please-config.json           # NEW — release-type: python, package "."
├── .release-please-manifest.json        # NEW — seeded {".": "2.0.0"}
├── .github/workflows/
│   ├── ci.yml                           # existing, unchanged
│   ├── codeql-analysis.yml              # existing, unchanged
│   ├── gitleaks.yml                     # existing, unchanged (currently startup_failure — pre-existing debt)
│   └── release-please.yml               # NEW — RH-02
├── README.md                            # rewritten — RH-06
├── SECURITY.md                          # contact section rewritten — RH-07
└── CODE_OF_CONDUCT.md                   # enforcement contact rewritten — RH-07
```

### Pattern 1: Manifest-seeded release-please bootstrap (RH-02)
**What:** Seed `.release-please-manifest.json` with the current (just-reconciled) version instead of leaving it empty or `{}`.
**When to use:** Any existing repo adopting release-please after it already has a meaningful version number — exactly this repo's situation (v2.0.0 is the intended first public release, not `0.0.0`).
**Example:**
```json
{
  ".": "2.0.0"
}
```
```json
{
  "$schema": "https://raw.githubusercontent.com/googleapis/release-please/main/schemas/config.json",
  "release-type": "python",
  "packages": {
    ".": {
      "package-name": "shoppybot"
    }
  }
}
```
Source: `[CITED: github.com/googleapis/release-please/blob/main/docs/manifest-releaser.md]` — "release-please will now use '1.1.1' as the last-released/current version for 'path/to/pkg' and suggest the next version according to conventional commits it has found since the last merged release PR." Applied here: seeding `2.0.0` means release-please treats 2.0.0 as already-released and proposes the *next* bump (e.g., 2.0.1/2.1.0/3.0.0 depending on commit types since the seed) in its first release PR — it does **not** try to (re-)tag 2.0.0 itself.

### Pattern 2: release-please.yml workflow (RH-02)
```yaml
name: release-please

on:
  push:
    branches: [master]

permissions:
  contents: write
  pull-requests: write

jobs:
  release-please:
    runs-on: ubuntu-latest
    steps:
      - uses: googleapis/release-please-action@v5
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
```
Notes:
- `release-type` is **not** passed as an action input here — it lives in `release-please-config.json`, which the action auto-discovers at the repo root by default (confirmed via `action.yml` inputs: `config-file`/`manifest-file` default to empty string, meaning "use the conventional root-level filenames"). Passing `release-type: python` directly as an input is the *legacy* single-package mode and would conflict with manifest mode; do not mix the two. `[CITED: raw.githubusercontent.com/googleapis/release-please-action/main/action.yml]`
- `permissions: contents: write` + `pull-requests: write` at the workflow level matches CONTEXT.md's locked requirement and googleapis' own documented minimum permission set for release-please-action.
- Trigger is `push: branches: [master]` only (not `dev`) — release-please tracks the release branch; this repo's default/release branch is `master` (confirmed via `gh repo view` → `defaultBranchRef.name: "master"`).

### Anti-Patterns to Avoid
- **Adding `extra-files` to update `pyproject.toml`:** Unnecessary. The python strategy's built-in `pyproject-toml.ts` updater already targets `pyproject.toml` automatically because it has a `[project]` table with a `version` key. Adding a redundant `extra-files` entry risks a double-write or path-mismatch bug.
- **Passing `release-type` as an action `with:` input while also using a manifest config:** Legacy/manifest mode conflict — pick one. This phase uses manifest mode exclusively (CONTEXT.md's locked choice).
- **Fabricating a maintainer email for RH-07 "to be safe":** Explicitly forbidden by CONTEXT.md's locked decision — GitHub Private Vulnerability Reporting is the sole channel; no email substitution under any circumstance in this phase.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| Conventional-commit parsing → semver bump | A custom git-log-scanning changelog script | `googleapis/release-please-action` (already locked in CONTEXT.md) | Correctly handles breaking-change footers, multiple commit types per release, and monorepo-safe manifest tracking; a hand-rolled parser would need to reimplement all of this for zero benefit |
| Vulnerability report intake | A custom web form / mailbox-parsing script | GitHub Private Vulnerability Reporting (`.../security/advisories/new`) | Free, built into GitHub, private by default, has its own audit trail and CVE-request workflow — building an equivalent is pure surface area for a project this size |

**Key insight:** every "don't hand-roll" candidate in this phase is a solved problem CONTEXT.md already locked to a platform-native solution (release-please, GitHub Security Advisories). The only genuine engineering judgment left is *wiring* (config file correctness) and *prose accuracy* (README), not algorithm design.

## Common Pitfalls

### Pitfall 1: Repo Actions-permissions policy blocks third-party actions (release-please-action WILL fail identically to gitleaks)
**What goes wrong:** `.github/workflows/release-please.yml` is added, looks syntactically correct, but every run ends `conclusion: "startup_failure"` with zero jobs ever created.
**Why it happens:** `gh api repos/thezoid/ShopPyBot/actions/permissions` returns `{"allowed_actions":"selected","enabled":true}`, and `gh api repos/thezoid/ShopPyBot/actions/permissions/selected-actions` returns `{"github_owned_allowed":true,"patterns_allowed":[],"verified_allowed":false}`. This means **only actions published by GitHub itself** are permitted to run — not "verified creator" actions, not GitHub-org actions like `github/codeql-action` (still runs today only because it predates enforcement or is treated as adjacent-to-GitHub-owned — unconfirmed which), and definitively not `gitleaks/gitleaks-action` or `googleapis/release-please-action`. This is not a hypothesis: `gh run view 28619876909` (the most recent `gitleaks.yml` run, triggered on the current PR's head commit) shows `"conclusion":"startup_failure"` with `jobs: []` — the exact failure mode release-please.yml will exhibit under the same policy.
**How to avoid:** This phase should still author and land `release-please.yml` + config/manifest (per CONTEXT.md: automation lands, first release stays operator-gated) but the plan must include an explicit, clearly-labeled **operator action item** (not something Claude can toggle autonomously — it's a repo Settings change, same category as the Private Vulnerability Reporting toggle CONTEXT.md already flags as operator-gated): go to Settings → Actions → General → Actions permissions, and either select "Allow all actions and reusable workflows" or add `googleapis/release-please-action@*` to the selected-actions pattern list. Recommend also adding `gitleaks/gitleaks-action@*` at the same time to fix the pre-existing (Phase 31) startup_failure, since it's the same root cause — but that fix itself is out of RH-02/03/06/07 scope; only *flag* it, don't silently expand scope to "fix" Phase 31's gitleaks workflow.
**Warning signs:** Any Actions run for a third-party-action workflow showing `conclusion: startup_failure` with an empty `jobs` array in `gh api .../actions/runs/{id}/jobs`.

### Pitfall 2: Confusing "seed the manifest at 2.0.0" with "release-please will tag 2.0.0"
**What goes wrong:** Expecting the first release-please run to produce a GitHub Release/tag literally named `v2.0.0`.
**Why it happens:** Manifest seeding semantics are non-obvious — the seeded value is the *baseline*, not a pending release.
**How to avoid:** Document clearly (in SUMMARY, not README) that release-please's first proposed release PR will target whatever version conventional commits *since the seed* compute (e.g., if only `fix:`/`docs:` commits land after this phase merges, the next proposed version could be `2.0.1`, not `2.0.0`). If the operator specifically wants the first tagged release to literally be `v2.0.0`, they need to either (a) accept whatever release-please proposes next, or (b) manually create a `v2.0.0` GitHub Release/tag out-of-band before/instead of relying on release-please for that exact number — this is an operator decision explicitly deferred by CONTEXT.md ("actually cutting/publishing the first GitHub release" is out of scope).
**Warning signs:** A plan task that asserts "release-please tags 2.0.0" as a verifiable phase outcome — it cannot be, since cutting the release is explicitly out of scope.

### Pitfall 3: README badges reference workflow files that don't exist
**What goes wrong:** Badges render as GitHub's generic "workflow not found" broken-image icon, or (worse) silently 404 without visual indication depending on client caching.
**Why it happens:** The current README badges point at `app_linuxBuild.yml`, `app_macBuild.yml`, `app_windowsBuild.yml` — confirmed via `Glob`/`find` that **none of these three files exist** anywhere in the repo (only `ci.yml`, `codeql-analysis.yml`, `gitleaks.yml` exist in `.github/workflows/`). This is legacy content from before the CI pipeline was consolidated.
**How to avoid:** Point badges at the actual workflow files: `https://github.com/thezoid/ShopPyBot/actions/workflows/ci.yml/badge.svg`, `.../codeql-analysis.yml/badge.svg`, and optionally `.../gitleaks.yml/badge.svg`. Do not add a license badge — **no `LICENSE` file exists in this repo** (confirmed: `Glob "LICENSE*"` finds nothing at repo root, and `gh api repos/thezoid/ShopPyBot/license` returns `404 Not Found`) — a license badge would be fabricated and misleading. Flagged in Open Questions below for operator decision.
**Warning signs:** Any badge URL in a plan/task that references `app_linuxBuild.yml`/`app_macBuild.yml`/`app_windowsBuild.yml`, or any badge claiming a license that doesn't exist as a file.

### Pitfall 4: Python release-type's `__init__.py`/`setup.py`/`setup.cfg` updaters are harmless no-ops here — don't "fix" them
**What goes wrong:** A well-meaning task tries to create a `setup.py`/`setup.cfg` "because release-please's python strategy looks for them."
**Why it happens:** Reading the strategy in isolation (it always *attempts* setup.cfg/setup.py updates) without checking `createIfMissing` behavior.
**How to avoid:** Verified via GitHub source read (`src/strategies/python.ts` behavior, confirmed via WebFetch analysis) that `setup.cfg`/`setup.py` updaters use `createIfMissing: false` — meaning release-please silently skips them if they don't exist; it does **not** create them, and does **not** fail the run. Similarly, the `__init__.py` package-file matcher looks for `{package-name}/__init__.py` derived from `package-name` in `release-please-config.json` — since ShopPyBot's packages are `core/`, `plugins/`, `notifications/`, `web/` (not a single `shoppybot/` package dir), this matcher will find nothing and skip, which is expected and fine. No action needed for either.
**Warning signs:** A task titled anything like "add setup.py for release-please compatibility" — unnecessary, do not create.

### Pitfall 5: Scrubbing `SECURITY_CONTACT_PLACEHOLDER@example.com` from historical `.planning/` docs
**What goes wrong:** A task tries to "achieve zero occurrences repo-wide" by editing `.planning/milestones/v1-phases/03-community-documentation/*.md` and `.planning/REQUIREMENTS.md`/`ROADMAP.md`, which reference the placeholder string as historical record of the original decision.
**Why it happens:** CONTEXT.md's specifics section says "grep the whole repo... to catch every occurrence" without explicitly carving out `.planning/`.
**How to avoid:** RH-07's success criterion ("zero placeholder occurrences") is about *live, consumer-facing* docs — verified via grep that exactly 2 live occurrences exist (`SECURITY.md:21`, `CODE_OF_CONDUCT.md:20`). The other 8 occurrences found are all inside `.planning/` (historical PLAN/SUMMARY/VERIFICATION/CONTEXT/REQUIREMENTS/ROADMAP records describing *that this placeholder was intentionally used*) — these are the project's own audit trail of the decision and should not be rewritten; doing so would falsify history. Scope RH-07's grep-verification to exclude `.planning/`.
**Warning signs:** A verification step that greps the entire repo including `.planning/` and treats any match as a failure.

## Code Examples

### `release-please-config.json` (RH-02)
```json
{
  "$schema": "https://raw.githubusercontent.com/googleapis/release-please/main/schemas/config.json",
  "release-type": "python",
  "packages": {
    ".": {
      "package-name": "shoppybot"
    }
  }
}
```
Source: `[CITED: github.com/googleapis/release-please/blob/main/docs/manifest-releaser.md]` + `[VERIFIED: github.com/googleapis/release-please repo source tree]` (strategy file existence confirmed live via `gh api`)

### `.release-please-manifest.json` (RH-02, seeded 2.0.0)
```json
{
  ".": "2.0.0"
}
```

### `.github/workflows/release-please.yml` (RH-02)
```yaml
name: release-please

on:
  push:
    branches: [master]

permissions:
  contents: write
  pull-requests: write

jobs:
  release-please:
    runs-on: ubuntu-latest
    steps:
      - uses: googleapis/release-please-action@v5
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
```

### `pyproject.toml` version reconcile (RH-03)
```toml
[project]
name = "shoppybot"
version = "2.0.0"
requires-python = ">=3.11"
dependencies = ["platformdirs==4.10.0"]
```
(Only the `version` line changes; everything else in `pyproject.toml` is unaffected.)

### SECURITY.md contact section (RH-07)
Current (SECURITY.md:14-23):
```markdown
Use one of these private channels:

1. **GitHub private security advisory (preferred):** Navigate to the Security
   tab of this repository and choose "Report a vulnerability". GitHub keeps the
   report private until coordinated disclosure.

2. **Direct email:** Send a report to
   `SECURITY_CONTACT_PLACEHOLDER@example.com`
   *(This is a placeholder. The maintainer must replace it with a real verified
   address before launch.)*
```
Recommended replacement (single private channel, no email):
```markdown
Use GitHub's private vulnerability reporting flow: navigate to
[https://github.com/thezoid/ShopPyBot/security/advisories/new](https://github.com/thezoid/ShopPyBot/security/advisories/new)
(or the Security tab → "Report a vulnerability"). GitHub keeps the report
private until coordinated disclosure — this is the only supported reporting
channel; there is no public email address for security reports.

> **Operator note:** Private Vulnerability Reporting must be enabled once in
> repository Settings → Security → "Private vulnerability reporting" for this
> link to work. This is a one-time repo setting and is not toggled by this
> automation.
```

### CODE_OF_CONDUCT.md enforcement section (RH-07)
Current (CODE_OF_CONDUCT.md:15-22):
```markdown
Instances of abusive, harassing, or otherwise unacceptable behavior may be
reported privately to the project maintainer at:

`SECURITY_CONTACT_PLACEHOLDER@example.com`
*(This is a placeholder. The maintainer must replace it with a real verified
address before launch.)*
```
Recommended replacement:
```markdown
Instances of abusive, harassing, or otherwise unacceptable behavior may be
reported privately via GitHub's private vulnerability reporting flow:
[https://github.com/thezoid/ShopPyBot/security/advisories/new](https://github.com/thezoid/ShopPyBot/security/advisories/new)
(Security tab → "Report a vulnerability"). This channel is private by design
and reaches the project maintainer directly.
```

## State of the Art

| Old (current README) | Correct (as of this research) | Verified By | Impact |
|-----------------------|-------------------------------|-------------|--------|
| Prereq "Python 3.8+" | Python 3.11+ | `pyproject.toml requires-python = ">=3.11"` | Wrong prereq will let a new contributor hit install-time errors on 3.8-3.10 |
| Install `pip install -r requirements.txt` | `pip install -e .[web]` | `pyproject.toml [project.optional-dependencies].web` + `[project.scripts]` | Old command skips the `[web]` extra (FastAPI/uvicorn/jinja2/python-multipart) and doesn't register the `shoppybot` console script |
| Run `python main.py` | `shoppybot` console entry point (or `python main.py`, both still work) | `pyproject.toml [project.scripts] shoppybot = "core.service:main"`; `main.py` confirmed still present and functional, delegates to `core.service.BotService` | README should document the packaged entry point as primary since that's what `pip install -e .` gives a new contributor |
| Clone URL `github.com/yourusername/ShopPyBot.git` | `github.com/thezoid/ShopPyBot.git` | `gh repo view` → real public repo confirmed | Placeholder URL is non-functional copy-paste for every reader |
| "Amazon and BestBuy" (Overview + Features) | 7 platforms: Amazon, BestBuy, Walmart, Target, GameStop, NewEgg, Square Enix | `ls plugins/` → 7 `shopbot_plugin_*.py` files confirmed; also enumerated with per-platform risk table already in `SECURITY.md` | Understates the project's actual scope by 5 platforms |
| No web dashboard mention | Web dashboard + observability (SSE, health surface, log filtering) | `ls web/` → `routes/`, `static/`, `templates/`, `sse_hub.py`, `log_reader.py`, `security.py`, `config_web.py` confirmed | Major feature entirely undocumented |
| No price monitoring mention | Price monitoring (target price / drop %) | `main.py` calls `update_item_price_config_sync(item.link, item.target_price, item.price_drop_pct)`; `sample.config.yml` items support `type`, price fields referenced in `core/` per STATE.md PRICE-01..05 | Undocumented feature |
| No anti-detection mention | Fingerprint/proxy rotation + 2captcha CAPTCHA solving | `core/stealth.py` (12.3K), `core/captcha.py` (2captcha v1 client, confirmed via grep) | Undocumented feature |
| No session persistence mention | Encrypted session persistence (Fernet + scrypt) | `core/session_store.py`, `core/credentials.py` `EncryptedFileBackend` confirmed via grep | Undocumented feature |
| Badges: `app_linuxBuild.yml`/`app_macBuild.yml`/`app_windowsBuild.yml` | Badges: `ci.yml`, `codeql-analysis.yml`, (optionally `gitleaks.yml`) | `.github/workflows/` directory listing — old files absent, current files present | All 3 current badges are dead links |
| "Edit config.yml to include your Amazon and BestBuy account details" | Credentials are environment-variable/credential-store only, never in `config.yml` | `SECURITY.md` "Credentials and Secrets" section; `sample.config.yml` comments confirm `AMZ_EMAIL`/`AMZ_PWD`/`BB_EMAIL`/`BB_PASSWORD` env vars + `.env.example` | Current README instruction is actively wrong and contradicts the project's own security policy |

**Deprecated/outdated:**
- `requirements.txt`-based install flow: superseded by `pyproject.toml` + `pip install -e .[web]` as of the plugin/web-dashboard architecture (Phases 2, 10+). `requirements.txt` still exists at repo root (304B) but is legacy; README should lead with the pyproject-based install.
- Root-level `amazon_bot.py` / `bestbuy_bot.py`: present at repo root but **not** listed in `pyproject.toml`'s `[tool.setuptools] py-modules` (only `models, logger, config, utils, main` are). These predate the `plugins/shopbot_plugin_amazon.py` / `plugins/shopbot_plugin_bestbuy.py` architecture. Not part of RH-06's explicit scope (README accuracy, not dead-code removal) — flagged in Open Questions, not actioned.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|----------------|
| A1 | `googleapis/release-please-action@v5` is safe to pin as "current major" rather than v4 | Standard Stack | Low — v5.0.0 is confirmed live and not a pre-release via direct fetch of the official GitHub releases page; if this changes before the plan executes, the fallback (`@v4`) is a one-line workflow edit, not a design change |
| A2 | `action.yml`'s `config-file`/`manifest-file` empty-string defaults mean "auto-discover root-level conventional filenames" (rather than "no config used at all") | Architecture Patterns / Pattern 2 | Medium — this is inferred from the action's documented default behavior and widespread real-world manifest-mode examples, not from an explicit line in `action.yml` stating the fallback filename. If wrong, the workflow would need explicit `config-file: release-please-config.json` / `manifest-file: .release-please-manifest.json` inputs added — low-cost fix, does not change the config/manifest file contents themselves |
| A3 | `github/codeql-action` continues to run successfully today despite the `github_owned_allowed`-only policy (i.e., GitHub treats `github/*` org actions as "GitHub-owned" even though the org login is literally "github" not "actions") | Common Pitfalls / Pitfall 1 | Low-Medium — not directly re-verified with a fresh `codeql-analysis.yml` run in this session (only inferred from Phase 31 being marked Complete); if `github/codeql-action` is ALSO blocked, that's a pre-existing Phase 31 gap, not something this phase introduces or must fix, so the risk is scoped away from RH-02/03/06/07 either way |

**If this table is empty:** N/A — see above.

## Open Questions

1. **Should this phase add a `LICENSE` file?**
   - What we know: No `LICENSE` file exists at repo root; `gh api repos/thezoid/ShopPyBot/license` returns 404. CONTEXT.md's RH-06 decision says badges should include "license... as applicable" — implying conditional inclusion, not fabrication.
   - What's unclear: Whether "as applicable" was intended to mean "add a LICENSE file so the badge becomes applicable" or "skip the license badge since none exists."
   - Recommendation: Treat as **out of this phase's locked scope** (CONTEXT.md's Decisions section does not mention creating a LICENSE file, only badge correctness). Omit the license badge from the README rewrite rather than fabricate one. Surface as a one-line operator note in the phase SUMMARY: "No LICENSE file exists; add one (e.g., MIT) before/at first public release if intended to be open-source-licensed."

2. **Root-level `amazon_bot.py` / `bestbuy_bot.py` and `_deprecated/` directory — dead code cleanup?**
   - What we know: These files are not referenced by `pyproject.toml`'s packaging config and appear superseded by `plugins/shopbot_plugin_amazon.py` / `plugins/shopbot_plugin_bestbuy.py`. `_deprecated/` contains an entirely separate legacy PowerShell-based bot (`bot.py`, `bot-availCheck.py`, `installDependencies.ps1`).
   - What's unclear: Whether they're intentionally kept for reference/rollback or are simply forgotten.
   - Recommendation: Out of RH-06/RH-07 scope (README *accuracy*, not dead-code removal). Do not delete in this phase. Mention as adjacent-issue in the phase SUMMARY per the project's Scope Control convention (mention briefly, offer options, don't action without direction).

3. **CLAUDE.md's own Architecture section describes the pre-refactor single-process/`while True` design, not the current plugin/orchestrator/web-dashboard architecture.**
   - What we know: `CLAUDE.md`'s "Architecture" and "Module responsibilities" sections describe `main.py`'s `while True` loop routing by URL domain to `amazon_bot.py`/`bestbuy_bot.py` — this is the pre-Phase-2 architecture, not the current 7-plugin/orchestrator/web-dashboard system this research otherwise documents.
   - What's unclear: Whether updating CLAUDE.md is anyone's responsibility going forward.
   - Recommendation: Out of RH-02/03/06/07 scope entirely (CLAUDE.md is not in the phase's `files_to_read` output targets, and none of the 4 requirement IDs cover it). Flag only — do not edit CLAUDE.md in this phase.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|--------------|-----------|---------|----------|
| `gh` CLI | Verifying repo/Actions settings, workflow run status | Yes | (session-verified functional) | — |
| GitHub Actions (repo-hosted) | Running `release-please.yml` post-push | Partially — **blocked for third-party actions** (see Pitfall 1) | n/a | Operator must adjust Settings → Actions → General → Actions permissions before release-please.yml can execute; config/manifest files themselves are still correct/lands regardless |
| Node.js / npm (local) | N/A — not needed | N/A | N/A | release-please runs entirely inside the GitHub-hosted Action runner; Zero-Node constraint (STATE.md) is not implicated |
| Python 3.11+ / pip | No install/build step needed for this phase (docs + JSON/YAML config only) | Yes | project already requires 3.11+ | — |

**Missing dependencies with no fallback:**
- None that block *authoring* the phase's deliverables. The Actions-permissions gate blocks *execution* of release-please.yml post-push, which CONTEXT.md already scopes as CI-verification debt (the first release PR/tag is explicitly out of scope for this phase).

**Missing dependencies with fallback:**
- Third-party Actions execution (release-please-action) — fallback is the documented operator Settings change; not a code-level fallback since this is a platform policy, not a library choice.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 (confirmed installed in `.venv`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths = ["tests"]`, `asyncio_mode = "auto"`) |
| Quick run command | `pytest tests/test_docs.py tests/test_security_md.py -x` (existing doc/security-content test files, if they cover this phase's targets — see Wave 0 Gaps) |
| Full suite command | `pytest --tb=short` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|--------------|
| RH-03 | `pyproject.toml` version == "2.0.0" | unit (static assertion) | `pytest tests/test_docs.py -k version -x` (or a new small assertion reading `pyproject.toml` via `tomllib`) | Likely ❌ — `test_docs.py` exists (1.9K) but scope unconfirmed; treat as Wave 0 gap unless verified to already assert on version |
| RH-02 | `release-please-config.json` is valid JSON with `release-type: "python"` and package `"."` present; `.release-please-manifest.json` is valid JSON seeded `{".": "2.0.0"}` | unit (static config validation) | `python -c "import json; json.load(open('release-please-config.json')); json.load(open('.release-please-manifest.json'))"` — or a small pytest wrapping the same assertion | ❌ Wave 0 — files don't exist yet, this phase creates them |
| RH-02 | `.github/workflows/release-please.yml` is syntactically valid YAML with `permissions: contents: write, pull-requests: write` and triggers on `push: branches: [master]` | unit (static YAML validation) | `python -c "import yaml; yaml.safe_load(open('.github/workflows/release-please.yml'))"` | ❌ Wave 0 — file doesn't exist yet |
| RH-06 | README contains no placeholder clone URL, no dead badge references, and mentions all 7 platforms + web dashboard + price monitoring + anti-detection + sessions | manual-only (content/prose correctness is not meaningfully unit-testable) | N/A — code review / checklist against the gap table in this document's "State of the Art" section | N/A |
| RH-07 | Zero occurrences of `SECURITY_CONTACT_PLACEHOLDER@example.com` in `SECURITY.md` and `CODE_OF_CONDUCT.md` (excluding `.planning/`) | unit (static grep-style assertion) | `pytest tests/test_security_md.py -x` if it already covers this string, else a new 3-line pytest asserting the string is absent from both files | Partially — `test_security_md.py` (3.5K) exists; scope needs confirmation in Wave 0 |

### Sampling Rate
- **Per task commit:** run the specific static-assertion test(s) for the requirement just touched (fast, config/text-only — no need for the full suite per task)
- **Per wave merge:** `pytest --tb=short` (full suite; this phase touches no application logic, so regression risk is near-zero, but the full-suite run is cheap and catches any accidental syntax breakage in `pyproject.toml`)
- **Phase gate:** Full suite green before `/gsd:verify-work`; additionally, post-push, `gh run list` should be checked for the new `release-please.yml` run's conclusion (expected: `startup_failure` until the operator fixes the Actions-permissions allowlist — this is a **known, pre-flagged** CI-verification-debt outcome, not a phase failure, per CONTEXT.md's explicit scoping of "green run in Actions" as post-push debt)

### Wave 0 Gaps
- [ ] Confirm whether `tests/test_docs.py` and `tests/test_security_md.py` already assert on version-string / placeholder-string content, or need new/extended assertions for RH-03/RH-02/RH-07's static-validation checks
- [ ] No test file currently validates `release-please-config.json` / `.release-please-manifest.json` — new, since these files don't exist yet (this phase creates them)
- [ ] No test file currently validates the new `release-please.yml` workflow's YAML syntax — new

*(If no gaps: N/A — gaps exist and are listed above)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|----------------|---------|-------------------|
| V2 Authentication | No | Phase touches no auth code |
| V3 Session Management | No | Phase touches no session code |
| V4 Access Control | No | Phase touches no access-control code |
| V5 Input Validation | No | No new user-facing input surfaces added |
| V6 Cryptography | No | No cryptographic code touched |
| V14 Configuration (closest ASVS fit for this phase) | Yes | GitHub repo-level configuration (Actions permissions, PR-creation permission, Private Vulnerability Reporting toggle) — all platform-native controls, not application code; this phase's SECURITY.md changes correctly route disclosure through GitHub's built-in private-report mechanism rather than a custom channel |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Publishing a real maintainer email on a public repo (permanent, scrapable exposure) | Information Disclosure | CONTEXT.md's locked decision: use GitHub Private Vulnerability Reporting exclusively, never publish an email — implemented as designed in this research's Code Examples section |
| Overly-broad Actions permissions (`Allow all actions and reusable workflows`) as the fix for Pitfall 1 | Elevation of Privilege (supply-chain: any public Action could now run with this repo's `GITHUB_TOKEN`) | Prefer the narrower fix — add specific patterns (`googleapis/release-please-action@*`, etc.) to `patterns_allowed` rather than switching to "allow all." Document both options in the operator-facing note; recommend the narrower one. |
| `GITHUB_TOKEN` permissions creep in `release-please.yml` | Elevation of Privilege | Workflow-level `permissions:` block scoped to exactly `contents: write` + `pull-requests: write` — no `actions: write`, no `id-token: write`, matching the minimum release-please-action needs (already reflected in Code Examples) |

## Sources

### Primary (HIGH confidence)
- Live repo inspection via `Read`/`Grep`/`Glob`/`Bash`: `pyproject.toml`, `README.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `.github/workflows/{ci,codeql-analysis,gitleaks}.yml`, `plugins/` (7 files), `web/`, `core/`, `sample.config.yml`, `main.py`
- `gh api repos/thezoid/ShopPyBot` and sub-resources (`/actions/permissions`, `/actions/permissions/selected-actions`, `/actions/permissions/workflow`, `/license`, `/actions/runs/{id}`, `/actions/runs/{id}/jobs`) — live repo-settings and workflow-run-status verification
- `gh api repos/googleapis/release-please/contents/{docs,src/strategies,src/updaters/python}` — live source-tree confirmation of python release-type behavior

### Secondary (MEDIUM confidence)
- `WebFetch` of `github.com/googleapis/release-please-action/releases` — current version listing (v5.0.0 latest)
- `WebFetch` of `raw.githubusercontent.com/googleapis/release-please-action/main/action.yml` — action input names/defaults
- `WebFetch` of `github.com/googleapis/release-please/blob/main/docs/manifest-releaser.md` — manifest-seeding semantics
- `WebFetch` of `raw.githubusercontent.com/googleapis/release-please/main/src/strategies/python.ts` — python strategy file-updater list and `createIfMissing` behavior

### Tertiary (LOW confidence)
- None — all findings above were cross-verified against at least one live source (repo inspection or official GitHub/googleapis source/docs).

## Metadata

**Confidence breakdown:**
- Standard stack (release-please-action version, python release-type behavior): HIGH — verified directly against live GitHub source and releases, not training-data recall
- Architecture (config/manifest/workflow shape): HIGH — cross-verified against googleapis' own manifest-releaser.md and action.yml
- Pitfalls (Actions-permissions blocker): HIGH — directly observed via `gh api` live run data (`startup_failure`), not inferred
- README gap list: HIGH — every claim cross-checked against actual repo contents (plugin file count, web/ dir contents, badge target existence, LICENSE absence)

**Research date:** 2026-07-02
**Valid until:** 30 days (release-please-action version pin should be re-checked if the plan doesn't execute within that window, since Google ships new majors periodically — v5.0.0 was itself only released recently relative to v4's long run)
