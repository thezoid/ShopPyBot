---
phase: 28-frontend-observability-surfaces
plan: "02"
requirements: [OBS-01, OBS-02, OBS-06]
subsystem: health-backend + css-design-system
tags: [health, css, observability, tokens, tdd]
dependency_graph:
  requires: ["28-01"]
  provides: ["heartbeat_age_secs in get_snapshot()", "Phase 28 CSS component classes"]
  affects: ["28-03", "28-04", "29-01"]
tech_stack:
  added: []
  patterns:
    - "Server-side derived field computed once in get_snapshot() (monotonic clock delta)"
    - "Token-only CSS classes extending Phase 25 design system"
key_files:
  modified:
    - core/health.py
    - web/static/components.css
decisions:
  - "heartbeat_age_secs computed in get_snapshot() not at route boundary so Phase 29 SSE poll reads the field automatically"
  - "round(now - last_heartbeat, 1) with a single now = time.monotonic() call per snapshot"
  - "select rule added to match input[type=text] styling so log level dropdown inherits border/height/focus"
  - ".log-line padding: 0 (row spacing from .log-buffer line-height --leading-ui per spec)"
metrics:
  duration_secs: 262
  completed_date: "2026-06-27"
  tasks_completed: 2
  files_modified: 2
---

# Phase 28 Plan 02: Backend Heartbeat Age + Phase 28 CSS Summary

**One-liner:** Server-computed `heartbeat_age_secs` field added to `get_snapshot()` (monotonic delta, None on never-heartbeated) and all Phase 28 observability CSS classes appended to `components.css` using only `var(--xxx)` tokens.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add heartbeat_age_secs to get_snapshot() | 0e0d044 | core/health.py |
| 2 | Add Phase 28 component classes to components.css | 1d3cc97 | web/static/components.css |

## Verification Results

- `pytest tests/test_health.py -q`: 13 passed (all Wave 0 health tests GREEN including test_heartbeat_age_secs_fresh, test_heartbeat_age_secs_never, test_snapshot_public_keys_exact)
- `pytest tests/test_design_system.py -q`: 3 passed (zero hardcoded hex, all required tokens declared, uPlot vendor files exist)
- Full suite: 789 passed, 4 failed (test_observability_ui.py scaffold tests -- expected RED until 28-03/28-04), 2 skipped

## Implementation Details

### Task 1: core/health.py get_snapshot()

Rewrote `get_snapshot()` to:
1. Compute `now = time.monotonic()` once.
2. Build the public-key dict for each plugin (stripping `_`-prefixed keys).
3. Append `heartbeat_age_secs`: `None` when `last_heartbeat == 0.0` (never-heartbeated sentinel from `_ensure`), else `round(now - lhb, 1)`.

Computation lives in `get_snapshot()` -- not at the route boundary -- so the Phase 29 SSE poll loop that calls `get_snapshot()` directly will include the field without any additional wiring.

### Task 2: web/static/components.css

Appended 147 lines of new component rules covering all Phase 28 surfaces:
- `.health-grid` with responsive `@media (max-width: 640px)` breakpoint
- `.health-card` family (name, stats, error)
- `.status-dot.error` (completes the running/stopped/error trio)
- `.badge` family (ok, neutral, err)
- `.heartbeat-age` + three staleness band classes (ok/warn/err)
- `.chart-container` + `.chart-empty`
- `.log-viewer`, `.log-controls`, `select` rule, `.log-buffer` (300px, monospace)
- `.log-line` with `padding: 0` per spec
- `.log-level-*` five level classes (error/warn/info/debug/trace)

All colors use `var(--color-status-*/--color-text*/--color-surface/--color-bg/--color-border)`. Layout dimensions (220px minmax, 300px height) are pixel layout values, not color/spacing tokens, and are permitted per spec.

## Deviations from Plan

None -- plan executed exactly as written.

## Known Stubs

None -- this plan adds backend computation and CSS only; no UI rendering or data wiring.

## Threat Flags

No new threat surface. T-28-03 (CSS color injection) mitigated: all colors via declared `var(--xxx)` tokens; `test_no_hardcoded_hex_in_components` guard passes.

## Self-Check: PASSED

- core/health.py modified and committed (0e0d044) -- verified by test suite (13 passed)
- web/static/components.css modified and committed (1d3cc97) -- verified by design-system suite (3 passed)
- No web/templates/dashboard.html changes made (owned by 28-03/28-04)
- Observability UI scaffold tests remain RED as expected (4 failures in test_observability_ui.py)
