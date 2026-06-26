# Phase 26: Read-Only API Endpoints - Context

**Gathered:** 2026-06-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Expose all observability data the frontend needs as curl-testable, read-only HTTP
endpoints; wrap every sync DB/file read in `asyncio.to_thread` so uvicorn's event
loop never blocks; and establish the secret-leak invariant (scrub error surfaces to
exception class name) with a CI assertion. Backend/web-layer only; no frontend
rendering (Phase 28) and no SSE (Phases 27/29). Covers OBS-08 and SSE-03.

</domain>

<decisions>
## Implementation Decisions

### Endpoint Contracts & Shapes
- `GET /api/history` returns `{"confirmed_orders": [{name, order_id, confirmed_at,
  checkout_attempts}]}`; empty list when no confirmed orders exist.
- `GET /api/price-history/{link_b64}` returns `{"series": [{"t": <iso>, "price": <float>}]}`;
  returns `{"series": []}` for non-Amazon items / items with no price data.
- Invalid or garbage `link_b64` returns `{"series": []}` gracefully (no error) — criterion
  2 requires the call to complete without error in both cases.
- `confirmed_at` is passed through from the DB as an ISO-8601 string.

### Log Filtering (OBS-08)
- `GET /api/logs` supports `level` (exact `[LEVEL]` prefix match), `search`
  (case-insensitive substring), and `n`; filters are AND-combined.
- Plugin filter is DEFERRED: log lines are formatted `[TYPE][timestamp] message`
  (logger.py) with no `[PLUGIN_NAME]` tag, so a plugin filter is not verifiable — per
  OBS-08's own contingency. Document the deferral; do not modify logger.py to add tags.
- `search` is case-insensitive substring matching.
- With no query params, `GET /api/logs` degrades to the existing `read_recent_logs(50)`
  behavior unchanged (criterion 3).

### Secret Scrubbing & CI Guard (SSE-03)
- Add a scrubbed `last_error` field to the per-plugin health snapshot containing only
  `exc.__class__.__name__` (never `str(exc)`) — forward-prep for the Phase 28 status badge.
  Note: `core/health.py` has no `last_error` field today; this adds it scrubbed-by-construction.
- Scrub at the boundary where the exception is recorded (orchestrator/health registry) —
  `str(exc)` must never enter the snapshot.
- CI assertion: `/api/status` JSON and a representative `get_status()` payload contain no
  credential-pattern strings (regexes for `@`, `password`, `token`, `key=`, `cvv`,
  case-insensitive).
- Do NOT scrub `/api/logs` response content — those are the operator's own log files and
  scrubbing would corrupt them. The credential guard targets status/SSE JSON only.

### Async Safety & Endpoint Conventions
- Wrap every sync DB/file read (`/api/history`, `/api/price-history`, log reads) in
  `asyncio.to_thread` so the event loop is never blocked.
- Leave `get_status()` called directly — it is in-memory and cheap by contract (REL-07);
  wrap only DB/file I/O.
- New read-only GET endpoints do NOT use `check_origin` — consistent with the existing
  GET `/api/status` and `/api/logs`; the CSRF origin gate is reserved for mutations.
- On 5xx, return a generic message with no exception detail (ties to the scrubbing
  invariant); bad price-history input degrades to an empty series rather than erroring.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `web/routes/api.py` — existing endpoints (`get_status`, `get_logs`, `bot_start`,
  `bot_stop`, `list_items`, `add_item`, `remove_item`). Mutations use
  `dependencies=[Depends(check_origin)]`; GET reads do not. `remove_item` shows the
  `base64.urlsafe_b64decode(link_b64.encode())` pattern (with `=` padding kept) for
  decoding link path params.
- `web/log_reader.py` (21 lines) — `read_recent_logs(n=50)` reads today's log file
  (`%Y%B%d.log`), returns `splitlines()[-n:]`, `[]` if missing. Extend here for filtering.
- `core/service.py` `get_status()` — returns `{running, uptime_secs, plugins}` where
  `plugins` = `HealthRegistry.get_snapshot()`.
- `core/health.py` `HealthRegistry` — per-plugin dict: `last_heartbeat`,
  `consecutive_errors`, `items_checked`, `orders_confirmed`. Add scrubbed `last_error` here.
- `models.py` — items table carries `order_id`, `confirmed_at`, `checkout_attempts`
  (v4.0 BUY-04); `price_history` table populated by the Amazon plugin. No schema changes.
- `logger.py` `writeLog(message, type)` — line format `[{TYPE}][{Y%B%d@H:M:S}] {message}`.

### Established Patterns
- Routes return `JSONResponse`; async handlers take `request: Request`; service accessed
  via `request.app.state.svc`.
- DB access via `models.py` functions (sync SQLite).

### Integration Points
- Add `GET /api/history` and `GET /api/price-history/{link_b64}` to `web/routes/api.py`.
- Add query-param filtering to existing `GET /api/logs` + `read_logs_filtered()` in
  `web/log_reader.py`.
- Add `last_error` (scrubbed) to `core/health.py` snapshot + record site in orchestrator.

</code_context>

<specifics>
## Specific Ideas

- Research SUMMARY (.planning/research/SUMMARY.md): Phase B uses `asyncio.to_thread` for
  all sync reads; no new packages. The cross-thread/SSE work is Phase 27 — keep this phase
  purely request/response, curl-testable in isolation.
- Verification is curl-driven: each criterion maps to a `curl` invocation that must succeed.

</specifics>

<deferred>
## Deferred Ideas

- Log plugin filter — requires `[PLUGIN_NAME]` tagging that the current log format lacks
  (OBS-08 contingency). Revisit only if logger format changes.
- SSE streaming of these reads — Phase 27 (`/api/events`).
- Price capture for non-Amazon plugins (PRC-01) — future milestone.

</deferred>
