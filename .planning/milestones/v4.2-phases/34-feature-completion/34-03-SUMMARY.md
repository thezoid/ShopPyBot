---
phase: 34-feature-completion
plan: 03
subsystem: api
tags: [analytics, fastapi, sqlite, dashboard, jinja2, xss-safe-dom]

# Dependency graph
requires:
  - phase: 30-breakfix-hardening
    provides: place_order_attempted_at write-ahead marker (BF-02) used as the attempted/time-to-checkout anchor
  - phase: 19-db-schema-confirmation-detection
    provides: order_id/confirmed_at confirmation columns (BUY-04) and the CONFIRMED-<ts> sentinel convention
provides:
  - PURE core/analytics.py:compute_analytics(rows, platform_of) -- success_rate + time_to_checkout, overall + per-plugin
  - models.get_order_analytics_rows_sync() read-only accessor over items
  - BotService.get_analytics() seam resolving link -> platform_key via registry domain_patterns
  - GET /api/analytics (aggregate-only JSON, no link/credential leak)
  - Dashboard analytics view (stat cards + per-plugin table)
affects: [35-audit-fixes-doc-hygiene]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure computation module (core/analytics.py) with zero DB/framework imports, tested via exact-fixture assertions -- no mocking needed"
    - "link resolved to platform_key inside BotService.get_analytics only; never forwarded to the JSON response (data minimization at the seam, not the route)"

key-files:
  created:
    - core/analytics.py
    - tests/test_analytics.py
  modified:
    - models.py
    - core/service.py
    - web/routes/api.py
    - web/templates/dashboard.html
    - tests/test_api_observability.py

key-decisions:
  - "success_rate denominator (attempted) = place_order_attempted_at IS NOT NULL OR order_id IS NOT NULL -- deliberately excludes checkout_attempts, which increments even under test_mode and would deflate the rate"
  - "time_to_checkout scoped to the two durable buy-flow timestamps (place_order_attempted_at -> confirmed_at); no earlier detection-timestamp anchor exists in the schema, so the metric is honestly scoped rather than invented"
  - "CONFIRMED-<ts> sentinel counted in attempted, excluded from confirmed (unverified order, per core/confirmation.py)"

patterns-established:
  - "Analytics stat cards reuse .health-card/.health-grid verbatim (label + value only, no badge/status-dot) -- zero new CSS for a new dashboard surface"

requirements-completed: [FC-02]

# Metrics
duration: 15min
completed: 2026-07-02
---

# Phase 34 Plan 3: Outcome Analytics Summary

**Operator-facing success-rate and time-to-checkout analytics computed from existing BUY-04 order records via a pure, fixture-tested `compute_analytics` function, exposed through a read-only `GET /api/analytics` endpoint and a new dashboard stat-card + table view.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-07-02T20:39:00Z (approx, session start)
- **Completed:** 2026-07-02T20:51:00Z
- **Tasks:** 3
- **Files modified:** 6 (2 created, 4 modified)

## Accomplishments
- `core/analytics.py:compute_analytics(rows, platform_of)` -- a pure function (stdlib `datetime` only, no DB/fastapi imports) computing `success_rate` and `avg_time_to_checkout_secs` overall and per-plugin, verified exact against a deterministic 4-row fixture plus edge cases (empty dataset, missing-timestamp exclusion, sentinel exclusion, checkout_attempts-is-not-a-denominator)
- `models.get_order_analytics_rows_sync()` read-only accessor mirroring `get_confirmed_orders_sync`
- `BotService.get_analytics()` resolves `link -> platform_key` via `PluginRegistry.domain_patterns` (no hardcoded plugin list, no new plugin/platform column) and delegates to `compute_analytics`
- `GET /api/analytics` (read-only, `asyncio.to_thread`, no `check_origin` dep, matches `/status` `/history` `/logs` convention) returns aggregate-only JSON
- Dashboard `#section-analytics`: two `.health-card` stat cards (overall success rate, avg time-to-checkout) + a bare `<table id="analytics-table">` per-plugin breakdown, rendered via `createElement`/`textContent` only; null metrics render `"N/A"`

## Task Commits

Each task was committed atomically (TDD RED->GREEN for Task 1):

1. **Task 1 RED: failing fixture tests** - `45e51a7` (test)
2. **Task 1 GREEN: compute_analytics + models accessor** - `c66fc6a` (feat)
3. **Task 2: BotService.get_analytics + GET /api/analytics** - `9bf6652` (feat)
4. **Task 3: dashboard analytics view** - `71abe90` (feat)

**Plan metadata:** (this commit, pending)

## Files Created/Modified
- `core/analytics.py` - PURE `compute_analytics(rows, platform_of)`, `_summarize`, `_merge`, `_is_confirmed` sentinel guard
- `tests/test_analytics.py` - exact-fixture success_rate/time_to_checkout assertions, empty-dataset, missing-timestamp exclusion, checkout_attempts-denominator-exclusion tests
- `models.py` - `get_order_analytics_rows_sync()` read-only accessor
- `core/service.py` - `BotService.get_analytics()` (registry-based `platform_of` closure)
- `web/routes/api.py` - `GET /analytics` route
- `tests/test_api_observability.py` - analytics endpoint tests (aggregate-only, no-link-key recursive check, CRED_PATTERN, empty-dataset)
- `web/templates/dashboard.html` - `#section-analytics` markup + `pollAnalytics()`/`renderAnalytics()`/`makeStatCard()`/`formatSuccessRate()`/`formatDurationSecs()` JS, wired into the initial backfill block

## Decisions Made
- Attempted denominator uses `place_order_attempted_at IS NOT NULL OR order_id IS NOT NULL` (union), never `checkout_attempts` -- matches RESEARCH.md's "State of the Art" metric-definition resolution exactly.
- No new CSS: analytics stat cards use `.health-card`/`.health-card-name`/`.health-card-stats` verbatim (a 2-element card: label + value), and the per-plugin table is a bare `<table>` mirroring the Confirmed Orders table structure.
- `link` is read only inside `BotService.get_analytics()` to build `platform_of`; the row dicts built in `compute_analytics` are keyed by the 7 DB columns internally, but the returned aggregate dict never carries `link`, `order_id`, or any raw row data -- only `platform_key` + counts/rates.

## Deviations from Plan

None - plan executed exactly as written. All three tasks matched the plan's `<action>` and `<acceptance_criteria>` blocks verbatim; no Rule 1-4 auto-fixes were needed.

## Issues Encountered

None.

## Threat Flags

None - the plan's `<threat_model>` (T-34-05, T-34-06, T-34-07, T-34-SC) fully covers the new surface introduced by this plan; no additional network endpoints, auth paths, or schema changes were introduced beyond what the plan declared.

## Known Stubs

None - the analytics view is fully wired end-to-end (real DB read -> BotService -> compute_analytics -> JSON -> dashboard render); no hardcoded/mock data paths.

## User Setup Required

None - no external service configuration required. No new dependencies (stdlib `datetime` + existing `sqlite3`/`fastapi`).

## Next Phase Readiness

FC-02 is fully satisfied: pure fixture-exact analytics, a leak-free read-only endpoint, and a dashboard view all landed with full test coverage. Phase 34 (Feature Completion) is now fully complete -- FC-01 (34-01) and FC-02 (34-02 was actually the log-filter plan, not yet executed as of this plan's start; see note below) are both required by the phase, but this plan (34-03) only covers FC-02. Phase 34 overall completion depends on 34-02 (the `/api/logs` plugin-filter plan) also landing.

No blockers for Phase 35 (Audit-Fixes & Doc-Hygiene Cleanup).

---
*Phase: 34-feature-completion*
*Completed: 2026-07-02*

## Self-Check: PASSED

All created/modified files confirmed present on disk; all 4 task commit hashes
(45e51a7, c66fc6a, 9bf6652, 71abe90) confirmed present in git log.
