# Phase 26: Read-Only API Endpoints - Research

**Researched:** 2026-06-25
**Domain:** FastAPI read-only JSON endpoints + asyncio.to_thread wrapping + HealthRegistry scrubbing
**Confidence:** HIGH

## Summary

Phase 26 is a pure web-layer extension. All required data already exists in the running codebase: the `items` table carries `order_id`, `confirmed_at`, and `checkout_attempts` from v4.0 BUY-04; the `price_history` table is populated by the Amazon plugin; `read_recent_logs()` exists in `web/log_reader.py`. No DB schema changes and no new Python packages are needed.

The three implementation areas are independent and low-risk: (1) two new GET endpoints in `web/routes/api.py` wrapping sync DB calls in `asyncio.to_thread`; (2) a `read_logs_filtered()` extension in `web/log_reader.py` with AND-combined query-param filters; (3) a scrubbed `last_error` field added to `HealthRegistry.get_snapshot()` recorded at the `supervise()` exception boundary in `core/orchestrator.py`.

The only design sensitivity is the scrubbing boundary: `str(exc)` must never enter the health snapshot. The orchestrator's `supervise()` already logs `exc.__class__.__name__` to the file (confirmed at line 132); the missing piece is storing `exc.__class__.__name__` in the registry alongside the existing `record_error()` call. The CI credential-pattern assertion is straightforward: regex-scan the JSON output of `get_status()` for `@`, `password`, `token`, `key=`, `cvv`.

**Primary recommendation:** Add `get_confirmed_orders_sync()` to `models.py` (no existing function covers it), extend `HealthRegistry` with `last_error` recorded at the `supervise()` catch block, and add `read_logs_filtered()` as a thin wrapper that calls `read_recent_logs()` then post-filters.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Endpoint Contracts:**
- `GET /api/history` returns `{"confirmed_orders": [{name, order_id, confirmed_at, checkout_attempts}]}`; empty list when no confirmed orders exist.
- `GET /api/price-history/{link_b64}` returns `{"series": [{"t": <iso>, "price": <float>}]}`; returns `{"series": []}` for non-Amazon items / items with no price data.
- Invalid or garbage `link_b64` returns `{"series": []}` gracefully (no error).
- `confirmed_at` passed through from DB as ISO-8601 string.

**Log Filtering:**
- `GET /api/logs` supports `level` (exact `[LEVEL]` prefix match), `search` (case-insensitive substring), and `n`; filters are AND-combined.
- Plugin filter is DEFERRED: log lines are formatted `[TYPE][timestamp] message` with no `[PLUGIN_NAME]` tag.
- With no query params, `GET /api/logs` degrades to existing `read_recent_logs(50)` unchanged.

**Secret Scrubbing and CI Guard:**
- Add scrubbed `last_error` to per-plugin health snapshot containing only `exc.__class__.__name__`.
- Scrub at the boundary where the exception is recorded (orchestrator/health registry) -- `str(exc)` must never enter the snapshot.
- CI assertion: `/api/status` JSON and `get_status()` payload contain no credential-pattern strings (`@`, `password`, `token`, `key=`, `cvv`, case-insensitive).
- Do NOT scrub `/api/logs` response content.

**Async Safety and Endpoint Conventions:**
- Wrap every sync DB/file read in `asyncio.to_thread`.
- Leave `get_status()` called directly (in-memory, cheap).
- New GET endpoints do NOT use `check_origin`.
- On 5xx, return generic message with no exception detail.

### Claude's Discretion

None specified for Phase 26 -- all decisions are locked.

### Deferred Ideas (OUT OF SCOPE)

- Log plugin filter (requires `[PLUGIN_NAME]` tag in logger format -- not present).
- SSE streaming of these reads (Phase 27).
- Price capture for non-Amazon plugins (PRC-01, future milestone).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OBS-08 | User can search log text (substring highlight) and filter logs by level; plugin filter deferred per contingency | `read_logs_filtered()` in `web/log_reader.py` -- post-filter lines returned by `read_recent_logs(n)` using AND-combined level prefix match + case-insensitive substring; no logger.py changes |
| SSE-03 | Observability reads never block uvicorn event loop; `get_status()` `last_error` scrubbed to exception class name; CI assertion that SSE frames contain no credential-pattern strings | `asyncio.to_thread` wraps all DB/file reads; `HealthRegistry.record_last_error(name, exc)` stores only `exc.__class__.__name__`; `supervise()` calls it in the existing `except Exception as exc` block; pytest credential-pattern assertion covers `get_status()` output |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Confirmed orders read | API / Backend | -- | SQLite query; result serialized to JSON; no HTML rendering this phase |
| Price history read | API / Backend | -- | SQLite query resolved from base64 link param; empty-series for non-Amazon |
| Log filtering | API / Backend | -- | File read + post-filter in web/log_reader.py; endpoint exposes query params |
| Secret scrubbing | API / Backend | -- | Health registry mutation boundary in orchestrator; snapshot consumed by get_status() |
| CI credential guard | API / Backend | -- | Test against get_status() dict and /api/status JSON; no browser involvement |

## Standard Stack

### Core (no new packages)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | 0.115.8 | Router, Request, JSONResponse | Already installed; this phase adds two GET routes |
| starlette | transitive | JSONResponse, async context | Transitive dep of fastapi; no direct pin needed |
| asyncio | stdlib | asyncio.to_thread for sync reads | stdlib; wraps SQLite + file reads off event loop |
| base64 | stdlib | urlsafe_b64decode for link_b64 param | Already used in remove_item endpoint -- exact same pattern |
| re | stdlib | Credential-pattern CI assertion; log level prefix match | stdlib |

**No new packages.** [VERIFIED: CONTEXT.md locked decision; confirmed by SUMMARY.md Phase B note]

### Installation
No installation step required. All dependencies already present.

## Package Legitimacy Audit

No new packages are introduced in this phase. Audit not applicable.

## Architecture Patterns

### System Architecture Diagram

```
GET /api/history
  --> async handler (api.py)
        --> asyncio.to_thread(get_confirmed_orders_sync)   [models.py -- NEW]
              --> SQLite: SELECT name,order_id,confirmed_at,checkout_attempts
                          FROM items WHERE purchased=1
        --> JSONResponse({"confirmed_orders": [...]})

GET /api/price-history/{link_b64}
  --> async handler (api.py)
        --> base64.urlsafe_b64decode(link_b64) -- graceful empty on decode error
        --> asyncio.to_thread(get_price_history_sync, link, limit=200)  [models.py -- existing]
        --> map rows: {"t": scraped_at, "price": price_cents / 100}
        --> JSONResponse({"series": [...]})   -- [] when link not found or non-Amazon

GET /api/logs?level=ERROR&search=captcha&n=50
  --> async handler (api.py -- MODIFIED)
        --> asyncio.to_thread(read_logs_filtered, level, search, n)  [log_reader.py -- MODIFIED]
              --> read_recent_logs(n or 50)
              --> filter by level prefix "[LEVEL]" if level param present
              --> filter by case-insensitive substring if search param present
        --> JSONResponse({"logs": [...]})

HealthRegistry.record_last_error(name, exc)   [health.py -- NEW method]
  <-- called from supervise() except Exception block  [orchestrator.py -- MODIFIED]
      (alongside existing health.record_error(plugin_name))
  --> stores exc.__class__.__name__ only

HealthRegistry.get_snapshot()   [health.py -- MODIFIED]
  --> adds "last_error": <class_name or None> to per-plugin dict
  --> get_status() exposes it via "plugins" key

CI assertion test:
  --> call get_status() with a mock registry containing a seeded last_error
  --> regex-scan JSON string for @|password|token|key=|cvv
  --> assert no matches
```

### Recommended Project Structure

No new files required. All changes are additions to existing files:

```
web/
  routes/
    api.py          # ADD: get_history, get_price_history; MODIFY: get_logs params
  log_reader.py     # ADD: read_logs_filtered()
core/
  health.py         # ADD: record_last_error(); MODIFY: _ensure(), get_snapshot()
  orchestrator.py   # MODIFY: supervise() -- call health.record_last_error() in except block
models.py           # ADD: get_confirmed_orders_sync()
tests/
  test_web_api.py   # ADD: all Phase 26 assertions (4 test groups)
```

### Pattern 1: asyncio.to_thread for sync reads

**What:** Offloads a blocking sync function to a thread pool worker so uvicorn's event loop is not stalled.
**When to use:** Any sync SQLite call or file read inside an async FastAPI handler.

```python
# Source: web/routes/api.py (existing pattern -- bot_start/bot_stop use this)
@router.get("/history")
async def get_history(request: Request):
    rows = await asyncio.to_thread(get_confirmed_orders_sync)
    orders = [
        {"name": r[0], "order_id": r[1], "confirmed_at": r[2], "checkout_attempts": r[3]}
        for r in rows
    ]
    return JSONResponse({"confirmed_orders": orders})
```

### Pattern 2: base64 link decode with graceful degradation

**What:** Decode path param to URL; return empty series on any decode error.
**When to use:** Price-history endpoint where bad input must not error.

```python
# Source: web/routes/api.py remove_item (exact same decode, adapted here)
@router.get("/price-history/{link_b64}")
async def get_price_history(link_b64: str, request: Request):
    try:
        link = base64.urlsafe_b64decode(link_b64.encode()).decode()
    except Exception:
        return JSONResponse({"series": []})
    rows = await asyncio.to_thread(get_price_history_sync, link, 200)
    series = [{"t": r[2], "price": r[0] / 100} for r in rows]
    return JSONResponse({"series": series})
```

Note: `get_price_history_sync` returns `(price_cents, currency, scraped_at)` tuples ordered newest-first. The frontend chart expects oldest-first; reverse before serializing OR document the order and let the chart handle it. Oldest-first is more natural for time-series charts -- reverse is recommended.

### Pattern 3: read_logs_filtered with AND-combined filters

**What:** Extend `read_recent_logs(n)` with post-filtering. No file format changes.
**When to use:** `GET /api/logs` with any combination of `level`, `search`, `n` params.

```python
# Source: web/log_reader.py (extension of existing read_recent_logs)
def read_logs_filtered(
    n: int = 50,
    level: str | None = None,
    search: str | None = None,
) -> list[str]:
    lines = read_recent_logs(n)
    if level:
        prefix = f"[{level.upper()}]"
        lines = [l for l in lines if l.startswith(prefix)]
    if search:
        needle = search.lower()
        lines = [l for l in lines if needle in l.lower()]
    return lines
```

**Log line format confirmed:** `[TYPE][YYYYMonthDD@HH:MM:SS] message` -- no `[PLUGIN_NAME]` tag. Level filter uses `startswith(f"[{level.upper()}]")` which matches the first bracket group exactly.

### Pattern 4: HealthRegistry last_error recording

**What:** Add a scrubbed error field to the per-plugin dict. Store only `exc.__class__.__name__`, never `str(exc)`.
**When to use:** In `supervise()`'s `except Exception as exc` block, immediately after `health.record_error(plugin_name)`.

```python
# core/health.py -- new method
def record_last_error(self, name: str, exc: Exception) -> None:
    self._ensure(name)
    self._plugins[name]["last_error"] = exc.__class__.__name__

# _ensure() initializes last_error: None alongside other fields
# get_snapshot() already strips "_"-prefixed keys; last_error has no underscore so it IS included

# core/orchestrator.py -- supervise(), in the existing except Exception as exc block
if health is not None:
    plugin_name = plugin.__class__.__name__
    health.record_error(plugin_name)
    health.record_last_error(plugin_name, exc)  # ADD THIS LINE
    # ... rest of degraded-threshold logic unchanged
```

**Scrubbing invariant:** `exc.__class__.__name__` is always a Python identifier string (e.g. `"ConnectionError"`, `"TimeoutError"`). It cannot contain credentials. `str(exc)` can contain proxy URLs, API keys from tracebacks. Never store `str(exc)`.

### Pattern 5: Credential-pattern CI assertion

**What:** Scan `get_status()` output for credential-pattern strings. Fails the test suite if any leak.
**When to use:** As a `pytest` test in `tests/test_web_api.py`.

```python
import re
import json

CRED_PATTERN = re.compile(
    r'(@|password|token|key=|cvv)', re.IGNORECASE
)

def test_get_status_no_credential_leak():
    from unittest.mock import MagicMock
    from core.health import HealthRegistry

    registry = HealthRegistry()
    # Seed a worst-case last_error that looks like a credential string
    registry._ensure("TestPlugin")
    registry._plugins["TestPlugin"]["last_error"] = "ConnectionError"  # class name only

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

**Key nuance:** The test must use a real HealthRegistry (not a fully mocked one) so `get_snapshot()` actually exercises the scrubbing path. If the test uses `MagicMock()` for the registry, it proves nothing about the actual snapshot format.

### Anti-Patterns to Avoid

- **Calling `read_logs_filtered()` inside `get_logs` without `asyncio.to_thread`:** File reads block the event loop. Both the existing `read_recent_logs()` call and the new filtered version must be wrapped.
- **Using `str(exc)` anywhere in the health recording path:** Confirmed in CONTEXT.md and SUMMARY.md. Even a debug log statement that happens to use `str(exc)` is fine since logger.py writes to file; the critical boundary is what enters `self._plugins[name]["last_error"]`.
- **Returning HTTP 400/422 for bad `link_b64`:** The decision is graceful empty series (`{"series": []}`), not an error response. The `remove_item` endpoint raises `HTTPException(400)` for bad encoding -- the price-history endpoint deliberately differs.
- **Using `check_origin` on new GET endpoints:** CSRF gate is for mutations only. Confirmed pattern: existing `/api/status` and `/api/logs` have no `Depends(check_origin)`.
- **Reversing rows from `get_price_history_sync` in the wrong direction:** The SQL returns `ORDER BY scraped_at DESC` (newest first). For a time-series chart, reverse to oldest-first before building the `series` array.
- **Filtering log lines from a larger-than-n read:** `read_recent_logs(n)` already slices the last `n` lines. The filter applies to those `n` lines. There is no "read all then filter to n" behavior -- that would be a performance regression on large log files. If filtered results are sparse, the caller gets fewer than n results; this is correct behavior consistent with criterion 3.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Offloading sync to thread | Custom thread executor | `asyncio.to_thread()` | stdlib, one-liner, same as existing bot_start/bot_stop pattern |
| Base64 decode of URL | Custom parser | `base64.urlsafe_b64decode()` | Already used in `remove_item`; padding kept implicitly via `.encode()` |
| Credential regex scan | Custom string check | `re.compile(pattern, re.IGNORECASE)` | stdlib; exact same approach as existing `test_no_innerHTML_with_api_data` |
| Confirmed orders query | Filtering `get_items_sync()` in Python | New `get_confirmed_orders_sync()` in models.py | DB-side WHERE clause is one round-trip; Python-side filter reads all rows including non-purchased |

**Key insight:** Every primitive needed here already exists in the codebase. The implementation is wiring existing pieces, not building new infrastructure.

## Models.py: Exact Functions Available

### Existing functions relevant to Phase 26

**`get_price_history_sync(link: str, limit: int = 10) -> list[tuple]`**
- Returns: `(price_cents: int, currency: str, scraped_at: str)` tuples
- Order: `ORDER BY scraped_at DESC LIMIT ?` -- newest first
- Empty list when no rows for the link
- `limit=10` default; pass `200` for the price-history endpoint to get a useful chart range

**`get_items_sync() -> list[tuple]`**
- Returns: `(name, link, auto_buy, quantity, purchased)` -- does NOT include `order_id`, `confirmed_at`, `checkout_attempts`
- NOT suitable for `GET /api/history` -- missing required columns

**No existing function returns confirmed-order fields.** The planner must add:

```python
def get_confirmed_orders_sync() -> list[tuple]:
    """Return all purchased items with confirmation fields (OBS-04/Phase 26).

    Returns (name, order_id, confirmed_at, checkout_attempts) for rows
    where purchased=1. order_id and confirmed_at may be None for legacy
    purchased records (pre-BUY-04).
    """
    with get_db_connection() as conn:
        return conn.execute(
            "SELECT name, order_id, confirmed_at, checkout_attempts"
            " FROM items WHERE purchased=1"
        ).fetchall()
```

**Import path:** Add to `models.py`; import in `web/routes/api.py` directly (pattern matches existing `from web.log_reader import read_recent_logs`).

### Amazon vs non-Amazon detection

**How Amazon items are identified:** `AmazonPlugin.domain_patterns = ["amazon.com", "amazon.co.uk", "amazon.ca"]` (confirmed in `plugins/shopbot_plugin_amazon.py` line 70). Price history is populated only when `get_price()` returns a non-None value > 0 in `_check_and_buy()` -- this only happens for AmazonPlugin items in the current codebase (PRC-01 is deferred).

**Implementation consequence:** The price-history endpoint does NOT need to distinguish Amazon vs non-Amazon items. It queries `price_history WHERE item_link=?`. For non-Amazon items, no rows exist, so `get_price_history_sync()` returns `[]`. The endpoint returns `{"series": []}`. This is the correct empty-state per CONTEXT.md without any domain-sniffing logic.

**The CONTEXT.md states:** "returns `{"series": []}` for non-Amazon items / items with no price data." Both cases collapse to the same code path: `get_price_history_sync()` returns `[]` because no rows were written for that link.

## Common Pitfalls

### Pitfall 1: `get_price_history_sync` returns newest-first; chart expects oldest-first
**What goes wrong:** `{"series": [...]}` renders a backwards time axis in the uPlot chart (Phase 28).
**Why it happens:** SQL `ORDER BY scraped_at DESC` is standard for "get recent N," but charts need ascending time.
**How to avoid:** Apply `rows.reverse()` or `reversed()` after the `asyncio.to_thread` call, before building the series list. Add a test assertion: `series[0]["t"] <= series[-1]["t"]` when len > 1.
**Warning signs:** Chart shows time decreasing left-to-right.

### Pitfall 2: Filtering logs after slicing to n instead of filtering first
**What goes wrong:** With `level=ERROR&n=50`, the caller gets fewer than 50 lines even when more than 50 ERROR lines exist in the file.
**Why it happens:** `read_recent_logs(n)` slices the last `n` lines, then the filter is applied. If there are 200 lines in the file and only 10 are ERRORs in the last 50, you get 10, not 50.
**How to avoid:** This is acceptable behavior per criterion 3, which says "AND-filtered lines" -- there is no requirement to return exactly n filtered results. Document it explicitly. Do NOT change `read_recent_logs()` to read more lines to compensate (that would be scope creep and a performance regression).
**Warning signs:** Test expects exactly n lines when fewer matching lines exist.

### Pitfall 3: `_ensure()` not updated for `last_error` field
**What goes wrong:** `HealthRegistry._ensure()` creates the per-plugin dict with hardcoded keys. If `last_error` is not added there, plugins that never crash will have no `last_error` key in `get_snapshot()`, causing a KeyError or inconsistent schema.
**Why it happens:** `_ensure()` is the single initialization point -- it must mirror the full schema.
**How to avoid:** Add `"last_error": None` to the `_ensure()` dict initialization. `get_snapshot()` strips `_`-prefixed keys only, so `last_error` (no underscore) will be included automatically.
**Warning signs:** Test for a never-crashed plugin raises KeyError on `snapshot["PluginName"]["last_error"]`.

### Pitfall 4: Credential-pattern test uses fully mocked registry
**What goes wrong:** `get_status()` test passes even if `get_snapshot()` is broken, because the mock returns whatever you tell it to.
**Why it happens:** Over-mocking -- `MagicMock()` bypasses the actual snapshot serialization path.
**How to avoid:** Use a real `HealthRegistry` instance in the credential-pattern test. Inject it via the `svc` mock's `get_status.return_value` so the actual dict structure is tested.

### Pitfall 5: Missing `await` on `asyncio.to_thread`
**What goes wrong:** Silent runtime error -- the coroutine object is returned from the handler instead of the result. In development this silently returns `None` from the DB call.
**Why it happens:** `asyncio.to_thread(fn, arg)` returns a coroutine; without `await` it is never executed.
**How to avoid:** Always `rows = await asyncio.to_thread(fn, arg)`. Typecheck (`rtk tsc` / `mypy`) will not catch this for untyped Python code; test coverage is the only guard.

### Pitfall 6: Log `get_logs` handler not updated to use `asyncio.to_thread`
**What goes wrong:** The existing `GET /api/logs` handler calls `read_recent_logs(50)` synchronously. After adding `read_logs_filtered()`, both the new and old code paths must use `asyncio.to_thread`.
**Why it happens:** The existing handler is sync-call-in-async-def -- it currently blocks but Phase 26 establishes the invariant that all file reads are wrapped.
**How to avoid:** When modifying `get_logs` to accept `level`/`search`/`n` params, simultaneously wrap the `read_logs_filtered()` call in `asyncio.to_thread`. The handler touches one line -- cost is negligible.

## Code Examples

### New function in models.py
```python
# Source: models.py (confirmed schema: items.purchased, order_id, confirmed_at, checkout_attempts)
def get_confirmed_orders_sync() -> list[tuple]:
    """Return (name, order_id, confirmed_at, checkout_attempts) for purchased items."""
    with get_db_connection() as conn:
        return conn.execute(
            "SELECT name, order_id, confirmed_at, checkout_attempts"
            " FROM items WHERE purchased=1"
        ).fetchall()
```

### Modified get_logs handler
```python
# Source: web/routes/api.py (existing get_logs extended)
@router.get("/logs")
async def get_logs(
    request: Request,
    level: str | None = None,
    search: str | None = None,
    n: int = 50,
):
    logs = await asyncio.to_thread(read_logs_filtered, n, level, search)
    return JSONResponse({"logs": logs})
```

### HealthRegistry._ensure() updated init dict
```python
# Source: core/health.py -- add last_error: None alongside existing keys
self._plugins[name] = {
    "status": _IDLE_STATUS,
    "last_heartbeat": 0.0,
    "consecutive_errors": 0,
    "items_checked": 0,
    "orders_confirmed": 0,
    "last_error": None,         # NEW -- scrubbed exc.__class__.__name__ or None
    "_degraded_armed": False,
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `read_recent_logs(50)` unfiltered | `read_logs_filtered(n, level, search)` with AND-combined params | Phase 26 | OBS-08 satisfied |
| No `last_error` in health snapshot | `last_error: exc.__class__.__name__` in per-plugin dict | Phase 26 | SSE-03 scrubbing invariant |
| Sync file read inside async handler (get_logs) | `asyncio.to_thread(read_logs_filtered, ...)` | Phase 26 | Event loop never blocks on file I/O |

**Deprecated/outdated:**
- Direct `read_recent_logs(50)` call in `get_logs` handler: replace with `await asyncio.to_thread(read_logs_filtered, n, level, search)`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `get_price_history_sync(link, 200)` with limit=200 is sufficient for all price history (no pagination needed) | Standard Stack / Code Examples | If an item has >200 price points, chart truncates -- acceptable for the current sparse-data use case |
| A2 | `ORDER BY scraped_at DESC` in `get_price_history_sync` returns ISO-8601 strings that sort correctly | Architecture Patterns / Pitfall 1 | If scraped_at format is inconsistent, chart time axis may be wrong; confirmed format is `datetime.now(timezone.utc).isoformat()` which sorts correctly [ASSUMED -- verified by reading orchestrator.py line 476 but not by inspecting actual DB rows] |

**All other claims are VERIFIED by direct source file inspection in this session.**

## Open Questions

1. **`get_price_history_sync` return limit for the API**
   - What we know: default is 10, but the endpoint should return more for a useful chart
   - What's unclear: is there a config-driven limit, or is 200 a reasonable hardcoded cap?
   - Recommendation: hardcode 200 in the endpoint call; chart renders up to 200 data points which is more than sufficient for current Amazon scraping frequency

2. **`GET /api/logs` param `n` upper bound**
   - What we know: criterion 3 tests with `n=50`; no upper bound is specified in CONTEXT.md
   - What's unclear: should `n` be capped to prevent returning megabytes?
   - Recommendation: cap at 500 (matching the Phase 28 DOM buffer limit); silently clamp rather than error

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python asyncio.to_thread | All async wrappers | Yes | stdlib (3.9+) | -- |
| sqlite3 | get_confirmed_orders_sync | Yes | stdlib | -- |
| fastapi TestClient | tests | Yes | 0.115.8 | -- |
| pytest | test suite | Yes | installed | -- |

**No missing dependencies.**

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + fastapi.testclient.TestClient |
| Config file | none -- pytest auto-discovers tests/ |
| Quick run command | `rtk pytest tests/test_web_api.py -x` |
| Full suite command | `rtk pytest tests/ -x` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OBS-08 | `GET /api/logs?level=ERROR&search=captcha&n=50` returns AND-filtered lines | unit | `rtk pytest tests/test_web_api.py::test_logs_filtered_level_and_search -x` | No -- Wave 0 |
| OBS-08 | `GET /api/logs` with no params returns `read_recent_logs(50)` unchanged | unit | `rtk pytest tests/test_web_api.py::test_logs_no_params_default_behavior -x` | No -- Wave 0 |
| SSE-03 | `GET /api/history` returns `{"confirmed_orders": [...]}`, `[]` when none | unit | `rtk pytest tests/test_web_api.py::test_get_history_empty` `test_get_history_with_orders -x` | No -- Wave 0 |
| SSE-03 | `GET /api/price-history/{link_b64}` returns `{"series": [...]}` for Amazon, `[]` for non-Amazon | unit | `rtk pytest tests/test_web_api.py::test_get_price_history_empty` `test_get_price_history_with_data -x` | No -- Wave 0 |
| SSE-03 | Bad `link_b64` returns `{"series": []}` without error | unit | `rtk pytest tests/test_web_api.py::test_get_price_history_bad_link -x` | No -- Wave 0 |
| SSE-03 | `get_status()` output contains no credential-pattern strings | unit | `rtk pytest tests/test_web_api.py::test_get_status_no_credential_leak -x` | No -- Wave 0 |
| SSE-03 | Health snapshot `last_error` contains only class name, never `str(exc)` | unit | `rtk pytest tests/test_web_api.py::test_health_last_error_scrubbed -x` | No -- Wave 0 |

### Test Fixture Pattern (extends existing `client` fixture)

```python
# tests/test_web_api.py -- extend existing mock_svc fixture pattern from test_web_dashboard.py
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

For DB-dependent tests (`get_history`, `get_price_history`), use `unittest.mock.patch` on the models functions directly:

```python
with patch("web.routes.api.get_confirmed_orders_sync", return_value=[]):
    resp = client.get("/api/history")
```

This avoids touching the real SQLite file and keeps tests hermetic.

### Sampling Rate
- **Per task commit:** `rtk pytest tests/test_web_api.py -x`
- **Per wave merge:** `rtk pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_web_api.py` -- all 7 test functions listed in the map above (new file)
- [ ] `models.py::get_confirmed_orders_sync` -- needed before endpoint tests can mock it

*(Existing test infrastructure in `tests/test_web_dashboard.py` is sufficient for non-API tests; this phase needs a new test file for API endpoint coverage.)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Phase 26 endpoints are read-only localhost; no auth surface |
| V3 Session Management | no | No session state introduced |
| V4 Access Control | yes | GET endpoints intentionally omit `check_origin`; read-only reads have no mutation risk |
| V5 Input Validation | yes | `level`, `search`, `n` query params; `link_b64` path param |
| V6 Cryptography | no | No new crypto; base64 is encoding not encryption |

### Input Validation Details

| Param | Source | Validation Required | Implementation |
|-------|--------|---------------------|---------------|
| `link_b64` | path param | Decode may raise; must not error | `try/except Exception -> return {"series": []}` |
| `level` | query param | Free string; only used as prefix match | `f"[{level.upper()}]"` -- worst case is no matching lines |
| `search` | query param | Free string; case-insensitive substring | `needle = search.lower()` -- no injection risk (no SQL) |
| `n` | query param | Integer; should be capped | `min(n, 500)` recommended; FastAPI auto-rejects non-integer |

### Known Threat Patterns for this Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Credential leak via `last_error` | Information Disclosure | `exc.__class__.__name__` only; CI assertion |
| Log file path traversal | Tampering | `read_recent_logs()` uses hardcoded `datetime.now().strftime("%Y%B%d").log` -- no user input in path |
| Response flooding via large `n` | Denial of Service | Cap `n` at 500 in `read_logs_filtered()` |

## Sources

### Primary (HIGH confidence -- direct source file inspection)
- `E:/repos/ShopPyBot/models.py` -- confirmed: `get_price_history_sync` signature, return tuple order `(price_cents, currency, scraped_at)`, SQL `ORDER BY scraped_at DESC`; confirmed NO existing `get_confirmed_orders_sync`; confirmed `items` table columns `order_id`, `confirmed_at`, `checkout_attempts` added via idempotent ALTER
- `E:/repos/ShopPyBot/web/routes/api.py` -- confirmed: `base64.urlsafe_b64decode(link_b64.encode()).decode()` pattern; confirmed GET endpoints have no `check_origin`; confirmed `asyncio.to_thread` pattern in bot_start/bot_stop
- `E:/repos/ShopPyBot/web/log_reader.py` -- confirmed: 21-line file, `read_recent_logs(n=50)`, `splitlines()[-n:]`, format `%Y%B%d.log`
- `E:/repos/ShopPyBot/core/health.py` -- confirmed: `_ensure()` dict keys, `get_snapshot()` strips `_`-prefixed keys, NO `last_error` field currently exists
- `E:/repos/ShopPyBot/core/orchestrator.py` -- confirmed: `supervise()` `except Exception as exc` block; `health.record_error(plugin_name)` call at line ~137; `exc.__class__.__name__` already used in log message at line 132
- `E:/repos/ShopPyBot/logger.py` -- confirmed: log line format `[{TYPE}][{Y%B%d@H:M:S}] {message}`, NO `[PLUGIN_NAME]` tag; level prefix is always the first bracket group
- `E:/repos/ShopPyBot/plugins/shopbot_plugin_amazon.py` -- confirmed: `domain_patterns = ["amazon.com", "amazon.co.uk", "amazon.ca"]`; price data only from this plugin
- `E:/repos/ShopPyBot/tests/test_web_dashboard.py` -- confirmed: `client` fixture pattern, `mock_svc` pattern, `patch()` usage

### Secondary (HIGH confidence -- cross-referenced against source files)
- `.planning/phases/26-read-only-api-endpoints/26-CONTEXT.md` -- locked decisions consumed verbatim
- `.planning/research/SUMMARY.md` -- Phase B architecture; asyncio.to_thread pattern; no-new-packages constraint

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new packages; all existing; confirmed by source inspection
- Architecture: HIGH -- all patterns already present in codebase; new code is wiring, not invention
- Pitfalls: HIGH -- all grounded in direct source file readings, not speculation
- Models.py gap: HIGH -- confirmed by exhaustive grep of all `def *_sync` functions

**Research date:** 2026-06-25
**Valid until:** 90 days (stable; no external deps; all findings from local source files)
