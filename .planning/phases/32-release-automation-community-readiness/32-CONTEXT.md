# Phase 32: Release Automation & Community Readiness - Context

**Gathered:** 2026-07-02
**Status:** Ready for planning
**Mode:** Smart discuss (autonomous). Mostly infra + docs with clear best-practice defaults; the one true user decision (RH-07 security contact) was surfaced to the operator, who was away — resolved with a privacy-safe default (see decisions).

<domain>
## Phase Boundary

The repo is ready to cut its first public release: the version source of truth is consistent (RH-03), release-please automates changelog/tagging from conventional commits seeded at v2.0.0 (RH-02), and the README + security/community docs are accurate for a new contributor or operator (RH-06, RH-07).

**In scope:** pyproject version reconcile to 2.0.0; release-please workflow + config + manifest seeded at 2.0.0 (python release-type); README rewrite for accuracy; SECURITY.md + CODE_OF_CONDUCT.md real contact.

**Depends on:** Phase 31 (release-please should land against a CI pipeline with working CodeQL/dependabot — done).

**Explicitly OUT of scope:** actually cutting/publishing the first GitHub release (release-please seeds the automation; the operator triggers the first release by merging the release PR). Destructive SEED-001 history scrub remains operator-gated.
</domain>

<decisions>
## Implementation Decisions

### RH-03 Version Reconcile — locked
- Set `pyproject.toml` canonical `version` to `2.0.0`. Verify no other conflicting version source exists (e.g., a `__version__` in the package) and reconcile if found so release-please has a single source of truth.

### RH-02 Release-please — Claude's Discretion, recommended defaults
- Use `googleapis/release-please-action` (current major) in a `.github/workflows/release-please.yml` triggered on push to the default branch (master).
- `release-type: python`. Seed via the manifest approach: `.release-please-manifest.json` set to `{ ".": "2.0.0" }` and a `release-please-config.json` with the python release-type + the package config. Seeding at 2.0.0 makes the first release-please run treat 2.0.0 as the current version and compute the next bump from conventional-commit history.
- Verify by a dry-run / manifest read that the seed is 2.0.0 and conventional-commit history parses. The actual release PR / tag is operator-triggered (out of scope), so "green run in Actions" is CI-verification debt (post-push).
- Do NOT introduce Node tooling for the app itself (Zero-Node constraint) — release-please runs as a GitHub Action, not a local dep, so it does not violate the constraint.

### RH-06 README — locked to success criteria
Rewrite/verify README to accurately document:
- The 7-platform ecosystem (Amazon, BestBuy, Walmart, Target, GameStop, NewEgg, SquareEnix).
- Web dashboard + observability (SSE, health surface, log filtering), price monitoring, anti-detection (fingerprint/proxy + 2captcha), encrypted session persistence.
- Prereq: Python 3.11+.
- Install: `pip install -e .[web]`; run via the `shoppybot` console entry point.
- Badges must resolve (CI, CodeQL, license, python-version as applicable) — no dead/placeholder badges.
- Clone URL must be the real repo: `https://github.com/thezoid/ShopPyBot.git`. Remove any placeholder/example URLs.
- Optional compatibility note: cryptography 49.0.0 (pinned in Phase 31) dropped 32-bit Windows and x86_64 macOS wheels — if README has a platform/support section, note 64-bit only; otherwise skip (do not invent a section).

### RH-07 Security Contact — operator decision, resolved with privacy-safe default
- The operator was asked which contact to publish; away at decision time. Resolved to: **use GitHub Private Vulnerability Reporting as the channel**, NOT a published email address.
- SECURITY.md instructs reporters to use the repo's "Report a vulnerability" flow (GitHub Security Advisories: `https://github.com/thezoid/ShopPyBot/security/advisories/new`). CODE_OF_CONDUCT.md enforcement-contact points to the same private reporting channel (or a maintainer note), NOT a fake email.
- Remove ALL occurrences of `SECURITY_CONTACT_PLACEHOLDER@example.com` across the repo (RH-07 success criterion). Do NOT substitute the maintainer's personal/business email — publishing a private address on a public repo is a lasting exposure the operator did not explicitly authorize.
- Add a single clear operator note in SECURITY.md (or the phase SUMMARY) that Private Vulnerability Reporting must be enabled once in repo Settings → Security & analysis for the flow to work. Do NOT toggle that repo setting autonomously.
- This satisfies RH-07's "zero placeholder occurrences" criterion without email exposure. If the operator later prefers an email, it's a one-line edit.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `pyproject.toml` (canonical version source; defines `[web]` extra + the `shoppybot` console script).
- Existing `.github/workflows/` (CI + CodeQL + gitleaks from Phase 31) — release-please.yml is added alongside.
- Existing README.md, SECURITY.md, CODE_OF_CONDUCT.md (the placeholder lives in the latter two).

### Established Patterns
- Conventional-commit messages are used throughout (type(scope): desc) — release-please depends on this and the history is compliant.
- Zero-Node for the app; pinned FastAPI/uvicorn.

### Integration Points
- `.github/workflows/release-please.yml` (new), `release-please-config.json` + `.release-please-manifest.json` (new), `pyproject.toml`, `README.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`.
</code_context>

<specifics>
## Specific Ideas

- Real repo: `thezoid/ShopPyBot` (public). All URLs/badges target this.
- release-please seed version: 2.0.0 (matches RH-03 pyproject reconcile — single source of truth for the python release-type).
- Grep the whole repo for `SECURITY_CONTACT_PLACEHOLDER@example.com` and `example.com` to catch every occurrence before declaring RH-07 done.
</specifics>

<deferred>
## Deferred Ideas

- Cutting/publishing the actual first GitHub release (operator merges the release-please PR).
- Enabling GitHub Private Vulnerability Reporting toggle (operator, one-time, repo Settings).
- Destructive SEED-001 history scrub — operator-gated, out of milestone scope.
</deferred>
