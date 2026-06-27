# Phase 28: Frontend Observability Surfaces - Context

**Gathered:** 2026-06-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Render all four observability surfaces in the dashboard — per-plugin health cards,
confirmed-buys table, per-item price-history charts (uPlot), and a filtered log viewer
with tail controls — plus bot uptime in the header. All driven by one-shot fetch /
existing ~2s poll against Phase 26 REST endpoints and the Phase 25 design system.
SSE live-push is Phase 29. Covers OBS-01, OBS-02, OBS-03, OBS-04, OBS-05, OBS-06,
OBS-07, OBS-08 (UI rendering of the level/search filter), OBS-09.

</domain>

<decisions>
## Implementation Decisions

### Health Cards + Uptime (OBS-01/02/03/09)
- **Backend touch (approved):** add a server-computed `heartbeat_age_secs`
  (`time.monotonic() - last_heartbeat`) to the per-plugin status payload. The raw
  monotonic `last_heartbeat` is meaningless to the browser (different clock/process),
  so staleness MUST be computed server-side. Add it where the snapshot is produced
  (core/health.py get_snapshot or a transform at the get_status/route boundary) without
  breaking the existing `test_snapshot_public_keys_exact` (update that guard if the key
  set changes). A never-heartbeated plugin (last_heartbeat 0.0) should report a sentinel
  (e.g. null / very-large age) the client renders as "never".
- Client color-codes the age into three bands: <30s green, 30-60s amber, >60s red.
- Status badge from the snapshot `status` field (+ color); show the scrubbed `last_error`
  class name as a subtle sub-label when present.
- Layout: responsive grid, one card per plugin showing badge, colored heartbeat age,
  consecutive-error count, items-checked count, and orders_confirmed counter. New
  "Plugin Health" section.
- Uptime (OBS-09): humanized `uptime_secs` (e.g. "1h 23m") rendered into the sticky
  header `#header-uptime` slot built in Phase 25.

### Confirmed-Buys Table + Price Charts (OBS-04/05)
- Confirmed-buys: new section table (name, order_id, confirmed_at, checkout_attempts)
  from `GET /api/history`; render an explicit empty row ("No confirmed orders yet") when
  the list is empty — the table is present, not absent. Safe DOM (textContent).
- Price charts: one uPlot line chart per item, lazy-fetched from
  `GET /api/price-history/{link_b64}` on render, placed in the Items section.
- Empty/sparse: items with no price data (non-Amazon plugins) show
  "No price history available for this plugin" text (never a blank chart or render error);
  fewer than 2 points → render point markers.
- `link_b64` = `base64.urlsafe` of the item link, keeping `=` padding (matches the
  Phase 26 endpoint's `urlsafe_b64decode`, which requires padding).

### Log Viewer (OBS-06/07, OBS-08 UI)
- Dedicated log panel; per-level color coding via a CSS class derived from the `[LEVEL]`
  prefix; monospace.
- Filters: level dropdown (ALL/ERROR/WARNING/INFO/…) + search box → `GET /api/logs?level=&search=&n=500`.
  Plugin filter omitted (OBS-08 plugin filter deferred — no `[PLUGIN_NAME]` tag in logs).
- Tail/follow: a "Follow" toggle auto-scrolls to the newest line; pauses when the user
  scrolls up; resumes when scrolled back to the bottom or re-toggled.
- DOM buffer capped at 500 lines (trim oldest nodes); fetch `n=500` (OBS-07).

### Refresh Model & Safety (Phase 28 = one-shot fetch / existing poll; SSE is Phase 29)
- Keep the existing ~2s poll for status + logs (extend the current `pollStatus`/`pollLogs`);
  charts + confirmed-buys fetched one-shot on load. Phase 29 replaces polling with SSE.
- Server-computed `heartbeat_age_secs` refreshes via each status poll (no client-side ticking).
- All surfaces build via `createElement`/`textContent` (UI-03 safe-DOM pattern); charts use
  the uPlot data API (arrays), never innerHTML.
- Each surface degrades gracefully: fetch error → "Failed to load X"; empty → explicit
  empty message; never a blank/absent section.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `web/templates/dashboard.html` — sticky header with `#header-uptime` slot; Items
  section/table; existing `pollStatus`/`pollLogs` (~2s) and the safe-DOM `makeCell`/
  `escHtml` helpers + createElement patterns from Phase 25.
- Design system: `web/static/tokens.css` (status colors `--color-status-ok/warn/err`,
  spacing/type tokens), `web/static/components.css` (`.card`, `.status-dot`, `.btn`, etc.).
- uPlot vendored at `web/static/vendor/uplot.iife.min.js` + `uplot.min.css`, already
  linked in `dashboard.html` (Phase 25).
- Phase 26 endpoints: `GET /api/status` (running, uptime_secs, plugins snapshot),
  `GET /api/history`, `GET /api/price-history/{link_b64}`, `GET /api/logs?level=&search=&n=`.
- `core/health.py` `HealthRegistry.get_snapshot()` — per-plugin: status, last_heartbeat,
  consecutive_errors, items_checked, orders_confirmed, last_error. Add `heartbeat_age_secs` here.
- `core/service.py` `get_status()` returns running, uptime_secs, plugins.

### Established Patterns
- Client hydrates via `fetch('/api/*')`; safe DOM construction (UI-03); no innerHTML on API data.
- CSS tokens/components for all styling (no hardcoded hex — Phase 25 guard).

### Integration Points
- `web/templates/dashboard.html` — four new sections + header uptime + JS render/fetch.
- `web/static/components.css` — health-card / log-line / chart-empty styles (token-driven).
- `core/health.py` (or get_status boundary) — `heartbeat_age_secs` computation.

### Guards To Respect
- Phase 25 CSS tests: no hardcoded hex in components.css; token coverage.
- Phase 25 XSS guard: no `innerHTML` on API data (test_no_innerHTML_with_api_data).
- `test_snapshot_public_keys_exact` — update if the snapshot key set changes (heartbeat_age_secs).
- MC-4 non-local banner preserved.

</code_context>

<specifics>
## Specific Ideas

- Research SUMMARY (.planning/research/SUMMARY.md) Phase D is authoritative: empty-state
  for sparse/Amazon-only price data; point markers when <2 points; verify `writeLog` log
  tagging (plugin filter deferred — confirmed no `[PLUGIN_NAME]`).
- Build the surfaces so Phase 29 only swaps the data source (poll → SSE) without
  re-rendering logic: keep render functions (renderHealthCards(status), appendLogLine(line))
  separate from the fetch/poll trigger.

</specifics>

<deferred>
## Deferred Ideas

- SSE live push / EventSource wiring, "Live/Reconnecting" indicator — Phase 29.
- Log plugin filter — needs `[PLUGIN_NAME]` tagging (OBS-08 contingency).
- Order deep-links, multi-day log browsing, log-level count badges — future (OBSX).
- Price capture for non-Amazon plugins (PRC-01) — future milestone.

</deferred>
