---
id: SEED-001
status: dormant
planted: 2026-06-09
planted_during: v3.0 Resilience + Ecosystem (Phase 16)
trigger_when: before any public release / tag, and before announcing the repo — audit + squash git history first
scope: small
---

# SEED-001: Public repo — scrub history and squash before release

This is a PUBLIC repository (`thezoid/ShopPyBot`). Before it is released, tagged, or
announced, its git history must be audited for sensitive information and squashed so
that no secret was ever committed or pushed in an earlier commit.

## Why This Matters

The repo is public, so every pushed commit (and its full history) is world-readable
and may be cached/indexed by third parties even after deletion. A single accidental
commit of a real secret (2captcha API key, proxy credentials, a populated `config.yml`,
a real `data/shop_py_bot.db`, keyring material, a `.env`) is effectively permanent once
pushed — rotating the secret is the only true remediation, but scrubbing history limits
exposure. v3.0 added several credential-handling surfaces (proxy `user:pass@` URLs,
`TWOCAPTCHA_API_KEY` in CredentialStore) that make this audit important before release.

## When to Surface

**Trigger:** Before the first public release/tag of the project, before linking the repo
anywhere public, and any time a contributor reports a possible secret leak. Re-surface at
`/gsd:new-milestone` if a "release" or "publish" milestone is scoped.

## Scope Estimate

**Small** — a few hours, mostly verification:

1. Confirm `.gitignore` covers all sensitive paths: `config.yml`, `data/*.db`, `logs/`,
   `.env`, any credential store files. (config.yml is already gitignored per CLAUDE.md.)
2. Scan full history for secrets — e.g. `gitleaks detect`, `trufflehog`, or
   `git log -p | grep -iE 'api[_-]?key|secret|password|TWOCAPTCHA|proxy.*:.*@'`.
3. If anything is found: rotate the affected secret IMMEDIATELY (assume compromised),
   then rewrite history (`git filter-repo` / BFG) to purge it, and force-push.
4. Squash the development history into a clean release history if desired, then
   force-push the cleaned history and have collaborators re-clone.
5. Verify no large/binary artifacts (a real `shop_py_bot.db`) are tracked.

## Breadcrumbs

- `CLAUDE.md` (project) — notes `config.yml` is gitignored; `data/shop_py_bot.db` created on first run.
- `core/credentials.py` — `SECRET_KEYS` incl. `TWOCAPTCHA_API_KEY` (Phase 14).
- `core/stealth.py` / `core/config_schema.py` `ProxyConfig` — proxy `user:pass@host:port` handling (Phase 13); creds must never be in committed `config.yml`.
- `sample.config.yml` — the safe, committed template (real values go only in gitignored `config.yml`).
- GitHub already reports Dependabot vulnerabilities on the default branch — review those at release time too.

## Notes

Captured mid-autonomous-run (v3.0). The autonomous milestone run auto-commits and
auto-pushes planning docs + source to this public remote per the user's standing
authorization; those planning docs reference secret NAMES only (never values), but a
full history audit + squash is still required before the repo is treated as a public
release. Convert to a dedicated "Release Hardening" phase/todo when the milestone wraps.
