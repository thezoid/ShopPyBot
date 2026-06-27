---
gsd_state_version: 1.0
milestone: v4.1
milestone_name: Dashboard & Observability
status: executing
last_updated: "2026-06-27T08:27:45.753Z"
last_activity: 2026-06-27 -- Phase 27 planning complete
progress:
  total_phases: 5
  completed_phases: 2
  total_plans: 9
  completed_plans: 6
  percent: 40
---

# ShopPyBot — State

## Project Reference

**Core Value**: Drop-in plugin framework — community adds retail platform integrations via a single Python file in `plugins/`; no core changes required.

**Project**: ShopPyBot
**Milestone**: v4.1 Dashboard & Observability
**Total Phases**: 5 (Phases 25-29)
**Total Requirements**: 16 (UI-01..04, OBS-01..09, SSE-01..03)

---

## Current Position

Phase: 26 (Read-Only API Endpoints) — EXECUTING
Plan: 2 of 3
Status: Ready to execute
Last activity: 2026-06-27 -- Phase 27 planning complete

## Phase Status

| Phase | Goal Summary | Status | Reqs |
|-------|-------------|--------|------|
| 25 — Design System | vendored CSS tokens + components, light/dark FOUC-safe, XSS fix, uPlot vendor, MC-4 preserved | Not started | UI-01, UI-02, UI-03, UI-04 |
| 26 — Read-Only API Endpoints | GET /api/history, GET /api/price-history, log filter/search params, asyncio.to_thread, secret-scrub CI assertion | Not started | OBS-08, SSE-03 |
| 27 — SSE Infrastructure | web/sse_hub.py + web/routes/sse.py, cross-thread bridge (SPIKE), keepalive, disconnect cleanup, cursor log tail | Not started | SSE-02 |
| 28 — Frontend Observability Surfaces | health cards, confirmed-buys table, price-history uPlot charts, log viewer + tail/filter, uptime bar | Not started | OBS-01, OBS-02, OBS-03, OBS-04, OBS-05, OBS-06, OBS-07, OBS-09 |
| 29 — SSE Client Wiring | replace setInterval with EventSource, dispatch by type, live health + log append, fallback, Live indicator | Not started | SSE-01 |

---

## Performance Metrics

**Plans completed**: 0 of TBD
**Requirements completed**: 0 of 16
**Phases completed**: 0 of 5
**Blockers resolved**: 0

---

## Accumulated Context

### Key Decisions Logged (v4.1)

- [Phase 25 — roadmap]: charting library = uPlot 1.6.32 (MIT, ~52KB IIFE + ~1KB CSS, interactive tooltips, Canvas 2D, time series); vendored to `web/static/uplot.min.js` + `web/static/uplot.min.css`; no CDN, no Node.
- [Phase 25 — roadmap]: CSS 3-file split: `tokens.css` (`:root` blocks only), `components.css` (component rules via `var(--xxx)` only), `dashboard.css` (layout + `@import`); each file stays under 200 lines.
- [Phase 25 — roadmap]: FOUC prevention: inline synchronous `<script>` as FIRST child of `<head>` (before any `<link>`); reads `localStorage.getItem("theme")` and sets `document.documentElement.dataset.theme`; executes before browser requests any CSS.
- [Phase 27 — roadmap]: SSE bridge pattern: uvicorn-side `_poll_loop` background task is the SOLE SSE producer; calls `asyncio.to_thread(svc.get_status)` on uvicorn's event loop; bot daemon thread never touches `asyncio.Queue` objects. BotService is unchanged.
- [Phase 27 — roadmap]: SPIKE recommended at Phase 27 start — validate lifespan + `asyncio.create_task` + `SseHub` wiring against actual `web/__init__.py` `create_app()` factory before full implementation.
- [Phase 26 — roadmap]: `get_status()` `last_error` scrubbed to `exc.__class__.__name__` only at the `get_status()` boundary (never `str(exc)`); CI assertion validates SSE frames contain no credential-pattern strings (`@`, `password`, `token`, `key=`, `cvv`).
- [Phase 26 — roadmap]: No new Python dependencies; raw `StreamingResponse(media_type="text/event-stream")` from starlette (already transitive dep) covers all SSE needs; do NOT add `sse-starlette`; do NOT upgrade FastAPI to 0.135+ in this milestone.
- [Phase 26 — roadmap]: Log plugin-filter (OBS-08) is contingent — verify `writeLog` consistently tags lines with `[PLUGIN_NAME]` before building; if inconsistent, defer plugin filter sub-feature (not the whole requirement) to post-v4.1.

### Key Decisions Logged (v4.0 carried)

- [Phase 10-01]: create_app() router imports deferred inside factory body to avoid circular import; all fastapi imports confined to web/ package (CLI-04)
- [Phase 10-01]: WEB_ALLOWLIST extends CLI ALLOWLIST with 4 notifier toggles only (no platform enables -- AppConfig has no enabled field per config-scope-note)
- [Phase 10-01]: TemplateResponse uses new Starlette API signature: TemplateResponse(request, name, context) to avoid DeprecationWarning
- [Phase 18-02]: place_order_guarded is a concrete async method on RetailerPlugin ABC; test_mode default True (fail-safe suppress when config missing); PLUGIN_API_VERSION stays 2 (additive BUY-02)
- [Phase 22-02]: sqlite3.OperationalError only caught in run_plugin items read; DatabaseError (corruption) propagates (REL-05 / Pitfall 7)
- [Phase 23-01]: SessionStore mirrors EncryptedFileBackend [salt][Fernet token] layout; restore() returns None (not raises) on InvalidToken -- REL-04 silent login fallback contract

### Research Flags (v4.1 — carry into planning)

- Phase 25: Run MC-4 test against the new template before closing the phase — non-local banner must remain visible and correctly styled in both themes (Pitfall 9).
- Phase 26: Verify log line format for `[PLUGIN_NAME]` tag consistency before building plugin filter in `read_logs_filtered()`; if inconsistent, scope OBS-08 to level+search only (plugin filter deferred).
- Phase 27: Spike at phase start — validate `asyncio.create_task(_poll_loop(...))` inside FastAPI lifespan context manager against installed `fastapi==0.115.8` + `uvicorn==0.30.6` before full implementation (cross-loop race is highest-risk pitfall).
- Phase 27: `request.is_disconnected()` must be polled inside the SSE generator loop — verify FastAPI 0.115.8 supports this API (HIGH confidence per research, but confirm before implementing).
- Phase 28: Price data is Amazon-only today (PRICE-02); non-Amazon items get explicit "No price history available for this plugin" message — never a blank chart area.
- All phases: Zero-Node constraint is hard — no package.json, no CDN references, no external font URLs; all JS/CSS vendored via `web/static/`.

### Active Todos

- Execute Phase 25 plan (`/gsd:plan-phase 25`).
- Operator: complete the v4.0 live-UAT checklist (STATE.md Deferred Items) before first production live-buy.

### Blockers

- None

---

## Deferred Items

### Carried from v4.0 milestone close (2026-06-25) — 17 items

All deferred per the autonomous live-UAT policy; none are code gaps. This is the operator's pre-production live-buy checklist.

| Category | Item | Status |
|----------|------|--------|
| uat | Phase 18 — live `--monitor-only` run fires alerts but places no order (18-HUMAN-UAT.md) | partial (1 pending) |
| uat | Phase 19 — live Amazon/BestBuy confirmation URL + DOM order-number selectors (19-HUMAN-UAT.md) | partial (3 pending) |
| uat | Phase 20 — live BestBuy/Amazon shipping form-fill selectors + CVV entry (20-HUMAN-UAT.md) | partial (4 pending) |
| uat | Phase 21 — per-step timeout clean-abort under a real slow drop (21-HUMAN-UAT.md) | partial (2 pending) |
| uat | Phase 22 — live supervisor restart + browser relaunch + SIGTERM teardown (22-HUMAN-UAT.md) | partial (2 pending) |
| uat | Phase 23 — live cross-restart MFA/login-skip; persisted session accepted (23-HUMAN-UAT.md) | partial (2 pending) |
| uat | Phase 24 — live headless-server run, no audio device / pygame absent (24-HUMAN-UAT.md) | partial (1 pending) |
| verification | Phases 18-24 — VERIFICATION.md status `human_needed` (automated must-haves passed; live checks deferred) | human_needed (7) |
| todo | Amazon WAF CAPTCHA auto-solve wiring (waf-auto-solve-followup.md) | pending (medium); manual-pause fallback in place |
| seed | SEED-001 — public repo history scrub/squash before release | dormant (release milestone) |
| seed | SEED-002 — release-please automatic version tagging | dormant (release milestone) |

**Tracked HIGH item (from v4.0 audit):** Phase 21 place-order-stage timeout double-buy edge (placed-but-unconfirmed) — verify live and consider P22-style hardening.

---
| Phase 25-design-system P01 | 566s | 2 tasks | 2 files |
| Phase 25-design-system P02 | 480s | 3 tasks | 5 files |
| Phase 25-design-system P03 | 412 | 3 tasks | 1 files |
| Phase 26-read-only-api-endpoints P01 | 360 | 3 tasks | 2 files |

## Session Continuity

**Last action**: v4.1 roadmap defined (Phases 25-29, 16 requirements mapped).
**Next action**: Execute `/gsd:plan-phase 25` to plan Phase 25 (Design System).
**Context to carry**: uPlot chosen as charting library (vendored, MIT); 3-file CSS split (tokens/components/layout); FOUC prevention via inline sync script first in `<head>`; SSE bridge pattern is uvicorn-only poll (bot thread never touches queues); Phase 27 spike required before full implementation; MC-4 test must pass at Phase 25 close.

---

## Performance Metrics (all milestones history)

| Phase | Plan | Duration | Notes |
|-------|------|----------|-------|
| Phase 01-foundations-security P01 | 8m | 3 tasks | 5 files |
| Phase 01 P02 | 5m | - tasks | - files |
| Phase 01 P03 | 5m | 2 tasks | 2 files |
| Phase 01 P04 | 8min | 3 tasks | 3 files |
| Phase 01 P05 | 11min | 3 tasks | 4 files |
| Phase 02-plugin-migration P01 | 207 | 2 tasks | 2 files |
| Phase 02-plugin-migration P03 | 20m | 2 tasks | 2 files |
| Phase 02-plugin-migration P04 | 20min | 2 tasks | 4 files |
| Phase 02-plugin-migration P06 | 15 | 2 tasks | 3 files |
| Phase 02-plugin-migration P05 | 10 | 1 tasks | 1 files |
| Phase 03-community-documentation P01 | 8m | 2 tasks | 3 files |
| Phase 03-community-documentation P02 | 5min | 2 tasks | 5 files |
| Phase 04-async-orchestrator P01 | 15 | 2 tasks | 3 files |
| Phase 04-async-orchestrator P04 | 15m | 2 tasks | 5 files |
| Phase 04-async-orchestrator P05 | 15 | 1 tasks | 3 files |
| Phase 05-notification-system P02 | 12m | 2 tasks | 3 files |
| Phase 05-notification-system P03 | 4m | 2 tasks | 3 files |
| Phase 05-notification-system P04 | 3 | 1 tasks | 3 files |
| Phase 05-notification-system P05 | 25 | 2 tasks | 4 files |
| Phase 06-platform-expansion P01 | 15 | 2 tasks | 9 files |
| Phase 06-platform-expansion P06-02 | 5 minutes | - tasks | - files |
| Phase 06 P03 | 12 | 3 tasks | 9 files |
| Phase 06-platform-expansion P04 | 4m | 2 tasks | 4 files |
| Phase 06-platform-expansion P05 | 5m | 2 tasks | 2 files |
| Phase 07-modular-core-service P01 | 375s | 2 tasks | 3 files |
| Phase 07-modular-core-service P02 | 4min | 1 tasks | 3 files |
| Phase 07-modular-core-service P03 | 5m | 2 tasks | 2 files |
| Phase 08-credential-store P01 | 8min | 3 tasks | 4 files |
| Phase 08-credential-store P02 | 7min | 2 tasks | 3 files |
| Phase 08 P03 | 12min | 3 tasks | 4 files |
| Phase 08-credential-store P04 | 15min | 3 tasks | 14 files |
| Phase 09-cli-front-end P01 | 12m | 3 tasks | 15 files |
| Phase 09-cli-front-end P02 | 8min | 2 tasks | 4 files |
| Phase 09-cli-front-end P03 | 4min | 2 tasks | 2 files |
| Phase 09-cli-front-end P04 | 4m | 1 tasks | 1 files |
| Phase 10-optional-web-ui P01 | 15m | 3 tasks | 21 files |
| Phase 10-optional-web-ui P02 | 6m | 2 tasks | 2 files |
| Phase 10-optional-web-ui P03 | 3m | 1 tasks | 1 files |
| Phase 10-optional-web-ui P04 | 8min | 2 tasks | 3 files |
| Phase 11 P01 | 5m | 3 tasks | 4 files |
| Phase 11 P02 | 8min | 3 tasks | 5 files |
| Phase 11 P03 | 7m | 3 tasks | 3 files |
| Phase 11 P04 | 8m | 2 tasks | 2 files |
| Phase 13 P01 | 7min | 2 tasks | 2 files |
| Phase 13 P02 | 5min | 2 tasks | 3 files |
| Phase 12-stability-foundation P01 | 3min | 2 tasks | 2 files |
| Phase 12-stability-foundation P02 | 237 | 2 tasks | 2 files |
| Phase 12 P03 | 4min | - tasks | - files |
| Phase 12 P04 | 5min | 2 tasks | 1 files |
| Phase 13 P03 | 13min | 3 tasks | 11 files |
| Phase 14 P01 | 10min | 2 tasks | 7 files |
| Phase 14-anti-detection-layer-2-captcha-solving P02 | 8min | 2 tasks | 4 files |
| Phase 14-anti-detection-layer-2-captcha-solving P03 | 18min | 2 tasks | 4 files |
| Phase 15-plugin-ecosystem-registry P01 | 8min | 2 tasks | 2 files |
| Phase 15-plugin-ecosystem-registry P02 | 12min | 3 tasks | 4 files |
| Phase 15-plugin-ecosystem-registry P03 | 9min | 3 tasks | 5 files |
| Phase 16-price-monitoring P01 | 5min | 2 tasks | 3 files |
| Phase 16 P02 | 8min | 4 tasks | 6 files |
| Phase 16-price-monitoring P03 | 8min | 3 tasks | 5 files |
| Phase 16-price-monitoring P04 | 5min | 3 tasks | 3 files |
| Phase 17-test-hardening P01 | 15 | 2 tasks | 3 files |
| Phase 17-test-hardening P02 | 3min | 2 tasks | 1 files |
| Phase 17-test-hardening P03 | 8min | 2 tasks | 2 files |
| Phase 17-test-hardening P04 | 4min | 1 tasks | 1 files |
| Phase 18 P02 | 267 | 2 tasks | 2 files |
| Phase 18 P18-03 | 8m | 2 tasks | 6 files |
| Phase 18 P04 | 18 | 2 tasks | 9 files |
| Phase 19 P19-01 | 4min | 3 tasks | 2 files |
| Phase 19-db-schema-confirmation-detection P02 | 8 | 2 tasks | 2 files |
| Phase 19 P19-03 | 3min | 1 task | 2 files |
| Phase 19-db-schema-confirmation-detection P19-04 | 15min | 3 tasks | 6 files |
| Phase 20 P20-01 | 8min | 2 tasks | 3 files |
| Phase 20 P20-02 | 6min | 2 tasks | 3 files |
| Phase 20-checkout-profile-form-fill P03 | 7min | 2 tasks | 4 files |
| Phase 20-checkout-profile-form-fill P04 | 14min | 3 tasks | 7 files |
| Phase 21 P21-02 | 7min | 1 tasks | 2 files |
| Phase 21-per-step-timeouts-unified-retry-cart-retry P03 | 30 | 2 tasks | 7 files |
| Phase 21 P04 | 20min | 1 tasks | 3 files |
| Phase 22 P01 | 8min | 2 tasks | 3 files |
| Phase 22 P02 | 6min | 2 tasks | 2 files |
| Phase 22 P03 | 21min | 3 tasks | 2 files |
| Phase 23-encrypted-session-persistence P23-01 | 4min | 2 tasks | 2 files |
| Phase 23-encrypted-session-persistence P23-02 | 5min | 2 tasks | 2 files |
| Phase 23-encrypted-session-persistence P23-03 | 3min | 1 task | 1 file |
| Phase 23-encrypted-session-persistence P23-04 | 12min | 3 tasks | 5 files |
| Phase 24-health-surface-server-safety P24-01 | 8m | 2 tasks | 2 files |

---

*Last updated: 2026-06-25 — v4.1 roadmap created (Phases 25-29)*

## Decisions

- [Phase ?]: Phase 25-01: CSS comment stripping in test_no_external_urls_in_static prevents false positives on dashboard.css header comment text
- [Phase ?]: Phase 25-01: test_no_innerHTML_with_api_data uses re.DOTALL to catch both XSS violations including the multiline cred.name case at line 255
- [Phase ?]: CSS token split
- [Phase ?]: escHtml unused stub
