# Phase 12: Stability Foundation - Context

**Gathered:** 2026-06-09
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase — discuss skipped)

<domain>
## Phase Boundary

Pay down v2.0 deferred debt and audit tech-debt before v3.0 features land, producing a reliable test baseline. Scope is exactly: (1) execute and document the 4 deferred cross-OS/UI manual checks (keyring restart survival, masked-TTY passphrase prompt, web dashboard render on Ubuntu, `0.0.0.0` bind warning), fixing any failures; (2) add a targeted regression test for each of the 4 v2.0 audit tech-debt items. No broad refactors — only the specific in-scope items change.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure/debt-paydown phase. Use the ROADMAP success criteria, requirements STAB-01 and STAB-02, the v2.0 milestone audit findings, and existing codebase test conventions to guide decisions. Hard constraint from success criteria: no broad refactors, change only the specific items in scope.

</decisions>

<code_context>
## Existing Code Insights

Codebase context (existing pytest suite under `tests/`, keyring/passphrase handling, web dashboard, bind-address logic, and the recorded v2.0 audit tech-debt items) will be gathered during plan-phase research.

</code_context>

<specifics>
## Specific Ideas

The exact 4 audit tech-debt items must be sourced from the v2.0 milestone audit artifacts during planning. Each gets one targeted regression test that passes in CI. Manual checks must be documented pass/fail even where they cannot be automated on this platform.

</specifics>

<deferred>
## Deferred Ideas

None — infrastructure phase.

</deferred>
