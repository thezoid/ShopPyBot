# Phase 3: Community Documentation - Context

**Gathered:** 2026-06-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Add the community-facing governance docs so external contributors can submit plugins, report security issues, and engage safely: `CONTRIBUTING.md`, a repo-root `SECURITY.md` (responsible-disclosure policy + per-platform risk), GitHub issue templates, and a PR template. Documentation only — no application code changes. Covers DOCS-01..DOCS-05.

NOT in scope: the plugin technical how-to (already shipped as `plugins/PLUGIN_DEV.md` in Phase 2 — link to it, don't duplicate), CI workflows, or new app behavior.
</domain>

<decisions>
## Implementation Decisions

### Security & Disclosure (SECURITY.md — DOCS-02)
- Disclosure channel: GitHub private security advisories AND a contact email; do NOT use public issues for vulnerabilities.
- Per-platform risk presented as a 3-tier table (low / medium / high) capturing both anti-detection risk and TOS/legal risk for each supported platform (Amazon, BestBuy now; new platforms append their row).
- Coordinated disclosure: acknowledge within 7 days, target 90-day coordinated disclosure window.
- Legal scope mirrors the README disclaimer: personal/non-commercial use, provided as-is/no-warranty, each contributor and operator is responsible for complying with retailer Terms of Service and applicable law.

### CONTRIBUTING Workflow (DOCS-01, DOCS-05)
- CONTRIBUTING.md covers the contribution PROCESS (fork → branch → implement → test → PR) and LINKS to `plugins/PLUGIN_DEV.md` for plugin-specific technical detail; it does not duplicate the ABC/how-to content.
- Tests required: each new plugin must ship a pytest test file; the full suite must be green before a PR is accepted.
- Anti-detection risk declaration is mandatory: every plugin PR declares a risk level (low/med/high) with rationale, surfaced both in the PR and the plugin's module docstring.
- Style rules mirror the repo: Conventional Commits, PEP8 / snake_case, no new dependencies without justification.

### Issue & PR Templates (DOCS-03, DOCS-04)
- Two GitHub issue templates as YAML forms under `.github/ISSUE_TEMPLATE/`: (a) bug report, (b) new-plugin / platform request — each with required fields.
- PR template checklist: RetailerPlugin ABC compliance, `shopbot_plugin_*.py` naming convention, test file present and suite green, anti-detection risk declared, no secrets/credentials committed.
- Include a short Code of Conduct (Contributor Covenant reference).
- `.github/ISSUE_TEMPLATE/config.yml`: `blank_issues_enabled: false` with a contact link pointing security reports to SECURITY.md / the private advisory channel.

### Claude's Discretion
- Exact wording/section ordering of each doc, the placeholder contact email/handle (use a clearly-marked placeholder for the maintainer to fill), and the precise YAML field set per template, provided the required fields above are present.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `plugins/PLUGIN_DEV.md` (Phase 2): the plugin technical guide — CONTRIBUTING links to it.
- `README.md`: already contains the Disclaimer (personal-use, TOS, no-warranty) — SECURITY.md legal scope should be consistent with it.
- `.planning/phases/01-foundations-security/01-SECURITY.md`: the internal STRIDE threat model (engineering artifact) — distinct from the community-facing repo-root SECURITY.md this phase creates.

### Established Patterns
- Security posture from Phase 1: credentials only via env/getpass, never logged or in config — CONTRIBUTING/PR checklist must reinforce "no secrets committed".
- Naming convention `shopbot_plugin_*.py` and the RetailerPlugin v2 ABC (Phase 2) — referenced by CONTRIBUTING + PR checklist.

### Integration Points
- New files live at repo root (`CONTRIBUTING.md`, `SECURITY.md`) and under `.github/` (PR template, `ISSUE_TEMPLATE/`). No source code touched.
</code_context>

<specifics>
## Specific Ideas

- Contact email/handle should be a clearly-marked placeholder for the maintainer to fill in (do not invent a real address).
- Per-platform risk table seeds rows for Amazon and BestBuy; Phase 6's new platforms each add a row.
</specifics>

<deferred>
## Deferred Ideas

- CI/GitHub Actions workflows (lint/test on PR) — not in this phase's scope.
- Automated plugin-risk linting/enforcement — future enhancement; this phase only requires a human-declared risk level.
</deferred>

---

*Phase: 3-community-documentation*
*Context gathered: 2026-06-03*
