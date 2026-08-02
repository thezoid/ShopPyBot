---
phase: 28-frontend-observability-surfaces
plan: "04"
requirements: [OBS-04, OBS-06]
subsystem: frontend/dashboard
tags: [observability, uplot, log-viewer, confirmed-buys, price-charts, xss-safe]
dependency_graph:
  requires: ["28-01", "28-02", "28-03"]
  provides: ["loadConfirmedBuys", "loadPriceChart", "renderLogLines", "appendLogLine", "pollLogs-extended"]
  affects: ["web/templates/dashboard.html"]
tech_stack:
  added: []
  patterns:
    - "loadConfirmedBuys: GET /api/history -> makeCell/textContent rows into #buys-tbody"
    - "loadPriceChart: URL-safe b64 + Date.parse(p.t)/1000 -> new uPlot(opts, [ts, prices], el)"
    - "logLevelClass: /^\\[(\\w+)\\]/ regex maps level prefix to log-level-* CSS class"
    - "renderLogLines: clear-only innerHTML='', appendLogLine each, DOM cap trim loop"
    - "pollLogs extended in-place: URLSearchParams n=500 + level/search from DOM"
    - "Follow logic: scroll listener pauses, click listener resumes, maybeScrollToBottom"
key_files:
  modified:
    - web/templates/dashboard.html
decisions:
  - "chart containers injected as sibling divs below #items-table (not nested tr>td); avoids nested-div-in-tr table constraint"
  - "pollLogs extended in-place (not refactored); keeps existing #log-content pre updated alongside new renderLogLines()"
  - "IIFE scope used for follow toggle and filter control listeners to avoid polluting global scope"
  - "logSearchTimer declared as module-scoped var for 300ms debounce on search input"
metrics:
  duration_secs: 420
  completed_date: "2026-06-27"
  tasks_completed: 2
  files_modified: 1
---

# Phase 28 Plan 04: Frontend Observability Data Surfaces Summary

**One-liner:** Confirmed-buys table, per-item uPlot price charts with ISO->Unix conversion and correct URL-safe b64 encoding, and a filterable color-coded log viewer with Follow/pause-on-scroll and 500-line DOM cap.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | loadConfirmedBuys() and loadPriceChart() | 137be25 | web/templates/dashboard.html |
| 2 | Log viewer render, pollLogs() extended, Follow logic | d701353 | web/templates/dashboard.html |

## What Was Built

### Task 1: Confirmed Buys + Price Charts

`loadConfirmedBuys()` fetches `GET /api/history` and populates `#buys-tbody`:
- Empty state: single `<tr>` with `<td colspan="4" class="text-secondary">No confirmed orders yet.</td>`
- Data rows: four `makeCell()` calls per order (name, order_id, confirmed_at as-is, String(checkout_attempts))
- Error state: single colspan-4 row "Failed to load order history. Check server logs."
- Called once in the page-load block alongside `loadItems()`

`loadPriceChart(itemLink)` fetches `GET /api/price-history/{b64}` per item:
- b64 uses verbatim `removeItem()` encoding: `btoa(unescape(encodeURIComponent(link))).replace(/\+/g,'-').replace(/\//g,'_')` with `=` padding kept
- CRITICAL conversion: `ts = series.map(p => Date.parse(p.t) / 1000)` converts ISO strings to Unix seconds before `new uPlot()`
- `series.length === 0`: renders `<div class="chart-empty" role="status">No price history available for this plugin.</div>`
- uPlot: width from `containerEl.clientWidth || 300`, height 120, stroke colors from `getComputedStyle` CSS tokens (no hardcoded hex), `points.show = ts.length < 2` for single-point marker
- Chart containers inserted as sibling `<div>` elements below `#items-table` (not nested inside `<tr>`)

`loadItems()` extended: sets `data-link` on each `<tr>`, builds `<div id="chart-{b64}" class="chart-container">` wrapper for each item, calls `loadPriceChart(item.link)` for each item after all rows are in DOM.

### Task 2: Log Viewer

`logLevelClass(line)`: regex `/^\[(\w+)\]/` extracts level, maps ERROR/WARNING/INFO/DEBUG/TRACE to log-level-* classes; defaults to `log-level-info` on no match.

`appendLogLine(lineText)`: creates `<span class="log-line {level-class}">` with `textContent = lineText` (never innerHTML).

`renderLogLines(lines)`: clears `#log-buffer` via `innerHTML = ''` (clear-only); shows `<p class="text-secondary">No log lines match the current filter.</p>` on empty; else appends each line; trims oldest firstChild while `children.length > MAX_LOG_LINES`; calls `maybeScrollToBottom()`.

`pollLogs()` extended in-place: reads `#log-level-filter.value` and `#log-search.value` from DOM each call; builds `URLSearchParams({n: 500})` adding level/search only when non-empty; updates both `#log-content` pre and calls `renderLogLines()`. Error path renders "Failed to load logs. Retrying..." in `#log-buffer`.

Follow logic: `logFollowEnabled = true` module-scoped; scroll listener detects `scrollHeight - scrollTop <= clientHeight + 8` and pauses follow; click listener on `#btn-log-follow` toggles state, toggles `.btn-accent`, sets `aria-pressed`; `maybeScrollToBottom()` auto-scrolls only when enabled. Filter controls wired: level `change` calls `pollLogs()` immediately; search `input` debounced 300ms; refresh `click` calls `pollLogs()` immediately. No new `setInterval` added.

## Verification

Full suite: `793 passed, 2 skipped` GREEN.

Specific guards:
- `test_no_innerHTML_with_api_data`: PASSED (all API data via textContent)
- `test_uplot_script_and_css_present`: PASSED
- `test_dashboard_renders_buys_section`: PASSED
- `test_dashboard_renders_log_viewer_section`: PASSED
- `test_log_dom_cap_constant`: PASSED (literal `MAX_LOG_LINES = 500` present)

## Deviations from Plan

None. Plan executed exactly as written.

## Known Stubs

None. All three surfaces fetch real data from implemented API endpoints.

## Threat Flags

None. All API-sourced data flows through textContent (T-28-07, T-28-08, T-28-09 mitigated). No new network endpoints introduced.

## Manual UAT (Deferred)

- Open dashboard with an Amazon item: verify line chart renders with correct time x-axis
- Open dashboard with a non-Amazon item: verify "No price history available for this plugin." message, no JS error
- Confirmed-buys table: verify populates with real orders or shows empty row
- Log viewer: generate logs; confirm per-level colors, level filter narrows, search debounces, Follow auto-scrolls then pauses on scroll-up, buffer stays <=500 lines

## Self-Check: PASSED

- `web/templates/dashboard.html` exists and contains all required functions
- Commit 137be25 exists (Task 1)
- Commit d701353 exists (Task 2)
- Full pytest suite GREEN: 793 passed
