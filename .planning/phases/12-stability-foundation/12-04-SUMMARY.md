---
phase: 12-stability-foundation
plan: "04"
subsystem: docs/verification
tags: [manual-checks, platforms, stab-01, deferred-debt]
dependency_graph:
  requires: ["12-03"]
  provides: ["STAB-01 documentation closure"]
  affects: ["docs/PLATFORMS.md"]
tech_stack:
  added: []
  patterns: []
key_files:
  created: []
  modified:
    - docs/PLATFORMS.md
decisions:
  - "MC-1..MC-4 Windows variants recorded PENDING (non-interactive agent env, no real TTY/restart cycle available) -- must be completed by a human on an interactive Windows session"
  - "MC-1..MC-4 Ubuntu variants recorded 'pending Ubuntu access' (no Ubuntu host or WSL2 in this environment)"
  - "MC-4 banner Jinja2 conditional is CI-asserted by tests/test_web_dashboard.py (Plan 12-03); live browser render still requires human confirmation"
metrics:
  duration: "5 minutes"
  completed: "2026-06-09"
  tasks_completed: 2
  files_changed: 1
---

# Phase 12 Plan 04: Manual-Checks Documentation Summary

One-liner: Documented MC-1..MC-4 deferred manual checks in docs/PLATFORMS.md with explicit PENDING statuses for all cells that require an interactive TTY, OS keyring restart, or Ubuntu host.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Execute MC-1/MC-2/MC-3/MC-4 (environment assessment) | n/a (environment gate, no interactive TTY) | -- |
| 2 | Record MC-1..MC-4 results in docs/PLATFORMS.md | see commit | docs/PLATFORMS.md |

## What Was Done

### Task 1: Environment Assessment

The plan's checkpoint:human-verify for live OS checks was evaluated against the execution environment. This run executes inside a non-interactive Windows agent (no real TTY, no browser, no process-restart cycle possible). Per the documented environment_constraint fallback:

- MC-1 (keyring restart survival, Windows): requires `shoppybot setup` + full process exit + new process start + no env vars. Not performable in agent environment.
- MC-2 (masked-TTY passphrase prompt, Windows): requires a real interactive terminal and a human observer to confirm no-echo. Not performable in agent environment.
- MC-3 (web dashboard live render, Windows): requires a browser session and human observation of Start/Stop + log polling. Not performable in agent environment.
- MC-4 (0.0.0.0 banner live render): the automated TestClient assertion was committed in Plan 12-03 (`tests/test_web_dashboard.py`, `test_banner_renders_when_non_local` + `test_banner_absent_when_local`). The live browser render requires a human observer.
- Ubuntu variants of all four checks require an Ubuntu host or WSL2, neither available.

### Task 2: docs/PLATFORMS.md Updated

All MC-1..MC-4 table cells in the Phase 8, 9, and 10 Deferred Live Checks sections now contain explicit statuses:

- Windows columns: `PENDING -- pending interactive manual run on a real Windows TTY`
- Ubuntu columns: `pending Ubuntu access`
- N/A columns: unchanged (preserved from original table)
- Dated execution notes added above each section explaining why PENDING was recorded

No bare `[ ]` cells remain in the deferred-check sections. The main manual checklist matrix (Core CLI Commands, Credential Backend Selection, Path Resolution) retains its original `[ ]` cells as those are not MC-1..MC-4 and are out of scope for this plan.

## Deviations from Plan

### Environment-driven deviation: no live check results recorded

The plan was written as a checkpoint:human-verify plan (blocking gate). Per the autonomous_authorization and environment_constraint overrides in the execution prompt, the agent proceeded to document PENDING rather than halting for a human who cannot run the checks in this environment. This is the documented fallback path in the plan itself.

No code was changed. Pytest suite unchanged: 359 passed, 2 skipped.

## Verification

- docs/PLATFORMS.md Phase 8/9/10 deferred-check rows: no bare `[ ]` cells. Confirmed by grep.
- "pending Ubuntu" appears in the file (grep count > 0). Confirmed.
- pytest: 359 passed, 2 skipped. Unchanged from Plan 12-03 baseline.

## Known Stubs

None. This is a documentation-only plan.

## Threat Flags

None. Documentation-only plan; no new code surface introduced.

## STAB-01 Status

STAB-01 is partially closed: the deferred-check tables are fully populated with explicit statuses. The four Windows interactive checks and all Ubuntu checks remain PENDING and must be completed by a human on a real interactive session. The MC-4 automated assertion is committed and green in CI.

## Self-Check: PASSED

- docs/PLATFORMS.md exists and contains PENDING/pending Ubuntu access in all MC rows: confirmed
- No bare `[ ]` in Phase 8/9/10 deferred sections: confirmed
- pytest 359 passed, 2 skipped: confirmed
