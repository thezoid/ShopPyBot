---
phase: 28-frontend-observability-surfaces
verified: 2026-06-27T00:00:00Z
status: human_needed
score: 9/9 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Open dashboard with one active plugin running. Observe #health-grid."
    expected: "A health card appears with status badge, colored heartbeat staleness (green <30s / amber 30-60s / red >=60s), error count, items-checked count, and orders-confirmed count."
    why_human: "renderHealthCards() builds DOM via createElement at runtime. Static test confirms scaffold and JS code presence but cannot exercise live API data flow in a headless run."
  - test: "Wait 60+ seconds without restarting the bot; observe the heartbeat age band on a plugin card."
    expected: "Color transitions from green to amber (30-60s) then red (>=60s or when null). Header shows 'Up Nh Mm' or 'Up Mm' while running and blank when stopped."
    why_human: "Temporal color-band cycling and uptime humanization require a live running process with real monotonic time advancing."
  - test: "Trigger a confirmed buy in test_mode. Open the Confirmed Orders section."
    expected: "A data row appears with item name, order ID, confirmed_at ISO string, and checkout attempt count. If no orders exist, 'No confirmed orders yet.' row appears."
    why_human: "loadConfirmedBuys() fetches /api/history at runtime. Cannot populate a real purchase record headlessly."
  - test: "Add an Amazon item. Observe the price chart area below the items table."
    expected: "A uPlot line chart renders with a time-based x-axis and the --color-accent stroke color. For a non-Amazon item, 'No price history available for this plugin.' message appears instead."
    why_human: "loadPriceChart() creates a uPlot canvas at runtime. ISO->Unix conversion and chart rendering are visual and require a browser with a real DOM and item price data in the DB."
  - test: "Open the Log Viewer section. Let logs accumulate past 500 lines."
    expected: "Lines are color-coded by level (red ERROR, amber WARNING, default INFO, muted DEBUG/TRACE). Level filter and search narrow the visible lines. Follow button auto-scrolls; scrolling up pauses follow. Buffer never exceeds 500 DOM children."
    why_human: "Log streaming, filter interaction, scroll-follow behavior, and DOM cap enforcement all require live browser interaction and real log events."
---

# Phase 28: Frontend Observability Surfaces Verification Report

**Phase Goal:** Operators see all four observability surfaces rendered correctly in the dashboard: per-plugin health cards, confirmed-buys table, price-history charts, and a filtered log viewer with tail controls, all driven by one-shot fetch against Phase 26 endpoints.
**Verified:** 2026-06-27
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `get_snapshot()` returns `heartbeat_age_secs` (None when never heartbeated, float otherwise) | VERIFIED | `core/health.py` lines 88-97: `now = time.monotonic()` computed once; `None if lhb == 0.0 else round(now - lhb, 1)`. `test_heartbeat_age_secs_fresh` and `test_heartbeat_age_secs_never` both PASS. |
| 2 | `test_snapshot_public_keys_exact` includes `heartbeat_age_secs` in expected key set | VERIFIED | `tests/test_health.py` line 108: `"heartbeat_age_secs"` in `expected_keys`. Test PASSES. |
| 3 | `#section-health` / `#health-grid` scaffold exists in rendered HTML | VERIFIED | `dashboard.html` lines 59-63: `<section class="card" id="section-health">` with `<div class="health-grid" id="health-grid">`. `test_dashboard_renders_health_section` PASSES. |
| 4 | `#section-buys` / `#buys-tbody` with four required headers in rendered HTML | VERIFIED | `dashboard.html` lines 127-142: section with "Confirmed Orders" heading, thead with Item / Order ID / Confirmed At / Checkout Attempts, `<tbody id="buys-tbody">`. `test_dashboard_renders_buys_section` PASSES. |
| 5 | `#section-log-viewer` with `#log-buffer`, `#log-level-filter`, `#log-search` controls | VERIFIED | `dashboard.html` lines 161-183: complete log viewer scaffold with all required element IDs and ARIA attributes. `test_dashboard_renders_log_viewer_section` PASSES. |
| 6 | `MAX_LOG_LINES = 500` literal present in template | VERIFIED | `dashboard.html` line 319: `const MAX_LOG_LINES = 500;`. `test_log_dom_cap_constant` PASSES. |
| 7 | uPlot script and CSS assets linked | VERIFIED | `dashboard.html` lines 20, 459+: `uplot.min.css` in head; `uplot.iife.min.js` script tag present. `test_uplot_script_and_css_present` PASSES. |
| 8 | All API-sourced values use `textContent` / `createElement`; no interpolated `innerHTML` | VERIFIED | `renderHealthCards`, `loadConfirmedBuys`, `appendLogLine` all use `textContent`. Clear-only `innerHTML = ''` resets are allowlisted. `test_no_innerHTML_with_api_data` PASSES. |
| 9 | All Phase 28 CSS component classes present and token-only (no hardcoded hex) | VERIFIED | `components.css` lines 183-325: `.health-grid`, `.health-card`, `.badge-ok/neutral/err`, `.heartbeat-ok/warn/err`, `.chart-container`, `.chart-empty`, `.log-buffer`, `.log-level-*` all present using `var(--xxx)` exclusively. `test_no_hardcoded_hex_in_components` PASSES (793 passed total). |

**Score:** 9/9 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `core/health.py` | `heartbeat_age_secs` in `get_snapshot()` | VERIFIED | Lines 88-97; monotonic delta; None sentinel for last_heartbeat==0.0 |
| `tests/test_health.py` | Three new heartbeat_age_secs tests | VERIFIED | Lines 101-127; all three PASS |
| `tests/test_observability_ui.py` | Six scaffold assertion tests | VERIFIED | All 6 tests PASS including the nodriver issue from 28-03 resolved in full suite |
| `web/templates/dashboard.html` | Four render functions + three section scaffolds | VERIFIED | `renderHealthCards`, `renderUptime`, `loadConfirmedBuys`, `loadPriceChart`, `renderLogLines`, `appendLogLine`, `pollLogs` (extended) all present and substantive |
| `web/static/components.css` | Phase 28 observability component classes | VERIFIED | 147 lines appended, all token-only |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `pollStatus()` | `renderHealthCards(data)` + `renderUptime(data.uptime_secs)` | Called inside try-block after button updates | VERIFIED | `dashboard.html` lines 340-341 |
| `renderHealthCards` | `data.plugins` from `/api/status` | `Object.entries(plugins).forEach` + `createElement/textContent` | VERIFIED | Lines 246-302 |
| `heartbeatClass(ageSecs)` | OBS-02 three bands | null/undefined or >=60 -> err; <30 -> ok; else warn | VERIFIED | Lines 210-215 |
| `loadPriceChart(itemLink)` | `GET /api/price-history/{link_b64}` | `btoa(unescape(encodeURIComponent(link))).replace(/\+/g,'-').replace(/\//g,'_')` with `=` padding | VERIFIED | Lines 396-399, 417 |
| `loadPriceChart` ISO -> Unix | `Date.parse(p.t) / 1000` before `new uPlot` | `series.map(function(p) { return Date.parse(p.t) / 1000; })` | VERIFIED | Line 438 |
| `pollLogs()` | `GET /api/logs?level=&search=&n=500` | `URLSearchParams({n: 500})` reading DOM filter values each call | VERIFIED | Lines 537-543 |
| `loadConfirmedBuys()` | `GET /api/history` | `makeCell` textContent rows into `#buys-tbody` | VERIFIED | Lines 358-393 |
| `loadConfirmedBuys()` | page-load block | Called alongside `loadItems()` | VERIFIED | `setInterval(pollStatus, POLL_MS)` + explicit `pollLogs()` / `pollStatus()` calls; `loadConfirmedBuys` called in page-load IIFE scope — confirmed by grep on lines 571-574 |
| uPlot instance destroy on re-render | `_chartInstances[id].destroy()` | Registry + destroy before re-init | VERIFIED | Lines 404, 411-412 |
| DOM cap trim loop | `while (bufferEl.children.length > MAX_LOG_LINES) bufferEl.removeChild(bufferEl.firstChild)` | Inside `appendLogLine` after append | VERIFIED | Lines 485-487 |
| Follow pause on scroll-up | scroll listener removes `.btn-accent`, sets `aria-pressed=false` | atBottom check with +8px tolerance | VERIFIED | Lines 517-524 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `renderHealthCards` | `statusPayload.plugins` | `GET /api/status` via `pollStatus()` | Yes — `BotService.get_status()` -> `HealthRegistry.get_snapshot()` (Phase 26) | FLOWING |
| `loadConfirmedBuys` | `data.confirmed_orders` | `GET /api/history` (Phase 26 endpoint) | Yes — queries purchased items from SQLite | FLOWING |
| `loadPriceChart` | `data.series` | `GET /api/price-history/{b64}` (Phase 26 endpoint) | Yes — queries price_history table; returns empty array for non-Amazon | FLOWING |
| `renderLogLines` | `data.logs` | `GET /api/logs?n=500` via `pollLogs()` | Yes — reads log file server-side (Phase 26 endpoint) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full pytest suite | `python -m pytest -q` | 793 passed, 2 skipped | PASS |
| Health + observability UI tests | `python -m pytest tests/test_observability_ui.py tests/test_health.py tests/test_web_dashboard.py -v` | 34 passed, 0 failed | PASS |
| XSS guard | `test_no_innerHTML_with_api_data` | PASSED | PASS |
| MC-4 banner guard | `test_banner_renders_when_non_local` + `test_banner_absent_when_local` | PASSED | PASS |
| Design system hex guard | `test_no_hardcoded_hex_in_components` | PASSED (included in 793) | PASS |

### Probe Execution

No probe scripts declared for this phase. Step 7c: SKIPPED (no probe-*.sh files exist for Phase 28).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| OBS-01 | 28-01, 28-02, 28-03 | Per-plugin health card: status badge, heartbeat staleness, consecutive-error count, items-checked | SATISFIED | `renderHealthCards` builds all four fields via createElement/textContent; CSS classes present |
| OBS-02 | 28-02, 28-03 | Heartbeat staleness color-coded in three bands (<30s green / 30-60s amber / >60s red) | SATISFIED | `heartbeatClass()` implements exact bands; `.heartbeat-ok/warn/err` CSS classes via `var(--color-status-*)` |
| OBS-03 | 28-01, 28-03 | Per-plugin confirmed-orders counter on health card | SATISFIED | `ordStat.textContent = 'Orders confirmed: ' + (rec.orders_confirmed \|\| 0)` in `renderHealthCards` |
| OBS-04 | 28-04 | Confirmed-buys table (name, order_id, confirmed_at, checkout_attempts) | SATISFIED | `loadConfirmedBuys()` fetches `/api/history`, renders four `makeCell` columns; empty-state row present |
| OBS-05 | 28-04 | Per-item price-history chart (uPlot) with explicit empty state | SATISFIED | `loadPriceChart()` with ISO->Unix conversion, correct b64 encoding, empty message for zero-series |
| OBS-06 | 28-02, 28-04 | Log viewer with per-level color-coding and level filter | SATISFIED | `logLevelClass()` + `.log-level-*` CSS + `pollLogs()` reads `#log-level-filter.value` |
| OBS-07 | 28-03, 28-04 | Tail/follow with pause-on-scroll and 500-line DOM cap | SATISFIED | Follow IIFE with scroll listener + click toggle; `MAX_LOG_LINES = 500` trim loop in `appendLogLine` |
| OBS-08 | REQUIREMENTS.md maps to Phase 26 | Log text search / filter | SATISFIED (Phase 26) | `pollLogs()` forwards `search` param from `#log-search` to `/api/logs?search=`; REQUIREMENTS.md traceability table confirms OBS-08 belongs to Phase 26, not Phase 28. Plans 28-01/02/03/04 carry OBS-08 as UI wiring only. |
| OBS-09 | 28-03 | Bot uptime in global status bar | SATISFIED | `renderUptime(data.uptime_secs)` writes `humanizeUptime()` result to `#header-uptime` via textContent; called from `pollStatus()` |

**Note on OBS-08:** REQUIREMENTS.md traceability maps OBS-08 to Phase 26 (Complete). Phase 28 plans list OBS-08 only in plan 28-01's `requirements` array, which includes the search input UI wiring. The search input `#log-search` is present in the rendered HTML and `pollLogs()` forwards the value to the server. The server-side filter was Phase 26's responsibility. Requirement is satisfied end-to-end across the two phases.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `dashboard.html` | 665 | `tbody.innerHTML = '...'` static string (no API data) in `loadItems()` empty-state path | INFO | Contains only hardcoded English text, no API-sourced values; not an XSS vector. `test_no_innerHTML_with_api_data` confirms the regex guard does not flag this (static literal, no `${}`). |
| `dashboard.html` | 413 | `containerEl.innerHTML = ''` clear-only in `loadPriceChart` | INFO | Clear-only reset, no interpolation. Explicitly allowlisted pattern. |

No `TBD`, `FIXME`, or `XXX` markers found in Phase 28 modified files. No `return null` / placeholder stubs. No hardcoded hex in CSS.

### Human Verification Required

#### 1. Per-Plugin Health Cards (OBS-01, OBS-02, OBS-03)

**Test:** Open the dashboard with at least one active plugin running.
**Expected:** A health card appears per plugin showing: status badge with colored dot, heartbeat staleness text colored green (<30s) / amber (30-60s) / red (>=60s or never), consecutive error count, items-checked count, orders-confirmed count. When bot is stopped, cards show "Heartbeat: never" in red.
**Why human:** `renderHealthCards()` executes at runtime against live `/api/status` data. Static scaffold tests confirm the code is present and wired but cannot exercise DOM rendering.

#### 2. Bot Uptime in Header (OBS-09)

**Test:** Start the bot and observe the header area.
**Expected:** Text like "Up 0h 2m" appears in the header next to the title. When stopped, the slot is blank.
**Why human:** `renderUptime()` produces text from `data.uptime_secs` at runtime. Requires a live process.

#### 3. Confirmed Orders Table (OBS-04)

**Test:** Trigger a test-mode purchase. Open the Confirmed Orders section.
**Expected:** A table row appears with item name, order ID, ISO timestamp, and attempt count. If no orders, "No confirmed orders yet." appears in a single spanning cell.
**Why human:** `loadConfirmedBuys()` fetches `/api/history` which reads the SQLite `purchased` records. Requires a real record to validate data rows.

#### 4. Per-Item Price History Chart (OBS-05)

**Test:** Add an Amazon item with price history in the DB. Add a non-Amazon item. Observe below the items table.
**Expected:** Amazon item shows a uPlot line chart with a time-based x-axis (correct Unix-second conversion) and accent color stroke. Non-Amazon item shows "No price history available for this plugin." with no JS error.
**Why human:** uPlot canvas rendering and ISO->Unix conversion correctness require a live browser. The chart `id` strip of `=` padding (via `chartId()`) must resolve correctly to the DOM element.

#### 5. Log Viewer Behavior (OBS-06, OBS-07, OBS-08)

**Test:** Generate logs spanning multiple levels. Use the level dropdown and search field. Scroll up in the log buffer; then click Follow.
**Expected:** ERROR lines are red, WARNING amber, INFO default text, DEBUG/TRACE muted. Level filter narrows visible lines immediately. Search debounces ~300ms then narrows. Scrolling up pauses follow (Follow button loses accent style, aria-pressed=false). Clicking Follow resumes auto-scroll and button re-accents. Buffer stays at or below 500 DOM children when many lines accumulate.
**Why human:** All behaviors require live browser interaction, real log generation, and visual inspection of CSS class application and scroll behavior.

### Gaps Summary

No automated gaps. All nine must-have truths are VERIFIED by direct code inspection and passing tests. The five human verification items above are the only outstanding items — they are inherently un-automatable visual/interactive behaviors that require a live browser session.

The pre-existing nodriver/Python 3.14 `SyntaxError` that caused `test_dashboard_renders_health_section` to ERROR in the 28-03 SUMMARY is resolved in the full test suite (34/34 pass in targeted run, 793 pass in full run). That was an environment ordering artifact, not a code defect.

---

_Verified: 2026-06-27_
_Verifier: Claude (gsd-verifier)_
