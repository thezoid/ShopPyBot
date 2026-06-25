# Feature Research

**Domain:** Single-operator localhost ops dashboard — observability surfaces for ShopPyBot v4.1
**Researched:** 2026-06-25
**Confidence:** HIGH (existing data shapes confirmed from source; UX patterns from multiple sources)

---

## Scope Reminder

This is a **single-operator, localhost-bound, no-Node** tool. The operator is also the developer.
Every "anti-feature" below is real scope that gets proposed for tools like this and should be
actively rejected. The 4 surfaces in scope are:

1. Live per-plugin health cards
2. Run history + confirmed buys
3. Price-history charts
4. Better log viewer

Plus: SSE push (replaces 2s polling) and a vendored design-system redesign.

---

## Surface 1: Per-Plugin Health Cards

Existing data source: `BotService.get_status()` returns:
```json
{
  "running": true,
  "uptime_secs": 3742.1,
  "plugins": {
    "amazon": {
      "status": "checking",
      "last_heartbeat": 1234567.8,
      "consecutive_errors": 0,
      "items_checked": 47,
      "orders_confirmed": 1
    }
  }
}
```
`last_heartbeat` is a `time.monotonic()` float (seconds since process start, not wall-clock epoch).
Staleness must be computed as `now_monotonic - last_heartbeat`.

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| One card per plugin, named | Operator cannot tell plugins apart without it | LOW | Derived from `plugins` dict keys |
| Status badge (idle / checking / error / degraded) | Primary at-a-glance signal | LOW | Map `status` field to color token |
| Last-heartbeat staleness ("3s ago", "stale") | Time-since-check is the most actionable number | LOW | `now - last_heartbeat`; no wall-clock; show "stale" when > 60s |
| Consecutive-errors counter | Shows whether degraded is transient or sustained | LOW | `consecutive_errors` field direct |
| items_checked lifetime counter | Confirms the plugin is actually running | LOW | `items_checked` field direct |
| Degraded visual state | `health_degraded` alert fires when `consecutive_errors >= threshold`; card must look alarming | LOW | Use `status == "degraded"` or `consecutive_errors > 0` as secondary signal |
| Cards update via SSE (not polling) | Eliminates 2s latency on degraded detection | MEDIUM | Part of SSE stream; same event type as status update |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| orders_confirmed on card | Operator sees acquisition success at a glance without opening history | LOW | `orders_confirmed` field on each plugin record |
| Uptime display on global status bar | Reassurance for multi-hour unattended runs | LOW | `uptime_secs` from get_status(); format as H:MM:SS |
| Staleness color gradient (fresh / aging / stale) | Communicates "about to go stale" vs already stale without binary flip | MEDIUM | Three threshold bands: <30s green, 30-60s amber, >60s red |

### Anti-Features (do NOT build)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Alerting rules engine (configure thresholds in UI) | "What if I want 90s stale threshold?" | Single operator; thresholds are config.yml knobs; a UI rules engine is an admin product | Hard-code reasonable defaults (60s stale, 3 consecutive errors = degraded); let YAML drive them if needed |
| Plugin enable/disable toggle from UI | Convenient-seeming control | Plugin lifecycle is managed by the orchestrator + config; toggling mid-run is a footgun with no safe teardown path | Document that restarting the bot with modified config is the correct approach |
| Historical health trend chart (uptime %) | Looks professional | HealthRegistry is in-memory and resets on restart; there is no persistence for trend data; implementing it requires a new append table | Not in scope; the run history surface covers bot-level events |
| Per-plugin restart button | Recovery shortcut | The supervisor already handles restarts; a UI-triggered restart races with it and can leave a plugin in double-start state | Trust the supervisor; surface `consecutive_errors` so operator knows when to manually stop/start the whole bot |

---

## Surface 2: Run History + Confirmed Buys

Existing data source: `items` table columns per-row:
- `name`, `link`, `purchased` (bool), `order_id` (text, nullable), `confirmed_at` (text ISO-8601, nullable), `checkout_attempts` (int)

There is no separate orders table. Each item row is either purchased or not.
The history surface therefore reads all items with `purchased=1` and displays them as a list.

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Confirmed-buys table (name, order_id, confirmed_at) | Core output of the bot; operator needs proof of purchase at a glance | LOW | `SELECT name, link, order_id, confirmed_at FROM items WHERE purchased=1 ORDER BY confirmed_at DESC` |
| checkout_attempts displayed per item | Distinguishes "got it on first try" from "retried 5 times" | LOW | Direct column |
| Empty-state messaging | Operator who has never bought anything needs guidance that this is normal | LOW | "No confirmed orders yet" placeholder |
| Recent-activity timestamp formatting | Raw ISO-8601 is unfriendly; "2 hours ago" or locale date is the minimum | LOW | Format in JS; no library needed |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Link to retailer order page (if URL derivable) | Operator can jump to the real order in one click | MEDIUM | `order_id` format is retailer-specific; treat as MEDIUM confidence for correctness; link to the order list page as a safe fallback |
| All-items table showing purchased flag inline | Items section already exists; adding a purchased column shows full funnel | LOW | Already in `/api/items`; just add a column to existing table |
| Items sorted: unpurchased first, purchased last | Operator cares about what is still being monitored | LOW | Sort in existing items query |

### Anti-Features (do NOT build)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Separate Orders page / route | "Cleaner navigation" | For a single operator with <=20 items, a dedicated page adds a nav hop for no real gain; all confirmed buys fit in a small table on the main dashboard | Collapsible section or a tab within the existing single-page layout |
| Order filtering / search | "What if I have hundreds of orders?" | This bot auto-stops items on purchase (`purchased=1`); there will never be hundreds of rows; the maximum is bounded by the item list size | None needed; if list exceeds ~20 rows the operator should be cleaning up items |
| Outcome analytics (success rate, time-to-checkout) | Sounds useful | Requires a separate append-only events table; v4.0 explicitly deferred this to post-v4.1; `checkout_attempts` gives a proxy already | Flag as post-v4.1 future direction |
| Pagination | Standard table affordance | Data volume never warrants it; single-operator item lists are small | Simple full-list render |
| Export to CSV | "I want my records" | One operator; order_id is already visible; screenshot or browser copy works | Not worth the route |

---

## Surface 3: Price-History Charts

Existing data source: `price_history` table:
- `item_link` (FK to items.link), `price_cents` (int), `currency` (text), `scraped_at` (text ISO-8601)

Current data: Amazon plugin only (PRICE-02). Other plugins have no price scraping.
Data is sparse and irregular: one row per check cycle per item (cycle interval is configurable).
A typical item may have 5-50 data points in an active monitoring window, not thousands.

Chart library constraint: no CDN, no npm, vendored only. Must be a single droppable file.

**Recommendation: uPlot** (~50KB minified IIFE, zero dependencies, Canvas 2D, vendorable as `web/static/uplot.iife.min.js`). For the data volumes here (5-200 points), hand-rolled SVG polyline is also viable and adds zero weight. uPlot is preferred if interactive tooltips are wanted; hand-rolled SVG is preferred for zero-weight simplicity. Use uPlot unless the design system phase determines the SVG approach is cleaner to maintain.

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Line chart per item (price over time) | The price_history table exists specifically to be visualized | MEDIUM | `/api/price-history/<item_link_b64>` endpoint needed; chart rendered per item |
| Price in readable currency (dollars, not cents) | price_cents must be divided by 100 | LOW | Pure JS transform before render |
| Time axis in human-readable form | ISO-8601 scraped_at strings need parsing | LOW | `new Date(scraped_at)` in JS |
| Target price reference line | item.target_price column exists; drawing a horizontal rule at that value adds immediate context | LOW | Horizontal SVG line or uPlot annotation; target_price is nullable so conditional |
| "No data yet" placeholder for non-Amazon items | BestBuy, Walmart, etc. have zero rows; showing a blank chart is confusing | LOW | API returns empty array; render "Price history not available for this plugin" text |
| Chart only shown when data exists | Rendering 7 empty charts wastes space | LOW | Conditional render |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Most-recent price prominently labeled | Operator's first question is "what is it priced at now" not "draw me a chart" | LOW | Text above chart: "Current: $59.99 (Amazon, 5 min ago)" |
| Price delta since first observation | "Down $20 since I started watching" is motivating context | LOW | `last_price - first_price` from the history array |
| Chart collapsible per item (collapsed by default if no price drop) | Keeps the page scannable when monitoring many items | LOW | `<details>` element; no JS needed for basic collapse |

### Anti-Features (do NOT build)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Cross-item price comparison chart | "Interesting to compare" | Items are on different retailers with different base prices; a single Y-axis is meaningless; volume is too low to reveal patterns | Per-item charts only |
| Candlestick / OHLC chart | "More financial-looking" | Data is one-scrape-per-cycle, not tick-level OHLC; there is no open/high/low/close structure | Line chart is correct for this data shape |
| Chart zoom / pan | Standard chart interaction | With 5-50 sparse points the chart fits in a 300px card; zoom is unnecessary complexity | Static chart with tooltip on hover only |
| Persistent chart settings (zoom level, time range) | "Save my view" | Single operator; page load always starts fresh | No state persistence needed |
| Price alert configuration in the chart UI | "Click the chart to set my target" | Price targets live in config.yml / database; a click-to-set interaction requires a write path through the chart | Keep config.yml / existing items form as the price config path |
| Server-side chart rendering (Matplotlib, Plotly server) | Avoids JS | Adds a Python image dependency; PNG charts are not interactive; SSE updates can't refresh PNGs without full reload | Client-side chart with vendored lib |
| Real-time price chart updates via SSE | "Show price ticking live" | Price scrapes are slow (one per poll cycle, 30-120s); the chart is not a live ticker; polling on demand is sufficient | REST endpoint on page load / manual refresh |

---

## Surface 4: Log Viewer

Existing implementation: `/api/logs` returns last 50 lines of today's log file as plain strings.
The 2s polling loop dumps them into a `<pre>`. No structure, no filtering.

Log format (from `logger.py`): `writeLog(message, type)` with colorama colors to file.
The file format is plain text lines with timestamp + level + optional plugin prefix + message.

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Color-coded log levels in UI | Errors must visually jump out; INFO/DEBUG should recede | LOW | CSS class per level; parse level token from line string with a regex |
| Level filter (ALL / ERROR / WARN / INFO / DEBUG / TRACE) | Operator watching for errors does not want 500 DEBUG lines | LOW | Client-side filter on rendered lines; no server round-trip needed |
| Tail / follow mode (auto-scroll to bottom on new lines) | Standard expectation for any log viewer | LOW | `el.scrollTop = el.scrollHeight` on SSE message; pause when user scrolls up |
| Pause tail when user scrolls up, resume on scroll-to-bottom | Without pause, auto-scroll fights the user who is reading history | LOW | Track `isUserScrolledUp` boolean; resume on scroll-to-bottom |
| SSE push (replaces 2s poll) | New logs appear immediately, not after up to 2s lag | MEDIUM | FastAPI `StreamingResponse` with event-stream; backend reads log file tail and pushes new lines |
| Reasonable line cap in memory (last 500 lines) | Unbounded append causes memory growth in a long-running tab | LOW | Rotate DOM lines: keep a circular buffer of 500, drop oldest |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Plugin filter (dropdown: ALL / amazon / bestbuy / etc.) | Multi-plugin runs generate interleaved logs; isolating one plugin is the primary debugging workflow | MEDIUM | Parse plugin name from log prefix; populate dropdown from HealthRegistry plugin names or known list; client-side filter |
| Substring search / highlight | "Where did the error happen in the flow?" | MEDIUM | Client-side: filter lines containing query string OR highlight matching spans; not a server search |
| Log level count badges | "How many errors since last clear?" | LOW | Count by level as lines accumulate; reset on page load or manual clear |
| Clear log view button | Operator wants a fresh visual starting point without restarting anything | LOW | Clear the in-memory DOM buffer only; does not touch the log file |

### Anti-Features (do NOT build)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Log file management (rotate, delete, archive) | "Clean up old logs" | Log rotation is an OS/process concern; doing it from the UI introduces race conditions with the logger and is a destructive operation from a web endpoint | Document that logs are in `logs/YYYYMONTHDD.log` and the operator deletes them manually |
| Regex filter | "Power-user search" | Substring search covers 95% of single-operator use; regex in a real-time filter on a 500-line DOM buffer is overkill and requires error handling for invalid patterns | Substring search; operator can open the log file in a real editor for regex |
| Multi-day log browsing (date picker) | "See yesterday's run" | Past log files are static; the dashboard's purpose is live ops, not historical audit; the CLI `shoppybot status` and log files themselves serve the historical use case | Direct file access; no UI date picker |
| Log persistence to database | "Store structured logs in SQLite" | Requires a schema migration, an insert on every log line, and a retention policy; the file-based logger already provides persistence | File log is the persistence layer |
| Remote log shipping (Loki, Elasticsearch, Datadog) | "Ship to central log aggregator" | Single-operator personal tool; adding an external dependency violates the no-CDN/self-contained posture | Not in scope |
| Export logs as file from UI | "Download for sharing" | Single operator; the log file is at a known path on disk | Document path; open file explorer |
| Virtual scrolling | "Performance for huge logs" | The 500-line cap makes this unnecessary; DOM with 500 `<div>` elements is fast | Simple DOM append with cap |

---

## Feature Dependencies

```
SSE endpoint (FastAPI StreamingResponse)
    required by: Live health cards (SSE event: "status")
    required by: Log viewer SSE tail (SSE event: "log")
    NOT required by: Price charts (REST on demand is sufficient)

/api/price-history/<link_b64> endpoint (new REST)
    required by: Price-history chart render

Vendored design system (CSS tokens + components)
    required by: All 4 surfaces (cards, tables, charts, log panel)
    required by: Light/dark mode (CSS custom properties)

HealthRegistry.get_snapshot() [already exists in core/health.py]
    feeds: Health cards
    feeds: SSE status event payload

items table (order_id, confirmed_at, checkout_attempts columns -- all shipped in v4.0)
    feeds: Run history / confirmed buys table

price_history table [already exists]
    feeds: Price-history charts
```

### Dependency Notes

- SSE must come before live health cards and live log tail. Both surfaces degrade gracefully to polling if SSE is not yet wired (the 2s poll already exists).
- The design system redesign is a prerequisite for all surface work because it establishes the card/token/color system that health cards, charts, and the log panel all use.
- Price charts do NOT require SSE; a REST endpoint on demand is sufficient given sparse data.
- The confirmed-buys surface requires no new DB columns; all needed fields shipped in v4.0 (BUY-04).

---

## MVP Definition for v4.1

### Phase order implied by dependencies

Phase A (design system + SSE foundation) must precede Phase B (surfaces).

### Launch With (all 4 surfaces, minimum viable form)

- [ ] Vendored design system: CSS tokens, card component, light/dark -- required by everything else
- [ ] SSE endpoint streaming `status` + `log` event types -- required for live health cards + log tail
- [ ] Health cards: name, status badge, staleness, consecutive_errors, items_checked -- reads from SSE "status" event
- [ ] Confirmed-buys table: name, order_id, confirmed_at, checkout_attempts -- REST, reads items table
- [ ] Price-history chart: per-item line chart via uPlot or hand-rolled SVG -- REST `/api/price-history/<b64>`, empty-state for non-Amazon items
- [ ] Log viewer: level color-coding, level filter, tail/follow, pause-on-scroll, SSE push, 500-line cap

### Add After Core Works (within v4.1 if scope permits)

- [ ] Plugin filter on log viewer -- depends on log format consistency; add after verifying level parse works
- [ ] Log substring search/highlight -- polish, not blocking
- [ ] Uptime display in global status bar -- low effort; add if a spare slot exists in the design system phase
- [ ] Staleness color gradient (three bands) -- polish tier; binary stale/fresh is good enough for launch
- [ ] orders_confirmed counter on health card -- data is available; add if card layout has room

### Defer to Post-v4.1

- [ ] Outcome analytics (success rate, time-to-checkout) -- requires new append-only events table; explicitly deferred in PROJECT.md
- [ ] Amazon/BestBuy order deep-link -- order_id URL formats need validation against live retailer pages; medium confidence risk
- [ ] Log level count badges -- nice-to-have polish
- [ ] Multi-day log browsing -- out of scope for this milestone

---

## Feature Prioritization Matrix

| Feature | Operator Value | Implementation Cost | Priority |
|---------|----------------|---------------------|----------|
| Vendored design system (CSS tokens, card, dark mode) | HIGH | MEDIUM | P1 |
| SSE endpoint (status + log streams) | HIGH | MEDIUM | P1 |
| Health cards (status, staleness, errors) | HIGH | LOW | P1 |
| Log viewer: level filter + tail + SSE push | HIGH | MEDIUM | P1 |
| Confirmed-buys table | HIGH | LOW | P1 |
| Price-history chart (uPlot or SVG) + REST endpoint | HIGH | MEDIUM | P1 |
| Uptime display on status bar | MEDIUM | LOW | P2 |
| Plugin filter on log viewer | MEDIUM | MEDIUM | P2 |
| Log substring search | MEDIUM | MEDIUM | P2 |
| Staleness gradient (3 bands) | MEDIUM | LOW | P2 |
| orders_confirmed on health card | LOW | LOW | P2 |
| Log level count badges | LOW | LOW | P3 |
| Amazon/BestBuy order deep-link | LOW | MEDIUM | P3 |

**Priority key:**
- P1: Must have for v4.1 launch
- P2: Add within v4.1 phases if cost permits
- P3: Nice-to-have; defer

---

## Single-Operator Scope: Global Anti-Features

These cross-cutting concerns should be rejected at any point during v4.1 planning.

| Anti-Feature | Category | Why Rejected |
|--------------|----------|-------------|
| Multi-tenant / user roles | Auth | Single operator; localhost-bound; no multi-user need |
| Auth roles / permissions UI | Auth | Same reason; the localhost bind IS the auth boundary |
| Retention policy UI (auto-delete logs/history after N days) | Ops admin | One operator; manual file deletion is fine |
| Alerting rules engine in UI | Observability over-engineering | Thresholds are config.yml or code constants; a rules UI is a product in itself |
| Dashboard sharing / embeds | Multi-user | Not in scope; tool is personal-use |
| WebSocket (vs SSE) | Transport over-engineering | SSE is unidirectional server-push; that is all we need; WebSocket adds handshake complexity for zero benefit |
| i18n / localization | Enterprise feature | Single operator; English only |
| Node.js build pipeline / bundler | Constraint violation | Explicit project constraint: zero Node; vendored CSS + JS only |
| External fonts (Google Fonts, etc.) | Constraint violation | Explicit project constraint: no CDN; system font stack only |

---

## Sources

- HealthRegistry and get_status() payload: `core/health.py`, `core/service.py` (direct read, HIGH confidence)
- price_history and items table schema: `models.py` (direct read, HIGH confidence)
- uPlot library: https://github.com/leeoniya/uPlot -- ~50KB IIFE, zero dependencies, Canvas 2D (MEDIUM confidence on exact file size; HIGH confidence on dependency-free status)
- SSE UX patterns for log viewers: https://dev.to/polliog/building-a-real-time-log-viewer-with-server-sent-events-and-svelte-5-13dd
- Live log tail with SSE: https://logdy.dev/blog/post/live-log-tail-with-logdy-stream-logs-from-anywhere-to-web-browser
- Real-time dashboard UX (staleness patterns): https://smashingmagazine.com/2025/09/ux-strategies-real-time-dashboards/ (MEDIUM confidence; general design guidance)
- Admin dashboard operator UX task-oriented design: https://www.glitchlabs.app/insights/admin-dashboard-ux-patterns (MEDIUM confidence)
- Carbon Design System status indicator pattern: https://carbondesignsystem.com/patterns/status-indicator-pattern/ (MEDIUM confidence)
- FastAPI SSE official docs: https://fastapi.tiangolo.com/tutorial/server-sent-events/ (HIGH confidence)

---

*Feature research for: ShopPyBot v4.1 Dashboard & Observability*
*Researched: 2026-06-25*
