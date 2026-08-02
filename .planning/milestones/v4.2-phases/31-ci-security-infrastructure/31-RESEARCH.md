# Phase 31: CI & Security Infrastructure - Research

**Researched:** 2026-07-02
**Domain:** GitHub Actions CI/CD security tooling (secret scanning, static analysis, dependency management) for a Python repo
**Confidence:** HIGH

## Summary

All three requirements were verified against live, authoritative sources rather than training-data assumptions, and two of CONTEXT.md's placeholder defaults turned out to be stale: `codeql-action` has moved past v3 to v4, and `actions/checkout` needs v6 (not v4) to stay ahead of GitHub's Node.js 20 Actions-runtime retirement, whose forced-default-switch date has already passed as of this research session (2026-07-02). Both corrections are cited below with primary sources.

A live gitleaks scan was executed against this repo during research (binary downloaded from the official GitHub release, SHA256-verified). Full git-history scan (`gitleaks git`, 964 commits) found exactly **one** finding: a test fixture at `tests/test_captcha.py:381` (`sentinel_key = "sentinel-api-key-cp03-xyzzy"`), confirmed by reading the source as an intentional fake credential for a mocked `CaptchaSolver` test, not a real secret. No other tracked-file findings exist. `.gitignore` already correctly excludes `config.yml`, `data/*` (covers `shop_py_bot.db`, `creds.bin`, `sessions/*.bin`), verified via `git check-ignore` + `git ls-files` — RH-01's "zero findings" bar requires one `#gitleaks:allow` inline suppression, not a history rewrite.

RH-04's CodeQL workflow (`.github/workflows/codeql-analysis.yml`) uses four retired action references (`checkout@v2`, `codeql-action/{init,autobuild,analyze}@v1`) that will not run at all (Node16 runtime removed by GitHub). GitHub's default (non-workflow) CodeQL setup was confirmed **not configured** for this repo (`state: "not-configured"` via live API call), so an advanced/workflow-based CodeQL setup will not conflict.

RH-05's 7 open Dependabot alerts were pulled live via `gh api` and cross-referenced against `requirements.txt`/`pyproject.toml`. All 7 are cleanly remediable by bumping 3 packages (`cryptography`, `pydantic-settings`, `jinja2`) — **none require a documented-dismiss** and none touch the pinned FastAPI/uvicorn versions or introduce `sse-starlette`/Node.

**Primary recommendation:** Bump `codeql-analysis.yml` to `checkout@v6` + `codeql-action/{init,analyze}@v4` with `build-mode: none` (drop the autobuild step entirely); add a `gitleaks/gitleaks-action@v3` CI job with `checkout@v6`; add `.gitleaks.toml`-free inline `#gitleaks:allow` suppression for the one test-fixture false positive; create `.github/dependabot.yml` with `pip` + `github-actions` ecosystems; bump `cryptography==44.0.2→49.0.0`, `pydantic-settings==2.14.0→2.14.2`, `jinja2==3.1.4→3.1.6` (in `pyproject.toml`, not `requirements.txt` — see Pitfall 5).

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RH-01 | Repo git history and `.gitignore` audited so no secret, populated `config.yml`, real `data/*.db`, or credential-store artifact is tracked; clean gitleaks/trufflehog scan is the evidence | Live gitleaks scan executed (964 commits, 1 false-positive finding identified + confirmed); exact `.gitleaks.toml`-free suppression syntax; exact `git check-ignore`/`git ls-files` proof commands; minimal `gitleaks-action@v3` CI job spec |
| RH-04 | CodeQL static-security-scan workflow runs successfully (retired `checkout@v2`/`codeql-action@v1` bumped to supported versions) | Existing workflow read and every retired reference enumerated; current supported majors verified live (`checkout@v6`, `codeql-action@v4`); official starter-workflow diffed; default-setup conflict checked and cleared; minimal diff provided |
| RH-05 | `.github/dependabot.yml` exists and open vulnerability alerts are reviewed/remediated to a clean state | Correct `dependabot.yml` for pip+pyproject dual-manifest layout; all 7 open alerts pulled live via `gh api`, cross-referenced to exact pinned versions, remediation versions verified against PyPI, zero conflicts with pinned-constraint rule |
</phase_requirements>

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Secret Scanning (RH-01):**
- Tool: gitleaks (fast, single-binary, standard GitHub Action, scans full history). trufflehog acceptable as fallback if gitleaks unavailable in the runner.
- Scope: full `git log`/history + working tree. Evidence of success = a clean gitleaks run (zero findings) captured in the phase summary.
- `.gitignore` must demonstrably exclude: `config.yml`, `data/*.db` (and any `*.db`), credential-store artifacts. Verify each is ignored (`git check-ignore`) AND not currently tracked (`git ls-files`).
- Add a lightweight gitleaks CI job to GitHub Actions (ongoing, not one-time local check). Fail the job on findings.
- **Non-destructive only**: if a secret is found tracked in history, the deliverable is surface + stop tracking + flag rotation as operator debt, NOT history rewrite. Never `git filter-repo`, `git rebase -i` history rewrite, or force-push in this phase.

**CodeQL (RH-04):**
- Bump retired action versions: `actions/checkout@v2 → @v4` (research finding: this default is stale — see Pitfall 3, corrected to `@v6`), `github/codeql-action/*@v1 → @v3` (research finding: this default is stale — see Pitfall 3, corrected to `@v4`). Bump any other retired actions in the same workflow to current supported majors.
- Language matrix: Python only. Keep the default query suite.
- "Green run in Actions" is verified post-push via `gh run` on the pushed branch (live-CI verification).

**Dependabot + Vulnerability Remediation (RH-05):**
- Create `.github/dependabot.yml`: `pip` ecosystem (requirements.txt and/or pyproject) + `github-actions` ecosystem. Weekly schedule, sensible open-PR limits.
- Remediate the 7 open alerts by bumping the affected dependency to the patched version. Preserve existing hard version constraints from prior milestones (do NOT upgrade FastAPI past the v4.1-pinned range, do NOT add sse-starlette, do NOT introduce Node).
- If an alert cannot be remediated without violating a pinned constraint or breaking tests, document the tradeoff and dismiss with written rationale instead of forcing a breaking upgrade. Every dismissal gets a one-line justification.
- After bumps, full pytest suite (887 passed baseline) must stay green.

**Verification Boundary (autonomous, live-CI):**
- Code-complete + CI-green is the DoD. Local-verifiable now: gitleaks clean, `.gitignore` correctness, workflow YAML validity, `dependabot.yml` validity, dependency bumps applied, tests green.
- Live-GitHub-verifiable only after push: CodeQL Actions run turning green, dependabot alert queue draining. Checked via `gh run list`/`gh api` after push; if runner unavailable, recorded as CI-verification debt.

### Claude's Discretion
- Exact `.gitleaks.toml` / inline-comment suppression mechanism for any false positive found (research recommends `#gitleaks:allow` inline comment — see Code Examples).
- Exact dependabot.yml `open-pull-requests-limit` values and label taxonomy.
- Whether to bump `ci.yml`'s own `checkout@v4`/`setup-python@v5` alongside the CodeQL fix (research surfaces this as a related Node20-EOL risk — see Pitfall 3 — but it is not literally named by RH-04/05; flagged as an Open Question for the planner).

### Deferred Ideas (OUT OF SCOPE)
- Destructive SEED-001 history scrub/squash, secret rotation, force-push, collaborator re-clone — operator-gated, out of milestone scope.
</user_constraints>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Secret detection (history + working tree) | CI / GitHub Actions | Local dev (pre-commit optional) | gitleaks-action runs on every push/PR; a pytest guard (existing pattern: `test_no_committed_sessions.py`) gives faster local feedback but is not a substitute for full-history scanning |
| Static security analysis (CodeQL) | CI / GitHub Actions | — | CodeQL requires the GitHub-hosted analysis engine; cannot run meaningfully as a local pytest check |
| Dependency vulnerability tracking | GitHub platform (Dependabot service) | CI / GitHub Actions (github-actions ecosystem) | Dependabot alerts are generated by GitHub's dependency graph, not by a workflow job; `dependabot.yml` only configures the *update PR* behavior, not alert generation (alerts already exist without any config file) |
| Dependency version pins | Repo source (`requirements.txt` / `pyproject.toml`) | — | Single source of truth per existing project convention (CLAUDE.md: "Config: `config.yml` drives all behavior"; same principle applies to dependency manifests) |
| `.gitignore` correctness | Repo source (VCS config) | — | Prevention layer; verified via `git check-ignore`/`git ls-files`, not runtime code |

## Standard Stack

### Core
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| gitleaks (CLI) | 8.30.1 | Full-history + working-tree secret scanning | Single static Go binary, no runtime deps, official GitHub Action wrapper, actively maintained (release cadence ~weekly) [VERIFIED: github.com/gitleaks/gitleaks releases API, live-tested against this repo] |
| gitleaks/gitleaks-action | v3.0.0 | CI enforcement of gitleaks scan on push/PR | Official action; v3 required as of this research date — v2 is Node20 and GitHub's runner default already switched to Node24 (2026-06-02/16); v2 requires an insecure opt-out env var to keep running today and stops working entirely 2026-09-16 [VERIFIED: raw.githubusercontent.com/gitleaks/gitleaks-action/main/README.md, dated migration notice] |
| github/codeql-action | v4 (init + analyze) | Static security analysis (SAST) | Current major as of this research date; v3 is Node20 (same EOL risk as above) and is scheduled for deprecation Dec 2026; v4 runs on Node24 [VERIFIED: github.blog/changelog/2025-10-28-upcoming-deprecation-of-codeql-action-v3, repo tag list via `gh api repos/github/codeql-action/tags`] |
| actions/checkout | v6 | Repo checkout in every new/modified job | v6 is explicitly documented by gitleaks-action's own README as "the Node 24 release"; confirmed via `gh api repos/actions/checkout/releases/tags/v6.0.0` release body ("Update README to include Node.js 24 support") [VERIFIED: GitHub API, live query] |

### Supporting
| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| `.github/dependabot.yml` | schema v2 | Automated dependency-update PRs | pip ecosystem (requirements.txt + pyproject.toml, same `directory: "/"` entry) + github-actions ecosystem |
| `cryptography` | 44.0.2 → **49.0.0** | Fernet + scrypt KDF for credential/session encryption | Bump clears all 3 open cryptography alerts (#6 high, #11 high, #7 low); latest stable, verified no breaking API impact on `Fernet`/`Scrypt` usage (see Pitfall 6) [VERIFIED: pip index versions cryptography] |
| `pydantic-settings` | 2.14.0 → **2.14.2** | Config loading (`AppConfig(BaseSettings)`) | Clears #12 (moderate); patch-level bump, zero API risk [VERIFIED: pip index versions pydantic-settings] |
| `jinja2` | 3.1.4 → **3.1.6** | Web dashboard templates (`[web]` extra) | Clears #8, #9, #10 (all moderate); patch-level bump within 3.1.x [VERIFIED: pip index versions jinja2] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| gitleaks | trufflehog | CONTEXT.md names this as acceptable fallback; trufflehog does deeper credential-verification (live API-key validation) but is heavier and has a steeper config curve. gitleaks is faster and sufficient for this repo's scope — no reason to deviate from the CONTEXT.md primary choice. |
| Inline `#gitleaks:allow` for the one false positive | Global `.gitleaks.toml` `[[allowlists]]` regex/path exemption | A path-based exemption for all of `tests/` would silently suppress any *future* real secret accidentally committed to a test file. Inline comment is precise (single line, single fingerprint) — lower blast radius. [CITED: gitleaks README `#### gitleaks:allow` section] |
| Bumping `cryptography` to the minimum patched version (48.0.1) | Bumping to latest (49.0.0) | 49.0.0 additionally removes SECT-curve binary-elliptic-curve support entirely (the root cause class of alert #6), rather than merely validating it — strictly safer, and ShopPyBot's codebase does not reference SECT curves (`grep` confirmed) [VERIFIED: cryptography.io changelog via WebSearch, cross-referenced against local `core/credentials.py`/`core/session_store.py` usage] |

**Installation (no new dependencies — all 3 packages already in `requirements.txt`/`pyproject.toml`, version bump only):**
```bash
pip install -r requirements.txt
pip install -e .[web]
pytest --tb=short   # full 887-passed baseline must stay green
```

**Version verification (live, this session):**
```
cryptography:       INSTALLED 44.0.2 (pinned) → LATEST 49.0.0   [pip index versions cryptography]
pydantic-settings:  INSTALLED 2.14.0 (pinned) → LATEST 2.14.2   [pip index versions pydantic-settings]
jinja2:              INSTALLED 3.1.4 (pinned) → LATEST 3.1.6     [pip index versions jinja2]
```

## Package Legitimacy Audit

No *new* packages are introduced by this phase — all three RH-05 remediations are version bumps of already-declared, long-established dependencies. slopcheck was run for completeness per protocol.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| cryptography | PyPI | 14+ yrs (pyca org) | very high | github.com/pyca/cryptography | [OK] | Approved (existing dep, version bump only) |
| pydantic-settings | PyPI | 5+ yrs (pydantic org) | very high | github.com/pydantic/pydantic-settings | [OK] | Approved (existing dep, version bump only) |
| jinja2 | PyPI | 15+ yrs (pallets org) | very high | github.com/pallets/jinja | [OK] | Approved (existing dep, version bump only) |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

`gitleaks`/`gitleaks-action` and `codeql-action`/`actions/checkout` are GitHub Actions marketplace entries, not pip/npm packages — slopcheck does not apply. Legitimacy was instead verified by: (1) downloading the official `gitleaks_8.30.1_windows_x64.zip` release asset and confirming its SHA256 against the maintainer-published `gitleaks_8.30.1_checksums.txt`, and (2) resolving every Action's major-version tag directly against its GitHub repo via `gh api repos/<org>/<repo>/tags` and `releases/tags/<tag>` (all first-party `github.com/actions/*`, `github.com/github/codeql-action`, `github.com/gitleaks/gitleaks-action` — official publishers, not third-party forks).

## Architecture Patterns

### System Architecture Diagram

```
 Developer push / PR                    Scheduled (cron)
        │                                      │
        ▼                                      ▼
 ┌─────────────────────────────────────────────────────┐
 │              GitHub Actions (this repo)              │
 │                                                       │
 │  ci.yml (test)        codeql-analysis.yml   gitleaks.yml (NEW)
 │  ┌───────────┐        ┌──────────────┐      ┌──────────────┐
 │  │ checkout  │        │ checkout@v6  │      │ checkout@v6  │
 │  │ setup-py  │        │ codeql/init  │      │ fetch-depth:0│
 │  │ pip install│       │  build-mode: │      │ gitleaks-    │
 │  │ pytest    │        │    none      │      │  action@v3   │
 │  └───────────┘        │ codeql/analyze│     └──────┬───────┘
 │                        └──────┬───────┘             │
 │                               │                      │
 │                               ▼                      ▼
 │                    Security tab (Code scanning)  fails job on
 │                                                   findings +
 │                                                   PR comment
 └───────────────────────────────┬──────────────────────┘
                                  │
                    ┌─────────────┴──────────────┐
                    ▼                             ▼
        GitHub Dependency Graph          .github/dependabot.yml (NEW)
        (auto-generates alerts from            │
         requirements.txt + pyproject.toml)     ▼
                    │                  weekly PRs: pip ecosystem
                    ▼                  (directory "/") +
        Security tab → Dependabot alerts    github-actions ecosystem
        (7 open today; target: 0 after
         the 3 version bumps below merge)
```

### Recommended Project Structure
```
.github/
├── dependabot.yml              # NEW — RH-05
└── workflows/
    ├── ci.yml                  # unchanged (test matrix) — see Pitfall 3 for adjacent risk
    ├── codeql-analysis.yml     # MODIFIED — RH-04 (retired actions bumped)
    └── gitleaks.yml            # NEW — RH-01 (secret-scan job)
tests/
└── test_no_tracked_secrets.py  # NEW (recommended) — RH-01 fast local guard, mirrors
                                 #   the existing test_no_committed_sessions.py pattern
```

### Pattern 1: CodeQL build-mode matrix (replaces autobuild step)
**What:** CodeQL v4's `init` action takes a `build-mode` input directly; for interpreted languages (Python) this should be `none`. The separate `autobuild` step is being phased out in favor of this.
**When to use:** Any Python (or other interpreted-language) CodeQL workflow being upgraded from a v1/v2-era template.
**Example:**
```yaml
# Source: github.com/actions/starter-workflows code-scanning/codeql.yml (live-fetched)
#         + github.com/github/codeql-action __build-mode-none.yml PR-check fixture
strategy:
  fail-fast: false
  matrix:
    include:
      - language: python
        build-mode: none

steps:
  - name: Checkout repository
    uses: actions/checkout@v6

  - name: Initialize CodeQL
    uses: github/codeql-action/init@v4
    with:
      languages: ${{ matrix.language }}
      build-mode: ${{ matrix.build-mode }}

  - name: Perform CodeQL Analysis
    uses: github/codeql-action/analyze@v4
    with:
      category: "/language:${{matrix.language}}"
```

### Pattern 2: Minimal gitleaks CI job (public/personal-account repo)
**What:** A dedicated workflow that runs gitleaks on every push/PR and fails the job on any finding.
**When to use:** RH-01's "bake the scan into CI, non-blocking-hostile: fail on findings" requirement.
**Example:**
```yaml
# Source: raw.githubusercontent.com/gitleaks/gitleaks-action/main/README.md (live-fetched, dated migration notice included)
name: gitleaks
on:
  push:
    branches: [master, dev]
  pull_request:
    branches: [master, dev]
  workflow_dispatch:
jobs:
  scan:
    name: gitleaks
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
        with:
          fetch-depth: 0        # full history required — shallow clone breaks history scan
      - uses: gitleaks/gitleaks-action@v3
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          # GITLEAKS_LICENSE not required: thezoid/ShopPyBot is a personal account, not an org
          # (confirmed via gh api repos/thezoid/ShopPyBot: visibility=public, no org).
```
Repo's `default_workflow_permissions` is already `write` (confirmed via `gh api repos/thezoid/ShopPyBot/actions/permissions/workflow`), so no extra `permissions:` block is needed for gitleaks-action's PR-comment feature.

### Pattern 3: Suppressing a confirmed test-fixture false positive
**What:** Inline `#gitleaks:allow` trailing comment on the exact offending line.
**When to use:** A known, reviewed, intentional fake secret in test code (this repo's exact situation at `tests/test_captcha.py:381`).
**Example:**
```python
# Source: github.com/gitleaks/gitleaks README "#### gitleaks:allow" section (live-fetched)
sentinel_key = "sentinel-api-key-cp03-xyzzy"  #gitleaks:allow
```

### Pattern 4: Local pytest guard mirroring existing security-test conventions
**What:** A fast (<1s), git-based pytest assertion that no sensitive path is tracked — same pattern as the existing `tests/test_no_committed_sessions.py`.
**When to use:** Gives immediate local/CI feedback without waiting for the gitleaks job; defense-in-depth alongside (not instead of) the CI gitleaks job.
**Example:**
```python
# Source: existing tests/test_no_committed_sessions.py (this repo, pattern to extend)
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SENSITIVE_TRACKED_CHECKS = ["config.yml", "data/", "*.db", "*creds.bin", "*sessions/*.bin"]

def test_no_tracked_sensitive_paths():
    result = subprocess.run(
        ["git", "-C", str(_REPO_ROOT), "ls-files"] + _SENSITIVE_TRACKED_CHECKS,
        capture_output=True, text=True, check=False,
    )
    tracked = [line for line in result.stdout.splitlines() if line.strip()]
    assert tracked == [], f"Sensitive paths are git-tracked: {tracked}"
```

### Anti-Patterns to Avoid
- **Blanket `[[allowlists]] paths = ['''tests/.*''']` in `.gitleaks.toml`:** Suppresses ALL future findings under `tests/`, including a genuinely leaked real secret accidentally pasted into a test file. Use the fingerprint-precise inline comment instead (Pattern 3).
- **Using `gitleaks detect --source .`:** Deprecated since gitleaks v8.19.0 (still works but hidden from `--help`); current commands are `gitleaks git` (history) and `gitleaks dir` (filesystem). CONTEXT.md's own SEED-001 doc (`.planning/seeds/SEED-001-...md`) still references the old `gitleaks detect` syntax — do not copy that into the new CI job.
- **Running `gitleaks dir` as the "working tree" check without exclusions:** `dir` scans the raw filesystem and does **not** respect `.gitignore` (verified live — it picked up 2 findings inside `.venv/`, a gitignored directory). If a local "working tree" pass is ever run outside CI, scope it to tracked/staged paths, not a blanket `gitleaks dir .`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| Secret pattern detection across git history | A custom regex-grep-over-`git log -p` script | gitleaks | gitleaks maintains an actively-updated ruleset (AWS keys, GitHub tokens, generic high-entropy strings, etc.) and handles binary/large-file edge cases; a hand-rolled grep (as sketched in the old SEED-001 doc: `git log -p \| grep -iE 'api[_-]?key...'`) misses encoded/obfuscated secrets and has no false-positive suppression mechanism |
| Vulnerability-alert version resolution | Manually cross-referencing CVE databases against `requirements.txt` | GitHub Dependabot (already generating alerts via the Dependency Graph — confirmed live, `dependabot.yml` only configures *update PR* behavior, not detection) | GitHub's advisory database (GHSA) is already doing this; `dependabot.yml` is config, not new tooling |
| CodeQL query authoring | Custom AST-grep security lint rules | CodeQL's default query suite (`security-extended` optionally) | CodeQL's default suite is what RH-04 asks to keep; writing custom queries is out of scope and unnecessary for this phase |

**Key insight:** Every requirement in this phase (RH-01/04/05) is served by GitHub-native or GitHub-official tooling that is already partially wired into this repo (an existing-but-broken CodeQL workflow, an existing Dependency Graph already generating alerts). The work is bumping/adding config, not building scanning logic.

## Common Pitfalls

### Pitfall 1: gitleaks false positive on test fixtures
**What goes wrong:** A "clean scan" evidence bar (CONTEXT.md: "zero findings") can be blocked indefinitely by a legitimate test fixture that merely *looks* like a secret (high entropy string assigned to a `_key`/`_token`-named variable).
**Why it happens:** gitleaks' `generic-api-key` rule flags any high-entropy string near a credential-suggestive variable name, regardless of whether it's a mock/sentinel value.
**How to avoid:** Confirmed live in this repo — `tests/test_captcha.py:381` (`sentinel_key = "sentinel-api-key-cp03-xyzzy"`) is exactly this pattern (docstring literally says "the sentinel api key must never appear in any log record", CP-03 test). Suppress with an inline `#gitleaks:allow` comment (Pattern 3), not a scope-widening allowlist.
**Warning signs:** A finding whose `File` path is under `tests/` and whose `Secret` value contains an obviously fake/placeholder-shaped string (e.g., contains "sentinel", "test", "fake", "xyzzy", "example").

### Pitfall 2: `gitleaks dir` does not respect `.gitignore`
**What goes wrong:** Running `gitleaks dir -v .` locally (the "working tree" half of RH-01's audit) picks up findings inside `.venv/`, `__pycache__/`, or any other gitignored-but-locally-present directory, producing false alarm noise unrelated to what's actually trackable.
**Why it happens:** `dir` mode is a plain filesystem walk; only `git` mode is git-aware (scans `git log -p`, i.e., only ever-committed content).
**How to avoid:** For local RH-01 verification, prefer `gitleaks git -v .` (full history, git-tracked-only, exactly matches "no secret ever tracked") over `gitleaks dir`. If a working-tree-inclusive check is genuinely needed (to catch a secret staged-but-not-yet-committed), scope the `dir` scan explicitly (e.g., `git diff --cached --name-only` piped through, or a `--gitleaks-ignore-path` pointing at `.venv`), not a blanket `.`.
**Warning signs:** Findings whose `File` path starts with `.venv/`, `node_modules/`, or other clearly-vendored/ignored directories.

### Pitfall 3: GitHub Actions Node.js 20 retirement — broader than the two actions RH-04 names
**What goes wrong:** CONTEXT.md's placeholder recommendation (`checkout@v4`, `codeql-action@v3`) reflects what was current at discuss-phase time but is now stale. As of this research date (2026-07-02), GitHub's runner default has already switched to Node24 (the forced-default-switch milestone was 2026-06-02/06-16); Node20-labeled actions require the `ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION=true` opt-out to keep running today, and Node20 is fully removed from runners 2026-09-16. `actions/checkout@v4`, `actions/setup-python@v5`, and `github/codeql-action@v3` are all Node20-based.
**Why it happens:** Actions marketplace majors don't automatically track Node runtime EOL; each action publisher cuts a new major (checkout v6, setup-python v6, codeql-action v4) specifically for the Node24 migration, and repos pinned to the previous major silently accumulate deprecation risk until the hard cutoff.
**How to avoid:** This phase must bump to `checkout@v6` (not v4) and `codeql-action@v4` (not v3) — corrected in this research (see Standard Stack). `ci.yml`'s existing `actions/checkout@v4` + `actions/setup-python@v5` carry the same risk but are not literally named by RH-04/05's wording — flagged as an Open Question for the planner rather than silently folded in or silently ignored.
**Warning signs:** Workflow run logs showing "Node.js 20 actions are deprecated" warnings, or (after 2026-09-16) hard failures with no warning grace period.

### Pitfall 4: CodeQL default-setup vs. advanced-setup conflict
**What goes wrong:** If a repo has GitHub's "default setup" for code scanning enabled, pushing an advanced (workflow-file-based) CodeQL configuration errors out with a conflict, because GitHub refuses to run two CodeQL configurations simultaneously.
**Why it happens:** GitHub offers two mutually-exclusive CodeQL setup paths: "default" (UI-toggled, no workflow file) and "advanced" (a workflow YAML like this repo's existing `codeql-analysis.yml`).
**How to avoid:** Checked live for this repo: `gh api repos/thezoid/ShopPyBot/code-scanning/default-setup` → `{"state":"not-configured", ...}`. No conflict exists — the advanced/workflow-file approach (already in place, just broken on retired actions) is safe to keep and fix in place.
**Warning signs:** A CodeQL run failing immediately with a message referencing "default setup" or "already configured."

### Pitfall 5: Dependabot alert `manifest_path` can be stale/mislabeled for `pyproject.toml` optional-dependencies
**What goes wrong:** All 3 open jinja2 alerts (#8, #9, #10) report `manifest_path: "requirements.txt"`, but `jinja2` is not declared in `requirements.txt` at all — it is pinned only in `pyproject.toml`'s `[project.optional-dependencies].web` list (confirmed via `grep` + cross-referenced against the live GitHub Dependency-Graph SBOM, which shows `jinja2 3.1.4` matching the `pyproject.toml` pin exactly).
**Why it happens:** GitHub's dependency-graph/Dependabot alert manifest attribution does not always retroactively re-resolve when a package's declaration moves between manifest files; the alert may have been opened when jinja2's declaration lived elsewhere, or the attribution logic groups all `pip`-ecosystem findings under a single manifest label.
**How to avoid:** Apply the jinja2 version bump in `pyproject.toml` (`"jinja2==3.1.4"` → `"jinja2==3.1.6"`), not `requirements.txt`. Verify post-bump via `gh api repos/thezoid/ShopPyBot/dependency-graph/sbom` that the resolved version updated.
**Warning signs:** An alert's `manifest_path` doesn't match `grep -rn "<package>" requirements.txt pyproject.toml` — always verify against the actual file before editing.

### Pitfall 6: `platformdirs` is declared in both `requirements.txt` and `pyproject.toml`
**What goes wrong:** Dependabot has a documented failure mode (dependabot-core issue #6625) where a dependency constrained in *both* `pyproject.toml` and `requirements.txt` in the same directory can cause Dependabot to silently skip opening an update PR for that package.
**Why it happens:** Dependabot's pip-ecosystem resolver treats a same-directory `requirements.txt` + `pyproject.toml` pair as potentially conflicting sources of truth; historically most common in Poetry-style projects where this pairing is unintentional.
**How to avoid:** `platformdirs==4.10.0` is currently identical in both files (`requirements.txt` line 6, `pyproject.toml` line 9) — consistent, not conflicting, and not part of the 7 open alerts, so no immediate action is required. Flagged so the planner/executor doesn't spend time chasing a missing platformdirs Dependabot PR later and mistake it for a bug in `dependabot.yml`.
**Warning signs:** Dependabot opens PRs for `cryptography`, `pydantic-settings`, and `jinja2` but never for `platformdirs`, even after a new platformdirs release ships.

### Pitfall 7: `cryptography` version jump size (44 → 49, 5 majors)
**What goes wrong:** A large major-version jump *could* carry breaking API changes; blindly trusting "latest patches all CVEs" without checking the changelog risks a red test suite.
**Why it happens:** `cryptography` follows a roughly-quarterly major-version cadence (CalVer-adjacent); 44.0.2 → 49.0.0 spans about 15 months of releases.
**How to avoid:** Changelog audited live (cryptography.io + WebSearch cross-reference): 45.0.0 deprecates CAST5/SEED/IDEA/Blowfish into a `decrepit` module, 48.0.0 deprecates TripleDES/ARC4, 49.0.0 removes SECT binary-curve support and requires OpenSSL 3.0+ (bundled in the PyPI wheel, not a system dependency). ShopPyBot's actual usage (`core/credentials.py`, `core/session_store.py`) is limited to `Fernet`, `InvalidToken`, and `hazmat.primitives.kdf.scrypt.Scrypt` — none of the deprecated/removed surface. Still: **run the full pytest suite after the bump and treat a red result as a signal to fall back to the minimum-patched floor (48.0.1) rather than latest.**
**Warning signs:** Any `ImportError`/`AttributeError` referencing `cryptography.hazmat.primitives.ciphers.algorithms.{CAST5,SEED,IDEA,Blowfish,TripleDES,ARC4}` or `EllipticCurveType.SECT*` — none of which appear in this codebase today.

## Code Examples

### Full RH-04 minimal diff (codeql-analysis.yml)
```yaml
# Source: current file read (E:\repos\ShopPyBot\.github\workflows\codeql-analysis.yml)
#         + actions/starter-workflows code-scanning/codeql.yml (live-fetched)
#         + version corrections per Pitfall 3 (checkout v6 not v4, codeql-action v4 not v3)

name: "CodeQL"

on:
  push:
    branches: [ master, dev ]
  pull_request:
    branches: [ master, dev ]
  schedule:
    - cron: '23 5 * * 5'

jobs:
  analyze:
    name: Analyze
    runs-on: ubuntu-latest
    permissions:
      actions: read
      contents: read
      security-events: write

    strategy:
      fail-fast: false
      matrix:
        include:
          - language: python
            build-mode: none

    steps:
    - name: Checkout repository
      uses: actions/checkout@v6

    - name: Initialize CodeQL
      uses: github/codeql-action/init@v4
      with:
        languages: ${{ matrix.language }}
        build-mode: ${{ matrix.build-mode }}

    - name: Perform CodeQL Analysis
      uses: github/codeql-action/analyze@v4
      with:
        category: "/language:${{matrix.language}}"
```
Diff summary: `checkout@v2→v6`; `codeql-action/init@v1→v4` + `build-mode: none` input added; `codeql-action/autobuild@v1` step **removed entirely** (not needed for interpreted languages, and being phased out generally in favor of the `build-mode` input); `codeql-action/analyze@v1→v4` + `category` input added (matches current official template); matrix restructured from `language: [ 'python' ]` to `include: - language: python, build-mode: none`. `on:`/`permissions:`/cron schedule unchanged.

### RH-05 dependabot.yml
```yaml
# Source: docs.github.com dependabot-options schema (cross-referenced via WebSearch,
#         dual-manifest pip pattern per dependabot-core known-issue #6625 — see Pitfall 6)
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

  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 5
    labels:
      - "dependencies"
      - "github-actions"
```
A single `pip` ecosystem entry with `directory: "/"` covers **both** `requirements.txt` and `pyproject.toml` in the repo root — no separate entry needed per manifest file.

### RH-01 proof commands (`.gitignore` correctness — live output from this session)
```bash
$ git check-ignore -v config.yml data/shop_py_bot.db data/creds.bin data/sessions/amazon.bin
.gitignore:7:/config.yml       config.yml
.gitignore:8:data/*            data/shop_py_bot.db
.gitignore:8:data/*            data/creds.bin
.gitignore:8:data/*            data/sessions/amazon.bin

$ git ls-files | grep -iE '\.db$|\.bin$|config\.yml$|creds|session'
# (only test files and planning docs matched — zero real artifacts tracked)
```

### RH-01 full-history gitleaks scan (live output from this session)
```
$ gitleaks git -v --report-path gitleaks-history-report.json .
Finding:     sentinel_key = "sentinel-api-key-cp03-xyzzy"
RuleID:      generic-api-key
File:        tests/test_captcha.py
Line:        381
Commit:      58b71117032e8e8f2c514d75e99f62fe8ab51e02
964 commits scanned.
scanned ~9395475 bytes (9.40 MB) in 932ms
leaks found: 1
```
After adding `#gitleaks:allow` to `tests/test_captcha.py:381`, re-running this exact command is expected to report `leaks found: 0` — that is the "zero findings" evidence artifact for the phase summary.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `gitleaks detect --source .` | `gitleaks git .` / `gitleaks dir .` | v8.19.0 (command deprecated, still functions but hidden from `--help`) | The old SEED-001 planning doc and CONTEXT.md's original phrasing both reference the deprecated `detect` verb; use `git`/`dir` in any new tooling |
| `github/codeql-action/{init,autobuild,analyze}@v1`/`@v2`/`@v3` | `@v4` | v2 deprecated 2025-01-10; v3 deprecation announced 2025-10-28, effective Dec 2026; v4 released with Node24 runtime | v1 is fully non-functional today (Node16 removed); v3 still works but is on a deprecation clock and is Node20 (same EOL exposure as checkout@v4) |
| Separate `codeql-action/autobuild` step | `build-mode` input on `codeql-action/init` (`none`/`autobuild`/`manual`) | Current official starter-workflow pattern | For Python (interpreted, no build step needed), `build-mode: none` replaces the autobuild step outright |
| `actions/checkout@v4` (Node20) | `actions/checkout@v6` (Node24) | v6.0.0, per release notes "Update README to include Node.js 24 support" | GitHub's runner-default forced-switch to Node24 already occurred (2026-06-02/06-16) as of this research date; Node20 full removal 2026-09-16 |
| `gitleaks/gitleaks-action@v2` (Node20) | `@v3` (Node24) | v3.0.0, explicit migration notice in README dated to this Node20-EOL timeline | v2 already requires `ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION=true` to run as of this research date |

**Deprecated/outdated:**
- `github/codeql-action@v1`/`@v2`: v1 non-functional (Node16 removed by GitHub); v2 deprecated since 2025-01-10.
- `actions/checkout@v2`/`@v3`: Node16-based, non-functional on current GitHub-hosted runners.
- `gitleaks detect`/`gitleaks protect` CLI subcommands: hidden since gitleaks v8.19.0; use `gitleaks git`/`gitleaks dir`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|----------------|
| A1 | Recommending `cryptography==49.0.0` (latest) rather than the minimum-patched floor `48.0.1` is safe for this codebase's actual usage surface | Standard Stack, Pitfall 7 | Changelog was audited and cross-referenced against this repo's actual `Fernet`/`Scrypt` call sites (no deprecated-cipher usage found), but the executor should still confirm via a green full pytest run before merging; if red, fall back to `48.0.1` |
| A2 | `default_workflow_permissions: write` (confirmed live via API) will remain unchanged by the time this phase executes/pushes | Pattern 2 | Low risk — this is a repo setting, not something this phase modifies; if changed by the operator, gitleaks-action's PR-comment feature (not its fail-on-finding behavior) would silently no-op |

**All other claims in this research were verified live** (via `gh api`, `pip index versions`, a real gitleaks binary execution with SHA256-verified download, and direct reads of official GitHub template/README sources) rather than sourced from training-data assumptions — no additional user-confirmation items beyond A1/A2 above.

## Open Questions

1. **Should `ci.yml`'s `checkout@v4`/`setup-python@v5` be bumped in this phase too?**
   - What we know: Both are Node20-based and carry the same EOL exposure documented in Pitfall 3 (forced-default-switch already passed 2026-06; hard removal 2026-09-16).
   - What's unclear: RH-04/RH-05 as literally worded only name the CodeQL workflow and dependabot.yml — `ci.yml`'s test job is not explicitly in scope.
   - Recommendation: Fold it in as a low-risk, one-line-per-step addition to the phase (bump `checkout@v4→v6`, `setup-python@v5→v6` in `ci.yml`) since the phase's own goal statement is "the repo's CI actually scans... and reports a clean, trustworthy result" — leaving a second, adjacent Node20 time bomb ticking while fixing the CodeQL one is inconsistent with that goal. If descoped, track as a fast-follow before 2026-09-16.

2. **Exact final pin: `cryptography==49.0.0` vs. a range (`>=48.0.1,<50`)?**
   - What we know: CONTEXT.md's existing pins in `requirements.txt` are all exact-pinned (`==`), matching the project's established convention (every other line in `requirements.txt` uses `==`).
   - What's unclear: Whether exact-pinning `cryptography==49.0.0` re-triggers a fresh Dependabot alert the moment `49.0.1`/`50.0.0` ships with any future CVE (same treadmill RH-05 exists to clear), vs. a range giving Dependabot room to auto-patch.
   - Recommendation: Keep exact-pin (`==49.0.0`) to match the existing file convention and this milestone's "preserve constraint style" spirit; Dependabot's `github-actions`/`pip` ecosystems in the new `dependabot.yml` will open a PR automatically for the next patch release regardless of pin style.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `gh` CLI | Pulling live Dependabot alerts, checking default-setup state, pushing/verifying CI runs | ✓ | 2.89.0, authenticated as `thezoid` with `repo`+`workflow` scopes | — |
| `git` | All RH-01 proof commands | ✓ | (system git via Bash tool) | — |
| `gitleaks` CLI | Local full-history/working-tree scan | ✗ (not pre-installed in this dev environment) | — | Downloaded `gitleaks_8.30.1_windows_x64.zip` from the official GitHub release for this research session (SHA256-verified against maintainer checksums) — same approach works for the executor; the CI job (`gitleaks-action@v3`) does not require a local install at all |
| Python / pip | Version verification (`pip index versions`), dependency bumps | ✓ | Python 3.13 (local); repo requires >=3.11 | — |
| `slopcheck` | Package legitimacy audit | ✓ (installed this session via `pip install slopcheck`) | latest | — |
| `go` | Building gitleaks from source (not needed — prebuilt binary used instead) | ✓ (present but unused) | — | n/a |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** `gitleaks` CLI — not pre-installed locally, but the official prebuilt binary was downloaded and checksum-verified for this research session; the CI enforcement path (`gitleaks-action@v3`) is self-contained and needs no local install.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio 1.3.0 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths = ["tests"]`, `asyncio_mode = "auto"`) |
| Quick run command | `pytest --tb=short -q` |
| Full suite command | `pytest --tb=short` (matches `ci.yml`'s existing `Test` step exactly — no separate quick/full tier exists in this repo; no pytest markers for slow tests were found) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|-------------|
| RH-01 | No sensitive path (`config.yml`, `data/*.db`, `*creds.bin`, `sessions/*.bin`) is git-tracked | unit (fast local guard) | `pytest tests/test_no_tracked_secrets.py -x` | ❌ Wave 0 (new file, mirrors existing `tests/test_no_committed_sessions.py`) |
| RH-01 | Zero gitleaks findings across full git history | CI-job-level (not pytest) | `gitleaks git -v .` — exit code 0 | N/A — enforced by the new `gitleaks.yml` job, not a test file (per CONTEXT.md's local-vs-live-CI verification boundary) |
| RH-04 | CodeQL workflow YAML is syntactically valid | local pre-push check | `python -c "import yaml; yaml.safe_load(open('.github/workflows/codeql-analysis.yml'))"` | ✅ (no new file — ad hoc command, already proven to work against both existing workflow files this session) |
| RH-04 | CodeQL Actions run completes green | live-CI (not pytest) | `gh run list --workflow=codeql-analysis.yml` / `gh run watch` after push | N/A — live-CI verification per CONTEXT.md boundary |
| RH-05 | `dependabot.yml` is syntactically valid | local pre-push check | `python -c "import yaml; yaml.safe_load(open('.github/dependabot.yml'))"` | ❌ Wave 0 (file doesn't exist yet) |
| RH-05 | 3 version bumps (`cryptography`, `pydantic-settings`, `jinja2`) don't regress existing behavior | full-suite regression | `pytest --tb=short` (887-passed baseline must hold) | ✅ (existing full suite — no new test file, this is the existing regression net) |
| RH-05 | Dependabot alert queue reaches 0 open | live-CI (not pytest) | `gh api repos/thezoid/ShopPyBot/dependabot/alerts?state=open --paginate` after the 3 bumps merge | N/A — live-CI verification per CONTEXT.md boundary |

### Sampling Rate
- **Per task commit:** `pytest --tb=short -q` (fast — flat suite, no slow-marker tier exists to skip)
- **Per wave merge:** `pytest --tb=short` (full suite — same command, no distinct "full" tier in this repo)
- **Phase gate:** Full suite green before `/gsd:verify-work`; additionally, live-CI gates (`gh run list` for CodeQL green, `gh api .../dependabot/alerts?state=open` for zero-open) per the CONTEXT.md verification boundary — these are checked post-push, not local-verifiable.

### Wave 0 Gaps
- [ ] `tests/test_no_tracked_secrets.py` — covers RH-01's local-guard half (mirrors `tests/test_no_committed_sessions.py`)
- [ ] `.github/dependabot.yml` — does not exist yet (RH-05)
- [ ] `.github/workflows/gitleaks.yml` — does not exist yet (RH-01)

*(No test-framework install gap — pytest/pytest-asyncio already fully configured and green per the 887-passed baseline in STATE.md.)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|----------------|---------|-------------------|
| V2 Authentication | no | Phase touches CI tooling only, no auth code paths |
| V3 Session Management | no | Phase touches CI tooling only, no session code paths (though `SessionStore`/`EncryptedFileBackend` are the *subject* of the secret-scanning audit, not modified) |
| V4 Access Control | no | Not applicable to CI/dependency tooling |
| V5 Input Validation | no | Not applicable — no user-facing input surfaces touched |
| V6 Cryptography | yes (indirectly) | `cryptography` library bump (44.0.2→49.0.0) is exactly a V6-relevant dependency; existing `Fernet`+`scrypt` usage in `core/credentials.py`/`core/session_store.py` is unchanged by this phase (version bump only, no crypto-logic changes) — never hand-roll crypto, already followed |

### Known Threat Patterns for CI/CD + Python dependency ecosystem

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|-----------------------|
| Secret committed to git history (API keys, credential-store passphrase, populated `config.yml`) | Information Disclosure | gitleaks CI job (RH-01) — full-history scan on every push, fails the job on any finding |
| Known-CVE dependency shipped to production (e.g., the 7 open alerts) | Elevation of Privilege / Information Disclosure (varies by CVE — e.g., #6/#11 are high-severity cryptography issues) | Dependabot alerts (already generating) + `dependabot.yml` automated update PRs (RH-05) + this phase's immediate 3-package remediation |
| Malicious/compromised GitHub Action supply-chain (a `uses:` reference pointing at an unpinned or attacker-controlled tag) | Tampering | All actions recommended in this research are first-party (`actions/*`, `github/codeql-action`, `gitleaks/gitleaks-action`) referenced by verified major-version tags resolved live against each org's own GitHub repo — not third-party forks |
| CodeQL/SAST scan silently not running (misconfigured workflow, retired action) | Repudiation (false sense of security — "we have CodeQL" while it's actually failing every run) | RH-04's core purpose: bump retired actions so the workflow actually executes; verified live that no default-setup conflict masks this |

## Sources

### Primary (HIGH confidence)
- `gh api repos/thezoid/ShopPyBot/dependabot/alerts?state=open --paginate` — live pull of all 7 open alerts, this session
- `gh api repos/thezoid/ShopPyBot/code-scanning/default-setup` — live confirmation of `state: "not-configured"`, this session
- `gh api repos/thezoid/ShopPyBot/dependency-graph/sbom` — live resolved-version cross-reference for cryptography/jinja2/pydantic-settings
- `gh api repos/thezoid/ShopPyBot/actions/permissions/workflow` — live confirmation `default_workflow_permissions: write`
- `gh api repos/actions/checkout/tags`, `repos/github/codeql-action/tags`, `repos/actions/setup-python/tags`, `repos/gitleaks/gitleaks-action/tags` — live major-version tag enumeration
- `gh api repos/actions/checkout/releases/tags/v6.0.0`, `repos/actions/setup-python/releases/tags/v6.0.0` — live release-body confirmation of Node24 migration point
- `raw.githubusercontent.com/gitleaks/gitleaks-action/main/README.md` — live-fetched, dated Node20-EOL migration notice, license requirements, exact usage YAML
- `raw.githubusercontent.com/gitleaks/gitleaks/master/README.md` — live-fetched, exact CLI command reference (`git`/`dir`/`stdin`, `#gitleaks:allow` syntax, `.gitleaksignore` syntax)
- `gh api repos/actions/starter-workflows/contents/code-scanning/codeql.yml` — live-fetched official GitHub starter template
- `gh api repos/github/codeql-action/contents/.github/workflows/__build-mode-none.yml` — live-fetched official build-mode-none example from the codeql-action repo's own PR-check fixtures
- Live gitleaks scan execution (binary downloaded from `gh release download v8.30.1 --repo gitleaks/gitleaks`, SHA256-verified against `gitleaks_8.30.1_checksums.txt`) against this exact repo — `gitleaks git -v .` (964 commits, 1 finding) and `gitleaks dir -v .` (3 findings incl. `.venv/` noise)
- `pip index versions cryptography|pydantic-settings|jinja2` — live PyPI version checks

### Secondary (MEDIUM confidence)
- [Upcoming deprecation of CodeQL Action v3](https://github.blog/changelog/2025-10-28-upcoming-deprecation-of-codeql-action-v3/) — GitHub Changelog, WebSearch-surfaced, cross-referenced against live tag data
- [Deprecation of Node 20 on GitHub Actions runners](https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/) — GitHub Changelog, WebSearch-surfaced, cross-referenced against gitleaks-action's own README timeline (both sources agree)
- cryptography.io changelog (45.0.0 through 49.0.0 breaking-change summary) — WebSearch-surfaced, cross-referenced against this repo's actual `cryptography` usage via `grep`

### Tertiary (LOW confidence)
- None — every finding in this research was either directly executed/verified live, or cross-referenced against a second independent source before being stated as fact.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every version number was resolved via a live `gh api` call against the actual publisher repo, not training-data recall
- Architecture: HIGH — the minimal diffs for both `codeql-analysis.yml` and the new `gitleaks.yml`/`dependabot.yml` are built directly from live-fetched official templates
- Pitfalls: HIGH — Pitfalls 1, 2, 4, 5, 6 were each directly reproduced/confirmed against this exact repo during research (not theoretical); Pitfalls 3 and 7 are cross-referenced against 2+ independent sources

**Research date:** 2026-07-02
**Valid until:** 2026-08-01 (30 days — CI action major versions and the Dependabot alert queue are fast-moving; re-verify action versions and re-pull the alert list if planning is delayed past this window, especially given the active Node20 EOL clock running through 2026-09-16)
