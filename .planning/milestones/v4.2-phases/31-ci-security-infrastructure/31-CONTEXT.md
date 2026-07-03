# Phase 31: CI & Security Infrastructure - Context

**Gathered:** 2026-07-02
**Status:** Ready for planning
**Mode:** Smart discuss (autonomous) — infrastructure phase, no user-facing behavior; grey-area questions skipped, best-practice decisions pre-selected at Claude's discretion.

<domain>
## Phase Boundary

The repo's CI actually scans for secrets and vulnerabilities and reports a clean, trustworthy result: no tracked secrets or credential artifacts (RH-01), a green CodeQL run (RH-04), and a valid `.github/dependabot.yml` with a clean/triaged vulnerability alert queue (RH-05).

**In scope:** non-destructive secret audit of git history + working tree; `.gitignore` correctness verification; CodeQL workflow action-version bump to supported releases; `dependabot.yml` creation; remediation (bump or documented-dismiss) of the 7 currently-open dependabot alerts (2 high, 4 moderate, 1 low, confirmed on the remote default branch).

**Explicitly OUT of scope (operator-gated debt, per REQUIREMENTS.md deferral table):** the destructive SEED-001 history rewrite / force-push / secret rotation / collaborator re-clone. RH-01 covers ONLY the non-destructive audit; if the audit finds a tracked secret, the deliverable is to surface it + fix `.gitignore` + stop tracking it going forward, NOT to rewrite history. Any found secret requiring rotation is flagged as operator debt, not actioned autonomously.
</domain>

<decisions>
## Implementation Decisions

### Secret Scanning (RH-01) — Claude's Discretion, recommended defaults
- Tool: **gitleaks** (fast, single-binary, standard GitHub Action, scans full history). trufflehog acceptable as an alternative if gitleaks is unavailable in the runner.
- Scope of the audit: full `git log`/history + working tree. Evidence of success = a clean gitleaks run (zero findings) captured in the phase summary.
- `.gitignore` must demonstrably exclude: `config.yml`, `data/*.db` (and any `*.db`), and credential-store artifacts (the encrypted session/credential files). Verify each is ignored (`git check-ignore`) and NOT currently tracked (`git ls-files`).
- Add a lightweight **gitleaks CI job** to the GitHub Actions workflow so secret scanning is ongoing, not a one-time local check (this is "CI & Security Infrastructure" — bake the scan into CI). Keep it non-blocking-hostile: fail the job on findings.

### CodeQL (RH-04) — Claude's Discretion, recommended defaults
- Bump retired action versions in the CodeQL workflow: `actions/checkout@v2 → @v4`, `github/codeql-action/*@v1 → @v3`. Bump any other retired actions in the same workflow to current supported majors.
- Language matrix: Python (this is a Python repo). Keep the default query suite.
- "Green run in Actions" is verified post-push via `gh run` on the pushed branch (live-CI verification — see verification boundary below).

### Dependabot + Vulnerability Remediation (RH-05) — Claude's Discretion, recommended defaults
- Create `.github/dependabot.yml` with two ecosystems: `pip` (Python deps — requirements.txt and/or pyproject) and `github-actions`. Weekly schedule, sensible open-PR limits.
- Remediate the 7 open alerts by bumping the affected dependency to the patched version in `requirements.txt` (and `pyproject.toml` if it pins). Preserve the existing hard version constraints from prior milestones (do NOT upgrade FastAPI past the v4.1-pinned range, do NOT add sse-starlette, do NOT introduce Node — per logged v4.1 decisions).
- If an alert cannot be remediated without violating a pinned constraint or breaking tests, document the tradeoff and dismiss with a written rationale rather than forcing a breaking upgrade. Every dismissal gets a one-line justification in the phase summary.
- After bumps, the full pytest suite (887 passed baseline) must stay green.

### Verification Boundary (autonomous, live-CI)
- Code-complete + CI-green is the DoD. Local-verifiable now: gitleaks clean, `.gitignore` correctness, workflow YAML validity, `dependabot.yml` validity, dependency bumps applied, tests green.
- Live-GitHub-verifiable only after push: the CodeQL Actions run turning green and the dependabot alert queue draining. These are checked via `gh run list` / `gh api` after the phase pushes; if the runner is unavailable in this session, they are recorded as CI-verification debt (not code gaps), consistent with the autonomous live-check deferral policy.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- Existing GitHub Actions workflows under `.github/workflows/` (a CodeQL workflow already exists — it is failing on retired action versions, per RH-04). The phase edits these in place rather than authoring from scratch.
- `requirements.txt` + `pyproject.toml` are the dependency source of truth. `pyproject` defines the `[web]` extra (`pip install -e .[web]`).
- Existing `.gitignore` already excludes most artifacts; RH-01 verifies + tightens it, not rewrites it.

### Established Patterns
- Zero-Node constraint is hard (no package.json, no CDN). Python-only toolchain.
- Prior milestones pinned FastAPI/uvicorn and forbade certain upgrades — those pins are constraints on RH-05 remediation.

### Integration Points
- `.github/workflows/*` (CodeQL + any secret-scan job), `.github/dependabot.yml` (new), `.gitignore`, `requirements.txt`, `pyproject.toml`.
</code_context>

<specifics>
## Specific Ideas

- The 7 open dependabot alerts (2 high, 4 moderate, 1 low) are confirmed present on the remote default branch (observed on every push during Phase 30). Pull the concrete list via `gh api /repos/{owner}/{repo}/dependabot/alerts?state=open` during planning/research to drive exact version bumps.
- Non-destructive only: never `git filter-repo`, `git rebase -i` history rewrite, or force-push in this phase.
</specifics>

<deferred>
## Deferred Ideas

- Destructive SEED-001 history scrub/squash, secret rotation, force-push, collaborator re-clone — operator-gated, out of milestone scope.
</deferred>
