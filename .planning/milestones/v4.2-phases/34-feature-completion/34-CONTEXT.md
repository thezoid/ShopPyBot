# Phase 34: Feature Completion - Context

**Gathered:** 2026-07-02
**Status:** Ready for planning
**Mode:** Smart discuss (autonomous). User-facing feature phase; grey areas resolved with best-practice defaults grounded in the existing v4.1 dashboard design system. One load-bearing research question (the v4.1-deferred [plugin]-tag consistency check) is flagged for research to verify against the real code.

<domain>
## Phase Boundary

An operator can filter dashboard/API logs by plugin (FC-01, completes the v4.1-deferred OBS-08) and see success-rate + time-to-checkout analytics computed from existing confirmed-order (BUY-04) records (FC-02).

**In scope:** guarantee every log line carries a `[plugin]` tag; a `plugin` filter parameter on `/api/logs`; a log-filter UI control; an analytics endpoint + operator-facing view computing success-rate and time-to-checkout from existing verified-order records; tests for both (analytics verified against a fixture order set).

**Out of scope:** new order-capture logic (analytics reads EXISTING records only), new charting library (reuse the vendored uPlot if a chart is warranted; otherwise stat cards/table), retroactively tagging historical log FILES (the guarantee applies to newly-written lines).
</domain>

<decisions>
## Implementation Decisions

### FC-01 [plugin] log tag + /api/logs filter
- **RESEARCH QUESTION (load-bearing, v4.1-deferred OBS-08 flag):** verify how log lines are CURRENTLY tagged with plugin identity. `logger.py:writeLog` does NOT appear to auto-inject a plugin tag (tags, if any, come from callers) — confirm the real state and consistency. If tagging is inconsistent, the plugin filter is unreliable. **Decision leaning:** guarantee consistency by having the logging path inject a `[plugin]` tag from the currently-active plugin context (e.g. a `contextvars.ContextVar` set by the orchestrator per plugin iteration, or the plugin passing its `platform_key` into writeLog) rather than auditing every call site. Research picks the cleanest mechanism that guarantees "every log line carries a `[plugin]` tag" without a massive call-site sweep. Lines with no active plugin (startup/global) get a sentinel tag (e.g. `[core]` / `[system]`).
- **Tag format:** `[plugin]` where plugin = the plugin's `platform_key` (amazon, bestbuy, walmart, ... squareenix no-underscore, matching the config key convention). Must be machine-parseable so the filter can match exactly.
- **/api/logs filter:** add an optional `plugin` query parameter to the existing `/api/logs` endpoint (which already supports level + search from v4.1 OBS-08). Reuse the existing `read_logs_filtered()` path; add plugin matching. Empty/absent param = all plugins (no behavior change for existing callers).
- **Log-filter UI:** a plugin dropdown in the existing dashboard log panel, populated from the known plugin list, wired to the `plugin` query param. Reuse the EXISTING log-level/search control styling (components.css) — no new design language.

### FC-02 outcome analytics
- **Metrics:** (1) success-rate and (2) time-to-checkout, computed from existing confirmed-order (BUY-04) records. Provide BOTH overall and per-plugin breakdowns.
  - **RESEARCH QUESTION:** confirm the exact order-record schema (which table/columns hold confirmed orders, timestamps, plugin identity). Define success-rate from the available fields (e.g. confirmed / attempted, using the place_order_attempted_at marker from Phase 30 + confirmed timestamp/order_id), and time-to-checkout as a duration between two existing timestamps (e.g. attempt/detection → confirmation). Do NOT invent new columns — if a needed timestamp is missing, scope the metric to what the data supports and document the limitation.
- **Endpoint:** a read-only analytics endpoint (e.g. `GET /api/analytics`) returning the computed metrics as JSON. Follow the existing read-only API pattern (v4.1 phase 26) — no new writes, no credential exposure (scrub per the established get_status boundary conventions).
- **View:** an operator-facing analytics surface on the existing dashboard. **Presentation decision:** stat cards for the headline numbers (overall success-rate %, avg time-to-checkout) + a compact per-plugin table (plugin, orders, success-rate, avg time-to-checkout). Only add a uPlot chart if the data is genuinely time-series and the chart adds value; default to cards+table (simpler, matches the existing dashboard density). Reuse existing card/table components + tokens.css — extend the design system, do NOT invent new visual patterns.
- **Fixture verification:** FC-02 success criterion requires correct output against a FIXTURE set of orders — build a deterministic fixture (known orders with known timestamps) and assert the computed success-rate + time-to-checkout exactly.

### Design-system reuse (hard)
All new UI reuses the existing v4.1 design system verbatim: `web/static/tokens.css` (design tokens), `components.css` (component rules via var(--xxx)), `dashboard.css` (layout). Zero-Node constraint holds — no package.json, no CDN, all assets vendored. FOUC-prevention + theme conventions from v4.1 are preserved. No new external fonts/URLs.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `logger.py:writeLog(message, type)` — the single logging entry point (FC-01 hooks here for the tag guarantee).
- The existing `/api/logs` endpoint + `read_logs_filtered()` (v4.1 OBS-08: level + search; plugin filter was deferred to here).
- The v4.1 web dashboard: `web/` package (FastAPI create_app factory, read-only API endpoints from phase 26, SSE from phase 27, observability surfaces from phase 28-29), `web/static/` design system (tokens/components/dashboard css, vendored uPlot).
- Confirmed-order records in the SQLite DB (`data/shop_py_bot.db`) — BUY-04 confirmation detection + Phase 30's place_order_attempted_at marker + confirmed order_id/timestamp.
- The plugin registry / `platform_key` list (for populating the filter dropdown + per-plugin analytics).

### Established Patterns
- Read-only API: raw StreamingResponse / JSONResponse, no new deps; credential-scrub at the response boundary (last_error → exc.__class__.__name__).
- CSS 3-file split, var(--xxx) only in components, each file <200 lines; inline synchronous theme script for FOUC prevention.
- Plugin platform_key convention (squareenix no underscore).

### Integration Points
- `logger.py` (tag injection), the `/api/logs` route + read_logs_filtered (plugin param), a new analytics route + service function, `web/static/` (dashboard log-filter control + analytics view), templates, tests.
</code_context>

<specifics>
## Specific Ideas

- FC-01 must GUARANTEE every newly-written log line is tagged — verify the mechanism handles lines emitted when no plugin is active (sentinel tag).
- FC-02 must be proven against a deterministic fixture order set (exact success-rate + time-to-checkout assertions).
- Reuse the existing design system verbatim; no new visual language, no Node, no CDN.
</specifics>

<deferred>
## Deferred Ideas

- Retroactive tagging of historical log files (only newly-written lines are guaranteed).
- Advanced analytics (trends over time, funnels) beyond success-rate + time-to-checkout.
- New charting beyond the vendored uPlot.
</deferred>
