# Phase 35: Audit-Fixes & Doc-Hygiene Cleanup - Context

**Gathered:** 2026-07-02
**Status:** Ready for planning
**Mode:** Smart discuss (autonomous). Trailing cleanup phase — the requirements are prescriptive, so decisions below are the requirements themselves plus the mechanism at Claude's discretion. Low-effort, low-risk.

<domain>
## Phase Boundary

Resolve the three outstanding low-severity v4.1-audit warnings (AF-01/02/03) and reconcile the v4.0/v4.1 planning-artifact frontmatter (DH-01/02/03) so the audit 3-source cross-reference accurately reflects each phase's actual passing validation status.

**In scope:** AF-01 SSR remove-button graceful degradation; AF-02 remove raw `last_heartbeat` from get_status + SSE frames; AF-03 delete dead `escHtml()`; DH-01/02/03 frontmatter reconciliation on historical VALIDATION.md/SUMMARY.md files.

**Out of scope:** any behavior change beyond the three audit fixes; rewriting historical planning-artifact BODIES (only frontmatter reconciliation, and only to reflect what actually passed — never to fabricate status).
</domain>

<decisions>
## Implementation Decisions

### AF-01 SSR remove-button graceful degradation
- The dashboard SSR items-table remove button must remove an item even when the JS `loadItems()` fetch/render path fails. **Mechanism (Claude's discretion):** make the SSR-rendered remove action a real server-side action (an HTML form POST to a remove route, or a link that hits a remove endpoint) so it works without the JS render path, degrading gracefully. **RESEARCH:** locate the current SSR items-table + remove button + the JS loadItems() path; determine whether a remove endpoint already exists to POST to, or one must be added (prefer reusing an existing remove route). Zero-Node.
- **Test:** simulate a failed `loadItems()` fetch and confirm the SSR-rendered remove action still functions (removes the item).

### AF-02 remove raw last_heartbeat
- `get_status()` and the SSE status frames must NOT contain the raw `last_heartbeat` monotonic float; only the derived `heartbeat_age_secs` (already computed in v4.1 Phase 28-02). **RESEARCH:** find where `last_heartbeat` is put into the get_status() dict / status payload and remove it, keeping `heartbeat_age_secs`. Confirm nothing downstream (dashboard JS, SSE consumers) depends on the raw field.
- **Test:** assert the raw `last_heartbeat` field is ABSENT from both the get_status() output and the SSE status frame; `heartbeat_age_secs` still present.

### AF-03 remove dead escHtml()
- Delete the dead `escHtml()` helper from the dashboard frontend source. **RESEARCH:** confirm it is genuinely dead (zero call sites) before removing. **Test/verify:** grep confirms `escHtml` no longer exists anywhere in the dashboard frontend.

### DH-01/02/03 frontmatter reconciliation (mechanical, MUST reflect actual status)
- **DH-01:** v4.1 VALIDATION.md frontmatter for phases 25/26/27 → `status: validated`, `wave_0_complete: true`.
- **DH-02:** v4.1 SUMMARY.md frontmatter for phases 27/28/29 → add `requirements:` listing the phase's requirement IDs so the audit 3-source cross-reference reports OBS-01/02/03/04/06/09 as VERIFIED.
- **DH-03:** v4.0 VALIDATION.md `nyquist_compliant` → `true` for phases 18-24.
- **HARD CONSTRAINT:** these flags may only be flipped to reflect what ACTUALLY passed. **RESEARCH/VERIFY:** confirm each phase's suite actually passed (the milestone history + green test suites indicate they did) before flipping. Do NOT fabricate — the frontmatter merely lagged the real passing status. If any phase did NOT actually pass, leave its flag and flag the discrepancy.
- **RESEARCH:** locate the exact file paths (these v4.0/v4.1 artifacts may live under `.planning/phases/` or an archived milestones directory) and the exact requirement IDs to add for DH-02.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- The v4.1 dashboard: `web/templates/dashboard.html` (SSR items table, remove button, escHtml, loadItems), `web/routes/` (item routes — a remove endpoint may exist), `core/service.py` get_status (heartbeat_age_secs computed in get_snapshot per v4.1 Phase 28-02 decision).
- The historical planning artifacts under `.planning/` (VALIDATION.md / SUMMARY.md for phases 18-29).

### Established Patterns
- Zero-Node; CSS 3-file split; textContent (no innerHTML) for DOM safety; credential-scrub at the get_status boundary (which is exactly why AF-02 matters — keep the surface clean).
- get_status already derives heartbeat_age_secs; AF-02 just removes the raw source field from the surface.

### Integration Points
- `web/templates/dashboard.html` (AF-01 SSR remove, AF-03 escHtml), a remove route (AF-01), `core/service.py`/get_status + SSE status frame (AF-02), the v4.0/v4.1 VALIDATION.md/SUMMARY.md frontmatter (DH-01/02/03).
</code_context>

<specifics>
## Specific Ideas

- AF-01 must be proven by a failed-fetch simulation test (SSR path works independently of JS).
- AF-02 must assert absence from BOTH get_status() AND the SSE status frame.
- DH reconciliation reflects actual passing status only — verify before flipping; this is the milestone's own audit-hygiene, so accuracy matters most.
- Also worth surfacing (not necessarily in scope): the recurring STATE.md schema drift (SDK verbs can't parse the custom `Last action`/`Next action` field format) + the stale project CLAUDE.md architecture section (still describes pre-refactor amazon_bot.py/bestbuy_bot.py) — research should note if either is cheaply reconcilable within the DH spirit, but do NOT expand scope beyond AF/DH without flagging.
</specifics>

<deferred>
## Deferred Ideas

- Broader doc overhaul beyond the specified frontmatter reconciliation.
- Rewriting historical planning-artifact bodies.
</deferred>
