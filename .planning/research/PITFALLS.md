# Pitfalls Research: v4.1 Dashboard & Observability

**Domain:** Adding SSE live-push, dependency-free charts, vendored design system, and
log-viewer filtering/tailing to an existing FastAPI localhost dashboard that runs alongside
a BotService daemon thread with its own asyncio event loop.
**Researched:** 2026-06-25
**Confidence:** HIGH for SSE/asyncio interaction patterns (directly traceable to
`core/service.py` and existing `web/` code). HIGH for XSS/log-injection (standard
DOM/security patterns). MEDIUM for FOUC specifics (browser-dependent timing).
**Supersedes:** v4.0 PITFALLS.md for v4.1 scope only. v4.0 pitfalls (double-buy,
idempotency, CVV logging, asyncio write-queue) remain in force and are not repeated here.

---

## Critical Pitfalls

### Pitfall 1 [HIGHEST RISK]: BotService-Thread SSE Bridge Blocks Uvicorn's Event Loop

**What goes wrong:**
`BotService.start()` launches a daemon thread that creates its own `asyncio` event loop
(`asyncio.new_event_loop()`, stored as `self._loop`) and runs `async_main` inside it.
Uvicorn runs its own event loop on the main thread. An SSE generator that directly calls
any BotService method which blocks — or tries to `await` something on the wrong loop —
will hang uvicorn's event loop, freezing all other HTTP requests, the status API, and
the dashboard page load.

Specific failure modes in this codebase:

1. `get_status()` is already non-blocking (in-memory reads only) — safe to call from the
   SSE generator on uvicorn's loop. Do NOT change it to do I/O.
2. Any new health/heartbeat data that requires calling into the BotService thread's loop
   (e.g., `loop.call_soon_threadsafe(...)` with a `Future` that the generator `await`s)
   needs careful bridge plumbing. Awaiting a `concurrent.futures.Future` or a
   `threading.Event` inside an `async def` generator on uvicorn's loop is safe only if
   done via `asyncio.get_event_loop().run_in_executor()` or `asyncio.to_thread()` — NOT
   via bare `await future`.
3. SQLite reads for price history or order records inside the SSE generator must use
   `await asyncio.to_thread(...)` — sqlite3 is synchronous and will block uvicorn's loop
   if called directly.
4. `read_recent_logs()` in `web/log_reader.py` does `log_path.read_text(...)` — a
   synchronous filesystem call. In the existing 2s poll route it barely matters; inside a
   persistent SSE generator it runs on every push event and blocks the loop each time.

**Why it happens:**
Developers see `svc.get_status()` is already called in `async def get_status(request)` in
`api.py` and assume any BotService call is safe. The safe ones happen to be in-memory only.
The SSE generator looks like just another async route so the loop-blocking rule isn't obvious.

**How to avoid:**
- Keep the SSE generator's data-gathering to: (a) in-memory reads from `get_status()` as-is,
  (b) DB reads wrapped in `await asyncio.to_thread(...)`, (c) log reads wrapped in
  `await asyncio.to_thread(read_recent_logs, n)`.
- The SSE bridge to BotService's thread loop is best implemented as a thread-safe queue:
  BotService thread puts status snapshots/log lines into a `queue.Queue` (or
  `asyncio.Queue` bridged via `loop.call_soon_threadsafe`); the SSE generator drains it
  with `await asyncio.to_thread(q.get, timeout)`. Never directly `await` anything on the
  bot's private loop from uvicorn's loop.
- Write a test that starts uvicorn, opens an SSE connection, and asserts that `/api/status`
  still responds in under 200ms while SSE is streaming.

**Warning signs:**
- Dashboard page hangs on load when the SSE connection is open.
- `/api/status` poll stops responding while SSE is connected.
- Python warning: `coroutine was never awaited` or `Future attached to different event loop`.

**Phase to address:** SSE phase (first SSE phase in v4.1).

---

### Pitfall 2 [HIGHEST RISK]: XSS via Untrusted Strings in DOM-Built Log/Chart HTML

**What goes wrong:**
`dashboard.html` already has one live XSS vector: `loadItems()` does:

```js
tr.innerHTML = `<td>${item.name}</td><td>${item.link}</td>...`;
```

`item.name` and `item.link` come from the DB (user-supplied at add time) without escaping.
An item name of `<img src=x onerror=alert(1)>` executes immediately on `loadItems()`.
The v4.1 features add more surfaces for the same mistake:

- **Log viewer:** Log lines written by `writeLog()` include user-controlled data:
  item names, URLs, plugin names, and exception messages. Rendering log lines via
  `innerHTML` or `insertAdjacentHTML` without sanitization is an instant XSS sink.
- **Price-history charts:** Chart labels use item names. Any SVG/canvas label built via
  string concatenation into `innerHTML` with an unsanitized item name is an XSS sink.
- **Health cards:** Plugin names and last-error strings (from `get_status()`) rendered
  with `innerHTML` are the same risk.
- **Inline SVG charts:** SVG rendered via `innerHTML = '<svg>...' + itemName + '...'`
  is a well-known XSS vector; SVG can execute `<script>` and event handlers.

**Why it happens:**
The pattern `element.innerHTML = \`<td>${data}</td>\`` is the path of least resistance for
dynamic DOM. The existing dashboard already uses it (line 241 in `dashboard.html`). Adding
new features copies the pattern without recognizing it as dangerous.

**How to avoid:**
- Use `document.createElement` + `element.textContent = value` for all data from the API.
  `textContent` never interprets HTML. This is the correct pattern already present in the
  credential and config sections of the dashboard.
- For the log viewer: `pre.textContent = lines.join('\n')` — never `innerHTML`.
- For SVG charts built as strings: escape all user data with a dedicated helper before
  interpolation:
  ```js
  function escHtml(s) {
    return String(s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;')
      .replace(/'/g,'&#39;');
  }
  ```
  Never build SVG strings without passing every user-controlled value through `escHtml`.
- Fix the existing `item.name`/`item.link` `innerHTML` XSS in `loadItems()` in the same
  phase — do not leave a known hole open while adding new surfaces.
- Add a CI assertion: scan `dashboard.html` (and any new template files) for
  `innerHTML` assignments that reference API response data. Flag for manual review.

**Warning signs:**
- Item names with `<` or `>` in the DB display as broken HTML or trigger browser errors.
- A log line containing `<script>` causes unexpected console output.
- Any `innerHTML` assignment that receives a string derived from DB/API data.

**Phase to address:** Design system / template phase (fix existing `loadItems()` XSS at
the same time the new log viewer and chart templates are built).

---

### Pitfall 3: SSE Generator Leaks on Client Disconnect

**What goes wrong:**
FastAPI SSE generators using `EventSourceResponse` (from `sse-starlette`) or a raw
`StreamingResponse` keep the generator alive until the server explicitly checks whether
the client is still connected. If the client tab closes or the browser refreshes, the
generator continues running indefinitely: reading logs, calling `get_status()`, and holding
an open HTTP connection. Under the localhost single-user model this is low risk for resource
exhaustion, but it causes log reads and DB queries to continue running after the user has
left the page, and on bot restart the accumulated stale generators can cause surprising
behavior.

**Why it happens:**
SSE is a one-way push; the server has no synchronous signal of client disconnect. FastAPI's
`request.is_disconnected()` must be polled explicitly inside the generator. Developers write
`while True: yield event; await asyncio.sleep(1)` and forget the disconnect check.

**How to avoid:**
```python
async def status_stream(request: Request):
    while True:
        if await request.is_disconnected():
            break
        data = svc.get_status()
        yield f"data: {json.dumps(data)}\n\n"
        await asyncio.sleep(1)
```
Wrap the entire generator body in a `try/finally` block that logs generator exit so
disconnect detection can be verified in testing. Use a short sleep (1-2s) so the disconnect
poll runs frequently.

**Warning signs:**
- Server log shows active generators after browser tab is closed.
- Memory or file handle count grows over time with repeated dashboard opens/closes.
- `asyncio` task list shows stale SSE tasks that should have cleaned up.

**Phase to address:** SSE phase.

---

### Pitfall 4: SSE Without Heartbeat Causes Proxy/Browser Timeout

**What goes wrong:**
When the bot is stopped (`get_status().running == False`), status changes infrequently.
If the SSE connection sends no data for 30-60 seconds, many HTTP proxies (nginx, Caddy,
any reverse proxy the user might put in front) and some browsers will close the connection
as idle. The client receives a silent disconnect and falls back to polling (or worse, shows
a stale state forever). For a localhost-only app this is less likely but remains a real
failure mode for users who route through any local proxy or use Firefox which has tighter
SSE timeout behavior.

**Why it happens:**
SSE streams that only emit on state changes have natural quiet periods. A "comment" keepalive
is specified in the SSE spec but is easy to omit.

**How to avoid:**
Emit an SSE comment line every 15-20 seconds regardless of data changes:
```python
yield ": keepalive\n\n"  # SSE comment; ignored by EventSource but resets proxy timers
```
The `EventSource` spec requires browsers to auto-reconnect after disconnect, but the
keepalive prevents unnecessary reconnection churn.

**Warning signs:**
- SSE stream silently drops after ~30s of no bot activity.
- Browser network tab shows SSE connection closed then immediately reopened.
- Dashboard shows stale "Running" state because the last event was before a stop.

**Phase to address:** SSE phase.

---

### Pitfall 5: No Client-Side SSE Reconnect Backoff

**What goes wrong:**
The browser's native `EventSource` will auto-reconnect on disconnect, but it retries
immediately by default (or after a short browser-set interval). If the server is
temporarily unavailable (restart, `uvicorn` reload during development) and the client
reconnects in a tight loop, server logs fill with rapid connection attempts and any
startup work (DB init, registry load) competes with reconnection traffic. This is minor
for localhost but still creates confusing logs during development.

**Why it happens:**
`new EventSource('/api/sse/status')` reconnects automatically with no application control
over retry timing. Developers don't realize the browser handles reconnection.

**How to avoid:**
Use `retry:` field in the SSE stream to set a reconnect interval (in milliseconds):
```python
yield "retry: 3000\n\n"  # tell browser to wait 3s before reconnecting
```
Send this once at stream open. The browser honors it for all subsequent reconnects.
For the client-side implementation, do not add a manual `EventSource` close/reopen loop
on top of the native reconnect — it creates double-reconnect behavior.

**Warning signs:**
- Server access log shows `/api/sse/status` being hit many times per second after a
  server restart.
- Two or more SSE connections open simultaneously from the same browser tab.

**Phase to address:** SSE phase.

---

### Pitfall 6: Unbounded Log Memory in the Tailing Log Viewer

**What goes wrong:**
The current `read_recent_logs(n=50)` reads the entire log file into memory with
`log_path.read_text(...)` then slices the last `n` lines. On a long unattended run the
daily log file can grow to many megabytes. Reading the entire file on every SSE push
event (every 1-2 seconds) means: (a) the entire file is read into memory repeatedly,
(b) uvicorn's loop is blocked on that I/O (see Pitfall 1), (c) on very large logs the
SSE event payload itself becomes large.

For the tailing log viewer with SSE, a naive "push the last 50 lines" approach is also
semantically wrong: every 1-2s the full tail is re-sent rather than just new lines,
causing the viewer to show duplicate content or flash on updates.

**Why it happens:**
`read_recent_logs` was designed for the 2s poll endpoint — it reads all and slices. Reusing
it verbatim for SSE continuous tailing inherits both the full-file read and the
"send all 50 again" semantics.

**How to avoid:**
- For SSE log tailing: maintain a cursor (byte offset or line count) in the generator's
  local state. On each tick, open the file, seek to the cursor, read only new bytes, update
  the cursor. Only emit lines that are genuinely new.
- Wrap all file I/O in `await asyncio.to_thread(...)` (see Pitfall 1).
- Cap the maximum lines sent in a single SSE event (e.g., 100 new lines). If a burst of
  logging produces 10,000 lines between two ticks, send the last 100 and advance the
  cursor past all of them.
- For the initial page load (HTTP endpoint, not SSE), the existing `read_recent_logs(50)`
  pattern is fine. The SSE-specific tailing path needs a separate implementation.

**Warning signs:**
- Server memory usage grows steadily during a bot run.
- SSE event payload size grows over the run duration.
- The log viewer flashes or shows the same lines repeated every few seconds.

**Phase to address:** Log viewer phase.

---

### Pitfall 7: Secret-Bearing Log Lines Exposed to the Browser

**What goes wrong:**
`writeLog()` in `logger.py` writes to files in `logs/YYYYMONTHDD.log`. The log reader
serves those lines to the browser via `/api/logs` (currently) and the SSE log stream
(v4.1). If any code path passes a secret-bearing string to `writeLog()`, it is on disk
and will appear in the browser's log viewer.

Known risky patterns already guarded against in v4.0:
- `_fill_field` logs `selector name only never field value` (Phase 20 decision)
- CVV: `exc.__class__.__name__` not `str(exc)` on checkout exception paths (v4.0 decision)
- `TWOCAPTCHA_API_KEY` excluded from any debug log (Phase 14 decision)

New risks introduced by v4.1:
- The log viewer with search/filter runs client-side regex over log lines already sent to
  the browser. If a secret ever reaches a log line, search/filter does not add risk — the
  secret is already in the browser. But the SSE stream pushes lines in near-real-time,
  reducing the window for a human to notice before a secret is rendered on screen.
- `get_status()` returns plugin health strings including last-error messages. If a plugin
  emits `health_degraded` with a message that includes a URL with embedded credentials
  (e.g., `http://user:pass@proxy/`) the SSE health-card push sends it to the browser.
- Price history labels (item names) in chart data could contain Unicode or control
  characters that confuse the chart renderer if not normalized.

**Why it happens:**
Log consumers (the browser) are never validated against the log producer's (BotService)
secret-safety guarantees. The `SECRET_KEYS` list in `core/credentials.py` guards env-var
reads; there is no analogous guard on log writes.

**How to avoid:**
- Extend the existing CI AST grep assertion (from v4.0, "never add CVV/CARD_NUMBER to
  SECRET_KEYS" equivalent) to also scan for `writeLog` calls whose format strings
  concatenate or format any value derived from `get_store()`, the credential store, or
  checkout profile fields.
- For `get_status()` health strings: scrub or truncate `last_error` fields at the
  `get_status()` boundary. A safe pattern: return only `exc.__class__.__name__` in the
  health surface, not `str(exc)`.
- The log viewer must NOT add any "enhance" step that joins log lines with additional data
  (config values, credential store keys). Filter/search is read-only over already-sent
  lines only.
- Document in `SECURITY.md`: "Log lines are browser-visible via the dashboard. Never log
  secret values, full URLs with embedded credentials, or card data."

**Warning signs:**
- A log line in the browser log viewer contains `password`, `token`, `key=`, `cvv`, or
  a URL with `@` (embedded credentials).
- `get_status()` response JSON in the network tab contains a stack trace or error string
  that includes a secret value.

**Phase to address:** SSE phase (add scrubbing to `get_status()` health strings) + log
viewer phase (CI assertion for log-secret policy).

---

### Pitfall 8: FOUC (Flash of Unstyled Content) During Design System Integration

**What goes wrong:**
When the vendored design system CSS is loaded via `<link rel="stylesheet">` in the `<head>`,
the browser may render the page with no styles (or old styles) for a visible flash before
the stylesheet parses. This is worse when:
- The CSS file is large (a full design system with tokens, components, utilities).
- Critical tokens (background color, text color) are defined in CSS custom properties set
  on `:root`, but the browser applies the default white background first.
- Light/dark mode is determined by `prefers-color-scheme` media query in CSS but the
  browser paints the default (light) background before the media query fires.
- The existing `dashboard.css` is replaced or extended, leaving a brief period where
  neither old nor new styles apply.

**Why it happens:**
CSS is render-blocking by default, but there is a timing window between HTML parse start
and CSS parse complete. For locally-served files this window is very short but visible on
slower machines or when the CSS is large.

**How to avoid:**
- Inline the critical CSS tokens (background color, text color, font-family) in a `<style>`
  block in `<head>` before the `<link>` tag. This sets the base appearance before the
  external stylesheet loads, eliminating the FOUC.
- For light/dark: inline a tiny `<script>` in `<head>` (before `<body>`) that reads
  `window.matchMedia('(prefers-color-scheme: dark)').matches` and sets a `data-theme`
  attribute on `<html>`. The design system's tokens then reference `[data-theme=dark]`.
  This script runs synchronously before paint, preventing a dark-mode flash.
- Do not add a `<link rel="preload">` for the design system stylesheet and then also load
  it via a second `<link rel="stylesheet">` — double-load is a common mistake.
- Migrate the existing `dashboard.css` to the new design system tokens in a single commit
  so there is no intermediate state where both old and new styles partially apply.

**Warning signs:**
- Page visibly flashes white before the background color appears.
- On dark OS settings, page loads light then immediately switches to dark.
- Layout shifts (elements repositioned) during initial load.

**Phase to address:** Design system phase.

---

### Pitfall 9: Design System Breaks the Non-Local Warning Banner and CSRF Gate

**What goes wrong:**
The `is_non_local` warning banner in `dashboard.html` is a Jinja2 conditional that renders
a `<div class="banner-warning">` when `is_non_local=True`. During design system integration:
- The `banner-warning` class may be removed or renamed, causing the banner to render
  without visible styling (invisible warning).
- A CSS reset in the design system may override the banner's colors, making a red/yellow
  warning look the same as the page background.
- Template refactoring that splits the dashboard into components may accidentally move the
  `{% if is_non_local %}` block into a component that is conditionally rendered, breaking
  the always-visible guarantee.

The CSRF `check_origin` dependency is server-side and is not affected by CSS/template
changes, but the non-local warning is the user-facing safety signal — making it invisible
is a security regression.

**Why it happens:**
Design system integration typically involves replacing all existing CSS classes. The
`banner-warning` class is a one-off in the existing `dashboard.css` and will be caught
by a global class rename pass.

**How to avoid:**
- The existing test `test_web_dashboard.py` (Phase 12-03, `MC-4`) already asserts the
  banner is present when `is_non_local=True` and absent when `False`. Run this test
  against the new template in the design system phase — do not disable or skip it.
- After design system integration, manually verify the banner is visually distinct (colored
  background, contrasting text) in both light and dark mode.
- Keep the `{% if is_non_local %}` conditional at the top level of the template body, not
  inside a component or partial that could be accidentally skipped.

**Warning signs:**
- `MC-4` test fails or is skipped after template changes.
- The banner renders but is invisible (white text on white background or similar).
- `is_non_local=True` in a non-local run shows no visible warning.

**Phase to address:** Design system phase (must be verified before the phase is closed).

---

### Pitfall 10: Sparse / Amazon-Only Price Data Produces Misleading Charts

**What goes wrong:**
The `price_history` table is populated only by the Amazon plugin today (PRICE-02 research
flag). For all other plugins, `price_history` is empty. A price-history chart that:
- Shows "No data" for 6 of 7 plugins without explanation looks broken.
- Connects sparse data points with straight lines implies continuous price stability that
  doesn't exist.
- Displays a chart X-axis with 2 data points spanning 3 months looks like the item was
  never checked.

Additionally, `get_price_history()` in `BotService` takes a `name` argument, resolves it
to a `link` via `get_items_sync()`, and then queries `price_history` by `link`. If an item
is renamed in the DB without updating `price_history.item_link`, the history becomes
unreachable via the service layer (the link is the join key, not the name).

**Why it happens:**
Chart components are typically designed with "always has data" assumptions. Sparse data
handling and empty-state UI are afterthoughts.

**How to avoid:**
- Chart empty state: show an explicit "No price history (Amazon only)" message for plugins
  other than Amazon. Do not show a blank chart area — blank looks like a rendering failure.
- For sparse Amazon data: use discrete point markers rather than a continuous line. If
  fewer than 2 points exist, show a message not a chart.
- Do not connect non-adjacent data points with a line when there are gaps longer than 24h
  — use null/gap segments in the chart rendering.
- The X-axis should auto-scale to the range of the data, not to "last 30 days" when there
  are only 2 points 3 weeks apart.
- Add a tooltip showing exact timestamp and price on hover so sparse charts are still
  informative.

**Warning signs:**
- Price chart shows a flat diagonal line for an item that was only checked twice.
- Non-Amazon plugin items show a blank chart area with no explanation.
- Item was renamed and its price history is now unreachable via the service layer.

**Phase to address:** Charts phase.

---

### Pitfall 11: SSE Route Bypasses CSRF Check

**What goes wrong:**
The existing CSRF `check_origin` dependency is applied only to state-changing routes
(`POST`, `DELETE`). `GET` routes (including SSE streams) are exempt, which is correct for
read-only data. However, the SSE route could be abused as a side-channel: a malicious page
on `localhost` (e.g., a different app bound to another localhost port) can open an
`EventSource` to the SSE endpoint and receive live status, log lines, and health data.
This is a cross-origin read, not a cross-origin write, so CSRF protections do not apply by
design — but it is still an information disclosure risk for log lines that may contain
sensitive operational data.

For localhost-only deployments this risk is low: the attacker must already have code
execution on the local machine. But it is worth understanding the boundary.

**Why it happens:**
Developers sometimes add `Depends(check_origin)` to SSE routes thinking it prevents
cross-origin reads. It does not (CSRF is for state changes). Cross-origin reads are
prevented by CORS headers, not CSRF checks. FastAPI adds permissive CORS by default
(no `CORSMiddleware` installed = browser's default same-origin policy applies). The
browser's `EventSource` does follow CORS, so a cross-origin page cannot read the SSE
stream unless the server sends `Access-Control-Allow-Origin`. The existing app does not
add CORS middleware, so the browser's same-origin policy blocks cross-origin SSE reads
— this is the correct posture for localhost.

**How to avoid:**
- Do NOT add `Depends(check_origin)` to SSE `GET` routes. It does not help and adds
  latency to every SSE event.
- Do NOT add a blanket `CORSMiddleware` with `allow_origins=["*"]` for the SSE route —
  that would undo the browser's same-origin protection.
- The correct security posture is already in place (no CORS middleware = browser
  same-origin blocks cross-origin reads). Document this in a code comment on the SSE
  route so future maintainers do not "fix" it by adding CORS.
- If the non-local warning banner is active (`is_non_local=True`), log a WARNING at server
  start that the SSE stream is accessible from non-localhost origins.

**Warning signs:**
- `CORSMiddleware` added to `create_app()` with `allow_origins=["*"]`.
- `Depends(check_origin)` added to the SSE GET route (harmless but misleading).
- Server binds to `0.0.0.0` without `is_non_local=True` being set.

**Phase to address:** SSE phase (add code comment documenting why no CSRF on SSE GET).

---

### Pitfall 12: Log Injection via Crafted Log Lines

**What goes wrong:**
Log lines written by `writeLog()` include user-controlled data (item names, URLs, plugin
error messages). The log format is:
```
[LEVEL][YYYYMonthDD@HH:MM:SS] message
```
An item name of `\n[ERROR][2026June25@12:00:00] Fake error injected` would write a second
fake log line to the log file. When served to the browser log viewer, this fake line is
visually indistinguishable from a real log line. This is log injection.

In the context of this application the practical risk is low (the attacker must control
an item name in the local SQLite DB, which requires local access), but the browser log
viewer increases the surface: previously log injection only affected the file and terminal;
now it affects what the user sees in the dashboard, potentially causing them to act on
fake status messages.

**Why it happens:**
Log message sanitization is often omitted when the log is only machine-readable. A
browser-rendered log viewer elevates the impact.

**How to avoid:**
- Sanitize user-controlled values before passing to `writeLog()`: strip or escape
  newlines (`\n`, `\r`) from item names, URLs, and any user-provided string that goes
  into a log message.
- In the log viewer frontend: do NOT parse log lines as structured data (do not try to
  extract level/timestamp from the raw string and re-render them with styled spans based
  on that parsed level). Parse lines only for color-coding by prefix pattern matching
  against the known `[LEVEL]` prefix — but treat the entire rest of the line as opaque
  text, never as HTML.
- The log viewer should display lines using `textContent` (see Pitfall 2), which means
  even an injected `[ERROR]` prefix renders as visible text, not as a DOM element.

**Warning signs:**
- An item name with `\n` in it produces two lines in the log file.
- The log viewer shows a log line with no corresponding entry in the raw log file.
- A crafted item name causes the log viewer to show a different level badge than the
  actual message severity.

**Phase to address:** Log viewer phase.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Reuse `read_recent_logs()` for SSE log push | Zero new code | Full file read on every SSE tick; blocks event loop; sends duplicate lines | Never — SSE tailing needs a cursor-based implementation |
| `innerHTML` for dynamic log/chart DOM | Fast to write | XSS sink for every item name, log line, plugin name | Never for data from API responses |
| Skip `is_disconnected()` check in SSE generator | Simpler generator | Leaked generators accumulate over repeated dashboard opens | Never |
| Add `CORSMiddleware(allow_origins=["*"])` "for SSE" | Unblocks exotic setups | Undoes browser same-origin protection on all routes | Never on this localhost app |
| Render SVG charts via server-side Jinja2 template | No client-side chart code | Item names in SVG must be escaped in Jinja2 (`{{ name \| e }}`); easy to forget | Acceptable only if `\| e` filter is used everywhere |
| Single `while True` SSE loop without heartbeat | Simple code | Proxy/browser drops idle connection; dashboard shows stale state | Never — always add keepalive |
| Inline all CSS in `<head>` instead of vendored file | Eliminates FOUC entirely | CSS not cacheable; template becomes enormous | Acceptable for critical-path tokens only (not the full design system) |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| SSE + BotService daemon thread | Call any blocking BotService method directly in the SSE generator's async body | Wrap all blocking calls in `await asyncio.to_thread()`; keep `get_status()` in-memory only |
| SSE + FastAPI `EventSourceResponse` | Import `sse-starlette` without checking it's in `requirements.txt`; the zero-Node constraint doesn't block Python packages | Verify package is already a dependency or explicitly add it; alternatively use raw `StreamingResponse` with `text/event-stream` content type to avoid new deps |
| SVG chart + item names | Build SVG string via `f"<text>{item_name}</text>"` | Use `escHtml()` on every interpolated value, or build SVG via `document.createElementNS` + `.textContent` |
| Log viewer + SSE | Push full 50-line tail on every tick | Maintain byte-offset cursor; push only genuinely new lines |
| Light/dark mode + `:root` tokens | Rely on CSS to prevent FOUC | Inline a synchronous `<script>` in `<head>` to set `data-theme` before first paint |
| CSRF check on SSE route | Add `Depends(check_origin)` to the GET SSE route | Leave GET SSE routes without CSRF dep; document why |
| `get_status()` health strings | Return `str(exc)` from plugin health surface | Return only `exc.__class__.__name__`; never `str(exc)` which may include secrets |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Full log file read on every SSE tick | Memory grows with log file; CPU spikes every 1-2s | Cursor-based tail; wrap in `asyncio.to_thread` | Log file > ~1MB (single-day heavy run) |
| Synchronous SQLite call in SSE generator | All HTTP requests pause during DB read | `await asyncio.to_thread(db_read_fn, args)` | Immediately under any load |
| Rendering 10,000+ SVG points for a long-running price history | Browser hangs on chart render | Cap points returned by `get_price_history(limit=200)`; down-sample in Python before sending | > ~500 data points per item |
| Sending full status object on every SSE tick regardless of change | High bandwidth; client re-renders unnecessarily | Diff state before emitting; only push when state changes or on heartbeat tick | Immediately visible in network tab |
| `EventSource` opened multiple times (e.g., `loadItems()` also polls) | Two SSE connections compete; one is stale | Open SSE once at page load; replace all polling with SSE-driven updates | Multiple event sources from same tab |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| `innerHTML` with item names / log lines / plugin health strings | XSS: arbitrary HTML/JS execution on dashboard load | `textContent` for all API-sourced strings; `escHtml()` before SVG interpolation |
| Sending `str(exc)` in health surface or SSE data | Secrets (proxy URLs with credentials, CAPTCHA API key in traceback) exposed to browser | Return `exc.__class__.__name__` only; sanitize health strings in `get_status()` |
| Log lines with unsanitized newlines from user-supplied item names | Log injection: fake log lines in dashboard viewer | Strip `\n`/`\r` from user-controlled values before `writeLog()` |
| Adding `CORSMiddleware` with `allow_origins=["*"]` to unblock SSE from other origins | Cross-origin reads of live logs and health data | Rely on browser same-origin policy; never add `allow_origins=["*"]` |
| Logging item URLs verbatim when they contain embedded credentials (e.g., proxy-augmented URLs) | Secrets in log file and browser log viewer | Log only the domain or a sanitized version of URLs |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Blank chart area for non-Amazon plugins | User thinks charts are broken | Explicit "No price data — Amazon only" empty state |
| Straight line between sparse data points | Implies continuous monitoring; misleading | Point markers only for sparse data; gap segments for multi-day gaps |
| Log viewer sends full 50-line tail every tick | Lines repeat; viewer jumps to top on each update | Append-only update with cursor; scroll position preserved |
| No visual feedback that SSE is connected vs. polling | User cannot tell if data is live | Show "Live" / "Reconnecting" indicator driven by SSE `open`/`error` events |
| Dark-mode flash on page load | Jarring transition; looks broken | Synchronous `<script>` in `<head>` sets `data-theme` before paint |
| Non-local warning banner loses styling after design system merge | Safety warning invisible | Preserve `banner-warning` class and add to design system token set; run `MC-4` test |

---

## "Looks Done But Isn't" Checklist

- [ ] **SSE generator:** Checked that `await request.is_disconnected()` is called in the
      loop body — verify by closing browser tab and confirming server log shows generator
      exit.
- [ ] **SSE keepalive:** Confirmed a `: keepalive\n\n` comment is emitted every ~15s —
      verify by watching network tab for 30s with no bot activity.
- [ ] **Log viewer tailing:** Confirmed lines are not duplicated on successive SSE ticks —
      open log viewer, trigger a bot action, confirm each line appears exactly once.
- [ ] **XSS — item names:** Add an item named `<b>bold</b>` and confirm it renders as
      literal text `<b>bold</b>` in the items table, log viewer, and chart labels.
- [ ] **XSS — log lines:** Write a log line containing `<script>alert(1)</script>` (via
      a test item name in test mode) and confirm it renders as text in the log viewer.
- [ ] **Non-local banner:** Start the server with `--host 0.0.0.0` and confirm the
      banner is visible and styled in both light and dark mode.
- [ ] **`MC-4` test:** Runs and passes after all template changes.
- [ ] **Price chart empty state:** Add a Walmart item (no price history) and confirm an
      explicit empty-state message appears instead of a blank chart.
- [ ] **Secrets in health surface:** Trigger a plugin health-degraded event and confirm
      `get_status()` response JSON contains no URLs, no `str(exc)` values, only class
      names and timestamps.
- [ ] **Event loop not blocked:** While SSE is streaming, confirm `/api/status` HTTP
      endpoint responds in < 200ms via curl/network tab.
- [ ] **FOUC:** Load dashboard on a slow machine or with CPU throttling in devtools and
      confirm no white flash before background color appears.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| SSE generator blocks uvicorn loop | HIGH — all HTTP frozen | Kill uvicorn; move blocking call to `asyncio.to_thread()`; restart |
| XSS via innerHTML | MEDIUM — template change + test | Replace `innerHTML` with `createElement`/`textContent`; regression test |
| Leaked SSE generators | LOW — restart uvicorn | Add `is_disconnected()` check; generators clean up on next server restart |
| FOUC | LOW — CSS fix | Inline critical tokens in `<head> <style>`; redeploy |
| Banner invisible after design system | LOW — CSS fix | Restore `banner-warning` token; re-run `MC-4` test |
| Log viewer showing duplicate lines | LOW — cursor fix | Implement byte-offset cursor in SSE tail path |
| Secrets in SSE health data | HIGH — audit required | Audit all `get_status()` return values; scrub `last_error` fields; rotate any exposed secrets |
| Log injection via item names | LOW — sanitization fix | Add `\n`/`\r` stripping in `writeLog()` call sites; re-test log viewer |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1: Cross-loop SSE bridge blocks uvicorn | SSE phase | Run `/api/status` while SSE stream open; assert < 200ms response |
| 2: XSS via innerHTML in log/chart DOM | Design system + log viewer phase (fix existing `loadItems()` XSS simultaneously) | Add item with `<b>` in name; confirm literal text in all renderers |
| 3: SSE generator leak on disconnect | SSE phase | Close browser tab; confirm server log shows generator exit |
| 4: No heartbeat causes proxy timeout | SSE phase | Watch network tab for 30s idle; confirm keepalive comment sent |
| 5: No SSE reconnect backoff | SSE phase | Restart server; confirm EventSource waits 3s before reconnect |
| 6: Unbounded log read for tailing | Log viewer phase | Monitor memory during 1h bot run; confirm no growth |
| 7: Secrets in log lines reach browser | SSE + log viewer phase | Inspect SSE data frames for no credential-pattern strings |
| 8: FOUC on design system load | Design system phase | CPU-throttle in devtools; confirm no visible flash |
| 9: Design system breaks banner/CSRF gate | Design system phase | Run `MC-4` test; verify banner styled in both themes |
| 10: Sparse price data misleading chart | Charts phase | Add non-Amazon item; confirm empty-state message, not blank chart |
| 11: SSE route CSRF misconception | SSE phase | Code review: confirm no `Depends(check_origin)` and no CORS wildcard |
| 12: Log injection via item names | Log viewer phase | Item name with `\n`; confirm single log line in file and viewer |

---

## Sources

- `core/service.py`: BotService daemon thread and event loop architecture (confirmed: `asyncio.new_event_loop()` in `_run_loop`, `self._loop` is the bot's private loop)
- `web/routes/api.py`: existing safe pattern for calling blocking BotService methods (`asyncio.to_thread(svc.start)`, `asyncio.to_thread(svc.stop)`)
- `web/log_reader.py`: confirmed `log_path.read_text(...)` is a synchronous full-file read
- `web/templates/dashboard.html` line 241: confirmed existing `tr.innerHTML` XSS in `loadItems()`
- `web/security.py`: confirmed CSRF check is `Depends(check_origin)` on POST/DELETE only; no CORS middleware in `create_app()`
- `core/credentials.py` `SECRET_KEYS`: 20 canonical secret key names; TWOCAPTCHA_API_KEY is included
- STATE.md decisions: `_fill_field` logs selector only; `exc.__class__.__name__` on checkout paths; CVV never logged
- PROJECT.md v4.1 research flags: charts dependency-free; price data Amazon-only (PRICE-02)
- FastAPI SSE patterns: `request.is_disconnected()` is the standard disconnect-check API (HIGH confidence from FastAPI docs and community patterns)
- SSE specification (RFC-based): `retry:` field controls client reconnect interval; `: comment` lines act as keepalive (HIGH confidence)

---
*Pitfalls research for: FastAPI SSE + dependency-free charts + vendored design system + log viewer on BotService daemon-thread architecture*
*Researched: 2026-06-25*
