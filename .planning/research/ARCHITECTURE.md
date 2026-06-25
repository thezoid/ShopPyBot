# Architecture Research

**Domain:** FastAPI dashboard with SSE live-push + design-system layer + observability surfaces (v4.1 Dashboard & Observability)
**Researched:** 2026-06-25
**Confidence:** HIGH (all integration points verified against actual source files and FastAPI 0.115.8 package API)

## Standard Architecture

### System Overview

```
Browser
  |  EventSource /api/events     (SSE multiplex, replaces 2s poll)
  |  GET /api/history            (confirmed buys read-only)
  |  GET /api/price-history/{b}  (per-item price series read-only)
  |  GET /api/logs?level=...     (enhanced log reader)
  |  (existing fetch CRUD unchanged)
  v
FastAPI / Uvicorn (uvicorn event loop -- single thread)
  |
  |-- web/__init__.py  create_app()        [MODIFIED: add sse_router, lifespan, SseHub on app.state]
  |-- web/routes/api.py                    [MODIFIED: add /history, /price-history]
  |-- web/routes/sse.py                    [NEW: /api/events StreamingResponse]
  |-- web/sse_hub.py                       [NEW: SseHub class + _poll_loop background task]
  |-- web/log_reader.py                    [MODIFIED: add filter + tail-with-cursor]
  |-- web/static/tokens.css               [NEW: design tokens, light/dark vars]
  |-- web/static/components.css           [NEW: component library consuming tokens]
  |-- web/static/dashboard.css            [MODIFIED: layout only, @imports tokens+components]
  |-- web/static/sparkline.js             [NEW: vendored zero-dep MIT sparkline ~1KB]
  |-- web/templates/dashboard.html        [MODIFIED: health cards, run-history, price charts,
  |                                         log filter UI; EventSource client; theme-init script]
  |
  |  asyncio.Queue per SSE client (owned by uvicorn event loop)
  |  _poll_loop calls asyncio.to_thread(svc.get_status) -- NO cross-loop touching
  v
BotService (daemon thread, owns its own asyncio event loop)
  |
  |-- get_status() [in-memory read, non-blocking, safe to call from any thread]
  |-- _health_registry.get_snapshot() [deep copy, private keys stripped, thread-safe]
  v
SQLite (WAL mode, existing models.py)
  |-- items table  (read: name, order_id, confirmed_at, checkout_attempts)
  |-- price_history table  (read: price_cents, currency, scraped_at)
```

### Component Responsibilities

| Component | Status | Responsibility |
|-----------|--------|----------------|
| `web/routes/sse.py` | NEW | Single `/api/events` endpoint; per-client asyncio.Queue; SSE text/event-stream generator |
| `web/sse_hub.py` | NEW | SseHub (set of active queues, broadcast method); `_poll_loop` async background task that drives all events |
| `web/static/tokens.css` | NEW | CSS custom properties for color, spacing, radius, shadow, type scale; light/dark via `prefers-color-scheme` + `[data-theme]` override |
| `web/static/components.css` | NEW | Button, card, badge, status-dot, table, form, log-panel rules that only reference token vars |
| `web/static/dashboard.css` | MODIFIED | Layout-only (container, grid, section order); opens with `@import` of tokens and components |
| `web/static/sparkline.js` | NEW | Vendored `fnando/sparkline` MIT, ~1KB minified; no CDN, no npm |
| `web/templates/dashboard.html` | MODIFIED | New sections: health cards, run history, price charts, log viewer with filter; EventSource replaces setInterval; inline theme-init in head |
| `web/routes/api.py` | MODIFIED | Add `/api/history` and `/api/price-history/{link_b64}` read-only routes |
| `web/log_reader.py` | MODIFIED | Add `read_logs_filtered(n, level, plugin, search)` and `tail_log_lines(after_line) -> (list, int)` |
| `web/__init__.py` | MODIFIED | Include `sse_router`; attach `SseHub` to `app.state.sse_hub`; register lifespan for `_poll_loop` |
| `BotService` / `HealthRegistry` | UNCHANGED | `get_status()` and `get_snapshot()` remain the sole read surface; no new writes or APIs |
| `models.py` | UNCHANGED | No schema changes; new queries use existing `get_db_connection()` context manager |

## Project Structure Changes

```
web/
  __init__.py               (MODIFIED: lifespan, sse_router, SseHub on app.state)
  sse_hub.py                (NEW)
  log_reader.py             (MODIFIED)
  routes/
    api.py                  (MODIFIED: /history, /price-history)
    sse.py                  (NEW)
    credentials.py          (unchanged)
    config.py               (unchanged)
    pages.py                (unchanged)
  static/
    tokens.css              (NEW)
    components.css          (NEW)
    dashboard.css           (MODIFIED: layout only, @imports)
    sparkline.js            (NEW: vendored)
  templates/
    dashboard.html          (MODIFIED)
```

## Architectural Patterns

### Pattern 1: CSS Token/Component Split (3-File Design System)

**What:** Split the single `dashboard.css` (182 lines) into three layers. `tokens.css` owns all custom property declarations scoped to `:root`. `components.css` owns component rules that ONLY reference those custom properties (never hardcoded hex values). `dashboard.css` is reduced to layout (container width, section ordering) and opens with `@import url("tokens.css"); @import url("components.css");`.

**When to use:** This project. Keeps concerns separated without any build step; all three are vendored static assets served by the existing `StaticFiles` mount. No Node, no CDN, no build pipeline.

**Trade-offs:** Three HTTP requests instead of one on first load (negligible for a localhost-only app). Each file stays under 200 lines. The existing `dashboard.css` content is partitioned, not discarded; no behavior changes in this step.

**Light/dark without FOUC, no external fonts:**

Use two-layer detection. The `:root` block in `tokens.css` defines light-mode token values. A `@media (prefers-color-scheme: dark)` block on `:root` overrides them to dark values. An `html[data-theme="dark"]` selector allows a JS toggle to override the media query (persisted to `localStorage`). The `:root` inside a `@media` query has lower specificity than `html[data-theme]`, so the explicit toggle always wins.

To prevent FOUC, put a synchronous inline `<script>` in `<head>` BEFORE the `<link>` tags:

```html
<head>
  <script>
    var t = localStorage.getItem("theme");
    if (t) document.documentElement.dataset.theme = t;
  </script>
  <link rel="stylesheet" href="/static/tokens.css">
  <link rel="stylesheet" href="/static/components.css">
  <link rel="stylesheet" href="/static/dashboard.css">
</head>
```

This script runs synchronously during HTML parse, before the browser issues any style-sheet requests. The `data-theme` attribute is present when the first style sheet is applied, so the correct token values are used from the first paint. No flash.

No external fonts. The existing system font stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`) stays in `tokens.css` as a `--font-family-base` token. Never `@import url(https://fonts.googleapis.com/...)` -- violates the zero-CDN constraint and breaks offline use.

### Pattern 2: SSE Endpoint with Per-Client asyncio.Queue Bridge

**What:** This is the highest-risk component. BotService runs on a daemon thread with its OWN asyncio event loop (`self._loop`). Uvicorn runs FastAPI on a SEPARATE asyncio event loop. These loops are independent; asyncio primitives are not shared between them.

**The correct bridge: uvicorn-side poll task only.**

A background async task running inside uvicorn's event loop polls `BotService.get_status()` using `asyncio.to_thread()`. The result is distributed to all active per-client `asyncio.Queue` objects via `queue.put_nowait()`. All queues, all SSE generators, and the poll task live exclusively in uvicorn's event loop. The bot daemon thread is NEVER aware of the SSE hub.

Key safety properties:
- `asyncio.Queue` is NOT thread-safe (Python docs confirmed). Never call `put_nowait` from the bot's daemon thread.
- `asyncio.to_thread()` offloads the sync `svc.get_status()` call to a thread-pool worker, returning the uvicorn event loop immediately. Available in Python 3.9+; confirmed available since the project requires Python 3.11+.
- `BotService.get_status()` is documented as "cheap and non-blocking: all reads are in-memory only." `HealthRegistry.get_snapshot()` returns a deep copy with private keys stripped. No lock needed from the caller.
- `self._loop` on BotService is `None` when the bot is not running. The uvicorn-side poll handles the `running=False` case naturally (get_status() is safe before `start()` per REL-07).

**SseHub module (`web/sse_hub.py`):**

```python
import asyncio

class SseHub:
    def __init__(self):
        self._queues: set[asyncio.Queue] = set()

    def subscribe(self, q: asyncio.Queue):
        self._queues.add(q)

    def unsubscribe(self, q: asyncio.Queue):
        self._queues.discard(q)

    def broadcast(self, payload: dict):
        dead = set()
        for q in self._queues:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                dead.add(q)
        self._queues -= dead
```

**Background poll task (runs in uvicorn event loop via lifespan):**

```python
async def _poll_loop(svc, hub: SseHub, interval: float = 1.0):
    log_cursor = 0
    while True:
        await asyncio.sleep(interval)
        status = await asyncio.to_thread(svc.get_status)
        hub.broadcast({"type": "status", "data": status})
        new_lines, log_cursor = await asyncio.to_thread(tail_log_lines, log_cursor)
        if new_lines:
            hub.broadcast({"type": "log", "data": new_lines})
```

**SSE endpoint (`web/routes/sse.py`):**

```python
@router.get("/events")
async def sse_events(request: Request):
    hub = request.app.state.sse_hub
    queue: asyncio.Queue = asyncio.Queue(maxsize=50)
    hub.subscribe(queue)
    async def generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(payload)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            hub.unsubscribe(queue)
    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

**FastAPI version note:** FastAPI 0.115.8 (the pinned version in `pyproject.toml`) does NOT include `fastapi.sse` or `EventSourceResponse`. That was added in FastAPI 0.135.0. Use `StreamingResponse` directly as shown above. No new dependency needed. Do NOT add `sse-starlette` unless there is a specific reason; raw `StreamingResponse` with `text/event-stream` is the correct zero-dep approach here.

**Client-side (browser):**

Replace `setInterval(pollStatus, 2000)` and `setInterval(pollLogs, 2000)` with a single `EventSource`:

```js
const es = new EventSource('/api/events');
es.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  if (msg.type === 'status') updateStatusUI(msg.data);
  if (msg.type === 'log') appendLogLines(msg.data);
};
es.onerror = () => { /* EventSource reconnects automatically */ };

// Polling fallback only for environments without EventSource (extremely rare)
if (typeof EventSource === 'undefined') {
  setInterval(pollStatus, 2000);
  setInterval(pollLogs, 2000);
}
```

`EventSource` reconnects automatically on connection loss. No additional reconnection logic needed.

**Lifespan wiring in `web/__init__.py`:**

```python
from contextlib import asynccontextmanager
from web.sse_hub import SseHub, _poll_loop

@asynccontextmanager
async def lifespan(app):
    hub = SseHub()
    app.state.sse_hub = hub
    task = asyncio.create_task(_poll_loop(app.state.svc, hub))
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

def create_app(svc, is_non_local=False):
    app = FastAPI(..., lifespan=lifespan)
    app.state.svc = svc
    ...
```

### Pattern 3: Read-Only History API Endpoints

**What:** Two new GET routes in `web/routes/api.py`. No schema changes; all columns exist from v4.0 (BUY-04: `order_id`, `confirmed_at`, `checkout_attempts` in `items`; v3.0: `price_history` table).

**Run/buy history (`GET /api/history`):**

Query (add a helper to `models.py` or inline via `get_db_connection()`):

```sql
SELECT name, link, order_id, confirmed_at, checkout_attempts
FROM items
WHERE purchased = 1 AND order_id IS NOT NULL
ORDER BY confirmed_at DESC
LIMIT 50
```

Response shape:
```json
{
  "confirmed_orders": [
    {
      "name": "string",
      "link": "string",
      "order_id": "string",
      "confirmed_at": "ISO8601",
      "checkout_attempts": 1
    }
  ]
}
```

Wrap the sync DB call in `asyncio.to_thread()` to avoid blocking uvicorn's event loop.

**Price-history series (`GET /api/price-history/{link_b64}`):**

Decode `link_b64` using the same urlsafe-base64 scheme as the existing `/api/items/{link_b64}` DELETE endpoint. Call `get_price_history_sync(link, limit=100)` (already in `models.py`). Series comes back newest-first; convert `price_cents -> price_dollars` at the API boundary.

Response shape:
```json
{
  "item_link": "string",
  "series": [
    {"price_cents": 4999, "price_dollars": 49.99, "currency": "USD", "scraped_at": "ISO8601"}
  ]
}
```

Note: price data is Amazon-only today (PRICE-02, Phase 16). Other plugins will return an empty `series`. Surface gracefully: if `series` is empty, the template renders placeholder text "No price history available for this plugin."

### Pattern 4: Enhanced Log Reader

**What:** Two additive functions in `web/log_reader.py`. Existing `read_recent_logs(n)` is NOT changed; the API endpoint gains optional query params.

**`read_logs_filtered(n, level, plugin, search) -> list[str]`:**

Reads the full log file (same `_log_path()` logic), applies filters AND-combined, returns last `n` matching lines:
- `level`: string like `"ERROR"` -- match lines containing `[ERROR]` (or whatever the logger format emits)
- `plugin`: substring match on plugin name (e.g. `"amazon"`)
- `search`: case-insensitive substring match anywhere in the line
- All params are optional/nullable; when all are None it degrades to `read_recent_logs(n)`

Wire into `GET /api/logs?level=ERROR&plugin=amazon&search=captcha&n=100` with query params on the existing endpoint.

**`tail_log_lines(after_line: int) -> tuple[list[str], int]`:**

Reads the current log file, returns `(lines[after_line:], total_line_count)`. Called by `_poll_loop` every second. When the log file rolls over at midnight (new filename), `after_line` will exceed the new file's line count; detect this (return value `new_cursor < after_line`) and reset the cursor to 0.

```python
def tail_log_lines(after_line: int) -> tuple[list[str], int]:
    path = _log_path()
    if not path.exists():
        return [], after_line
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    total = len(lines)
    if after_line > total:
        after_line = 0  # log rolled
    return lines[after_line:], total
```

### Pattern 5: Vendored Sparkline Chart

**What:** Download `sparkline.min.js` from github.com/fnando/sparkline (MIT license, ~1KB minified, zero dependencies). Vendor it to `web/static/sparkline.js`. Include via `<script src="/static/sparkline.js"></script>` in `dashboard.html`.

**Usage:**

```html
<svg class="price-sparkline" width="200" height="40" stroke-width="2"></svg>
```

```js
// series from /api/price-history, reversed to ascending time order
const values = series.map(s => s.price_dollars).reverse();
if (values.length > 0) {
  sparkline(svgEl, values);
}
```

Render one sparkline per item in the items table. Empty series: show placeholder text, do not call `sparkline()`.

**Alternative (server-side SVG, zero JS):** Generate sparkline `<polyline>` in Jinja2 using a custom template filter that normalizes the price series to SVG coordinates. Avoids even the vendored JS file. Downsides: Jinja2 math for coordinate normalization is verbose (min/max/normalize across a series); chart is static (no hover tooltip). Recommend vendored JS as the simpler path given the existing inline-JS pattern in `dashboard.html`.

## Data Flow

### SSE Push Flow

```
BotService daemon thread (owns its own asyncio loop)
  |
  | get_status() -> {"running": bool, "uptime_secs": float, "plugins": {...}}
  | [in-memory read, no blocking, thread-safe read of HealthRegistry deep copy]
  |
  v
uvicorn event loop
  |
  | _poll_loop() -- background task on uvicorn's loop
  | await asyncio.to_thread(svc.get_status)  -- offloads to thread-pool worker
  |
  v
SseHub.broadcast({"type": "status", "data": status_dict})
  |
  | iterates set of asyncio.Queue objects (all in uvicorn loop)
  | queue.put_nowait(payload)
  |
  v
SSE generator for each client
  | await asyncio.wait_for(queue.get(), timeout=15)
  | yields "data: {...}\n\n"
  |
  v
Browser EventSource
  | msg.type === "status" -> updateStatusUI()
  | msg.type === "log"    -> appendLogLines()
```

### Log Tail Flow

```
Log file (logs/YYYYMONTHDD.log) -- sync writes by bot via writeLog()
  |
  v
_poll_loop():
  await asyncio.to_thread(tail_log_lines, cursor)
  -> (new_lines, new_cursor)
  |
  v
SseHub.broadcast({"type": "log", "data": new_lines})  [if new_lines]
  |
  v
Browser: appends lines to log <pre>; trims to last 500 lines to cap DOM size
```

### Price History Flow

```
Browser -- on page load, per item in items list
  |
  | fetch GET /api/price-history/{link_b64}
  v
web/routes/api.py
  | await asyncio.to_thread(get_price_history_sync, link, 100)
  v
SQLite price_history table (WAL, existing connection pattern)
  |
  v
JSON {series: [{price_cents, price_dollars, currency, scraped_at}, ...]}
  |
  v
Browser: sparkline(svgEl, series.map(s => s.price_dollars).reverse())
```

### Theme Init Flow (prevents FOUC)

```
Browser parses <head>
  |
  v
Inline <script> executes synchronously:
  localStorage.getItem("theme") -> if set, document.documentElement.dataset.theme = value
  |
  v
Browser issues requests for tokens.css, components.css, dashboard.css
  tokens.css: html[data-theme="dark"] block already matches if dark was stored
  |
  v
First paint uses correct token values -- no flash of wrong theme
```

## Scaling Considerations

This is a single-user localhost dashboard; scaling is not a design concern. The SseHub `set` holds queues for open browser tabs (typically 1-2). The 1s poll interval is appropriate for operational monitoring. All poll reads (`get_status`, `tail_log_lines`) complete in microseconds to low milliseconds.

## Anti-Patterns

### Anti-Pattern 1: Pushing from BotService's Thread Directly to asyncio.Queue

**What people do:** Call `queue.put_nowait(payload)` from the bot daemon thread, or use `loop.call_soon_threadsafe(queue.put_nowait, payload)` targeting uvicorn's loop from the bot thread.

**Why it's wrong:** `asyncio.Queue` is NOT thread-safe (Python stdlib docs). Direct cross-thread `put_nowait` is a race condition. `call_soon_threadsafe` would work but requires the bot thread to hold a reference to uvicorn's event loop AND the specific client queues -- tight coupling with no benefit, and breaks when the bot is stopped (`self._loop` is `None`).

**Do this instead:** Uvicorn's background `_poll_loop` task reads state via `asyncio.to_thread(svc.get_status)` and distributes to all queues. The bot thread is never aware of SSE infrastructure.

### Anti-Pattern 2: Monolithic Token+Component+Layout in One CSS File

**What people do:** Add `:root { --color-bg: ... }` at the top of `dashboard.css` and keep everything in one file.

**Why it's wrong:** File grows past 300 lines; tokens and component rules are entangled; future theme changes require reading the whole file to find the tokens. The split costs nothing (no build step) and isolates each concern.

**Do this instead:** Three-file split. `tokens.css` only has `:root { --xxx: ... }` blocks. `components.css` only references `var(--xxx)`. `dashboard.css` only has layout and `@import` statements.

### Anti-Pattern 3: Blocking uvicorn's Event Loop in the SSE Generator or Poll Task

**What people do:** Call `svc.get_status()` or `path.read_text()` directly inside the async `_poll_loop` or SSE generator without `asyncio.to_thread()`.

**Why it's wrong:** Even microsecond-level sync calls accumulated across many poll cycles contribute to event loop latency. File reads under OS file cache miss can take milliseconds. This stalls all concurrent requests and SSE streams.

**Do this instead:** `await asyncio.to_thread(svc.get_status)` and `await asyncio.to_thread(tail_log_lines, cursor)` for every sync call in async context.

### Anti-Pattern 4: Multiple SSE Endpoints (One Per Data Type)

**What people do:** Create `/api/events/status`, `/api/events/logs`, `/api/events/health` as separate EventSource connections.

**Why it's wrong:** Browsers limit concurrent connections per origin (6 for HTTP/1.1, 100 for HTTP/2). Multiple SSE connections from a single page consume connection budget and complicate reconnect logic.

**Do this instead:** Single `/api/events` endpoint with a `type` discriminator in the JSON payload. Browser handler dispatches on `msg.type`. Use named SSE events (`event: status\ndata: ...\n\n`) if per-type filtering at the EventSource API level is desired.

### Anti-Pattern 5: Using `fastapi.sse.EventSourceResponse` at FastAPI 0.115

**What people do:** `from fastapi.sse import EventSourceResponse` based on current FastAPI docs.

**Why it's wrong:** `fastapi.sse` module does not exist in FastAPI 0.115.8 (verified against package `__init__.py`). It was introduced in FastAPI 0.135.0. This import raises `ImportError` at startup.

**Do this instead:** `StreamingResponse(generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})`. No extra dependency needed.

### Anti-Pattern 6: Inline FOUC-Prevention Script After the CSS Link Tags

**What people do:** Put the theme-init `<script>` at the bottom of `<head>` or in `<body>` after the CSS links.

**Why it's wrong:** CSS link tags are render-blocking but the browser begins applying styles as soon as the CSS downloads. If the script runs after style application begins, `data-theme` attribute may not be set in time to suppress the flash.

**Do this instead:** Inline `<script>` as the FIRST child of `<head>`, before any `<link>` or `<meta>` tags other than `<meta charset>`. The script is inline (not `src=`, not `type="module"`, not `defer`), so it executes synchronously during HTML parse before the browser requests any CSS.

## Integration Points

### New vs Modified Components

| Component | Status | What Changes |
|-----------|--------|--------------|
| `web/routes/sse.py` | NEW | `/api/events` StreamingResponse endpoint |
| `web/sse_hub.py` | NEW | SseHub class; `_poll_loop` background coroutine |
| `web/static/tokens.css` | NEW | All CSS custom property declarations, light+dark |
| `web/static/components.css` | NEW | All component rules consuming token vars |
| `web/static/sparkline.js` | NEW | Vendored MIT sparkline (~1KB, fnando/sparkline) |
| `web/templates/dashboard.html` | MODIFIED | Health cards section; run-history table; price charts section; log viewer filter UI; EventSource client; inline theme-init script in head |
| `web/routes/api.py` | MODIFIED | Add `/api/history` and `/api/price-history/{link_b64}` |
| `web/log_reader.py` | MODIFIED | Add `read_logs_filtered()` and `tail_log_lines()` |
| `web/__init__.py` | MODIFIED | Lifespan context; SseHub on app.state; include sse_router |
| `pyproject.toml` | UNCHANGED | No new deps; raw StreamingResponse needs nothing beyond existing FastAPI+uvicorn |
| `models.py` | UNCHANGED | No schema changes; existing functions cover all queries |
| `BotService` / `HealthRegistry` | UNCHANGED | Read-only surface is already sufficient |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Bot daemon thread to uvicorn SSE | uvicorn-side `asyncio.to_thread(svc.get_status)` poll; bot thread never touches queues | The central architectural risk; resolved by making uvicorn the sole owner of all SSE state |
| SseHub to SSE generator | `asyncio.Queue` per client; `put_nowait` from poll task; `await queue.get()` in generator | Entirely within uvicorn event loop; no thread crossing |
| api.py history routes to SQLite | `get_db_connection()` via `asyncio.to_thread()` | WAL mode handles concurrent reads; existing connection pattern |
| log_reader tail to log file | sync file read via `asyncio.to_thread()` in poll loop | File written by bot's `writeLog()`; safe to read concurrently (no file lock contention under WAL analogy) |
| Browser to `/api/events` | `EventSource` with JSON multiplex on `type` field | Replaces `setInterval` poll; auto-reconnects on disconnect |
| Browser to `/api/price-history` | One-time `fetch` per item on page load | Not SSE; price data does not change frequently enough to push |
| Theme toggle to CSS | `localStorage` + `document.documentElement.dataset.theme` + `[data-theme="dark"]` CSS selector | No server involvement; pure client-side; inline script prevents FOUC |

## Build Order (Dependency-Ordered)

Five sequential phases. Each is independently testable before the next begins.

**Phase A: Design System (no backend dependencies)**

Build first. All subsequent HTML work depends on a stable token/component layer. Zero Python changes.

1. Author `tokens.css`: `:root { --color-bg: ...; --color-surface: ...; ... }` for light; override block under `@media (prefers-color-scheme: dark)` and `html[data-theme="dark"]`.
2. Author `components.css`: migrate all non-layout rules from `dashboard.css` to component classes using `var(--xxx)`.
3. Reduce `dashboard.css` to layout rules + two `@import` lines.
4. Add inline theme-init `<script>` as first child of `<head>` in `dashboard.html`.
5. Vendor `sparkline.js` to `web/static/sparkline.js`.
6. Test: open dashboard; confirm all existing sections render identically; toggle dark/light in DevTools preferences; verify no FOUC on page reload with dark preference stored.

Deliverable: design system stable; existing dashboard unchanged in behavior.

**Phase B: New Read-Only API Endpoints (backend, no SSE)**

Build second. Independent of SSE; testable with curl before any frontend work.

1. Add `GET /api/history` to `web/routes/api.py` (confirmed orders query, wrapped in `asyncio.to_thread`).
2. Add `GET /api/price-history/{link_b64}` to `web/routes/api.py` (delegates to `get_price_history_sync`).
3. Extend `web/log_reader.py` with `read_logs_filtered()`.
4. Add optional `?level=&plugin=&search=&n=` query params to existing `GET /api/logs` endpoint.
5. Test: `curl http://localhost:8000/api/history` returns `{"confirmed_orders": [...]}`. `curl http://localhost:8000/api/price-history/{b64}` returns series or empty array. Verify `GET /api/logs?level=ERROR` filters correctly.

Deliverable: all read-only observability data available via HTTP.

**Phase C: SSE Infrastructure (backend, no frontend consumption)**

Build third. Highest-risk component; validate in complete isolation before wiring browser.

1. Author `web/sse_hub.py` (`SseHub` class + `broadcast()` method + `_poll_loop` coroutine).
2. Extend `web/log_reader.py` with `tail_log_lines(after_line)`.
3. Author `web/routes/sse.py` (`GET /api/events` endpoint with per-client queue).
4. Add `lifespan` context manager to `web/__init__.py`; attach `SseHub` to `app.state.sse_hub`; create `_poll_loop` task.
5. Register `sse_router` in `create_app()`.
6. Test: `curl -N http://localhost:8000/api/events` -- verify `data:` frames arrive every ~1s; start/stop bot via existing controls and verify `status.running` flips in SSE stream; tail test `echo "test line" >> logs/*.log` and verify it appears in the log-type SSE event; disconnect curl and verify queue is removed from hub (confirm via log line or test).

Deliverable: SSE infrastructure validated; browser not yet involved.

**Phase D: Frontend Observability Surfaces**

Build fourth, consuming Phase A (design system tokens) and Phase B (API endpoints). Does not yet wire EventSource.

1. Add health cards section to `dashboard.html`: iterate `status.plugins` using a `fetch('/api/status')` call on load; render one card per plugin with status badge, heartbeat age, consecutive errors, orders confirmed count. Style with Phase A component classes.
2. Add run history section: `fetch('/api/history')` on load; render table of confirmed orders.
3. Add price history section: for each item loaded via `fetch('/api/items')`, fetch `/api/price-history/{link_b64}`; call `sparkline(svgEl, values)` if series non-empty; show placeholder text if empty.
4. Add log viewer filter controls: level `<select>`, plugin `<input>`, search `<input>`; wire to `GET /api/logs?level=...` on submit; render filtered results in the existing log `<pre>`.
5. All sections use Phase A component classes.
6. Test: visual review; verify health cards reflect `get_status()` data; run history shows BUY-04 records; price chart renders for Amazon items; filter narrows log output.

Deliverable: all four observability surfaces rendered, still driven by one-shot fetch.

**Phase E: SSE Client Wiring (replace poll)**

Build last. Modifies existing behavior; safest to do after all other surfaces are validated.

1. Replace `setInterval(pollStatus, 2000)` and `setInterval(pollLogs, 2000)` with a single `EventSource('/api/events')` handler that dispatches on `msg.type`.
2. Add `EventSource` unavailability guard: `if (typeof EventSource === 'undefined') { /* fallback setInterval */ }`.
3. Update health cards to re-render on each `type === "status"` SSE event (not just on page load).
4. Update log panel to append lines from `type === "log"` SSE events; trim DOM to last 500 lines.
5. Test: DevTools Network tab shows one persistent `text/event-stream` connection replacing the two polling requests; status dot updates within 1-2s of bot start/stop; log lines appear in real time; close and reopen tab to verify EventSource reconnects cleanly.

Deliverable: live-push operational; 2s poll eliminated for all browsers with EventSource support (all modern browsers since 2012).

## Key Architectural Risk: Daemon Thread / uvicorn Event Loop Boundary

**Risk:** Writing to `asyncio.Queue` from the BotService daemon thread would be a race condition that corrupts queue state. The two asyncio loops (bot's vs uvicorn's) are completely independent and cannot share primitives.

**Resolution:** The uvicorn-side `_poll_loop` background task is the SOLE producer of SSE events. It reads bot state via `asyncio.to_thread(svc.get_status)`, which safely executes the sync call on a thread-pool worker and returns the result to uvicorn's loop. The bot thread is never involved in SSE delivery. The boundary is clean: bot thread writes to `HealthRegistry` (in-memory dict), uvicorn's `_poll_loop` reads it through `get_status()` on a scheduled interval.

`get_status()` is confirmed safe for this pattern: it is non-blocking, in-memory only, and `HealthRegistry.get_snapshot()` returns a deep copy. No additional locking is required.

## Sources

- FastAPI 0.115.8 `__init__.py` (verified directly: no `fastapi.sse`, no `EventSourceResponse` at this version)
- Python stdlib docs: `asyncio.Queue` is not thread-safe; `loop.call_soon_threadsafe()` required for thread-to-loop scheduling
- Python stdlib docs: `asyncio.to_thread()` for running sync callables from async context without blocking the event loop (Python 3.9+)
- FastAPI docs: `asyncio.to_thread()` recommended for blocking calls in async endpoints
- `web/__init__.py`: `create_app()` factory pattern verified; StaticFiles mount, router includes
- `web/routes/api.py`: existing endpoint patterns, CSRF dependency, JSONResponse usage
- `web/log_reader.py`: existing `read_recent_logs()` implementation and log path format
- `web/static/dashboard.css`: 182-line existing file; all non-layout content to migrate to components.css
- `web/templates/dashboard.html`: existing 4-section layout, inline JS poll pattern to replace
- `core/service.py`: `get_status()` confirmed in-memory only; `self._loop` lifecycle (None when bot stopped); daemon thread + own asyncio loop architecture
- `core/health.py`: `get_snapshot()` confirmed returns deep copy with `_`-prefixed private keys stripped
- `models.py`: `price_history` table schema confirmed; `get_price_history_sync()` signature; `order_id`/`confirmed_at`/`checkout_attempts` columns confirmed from v4.0 BUY-04
- `pyproject.toml`: FastAPI 0.115.8 + uvicorn 0.30.6 in `[web]` optional extras
- MDN: `EventSource` API; `prefers-color-scheme` CSS media feature; CSS custom property cascade
- fnando/sparkline GitHub: MIT license, ~1KB minified, zero-dep vanilla JS, `sparkline(svgEl, values)` API

---
*Architecture research for: ShopPyBot v4.1 Dashboard & Observability*
*Researched: 2026-06-25*
