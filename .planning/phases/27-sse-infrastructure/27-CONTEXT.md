# Phase 27: SSE Infrastructure - Context

**Gathered:** 2026-06-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Build a single `/api/events` Server-Sent Events endpoint that delivers live `status`
and `log` events to browser clients over a clean cross-thread bridge, validated in
complete isolation before any browser/Phase-29 involvement. Backend/web-layer only;
no browser-side EventSource wiring (Phase 29). Covers SSE-02. Highest-risk phase —
the cross-thread bridge is the central hazard.

</domain>

<decisions>
## Implementation Decisions

### SSE Bridge Architecture
- Single `_poll_loop` background task running on **uvicorn's** event loop calls
  `asyncio.to_thread(svc.get_status)` ~every 1s and broadcasts to per-client
  `asyncio.Queue`s. The **bot daemon thread NEVER touches the queues** (asyncio.Queue
  is not thread-safe) — uvicorn's `_poll_loop` is the sole SSE producer (research invariant).
- New `web/sse_hub.py` `SseHub`: holds a set of per-client `asyncio.Queue`s; methods
  `subscribe()` / `unsubscribe()` / `broadcast(payload)`.
- Add a FastAPI `lifespan` to `create_app`: build the `SseHub`, start the `_poll_loop`
  task on startup, cancel + await it on shutdown; store the hub on `app.state.sse_hub`.
- `_poll_loop` also tails NEW log lines via a new cursor-based `tail_log_lines(after_line)`
  (research Pitfall 6 — never full-file re-read per tick) and broadcasts `log` events.

### Event Format & Protocol
- Named SSE events: `event: status\ndata: {json}\n\n` and `event: log\ndata: {json}\n\n`
  (clean client dispatch in Phase 29).
- Keepalive: emit `: keep-alive\n\n` comment every ~15s during idle, via `asyncio.wait_for`
  timeout on `queue.get()`.
- Emit `retry: 3000\n\n` once on stream open (browser waits 3s before reconnecting).
- Status pushed every ~1s tick (criterion 1: "data frame approximately every second").

### Disconnect & Resource Safety
- Detect client disconnect with `await request.is_disconnected()` in the generator loop →
  break → `finally: hub.unsubscribe(queue)`. Guarantee unsubscribe even on CancelledError.
- No queue leak after disconnect (criterion 2).
- Bounded `asyncio.Queue(maxsize=100)` per client, drop-oldest when full (slow-client
  memory safety).
- `_poll_loop` catches + logs exceptions from `get_status()`/log tail and continues — a
  single error never kills the loop or the stream.

### Validation (spike-in-isolation) & Secrets
- Realize the recommended "spike" as a Wave-0 TestClient **isolation test**: assert the
  `retry:` line on open, a `data:` status frame arrives, the keepalive comment, and that a
  client disconnect leaves `SseHub` with zero queues. This validates the bridge before any
  Phase 29 browser wiring (satisfies "validated in complete isolation").
- Make the poll interval + keepalive timeout **injectable** (constructor args / constants)
  so tests run fast (~0.05s) without real 1s/15s waits.
- Test transport: pytest + TestClient streaming reads against `/api/events`.
- Add a credential-pattern assertion on an actual `/api/events` data frame (extends the
  SSE-03 scrub guard to the live stream); status frames already flow through the scrubbed
  `get_status()` (Phase 26 `last_error`).

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `web/__init__.py` `create_app(svc, is_non_local=False)` — currently has NO lifespan;
  builds FastAPI, mounts /static, includes routers. Add the lifespan here; store
  `app.state.sse_hub`.
- `core/service.py` `BotService.get_status()` — in-memory health surface (running,
  uptime_secs, plugins snapshot) — the status payload source; `last_error` already scrubbed
  (Phase 26).
- `web/log_reader.py` — `_read_today_lines()` / `read_recent_logs()` / `read_logs_filtered()`.
  Add the cursor-based `tail_log_lines(after_line)` here (midnight-rollover aware).
- `web/routes/api.py` — async handler + `asyncio.to_thread` patterns established (Phase 26).

### Established Patterns
- Routes via `web/routes/*.py` routers, included with `/api` prefix in create_app.
- Sync reads off the event loop via `asyncio.to_thread`.
- get_status() last_error scrubbed to `exc.__class__.__name__` (Phase 26 / SSE-03).

### Integration Points
- New `web/routes/sse.py` — `GET /api/events` `StreamingResponse(media_type="text/event-stream")`.
- New `web/sse_hub.py` — `SseHub`.
- `web/__init__.py` — lifespan to start/stop `_poll_loop`; include the sse router.
- `web/log_reader.py` — `tail_log_lines` cursor.

### Constraints
- Stack unchanged: raw `StreamingResponse` from starlette (no `sse-starlette`, no FastAPI
  upgrade). No new Python packages.
- TestClient enters/exits lifespan — the poll loop must start/stop cleanly under TestClient.

</code_context>

<specifics>
## Specific Ideas

- Research SUMMARY (.planning/research/SUMMARY.md) Phase C is authoritative for the bridge
  design and the seven SSE pitfalls (cross-loop race, generator leak, loop blocking,
  reconnect backoff, unbounded log read, secrets in stream, missing keepalive).
- Phase 29 will replace the dashboard's 2s polling with `EventSource('/api/events')`; build
  the named-event contract now so Phase 29 just dispatches on `event:` type.

</specifics>

<deferred>
## Deferred Ideas

- Browser-side `EventSource` wiring, polling fallback, "Live/Reconnecting" indicator — Phase 29.
- Real-time SSE for price charts — out of scope (price scrapes are sparse; REST suffices).
- FastAPI 0.135 native `EventSourceResponse` — future dep-refresh milestone.

</deferred>
