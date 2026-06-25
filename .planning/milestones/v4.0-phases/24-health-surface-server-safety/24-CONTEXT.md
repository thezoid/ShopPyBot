# Phase 24: Health Surface + Server Safety - Context

**Gathered:** 2026-06-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Operators can query per-plugin liveness and error state from the CLI or web UI, receive alerts when a plugin degrades, and run the bot headlessly on a server without a pygame import crash (REL-07, SRV-01). This is the final v4.0 phase.

Deliverables:
1. `core/health.py` `HealthRegistry` (per-plugin status, last_heartbeat, consecutive_errors, items_checked, orders_confirmed), updated by run_plugin + supervise + the confirmation path.
2. Expanded `BotService.get_status()` returning the structured health surface; surfaced via `shoppybot status` (new CLI) and the existing FastAPI `/status` endpoint.
3. A `health_degraded` notification dispatched through the existing fan-out when a plugin's `consecutive_errors` exceeds `alert_on_errors`.
4. A headless pygame import-crash guard in `utils.py` (silent no-op audio when no device).

Out of scope: nothing downstream (last phase). A web-dashboard health-panel redesign is out of scope (the `/status` JSON endpoint serves the data).
</domain>

<decisions>
## Implementation Decisions

### HealthRegistry & Data Model
- `core/health.py` `HealthRegistry`: a per-plugin record with `status`, `last_heartbeat`, `consecutive_errors`, `items_checked`, `orders_confirmed`. Updated by `run_plugin` (heartbeat + items_checked per cycle), `supervise` (consecutive_errors, status transitions: park/relaunch/degraded), and the confirmation path (orders_confirmed).
- `get_status()` returns `{"running": bool, "uptime_secs": float, "plugins": {name: {"status": str, "last_heartbeat": float, "consecutive_errors": int, "items_checked": int, "orders_confirmed": int}}}` (roadmap criterion 1 exact shape).
- `status` enum values: `running` | `degraded` | `parked` | `relaunching` | `idle`.
- A single `HealthRegistry` instance is created in `async_main` and passed to `supervise`/`run_plugin`; `BotService` holds a reference so `get_status()` can read it.

### health_degraded Alerting
- `health_degraded` fires when a plugin's `consecutive_errors` exceeds `CheckoutConfig.alert_on_errors` (the same sustained-degradation threshold as the Phase 22 park failure budget).
- Dedup: fire ONCE on crossing the threshold (armed/disarmed, mirroring the stock/price-alert dedup pattern) — never every cycle (no alert spam).
- This is distinct from the Phase 22 `plugin parked` notification: `health_degraded` signals sustained degradation BEFORE park; `parked` fires at park.
- A new `health_degraded` notification_type is dispatched through the existing notification fan-out (sound/discord/email/sms per config), reusing the NotificationEvent structure.

### CLI status, Web Surface & pygame Guard
- New `shoppybot status` CLI subcommand: prints a per-plugin table from `get_status()` (running, uptime, status/heartbeat/consecutive_errors/items_checked/orders_confirmed); `--json` flag for raw output; no network call.
- The existing FastAPI `/status` endpoint (`web/routes/api.py:24`) already returns `get_status()` — the richer dict flows through with NO endpoint change. A web-dashboard health panel is deferred (optional, out of scope).
- SRV-01 pygame guard: wrap the import-time `pygame.mixer.init()` in `utils.py` (line ~38) in try/except → set a module flag `_AUDIO_AVAILABLE = False` on failure → the play functions become silent no-ops when audio is unavailable; log a one-time INFO. The bot imports and runs without an audio device.
- `running`/`uptime_secs`: `BotService` records a start timestamp when `run()` begins; `uptime_secs = now - start`; `running` reflects the service state.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `core/service.py` — `BotService.get_status()` (line ~68) to EXPAND; add a start-time field set in `run()`. Holds the HealthRegistry reference.
- `core/orchestrator.py` — `run_plugin` (heartbeat + items_checked per poll cycle), `supervise` (P22 — consecutive_errors/status transitions; the health-degraded check goes alongside the failure-budget deque), `async_main` (creates HealthRegistry, passes it down), the confirmation enqueue path (orders_confirmed on a confirmed order). `alert_on_errors` from CheckoutConfig.
- `web/routes/api.py` — `/status` endpoint (line 24) returns `svc.get_status()`; no change needed (richer dict flows through).
- `core/cli/__init__.py` — subparser registration; add a `status` subcommand (analog: the `plugins list` command from v3.0, or `items` — a read-only CLI handler with --json).
- `utils.py` — `import pygame` (line 1), `initialize_pygame()` (line 8, `pygame.mixer.init()`), called at import time (line 38). Wrap for SRV-01.
- Notification dispatcher + `NotificationEvent` — reused for `health_degraded` (mirror the price_drop/stock notification_type + dedup pattern from v3.0).

### Established Patterns
- Structured dict from `get_status()`; FastAPI JSONResponse; CLI read-only handlers with `--json` (plugins list precedent).
- Armed/disarmed dedup for notifications (stock/price alerts) — the health_degraded dedup mirrors it.
- Additive, getattr-safe config reads; one-time INFO logs; degrade-not-crash.
- Notification fan-out via the dispatcher with a distinct notification_type.

### Integration Points
- `core/health.py` (NEW — HealthRegistry).
- `core/service.py` (get_status expansion + start time + registry ref).
- `core/orchestrator.py` (run_plugin heartbeat/items_checked; supervise status + health_degraded dispatch; async_main wiring; orders_confirmed).
- `core/cli/__init__.py` + a status handler (new `status` subcommand).
- `utils.py` (pygame headless guard).
- Notification dispatcher (health_degraded event).

</code_context>

<specifics>
## Specific Ideas

- The HealthRegistry is the read-side complement to Phase 22's supervisor: P22 tracks failures for restart/park decisions; P24 exposes that state (plus heartbeat/throughput counters) for operators. Reuse the supervisor's consecutive-failure tracking as the consecutive_errors source where possible.
- `health_degraded` dedup must be per-plugin armed/disarmed so a flapping plugin doesn't spam; re-arm when the plugin recovers (consecutive_errors drops back below threshold).
- SRV-01 is self-contained (pygame guard in utils.py) and low-risk; it can be a standalone plan.
- The web `/status` endpoint already exists — the only web-side requirement is that the richer get_status() dict serializes cleanly to JSON (floats, ints, strings, nested dict — all JSON-safe).

</specifics>

<deferred>
## Deferred Ideas

- Web-dashboard health panel / visual redesign → future (the `/status` JSON endpoint serves the data; no visual page in v4.0 scope).
- Historical health metrics / time-series → future (the registry is current-state only).
- Live headless-server run verification (pygame no-op on a real no-audio host; SIGTERM on the deploy OS) → UAT debt (tracked, not blocking).

</deferred>
