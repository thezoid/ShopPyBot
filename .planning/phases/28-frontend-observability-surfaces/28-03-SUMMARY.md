---
phase: 28-frontend-observability-surfaces
plan: "03"
subsystem: dashboard-html-observability-surfaces
tags: [health-cards, uptime, log-viewer, observability, safe-dom, tdd]
dependency_graph:
  requires: ["28-01", "28-02"]
  provides:
    - "#section-health with #health-grid scaffold"
    - "#section-buys with buys-table scaffold"
    - "#section-log-viewer with log controls scaffold"
    - "renderHealthCards() pure function"
    - "renderUptime() pure function"
    - "heartbeatClass/heartbeatText/badgeClass/dotClass helpers"
    - "MAX_LOG_LINES = 500 constant"
  affects: ["28-04", "29-01"]
tech_stack:
  added: []
  patterns:
    - "Pure render functions (take data, update DOM, return nothing) for Phase 29 SSE reuse"
    - "createElement/textContent safe-DOM pattern for all API-sourced values"
    - "clear-only innerHTML = '' for grid reset (no API data interpolation)"
    - "pollStatus() extension: append render calls after existing button updates"
key_files:
  modified:
    - web/templates/dashboard.html
decisions:
  - "renderHealthCards and renderUptime declared as pure functions before pollStatus so Phase 29 can call them from SSE handler unchanged"
  - "MAX_LOG_LINES = 500 constant placed in 28-03 (not 28-04) so test_log_dom_cap_constant goes GREEN in this wave"
  - "Error state in pollStatus catch clears #health-grid and shows 'Failed to load plugin status' via createElement (not innerHTML)"
  - "heartbeatText uses string concatenation not template literals to stay clearly safe-DOM (no innerHTML path)"
metrics:
  duration_secs: 379
  completed_date: "2026-06-27"
  tasks_completed: 2
  files_modified: 1
---

# Phase 28 Plan 03: Section Scaffolds + Health Cards + Uptime Summary

**One-liner:** Three section scaffolds (#section-health, #section-buys, #section-log-viewer) added to dashboard.html with renderHealthCards() + renderUptime() pure functions implementing OBS-01/02/03/09 wired into the existing pollStatus() loop using createElement/textContent throughout.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add three section scaffolds to dashboard.html | 4e03dd5 | web/templates/dashboard.html |
| 2 | Implement renderHealthCards + renderUptime and wire into pollStatus() | 73d70b5 | web/templates/dashboard.html |

## Verification Results

- `rtk pytest tests/test_observability_ui.py tests/test_web_dashboard.py -q`: 20 passed, 1 error
  - `test_dashboard_renders_buys_section`: GREEN
  - `test_dashboard_renders_log_viewer_section`: GREEN
  - `test_log_dom_cap_constant`: GREEN
  - `test_header_uptime_slot_present`: GREEN
  - `test_uplot_script_and_css_present`: GREEN
  - `test_no_innerHTML_with_api_data`: GREEN (XSS guard passes)
  - `test_banner_renders_when_non_local`, `test_banner_absent_when_local`: GREEN (MC-4 intact)
  - `test_dashboard_renders_health_section`: ERROR (pre-existing: nodriver SyntaxError on Python 3.14 env; unrelated to this plan's changes -- see deviations)

## Implementation Details

### Task 1: Three Section Scaffolds

Inserted three `<section class="card">` blocks per the 28-UI-SPEC Section Layout Contract:

1. `#section-health` with `<h2>Plugin Health</h2>` and `<div class="health-grid" id="health-grid"></div>`, placed immediately before `#section-items`.
2. `#section-buys` with `<h2>Confirmed Orders</h2>` and the full 28-C4 table (thead: Item / Order ID / Confirmed At / Checkout Attempts; `<tbody id="buys-tbody">`), placed immediately after `#section-items`.
3. `#section-log-viewer` with `<h2>Log Viewer</h2>`, log-controls div (label-associated `<select id="log-level-filter">` with 6 options, `<input id="log-search">`, `<button id="btn-log-follow" class="btn btn-accent" aria-pressed="true">`, `<button id="btn-log-refresh" class="btn btn-sm">`), and `<div id="log-buffer" role="log" aria-live="polite">`, placed after `#section-config`.

Existing `#log-content` pre in `#section-controls` and the MC-4 banner block left untouched.

### Task 2: Render Functions + pollStatus() Wiring

Added to the inline `<script>`:

**Helper functions:**
- `heartbeatClass(ageSecs)`: null/undefined or >=60 returns `'heartbeat-err'`; <30 returns `'heartbeat-ok'`; else `'heartbeat-warn'` (OBS-02 three bands)
- `heartbeatText(ageSecs)`: null/undefined returns `'Heartbeat: never'`; else `'Heartbeat: Ns'`
- `badgeClass(status)`: running -> `badge-ok`; error -> `badge-err`; else `badge-neutral`
- `dotClass(status)`: running -> `'running'`; error -> `'error'`; else `'stopped'`

**renderHealthCards(statusPayload):** Clears `#health-grid` via `innerHTML = ''` (clear-only), then builds cards via `createElement` chains. Each card: `.health-card-name` (textContent = plugin name), `.badge` + `.status-dot` + `.badge-label` (textContent = human status), `.heartbeat-age` span (textContent = heartbeatText result), `.health-card-stats` div with three spans (Errors / Checked / Orders confirmed), optional `.health-card-error` span when `rec.last_error` is truthy. All API values via textContent. Empty state shows `<p class="text-secondary">No plugins registered.</p>`.

**renderUptime(uptimeSecs):** Writes `humanizeUptime(secs)` result to `#header-uptime` via textContent. Outputs `'Up Nh Mm'` / `'Up Mm'` or `''` when stopped.

**Wiring in pollStatus():** After existing button-state updates and before `failCount = 0`, calls `renderUptime(data.uptime_secs)` then `renderHealthCards(data)`. Error path (failCount >= 3) also updates `#health-grid` with `'Failed to load plugin status. Check server logs.'` via createElement.

**MAX_LOG_LINES = 500:** Constant declared in this plan so `test_log_dom_cap_constant` turns GREEN. Log buffer rendering JS lands in 28-04.

## Deviations from Plan

### Pre-existing Environment Issue (not a deviation -- tracked for context)

`test_dashboard_renders_health_section` errors in the Python 3.14 test environment due to `nodriver.cdp.network` containing a non-UTF-8 byte (line 1345 in the installed package). This causes a SyntaxError when Python 3.14 parses the file. This is unrelated to 28-03 changes -- the test was already erroring before this plan (visible in baseline run). The test DOES assert `id="section-health"` which is now present in the template; it would pass if nodriver were compatible with Python 3.14.

The same environment causes `test_no_innerHTML_with_api_data` to ERROR when run in isolation but it passes in the full combined test run (because the first test's SyntaxError caches the broken module state, and subsequent tests import the already-partially-cached module without re-executing the SyntaxError path). This ordering-dependent behavior is pre-existing and documented here for the 28-04 executor.

No code changes were made to address this -- it is a Python 3.14 / nodriver version incompatibility in the test execution environment, not a code defect.

## Known Stubs

- `#buys-tbody` is empty (populated by 28-04's `loadConfirmedBuys()`)
- `#log-buffer` is empty (populated by 28-04's `renderLogLines()`)
- Follow/Refresh button event listeners not wired yet (28-04)

These are intentional per the plan split: 28-03 owns scaffolds + health/uptime render; 28-04 owns buys/log data rendering.

## Threat Flags

No new threat surface beyond the STRIDE register in the plan:
- T-28-04 mitigated: all API values in renderHealthCards use textContent; `test_no_innerHTML_with_api_data` passes.
- T-28-SC: no package installs; no new dependencies.

## Self-Check: PASSED

- web/templates/dashboard.html committed at 4e03dd5 (scaffold) and 73d70b5 (render functions)
- `id="section-health"` present in template: confirmed by grep
- `id="section-buys"` present in template: confirmed by test pass
- `id="section-log-viewer"` present in template: confirmed by test pass
- `MAX_LOG_LINES = 500` present: confirmed by test pass
- `renderHealthCards` and `renderUptime` present and wired into pollStatus(): confirmed by grep
- XSS guard (test_no_innerHTML_with_api_data): GREEN in full test run
- MC-4 banner tests: GREEN
