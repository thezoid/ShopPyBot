# Phase 27: SSE Infrastructure - Pattern Map

**Mapped:** 2026-06-27
**Files analyzed:** 5 (3 new, 2 modified)
**Analogs found:** 4 / 5 (1 new with no direct codebase analog)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `web/sse_hub.py` | service | event-driven (pub-sub) | `core/health.py` | structural-only (in-memory store shape) |
| `web/routes/sse.py` | route/controller | streaming | `web/routes/api.py` (get_logs, get_status) | role-match |
| `web/__init__.py` (modify) | config/factory | request-response | `web/__init__.py` itself (current state) | exact — shows delta |
| `web/log_reader.py` (modify) | utility | file-I/O | `web/log_reader.py` itself (existing functions) | exact — shows delta |
| `tests/test_sse.py` | test | request-response + streaming | `tests/test_api_observability.py`, `tests/test_web_dashboard.py` | role-match (FLAG: needs context-manager form) |

## Pattern Assignments

### `web/sse_hub.py` (service, event-driven pub-sub)

**Analog:** `core/health.py` — loose structural analog only. No direct streaming/queue analog exists in the codebase. The class shape (private dict/set store, simple mutating methods, a read-side accessor) matches `HealthRegistry`.

**Class shape pattern** (`core/health.py` lines 13-83):
```python
class HealthRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, dict] = {}      # private store

    def heartbeat(self, name: str) -> None:      # mutating method
        self._ensure(name)
        self._plugins[name]["last_heartbeat"] = time.monotonic()

    def get_snapshot(self) -> dict[str, dict]:   # read-side accessor, strips private keys
        return {
            name: {k: v for k, v in rec.items() if not k.startswith("_")}
            for name, rec in self._plugins.items()
        }
```

**Key divergence from analog:** `SseHub` uses a `set[asyncio.Queue]` (not a dict) as the backing store. `subscribe()` returns the queue object. `unsubscribe()` uses `set.discard()` (safe if already removed). `broadcast()` iterates a snapshot list (`list(self._queues)`) to avoid mutation-during-iteration. No analog exists in the codebase for the `asyncio.Queue` drop-oldest pattern — use the RESEARCH.md Pattern 2 directly.

**Module-level injectable constants** (planner must define at top of `web/sse_hub.py`):
```python
_POLL_INTERVAL_SECS = 1.0    # override in tests: sse_hub._POLL_INTERVAL_SECS = 0.05
_KEEPALIVE_SECS = 15.0       # override in tests: sse_hub._KEEPALIVE_SECS = 0.05
```

**`asyncio.to_thread` pattern for sync calls** (from `web/routes/api.py` lines 48, 62, 143, 167):
```python
logs = await asyncio.to_thread(read_logs_filtered, n, level, search)
await asyncio.to_thread(svc.start)
rows = await asyncio.to_thread(request.app.state.svc.get_confirmed_orders)
```
Copy this exact call form in `_poll_loop`: `await asyncio.to_thread(svc.get_status)` and `await asyncio.to_thread(tail_log_lines, cursor)`.

**Error logging pattern** (from `logger.py` interface used throughout codebase):
```python
from logger import writeLog
writeLog(f"SSE poll error: {exc.__class__.__name__}", "WARNING")
```
Use `"WARNING"` type string; never log `str(exc)` (SSE-03 scrub rule).

---

### `web/routes/sse.py` (route, streaming)

**Analog:** `web/routes/api.py`

**Router declaration pattern** (`web/routes/api.py` lines 17):
```python
router = APIRouter()
```
Copy verbatim. No prefix here; prefix is applied at include time.

**Imports pattern** (`web/routes/api.py` lines 1-14):
```python
import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
```
For `sse.py`, replace `JSONResponse` import with `StreamingResponse` from starlette:
```python
import asyncio
from fastapi import APIRouter, Request
from starlette.responses import StreamingResponse
```
Note: `starlette.responses` not `fastapi.responses` — `StreamingResponse` is not re-exported by fastapi in 0.115.8 at the `fastapi.responses` path.

**`app.state.svc` access pattern** (`web/routes/api.py` lines 26-28):
```python
@router.get("/status")
async def get_status(request: Request):
    svc = request.app.state.svc
    return JSONResponse(svc.get_status())
```
For `sse.py`, access `request.app.state.sse_hub` the same way:
```python
@router.get("/events")
async def sse_events(request: Request):
    hub = request.app.state.sse_hub
    return StreamingResponse(
        _event_generator(request, hub),
        media_type="text/event-stream",
    )
```

**No `check_origin` dependency on GET:** `web/routes/api.py` applies `Depends(check_origin)` only to POST/DELETE handlers (lines 56, 66, 97, 125). `/api/events` is a GET — no CSRF dependency needed.

**Async generator disconnect + finally pattern** (no direct codebase analog — use RESEARCH.md Pattern 3 verbatim):
```python
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

---

### `web/__init__.py` — modification (config/factory)

**Analog:** `web/__init__.py` itself (current state, read in full above).

**Current state** (lines 1-42) — the complete file today:
```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

_HERE = Path(__file__).parent


def create_app(svc, is_non_local: bool = False) -> FastAPI:
    app = FastAPI(title="ShopPyBot Dashboard", docs_url=None, redoc_url=None)
    app.state.svc = svc
    app.state.is_non_local = is_non_local

    app.mount("/static", StaticFiles(directory=str(_HERE / "static")), name="static")

    from web.routes.api import router as api_router
    from web.routes.credentials import router as credentials_router
    from web.routes.config import router as config_router
    from web.routes.pages import router as pages_router

    app.include_router(api_router, prefix="/api")
    app.include_router(credentials_router, prefix="/api")
    app.include_router(config_router, prefix="/api")
    app.include_router(pages_router)

    return app
```

**Exact delta — three additions, listed in order:**

1. Add imports at top (after existing imports):
```python
from contextlib import asynccontextmanager
import asyncio
from web.sse_hub import SseHub, _poll_loop
```

2. Add lifespan function before `create_app` (after `_HERE = ...`):
```python
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
```

3. Inside `create_app`, three line changes:
   - Line 26 (`FastAPI(...)` call): add `lifespan=lifespan` kwarg
   - After `app.state.is_non_local = is_non_local`: add `app.state.sse_hub = SseHub()`
   - After existing router includes: add `from web.routes.sse import router as sse_router` + `app.include_router(sse_router, prefix="/api")`

**Router include pattern** (lines 32-40 — the exact style to copy):
```python
from web.routes.api import router as api_router
# ...
app.include_router(api_router, prefix="/api")
```
The SSE router follows this same pattern: local import inside `create_app`, aliased as `sse_router`, included with `prefix="/api"`.

**Critical: `SseHub()` in factory body, task in lifespan:** `app.state.sse_hub = SseHub()` goes in `create_app()` (synchronous, safe). `asyncio.create_task(_poll_loop(...))` goes inside the lifespan coroutine only (where the event loop is running). Never swap these placements.

---

### `web/log_reader.py` — modification (utility, file-I/O)

**Analog:** `web/log_reader.py` itself (existing functions).

**`_read_today_lines` pattern** (lines 9-19 — the function `tail_log_lines` calls):
```python
def _read_today_lines() -> list[str]:
    fname = datetime.datetime.now().strftime("%Y%B%d") + ".log"
    log_path = _LOG_DIR / fname
    if not log_path.exists():
        return []
    return log_path.read_text(encoding="utf-8", errors="replace").splitlines()
```
`tail_log_lines` calls `_read_today_lines()` directly — no reimplementation.

**Slice-then-return pattern** (lines 22-24, `read_recent_logs`):
```python
def read_recent_logs(n: int = 50) -> list[str]:
    return _read_today_lines()[-n:]
```
`tail_log_lines` uses a different slice (`lines[after_line:]`) but follows the same structure: call `_read_today_lines()`, derive `lines`, slice, return.

**Function signature and return type to add** (after `read_logs_filtered`, new function):
```python
def tail_log_lines(after_line: int) -> tuple[list[str], int]:
    """Return (new_lines, new_cursor) from today's log, starting after after_line.

    after_line: 0-based count of lines already consumed. Returns lines[after_line:].
    Midnight rollover: if after_line > total, the file has rolled to a new day;
    reset cursor to 0 and return all lines from the new file.
    """
    lines = _read_today_lines()
    total = len(lines)
    if after_line > total:
        return lines, total
    return lines[after_line:], total
```
No new imports needed. `tuple` return type uses the existing Python 3.10+ `tuple[...]` syntax already in the file (`list[str]` at line 12).

---

### `tests/test_sse.py` (test, streaming)

**Analogs:** `tests/test_api_observability.py` (fixture and CRED_PATTERN) + `tests/test_web_dashboard.py` (TestClient fixture pattern).

**`importorskip` guard** (both analog files, line 3):
```python
import pytest
pytest.importorskip("fastapi")
```
Copy verbatim as lines 1-2 of `tests/test_sse.py`. Required because `fastapi` is an optional dep.

**`mock_svc` fixture pattern** (`tests/test_api_observability.py` lines 29-33):
```python
@pytest.fixture
def mock_svc():
    svc = MagicMock()
    svc.get_status.return_value = {"running": False, "uptime_secs": 0.0, "plugins": {}}
    svc.list_items.return_value = []
    return svc
```
Copy this exact fixture. The `uptime_secs` and `plugins` keys are required because `_poll_loop` calls `svc.get_status()` and broadcasts the result as a JSON frame — a mock missing these keys would produce a dict that still serializes, but the fuller shape matches what `BotService.get_status()` actually returns.

**CRED_PATTERN constant** (`tests/test_api_observability.py` line 20):
```python
CRED_PATTERNS = ["@", "password", "token", "key=", "cvv"]
```
Use as a list (not compiled regex) for the SSE assertion loop; the RESEARCH.md credential test uses per-pattern `assert pattern not in combined.lower()` plus a separate `re.search` for email-like strings.

**FLAG: `client` fixture MUST use context-manager form — existing fixture does NOT:**

The existing fixture in both analog test files (e.g., `test_web_dashboard.py` lines 19-21):
```python
@pytest.fixture
def client(mock_svc):
    from web import create_app
    return TestClient(create_app(mock_svc))   # NO context manager — lifespan DOES NOT run
```
This pattern is **wrong for SSE tests.** Without `with TestClient(app) as client:`, the lifespan never executes, `app.state.sse_hub` is never initialized, and hitting `/api/events` raises `AttributeError: 'State' object has no attribute 'sse_hub'`.

**Correct pattern for SSE tests** — inline `with` in each test body (do NOT create a shared `client` fixture for SSE):
```python
def test_sse_retry_line_on_open(mock_svc):
    from web import create_app
    from web import sse_hub as _sse_hub_mod

    _sse_hub_mod._POLL_INTERVAL_SECS = 0.05
    _sse_hub_mod._KEEPALIVE_SECS = 60.0

    try:
        with TestClient(create_app(mock_svc)) as client:
            with client.stream("GET", "/api/events") as resp:
                resp.raise_for_status()
                chunks = list(resp.iter_text())
                combined = "".join(chunks[:3])
                assert "retry: 3000" in combined
    finally:
        _sse_hub_mod._POLL_INTERVAL_SECS = 1.0
        _sse_hub_mod._KEEPALIVE_SECS = 15.0
```

**Open question A2 (from RESEARCH.md):** `resp.iter_text()` vs `resp.iter_lines()` chunking behavior with httpx. Assert on `"retry: 3000" in "".join(chunks[:3])` rather than `chunks[0]` exactly, to handle chunking variability. Spike this in Wave 0.

**Imports block for `tests/test_sse.py`**:
```python
import pytest
pytest.importorskip("fastapi")

import re
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
```

## Shared Patterns

### `asyncio.to_thread` for sync calls off the event loop
**Source:** `web/routes/api.py` lines 48, 62, 143, 167
**Apply to:** `web/sse_hub.py` `_poll_loop` (both `svc.get_status()` and `tail_log_lines()` calls)
```python
status = await asyncio.to_thread(svc.get_status)
new_lines, cursor = await asyncio.to_thread(tail_log_lines, cursor)
```

### `app.state` for dependency access in handlers
**Source:** `web/routes/api.py` lines 27, 59, 68, 83, 143
**Apply to:** `web/routes/sse.py` handler
```python
svc = request.app.state.svc        # existing pattern
hub = request.app.state.sse_hub    # new, same shape
```

### Credential leak prevention (SSE-03)
**Source:** `core/health.py` line 47, `tests/test_api_observability.py` line 20
**Apply to:** `web/sse_hub.py` error logging + `tests/test_sse.py` credential assertion
```python
# In _poll_loop error handler: never log str(exc)
writeLog(f"SSE poll error: {exc.__class__.__name__}", "WARNING")

# In test: scan all broadcasted frames
CRED_PATTERNS = ["@", "password", "token", "key=", "cvv"]
for pattern in CRED_PATTERNS:
    assert pattern not in combined.lower()
```

### `pytest.importorskip` guard for optional fastapi dep
**Source:** `tests/test_web_dashboard.py` line 3, `tests/test_api_observability.py` line 13
**Apply to:** `tests/test_sse.py` lines 1-2
```python
import pytest
pytest.importorskip("fastapi")
```

### Local imports inside `create_app` for router registration
**Source:** `web/__init__.py` lines 32-35
**Apply to:** `web/__init__.py` modification (add sse router import in same block)
```python
from web.routes.sse import router as sse_router
app.include_router(sse_router, prefix="/api")
```

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `web/sse_hub.py` (core logic) | service | event-driven pub-sub | No asyncio.Queue fanout or background poll task exists anywhere in the codebase. `core/health.py` provides structural shape only (class with private store + mutating methods). Use RESEARCH.md Patterns 2 and 4 directly for the queue and poll loop implementation. |

## Metadata

**Analog search scope:** `web/`, `tests/`, `core/`
**Files read:** `web/__init__.py`, `web/routes/api.py`, `web/log_reader.py`, `core/health.py`, `tests/test_web_dashboard.py`, `tests/test_api_observability.py`
**Pattern extraction date:** 2026-06-27
