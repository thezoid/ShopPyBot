# Phase 26: Read-Only API Endpoints - Pattern Map

**Mapped:** 2026-06-25
**Files analyzed:** 6 (4 modified, 1 new test file, 1 new test additions)
**Analogs found:** 6 / 6

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `web/routes/api.py` (add 2 GET endpoints, modify get_logs) | route/controller | request-response | `web/routes/api.py` existing GET handlers (get_status, get_logs, list_items, remove_item) | exact |
| `web/log_reader.py` (add read_logs_filtered) | utility | file-I/O | `web/log_reader.py` read_recent_logs (same file, extension) | exact |
| `models.py` (add get_confirmed_orders_sync) | model | CRUD | `models.py` get_price_history_sync / get_items_sync | exact |
| `core/health.py` (add record_last_error, update _ensure + get_snapshot) | service | request-response | `core/health.py` record_error / _ensure / get_snapshot (same file, extension) | exact |
| `core/orchestrator.py` (modify supervise except block) | service | event-driven | `core/orchestrator.py` lines 136-150 health.record_error call site | exact |
| `tests/test_web_api.py` (new file, 7 test functions) | test | request-response | `tests/test_web_dashboard.py` client+mock_svc fixture, patch pattern | exact |

## Pattern Assignments

### `web/routes/api.py` — GET /api/history (new endpoint)

**Analog:** `web/routes/api.py` `list_items` handler (lines 65-79) + `bot_start` asyncio.to_thread usage (lines 41-48)

**Imports pattern** (lines 1-16, already present — no new imports needed):
```python
import asyncio
import base64

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from web.security import check_origin
from web.log_reader import read_recent_logs
```
Add to imports: `from models import get_confirmed_orders_sync` (new function) alongside `read_recent_logs`.

**Core pattern for GET /api/history** — copy from list_items (lines 65-79) + to_thread from bot_start (line 47):
```python
# analog: list_items (lines 65-79) + asyncio.to_thread from bot_start (line 47)
@router.get("/history")
async def get_history(request: Request):
    rows = await asyncio.to_thread(get_confirmed_orders_sync)
    orders = [
        {
            "name": r[0],
            "order_id": r[1],
            "confirmed_at": r[2],
            "checkout_attempts": r[3],
        }
        for r in rows
    ]
    return JSONResponse({"confirmed_orders": orders})
```

Key points from analog:
- No `dependencies=[Depends(check_origin)]` — matches existing GET endpoints (get_status line 24, get_logs line 31, list_items line 65)
- `async def` + `await asyncio.to_thread(sync_fn)` pattern is from bot_start line 47
- `JSONResponse(dict)` return — consistent across all handlers
- Row-to-dict comprehension — copy from list_items lines 70-78

**No auth/guard** — confirmed by lines 24, 31, 65: GET endpoints carry no `Depends(check_origin)`.

---

### `web/routes/api.py` — GET /api/price-history/{link_b64} (new endpoint)

**Analog:** `web/routes/api.py` `remove_item` handler (lines 110-118) for base64 decode pattern; `bot_start` (lines 41-48) for asyncio.to_thread

**Base64 decode pattern** (lines 113-116 of remove_item):
```python
# Source: web/routes/api.py remove_item, lines 113-116
try:
    link = base64.urlsafe_b64decode(link_b64.encode()).decode()
except Exception:
    raise HTTPException(status_code=400, detail="Invalid link encoding")
```

**Core pattern for GET /api/price-history/{link_b64}** — same decode, different error handling (graceful empty instead of 400):
```python
# Differs from remove_item: bad link_b64 returns {"series": []} not HTTPException
@router.get("/price-history/{link_b64}")
async def get_price_history(link_b64: str, request: Request):
    try:
        link = base64.urlsafe_b64decode(link_b64.encode()).decode()
    except Exception:
        return JSONResponse({"series": []})
    rows = await asyncio.to_thread(get_price_history_sync, link, 200)
    rows = list(reversed(rows))  # SQL returns newest-first; chart needs oldest-first
    series = [{"t": r[2], "price": r[0] / 100} for r in rows]
    return JSONResponse({"series": series})
```

Add to imports: `from models import get_price_history_sync` (already exists in models.py line 216).

---

### `web/routes/api.py` — GET /api/logs (modify existing, lines 31-34)

**Analog:** `web/routes/api.py` existing get_logs (lines 31-34); bot_start asyncio.to_thread (line 47)

**Existing handler** (lines 31-34 — to be replaced):
```python
# Source: web/routes/api.py lines 31-34 (current)
@router.get("/logs")
async def get_logs(request: Request):
    """Return the last 50 lines of today's log file."""
    return JSONResponse({"logs": read_recent_logs(50)})
```

**Replacement pattern** — add query params, wrap in asyncio.to_thread, swap to read_logs_filtered:
```python
@router.get("/logs")
async def get_logs(
    request: Request,
    level: str | None = None,
    search: str | None = None,
    n: int = 50,
):
    logs = await asyncio.to_thread(read_logs_filtered, min(n, 500), level, search)
    return JSONResponse({"logs": logs})
```

Change import line 16 from `from web.log_reader import read_recent_logs` to `from web.log_reader import read_logs_filtered`.

---

### `web/log_reader.py` — add read_logs_filtered (extend existing file)

**Analog:** `web/log_reader.py` `read_recent_logs` (lines 9-21 — entire file)

**Existing function to call from** (lines 9-21):
```python
# Source: web/log_reader.py lines 9-21
def read_recent_logs(n: int = 50) -> list[str]:
    fname = datetime.datetime.now().strftime("%Y%B%d") + ".log"
    log_path = _LOG_DIR / fname
    if not log_path.exists():
        return []
    text = log_path.read_text(encoding="utf-8", errors="replace")
    return text.splitlines()[-n:]
```

**New function to add** — thin wrapper that post-filters the result of read_recent_logs:
```python
def read_logs_filtered(
    n: int = 50,
    level: str | None = None,
    search: str | None = None,
) -> list[str]:
    """Return last n log lines, AND-filtered by level prefix and/or search substring.

    level: exact match on first bracket group e.g. level="ERROR" matches "[ERROR][...]"
    search: case-insensitive substring match against full line text
    With no filters, degrades to read_recent_logs(n) behavior unchanged (OBS-08).
    """
    lines = read_recent_logs(n)
    if level:
        prefix = f"[{level.upper()}]"
        lines = [l for l in lines if l.startswith(prefix)]
    if search:
        needle = search.lower()
        lines = [l for l in lines if needle in l.lower()]
    return lines
```

Log line format confirmed from logger.py: `[TYPE][YYYYMonthDD@HH:MM:SS] message` — level prefix is always the first bracket group, so `startswith(f"[{level.upper()}]")` is the correct match.

---

### `models.py` — add get_confirmed_orders_sync

**Analog:** `models.py` `get_price_history_sync` (lines 216-223) — same role (read-only SELECT returning list of tuples), same data flow (CRUD via get_db_connection context manager)

**Direct analog** (lines 216-223):
```python
# Source: models.py lines 216-223
def get_price_history_sync(link: str, limit: int = 10) -> list[tuple]:
    """Return last N (price_cents, currency, scraped_at) rows, newest first."""
    with get_db_connection() as conn:
        return conn.execute(
            "SELECT price_cents, currency, scraped_at FROM price_history"
            " WHERE item_link=? ORDER BY scraped_at DESC LIMIT ?",
            (link, limit),
        ).fetchall()
```

**New function** — copy structure exactly:
```python
def get_confirmed_orders_sync() -> list[tuple]:
    """Return (name, order_id, confirmed_at, checkout_attempts) for purchased items.

    order_id and confirmed_at may be None for legacy purchased records (pre-BUY-04).
    """
    with get_db_connection() as conn:
        return conn.execute(
            "SELECT name, order_id, confirmed_at, checkout_attempts"
            " FROM items WHERE purchased=1"
        ).fetchall()
```

Place after `get_items_sync` (line 93) in the items section, before the price history section. The `get_db_connection` context manager pattern (lines 10-30) handles WAL pragmas, commit/rollback, and close automatically — do not replicate that logic.

---

### `core/health.py` — add record_last_error, update _ensure and get_snapshot

**Analog:** `core/health.py` `record_error` method (lines 38-40) for the new method shape; `_ensure` (lines 19-28) for the init dict; `get_snapshot` (lines 71-76) for the snapshot behavior

**_ensure dict** (lines 19-28 — current):
```python
# Source: core/health.py lines 19-28
def _ensure(self, name: str) -> None:
    if name not in self._plugins:
        self._plugins[name] = {
            "status": _IDLE_STATUS,
            "last_heartbeat": 0.0,
            "consecutive_errors": 0,
            "items_checked": 0,
            "orders_confirmed": 0,
            "_degraded_armed": False,
        }
```

**Modified _ensure** — add `"last_error": None` alongside existing keys (no underscore prefix so it IS included in get_snapshot output):
```python
self._plugins[name] = {
    "status": _IDLE_STATUS,
    "last_heartbeat": 0.0,
    "consecutive_errors": 0,
    "items_checked": 0,
    "orders_confirmed": 0,
    "last_error": None,          # scrubbed exc.__class__.__name__ or None (SSE-03)
    "_degraded_armed": False,
}
```

**record_error analog** (lines 38-40 — copy shape for new method):
```python
# Source: core/health.py lines 38-40
def record_error(self, name: str) -> None:
    self._ensure(name)
    self._plugins[name]["consecutive_errors"] += 1
```

**New method** — same structure, different assignment:
```python
def record_last_error(self, name: str, exc: Exception) -> None:
    """Store scrubbed error class name; never stores str(exc) (SSE-03)."""
    self._ensure(name)
    self._plugins[name]["last_error"] = exc.__class__.__name__
```

**get_snapshot** (lines 71-76 — unchanged, already correct):
```python
# Source: core/health.py lines 71-76
def get_snapshot(self) -> dict[str, dict]:
    """Return a deep copy of per-plugin records with private keys stripped."""
    return {
        name: {k: v for k, v in rec.items() if not k.startswith("_")}
        for name, rec in self._plugins.items()
    }
```

`last_error` has no underscore prefix, so it is automatically included in the snapshot output. No change to get_snapshot is needed beyond the _ensure dict update.

---

### `core/orchestrator.py` — supervise() except block (lines 125-150)

**Analog:** `core/orchestrator.py` lines 136-138 (existing health.record_error call site)

**Existing except block** (lines 125-150, the mutation target):
```python
# Source: core/orchestrator.py lines 125-150
except Exception as exc:
    now = time.monotonic()
    failure_times.append(now)
    while failure_times and (now - failure_times[0]) > _FAILURE_WINDOW_SECS:
        failure_times.popleft()
    writeLog(
        f"[{plugin.__class__.__name__}] crashed: {exc.__class__.__name__} "
        f"({len(failure_times)} in window)",
        "ERROR",
    )
    if health is not None:
        plugin_name = plugin.__class__.__name__
        health.record_error(plugin_name)
        # ... rest of degraded-threshold logic
```

**One-line addition** — insert after line 138 (`health.record_error(plugin_name)`):
```python
if health is not None:
    plugin_name = plugin.__class__.__name__
    health.record_error(plugin_name)
    health.record_last_error(plugin_name, exc)   # ADD: scrubbed last_error (SSE-03)
    # health_degraded: consecutive-error early-warning ...
```

No other changes to orchestrator.py. The `exc.__class__.__name__` pattern is already established at line 132 (writeLog call) — this mirrors that pattern into the registry.

---

### `tests/test_web_api.py` (new file)

**Analog:** `tests/test_web_dashboard.py` — complete file (lines 1-262)

**Fixture pattern** (lines 10-21 of test_web_dashboard.py — copy verbatim):
```python
# Source: tests/test_web_dashboard.py lines 1-21
import pytest
pytest.importorskip("fastapi")

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


@pytest.fixture
def mock_svc():
    svc = MagicMock()
    svc.get_status.return_value = {"running": False, "uptime_secs": 0.0, "plugins": {}}
    svc.list_items.return_value = []
    return svc


@pytest.fixture
def client(mock_svc):
    from web import create_app
    return TestClient(create_app(mock_svc))
```

Note: extend mock_svc.get_status.return_value to include `"uptime_secs": 0.0, "plugins": {}` so SSE-03 credential-pattern test has a realistic payload shape.

**Patch pattern for DB-dependent tests** (lines 77-82 of test_web_dashboard.py):
```python
# Source: tests/test_web_dashboard.py lines 77-82 (patch usage)
with patch("core.credentials.get_store", return_value=mock_store):
    app = create_app(svc)
    client = TestClient(app)
    resp = client.get("/")
```

Adapt for API tests:
```python
# Patch target is the import name in web.routes.api, not the source module
with patch("web.routes.api.get_confirmed_orders_sync", return_value=[]):
    resp = client.get("/api/history")
    assert resp.status_code == 200
    assert resp.json() == {"confirmed_orders": []}

with patch("web.routes.api.get_confirmed_orders_sync", return_value=[
    ("Widget A", "ORD-001", "2026-01-01T00:00:00+00:00", 1)
]):
    resp = client.get("/api/history")
    data = resp.json()
    assert data["confirmed_orders"][0]["order_id"] == "ORD-001"
```

**Credential-pattern test** — uses real HealthRegistry (not MagicMock) to exercise actual scrubbing path:
```python
import re
import json

CRED_PATTERN = re.compile(r'(@|password|token|key=|cvv)', re.IGNORECASE)

def test_get_status_no_credential_leak():
    from core.health import HealthRegistry
    registry = HealthRegistry()
    registry._ensure("TestPlugin")
    registry._plugins["TestPlugin"]["last_error"] = "ConnectionError"

    svc_mock = MagicMock()
    svc_mock.get_status.return_value = {
        "running": False,
        "uptime_secs": 0.0,
        "plugins": registry.get_snapshot(),
    }
    payload = json.dumps(svc_mock.get_status())
    assert not CRED_PATTERN.search(payload), (
        f"Credential pattern found in get_status() output: {CRED_PATTERN.findall(payload)}"
    )
```

The `re.compile` + `IGNORECASE` pattern is established in the codebase at `test_web_dashboard.py` lines 231-233 (`test_no_innerHTML_with_api_data` uses `re.compile` with `re.DOTALL`).

---

## Shared Patterns

### asyncio.to_thread for sync reads
**Source:** `web/routes/api.py` lines 41-48 (bot_start), lines 52-58 (bot_stop)
**Apply to:** All three modified/new GET endpoints in api.py (get_history, get_price_history, get_logs)
```python
# Source: web/routes/api.py lines 47 and 57
await asyncio.to_thread(svc.start)
await asyncio.to_thread(svc.stop)
# Pattern: rows = await asyncio.to_thread(sync_function, arg1, arg2)
```
Rule: every sync SQLite call or file read inside an async handler MUST be wrapped. `get_status()` is exempt (in-memory, REL-07).

### JSONResponse return convention
**Source:** `web/routes/api.py` lines 28, 34, 48, 57, 79, 107, 118
**Apply to:** All new and modified GET endpoints
```python
return JSONResponse({"key": value})
```
All handlers return `JSONResponse`, never plain `dict` or other response types.

### get_db_connection context manager
**Source:** `models.py` lines 10-30
**Apply to:** `get_confirmed_orders_sync` in models.py
```python
with get_db_connection() as conn:
    return conn.execute("SELECT ...").fetchall()
```
The context manager handles WAL pragmas, commit, rollback, and close. New sync functions follow this single-statement pattern exactly.

### No check_origin on GET endpoints
**Source:** `web/routes/api.py` lines 24, 31, 65 (no `dependencies=[Depends(check_origin)]`)
**Apply to:** All three new/modified GET endpoints
Confirmed invariant: CSRF gate is mutations only (POST/DELETE). GET endpoints carry no dependency.

### exc.__class__.__name__ scrubbing invariant
**Source:** `core/orchestrator.py` line 132 (writeLog call already uses this pattern)
**Apply to:** `core/health.py` record_last_error method; `core/orchestrator.py` call site
```python
# Source: core/orchestrator.py line 132
f"[{plugin.__class__.__name__}] crashed: {exc.__class__.__name__} "
```
`str(exc)` may contain proxy URLs, credentials from tracebacks. `exc.__class__.__name__` is always a Python identifier — cannot contain credentials.

## No Analog Found

All files have close analogs in the codebase. No entries.

## Metadata

**Analog search scope:** `web/routes/`, `web/`, `core/`, `models.py`, `tests/`
**Files scanned:** 6 source files read directly
**Pattern extraction date:** 2026-06-25
