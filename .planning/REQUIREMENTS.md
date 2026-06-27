# Requirements: ShopPyBot — Milestone v4.1 Dashboard & Observability

**Defined:** 2026-06-25
**Core Value:** Drop-in plugin framework — community adds retail platform integrations via a single Python file in `plugins/`; no core changes required.
**Milestone Goal:** Redesign the optional FastAPI web dashboard with a polished zero-dependency design system and surface rich live operational observability over SSE — without breaking the CLI-default, localhost-bound, no-Node posture.

## Milestone v4.1 Requirements

Requirements for this milestone. Each maps to exactly one roadmap phase (25-29).

### UI — Design System & Redesign

- [x] **UI-01**: User sees a redesigned dashboard built on a coherent vendored design system (CSS custom-property tokens + reusable component classes) with no external fonts, CDN, or Node build.
- [x] **UI-02**: User can switch between light and dark theme — auto via `prefers-color-scheme` plus a persisted manual toggle (`data-theme` on `<html>`) — with no flash-of-unstyled-content on page load.
- [x] **UI-03**: All API-sourced values render via safe DOM construction (`textContent`/`createElement`, never `innerHTML`); the existing items-table XSS at `dashboard.html` is fixed.
- [x] **UI-04**: The non-local access warning banner and CSRF origin protections remain visible and intact after the redesign (verified by the existing MC-4 test).

### OBS — Observability Surfaces

- [x] **OBS-01**: User sees a per-plugin health card showing status badge, heartbeat staleness, consecutive-error count, and items-checked count (from `get_status()` / `HealthRegistry`).
- [x] **OBS-02**: Each health card color-codes heartbeat staleness in three bands (<30s green / 30-60s amber / >60s red), computed with the monotonic clock.
- [x] **OBS-03**: Each health card shows a per-plugin confirmed-orders counter.
- [x] **OBS-04**: User sees a recent confirmed-buys table (item name, order_id, confirmed_at, checkout_attempts) sourced from purchased items (BUY-04 records).
- [x] **OBS-05**: User sees a per-item price-history chart (uPlot) with an explicit empty state for items that have no price data (e.g. non-Amazon plugins).
- [x] **OBS-06**: User sees a log viewer with per-level color-coding and a level filter.
- [x] **OBS-07**: User can tail/follow logs with pause-on-scroll and a bounded (500-line) DOM buffer that does not grow unbounded.
- [x] **OBS-08**: User can search log text (substring highlight) and filter logs by plugin (plugin filter contingent on logs consistently tagging `[PLUGIN_NAME]`; deferred if not verifiable).
- [x] **OBS-09**: User sees bot uptime in the global status bar (`uptime_secs` from `get_status()`).

### SSE — Live Push

- [ ] **SSE-01**: The dashboard receives live status and log updates over a single Server-Sent Events stream (`/api/events`), replacing the 2-second polling loop.
- [x] **SSE-02**: The SSE stream handles client disconnect/reconnect cleanly — keepalive heartbeat, automatic client reconnect, server-side generator cleanup on disconnect — and falls back to polling when SSE is unavailable.
- [x] **SSE-03**: Observability reads never block uvicorn's event loop (all sync reads via `asyncio.to_thread`) and never leak secrets to the browser (`get_status()` `last_error` scrubbed to exception class name; CI assertion that SSE frames contain no credential-pattern strings).

## Future Requirements

Deferred to a future milestone. Tracked but not in the v4.1 roadmap.

### Analytics

- **ANL-01**: Outcome analytics — success rate, time-to-checkout, drop-outcome trends (requires a new append-only events table; explicitly deferred in PROJECT.md).

### Dashboard Enhancements

- **OBSX-01**: Order deep-links from the confirmed-buys table to the retailer's order page (Amazon/BestBuy order_id URL formats unverified against live pages).
- **OBSX-02**: Multi-day log browsing and per-level log-count badges.

### Dependencies

- **DEP-01**: Upgrade FastAPI to 0.135+ to adopt native `fastapi.sse.EventSourceResponse` (crosses the 0.128 Pydantic floor change; belongs in a dedicated dep-refresh milestone with full test re-validation).

### Price Coverage

- **PRC-01**: Price capture (`get_price()`) for non-Amazon plugins so price-history charts are populated beyond Amazon (PRICE-02 follow-on).

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Any Node toolchain / package.json / CDN / external fonts | Hard milestone constraint; vendored CSS/JS only, preserves the v2.0 portability + security posture |
| Alerting rules engine in the UI | Single-operator localhost tool; YAGNI — notifications already fan out via the existing dispatcher |
| Plugin enable/disable from the dashboard | AppConfig has no per-plugin enabled field; web stays read-mostly over the core, not a control plane |
| Auth / roles / multi-tenant on the web UI | Localhost-bound single-operator tool; CSRF + non-local warning are the security model |
| Real-time SSE updates for price charts | Price scrapes are sparse/infrequent; an on-demand REST endpoint is sufficient |
| Chart zoom/pan, pagination, CSV export | Over-engineering for 5-50 sparse data points and a single operator |
| Moving the web UI off localhost-default / exposing it publicly | Violates held security posture; web binds localhost by default |
| Writes to credentials/config via new observability endpoints | Observability is strictly read-only over `get_status()` + DB; no new secrets, no new write paths |

## Traceability

Which phases cover which requirements. Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| UI-01 | Phase 25 | Complete |
| UI-02 | Phase 25 | Complete |
| UI-03 | Phase 25 | Complete |
| UI-04 | Phase 25 | Complete |
| OBS-01 | Phase 28 | Complete |
| OBS-02 | Phase 28 | Complete |
| OBS-03 | Phase 28 | Complete |
| OBS-04 | Phase 28 | Complete |
| OBS-05 | Phase 28 | Complete |
| OBS-06 | Phase 28 | Complete |
| OBS-07 | Phase 28 | Complete |
| OBS-08 | Phase 26 | Complete |
| OBS-09 | Phase 28 | Complete |
| SSE-01 | Phase 29 | Pending |
| SSE-02 | Phase 27 | Complete |
| SSE-03 | Phase 26 | Complete |

**Coverage:**

- v4.1 requirements: 16 total
- Mapped to phases: 16
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-25*
*Last updated: 2026-06-25 — traceability filled by roadmapper (all 16 requirements mapped)*
