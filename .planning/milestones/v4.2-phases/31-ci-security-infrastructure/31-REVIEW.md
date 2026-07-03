---
phase: 31-ci-security-infrastructure
reviewed: 2026-07-02T20:00:00Z
depth: deep
files_reviewed: 8
files_reviewed_list:
  - .github/workflows/gitleaks.yml
  - .github/workflows/codeql-analysis.yml
  - .github/workflows/ci.yml
  - .github/dependabot.yml
  - tests/test_captcha.py
  - tests/test_no_tracked_secrets.py
  - requirements.txt
  - pyproject.toml
findings:
  critical: 0
  warning: 2
  info: 3
  total: 5
status: issues_found
---

# Phase 31: Code Review Report

**Reviewed:** 2026-07-02T20:00:00Z
**Depth:** deep
**Files Reviewed:** 8
**Status:** issues_found

## Summary

This phase adds a gitleaks secret-scan CI job, bumps CodeQL to non-deprecated
action versions with `build-mode: none`, bumps `ci.yml` off Node20-based
actions, adds `dependabot.yml`, narrowly suppresses one confirmed test-fixture
false positive, adds a fast local secret-guard test, and bumps
`cryptography` 44.0.2 -> 49.0.0 / `pydantic-settings` 2.14.0 -> 2.14.2 /
`jinja2` 3.1.4 -> 3.1.6.

Every item in the review brief was independently verified with evidence
(not just read-through):

- Installed the exact pinned dependency set (`cryptography==49.0.0`,
  `pydantic-settings[yaml]==2.14.2`, `jinja2==3.1.6`) into an isolated venv
  and ran the full test suite: **889 passed, 2 skipped, 0 failed**
  (`core/credentials.py` EncryptedFileBackend and `core/session_store.py`
  SessionStore both exercise real Fernet/Scrypt round-trips, not mocks).
- Pulled the upstream `pyca/cryptography` CHANGELOG for every release
  between 44.0.2 and 49.0.0 and confirmed none of the listed
  `BACKWARDS INCOMPATIBLE` entries touch `Fernet`, `InvalidToken`, or
  `hazmat.primitives.kdf.scrypt.Scrypt` (the only cryptography APIs this
  codebase uses). The breaking changes in that range are all X.509 / ECDSA /
  ChaCha20-nonce / platform-wheel related.
  Note: 49.0.0 drops `x86_64` macOS and 32-bit Windows wheels — not a
  concern for this project's `ubuntu-latest`/`windows-latest` CI matrix.
- Confirmed `cryptography==49.0.0` actually resolves on PyPI (it does;
  it is the current latest release), so `pip install` in `ci.yml` will not
  fail on a non-existent pin.
- Confirmed `actions/checkout@v6`, `actions/setup-python@v6`,
  `github/codeql-action/{init,analyze}@v4`, and `gitleaks/gitleaks-action@v3`
  all exist as real, resolvable tags upstream.
- Fetched `gitleaks-action`'s v3 README: confirms v2->v3 is a Node20->Node24
  runtime bump only ("no changes to inputs, outputs, or behavior") and that
  no `GITLEAKS_LICENSE` is required for personal-account repos (confirmed via
  `gh repo view`: `thezoid/ShopPyBot` is `PUBLIC`, personal account).
- Fetched `dependabot-core`'s actual Ruby source
  (`python/file_parser/pyproject_files_parser.rb`,
  `using_pep621?` checks `project.dependencies` /
  `project.optional-dependencies`) — confirms the `pip` ecosystem entry with
  `directory: "/"` genuinely parses this repo's PEP 621
  `[project.optional-dependencies].web` array, not just `requirements.txt`.
- Empirically tested `git ls-files` pathspec semantics used by
  `test_no_tracked_secrets.py` against a throwaway repo to confirm the glob
  patterns match what the docstring claims.
- Confirmed via `gh api repos/.../actions/permissions/workflow` that
  `default_workflow_permissions` is currently `write`, which is what
  `gitleaks.yml` implicitly relies on (see WR-01 below).

No critical/blocker findings. Two warnings (both hardening/consistency gaps,
neither breaks fail-closed behavior today) and three info items.

## Warnings

### WR-01: gitleaks.yml has no explicit `permissions:` block

**File:** `.github/workflows/gitleaks.yml:10-20`
**Issue:** Unlike `codeql-analysis.yml` in this same phase (which explicitly
declares `actions: read`, `contents: read`, `security-events: write`),
`gitleaks.yml` declares no `permissions:` block at all. It works today only
because the repo's `default_workflow_permissions` is currently set to
`write` (verified via `gh api repos/thezoid/ShopPyBot/actions/permissions/workflow`
-> `"default_workflow_permissions":"write"`). That is a repo-level setting,
not something encoded in the workflow file — if it is ever tightened to
`read` (GitHub's own recommended default for new repos), the `GITHUB_TOKEN`
used by `gitleaks/gitleaks-action@v3` to post PR review comments will lose
write access. The scan's pass/fail exit code (the actual "fail closed"
mechanism) is independent of the PR-comment call, so this is not a fail-open
bug, but it is:
1. An inconsistent security posture within the same phase (CodeQL scopes its
   token, gitleaks does not).
2. A silent external dependency — the workflow's real permission is not
   visible by reading the file, and GITHUB_TOKEN currently gets far broader
   write access (issues, contents, deployments, etc.) than the job needs.
**Fix:**
```yaml
jobs:
  scan:
    name: gitleaks
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v6
        with:
          fetch-depth: 0
      - uses: gitleaks/gitleaks-action@v3
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### WR-02: dependabot.yml references labels that don't exist in the repo

**File:** `.github/dependabot.yml:9-11,19-21`
**Issue:** `dependabot.yml` declares labels `dependencies`, `python`, and
`github-actions`. Verified via `gh label list`: only `dependencies` (and the
GitHub default set: bug, documentation, duplicate, enhancement, etc.)
currently exist in the repo. `python` and `github-actions` are not present.
Dependabot does not fail PR creation on a missing label, it silently omits
it, so this is not a functional break — dependency-update PRs will still be
opened and will still carry the security-relevant information — but the
triage labeling this config was clearly meant to provide (distinguishing
pip bumps from Action bumps at a glance) silently won't work until those two
labels are created.
**Fix:** Create the `python` and `github-actions` labels (`gh label create
python --color <hex>` / `gh label create github-actions --color <hex>`), or
drop them from `dependabot.yml` if the finer-grained labeling isn't needed.

## Info

### IN-01: `test_no_tracked_sensitive_paths`'s bare `config.yml` pathspec only matches repo-root

**File:** `tests/test_no_tracked_secrets.py:20-26`
**Issue:** Verified empirically (`git ls-files "config.yml"` in a scratch
repo): a bare pathspec with no wildcard and no leading `/` still only
matches `config.yml` at the repository root, not a nested path such as
`backup/config.yml`. This is consistent with `.gitignore`'s own `/config.yml`
anchor and with how `config.py` loads the file (always from repo root), so
it is not currently exploitable, but it's worth noting explicitly since the
docstring says "no sensitive path... is git-tracked" without qualifying
that `config.yml` coverage is root-only (the `data/`, `*.db`, `*creds.bin`,
and `*sessions/*.bin` entries in the same list *do* match recursively).
**Fix:** Optional — add a comment noting `config.yml` is intentionally
root-scoped, or broaden to `**/config.yml` if nested config files ever
become a supported layout.

### IN-02: gitleaks/CI coverage is scoped to `master`/`dev` push and PRs targeting them

**File:** `.github/workflows/gitleaks.yml:3-8`, `.github/workflows/ci.yml:3-7`
**Issue:** Both workflows trigger only on `push` to `[master, dev]` and
`pull_request` targeting `[master, dev]`, plus `workflow_dispatch` for
gitleaks. A secret committed on a topic/feature branch (e.g. the current
`chore/v4.0-milestone-close` branch) is not scanned until a PR is opened
against `master`/`dev`. This mirrors the pre-existing `ci.yml` trigger
footprint exactly (not a regression introduced by this phase), and
`fetch-depth: 0` does mean that once a PR *is* opened, gitleaks sees the
full history of the compare — but it's worth flagging since the commit
message describing this workflow says "full-history scan on push/PR," which
is only true relative to branches that actually reach master/dev.
**Fix:** No action required if this matches intended workflow (PR-gated
scanning). If secrets on never-merged feature branches are an actual concern,
add `push: branches: ["**"]` or a scheduled full-repo scan.

### IN-03: cryptography 49.0.0 drops 32-bit Windows and x86_64 macOS wheels

**File:** `requirements.txt:3`
**Issue:** Per upstream CHANGELOG, `cryptography` 47.0.0 deprecated and
49.0.0 removed publishing of 32-bit Windows wheels, and 49.0.0 also dropped
`x86_64` macOS wheels (arm64-only going forward). `ci.yml`'s
`windows-latest` runner is 64-bit so CI is unaffected, but this is worth
recording for anyone running ShopPyBot on 32-bit Windows or older Intel
Macs outside CI — `pip install cryptography==49.0.0` will fail to find a
compatible wheel and require a Rust toolchain to build from source.
**Fix:** No action required unless 32-bit Windows / x86_64 macOS support is
an explicit project target; if so, document the constraint in the README/
setup docs.

---

_Reviewed: 2026-07-02T20:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
