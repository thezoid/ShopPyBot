---
phase: 28-frontend-observability-surfaces
reviewed: 2026-06-27T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - web/templates/dashboard.html
  - web/static/components.css
  - core/health.py
findings:
  critical: 3
  warning: 5
  info: 2
  total: 10
status: issues_found
---

# Phase 28: Code Review Report

**Reviewed:** 2026-06-27
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Three files implement Phase 28 observability surfaces: health cards (OBS-01/02), confirmed-buys table (OBS-04), per-item uPlot price charts (OBS-05), a log viewer with follow/filter (OBS-06/07/08), uptime display (OBS-09), and the `heartbeat_age_secs` backend field.

XSS surface is clean: every API-sourced value in `renderHealthCards`, `loadConfirmedBuys`, `appendLogLine`/`renderLogLines`, `renderUptime`, `loadCredentials`, and `loadConfig` reaches the DOM exclusively via `textContent` or `createElement`. The `innerHTML = ''` clear pattern is used acceptably on static container elements.

Three blockers were found: uPlot instances accumulate on every `loadItems()` call because `loadPriceChart` never destroys prior instances; `pollLogs` writes to the legacy `#log-content` `<pre>` on every tick (coupling two log surfaces to one fetch, and leaking unbounded text into a `<pre>`); and the `base64` encoding used for chart container IDs can produce characters illegal in HTML `id` attributes, causing silent chart-miss on any URL that encodes to a string containing `=`.

Five warnings cover: `loadItems` missing error handling; `loadConfirmedBuys` called only once (stale after first load); the DOM-cap trimming order relative to `renderLogLines` being wrong; `uPlot` loaded after the inline `<script>` block that references it; and the `heartbeat_age_secs` `None`-vs-`0.0` comparison being fragile.

---

## Critical Issues

### CR-01: uPlot instances leak on every loadItems() re-render

**File:** `web/templates/dashboard.html:643-688`

`loadItems()` is called after every add-item and remove-item operation. Each call removes the old `.item-chart-wrapper` DOM nodes (line 649-650) and creates new `#chart-<b64>` divs, then calls `loadPriceChart` for each item (line 686-688). `loadPriceChart` calls `new uPlot(opts, data, containerEl)` (line 446) unconditionally whenever series data is present, with no reference kept to prior instances and no `.destroy()` call.

Removing the container element from the DOM does not destroy the uPlot instance — uPlot holds internal timers (`requestAnimationFrame` loops) and resize observer callbacks that keep the old instance alive. After N add/remove cycles, N uPlot instances exist concurrently against detached DOM nodes. On a long-lived dashboard session this accumulates memory and orphaned RAF callbacks indefinitely.

**Fix:** Track instances by b64 key and destroy before re-creating.

```js
// Module-level map
const _chartInstances = {};

// In loadPriceChart, before `new uPlot`:
if (_chartInstances[b64]) {
  _chartInstances[b64].destroy();
  delete _chartInstances[b64];
}
// After `new uPlot`:
_chartInstances[b64] = new uPlot(opts, [ts, prices], containerEl);

// In loadItems, after removing old wrappers:
Object.keys(_chartInstances).forEach(k => {
  _chartInstances[k].destroy();
  delete _chartInstances[k];
});
```

---

### CR-02: base64 padding '=' in chart container ID is illegal and silently breaks charts

**File:** `web/templates/dashboard.html:397, 657`

`loadPriceChart` and `loadItems` both compute:

```js
const b64 = btoa(unescape(encodeURIComponent(itemLink)))
  .replace(/\+/g, '-').replace(/\//g, '_');
```

This replaces `+` and `/` (URL-safe base64 substitutions) but does NOT strip or replace `=` padding characters. The HTML `id` attribute value is then set to `'chart-' + b64` (line 680) and looked up with `document.getElementById('chart-' + b64)` (line 398).

Per HTML5, `id` values must not contain spaces, but `=` is technically allowed. However `querySelector` and `getElementById` with `=` in the id string are inconsistent across browsers and the CSS selector `#chart-abc=` is invalid (breaks uPlot's internal resize observer which uses `querySelector`). More concretely, the `data-link` attribute on `<tr>` at line 659 also stores the b64 value and is used to match rows — any mismatch causes a silent no-op chart render.

The backend uses `base64.urlsafe_b64decode` which handles padding implicitly, so the `=` padding in the key sent by the client is decoded correctly server-side. The issue is purely the DOM ID being unusable.

**Fix:** Strip `=` padding from the b64 key used for DOM IDs (and the URL path segment, which also doesn't need padding since the backend's `urlsafe_b64decode` pads implicitly):

```js
function linkToB64(link) {
  return btoa(unescape(encodeURIComponent(link)))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
}
```

Apply this helper consistently in `loadPriceChart` (line 397), `loadItems` (line 657), and `removeItem` (line 624). The backend's `urlsafe_b64decode` handles missing padding transparently.

---

### CR-03: pollLogs writes unbounded text into #log-content <pre> on every tick

**File:** `web/templates/dashboard.html:532`

Inside `pollLogs` (line 532):

```js
document.getElementById('log-content').textContent = logs.join('\n');
```

`#log-content` is the legacy `<pre>` element in the Controls card (line 55). On every 2-second tick `pollLogs` replaces that element's entire text content with up to 500 joined log lines. There is no cap on the string length written there — 500 lines of verbose trace logs could be many tens of kilobytes per tick.

This is also an architectural coupling defect: `pollLogs` is the log-viewer polling function (OBS-06) but it silently drives a second, entirely separate UI surface with no DOM-cap protection. If the legacy `#log-content` panel is intentional, it needs its own bounded update. If it is vestigial, writing to it on every tick is wasteful and confusing.

The `#log-buffer` viewer (line 180) has `renderLogLines` with the 500-child cap. The `<pre>` does not.

**Fix option A (remove legacy surface):** Delete line 532. The log viewer section already provides the correct bounded display.

**Fix option B (bound it):** Replace line 532 with a capped version:
```js
document.getElementById('log-content').textContent = logs.slice(-50).join('\n');
```

---

## Warnings

### WR-01: loadItems has no error handling — unhandled rejection crashes the call chain

**File:** `web/templates/dashboard.html:643-689`

```js
async function loadItems() {
  const resp = await fetch('/api/items');   // no try/catch
  const data = await resp.json();           // no try/catch
  ...
}
```

Any network error or non-JSON response causes an unhandled promise rejection. Because `loadItems` is called from the add-item form submit handler (line 613) and `removeItem` (line 626) via `await`-less fire-and-forget calls, rejections are silently swallowed in some browsers and visible as unhandled rejection warnings in others. The user sees no feedback. All other load functions (`loadCredentials`, `loadConfig`, `loadConfirmedBuys`) have try/catch — `loadItems` is inconsistently unguarded.

**Fix:** Wrap in try/catch matching the pattern used by `loadConfirmedBuys`:
```js
async function loadItems() {
  try {
    const resp = await fetch('/api/items');
    const data = await resp.json();
    ...
  } catch (e) {
    // surface error in tbody
  }
}
```

---

### WR-02: loadConfirmedBuys called only once — table goes stale after a buy occurs

**File:** `web/templates/dashboard.html:838`

`loadConfirmedBuys()` is called once at page load (line 838) and never again. `pollStatus` (called every 2 seconds) calls `renderHealthCards` and `renderUptime` but does not refresh the confirmed-orders table. After the bot confirms an order mid-session the Confirmed Orders table will show outdated data until a full page reload.

`pollStatus` already calls the `/api/status` endpoint which carries `orders_confirmed` counters per plugin. The table data comes from a separate `/api/history` endpoint and requires a separate call.

**Fix:** Either add `loadConfirmedBuys()` to `pollStatus()` after the health card render (keeping it lightweight since the route uses `asyncio.to_thread`), or set up a separate low-frequency interval:

```js
setInterval(loadConfirmedBuys, 15000);  // refresh every 15s
```

---

### WR-03: DOM cap in renderLogLines trims AFTER appending — cap is ineffective for bulk renders

**File:** `web/templates/dashboard.html:479-496`

`renderLogLines` clears the buffer then calls `appendLogLine` for each line (490), then trims:

```js
lines.forEach(function(line) { appendLogLine(line); });
while (bufferEl.children.length > MAX_LOG_LINES) {
  bufferEl.removeChild(bufferEl.firstChild);
}
```

Since `pollLogs` always fetches `n=500` and the API clamps to 500, `renderLogLines` will receive up to 500 lines, append 500 spans, then trim down to 500. The trim loop fires but removes 0 elements because `lines.length <= MAX_LOG_LINES` always. The cap is nominally correct for the current fetch size, but the intent was to protect against growth across multiple `appendLogLine` calls (the incremental append path). Because `renderLogLines` does `bufferEl.innerHTML = ''` at the start (line 481), it always starts from zero, making the trailing trim redundant rather than protective.

The real unbounded growth risk is if `appendLogLine` is ever called directly from an SSE path (Phase 29) without going through `renderLogLines`. In that path the cap logic is in `renderLogLines` and will never run. The cap should live in `appendLogLine` itself.

**Fix:** Move the cap enforcement into `appendLogLine`:
```js
function appendLogLine(lineText) {
  var bufferEl = document.getElementById('log-buffer');
  var span = document.createElement('span');
  span.className = 'log-line ' + logLevelClass(lineText);
  span.textContent = lineText;
  bufferEl.appendChild(span);
  while (bufferEl.children.length > MAX_LOG_LINES) {
    bufferEl.removeChild(bufferEl.firstChild);
  }
}
```

---

### WR-04: uPlot script tag placed after the inline script block that calls it

**File:** `web/templates/dashboard.html:840`

```html
  <script>
    // ... all JS including `new uPlot(...)` at line 446 ...
  </script>
  <script src="/static/vendor/uplot.iife.min.js"></script>  <!-- line 840 -->
</body>
```

The inline `<script>` block defines `loadPriceChart` which calls `new uPlot(...)`. The uPlot library is loaded in the `<script src>` tag that follows it. In practice this is fine because `loadPriceChart` is only invoked asynchronously (after `fetch` resolves) from within `loadItems`, which is called at line 835, at which point the browser has already parsed line 840 and executed the vendor script. However the load ordering is fragile: any synchronous call to `loadPriceChart` before the `<script src>` at line 840 executes will throw `ReferenceError: uPlot is not defined`. If a Phase 29 SSE handler calls `loadPriceChart` during the initial connection burst before the vendor script has loaded, the error will occur.

**Fix:** Move the uPlot `<script src>` tag to the `<head>` (before the inline script block), or add a guard in `loadPriceChart`:
```js
if (typeof uPlot === 'undefined') return;
```

---

### WR-05: heartbeat_age_secs None-check uses float equality on 0.0 — fragile sentinel

**File:** `core/health.py:93-95`

```python
public["heartbeat_age_secs"] = (
    None if lhb == 0.0 else round(now - lhb, 1)
)
```

The "never heartbeated" sentinel is the initial value `0.0` set in `_ensure` (line 23). The check `lhb == 0.0` is exact float equality. This is safe in the current code because `0.0` is the Python float literal assigned at initialization and `time.monotonic()` will never return exactly `0.0` in practice. However it is semantically fragile: the sentinel and the "no heartbeat" detection are conflated into a single numeric field rather than using an explicit `None` initial value.

If `_ensure` is ever changed to initialize `last_heartbeat` to `None` (the more Pythonic convention), the `== 0.0` check becomes a TypeError at runtime. Additionally, on a system where `time.monotonic()` starts very close to 0 (embedded environments, some CI containers), a plugin that heartbeated within the first tick could have `lhb` very close to 0.0 and `now - lhb` could be nearly 0 — the check is still correct but the `round(now - lhb, 1)` would return `0.0`, which the JS client bands as `heartbeat-ok` (correct behavior, no bug, just worth noting).

**Fix:** Initialize `last_heartbeat` to `None` and test for it explicitly:
```python
# in _ensure:
"last_heartbeat": None,

# in heartbeat():
self._plugins[name]["last_heartbeat"] = time.monotonic()

# in get_snapshot():
lhb = rec["last_heartbeat"]
public["heartbeat_age_secs"] = (
    None if lhb is None else round(now - lhb, 1)
)
```

---

## Info

### IN-01: escHtml helper is defined but unused

**File:** `web/templates/dashboard.html:630-634`

```js
function escHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}
```

The comment on line 629 acknowledges it is unused in Phase 25. It remains unused in Phase 28. Dead code that exists "in case" of future SVG interpolation is a YAGNI violation per project conventions. Its presence also invites future misuse: a developer might reach for `escHtml` to build an HTML string and assign it via `innerHTML`, bypassing the safe-DOM pattern used everywhere else.

**Fix:** Remove the function. If SVG interpolation becomes a concrete need in a future phase, add it then.

---

### IN-02: scroll-pause logic re-reads bufferEl from DOM on every scroll event

**File:** `web/templates/dashboard.html:503-509`

The scroll event listener inside the IIFE captures `bufferEl` by closure (line 500), which is correct. However `maybeScrollToBottom` (line 472) re-queries `document.getElementById('log-buffer')` on every invocation rather than using the closed-over reference. This is not a bug, but it is inconsistent with the IIFE pattern and slightly wasteful on high-frequency scroll events.

**Fix:** Pass `bufferEl` as a parameter to `maybeScrollToBottom`, or restructure so all log-viewer functions share the same closed-over reference.

---

_Reviewed: 2026-06-27_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
