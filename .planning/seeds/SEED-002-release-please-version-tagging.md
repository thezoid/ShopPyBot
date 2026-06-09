---
id: SEED-002
status: dormant
planted: 2026-06-09
planted_during: v3.0 Resilience + Ecosystem (Phase 16)
trigger_when: when setting up CI/release automation, or before the first public release/tag
scope: small
---

# SEED-002: Set up release-please for automatic version tagging (baseline v2.0)

Adopt Google's **release-please** to automate version bumping, changelog generation,
and GitHub release tagging driven by Conventional Commits. The product release version
should be seeded at **v2.0** (this is the second major revision of the product).

## Why This Matters

The repo already uses Conventional Commit messages (`type(scope): description`), which is
exactly release-please's input. Automating tags + CHANGELOG removes manual release bookkeeping,
gives users a clear version history, and pairs naturally with the public-repo release hardening
in [[SEED-001-public-repo-history-scrub-squash]]. Establishing a real semantic version line also
makes the milestone work shippable.

## When to Surface

**Trigger:** When wiring CI/CD or release automation, and before the first public release/tag.
Re-surface at `/gsd:new-milestone` if a "release", "CI", or "publish" milestone is scoped.

## Scope Estimate

**Small** — a few hours:

1. Add a `release-please` GitHub Action workflow (`.github/workflows/release-please.yml`) targeting
   the `master`/default branch.
2. Configure release type `simple` or `python` (project is Python; pick based on whether a version
   string lives in code, e.g. a `__version__`). Seed the initial version at **v2.0.0** via
   `release-please-config.json` + `.release-please-manifest.json` (`{".": "2.0.0"}`).
3. Confirm Conventional Commit prefixes already in use map to release-please's bump rules
   (`feat` → minor, `fix` → patch, `feat!`/`BREAKING CHANGE` → major).
4. Let release-please open/maintain a release PR; merging it tags + publishes the GitHub release
   and updates `CHANGELOG.md`.

## Note on versioning (important)

There are TWO independent version lines, do not conflate them:
- **GSD milestone numbering** (internal planning): currently "v3.0 Resilience + Ecosystem" — this
  is the planning roadmap milestone, NOT the product release version.
- **Product release version** (release-please tags): seed at **v2.0.0** per the user, since this is
  the product's second major revision. release-please manages this line going forward.

## Breadcrumbs

- `CLAUDE.md` (project + global) — Conventional Commit format already enforced (`type(scope): description`).
- `.github/` — existing PR template + issue templates; release-please workflow lands here.
- `CHANGELOG.md` — release-please will create/maintain this if absent.
- Related: [[SEED-001-public-repo-history-scrub-squash]] (do the history audit/squash before the first release tag).

## Notes

Captured mid-autonomous-run (v3.0 milestone). Convert to a dedicated "Release Automation" phase/todo
when the milestone wraps. Decide the release-please `release-type` (simple vs python) when a
canonical version string location is chosen.
