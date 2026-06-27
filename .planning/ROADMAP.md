# ShopPyBot — Roadmap

## Project

**Core Value:** A drop-in plugin framework that lets the community add new retail platform integrations by placing a single Python file in `plugins/` — no core changes required.

---

## Milestones

- ✅ **v1 Open Source Launch** — Phases 1-6 (shipped 2026-06-03)
- ✅ **v2.0 Modular Core + Cross-Platform UX** — Phases 7-11 (shipped 2026-06-06)
- ✅ **v3.0 Resilience + Ecosystem** — Phases 12-17 (shipped 2026-06-10)
- ✅ **v4.0 Win-the-Drop (Acquisition Core + Reliability)** — Phases 18-24 (shipped 2026-06-25)
- **v4.1 Dashboard & Observability** — Phases 25-29 (active)

---

## Phases

<details>
<summary>✅ v1 Open Source Launch (Phases 1-6) — SHIPPED 2026-06-03</summary>

- [x] Phase 1: Foundations + Security (5/5 plans) — 2026-06-02
- [x] Phase 2: Plugin Migration (6/6 plans) — 2026-06-03
- [x] Phase 3: Community Documentation (2/2 plans) — 2026-06-03
- [x] Phase 4: Async Orchestrator (5/5 plans) — 2026-06-03
- [x] Phase 5: Notification System (5/5 plans) — 2026-06-03
- [x] Phase 6: Platform Expansion (5/5 plans) — 2026-06-03

Full phase detail archived at `.planning/milestones/v1-phases` (see also `milestones/`).

</details>

<details>
<summary>✅ v2.0 Modular Core + Cross-Platform UX (Phases 7-11) — SHIPPED 2026-06-06</summary>

- [x] Phase 7: Modular Core Service (3/3 plans) — 2026-06-04
- [x] Phase 8: Credential Store (4/4 plans) — 2026-06-04
- [x] Phase 9: CLI Front-End (4/4 plans) — 2026-06-04
- [x] Phase 10: Optional Web UI (4/4 plans) — 2026-06-04
- [x] Phase 11: Cross-Platform Verification (5/5 plans) — 2026-06-05

Full phase detail archived at `.planning/milestones/v2.0-ROADMAP.md`.
Audit: `.planning/milestones/v2.0-MILESTONE-AUDIT.md` (status: passed).

</details>

<details>
<summary>✅ v3.0 Resilience + Ecosystem (Phases 12-17) — SHIPPED 2026-06-10</summary>

- [x] Phase 12: Stability Foundation (4/4 plans) — 2026-06-09
- [x] Phase 13: Anti-Detection Layer 1 — Fingerprint + Proxy (3/3 plans) — 2026-06-09
- [x] Phase 14: Anti-Detection Layer 2 — CAPTCHA Solving (3/3 plans) — 2026-06-09
- [x] Phase 15: Plugin Ecosystem Registry (3/3 plans) — 2026-06-09
- [x] Phase 16: Price Monitoring (4/4 plans) — 2026-06-10
- [x] Phase 17: Test Hardening (4/4 plans) — 2026-06-10

Full phase detail archived at `.planning/milestones/v3.0-ROADMAP.md`.
Audit: `.planning/milestones/v3.0-MILESTONE-AUDIT.md`.

</details>

<details>
<summary>✅ v4.0 Win-the-Drop (Phases 18-24) — SHIPPED 2026-06-25</summary>

- [x] Phase 18: Safety Gate + Config Foundation (4/4 plans) — 2026-06-11
- [x] Phase 19: DB Schema + Confirmation Detection (4/4 plans) — 2026-06-11
- [x] Phase 20: Checkout Profile + Form-Fill (4/4 plans) — 2026-06-11
- [x] Phase 21: Per-Step Timeouts + Unified Retry + Cart-Retry (4/4 plans) — 2026-06-12
- [x] Phase 22: Supervisor + Browser Relaunch + Server Safety (4/4 plans) — 2026-06-12
- [x] Phase 23: Encrypted Session Persistence (4/4 plans) — 2026-06-12
- [x] Phase 24: Health Surface + Server Safety (5/5 plans) — 2026-06-12

Full phase detail archived at `.planning/milestones/v4.0-ROADMAP.md`.
Audit: `.planning/milestones/v4.0-MILESTONE-AUDIT.md` (status: tech_debt — pre-accepted live-UAT debt).

</details>

### v4.1 Dashboard & Observability (Phases 25-29)

- [x] **Phase 25: Design System** — Vendored CSS token/component layer, light/dark theme (FOUC-safe), XSS fix, chart library vendor (completed 2026-06-25)
- [x] **Phase 26: Read-Only API Endpoints** (0/3 plans) — GET /api/history, GET /api/price-history/{item}, log filter/search query params, asyncio.to_thread wrapping + secret-scrub CI assertion (completed 2026-06-27)
- [x] **Phase 27: SSE Infrastructure** — web/sse_hub.py + web/routes/sse.py, cross-thread bridge, keepalive, disconnect cleanup, cursor-based log tail (completed 2026-06-27)
- [ ] **Phase 28: Frontend Observability Surfaces** — Health cards, confirmed-buys table, price-history charts, log viewer, uptime status bar (one-shot fetch)
- [ ] **Phase 29: SSE Client Wiring** — Replace setInterval with EventSource, dispatch by type, live health + log append, polling fallback, Live/Reconnecting indicator

---

## Phase Details

### Phase 25: Design System

**Goal**: Operators see a redesigned dashboard with a coherent, maintainable vendored design system that supports automatic and manual light/dark theme switching with no external dependencies, no flash of unstyled content, and no regressions to existing security controls.
**Depends on**: Nothing (pure frontend, zero Python changes)
**Requirements**: UI-01, UI-02, UI-03, UI-04
**Success Criteria** (what must be TRUE):

  1. Dashboard renders with consistent token-driven colors, spacing, and typography in both light and dark mode; no hardcoded hex values remain in component rules.
  2. Dark mode activates automatically from OS preference (`prefers-color-scheme`) and can be toggled manually; the choice persists across page reloads with no visible flash of the wrong theme on load.
  3. The existing `loadItems()` XSS vector (`tr.innerHTML` with `item.name`/`item.link`) is replaced with `createElement`/`textContent`; adding an item named `<b>bold</b>` renders as literal text in the items table.
  4. The non-local access warning banner and CSRF origin gate are visually intact and correctly styled in both themes; the existing MC-4 test passes against the new template.
  5. uPlot is vendored to `web/static/uplot.min.js` (and companion `uplot.min.css`) with no CDN reference; the file is served by the existing `StaticFiles` mount.

> Path note: the served vendor path is `web/static/vendor/uplot.iife.min.js` + `web/static/vendor/uplot.min.css` (all-lowercase, per 25-UI-SPEC.md). Criterion 5 ("no CDN, served by StaticFiles") is satisfied by any no-CDN path under the static mount; StaticFiles serves subdirectories.

**Plans**: 3 plans

- [x] 25-01-PLAN.md — Wave 0 test scaffold: CSS static-analysis tests + FOUC/link-order/XSS-regression/uPlot-served template tests
- [x] 25-02-PLAN.md — Wave 1: split tokens.css/components.css/dashboard.css (token-driven, zero hardcoded hex) + vendor uPlot 1.6.32
- [x] 25-03-PLAN.md — Wave 2: dashboard.html FOUC script, sticky header + theme toggle, XSS fix (loadItems/loadCredentials), MC-4 banner preserved

**UI hint**: yes

### Phase 26: Read-Only API Endpoints

**Goal**: All observability data the frontend needs is available as curl-testable HTTP endpoints; every sync DB read is wrapped in `asyncio.to_thread` so uvicorn's event loop is never blocked; and a CI assertion confirms the read path never leaks credential-pattern strings.
**Depends on**: Phase 25 (design system tokens ready; HTML surfaces built next)
**Requirements**: OBS-08, SSE-03
**Success Criteria** (what must be TRUE):

  1. `curl http://localhost:8000/api/history` returns `{"confirmed_orders": [...]}` with `name`, `order_id`, `confirmed_at`, and `checkout_attempts` fields; an empty list is returned when no confirmed orders exist.
  2. `curl http://localhost:8000/api/price-history/{link_b64}` returns `{"series": [...]}` for an Amazon item and `{"series": []}` for a non-Amazon item; the call completes without error in both cases.
  3. `GET /api/logs?level=ERROR&search=captcha&n=50` returns only lines matching all supplied filters; omitting all params degrades to the existing `read_recent_logs(50)` behavior.
  4. A CI test asserts that no SSE data frame or `/api/status` response JSON contains strings matching credential-pattern regexes (`@`, `password`, `token`, `key=`, `cvv`); `get_status()` `last_error` fields are scrubbed to `exc.__class__.__name__` only.

**Plans**: 3 plans

- [x] 26-01-PLAN.md — Wave 0 RED test scaffold: TestClient tests for /api/history, /api/price-history, /api/logs filtering, credential-leak guard + get_confirmed_orders_sync model test
- [x] 26-02-PLAN.md — Wave 1: get_confirmed_orders_sync + read_logs_filtered; GET /api/history, /api/price-history/{link_b64}, modified /api/logs (level/search/n) all asyncio.to_thread-wrapped
- [x] 26-03-PLAN.md — Wave 1: HealthRegistry.record_last_error (scrubbed) + supervise() call-site; credential-pattern CI guard GREEN

### Phase 27: SSE Infrastructure

**Goal**: A single `/api/events` SSE endpoint delivers live status and log events to browser clients over a clean cross-thread bridge, handles client disconnect without leaking generators, and is validated in complete isolation before any browser involvement.

NOTE: This is the highest-risk phase. A spike is recommended at the start — validate the lifespan + `asyncio.create_task` + `SseHub` wiring against the actual `web/__init__.py` `create_app()` factory before full implementation. The bot daemon thread must never touch `asyncio.Queue` objects directly; uvicorn's `_poll_loop` is the sole SSE producer.
**Depends on**: Phase 26 (API endpoint patterns established; to_thread wrapping pattern in place)
**Requirements**: SSE-02
**Success Criteria** (what must be TRUE):

  1. `curl -N http://localhost:8000/api/events` receives a `data:` frame approximately every 1 second; a `: keep-alive` comment line is emitted every ~15 seconds during idle periods so the connection stays open through proxy timeouts.
  2. Closing the curl client causes the server-side generator to exit cleanly (confirmed via a server log line or test assertion); no queue accumulates in `SseHub` after the disconnect.
  3. Starting and stopping the bot daemon causes `status.running` to flip in the SSE stream within 1-2 seconds; the stream remains open and continues delivering events across bot restarts without a server restart.
  4. The SSE stream opens with `retry: 3000\n\n` so the browser waits 3 seconds before reconnecting after a server restart, preventing rapid reconnect storms.

**Plans**: 3 plans

- [x] 27-01-PLAN.md — Wave 0 RED spike: tests/test_sse.py (6 isolation tests, one per criterion + SSE-03 carryover) + tests/test_log_reader.py (tail cursor + midnight rollover)
- [x] 27-02-PLAN.md — Wave 1: tail_log_lines cursor (web/log_reader.py) + SseHub bounded drop-oldest queues & _poll_loop sole-producer (web/sse_hub.py)
- [x] 27-03-PLAN.md — Wave 2: GET /api/events StreamingResponse + generator (web/routes/sse.py) + lifespan/SseHub/router wiring (web/__init__.py); all 6 SSE tests GREEN

### Phase 28: Frontend Observability Surfaces

**Goal**: Operators see all four observability surfaces rendered correctly in the dashboard — per-plugin health cards, confirmed-buys table, price-history charts, and a filtered log viewer with tail controls — all driven by one-shot fetch against Phase 26 endpoints.
**Depends on**: Phase 25 (design system components), Phase 26 (REST endpoints)
**Requirements**: OBS-01, OBS-02, OBS-03, OBS-04, OBS-05, OBS-06, OBS-07, OBS-08 (UI rendering), OBS-09
**Success Criteria** (what must be TRUE):

  1. Each plugin shows a health card with its status badge, heartbeat age, consecutive-error count, and items-checked count sourced from `get_status()`; heartbeat age is colored green (<30s), amber (30-60s), or red (>60s) using the monotonic clock.
  2. Each health card displays a per-plugin confirmed-orders counter drawn from `get_status()`.
  3. The confirmed-buys table renders rows with item name, order_id, confirmed_at, and checkout_attempts for all purchased items with a real order_id; the table is empty (not absent) when no confirmed orders exist.
  4. Each item in the items list shows a uPlot price-history chart when price data exists; items with no price history (non-Amazon plugins) show an explicit "No price history available for this plugin" message instead of a blank chart or render error.
  5. The log viewer renders lines with per-level color coding; the level filter narrows displayed lines; the tail/follow control auto-scrolls to new lines and pauses when the user scrolls up; the DOM buffer is capped at 500 lines.
  6. Bot uptime (from `get_status()` `uptime_secs`) appears in the global status bar.

**Plans**: 4 plans

- [ ] 28-01-PLAN.md — Wave 0 RED scaffold: heartbeat_age_secs snapshot-key guard + fresh/never unit tests; static-section/header-uptime/log-controls/uPlot-asset TestClient tests
- [ ] 28-02-PLAN.md — Wave 1: heartbeat_age_secs in get_snapshot() (core/health.py) + all token-only Phase 28 component classes (components.css)
- [ ] 28-03-PLAN.md — Wave 2: dashboard.html three section scaffolds + renderHealthCards()/renderUptime() wired into pollStatus() (OBS-01/02/03/09)
- [ ] 28-04-PLAN.md — Wave 3: dashboard.html loadConfirmedBuys() + loadPriceChart() (ISO→Unix, link_b64) + log viewer (color/filter/Follow/500-cap) (OBS-04/05/06/07/08-UI)

**UI hint**: yes

### Phase 29: SSE Client Wiring

**Goal**: The dashboard replaces its 2-second polling loop with a single persistent `EventSource('/api/events')` connection; health cards and the log panel update live from SSE events; a polling fallback activates in environments without `EventSource`; a "Live / Reconnecting" indicator shows connection state.
**Depends on**: Phase 27 (SSE infrastructure), Phase 28 (observability surfaces rendering correctly)
**Requirements**: SSE-01
**Success Criteria** (what must be TRUE):

  1. DevTools Network tab shows one persistent `text/event-stream` connection to `/api/events` replacing the two previous `setInterval` polling requests; no polling requests are made when SSE is connected.
  2. Health card status and heartbeat age update within 1-2 seconds of bot start/stop without any manual page refresh.
  3. New log lines appear in the log viewer in real time as the bot runs; each line appears exactly once (no duplicates from repeated full-tail pushes).
  4. Closing and reopening the browser tab results in a clean `EventSource` reconnect; the dashboard resumes live updates after reconnect without requiring a page reload or server restart.
  5. In a browser or environment without `EventSource` support, the dashboard falls back to the existing polling behavior; no JavaScript error is thrown.

**Plans**: TBD
**UI hint**: yes

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 25. Design System | 3/3 | Complete   | 2026-06-25 |
| 26. Read-Only API Endpoints | 3/3 | Complete   | 2026-06-27 |
| 27. SSE Infrastructure | 3/3 | Complete   | 2026-06-27 |
| 28. Frontend Observability Surfaces | 0/4 | Planned | - |
| 29. SSE Client Wiring | 0/TBD | Not started | - |

| Milestone | Phases | Plans | Status | Shipped |
|-----------|--------|-------|--------|---------|
| v1 Open Source Launch | 1-6 | 28/28 | ✅ Shipped | 2026-06-03 |
| v2.0 Modular Core + Cross-Platform UX | 7-11 | 20/20 | ✅ Shipped | 2026-06-06 |
| v3.0 Resilience + Ecosystem | 12-17 | 21/21 | ✅ Shipped | 2026-06-10 |
| v4.0 Win-the-Drop | 18-24 | 29/29 | ✅ Shipped | 2026-06-25 |
| v4.1 Dashboard & Observability | 25-29 | 6/TBD | In progress | - |

All requirements satisfied across v1 (44) + v2.0 (22) + v3.0 (18) + v4.0 (17). Per-milestone requirement detail in `.planning/milestones/v*-REQUIREMENTS.md`.

---

*Last updated: 2026-06-27 — Phase 28 planned (4 plans across 4 serialized waves: Wave 0 test scaffold, backend field + CSS, health/uptime HTML, buys/charts/log-viewer HTML).*
