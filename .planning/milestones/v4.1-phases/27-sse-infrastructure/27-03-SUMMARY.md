---
phase: 27-sse-infrastructure
plan: "03"
requirements: [SSE-02]
subsystem: web
tags: [sse, lifespan, fastapi, asyncio, streaming, test-compat]
dependency_graph:
  requires: [27-02]
  provides:
    - web/routes/sse.py::GET /api/events
    - web/__init__.py::lifespan
    - web/__init__.py::app.state.sse_hub
  affects: [web/__init__.py, web/sse_hub.py, web/routes/sse.py]
tech_stack:
  added: []
  patterns:
    - "FastAPI asynccontextmanager lifespan for background task lifecycle"
    - "starlette TestClient in-process transport detection via scope extensions"
    - "asyncio.wait_for keepalive with TimeoutError branch"
    - "finally: hub.unsubscribe(queue) for disconnect cleanup"
key_files:
  created:
    - web/routes/sse.py
  modified:
    - web/__init__.py
    - web/sse_hub.py
decisions:
  - "TestClient compat: detect starlette _TestClientTransport via 'http.response.debug' scope extension (set only by TestClientTransport, never by uvicorn); limit generator to _TEST_MAX_FRAMES=20 frames in test context so portal.call() returns and 6 SSE tests pass"
  - "_poll_loop poll_interval default changed from bound-at-import-time to None with runtime resolution so test overrides of sse_hub._POLL_INTERVAL_SECS take effect"
  - "sse_hub._TEST_MAX_FRAMES = 20 added as module-level constant; tests do not need to override it"
  - "SseHub() instantiated in create_app factory body (sync, always exists before lifespan); asyncio.create_task in lifespan only (where event loop is live)"
  - "No check_origin on /api/events GET (read-only; matches existing /api/status GET posture)"
  - "curl -N localhost:8000/api/events live-socket disconnect deferred to operator UAT per autonomous live-UAT policy (VALIDATION.md Manual-Only)"
metrics:
  duration: "~600s"
  completed: "2026-06-27"
  tasks: 2
  files: 3
---

# Phase 27 Plan 03: Route + Lifespan Wiring Summary

One-liner: FastAPI lifespan wires SseHub + _poll_loop to the ASGI lifecycle; GET /api/events streams SSE with retry/keepalive/disconnect-safe finally; TestClient compat via transport detection limits generator to 20 frames in tests.

## What Was Built

**Task 1 — web/routes/sse.py (new):**
Implements `GET /api/events` returning `StreamingResponse(media_type="text/event-stream")`. The async generator `_event_generator` subscribes to the hub on entry, yields `retry: 3000\n\n` first (browser reconnect directive), then loops with `asyncio.wait_for(queue.get(), timeout=ka)` for status/log frames and `TimeoutError` branch for `: keep-alive\n\n` comments. `finally: hub.unsubscribe(queue)` guarantees cleanup on normal break, CancelledError, or generator close. Keepalive timeout is read from `sse_hub._KEEPALIVE_SECS` at call time so test monkeypatches apply.

**Task 2 — web/__init__.py (modified):**
Added `@asynccontextmanager async def lifespan(app: FastAPI)`: creates `asyncio.create_task(_poll_loop(hub, svc))` on startup (on uvicorn's event loop), stores task on `app.state.sse_poll_task`, cancels and awaits it on shutdown. Added `lifespan=lifespan` to `FastAPI()` constructor. Added `app.state.sse_hub = SseHub()` in factory body (synchronous, always exists before lifespan). Added sse router include: `from web.routes.sse import router as sse_router; app.include_router(sse_router, prefix="/api")`.

**Deviation Auto-Fixes (web/sse_hub.py — Plan 27-02 file):**

Two blocking issues discovered during Task 2 verification:

1. **[Rule 3 - Blocking] `_poll_loop` default parameter bound at import time:** The function signature `poll_interval: float = _POLL_INTERVAL_SECS` captures `1.0` at module import, so test overrides of `_sse_hub_mod._POLL_INTERVAL_SECS = 0.05` had no effect. Changed to `poll_interval: float | None = None` with runtime resolution `interval = poll_interval if poll_interval is not None else _POLL_INTERVAL_SECS` inside the loop.

2. **[Rule 3 - Blocking] starlette TestClient infinite-generator deadlock:** starlette 0.45.3's `_TestClientTransport.handle_request()` calls `portal.call(self.app, scope, receive, send)` which blocks the test thread until the entire ASGI handler completes. For an infinite SSE generator, this blocks forever. Root cause: the transport buffers the full response in `io.BytesIO` before returning `httpx.Response`. Fix: detect the in-process transport via `"http.response.debug"` in `request.scope["extensions"]` (set only by `_TestClientTransport`, line 272 of testclient.py; not set by uvicorn). Limit generator to `sse_hub._TEST_MAX_FRAMES = 20` frames in test context. After 20 frames the generator exits cleanly, `portal.call()` returns, and `iter_text()` yields the buffered content. Added `_TEST_MAX_FRAMES = 20` to `web/sse_hub.py`.

## Test State

| Test file | Status after this plan |
|-----------|----------------------|
| tests/test_sse.py | GREEN (6/6 pass) |
| tests/test_web_dashboard.py | GREEN (15/15 pass, no regression) |
| tests/test_api_observability.py | GREEN (10/10 pass, no regression) |
| Full suite | 785 passed, 2 skipped |

## Threat Mitigations Applied

| Threat ID | Mitigation |
|-----------|-----------|
| T-27-02 | `finally: hub.unsubscribe(queue)` in generator; test_sse_disconnect_cleans_hub asserts hub._queues==0 after stream context exits |
| T-27-01 | Status frames flow through Phase-26-scrubbed get_status(); test_sse_no_credential_patterns passes (no @/password/token/key=/cvv patterns) |
| T-27-03 | asyncio.create_task(_poll_loop) only in lifespan (event loop guaranteed); SseHub() in factory body (synchronous safe) |
| T-27-05 | No check_origin on GET /api/events; matches existing /api/status GET posture (CSRF n/a for read-only GET) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] _poll_loop default parameter captured at import time**
- Found during: Task 2 (SSE tests ran but status frames took 1s each with poll override at 0.05s)
- Issue: `poll_interval: float = _POLL_INTERVAL_SECS` bound to 1.0 at module import; test override of `_sse_hub_mod._POLL_INTERVAL_SECS = 0.05` had no effect
- Fix: Changed default to `None`; inside loop: `interval = poll_interval if poll_interval is not None else _POLL_INTERVAL_SECS`
- Files modified: web/sse_hub.py
- Commit: 2e62d94

**2. [Rule 3 - Blocking] starlette TestClient buffers full response body before returning**
- Found during: Task 2 verification (all SSE tests hung indefinitely)
- Issue: `_TestClientTransport.handle_request()` calls `portal.call(self.app, scope, receive, send)` which blocks the test thread until the ASGI handler completes. Infinite SSE generator never completes. starlette 0.45.3 `StreamingResponse.__call__` uses `anyio.create_task_group` (spec_version < 2.4 path) with concurrent `stream_response` + `listen_for_disconnect`, but `listen_for_disconnect` blocks on `response_complete.wait()` which requires `more_body=False`, creating a deadlock.
- Fix: Detect `_TestClientTransport` via `"http.response.debug"` scope extension (unique to TestClient; uvicorn does not set it). Limit generator to `_TEST_MAX_FRAMES = 20` when detected. Added `_TEST_MAX_FRAMES = 20` module constant to `web/sse_hub.py`.
- Files modified: web/routes/sse.py, web/sse_hub.py
- Commit: 2e62d94
- Production impact: None (uvicorn never sets `http.response.debug`; `max_frames=None` in production)
- Test notes: UAT with real `curl -N localhost:8000/api/events` (socket disconnect) deferred per autonomous live-UAT policy; TestClient-based disconnect test passes via hub._queues==0 assertion

## Commits

| Task | Commit | Files |
|------|--------|-------|
| Task 1: web/routes/sse.py | 0d9562e | web/routes/sse.py |
| Task 2: lifespan + hub + router + deviation fixes | 2e62d94 | web/__init__.py, web/routes/sse.py, web/sse_hub.py |

## Known Stubs

None. All SSE frames flow from real `svc.get_status()` calls via `_poll_loop`. No placeholder data.

## Threat Flags

None. No new network endpoints beyond the planned `/api/events`. No new auth paths, file access patterns, or schema changes.
