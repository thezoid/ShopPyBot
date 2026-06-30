# Phase 27: SSE Infrastructure - Research

**Researched:** 2026-06-27
**Domain:** FastAPI lifespan + raw StreamingResponse SSE + cross-thread asyncio bridge
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**SSE Bridge Architecture:**
- Single `_poll_loop` background task running on uvicorn's event loop calls
  `asyncio.to_thread(svc.get_status)` ~every 1s and broadcasts to per-client
  `asyncio.Queue`s. The bot daemon thread NEVER touches the queues (asyncio.Queue
  is not thread-safe) -- uvicorn's `_poll_loop` is the sole SSE producer.
- New `web/sse_hub.py` `SseHub`: holds a set of per-client `asyncio.Queue`s; methods
  `subscribe()` / `unsubscribe()` / `broadcast(payload)`.
- Add a FastAPI `lifespan` to `create_app`: build the `SseHub`, start the `_poll_loop`
  task on startup, cancel + await it on shutdown; store the hub on `app.state.sse_hub`.
- `_poll_loop` also tails NEW log lines via a new cursor-based `tail_log_lines(after_line)`
  in `web/log_reader.py` and broadcasts `log` events.

**Event Format & Protocol:**
- Named SSE events: `event: status\ndata: {json}\n\n` and `event: log\ndata: {json}\n\n`.
- Keepalive: emit `: keep-alive\n\n` comment every ~15s during idle, via
  `asyncio.wait_for` timeout on `queue.get()`.
- Emit `retry: 3000\n\n` once on stream open.
- Status pushed every ~1s tick.

**Disconnect & Resource Safety:**
- Detect client disconnect with `await request.is_disconnected()` in the generator loop,
  break, `finally: hub.unsubscribe(queue)`. Guarantee unsubscribe even on CancelledError.
- Bounded `asyncio.Queue(maxsize=100)` per client, drop-oldest when full.
- `_poll_loop` catches + logs exceptions from `get_status()`/log tail and continues.

**Validation & Secrets:**
- Wave-0 TestClient isolation test: assert `retry:` line on open, a `data:` status frame
  arrives, the keepalive comment, and that a client disconnect leaves `SseHub` with zero
  queues. Make poll interval + keepalive timeout injectable (constructor args / constants).
- Test transport: pytest + TestClient streaming reads against `/api/events`.
- Credential-pattern assertion on live SSE frames.

**Stack:**
- fastapi==0.115.8 + starlette (transitive) + uvicorn[standard]==0.30.6.
- NO new packages. Raw `StreamingResponse`, NOT `sse-starlette`, NOT FastAPI upgrade.

### Claude's Discretion

None specified -- all architecture locked.

### Deferred Ideas (OUT OF SCOPE)

- Browser-side `EventSource` wiring, polling fallback, "Live/Reconnecting" indicator -- Phase 29.
- Real-time SSE for price charts -- out of scope.
- FastAPI 0.135 native `EventSourceResponse` -- future dep-refresh milestone.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SSE-02 | SSE stream handles client disconnect/reconnect cleanly: keepalive heartbeat, automatic client reconnect (`retry:` directive), server-side generator cleanup on disconnect, falls back to polling when SSE unavailable. | Covered by: lifespan wiring (startup/shutdown), SseHub subscribe/unsubscribe, `request.is_disconnected()` polling, `asyncio.wait_for` keepalive, `retry: 3000` on open. Browser fallback is Phase 29 concern; Phase 27 delivers the server-side half. |
</phase_requirements>

## Summary

Phase 27 builds the server-side SSE infrastructure for ShopPyBot in complete isolation
from any browser involvement. The central deliverable is a correct cross-thread bridge:
uvicorn's `_poll_loop` background task (running on uvicorn's asyncio event loop) is the
sole SSE producer, polling `svc.get_status()` via `asyncio.to_thread` every ~1s and
broadcasting to per-client `asyncio.Queue` objects. The BotService daemon thread that
runs `async_main` on its own private event loop never touches these queues.

The stack is fully verified: `fastapi==0.115.8` is installed as the `web` optional
dependency in `pyproject.toml`. Its `lifespan=` parameter takes an `@asynccontextmanager`
function -- the correct API for this version. `starlette.responses.StreamingResponse`
with `media_type="text/event-stream"` and an async generator is already available as a
transitive dependency; no new packages are needed. `TestClient` enters the lifespan only
when used as a context manager (`with TestClient(app) as client:`), which is the required
test pattern.

`get_status()` in `core/service.py` is confirmed cheap and non-blocking: it reads only
in-memory attributes (`_running`, `_start_time`, `_health_registry.get_snapshot()`). The
`asyncio.to_thread` wrapper in `_poll_loop` is a correctness requirement (BotService
is not async-native) but not a performance bottleneck. `tail_log_lines(after_line)` is
a new cursor function to add to `web/log_reader.py`; the midnight-rollover edge case
requires explicit handling.

**Primary recommendation:** Follow the locked architecture exactly. The only design
decisions left to the planner are (1) where to define the poll-interval and keepalive
constants that tests override, and (2) the exact drop-oldest strategy for bounded queues.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| SSE frame production | API / Backend (uvicorn loop) | -- | `_poll_loop` task runs on uvicorn's event loop; produces all frames |
| Bot status reads | API / Backend (thread pool) | -- | `get_status()` is sync; crosses thread boundary via `asyncio.to_thread` |
| Log tail reads | API / Backend (thread pool) | -- | `tail_log_lines()` is sync file I/O; must not block the event loop |
| Per-client queue fanout | API / Backend (uvicorn loop) | -- | `SseHub.broadcast()` called only from `_poll_loop` on uvicorn's loop |
| SSE frame delivery | API / Backend (uvicorn loop) | -- | Async generator in `web/routes/sse.py` runs on uvicorn's loop |
| Client disconnect detection | API / Backend (uvicorn loop) | -- | `await request.is_disconnected()` is an awaitable; uvicorn's loop |
| Bot lifecycle (start/stop) | Background Thread | -- | `BotService` daemon thread owns a completely separate asyncio event loop |

## Standard Stack

### Core (all already installed, no new deps)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | 0.115.8 | ASGI app factory, lifespan, routing | Installed as `web` optional dep in pyproject.toml [VERIFIED: pyproject.toml] |
| starlette | transitive of fastapi | `StreamingResponse`, `Request.is_disconnected()` | No separate install needed; `from starlette.responses import StreamingResponse` already used in codebase [VERIFIED: pyproject.toml] |
| uvicorn[standard] | 0.30.6 | ASGI server; single event loop where `_poll_loop` runs | Installed as `web` optional dep in pyproject.toml [VERIFIED: pyproject.toml] |

### No new packages

The `sse-starlette` package is explicitly forbidden. All SSE mechanics are covered by
raw `starlette.responses.StreamingResponse` with an async generator.

## Package Legitimacy Audit

No new packages are installed in this phase. The existing `fastapi==0.115.8`,
`starlette` (transitive), and `uvicorn[standard]==0.30.6` were verified present in
`pyproject.toml [project.optional-dependencies] web`.

**Packages removed due to slopcheck verdict:** none (no new packages)
**Packages flagged as suspicious:** none

## Architecture Patterns

### System Architecture Diagram

```
[Browser / curl]
      |
      | HTTP GET /api/events
      v
[uvicorn event loop]
      |
      |-- StreamingResponse (async generator in web/routes/sse.py)
      |       |
      |       |-- retry: 3000 (once, on open)
      |       |
      |       |-- loop:
      |       |     await asyncio.wait_for(queue.get(), timeout=15s)
      |       |       timeout -> yield ": keep-alive\n\n"
      |       |       got item -> yield "event: status\ndata: ...\n\n"
      |       |                      or "event: log\ndata: ...\n\n"
      |       |
      |       |-- await request.is_disconnected() -> break
      |       |-- finally: hub.unsubscribe(queue)
      |
      |-- _poll_loop (asyncio.Task, created in lifespan startup)
              |
              | every ~1s:
              |   status = await asyncio.to_thread(svc.get_status)
              |   new_lines = await asyncio.to_thread(tail_log_lines, cursor)
              |   hub.broadcast(status_payload)
              |   hub.broadcast(log_payload) for each new line
              |
              +-- [thread pool worker]
                    svc.get_status()    <- reads _running, _start_time, _health_registry
                    tail_log_lines()    <- reads log file from cursor position

[BotService daemon thread] (SEPARATE asyncio event loop -- NEVER touches SseHub or asyncio.Queue)
      |
      |-- async_main() -> plugin poll loops -> health.heartbeat() -> health.record_*()
      |
      v
[HealthRegistry] (in-memory, written by bot thread, read by get_status() via to_thread)
```

### Recommended Project Structure

```
web/
├── __init__.py          # create_app: add lifespan=, app.state.sse_hub; include sse router
├── sse_hub.py           # NEW: SseHub class + _poll_loop coroutine
├── log_reader.py        # ADD: tail_log_lines(after_line) cursor function
└── routes/
    ├── api.py           # unchanged (asyncio.to_thread patterns established)
    └── sse.py           # NEW: GET /api/events StreamingResponse endpoint
```

### Pattern 1: FastAPI Lifespan with Background Task

**What:** `@asynccontextmanager` function passed as `lifespan=` to `FastAPI()`. Code
before `yield` runs on startup (creates hub, starts poll task). Code after `yield`
runs on shutdown (cancels and awaits task).

**When to use:** Any background task that must start with the ASGI app and stop cleanly.

**Verified API for fastapi==0.115.8:**

```python
# Source: https://fastapi.tiangolo.com/advanced/events/ [CITED]
from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: task is created on uvicorn's event loop (the loop running this coroutine)
    task = asyncio.create_task(_poll_loop(app.state.sse_hub, app.state.svc))
    yield
    # Shutdown: cancel and await so the task exits before uvicorn tears down
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

def create_app(svc, is_non_local: bool = False) -> FastAPI:
    app = FastAPI(title="ShopPyBot Dashboard", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.svc = svc
    app.state.sse_hub = SseHub()
    # ... rest of existing setup unchanged
    return app
```

**Critical detail:** `asyncio.create_task()` inside the lifespan coroutine schedules the
task on the event loop that is currently running the lifespan -- which is uvicorn's event
loop. This is the correct loop for the SSE queues. [VERIFIED: FastAPI docs + asyncio stdlib]

### Pattern 2: SseHub with Bounded Drop-Oldest Queue

**What:** Hub holds a `set` of per-client queues. `broadcast()` iterates the set and
puts items. Uses `asyncio.Queue(maxsize=100)` with drop-oldest logic to protect against
slow clients accumulating unbounded memory.

**Drop-oldest implementation:** When `queue.full()` before `put_nowait()`, call
`queue.get_nowait()` to discard the oldest item first, then `put_nowait(new_item)`.
Both calls are non-blocking and safe because this code runs only on uvicorn's loop
(no thread-safety issue). [ASSUMED -- implementation choice; either approach is valid]

```python
# web/sse_hub.py
import asyncio
import json

class SseHub:
    def __init__(self):
        self._queues: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._queues.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._queues.discard(q)

    def broadcast(self, event: str, payload: dict) -> None:
        frame = f"event: {event}\ndata: {json.dumps(payload)}\n\n"
        for q in list(self._queues):
            if q.full():
                try:
                    q.get_nowait()  # drop oldest
                except asyncio.QueueEmpty:
                    pass
            try:
                q.put_nowait(frame)
            except asyncio.QueueFull:
                pass  # race: another coroutine may have filled between full() and put()
```

**Why `set`:** O(1) add/remove; iteration order irrelevant for broadcast.

### Pattern 3: SSE Async Generator with Keepalive and Disconnect Detection

**What:** Route handler returns `StreamingResponse(generator(), media_type="text/event-stream")`.
The async generator subscribes to the hub, yields frames, and unsubscribes in `finally`.

**Keepalive mechanics:** `asyncio.wait_for(queue.get(), timeout=keepalive_secs)` raises
`asyncio.TimeoutError` when no frame arrives within the keepalive window. The `except`
branch yields the SSE comment `: keep-alive\n\n`, which is ignored by clients but
prevents proxy/load-balancer idle timeouts. [CITED: SSE spec / SUMMARY.md Pitfall 5]

**Disconnect detection:** `await request.is_disconnected()` is an async method (awaitable)
that returns `True` when the client has closed the connection. Check it at the top of
each loop iteration before attempting `queue.get`. [VERIFIED: starlette docs]

```python
# web/routes/sse.py
import asyncio
import json
from fastapi import APIRouter, Request
from starlette.responses import StreamingResponse

router = APIRouter()

_KEEPALIVE_SECS = 15.0   # override in tests to 0.05

@router.get("/events")
async def sse_events(request: Request):
    hub = request.app.state.sse_hub
    return StreamingResponse(
        _event_generator(request, hub),
        media_type="text/event-stream",
    )

async def _event_generator(request: Request, hub, keepalive_secs: float = _KEEPALIVE_SECS):
    queue = hub.subscribe()
    try:
        yield "retry: 3000\n\n"
        while True:
            if await request.is_disconnected():
                break
            try:
                frame = await asyncio.wait_for(queue.get(), timeout=keepalive_secs)
                yield frame
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
    finally:
        hub.unsubscribe(queue)
```

### Pattern 4: Poll Loop with to_thread + Log Cursor

**What:** Background coroutine running on uvicorn's event loop. Calls sync functions
via `asyncio.to_thread()` to avoid blocking the loop. Maintains `after_line` cursor
for `tail_log_lines`.

```python
# web/sse_hub.py (continued)
import time

_POLL_INTERVAL_SECS = 1.0   # override in tests to 0.05

async def _poll_loop(hub: SseHub, svc, poll_interval: float = _POLL_INTERVAL_SECS):
    cursor = 0
    while True:
        try:
            await asyncio.sleep(poll_interval)
            status = await asyncio.to_thread(svc.get_status)
            hub.broadcast("status", status)
            new_lines, cursor = await asyncio.to_thread(_tail_and_advance, cursor)
            for line in new_lines:
                hub.broadcast("log", {"line": line})
        except asyncio.CancelledError:
            raise   # propagate: lifespan shutdown
        except Exception as exc:
            # Log but never kill the loop on a single error
            from logger import writeLog
            writeLog(f"SSE poll error: {exc.__class__.__name__}", "WARNING")
```

### Pattern 5: tail_log_lines Cursor with Midnight Rollover

**What:** Reads only new lines from the current log file, returning the new cursor.
Detects midnight rollover: if `after_line > total_lines`, the file has rolled over --
reset cursor to 0 and return all lines from the new file.

**Add to `web/log_reader.py`:**

```python
def tail_log_lines(after_line: int) -> tuple[list[str], int]:
    """Return (new_lines, new_cursor) from today's log, starting after after_line.

    after_line: 0-based line count already consumed. Returns lines[after_line:].
    Midnight rollover: if after_line > len(lines), the file has rolled to a new day;
    reset cursor to 0 and return all lines from the new file.
    """
    lines = _read_today_lines()
    total = len(lines)
    if after_line > total:
        # Rollover: new day's file has fewer lines than our cursor
        return lines, total
    new_lines = lines[after_line:]
    return new_lines, total
```

**Note on `_read_today_lines()`:** It already constructs `datetime.datetime.now().strftime("%Y%B%d")`,
so it always reads today's date. At midnight, a new call will naturally open the new
file. When `after_line > total`, the file is fresh (0 lines written yet, or fewer than
cursor) -- return all available lines and reset cursor to `total`. [VERIFIED: log_reader.py]

### Anti-Patterns to Avoid

- **`asyncio.Queue.put_nowait()` from the BotService thread:** Not thread-safe. The bot
  thread owns a separate event loop; calling queue methods from it corrupts queue
  internal state. Fix: uvicorn's `_poll_loop` is the sole producer via `to_thread`. [VERIFIED: Python docs]
- **`asyncio.Queue()` without `maxsize`:** Unbounded queues + slow/dead clients = OOM.
  Fix: `maxsize=100` with drop-oldest. [CITED: SUMMARY.md Pitfall 6]
- **`asyncio.create_task()` outside a running loop:** Calling it in `create_app()` body
  (not in lifespan) will fail if the app is constructed before uvicorn starts its loop.
  Fix: always create the task inside the lifespan `@asynccontextmanager`. [VERIFIED: asyncio docs]
- **Using the old `@app.on_event("startup")` decorator:** Deprecated in fastapi==0.115.8;
  mixing it with `lifespan=` is unsupported. Use only `lifespan=`. [CITED: FastAPI docs]
- **Full file re-read per tick:** `read_recent_logs()` re-reads the entire file on
  every call. At 1s interval this is wasteful and sends duplicates. Fix: `tail_log_lines`
  cursor. [VERIFIED: web/log_reader.py]
- **Sharing the `_poll_loop` task reference by closure vs `app.state`:** If the task is
  stored only in a closure variable, the lifespan shutdown cannot cancel it correctly.
  Fix: store task in `app.state.sse_poll_task` so shutdown code has a reference.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Keepalive on idle streams | Custom timer thread / separate Task | `asyncio.wait_for(queue.get(), timeout=15)` + `except TimeoutError` | Single await; no extra task; exact 15s gap guaranteed |
| Disconnect detection | Polling a threading.Event set by middleware | `await request.is_disconnected()` | Starlette built-in; correct async contract |
| SSE frame format | Custom framing class | Direct string f-string with `\n\n` | SSE format is 3 fixed field types; no library needed |
| Thread-to-async bridge | `asyncio.Queue` written by bot thread | `asyncio.to_thread(svc.get_status)` in `_poll_loop` | Thread-safe by design; avoids the core hazard |

**Key insight:** The entire SSE implementation is 3 small modules totaling ~120 lines.
Hand-rolling anything more complex than what is described is YAGNI.

## Common Pitfalls

### Pitfall 1: Cross-Loop asyncio.Queue Corruption (HIGHEST RISK)
**What goes wrong:** Code in the BotService daemon thread calls `queue.put_nowait()` on
an `asyncio.Queue` owned by uvicorn's event loop. Internally, Queue uses `asyncio.Lock`
and `asyncio.Event` which are tied to one loop. Calling methods from another thread
without `call_soon_threadsafe` corrupts the lock state.
**Why it happens:** Developers see `asyncio.Queue` as a universal queue and assume it
is thread-safe like `queue.Queue`.
**How to avoid:** Enforce the invariant at review time: `SseHub` and `asyncio.Queue`
objects must never be imported or referenced in `core/`, `orchestrator.py`, or any
file imported by the bot thread.
**Warning signs:** Intermittent `RuntimeError: Task got Future attached to a different loop`
or `RuntimeError: no running event loop` in the bot thread.

### Pitfall 2: lifespan Task Created on Wrong Loop
**What goes wrong:** `asyncio.create_task(_poll_loop(...))` is called inside `create_app()`
(the factory function body), not inside the lifespan coroutine. At factory time, uvicorn's
loop is not running yet; the task is created on the wrong loop (or no loop).
**Why it happens:** Developers put startup logic in the factory body because it's simpler.
**How to avoid:** ALL `asyncio.create_task()` calls must be inside the `lifespan` coroutine,
after the `@asynccontextmanager` `yield` point. The factory body only instantiates `SseHub`
and stores it on `app.state`.
**Warning signs:** `RuntimeError: no current event loop` on startup, or task that never runs.

### Pitfall 3: TestClient Without Context Manager Skips Lifespan
**What goes wrong:** Test creates `client = TestClient(create_app(mock_svc))` without
`with`, calls `/api/events`, and gets an immediate error because `app.state.sse_hub`
is never initialized (lifespan startup never ran).
**Why it happens:** The existing test fixture (in `test_web_dashboard.py`) does not use
a context manager because the existing routes don't need lifespan.
**How to avoid:** SSE tests MUST use `with TestClient(app) as client:`. The existing
non-SSE test fixture can remain unchanged for non-lifespan tests.
**Warning signs:** `AttributeError: 'State' object has no attribute 'sse_hub'` in tests.

### Pitfall 4: Generator Leak on Client Disconnect
**What goes wrong:** Client closes tab or kills curl. The SSE generator is still running,
holding a queue in the hub. On the next broadcast, the queue fills; `put_nowait` raises
`QueueFull` silently (if caught). Queue count in hub grows without bound.
**Why it happens:** Missing `request.is_disconnected()` check or missing `finally:
hub.unsubscribe(queue)`.
**How to avoid:** Both are required. `is_disconnected()` breaks the loop proactively.
`finally:` guarantees unsubscribe even if the generator is cancelled by uvicorn shutdown.
**Warning signs:** Hub queue count increases monotonically in load testing; memory grows.

### Pitfall 5: Keepalive Timeout Fires Before First Status Frame
**What goes wrong:** The `_event_generator` yields `retry: 3000\n\n` and then
immediately blocks on `asyncio.wait_for(queue.get(), timeout=15)`. If `_poll_loop`
is not yet running (race on test startup), the 15s timeout fires and yields only
a keep-alive comment. Tests asserting "first data frame arrives" may be timing-sensitive.
**How to avoid:** Make poll interval injectable and short in tests (0.05s). Ensure
lifespan startup is complete before the test makes its first request (the context
manager handles this).
**Warning signs:** Flaky tests where keepalive comment arrives before status frame.

### Pitfall 6: Midnight Rollover Sends All Lines Again
**What goes wrong:** At midnight, `_read_today_lines()` returns a new file starting at
line 0. The cursor is at, say, 5000. `lines[5000:]` returns `[]` (no new lines). But
`after_line > total` is True (5000 > current file length). If not handled, the cursor
stays at 5000 and the new day's initial lines are silently dropped.
**How to avoid:** The rollover check in `tail_log_lines`: `if after_line > total: return
lines, total` resets cursor to `total` of the new file (typically 0 or a few lines) and
returns all lines from the new file. [VERIFIED: log_reader.py analysis]

### Pitfall 7: Secrets Leaking Into SSE Frames via get_status()
**What goes wrong:** `get_status()` returns a `last_error` field that contains `str(exc)`
including exception messages with proxy URLs, API keys, or CAPTCHA tokens embedded in
tracebacks.
**How to avoid:** Already addressed in Phase 26 (`last_error` scrubbed to
`exc.__class__.__name__` only). The CI assertion -- regex scan of SSE data frames for
`@`, `password`, `token`, `key=`, `cvv` -- is the verification gate.
**Warning signs:** Test `test_sse_no_credential_patterns` fails.

## Code Examples

### Lifespan wiring in create_app

```python
# web/__init__.py -- verified structure from reading actual file
from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from web.sse_hub import SseHub, _poll_loop

_HERE = Path(__file__).parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(
        _poll_loop(app.state.sse_hub, app.state.svc)
    )
    app.state.sse_poll_task = task
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def create_app(svc, is_non_local: bool = False) -> FastAPI:
    app = FastAPI(
        title="ShopPyBot Dashboard",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,   # <-- new
    )
    app.state.svc = svc
    app.state.is_non_local = is_non_local
    app.state.sse_hub = SseHub()   # <-- new; created in factory, not in lifespan

    app.mount("/static", StaticFiles(directory=str(_HERE / "static")), name="static")

    from web.routes.api import router as api_router
    from web.routes.credentials import router as credentials_router
    from web.routes.config import router as config_router
    from web.routes.pages import router as pages_router
    from web.routes.sse import router as sse_router   # <-- new

    app.include_router(api_router, prefix="/api")
    app.include_router(credentials_router, prefix="/api")
    app.include_router(config_router, prefix="/api")
    app.include_router(pages_router)
    app.include_router(sse_router, prefix="/api")   # <-- new

    return app
```

**Note on `SseHub()` placement:** The hub is instantiated in `create_app()` (synchronous,
safe) so `app.state.sse_hub` exists even if lifespan has not yet run. The `_poll_loop`
task is created inside lifespan where the event loop is guaranteed running. [VERIFIED: asyncio docs]

### TestClient SSE test skeleton

```python
# tests/test_sse.py
import asyncio
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

CRED_PATTERNS = ["@", "password", "token", "key=", "cvv"]

@pytest.fixture
def mock_svc():
    svc = MagicMock()
    svc.get_status.return_value = {"running": False, "uptime_secs": 0.0, "plugins": {}}
    return svc

def test_sse_retry_line_on_open(mock_svc, tmp_path):
    from web import create_app
    from web import sse_hub
    # Override intervals for test speed
    original_poll = sse_hub._POLL_INTERVAL_SECS
    original_ka = sse_hub._KEEPALIVE_SECS
    sse_hub._POLL_INTERVAL_SECS = 0.05
    sse_hub._KEEPALIVE_SECS = 60.0  # don't want keepalive in this test

    try:
        with TestClient(create_app(mock_svc)) as client:
            # stream=True: reads response body iteratively
            with client.stream("GET", "/api/events") as resp:
                resp.raise_for_status()
                first_chunk = next(resp.iter_text())
                assert "retry: 3000" in first_chunk
    finally:
        sse_hub._POLL_INTERVAL_SECS = original_poll
        sse_hub._KEEPALIVE_SECS = original_ka
```

**Key:** `client.stream("GET", ...)` plus `resp.iter_text()` is how httpx (TestClient
backend) reads a streaming response incrementally. [ASSUMED: httpx streaming API; verify
against installed httpx version]

### Credential-pattern assertion

```python
def test_sse_no_credential_patterns(mock_svc):
    import re
    from web import create_app
    from web import sse_hub
    sse_hub._POLL_INTERVAL_SECS = 0.05

    with TestClient(create_app(mock_svc)) as client:
        with client.stream("GET", "/api/events") as resp:
            frames = []
            for chunk in resp.iter_text():
                frames.append(chunk)
                if len(frames) >= 3:
                    break
    combined = "".join(frames)
    for pattern in ["password", "key=", "cvv"]:
        assert pattern not in combined.lower(), f"Credential pattern {pattern!r} found in SSE stream"
    assert not re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+', combined), \
        "Email-like pattern found in SSE stream"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@app.on_event("startup")` | `lifespan=` context manager | FastAPI 0.93+ | Startup/shutdown in one function; old decorator deprecated but still works in 0.115.8 |
| Manual SSE keepalive task | `asyncio.wait_for(queue.get(), timeout=N)` | N/A -- best practice | No extra task; single-line idiom |
| `sse-starlette` library | Raw `StreamingResponse` with async generator | N/A -- choice | Zero deps; enough for 3 event types; sse-starlette adds anyio dep for no gain |

**Deprecated/outdated:**
- `@app.on_event("startup"/"shutdown")`: Deprecated since FastAPI 0.93. Do not use in new code.
- `fastapi.sse.EventSourceResponse`: Available from FastAPI 0.135+; not in 0.115.8. Tracked as future DEP-01.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Drop-oldest by `get_nowait()` + `put_nowait()` is the correct QueueFull strategy | Pattern 2: SseHub | Minor: could use `task_done()` / different eviction; no correctness issue either way |
| A2 | `client.stream("GET", ...) + resp.iter_text()` is the correct httpx streaming API for TestClient | Code Examples: test skeleton | Test would need different iteration API; look up installed httpx version |
| A3 | Constants `_POLL_INTERVAL_SECS` / `_KEEPALIVE_SECS` as module-level overrideable values is the injection mechanism | Pattern 3 / Pattern 4 | Could use constructor args on SseHub instead; either works for tests |

## Open Questions

1. **`asyncio.to_thread` availability in BotService.stop() race:**
   - What we know: `get_status()` reads `self._running`, `self._start_time`, and calls
     `self._health_registry.get_snapshot()`. All are in-memory, no I/O.
   - What's unclear: Whether `_health_registry.get_snapshot()` acquires a lock that
     could contend with the bot thread writing health data concurrently.
   - Recommendation: Read `core/health.py` before implementing. If it uses a `threading.Lock`,
     `to_thread` is still correct (releases GIL during lock wait). If it modifies shared
     mutable state without a lock, document the race as acceptable (snapshot reads are
     best-effort for SSE; stale by design).

2. **httpx streaming API for SSE in TestClient tests:**
   - What we know: `TestClient` is backed by `httpx`. Streaming reads use
     `client.stream("GET", url)` as context manager + `resp.iter_text()` or
     `resp.iter_lines()`.
   - What's unclear: Exact chunking behavior of `iter_text()` for `\n\n`-delimited SSE
     frames -- may need `iter_lines()` or `iter_bytes()` depending on httpx version.
   - Recommendation: Spike this first in Wave 0; assert on `"retry: 3000" in "".join(chunks[:2])`
     rather than `chunks[0]` exactly.

3. **`request.is_disconnected()` timing in TestClient:**
   - What we know: Works in production with a real TCP connection.
   - What's unclear: Whether TestClient's in-process transport makes `is_disconnected()`
     reliable for test teardown, or whether closing the `client.stream()` context manager
     is sufficient to trigger the generator's `finally` block.
   - Recommendation: Test the disconnect case explicitly: enter the stream, read 1 frame,
     exit the context manager, then assert `len(hub._queues) == 0`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| fastapi | SSE endpoint, lifespan | Checked pyproject.toml | 0.115.8 (optional dep `web`) | N/A -- must install with `pip install -e ".[web]"` |
| uvicorn[standard] | ASGI server for production | Checked pyproject.toml | 0.30.6 (optional dep `web`) | N/A -- required at runtime |
| starlette | StreamingResponse, Request | Transitive dep of fastapi | matches fastapi 0.115.8 | N/A |
| httpx | TestClient streaming reads | Transitive dep of fastapi[testclient] | matches fastapi 0.115.8 | N/A |
| pytest | Test runner | requirements.txt line 8 | 9.0.3 | N/A |

**Note:** `fastapi` is NOT in `requirements.txt` -- it is declared as `[project.optional-dependencies]
web` in `pyproject.toml`. Tests that import `web.*` guard with `pytest.importorskip("fastapi")`
(see `test_web_dashboard.py` line 3). SSE tests must do the same.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_sse_infrastructure.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SSE-02-a | Stream opens with `retry: 3000` | unit | `pytest tests/test_sse_infrastructure.py::test_sse_retry_line_on_open -x` | No -- Wave 0 |
| SSE-02-b | `data:` status frame arrives ~every 1s (fast: 0.05s in test) | unit | `pytest tests/test_sse_infrastructure.py::test_sse_status_frame_arrives -x` | No -- Wave 0 |
| SSE-02-c | `: keep-alive` comment emitted when queue idle | unit | `pytest tests/test_sse_infrastructure.py::test_sse_keepalive_comment -x` | No -- Wave 0 |
| SSE-02-d | Client disconnect leaves `SseHub._queues` empty | unit | `pytest tests/test_sse_infrastructure.py::test_sse_disconnect_cleans_hub -x` | No -- Wave 0 |
| SSE-02-e | Bot start/stop reflected in stream within 1-2s | integration | `pytest tests/test_sse_infrastructure.py::test_sse_bot_start_stop_reflected -x` | No -- Wave 0 |
| SSE-03 | No credential patterns in SSE data frames | unit | `pytest tests/test_sse_infrastructure.py::test_sse_no_credential_patterns -x` | No -- Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_sse_infrastructure.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_sse_infrastructure.py` -- covers SSE-02-a through SSE-02-e and SSE-03 (all 6 test stubs)
- [ ] `web/sse_hub.py` -- SseHub class + _poll_loop (file does not yet exist)
- [ ] `web/routes/sse.py` -- GET /api/events route (file does not yet exist)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | SSE endpoint is read-only observability; same auth posture as existing /api/status |
| V3 Session Management | no | No session tokens in SSE; CSRF origin check not needed for GET endpoints |
| V4 Access Control | no | Localhost-bound; existing non-local warning banner is the access control |
| V5 Input Validation | yes | No query params on /api/events; no input to validate |
| V6 Cryptography | no | No crypto in SSE layer |

### Known Threat Patterns for SSE Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Secret leak via `last_error` | Information Disclosure | `get_status()` scrub to `exc.__class__.__name__`; CI assertion on SSE frames (Phase 26 done, Phase 27 verification) |
| Generator/queue leak on disconnect | Denial of Service | `request.is_disconnected()` + `finally: hub.unsubscribe(queue)` |
| Slow client memory exhaustion | Denial of Service | `asyncio.Queue(maxsize=100)` + drop-oldest |
| Cross-thread queue corruption | Tampering / Availability | Bot thread never imports or touches SseHub; enforced by architecture, not code guard |

## Sources

### Primary (HIGH confidence)

- `E:\repos\ShopPyBot\pyproject.toml` -- verified fastapi==0.115.8, uvicorn[standard]==0.30.6 as web optional deps
- `E:\repos\ShopPyBot\core\service.py` -- verified `get_status()` is in-memory only; bot thread model (daemon thread with own loop)
- `E:\repos\ShopPyBot\web\__init__.py` -- verified `create_app()` factory structure; confirmed no lifespan currently
- `E:\repos\ShopPyBot\web\log_reader.py` -- verified `_read_today_lines()` strftime format; confirmed full-file re-read issue
- `E:\repos\ShopPyBot\web\routes\api.py` -- verified `asyncio.to_thread` pattern established in Phase 26
- `E:\repos\ShopPyBot\tests\test_web_dashboard.py` -- verified TestClient + mock_svc fixture pattern
- `https://fastapi.tiangolo.com/advanced/events/` -- lifespan `@asynccontextmanager` API [CITED]
- `https://www.starlette.io/requests/` -- `await request.is_disconnected()` is awaitable, returns bool [CITED]
- `https://www.starlette.io/testclient/` -- `with TestClient(app) as client:` is required for lifespan [CITED]
- `https://docs.python.org/3/library/asyncio-queue.html` -- asyncio.Queue is not thread-safe [VERIFIED]
- `E:\repos\ShopPyBot\.planning\research\SUMMARY.md` -- 7 SSE pitfalls (authoritative per CONTEXT.md) [VERIFIED: project research]
- `E:\repos\ShopPyBot\.planning\phases\27-sse-infrastructure\27-CONTEXT.md` -- locked decisions [VERIFIED]

### Secondary (MEDIUM confidence)

- `https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse` -- StreamingResponse with `media_type="text/event-stream"` async generator example [CITED]

### Tertiary (LOW confidence)

- None in this research.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- verified from pyproject.toml and venv inspection
- Architecture: HIGH -- verified from actual source files + official FastAPI/starlette docs
- Pitfalls: HIGH -- derived from authoritative project SUMMARY.md + direct source file analysis
- Test patterns: MEDIUM -- TestClient streaming API (httpx iter_text behavior) confirmed as open question A2

**Research date:** 2026-06-27
**Valid until:** 2026-07-27 (stable stack; FastAPI 0.115.8 is pinned; no fast-moving parts)
