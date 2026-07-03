---
gsd_state_version: 1.0
milestone: v4.2
milestone_name: Release Readiness
status: executing
last_updated: "2026-07-03T02:55:53.837Z"
last_activity: 2026-07-03
progress:
  total_phases: 6
  completed_phases: 5
  total_plans: 20
  completed_plans: 19
  percent: 83
---

# ShopPyBot — State

## Project Reference

**Core Value**: Drop-in plugin framework — community adds retail platform integrations via a single Python file in `plugins/`; no core changes required.

**Project**: ShopPyBot
**Milestone**: v4.2 Release Readiness (Phases 30-35)
**Total Phases**: 6 (Phases 30-35)
**Total Requirements**: 20 (RH-01..07, AF-01..03, BF-01..03, CFG-01..02, FC-01..02, DH-01..03)

---

## Current Position

Phase: 35
Plan: 02 complete (1 of 3 plans remaining: 35-03)
Status: Executing
Last activity: 2026-07-02

## Phase Status

| Phase | Goal Summary | Status | Reqs |
|-------|-------------|--------|------|
| 30 — Breakfix Hardening | Place-order double-buy latch (HIGH), Amazon WAF auto-solve wiring, post-login DOM/URL verification | In Progress (5/6 plans) | BF-01, BF-02, BF-03 |
| 31 — CI & Security Infrastructure | Non-destructive secret-scan audit, CodeQL workflow fix, dependabot + vuln remediation | Complete (3/3 plans) | RH-01, RH-04, RH-05 |
| 32 — Release Automation & Community Readiness | release-please seeded at v2.0.0 + pyproject version reconcile, README refresh, real security contact | Complete (3/3 plans) | RH-02, RH-03, RH-06, RH-07 |
| 33 — Config Refactor | Delay-field name harmonization with back-compat, generic per-platform config declaration | Complete (2/2 plans) | CFG-01, CFG-02 |
| 34 — Feature Completion | [plugin] log tags + /api/logs filter, outcome analytics over BUY-04 records | Complete (3/3 plans) | FC-01, FC-02 |
| 35 — Audit-Fixes & Doc-Hygiene Cleanup | SSR remove-button graceful degradation, last_heartbeat leak fix, dead escHtml() removal, v4.0/v4.1 frontmatter reconciliation | In Progress (2/3 plans) | AF-01, AF-02, AF-03, DH-01, DH-02, DH-03 |

---

## Performance Metrics

**Plans completed**: 0 of TBD
**Requirements completed**: 0 of 20
**Phases completed**: 0 of 6
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

### Sequencing Notes (v4.2 — carry into planning)

- Phase 30 (Breakfix Hardening) is sequenced first: BF-02 is the milestone's one HIGH-priority item (place-order-timeout double-buy latch); closing it before other debt reduces exposure the longest.
- Phase 31 must land before Phase 32: RH-04 (CodeQL) and RH-05 (dependabot) put CI security scanning in a working state before RH-02 (release-please) starts tagging releases against that same CI.
- Phase 32: RH-03 (pyproject version reconcile to 2.0.0) lands in the same phase as RH-02 (release-please seed) — release-please needs a correct pyproject source-of-truth from its first run.
- Phase 33: CFG-01 (field harmonization) must be implemented before CFG-02 (flexible per-platform config) — both touch the same config-schema surface; CFG-02 builds on the harmonized field set.
- Phase 34 FC-01 carries the v4.1 Phase 26 research flag forward: verify `[PLUGIN_NAME]` log-tag consistency in `writeLog` before building the `/api/logs` plugin filter (was deferred from OBS-08 pending this verification).
- Phase 35 folds Audit-Fixes (AF-*) and Doc-Hygiene (DH-*) together — both are low-effort, low-risk cleanup; sequenced last as the milestone's closing phase.

### Active Todos

- Continue `/gsd:execute-phase 35` (Audit-Fixes & Doc-Hygiene Cleanup) — plans 35-01 (AF-01 + AF-03) and 35-02 (AF-02) complete; 35-03 (DH-01/02/03 frontmatter reconciliation) remains.
- Operator: complete the v4.0 + v4.1 live-UAT checklists (STATE.md Deferred Items) before first production live-buy — unchanged, out of scope for v4.2.

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

**Tracked HIGH item (from v4.0 audit):** Phase 21 place-order-stage timeout double-buy edge (placed-but-unconfirmed) — verify live and consider P22-style hardening. **Addressed in v4.2 Phase 30 (BF-02).**
| Phase 30 P01 | 22min | 3 tasks | 5 files |
| Phase 30-breakfix-hardening P02 | 12min | 2 tasks | 2 files |
| Phase 30-breakfix-hardening P03 | 10min | 2 tasks | 3 files |
| Phase 30-breakfix-hardening P04 | 5min | 2 tasks | 4 files |
| Phase 30-breakfix-hardening P06 | 10min | 2 tasks | 10 files |
| Phase 30-breakfix-hardening P05 | 19min | 2 tasks | 4 files |
| Phase 31 P01 | 6min | 2 tasks | 3 files |
| Phase 31-ci-security-infrastructure P02 | 5min | 2 tasks | 2 files |
| Phase 31 P03 | 8min | 2 tasks | 3 files |
| Phase 32-release-automation-community-readiness P01 | 10min | 3 tasks | 4 files |
| Phase 32 P02 | 9min | 2 tasks | 1 files |
| Phase 32 P03 | 5min | 2 tasks | 2 files |
| Phase 33 P01 | 6min | 3 tasks | 5 files |
| Phase 33 P02 | 12min | - tasks | - files |
| Phase 34-feature-completion P01 | 3min | 2 tasks | 3 files |
| Phase 34 P03 | 15min | 3 tasks | 6 files |
| Phase 34 P02 | 4min | 2 tasks | 9 files |
| Phase 35 P01 | 5min | 3 tasks | 5 files |
| Phase 35 P02 | 8min | 2 tasks | 8 files |

### Acknowledged at v4.1 milestone close (2026-06-30) — 8 items

All deferred per the autonomous live-UAT policy; none are code gaps. Operator dashboard/observability checklist plus carried release items.

| Category | Item | Status |
|----------|------|--------|
| verification | Phase 27 — SSE infra live-socket checks (27-VERIFICATION.md) | human_needed |
| verification | Phase 28 — observability surfaces live-browser render (28-VERIFICATION.md) | human_needed |
| verification | Phase 29 — SSE client wiring live-browser (29-VERIFICATION.md) | human_needed |
| verification | Phase 29.1 — tech-debt fixes live-runtime (29.1-VERIFICATION.md) | human_needed |
| uat | Phase 29.1 — cold-load chart / stall->fallback / repeated-msg after repaint (29.1-HUMAN-UAT.md) | partial (3 pending) |
| todo | Amazon WAF CAPTCHA auto-solve wiring (waf-auto-solve-followup.md) | pending (medium); manual-pause fallback in place. **In scope as v4.2 Phase 30 (BF-01), code wiring only — live-challenge proof stays operator debt.** |
| seed | SEED-001 — public repo history scrub/squash before release | dormant (release milestone). **Non-destructive audit half in scope as v4.2 Phase 31 (RH-01); destructive rewrite stays operator-gated.** |
| seed | SEED-002 — release-please automatic version tagging | dormant (release milestone). **In scope as v4.2 Phase 32 (RH-02/RH-03).** |

**Audit warnings tracked to backlog (non-blocking, from v4.1 audit refresh):** UI-03 SSR remove-button dead click handler (Phase 25, graceful-degradation, not XSS) — **in scope as v4.2 Phase 35 (AF-01).** `last_heartbeat` raw monotonic float in `get_status()` / SSE status payload (Phase 27, cosmetic, no credential exposure) — **in scope as v4.2 Phase 35 (AF-02).**

---
| Phase 25-design-system P01 | 566s | 2 tasks | 2 files |
| Phase 25-design-system P02 | 480s | 3 tasks | 5 files |
| Phase 25-design-system P03 | 412 | 3 tasks | 1 files |
| Phase 26-read-only-api-endpoints P01 | 360 | 3 tasks | 2 files |
| Phase 27-sse-infrastructure P01 | 274s | 2 tasks | 2 files |
| Phase 27-sse-infrastructure P02 | 120s | 2 tasks | 2 files |
| Phase 27-sse-infrastructure P03 | 600 | 2 tasks | 3 files |
| Phase 28-frontend-observability-surfaces P01 | 269 | 2 tasks | 2 files |
| Phase 28-frontend-observability-surfaces P02 | 262 | 2 tasks | 2 files |
| Phase 28-frontend-observability-surfaces P03 | 379 | 2 tasks | 1 files |
| Phase 28-frontend-observability-surfaces P04 | 420 | 2 tasks | 1 files |
| Phase 29-sse-client-wiring PP01 | 233s | - tasks | - files |
| Phase 29-sse-client-wiring P02 | 240 | 2 tasks | 2 files |

## Session Continuity

**Last action**: Phase 33 Plan 02 complete (CFG-02: generic per-platform config declaration. `PlatformsConfig` gained `model_config = ConfigDict(extra="allow")` as its first class-body statement — an undeclared `platforms.<key>` section now passes through as a raw dict instead of being silently dropped (the literal bug CFG-02 fixes); the 7 declared platform fields keep full strict validation unchanged, proven by `test_known_platform_strict_validation_intact`. Added `RetailerPlugin.get_platform_config(model_cls)` to `core/plugin_base.py`: getattr-safe, four-case return logic (`model_cls()` defaults on missing config/key/section; the already-validated instance for a built-in platform; `model_cls(**raw)` for a new plugin's passthrough dict, raising `ValidationError` fail-loud on bad data; `model_cls()` fallback). `PLUGIN_API_VERSION` stays 2. Fixture-plugin test (`tests/test_platform_config_extension.py`) proves a brand-new `platforms.costco` section loads+validates via a test-module-scope `CostcoPlatformConfig` model (no `importlib.import_module` of the exec_module-loaded tmp plugin, per the plan's revised approach) with `core/config_schema.py` touched by nothing beyond the single `extra="allow"` line. TDD: RED->GREEN across 2 task commits; during GREEN verification, found the plan's proposed `AppConfig(**{"platforms": {...}})` fixture-construction snippet silently no-ops (`AppConfig.settings_customise_sources` excludes `init_settings` from its source tuple) — fixed by switching to the codebase's established `yaml_file=<Path>` injection pattern (Rule 1 auto-fix, test-only, no production-code change).) Full suite: 898 passed, 2 skipped (baseline 894 + 4 net-new tests), no regression. **Phase 33 (Config Refactor) is now fully complete: CFG-01 (33-01) and CFG-02 (33-02) both landed.** CFG-01 and CFG-02 marked complete in REQUIREMENTS.md. STATE.md/ROADMAP.md updated.
**Next action**: Continue `/gsd:execute-phase 35` -- run plan 35-03 (DH-01/02/03 frontmatter reconciliation), the phase's final plan. Phase 35 Plans 01 (AF-01 + AF-03) and 02 (AF-02) are now complete.
**Context to carry**: v4.2 is a debt-closure + release-hardening milestone; "done" = code-complete and CI-green, no live-environment testing in scope. Phase 30 (Breakfix) shipped first since BF-02 was the milestone's only HIGH item; 30-01..30-06 all complete. Phase 31 is fully complete (31-01 RH-01 secret-scan audit, 31-02 RH-04 CodeQL fix + ci.yml Node20 bump, 31-03 RH-05 dependabot + vuln remediation). Phase 32 is fully complete (32-01 RH-02/RH-03 release-please seed + pyproject reconcile, 32-02 RH-06 README rewrite, 32-03 RH-07 security contact). Phase 33 is now fully complete (33-01 CFG-01 field harmonization + back-compat shim, 33-02 CFG-02 generic per-platform config extension point via extra="allow" + get_platform_config). CI-verification/operator debt carried forward (post-push, not actioned this session per no-push policy): gitleaks-run green (31-01), CodeQL Actions green-run (31-02), Dependabot alert queue drain (31-03), release-please Actions-permissions allowlist gate (32-01 — third-party action blocked until operator widens selected-actions policy), and the PVR-enable repo Settings toggle (32-03) — all operator-gated GitHub Settings changes, not code gaps. New operator-UAT item from 33-01: live Amazon/BestBuy availability-poll cadence is now jittered 30-40s (was flat 30s) -- observable only against a live run, tracked in 33-VALIDATION.md. Phase 35 folds AF-* + DH-* as a trailing low-risk cleanup phase.

**Last action (34-01)**: Phase 34 Plan 01 complete (FC-01: `[plugin]` log tag guarantee. `logger.py` gained a module-level `_current_plugin: ContextVar[str]` (default `"core"`) and `set_log_plugin(platform_key)` that coerces falsy input to `"core"`. `writeLog()` now builds one `head = f"[{type.upper()}][{plugin}][{ts}]"` reused identically for both the colored `print()` and the file write — level bracket stays first, plugin is the second bracket, timestamp computed once (consolidating the pre-existing double `datetime.now()` call). `core/orchestrator.py:supervise()` calls `set_log_plugin(getattr(plugin, "platform_key", None) or plugin.__class__.__name__.lower())` as its first executable statement; `asyncio.TaskGroup`/`create_task` context-copy semantics give automatic per-plugin isolation with no locking. TDD: RED->GREEN across 2 task commits (5 new tests: tag injection, `[core]` sentinel, level-first-bracket format-compat, falsy-input coercion, level-gate regression). Manual verification confirmed the produced line format: `[INFO][amazon][2026July02@20:33:04] checking stock`. Full suite: 906 passed, 2 skipped (baseline 901 + 5 net-new tests), no regression. No deviations -- plan executed exactly as written.) FC-01 marked complete in REQUIREMENTS.md.

**Last action (34-03)**: Phase 34 Plan 03 complete (FC-02: outcome analytics, executed out of order ahead of 34-02 since the two plans touch disjoint files. `core/analytics.py` gained a PURE `compute_analytics(rows, platform_of)` -- stdlib `datetime` only, zero DB/fastapi imports -- computing `success_rate` (confirmed/attempted, union denominator `place_order_attempted_at IS NOT NULL OR order_id IS NOT NULL`, deliberately never `checkout_attempts` which increments under test_mode) and `avg_time_to_checkout_secs` (`confirmed_at - place_order_attempted_at` per confirmed row with both timestamps and a non-negative delta), overall + per-plugin, divide-by-zero-safe. `models.get_order_analytics_rows_sync()` mirrors `get_confirmed_orders_sync`. `BotService.get_analytics()` resolves `link -> platform_key` via `PluginRegistry.domain_patterns` (link never leaves this seam). `GET /api/analytics` (read-only, `asyncio.to_thread`, no `check_origin`) added to `web/routes/api.py`. Dashboard gained `#section-analytics`: two `.health-card` stat cards + a bare per-plugin `<table>`, rendered via `createElement`/`textContent` only (null metrics render "N/A"), wired into the initial backfill block. TDD: RED (4 fixture tests, `45e51a7`) -> GREEN (`c66fc6a`) for Task 1; Task 2 (`9bf6652`) added the endpoint + a no-link-key/CRED_PATTERN test; Task 3 (`71abe90`) added the dashboard view. Full suite: 912 passed, 2 skipped (baseline 906 + 6 net-new tests), no regression. Manual smoke test confirmed `BotService.get_analytics()` against a fresh empty DB returns valid JSON with `success_rate`/`avg_time_to_checkout_secs` = `null` and no `ZeroDivisionError`. No deviations -- plan executed exactly as written.) FC-02 marked complete in REQUIREMENTS.md. Phase 34 is now 2/3 plans complete -- 34-02 (`/api/logs` plugin filter, FC-01's remaining sub-feature) is the only plan left before Phase 34 closes.

**Last action (34-02)**: Phase 34 Plan 02 complete (FC-01 filter+UI, the deferred half of OBS-08. `web/log_reader.py:read_logs_filtered` gained a trailing `plugin: str | None = None` param AND-composed with the existing level/search filters via the `[plugin]` tag guaranteed by 34-01's ContextVar (filter-then-limit order preserved). `web/routes/api.py:/logs` validates `plugin` against `re.fullmatch(r"[a-z0-9]+", ...)` (V5 defense-in-depth whitelist, invalid values dropped to `None`) before passing it as the 4th positional to `asyncio.to_thread(read_logs_filtered, ...)`. `core/service.py:list_plugins()` gained a `platform_key` key per plugin (never the class name). `web/routes/pages.py`'s dashboard route now offloads `svc.list_plugins()` via `asyncio.to_thread` (Refinement 1, matches the `/logs`|`/history`|`/analytics` convention) and passes `plugins` into the template context. `web/templates/dashboard.html` gained a `#log-plugin-filter` `<select>` in `.log-controls`, Jinja2-populated from `platform_key` values, wired to `pollLogs()`'s `plugin` query param via a `change` listener mirroring the level dropdown -- zero new CSS (reuses the existing `select` rule). Refinement 2 (FC-01 live-tail completion): added a pure `lineMatchesFilters(line, level, search, plugin)` JS guard and gated the SSE `'log'` listener's `appendLogLine` call behind it, so live-streamed lines now respect the active level/search/plugin filters (previously only the one-shot `pollLogs` snapshot was filtered -- the plugin filter, and incidentally level+search too, were bypassed during live tailing, the dashboard's primary mode). Refinement 3 (param whitelist) evaluated and kept as the generic regex per the plan's own threat-model escape hatch: an enum check against the live `platform_key` set would require a `to_thread`-wrapped filesystem+importlib `PluginRegistry` scan on every `/api/logs` request, a hot, continuously-polled endpoint. TDD: RED (`6c93c87`) -> GREEN (`039f242`) for Task 1 (4-arg `read_logs_filtered` contract + updated arity asserts); Task 2 (`8543b57`) added the dropdown + platform_key + both refinements as a single commit. No JS test harness exists in this Zero-Node codebase, so the live-tail filter guard is verified via 2 new static-analysis tests in `tests/test_sse_wiring.py` (presence + ordering of `lineMatchesFilters(...)` before `appendLogLine(...)` in the rendered HTML), matching the codebase's existing `test_no_onmessage_for_named_events`-style pattern. Full suite: 923 passed, 2 skipped (baseline 912 + 11 net-new tests), no regression. No deviations beyond the 3 orchestrator-directed refinements, all applied as specified.) FC-01 and FC-02 both marked complete in REQUIREMENTS.md. **Phase 34 (Feature Completion) is now fully complete: 34-01, 34-02, 34-03 all landed.** STATE.md/ROADMAP.md updated.

**Last action (35-01)**: Phase 35 Plan 01 complete (AF-01 SSR remove-button graceful degradation + AF-03 dead escHtml() removal. `web/routes/pages.py` gained `POST /items/remove` on the unprefixed pages router: form-encoded, `Depends(check_origin)` CSRF-guarded (identical to every other mutating route), no-ops on an empty/missing `link` (never reaches `svc.remove_item`), calls `request.app.state.svc.remove_item(link)` for a non-empty link, and 303-redirects to `/` (POST/Redirect/GET). `web/templates/dashboard.html`'s dead SSR `.btn-remove` button (no JS listener existed anywhere) was replaced with a real `<form method="post" action="/items/remove">` + hidden `link` input + submit button reusing the existing `.btn-text-destructive` class -- the remove control now functions the instant the page loads or whenever `loadItems()`'s `fetch()` rejects, since `loadItems()` itself was left byte-for-byte unchanged (out of scope per RESEARCH.md Pitfall 1). AF-03: deleted the dead `escHtml()` helper (872-876) + its comment, confirmed 0 call sites via grep across `web/`. TDD: RED (`b9454d7`, 3 failing tests: functional remove+redirect, empty-link no-op, cross-origin 403) -> GREEN (`8f704ff`) for Task 1; Task 2 (`9794a10`) wired the SSR form + added an SSR-form-assertion test; Task 3 (`5e94f68`) deleted escHtml() + added a permanent grep-0 regression test. Full suite: 937 passed, 2 skipped (baseline 932 + 5 net-new tests), no regression. No deviations -- plan executed exactly as written.) AF-01 and AF-03 marked complete in REQUIREMENTS.md. Phase 35 is now 1/3 plans complete -- 35-02 (AF-02 last_heartbeat leak) and 35-03 (DH-01/02/03 frontmatter reconciliation) remain.

**Last action (35-02)**: Phase 35 Plan 02 complete (AF-02: raw `last_heartbeat` monotonic float scrubbed from the single shaping boundary, `HealthRegistry.get_snapshot()` (`core/health.py`) -- the public-dict comprehension now also excludes `last_heartbeat` while the existing `heartbeat_age_secs` derivation is unchanged. Since both `BotService.get_status()` (passthrough) and the SSE `"status"` frame (`web/sse_hub.py` broadcasts `get_status()` verbatim) consume this one shaped dict, the single fix closed both public surfaces atomically. Critical lockstep consumer `core/cli/status.py` was updated in the SAME task/commit to read `heartbeat_age_secs` instead of computing `now - rec['last_heartbeat']`, avoiding the CLI silently regressing to always showing "never"; the now-orphaned `now = time.monotonic()` and `import time` were removed. TDD: RED confirmed (3 failures at the exact expected fix sites: `test_snapshot_public_keys_exact`, `test_snapshot_excludes_last_heartbeat`, `test_status_table`) before the GREEN production fix landed (`585484c`). Task 2 (`2143edc`) fanned the change across the 5 last_heartbeat-touching test files plus a new SSE-frame absence test (`tests/test_sse.py::test_sse_status_frame_excludes_last_heartbeat`, mirroring the existing `test_sse_no_credential_patterns` credential-pattern pattern) proving both the REST and SSE surfaces are clean; `grep -rn "last_heartbeat" tests/` confirms every remaining reference is an absence-assertion, none assert presence on a public surface. Full suite: 939 passed, 2 skipped (baseline 937 + 2 net-new tests), no regression. No deviations -- plan executed exactly as written.) AF-02 marked complete in REQUIREMENTS.md. **Phase 35 is now 2/3 plans complete -- 35-03 (DH-01/02/03 frontmatter reconciliation) is the only plan left before Phase 35 (and the v4.2 milestone) closes.**

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

*Last updated: 2026-07-02 — v4.2 roadmap created (Phases 30-35, 20 requirements mapped)*

## Decisions

- [Phase ?]: Phase 25-01: CSS comment stripping in test_no_external_urls_in_static prevents false positives on dashboard.css header comment text
- [Phase ?]: Phase 25-01: test_no_innerHTML_with_api_data uses re.DOTALL to catch both XSS violations including the multiline cred.name case at line 255
- [Phase ?]: CSS token split
- [Phase ?]: escHtml unused stub
- [Phase ?]: A2 chunking resolved: join chunks[:8] for SSE frame assertions
- [Phase ?]: Phase 27-01: disconnect cleanup asserted via len(hub._queues)==0, not is_disconnected() (unreliable in TestClient)
- [Phase ?]: Phase 27-01: each SSE test opens its own TestClient context manager (no shared fixture); lifespan runs per-test
- [Phase ?]: TestClient compat
- [Phase ?]: TestClient compat: detect starlette _TestClientTransport via http.response.debug scope extension; limit SSE generator to _TEST_MAX_FRAMES=20 in test context
- [Phase ?]: _poll_loop poll_interval default changed to None; reads module var at runtime so test overrides of _POLL_INTERVAL_SECS take effect
- [Phase ?]: SseHub instantiated in create_app factory body; asyncio.create_task(_poll_loop) only in lifespan where event loop is live
- [Phase ?]: Phase 28-02: heartbeat_age_secs computed in get_snapshot() not at route boundary so Phase 29 SSE poll reads the field automatically
- [Phase ?]: Phase 28-02: select rule added to components.css to match input[type=text] styling for log level dropdown
- [Phase ?]: Phase 28-03: renderHealthCards and renderUptime are pure functions; MAX_LOG_LINES = 500 placed here so DOM cap test goes GREEN in wave 3
- [Phase ?]: Phase 29-01: test_no_onmessage_for_named_events is GREEN at Wave 0 (anti-pattern guard; .onmessage absent from template; stays green through all plans)
- [Phase 30-01]: place_order_attempted_at is a new dedicated TEXT column, not an overload of checkout_attempts or the CONFIRMED-<ts> sentinel (D-02)
- [Phase 30-01]: D-15 login-failure loop suppression implemented via the should_retry closure predicate (plugin._checkout_stage != login), not a new exception or hand-rolled loop -- lowest-risk mechanism, reuses existing telemetry
- [Phase 30-02]: WAF token injection via document.cookie tab.evaluate() (JS-eval), not CDP set_cookies — Plan permits either as best-effort per RESEARCH.md Assumption A1 (2captcha AmazonTask payload shape undocumented); JS-eval keeps the diff minimal with no new CDP imports
- [Phase 30-02]: No redundant can_solve() re-check inside the WAF branch — The existing top-of-function solver gate already covers D-08 solver-unavailable fallback before WAF detection runs, mirroring the solve_recaptcha branch
- [Phase 30-breakfix-hardening]: login() ABC default returns True (login-less plugin trivially logged in, D-14); every real plugin can now report a login failure — Enables the shared BF-03 verification mechanism without breaking existing no-op-login plugins
- [Phase 30-breakfix-hardening]: _verify_login_generic is the single shared BF-03 verification mechanism (D-11), no per-plugin duplication — url-off-signin AND form-absent -> True; any ambiguity or exception -> False (D-13)
- [Phase 30-breakfix-hardening]: relaunch() captures login_ok and logs ERROR on failure; no dispatcher plumbing added — relaunch() has never had orchestrator access; the D-15 operator alert already surfaces from the orchestrator's login_failed short-circuit (30-01) on the next monitoring cycle
- [Phase 30-breakfix-hardening]: BF-02 marker import (mark_place_order_attempted_sync) is inline inside auto_buy(), not top-level -- keeps the first plugin->models write edge narrow and localized — Matches RESEARCH.md Pattern 1's exact example; avoids widening the plugin/models coupling beyond the single call site
- [Phase 30-breakfix-hardening]: BestBuy parity marker write (Task 2) included rather than deferred — RESEARCH.md found the byte-identical swallowed-TimeoutError shape at bestbuy:389-396; the guard mechanism from 30-01 is platform-agnostic so closing the now-known symmetric exposure was low marginal cost
- [Phase 30-breakfix-hardening]: 5 community plugins use the generic _verify_login_generic signal only (D-12), no platform-specific override — selectors are unverified TODOs; selector tuning stays operator debt per D-12
- [Phase 30-breakfix-hardening]: D-15 implemented uniformly as abort-all-remaining-stages on failed login, not no-add-to-cart — all 5 community plugins call login() mid-flow after add-to-cart + checkout-proceed (Pitfall 3)
- [Phase 30-breakfix-hardening]: Amazon/BestBuy auto_buy sets _checkout_stage="login" and calls login() at their existing (unchanged) positions -- Amazon before DOM interaction, BestBuy mid-flow after add-to-cart/checkout-proceed -- with uniform abort-all-remaining-stages on False — D-15 implemented consistently across all 7 plugins regardless of where login() sits in each flow, matching the 30-06 community-plugin precedent
- [Phase 30-breakfix-hardening]: Amazon's tighter D-12 signal is absence of #ap_email (already the generic signal, since no live-verified account-landing selector exists); BestBuy's is redirect-off-/identity/signin (URL-only, honest available signal) — Neither plugin's post-login landing-page DOM is live-verified, so the URL-fragment-based generic check is the most honest signal available without inventing an unverified selector
- [Phase 30-breakfix-hardening]: 30-REVIEW.md (deep code review, 2026-07-02) found CR-01 (critical): the BF-02 place-order marker was written unconditionally by Amazon/BestBuy auto_buy() before place_order_guarded's test_mode/monitor_only suppression check, permanently latching items reached under the documented-default test_mode=true with no click ever fired, plus a false possibly_placed alert. Gap-closure (same day, TDD, 4 commits: ba16879/22ec887/861fc79/dbe1345) resolved CR-01 (marker write moved into place_order_guarded via order_marker_link kwarg), MED-02 (possibly_placed alert now fires once per latch via alerted_links, not every poll cycle), LOW-03 (added clear_place_order_marker_sync recovery accessor), LOW-01 (redundant asyncio.TimeoutError tuple removed). MED-01 (community-plugin marker write) and LOW-02 (_checkout_stage invariant) remain deferred, pre-declared debt. Full suite: 887 passed, 2 skipped (baseline 878 passed, 2 skipped).
- [Phase 31-01]: Suppressed the one gitleaks finding (tests/test_captcha.py:381 sentinel_key) with an inline #gitleaks:allow comment, not a .gitleaks.toml path exemption -- avoids silently suppressing a future real leak under tests/
- [Phase 31-01]: No local gitleaks binary run this session (not pre-installed); CI enforcement path (gitleaks-action@v3) is self-contained and does not need one -- workflow validated by YAML correctness + acceptance-criteria greps
- [Phase 31-02]: checkout@v6 + codeql-action@v4 used (not CONTEXT.md placeholder v4/v3) per live-verified research: current Node24 majors, not stale defaults
- [Phase 31-02]: Folded ci.yml checkout@v4->v6 and setup-python@v5->v6 into this plan (orchestrator-directed) to close the adjacent Node20 exposure alongside the CodeQL fix
- [Phase 31-02]: Autobuild step removed entirely rather than kept alongside build-mode -- Python is interpreted and autobuild is being phased out
- [Phase ?]: [Phase 31-03]: Exact-pin style (==) kept for cryptography/pydantic-settings/jinja2 bumps, matching requirements.txt convention (resolves research Open Question #2)
- [Phase ?]: [Phase 31-03]: cryptography bumped to latest 49.0.0 (not the minimum-patched 48.0.1 floor) -- removes the SECT-curve root-cause class outright; repo usage (Fernet/Scrypt only) has zero overlap with any deprecated/removed cipher surface
- [Phase ?]: [Phase 31-03]: jinja2 bump applied in pyproject.toml [web] extra, not requirements.txt, despite the alert's manifest_path saying requirements.txt -- jinja2 is not declared in requirements.txt at all (research Pitfall 5)
- [Phase 32-01]: Manifest-mode release-please with no extra-files entry; python release-type updates pyproject.toml natively
- [Phase 32-01]: release-please workflow permissions scoped to exactly contents:write + pull-requests:write; no actions:write/id-token:write
- [Phase 32-01]: Seeded .release-please-manifest.json at 2.0.0 = baseline only; release-please proposes the NEXT bump from commit history, does not re-tag 2.0.0
- [Phase ?]: [Phase 32-02]: Collapsed README master/dev two-block badge layout to a single master-branch badge row (CI, CodeQL, Gitleaks) plus a static python-3.11+ badge; no fabricated license badge (no LICENSE file exists)
- [Phase ?]: [Phase 32-02]: README Configuration section restructured to 3 explicit steps (non-secret config.yml edits vs .env credential setup) to align with SECURITY.md's env-var-only credential model
- [Phase 32]: [Phase 32-03]: No email address substituted for the placeholder under any circumstance (D-RH-07 locked) -- GitHub PVR (security/advisories/new) is the sole reporting channel for both vulnerability and conduct reports
- [Phase 32]: [Phase 32-03]: Operator note added inline in SECURITY.md (not just SUMMARY): Private Vulnerability Reporting must be enabled once in repo Settings -> Security -> 'Private vulnerability reporting' for the advisories/new link to resolve; not toggled by this automation
- [Phase 32]: [Phase 32-03]: .planning/ historical occurrences of the placeholder string (10 files) intentionally left untouched -- project's own decision audit trail, not live consumer-facing docs
- [Phase 33-01]: Option A (accepted): _get_plugin_sleep reads canonical delay_seconds/delay_jitter uniformly for all 7 platforms, activating Amazon/BestBuy poll-cadence jitter (30s flat -> 30-40s) for the first time -- recorded as an operator-UAT item
- [Phase 33-01]: Shim guard is has_legacy and not has_canonical -- explicit canonical delay_seconds/delay_jitter values are never clobbered by legacy min_delay/max_delay keys, even when both are present in the same construction
- [Phase 33-01]: No clamping of the derived delay_jitter in the legacy shim -- an inverted/negative legacy range flows into Field(ge=0.0) and raises ValidationError naturally, matching the fail-loudly convention
- [Phase ?]: [Phase 33-02]: extra="allow" added to PlatformsConfig (candidate a) -- undeclared platforms.<key> sections pass through as raw dicts; the 7 declared platform fields keep full strict validation unchanged
- [Phase ?]: [Phase 33-02]: RetailerPlugin.get_platform_config(model_cls) is the sanctioned mechanism for a new community plugin to declare+validate its own per-platform config section with zero core/config_schema.py edits
- [Phase ?]: [Phase 33-02]: Fixed the fixture test's AppConfig construction -- AppConfig(**kwargs) silently no-ops for platforms data since settings_customise_sources excludes init_settings from its source tuple; switched to yaml_file= injection matching the codebase's established test pattern
- [Phase 34-01]: ContextVar set in supervise() (not run_plugin) so restart/backoff/park logs are tagged; head=[LEVEL][plugin][ts] computed once for both print and file write — RESEARCH.md recommendation: writeLog is a custom print+file-append function, not a stdlib Logger, so a logging.Filter would not intercept lines without a full rewrite
- [Phase 34-03]: attempted denominator = place_order_attempted_at IS NOT NULL OR order_id IS NOT NULL, never checkout_attempts (which increments under test_mode and would deflate the rate)
- [Phase 34-03]: time_to_checkout scoped to place_order_attempted_at -> confirmed_at only; no earlier detection-timestamp anchor exists in the schema, so the metric is honestly scoped rather than invented
- [Phase 34-03]: link is read only inside BotService.get_analytics to resolve platform_key via registry domain_patterns; it never enters the compute_analytics output (T-34-06)
- [Phase 34-02]: Kept generic lowercase-alphanumeric plugin-param whitelist regex over an enum check against list_plugins() -- avoids a to_thread-wrapped filesystem+importlib PluginRegistry scan on the hot-polled /api/logs endpoint
- [Phase 34-02]: SSE 'log' listener gains a client-side lineMatchesFilters() guard before appendLogLine so live-tailed lines respect the active level/search/plugin filters, not just the one-shot pollLogs snapshot
- [Phase 35]: 35-01: POST /items/remove lives on web/routes/pages.py (unprefixed router) not api.py, since HTML forms cannot target DELETE and a form-target route belongs beside the SSR / route
- [Phase 35]: 35-01: 303 See Other used for the remove redirect (POST/Redirect/GET), guaranteeing a GET on redirect
- [Phase 35]: 35-02: core/cli/status.py lockstep fix landed in the same task/commit as the health.py get_snapshot() filter, avoiding a silent CLI 'always never' regression
- [Phase 35]: 35-02: single shaping boundary (HealthRegistry.get_snapshot) filters last_heartbeat once; both get_status() REST and the SSE status frame inherit the fix atomically since SSE broadcasts get_status() verbatim

## Operator Next Steps

- Continue `/gsd:execute-phase 35` (Audit-Fixes & Doc-Hygiene Cleanup) -- the milestone's final phase; plans 35-01 (AF-01 + AF-03) and 35-02 (AF-02) complete, 35-03 remains
