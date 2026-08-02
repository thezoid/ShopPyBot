---
phase: 35-audit-fixes-doc-hygiene-cleanup
plan: 02
subsystem: observability
tags: [fastapi, sse, cli, health-registry, information-disclosure]

# Dependency graph
requires:
  - phase: 28-frontend-observability-surfaces
    provides: heartbeat_age_secs derived field computed in HealthRegistry.get_snapshot()
provides:
  - HealthRegistry.get_snapshot() public dict with raw last_heartbeat excluded
  - core/cli/status.py reading heartbeat_age_secs instead of the raw monotonic float
  - Permanent regression guards on both the get_status() and SSE "status" frame surfaces
affects: [35-03-doc-hygiene-frontmatter]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single shaping boundary (HealthRegistry.get_snapshot()) filters a field once; every consumer (REST, SSE, CLI) inherits the fix atomically"

key-files:
  created: []
  modified:
    - core/health.py
    - core/cli/status.py
    - tests/test_health.py
    - tests/test_cli_status.py
    - tests/test_service.py
    - tests/test_orchestrator.py
    - tests/test_sse.py
    - tests/test_web_controls.py

key-decisions:
  - "core/cli/status.py lockstep fix landed in the SAME task/commit as the health.py filter, per the plan's explicit critical-lockstep requirement, avoiding a CLI 'always never' regression"
  - "test_web_controls.py's mock fixture cleanup (last_heartbeat -> heartbeat_age_secs) treated as optional non-breaking polish per RESEARCH.md, included since it was zero-cost and improves fixture realism"

patterns-established:
  - "AF-02 absence-test pattern: mirror the existing SSE credential-pattern test (test_sse_no_credential_patterns) for any future field that must never cross a public surface"

requirements-completed: [AF-02]

# Metrics
duration: 8min
completed: 2026-07-02
---

# Phase 35 Plan 02: AF-02 last_heartbeat Leak Fix Summary

**Removed the raw `last_heartbeat` monotonic float from `get_snapshot()`'s public dict (the single boundary feeding both `get_status()` and the SSE status frame), with the CLI status table updated in lockstep to read `heartbeat_age_secs` instead.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-07-02T22:41:00-04:00
- **Completed:** 2026-07-02T22:48:32-04:00
- **Tasks:** 2 completed
- **Files modified:** 8

## Accomplishments
- `HealthRegistry.get_snapshot()` (`core/health.py`) now excludes `last_heartbeat` from its public per-plugin dict while continuing to derive and keep `heartbeat_age_secs` unchanged — this single fix closes both the REST `get_status()` surface and the SSE `"status"` frame (which broadcasts `get_status()` verbatim), since both consume the same shaped dict.
- `core/cli/status.py` updated in the same task to read `heartbeat_age_secs` instead of computing `now - rec['last_heartbeat']`, eliminating the silent "always shows never" regression the raw-field removal would otherwise have caused; the now-orphaned `import time` and `now = time.monotonic()` were removed.
- Added permanent regression guards on both public surfaces: `tests/test_health.py::test_snapshot_excludes_last_heartbeat` (get_snapshot() boundary) and `tests/test_sse.py::test_sse_status_frame_excludes_last_heartbeat` (SSE frame, mirroring the existing credential-pattern test pattern), both asserting `last_heartbeat` absent and `heartbeat_age_secs` present.
- Fanned the change out across all 5 last_heartbeat-touching test files (`test_health.py`, `test_cli_status.py`, `test_service.py`, `test_orchestrator.py`, `test_web_controls.py`) plus the new SSE test in `test_sse.py`, so no test in the suite asserts the raw field's presence on any public surface.

## Task Commits

Each task was committed atomically:

1. **Task 1: Scrub raw last_heartbeat at the snapshot source + CLI lockstep (AF-02)** - `585484c` (fix)
2. **Task 2: Consumer test fan-out + SSE-frame absence proof (AF-02)** - `2143edc` (test)

**Plan metadata:** pending (docs: complete plan)

_Note: Task 1 followed TDD RED->GREEN within a single commit boundary — test file changes were verified RED against the pre-fix production code (3 failures at the exact expected fix sites) before the production-code fix was applied and re-verified GREEN, then committed together as one atomic task commit per the plan's task-commit protocol._

## Files Created/Modified
- `core/health.py` - `get_snapshot()` public-dict comprehension now also excludes `last_heartbeat`; `heartbeat_age_secs` derivation untouched
- `core/cli/status.py` - `_format_status_table` reads `heartbeat_age_secs`; removed `import time` and `now = time.monotonic()`
- `tests/test_health.py` - repurposed `test_heartbeat_sets_last_heartbeat` -> `test_heartbeat_sets_heartbeat_age_secs`; dropped `last_heartbeat` from `test_snapshot_public_keys_exact`; added `test_snapshot_excludes_last_heartbeat`
- `tests/test_cli_status.py` - `_STATUS_PAYLOAD` fixture supplies `heartbeat_age_secs`; `test_status_table` asserts the table shows a real age, not "never"
- `tests/test_service.py` - `test_get_status_shape_with_registry` expects `heartbeat_age_secs`, asserts `last_heartbeat` absent
- `tests/test_orchestrator.py` - post-cycle health assertion switched to `heartbeat_age_secs is not None`
- `tests/test_sse.py` - new `test_sse_status_frame_excludes_last_heartbeat`, mirrors `test_sse_no_credential_patterns`
- `tests/test_web_controls.py` - mock fixture cleanup, `last_heartbeat` -> `heartbeat_age_secs` (optional, non-breaking)

## Decisions Made
- CLI lockstep fix (core/cli/status.py) landed in the same task/commit as the health.py filter, exactly as the plan's critical-lockstep requirement specified — no separate commit, no window where the CLI could regress.
- Included the optional test_web_controls.py fixture cleanup since it was zero-risk (mock data only, not asserted against by the test body) and keeps the fixture representative of the real post-fix payload shape.

## Deviations from Plan

None - plan executed exactly as written. Both tasks matched the plan's `<action>` and `<acceptance_criteria>` blocks precisely; no Rule 1-4 auto-fixes were needed.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

AF-02 is fully closed: raw `last_heartbeat` is absent from both public surfaces (get_status()/REST and SSE), `heartbeat_age_secs` is retained on both, and the CLI status table renders real elapsed-time values with no "never" regression. Full suite green: 939 passed, 2 skipped (baseline 937 + 2 net-new tests, no regressions). Ready for 35-03 (DH-01/02/03 frontmatter reconciliation), which touches only `.planning/` YAML frontmatter and has no file overlap with this plan.

---
*Phase: 35-audit-fixes-doc-hygiene-cleanup*
*Completed: 2026-07-02*

## Self-Check: PASSED

- FOUND: core/health.py
- FOUND: core/cli/status.py
- FOUND: tests/test_sse.py
- FOUND: .planning/phases/35-audit-fixes-doc-hygiene-cleanup/35-02-SUMMARY.md
- FOUND: 585484c
- FOUND: 2143edc
