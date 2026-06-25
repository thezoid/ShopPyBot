# Project Research Summary

**Project:** ShopPyBot v4.1 Dashboard & Observability
**Domain:** FastAPI dashboard redesign — vendored design system, SSE live-push, observability surfaces
**Researched:** 2026-06-25
**Confidence:** HIGH

## Executive Summary

v4.1 is a pure front-end and web-layer milestone: redesign the existing single-page FastAPI dashboard with a structured CSS design system, replace its 2s polling loop with SSE push, and surface four new observability areas: per-plugin health cards, run/buy history, price-history charts, and a filtered log viewer. All required data already exists. `get_status()` exposes plugin health and heartbeats; the `items` table carries `order_id`, `confirmed_at`, and `checkout_attempts` from v4.0 BUY-04; `price_history` is populated by the Amazon plugin. No DB schema changes are needed. No new Python packages are needed. The entire milestone is solvable on the existing `fastapi==0.115.8` + `uvicorn[standard]==0.30.6` + `jinja2==3.1.4` stack with two small vendored static files added for the chart library.

The single highest-risk component is the SSE cross-thread bridge. BotService runs on its own daemon-owned asyncio event loop; uvicorn runs a completely separate asyncio event loop on the main thread. The correct bridge: uvicorn's own `_poll_loop` background task calls `asyncio.to_thread(svc.get_status)` on a ~1s cadence and fans results out to per-client `asyncio.Queue` objects — all owned by uvicorn's loop. The BotService daemon thread must never touch these queues directly (`asyncio.Queue` is not thread-safe per Python stdlib docs). This pattern has been fully designed and verified against actual source files. It must be built and validated in isolation (Phase C) before any browser-side SSE wiring is attempted. A spike at the start of Phase C is recommended.

Security is first-class in this milestone. Two specific obligations carry forward: fix the existing XSS at `dashboard.html` line ~241 (`tr.innerHTML` with `item.name`/`item.link`) in the design system phase; and scrub `get_status()` `last_error` fields to return only `exc.__class__.__name__` rather than `str(exc)`, preventing proxy credentials from reaching the browser via the SSE health surface or log stream. All new DOM construction must use `textContent`/`createElement` — never `innerHTML` with API-sourced values.

## Key Findings: Stack

No Python dependency changes are required. Raw `StreamingResponse(media_type="text/event-stream")` from starlette (already a transitive dep) handles SSE with zero new imports. Do not add `sse-starlette` (adds `anyio` transitive dep for no functional gain on three simple endpoints). Do not upgrade FastAPI to 0.135+ in this milestone — native `fastapi.sse.EventSourceResponse` requires crossing the 0.128 Pydantic v1-shim-removal boundary; defer to a dedicated dep-refresh task and note it as a future item.

Two vendored static files are added for charts (see Charting Library decision). No `package.json`. No CDN. No external fonts.

**Core technologies:**
- `fastapi==0.115.8`: ASGI framework — raw `StreamingResponse` covers all SSE needs; no upgrade required
- `uvicorn[standard]==0.30.6`: ASGI server — single asyncio event loop; SSE async generators run natively
- `jinja2==3.1.4`: HTML template rendering — one template modified, already installed
- CSS custom properties in existing `dashboard.css`: design token system — no Node, no CDN
- Vendored chart library (one JS file): price-history visualization — planning-phase pick required

**Charting Library Decision (flag for planning-phase):**

STACK + FEATURES research recommend uPlot 1.6.32 (MIT, ~52 KB IIFE + ~1 KB companion CSS, interactive tooltips, Canvas 2D, purpose-built for time series, actively maintained). ARCHITECTURE research recommends fnando/sparkline (MIT, ~1 KB, SVG output, no tooltips, single-value `sparkline(svgEl, values)` API).

Both are fully viable and vendorable with zero Node. The tradeoff is tooltip interactivity vs minimal weight. Given data is sparse (5-50 points, Amazon-only today), tooltips add real operator value. Default recommendation: **uPlot** for tooltips; **fnando/sparkline** if 1 KB minimalism is preferred and tooltips are skippable. Hand-rolled SVG polyline remains a zero-download fallback. Roadmapper must pick one and document it in the Phase A plan.

## Key Findings: Features

**Must have (P1 — v4.1 launch):**
- Vendored design system (CSS tokens, components, light/dark) — prerequisite for all four surfaces
- SSE endpoint (`/api/events`) streaming `status` and `log` event types — prerequisite for live health cards and log tail
- Health cards: one per plugin, status badge, heartbeat staleness (monotonic delta), consecutive-errors counter, items-checked counter
- Confirmed-buys table: name, order_id, confirmed_at, checkout_attempts (reads `items WHERE purchased=1`)
- Price-history chart: per-item line chart, empty-state for non-Amazon plugins (explicit message, not blank area)
- Log viewer: level color-coding, level filter, tail/follow with pause-on-scroll, SSE push, 500-line DOM cap

**Should have (P2 — within v4.1 if scope permits):**
- Plugin filter on log viewer (verify log lines consistently tag `[PLUGIN_NAME]` before building — see Gaps)
- Uptime display in global status bar (low effort; `uptime_secs` from `get_status()`)
- Staleness gradient (three bands: <30s green, 30-60s amber, >60s red)
- `orders_confirmed` counter on health card
- Log substring search/highlight (client-side)

**Defer to post-v4.1:**
- Outcome analytics (requires new append-only events table; explicitly deferred in PROJECT.md)
- Amazon/BestBuy order deep-link (order_id URL formats unverified against live retailer pages)
- Log level count badges, multi-day log browsing

**Global anti-features to reject during planning:**
- Alerting rules engine in UI, plugin enable/disable toggle, separate Orders page, chart zoom/pan, real-time price SSE updates, pagination, CSV export, multi-tenant, Node/CDN anything

## Key Findings: Architecture

Five-phase dependency-ordered build: Design System first, then Read-Only API endpoints, then SSE Infrastructure (highest risk, prove in isolation), then Frontend Observability Surfaces (one-shot fetch, no SSE yet), then SSE Client Wiring (replace 2s poll last). Each phase is independently testable and committable.

**Major components:**
1. `web/sse_hub.py` (NEW): `SseHub` holding per-client `asyncio.Queue` set; `broadcast()` distributes payloads; `_poll_loop` background task on uvicorn's loop calls `asyncio.to_thread()` for all sync reads
2. `web/routes/sse.py` (NEW): single `/api/events` `StreamingResponse`; per-client queue with `finally: hub.unsubscribe()`; `request.is_disconnected()` for cleanup; 15s `wait_for` timeout yields `: keep-alive`; `retry: 3000` on stream open
3. `web/static/tokens.css` + `components.css` (NEW): design token split — tokens owns `:root` blocks for light/dark; components owns component rules using only `var(--xxx)`; `dashboard.css` reduced to layout + `@import`
4. `web/routes/api.py` (MODIFIED): `GET /api/history` and `GET /api/price-history/{link_b64}`; both wrap sync DB calls in `asyncio.to_thread()`
5. `web/log_reader.py` (MODIFIED): `read_logs_filtered()` with AND-combined filters; `tail_log_lines(after_line)` cursor-based incremental read with midnight-rollover detection
6. `web/templates/dashboard.html` (MODIFIED): four new sections; `EventSource` replacing `setInterval`; inline theme-init `<script>` as FIRST child of `<head>` to prevent FOUC

**Key invariants:**
- Queues live exclusively in uvicorn's event loop — the BotService thread never touches them
- `heartbeat` staleness = `time.monotonic() - last_heartbeat` (both monotonic — never mix with wall-clock `time.time()`)
- `get_status()` `last_error` = `exc.__class__.__name__` only — never `str(exc)`
- All DOM construction for API-sourced data uses `textContent`/`createElement` — never `innerHTML`

## Key Findings: Critical Pitfalls

1. **SSE cross-thread bridge race condition** (HIGHEST RISK): `asyncio.Queue.put_nowait()` from the BotService daemon thread corrupts queue state. Fix: uvicorn's `_poll_loop` is the sole SSE producer via `asyncio.to_thread(svc.get_status)`. Bot thread is never aware of SSE infrastructure. Recommend a spike at Phase C start to validate before full implementation.
2. **XSS via innerHTML with API-sourced strings** (HIGHEST RISK): Existing `loadItems()` at `dashboard.html` line ~241 already has this bug. Fix in Phase A, simultaneously establishing the `textContent`/`createElement` pattern for all new surfaces. Add `escHtml()` helper for any SVG string interpolation. CI assertion: scan templates for `innerHTML` on API-derived data.
3. **Secret leak via `get_status()` and log stream**: `str(exc)` can include proxy credentials or CAPTCHA API keys from tracebacks. Fix: scrub at `get_status()` boundary — return `exc.__class__.__name__` only. Write a test asserting SSE data frames contain no credential-pattern strings (regex for `@`, `password`, `token`, `key=`, `cvv`).
4. **Blocking uvicorn's event loop**: Any sync call (`get_status`, `read_recent_logs`, SQLite) inside async context without `asyncio.to_thread()` stalls all concurrent HTTP. Fix: wrap every sync call. Latency test: assert `/api/status` responds under 200ms while SSE is open.
5. **SSE generator leak + missing keepalive**: Without `request.is_disconnected()`, generators accumulate after tab close. Without `: keep-alive\n\n` every ~15s, idle SSE connections timeout silently. Fix: both are 3-line additions; `retry: 3000\n\n` on stream open controls reconnect backoff.
6. **Cursor-less log tailing**: Reusing `read_recent_logs()` (full file read every SSE tick) sends duplicate lines and eventually reads megabytes repeatedly. Fix: `tail_log_lines(after_line)` cursor-based implementation with midnight-rollover detection (`after_line > total -> reset to 0`).

## Implications for Roadmap

**Suggested phase structure (5 phases, continuing from phase 24 → phases 25-29):**

**Phase A (25): Design System**
- Rationale: Zero backend dependency; establishes the CSS token/component layer consumed by all four surfaces; fixes known XSS simultaneously while establishing correct DOM construction patterns for all subsequent work.
- Delivers: `tokens.css`, `components.css`, refactored `dashboard.css` (layout only), FOUC-prevention inline script, vendored chart library file, XSS fix on existing `loadItems()`, non-local banner preserved and verified (run MC-4 test to close this phase).
- Avoids: Pitfalls 2 (XSS), 8 (FOUC), 9 (design system breaks banner/CSRF gate).
- Planning note: CSS 3-file split (tokens + components + layout) vs single file — planning-phase call. Split wins on maintainability at no real cost for localhost.

**Phase B (26): Read-Only API Endpoints**
- Rationale: Independently `curl`-testable; no event-loop interaction risk; establishes data contracts for the frontend surfaces.
- Delivers: `GET /api/history`, `GET /api/price-history/{link_b64}`, `read_logs_filtered()` + query params on existing `GET /api/logs`.
- Avoids: Pitfall 4 (all sync DB calls wrapped in `asyncio.to_thread`).
- Verification: `curl` both endpoints before proceeding.

**Phase C (27): SSE Infrastructure** (research spike recommended)
- Rationale: Highest-risk component. Validate cross-thread bridge in complete isolation before any browser involvement.
- Delivers: `web/sse_hub.py`, `web/routes/sse.py`, lifespan wiring in `web/__init__.py`, `tail_log_lines()` cursor implementation, `get_status()` last_error scrubbing, secret-leak CI assertion.
- Avoids: Pitfalls 1 (cross-loop race), 3 (generator leak), 4 (loop blocking), 5 (reconnect backoff), 6 (unbounded log read), 7 (secrets in SSE stream).
- Verification: `curl -N localhost:8000/api/events`; start/stop bot; log append test; disconnect/cleanup test; 200ms latency test on `/api/status` while SSE open.

**Phase D (28): Frontend Observability Surfaces**
- Rationale: Separate "do surfaces render correctly?" from "do they update live?" — two orthogonal concerns that should not be debugged simultaneously.
- Delivers: Health cards section (monotonic staleness, badge, errors, items-checked), confirmed-buys table, price-history charts (empty state for non-Amazon), log viewer filter controls wired to REST `GET /api/logs`.
- Uses: Phase A component classes; Phase B REST endpoints; vendored chart library.
- Avoids: sparse/Amazon-only price data — explicit "No price history (Amazon only)" message; point markers when fewer than 2 data points.
- Open question for planning: Does `writeLog` consistently tag lines with `[PLUGIN_NAME]`? If not, defer plugin filter to post-v4.1.

**Phase E (29): SSE Client Wiring**
- Rationale: Replaces existing working behavior last; if anything goes wrong, rollback is trivial (revert EventSource code, polling resumes).
- Delivers: Replace `setInterval` with single `EventSource('/api/events')`; dispatch on `msg.type`; polling fallback guard; health cards on `status` events; log panel append on `log` events; 500-line DOM cap; "Live / Reconnecting" indicator.
- Avoids: EventSource auto-reconnects — no manual reconnect loop needed; do not add one on top.
- Verification: DevTools Network shows one `text/event-stream` replacing two poll requests; status updates within 1-2s of bot start/stop; clean reconnect after tab close/reopen.

**Research flags:**
- Phase C (SSE): Spike recommended to validate lifespan + `asyncio.create_task` wiring against actual `web/__init__.py` `create_app()` factory before full implementation.
- All other phases: standard, well-documented patterns; no additional research-phase needed.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | PyPI version history, package `__init__.py` inspection, official FastAPI docs; `fastapi.sse` absence from 0.115.8 confirmed |
| Features | HIGH | `get_status()` payload, `items` schema, `price_history` schema confirmed from direct source reads |
| Architecture | HIGH | Cross-thread bridge verified against `core/service.py`; `asyncio.Queue` thread-safety confirmed from stdlib docs |
| Pitfalls | HIGH | XSS at `dashboard.html` line ~241 confirmed by direct inspection; `read_recent_logs()` sync full-file read confirmed |

**Overall confidence:** HIGH

**Gaps to address during planning:**
- **Log plugin-filter prerequisite**: The P2 log viewer plugin filter depends on every `writeLog` call tagging lines with `[PLUGIN_NAME]`. Verify format consistency before including in the Phase D plan. If inconsistent, defer.
- **`get_status()` last_error scrubbing verification**: Phase C must include a test asserting SSE data frames contain no credential-pattern strings (regex for `@`, `password`, `token`, `key=`, `cvv`). This test is the done-condition for the security scrubbing work.
- **Charting library final pick**: uPlot vs fnando/sparkline vs hand-rolled SVG — roadmapper must document this decision in the Phase A plan.
- **FastAPI 0.135 upgrade (tracked future item)**: `fastapi.sse.EventSourceResponse` available from 0.135.0 (March 2026; latest 0.138.0 June 2026). When a dep-refresh milestone is scoped, evaluate alongside the Pydantic floor change at 0.128.

---
*Research completed: 2026-06-25*
*Ready for roadmap: yes*
