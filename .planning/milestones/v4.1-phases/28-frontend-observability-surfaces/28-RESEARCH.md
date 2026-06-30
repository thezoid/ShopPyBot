# Phase 28: Frontend Observability Surfaces - Research

**Researched:** 2026-06-27
**Domain:** Dashboard JS rendering, uPlot time-series charts, CSS component extension, Python monotonic heartbeat age
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- Server-computed `heartbeat_age_secs` (`time.monotonic() - last_heartbeat`); null when never-heartbeated (`last_heartbeat == 0.0`). Added in `core/health.py get_snapshot()` or at the `get_status()` route boundary. Test `test_snapshot_public_keys_exact` must be updated.
- Client color-bands: `<30s` = `.heartbeat-ok`, `30-60s` = `.heartbeat-warn`, `>=60s or null` = `.heartbeat-err`.
- Status badge from snapshot `status` field; show `last_error` class name as sub-label when non-empty.
- Layout: responsive grid, one card per plugin. New "Plugin Health" section (`#section-health`).
- Uptime: humanized `uptime_secs` in `#header-uptime` slot.
- Confirmed-buys table from `GET /api/history`; always present, empty row when no orders. Safe DOM.
- Price charts: one uPlot chart per item, lazy-fetched from `GET /api/price-history/{link_b64}`. Empty state for no data. Point markers when `< 2` points.
- `link_b64` encoding: URL-safe base64 with `=` padding (matching Phase 26 decode).
- Log viewer: per-level color, level dropdown + search box, Follow toggle with pause-on-scroll, 500-line DOM cap. Plugin filter deferred.
- Keep existing ~2s poll for status + logs; extend `pollStatus()`/`pollLogs()`. Charts + confirmed-buys fetched one-shot on load.
- All DOM via `createElement`/`textContent`; charts via uPlot data array API. Zero `innerHTML` on API data.
- CSS: all via tokens, zero hardcoded hex in `components.css`.

### Claude's Discretion

- Exact DOM placement of chart containers relative to item rows (sibling `<div>` below table row or full-colspan nested `<tr>` — choose simpler approach avoiding nested-div-in-tr constraints).
- Whether `pollLogs()` is extended in-place or refactored to a separate `fetchLogs(level, search)` call.

### Deferred Ideas (OUT OF SCOPE)

- SSE live push / EventSource wiring (Phase 29).
- Log plugin filter (needs `[PLUGIN_NAME]` tagging — deferred).
- Order deep-links, multi-day log browsing, log-level count badges.
- Price capture for non-Amazon plugins (PRC-01).

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OBS-01 | Per-plugin health card: status badge, heartbeat staleness, consecutive-error count, items-checked count | `get_status()` payload confirmed; `heartbeat_age_secs` needs to be added to snapshot |
| OBS-02 | Heartbeat staleness three-band color (`<30s` green / `30-60s` amber / `>60s` red), monotonic clock | `last_heartbeat` already monotonic via `time.monotonic()`; age computed server-side |
| OBS-03 | Per-plugin confirmed-orders counter on health card | `orders_confirmed` already in snapshot |
| OBS-04 | Confirmed-buys table (name, order_id, confirmed_at, checkout_attempts) | `GET /api/history` implemented and tested; `get_confirmed_orders_sync()` confirmed |
| OBS-05 | Per-item price-history chart (uPlot) with explicit empty state | `GET /api/price-history/{link_b64}` implemented; uPlot IIFE confirmed at `window.uPlot`; ISO-to-Unix conversion required client-side |
| OBS-06 | Log viewer with per-level color-coding and level filter | `GET /api/logs?level=&search=&n=` implemented; level regex pattern confirmed from UI-SPEC |
| OBS-07 | Tail/follow with pause-on-scroll and 500-line DOM cap | Pattern fully specified in UI-SPEC; no blocking technical issues |
| OBS-08 | Log text search (level+search filters; plugin filter deferred) | `GET /api/logs?search=` implemented and tested |
| OBS-09 | Bot uptime in global status bar | `uptime_secs` in `get_status()` confirmed; `#header-uptime` slot exists in dashboard.html |

</phase_requirements>

## Summary

Phase 28 renders four observability surfaces entirely in `dashboard.html` JS, driven by Phase 26 REST endpoints that are already implemented and tested. The backend change is minimal: add `heartbeat_age_secs` to `get_snapshot()` in `core/health.py` (one computed field, update one test). The frontend work is new JS functions layered onto the existing poll architecture.

All data contracts are verified from source. The `GET /api/status` payload shape is confirmed (`running`, `uptime_secs`, `plugins` object keyed by plugin name with `status`, `last_heartbeat`, `consecutive_errors`, `items_checked`, `orders_confirmed`, `last_error`). The `GET /api/history` and `GET /api/price-history/{link_b64}` endpoints are already implemented and tested. The uPlot global is `window.uPlot` (or just `uPlot`); instantiation is `new uPlot(opts, data, el)`.

The only non-obvious gap is the price-history time-axis: `GET /api/price-history` returns `{"t": "<ISO-string>", "price": <float>}` per point, but uPlot `scales.x = {time: true}` expects Unix epoch seconds (integers). The client must convert: `Date.parse(t) / 1000`. This is straightforward but must be explicit in the plan. The UI-SPEC code block comments "Unix timestamps (seconds)" without spelling out the conversion step.

**Primary recommendation:** Add `heartbeat_age_secs` to `get_snapshot()`, update `test_snapshot_public_keys_exact`, then build five JS render functions (`renderHealthCards`, `renderUptime`, `loadConfirmedBuys`, `loadPriceChart`, `renderLogLines`/`appendLogLine`) as separate pure functions callable from either poll or SSE (Phase 29 compatibility contract). No new dependencies. No new Python packages. No new CSS tokens.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| heartbeat_age_secs computation | API/Backend (Python) | — | Monotonic clock is process-local; browser has no access to server's `time.monotonic()` epoch |
| Health card rendering | Browser/Client (JS) | — | Pure DOM construction from `GET /api/status` JSON |
| Staleness band classification | Browser/Client (JS) | — | Simple numeric comparison on server-computed value |
| Confirmed-buys table | Browser/Client (JS) | — | One-shot fetch from `GET /api/history` on page load |
| Price chart data fetch | Browser/Client (JS) | — | One-shot per-item fetch from `GET /api/price-history/{b64}` |
| Price chart rendering | Browser/Client (JS, uPlot) | — | uPlot already vendored; data arrays passed to canvas renderer |
| ISO-to-Unix timestamp conversion | Browser/Client (JS) | — | `Date.parse(t) / 1000`; API returns ISO strings, uPlot needs seconds |
| Log viewer render + filter | Browser/Client (JS) | — | Extends existing `pollLogs()` with query params |
| Log DOM cap (500 lines) | Browser/Client (JS) | — | `while (buffer.children.length > 500) buffer.removeChild(buffer.firstChild)` |
| Follow/pause-on-scroll | Browser/Client (JS) | — | `scroll` event listener on log buffer div |
| Uptime display | Browser/Client (JS) | — | Reads `data.uptime_secs` from existing `pollStatus()` response |
| CSS component classes | CDN/Static (CSS) | — | New classes in `components.css` extending Phase 25 design system |

## Standard Stack

Phase 28 introduces zero new dependencies. All libraries are already installed and vendored.

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `time.monotonic` | (built-in) | Server-side heartbeat age computation | Same clock as `last_heartbeat`; cross-process-safe |
| uPlot IIFE | 1.6.32 | Per-item price-history time-series charts | Already vendored at `web/static/vendor/uplot.iife.min.js`; confirmed from Phase 25 |
| Browser Fetch API | (built-in) | One-shot data fetching for charts and history | Used by existing `pollStatus()`/`pollLogs()` |
| CSS custom properties | (built-in) | All Phase 28 color/spacing via `var(--xxx)` | Phase 25 token system; CI enforces zero hardcoded hex |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `getComputedStyle(document.documentElement).getPropertyValue('--color-xxx')` | (built-in) | Read CSS tokens at chart render time for uPlot stroke colors | Always; avoids hardcoding hex in JS |
| `Date.parse(isoString) / 1000` | (built-in) | Convert ISO 8601 timestamps to Unix seconds for uPlot x-axis | In `loadPriceChart()` before passing data to `new uPlot()` |

**Installation:** None. All dependencies already present.

**Version verification:** `uPlot 1.6.32` confirmed from IIFE file header comment: `/*! https://github.com/leeoniya/uPlot (v1.6.32) */` [VERIFIED: direct file read].

## Package Legitimacy Audit

No new packages are installed in Phase 28. uPlot is already vendored from Phase 25. This section is not applicable.

## Architecture Patterns

### System Architecture Diagram

```
[Browser page load]
        |
        +---> pollStatus() every 2s -----> GET /api/status
        |           |                              |
        |           v                              v
        |     renderUptime(data.uptime_secs)    BotService.get_status()
        |     renderHealthCards(data.plugins)       |
        |                                        HealthRegistry.get_snapshot()
        |                                        (includes heartbeat_age_secs — NEW)
        |
        +---> pollLogs() every 2s -------> GET /api/logs?level=&search=&n=500
        |           |
        |           v
        |     renderLogLines(lines) -> appendLogLine(line)
        |           |
        |           v
        |     DOM cap: trim if > 500 spans
        |     Follow logic: auto-scroll if logFollowEnabled
        |
        +---> loadConfirmedBuys() [once] -> GET /api/history
        |           |
        |           v
        |     renderBuysTable(orders)
        |
        +---> loadItems() [existing] -> GET /api/items
                    |
                    v
              renderItemsTable(items) [existing]
                    |
                    +---> per item: loadPriceChart(item.link)
                                |
                                v
                          link_b64 = btoa(unescape(encodeURIComponent(link)))
                                      .replace(/\+/g,'-').replace(/\//g,'_')
                                |
                                v
                          GET /api/price-history/{link_b64}
                                |
                                v
                          series = [{t: ISO, price: float}, ...]
                                |
                                v
                          Convert: ts = series.map(p => Date.parse(p.t) / 1000)
                          prices  = series.map(p => p.price)
                                |
                                v
                          new uPlot(opts, [ts, prices], containerEl)
                          OR: chart-empty div (series.length === 0)
```

### Recommended Project Structure

No new directories. Changes are confined to:

```
web/
├── templates/
│   └── dashboard.html          # New sections + JS functions (primary change)
├── static/
│   └── components.css          # New component classes (health card, log viewer, chart)
core/
└── health.py                   # Add heartbeat_age_secs to get_snapshot()
tests/
├── test_health.py              # Update test_snapshot_public_keys_exact
└── test_web_dashboard.py       # Add scaffold assertions for new sections
```

### Pattern 1: heartbeat_age_secs in get_snapshot()

**What:** Compute monotonic age server-side and include it in the snapshot dict. `last_heartbeat` is 0.0 for never-heartbeated plugins (set in `_ensure()`); treat as "never" by returning `None`.

**When to use:** Called by `BotService.get_status()` which is called by the API route and by the SSE poll loop.

```python
# Source: core/health.py get_snapshot() — VERIFIED by direct read
def get_snapshot(self) -> dict[str, dict]:
    """Return a deep copy of per-plugin records with private keys stripped."""
    now = time.monotonic()
    return {
        name: {
            **{k: v for k, v in rec.items() if not k.startswith("_")},
            "heartbeat_age_secs": (
                None if rec["last_heartbeat"] == 0.0
                else round(now - rec["last_heartbeat"], 1)
            ),
        }
        for name, rec in self._plugins.items()
    }
```

Note: `time` is already imported at the top of `core/health.py` [VERIFIED: direct read].

The test guard to update:

```python
# Source: tests/test_health.py test_snapshot_public_keys_exact — VERIFIED by direct read
expected_keys = {
    "status", "last_heartbeat", "consecutive_errors",
    "items_checked", "orders_confirmed", "last_error",
    "heartbeat_age_secs",   # ADD THIS
}
```

### Pattern 2: uPlot Instantiation

**What:** `new uPlot(opts, data, el)` where `opts` is the config object, `data` is a 2D array `[[x0, x1, ...], [y0, y1, ...]]`, and `el` is the container DOM element uPlot appends its canvas into.

**Global name:** `uPlot` (exposed as `var uPlot` by the IIFE — the module exports the class directly, not under `window.uPlot.default` or any namespace). [VERIFIED: direct IIFE file header read]

**When to use:** After fetching price series and confirming `series.length >= 1`.

```javascript
// Source: 28-UI-SPEC.md + uPlot IIFE confirmed global — VERIFIED
function buildChart(containerEl, series) {
  const ts     = series.map(p => Date.parse(p.t) / 1000);  // ISO -> Unix seconds
  const prices = series.map(p => p.price);
  const style  = getComputedStyle(document.documentElement);
  const accentColor = style.getPropertyValue('--color-accent').trim();
  const mutedColor  = style.getPropertyValue('--color-text-muted').trim();

  const opts = {
    width:  containerEl.clientWidth || 300,
    height: 120,
    series: [
      {},
      {
        stroke: accentColor,
        width:  2,
        points: { show: ts.length < 2 },  // markers when < 2 points
      }
    ],
    axes: [
      { stroke: mutedColor },
      { stroke: mutedColor },
    ],
    scales: { x: { time: true } },
  };
  new uPlot(opts, [ts, prices], containerEl);
}
```

**CRITICAL:** `scales.x = {time: true}` requires Unix epoch seconds (numbers), NOT ISO strings. The API returns `{"t": "2026-06-01T12:00:00+00:00", "price": 12.99}`. Always apply `Date.parse(p.t) / 1000` before passing to uPlot. [VERIFIED: API source read + IIFE global confirmed]

### Pattern 3: link_b64 Client-Side Encoding

**What:** URL-safe base64 encoding of the item link, matching `base64.urlsafe_b64decode` on the server.

**When to use:** In `loadPriceChart(itemLink)` and already used in `removeItem(link)`.

```javascript
// Source: existing removeItem() in dashboard.html — VERIFIED by direct read
function linkToB64(link) {
  return btoa(unescape(encodeURIComponent(link)))
    .replace(/\+/g, '-')
    .replace(/\//g, '_');
  // Keep '=' padding — urlsafe_b64decode requires it
}
```

`btoa(unescape(encodeURIComponent(link)))` handles non-ASCII characters in URLs. The `+`→`-` and `/`→`_` swaps make it URL-safe. `=` padding is NOT stripped (matches Phase 26 `urlsafe_b64decode` which requires it). [VERIFIED: both `removeItem` in dashboard.html and `base64.urlsafe_b64decode` in api.py confirmed by direct read]

### Pattern 4: Follow Toggle with Pause-on-Scroll

**What:** Stateful follow flag that auto-scrolls the log buffer after render and pauses when the user scrolls up.

**When to use:** Log viewer `#log-buffer` element.

```javascript
// Source: 28-UI-SPEC.md — derived from locked decisions
let logFollowEnabled = true;
const bufferEl  = document.getElementById('log-buffer');
const followBtn = document.getElementById('btn-log-follow');

bufferEl.addEventListener('scroll', () => {
  const atBottom = bufferEl.scrollHeight - bufferEl.scrollTop
                   <= bufferEl.clientHeight + 8;
  if (!atBottom && logFollowEnabled) {
    logFollowEnabled = false;
    followBtn.classList.remove('btn-accent');
    followBtn.setAttribute('aria-pressed', 'false');
  }
});

followBtn.addEventListener('click', () => {
  logFollowEnabled = !logFollowEnabled;
  followBtn.classList.toggle('btn-accent', logFollowEnabled);
  followBtn.setAttribute('aria-pressed', String(logFollowEnabled));
  if (logFollowEnabled) bufferEl.scrollTop = bufferEl.scrollHeight;
});

function maybeScrollToBottom() {
  if (logFollowEnabled) bufferEl.scrollTop = bufferEl.scrollHeight;
}
```

**Resume condition:** scroll back to the bottom OR click Follow. Threshold of 8px prevents false-positive pauses from subpixel rounding. [ASSUMED — 8px threshold is a reasonable heuristic not verified against cross-browser data]

### Pattern 5: DOM Cap (500 lines)

**What:** Trim oldest `<span>` children from the log buffer after each append batch.

```javascript
// Source: 28-UI-SPEC.md — VERIFIED against OBS-07 requirement
const MAX_LOG_LINES = 500;
function trimLogBuffer() {
  while (bufferEl.children.length > MAX_LOG_LINES) {
    bufferEl.removeChild(bufferEl.firstChild);
  }
}
```

Call `trimLogBuffer()` after each `renderLogLines()` invocation.

### Anti-Patterns to Avoid

- **innerHTML on API data:** The existing CI guard (`test_no_innerHTML_with_api_data`) catches `innerHTML = \`...\${...}\`` patterns. All new functions must use `createElement`/`textContent`. The `tbody.innerHTML = ''` clear-only pattern is allowed (no interpolation).
- **Hardcoded hex in uPlot opts:** Do not pass `stroke: '#2563eb'` — always read from `getComputedStyle` so dark mode works.
- **Passing ISO strings to uPlot time axis:** `scales.x = {time: true}` silently misrenders if given strings instead of Unix seconds. Always `Date.parse(t) / 1000`.
- **link_b64 without URL-safety swap:** A raw `btoa(link)` (without `+`→`-`, `/`→`_`) will fail on the server's `urlsafe_b64decode`.
- **Dropping `=` padding:** The `urlsafe_b64decode` in `api.py` does NOT add missing padding. Keep `=` characters.
- **Mixing `time.time()` with `time.monotonic()`:** `last_heartbeat` is monotonic; `time.time()` is wall-clock and cannot be subtracted from it. The age computation MUST use `time.monotonic()`.
- **Moving `heartbeat_age_secs` to the route layer:** Adding it in `get_snapshot()` ensures it is available to both the REST route AND the SSE poll loop (Phase 29) without duplication.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Time-series line chart | Custom SVG/canvas chart | uPlot (vendored) | Already installed; handles time scale, tooltips, canvas sizing, responsive resize |
| CSS token reading in JS | Hardcoded color constants | `getComputedStyle().getPropertyValue()` | Automatically picks correct light/dark theme value at render time |
| URL-safe base64 encode | Custom encode function | Same `btoa(...).replace()` pattern from `removeItem()` | Already in codebase; single source of truth |
| Log follow/scroll detection | Custom visibility API | `scrollHeight - scrollTop <= clientHeight + threshold` | Sufficient for a single-panel log viewer; no IntersectionObserver needed |

## Runtime State Inventory

Not applicable. Phase 28 is a read-only frontend rendering change. No renames, refactors, or data migrations. No runtime state is affected.

## Common Pitfalls

### Pitfall 1: ISO Timestamp Passed to uPlot Time Axis

**What goes wrong:** `new uPlot(opts, [isoStrings, prices], el)` with `scales.x = {time: true}` produces a blank or broken x-axis. uPlot expects numeric Unix seconds.

**Why it happens:** `GET /api/price-history` returns `{"t": "2026-06-01T12:00:00+00:00", "price": 12.99}`. The `"t"` value is an ISO 8601 string, not a number. The UI-SPEC comment says "Unix timestamps (seconds)" but the conversion step is not explicit in the API contract doc.

**How to avoid:** Always map: `const ts = series.map(p => Date.parse(p.t) / 1000)` before building the uPlot data array.

**Warning signs:** Chart renders with no x-axis labels, or all points clustered at epoch zero.

### Pitfall 2: link_b64 Encoding Mismatch

**What goes wrong:** `GET /api/price-history/{link_b64}` returns `{"series": []}` for a link that has price data.

**Why it happens:** `btoa(link)` produces standard base64 (with `+` and `/`) but the server decodes with `base64.urlsafe_b64decode` which expects `-` and `_`. A mismatch causes the link decode to fail silently (the endpoint catches the exception and returns `{"series": []}`).

**How to avoid:** Use the identical pattern from `removeItem()`: `btoa(unescape(encodeURIComponent(link))).replace(/\+/g,'-').replace(/\//g,'_')`. Keep `=` padding.

**Warning signs:** Empty chart for an item known to have Amazon price history.

### Pitfall 3: heartbeat_age_secs Breaks test_snapshot_public_keys_exact

**What goes wrong:** `test_snapshot_public_keys_exact` asserts exact key set `{"status", "last_heartbeat", "consecutive_errors", "items_checked", "orders_confirmed", "last_error"}`. Adding `heartbeat_age_secs` to `get_snapshot()` without updating this test will cause a RED test.

**Why it happens:** The test is an exact-set guard (locked by design in Phase 25). Any snapshot key change must update this guard simultaneously.

**How to avoid:** Update `expected_keys` in `test_snapshot_public_keys_exact` in the same commit as `get_snapshot()` change.

**Warning signs:** `AssertionError: {'heartbeat_age_secs'} not in expected_keys`.

### Pitfall 4: heartbeat_age_secs at Route Boundary (Wrong Placement)

**What goes wrong:** If `heartbeat_age_secs` is computed in `web/routes/api.py` instead of `core/health.py get_snapshot()`, the SSE poll loop (Phase 29) does not get the field without duplicating the computation.

**Why it happens:** The route boundary seems like a natural place since it is the serialization point. But `get_snapshot()` is also called by the SSE `_poll_loop` which reads `svc.get_status()` -> `self._health_registry.get_snapshot()`.

**How to avoid:** Add `heartbeat_age_secs` directly in `get_snapshot()` (already has `import time`). This single-sources the computation.

**Warning signs:** Health cards work on REST but not on SSE events in Phase 29.

### Pitfall 5: uPlot Renders Before Container Has Width

**What goes wrong:** `containerEl.clientWidth` returns 0 when the element is not yet in the layout flow (e.g., inserted into a hidden section or before the browser has laid out the DOM).

**Why it happens:** `loadPriceChart()` is called during `loadItems()`, which runs on page load before full layout. If the chart container `<div>` is appended but the section is not yet visible, `clientWidth` is 0 and uPlot creates a 300px-fallback chart (via the `|| 300` guard).

**How to avoid:** The `|| 300` fallback in `opts.width: containerEl.clientWidth || 300` is sufficient for this use case (single-operator localhost tool, not a production dashboard). The 300px fallback is acceptable.

**Warning signs:** All charts render at exactly 300px width even on wide screens. Acceptable for Phase 28; can be improved with ResizeObserver in a future phase.

### Pitfall 6: pollLogs() Sends GET /api/logs Without Level/Search on First Call

**What goes wrong:** The filter controls are wired to re-trigger `pollLogs()` on `change`/`input`, but the initial `pollLogs()` call ignores the current control values if they happen to be pre-set.

**Why it happens:** If `pollLogs()` reads the filter values dynamically each call (from the DOM elements), there is no issue. If it is hardcoded to `?n=500` only, the first fetch ignores any pre-selected filter.

**How to avoid:** Always read filter values from the DOM inside `pollLogs()`: `document.getElementById('log-level-filter').value` and `document.getElementById('log-search').value`. Build the query string dynamically.

**Warning signs:** Level filter dropdown shows "ERROR" but log viewer shows all log levels on page load.

### Pitfall 7: Phase 25 CI Guards Break on New CSS Classes

**What goes wrong:** `test_no_hardcoded_hex_in_components()` fails if a new CSS class in `components.css` uses a hex literal instead of `var(--xxx)`. The test scans the entire file after stripping comments.

**Why it happens:** Developers sometimes add quick one-off color fixes during implementation.

**How to avoid:** Every new class in `components.css` must use only `var(--xxx)` tokens. Reference the UI-SPEC component spec table — all values are already specified with token names.

**Warning signs:** `AssertionError: Hardcoded hex found in components.css`.

## Code Examples

### heartbeat_age_secs Server Computation

```python
# Source: core/health.py get_snapshot() — to be modified
# VERIFIED: time already imported; _plugins structure confirmed; 0.0 sentinel confirmed

def get_snapshot(self) -> dict[str, dict]:
    now = time.monotonic()
    return {
        name: {
            **{k: v for k, v in rec.items() if not k.startswith("_")},
            "heartbeat_age_secs": (
                None if rec["last_heartbeat"] == 0.0
                else round(now - rec["last_heartbeat"], 1)
            ),
        }
        for name, rec in self._plugins.items()
    }
```

### Staleness Band Classification (JS)

```javascript
// Source: 28-UI-SPEC.md — VERIFIED against locked decisions
function heartbeatClass(ageSecs) {
  if (ageSecs === null || ageSecs === undefined) return 'heartbeat-err';
  if (ageSecs < 30)  return 'heartbeat-ok';
  if (ageSecs < 60)  return 'heartbeat-warn';
  return 'heartbeat-err';
}

function heartbeatText(ageSecs) {
  if (ageSecs === null || ageSecs === undefined) return 'Heartbeat: never';
  return `Heartbeat: ${ageSecs}s`;
}
```

### loadPriceChart with ISO Conversion

```javascript
// Source: 28-CONTEXT.md + 28-UI-SPEC.md + api.py confirmed shape — VERIFIED
async function loadPriceChart(itemLink) {
  const b64 = btoa(unescape(encodeURIComponent(itemLink)))
    .replace(/\+/g, '-').replace(/\//g, '_');
  const containerEl = document.getElementById('chart-' + b64);
  if (!containerEl) return;

  let series;
  try {
    const resp = await fetch('/api/price-history/' + b64);
    const data = await resp.json();
    series = data.series || [];
  } catch (_) {
    containerEl.innerHTML = '';
    const msg = document.createElement('div');
    msg.className = 'chart-empty';
    msg.textContent = 'Failed to load price history.';
    containerEl.appendChild(msg);
    return;
  }

  if (series.length === 0) {
    const msg = document.createElement('div');
    msg.className = 'chart-empty';
    msg.textContent = 'No price history available for this plugin.';
    containerEl.appendChild(msg);
    return;
  }

  // CRITICAL: convert ISO strings to Unix seconds (uPlot time scale requirement)
  const ts     = series.map(p => Date.parse(p.t) / 1000);
  const prices = series.map(p => p.price);
  const style  = getComputedStyle(document.documentElement);

  const opts = {
    width:  containerEl.clientWidth || 300,
    height: 120,
    series: [
      {},
      {
        stroke: style.getPropertyValue('--color-accent').trim(),
        width:  2,
        points: { show: ts.length < 2 },
      }
    ],
    axes: [
      { stroke: style.getPropertyValue('--color-text-muted').trim() },
      { stroke: style.getPropertyValue('--color-text-muted').trim() },
    ],
    scales: { x: { time: true } },
  };
  new uPlot(opts, [ts, prices], containerEl);
}
```

### pollLogs Extension with Filter Params

```javascript
// Source: existing pollLogs() in dashboard.html — VERIFIED by direct read; extended per locked decisions
async function pollLogs() {
  const level  = document.getElementById('log-level-filter').value;
  const search = document.getElementById('log-search').value;
  const params = new URLSearchParams({ n: 500 });
  if (level)  params.set('level',  level);
  if (search) params.set('search', search);
  try {
    const resp = await fetch('/api/logs?' + params.toString());
    const data = await resp.json();
    renderLogLines(data.logs || []);
  } catch (_) {
    /* silent on transient error; log-content unchanged */
  }
}
```

### Log Level Class Extraction

```javascript
// Source: 28-UI-SPEC.md — VERIFIED against actual log line format from test_api_observability.py
// "[ERROR][2026-01-01@00:00:00] captcha detected" -> 'log-level-error'
function logLevelClass(line) {
  const m = line.match(/^\[(\w+)\]/);
  if (!m) return 'log-level-info';
  const map = {
    ERROR: 'log-level-error', WARNING: 'log-level-warn',
    INFO:  'log-level-info',  DEBUG:   'log-level-debug',
    TRACE: 'log-level-trace',
  };
  return map[m[1].toUpperCase()] || 'log-level-info';
}
```

### New CSS Classes (components.css additions)

All from 28-UI-SPEC.md. All use `var(--xxx)` tokens only.

```css
/* Health grid and card */
.health-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: var(--space-md); margin-bottom: var(--space-md); }
.health-card { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; padding: var(--space-lg); display: flex; flex-direction: column; gap: var(--space-sm); }
.health-card-name  { font-size: var(--text-body); font-weight: var(--weight-semibold); color: var(--color-text); }
.health-card-stats { display: flex; flex-direction: column; gap: var(--space-xs); font-size: var(--text-sm); color: var(--color-text-muted); }
.health-card-error { font-size: var(--text-sm); color: var(--color-status-err); word-break: break-word; }

/* Status badge */
.badge         { display: inline-flex; align-items: center; gap: var(--space-xs); font-size: var(--text-sm); font-weight: var(--weight-semibold); }
.badge-ok      { color: var(--color-status-ok); }
.badge-neutral { color: var(--color-status-neutral); }
.badge-err     { color: var(--color-status-err); }
.status-dot.error { background: var(--color-status-err); }

/* Heartbeat age */
.heartbeat-age  { font-size: var(--text-sm); font-weight: var(--weight-semibold); }
.heartbeat-ok   { color: var(--color-status-ok); }
.heartbeat-warn { color: var(--color-status-warn); }
.heartbeat-err  { color: var(--color-status-err); }

/* Chart container */
.chart-container { margin-top: var(--space-sm); padding: var(--space-sm) 0; }
.chart-empty     { padding: var(--space-lg); font-size: var(--text-sm); color: var(--color-text-muted); text-align: center; }

/* Log viewer */
.log-viewer   { display: flex; flex-direction: column; gap: var(--space-sm); }
.log-controls { display: flex; align-items: center; gap: var(--space-sm); flex-wrap: wrap; }
.log-buffer   { font-family: monospace; font-size: var(--text-sm); line-height: var(--leading-ui); background: var(--color-bg); border: 1px solid var(--color-border); border-radius: 4px; padding: var(--space-sm); height: 300px; overflow-y: auto; white-space: pre-wrap; word-break: break-all; }
.log-line     { display: block; padding: 0; }
.log-level-error { color: var(--color-status-err); }
.log-level-warn  { color: var(--color-status-warn); }
.log-level-info  { color: var(--color-text); }
.log-level-debug { color: var(--color-text-muted); }
.log-level-trace { color: var(--color-text-muted); }

/* Responsive: single-column health grid on narrow viewport */
@media (max-width: 640px) { .health-grid { grid-template-columns: 1fr; } }
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `innerHTML = ...` with API data | `createElement` / `textContent` | Phase 25 | XSS fix; CI guard enforces; all new Phase 28 code follows this |
| Manual color constants in JS | `getComputedStyle().getPropertyValue('--token')` | Phase 25 (design system) | Automatic dark/light mode support; no hardcoded hex in JS |
| Static SSR Jinja items list | JS `loadItems()` via `GET /api/items` | Phase 25 | Dynamic updates; chart injection point aligns with this |

**Deprecated/outdated:**

- `pollLogs()` with hardcoded `?n=50` (no filter params): Phase 28 extends this to pass `level`, `search`, `n=500`.
- `<pre id="log-content">` in `#section-controls`: Retained for the existing poll path in Phase 28; both panels coexist. Phase 29 migrates Controls log to SSE.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | 8px scroll threshold for follow-pause is sufficient to avoid false-positive pauses from subpixel rendering | Common Pitfalls / Follow Pattern | Minor UX issue — could be tuned to 1px or 2px if reports emerge; no functional risk |
| A2 | `containerEl.clientWidth || 300` fallback is acceptable for Phase 28 | Common Pitfalls / Pitfall 5 | Charts render 300px-wide if called before layout; acceptable for localhost single-operator tool |

**All other claims in this research were verified or cited from direct source reads (no assumptions).**

## Open Questions

1. **Chart container DOM placement (discretionary)**
   - What we know: UI-SPEC recommends a `<div id="chart-{link_b64}">` inserted as a sibling below `#items-table`, grouped with the item by `data-link`. An alternative is a full-colspan `<tr>` containing the chart div.
   - What's unclear: Which approach is simpler given the existing `loadItems()` tbody construction.
   - Recommendation: Executor should use a sibling `<div>` per item appended after the `tr` is built inside `loadItems()`, avoiding the nested-div-in-`<tr>` table constraint. The planner can leave this as executor discretion.

2. **pollLogs() refactor scope (discretionary)**
   - What we know: Existing `pollLogs()` is 6 lines; Phase 28 needs it to read filter control values and pass `n=500`.
   - What's unclear: Whether to extend in-place or extract a `fetchLogs(level, search, n)` helper.
   - Recommendation: Extend in-place to minimize scope. A helper can be extracted in Phase 29 if needed.

## Environment Availability

Phase 28 is a code/CSS/template change with no external tool dependencies. No new CLI tools, databases, or services are required. uPlot is vendored; no npm or CDN. Step 2.6 is skipped (no external dependencies identified).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | none (conventional discovery) |
| Quick run command | `rtk pytest tests/test_health.py tests/test_web_dashboard.py tests/test_design_system.py -x` |
| Full suite command | `rtk pytest` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OBS-01/02/03 (backend) | `heartbeat_age_secs` present in snapshot; correct value; None when never-heartbeated | unit | `rtk pytest tests/test_health.py::test_snapshot_public_keys_exact -x` (update) + new `test_heartbeat_age_secs_*` | test_health.py exists; new tests needed |
| OBS-01/02/03/09 (template) | `#section-health` and `#header-uptime` present in rendered HTML | static | `rtk pytest tests/test_web_dashboard.py::test_dashboard_renders_health_section -x` | New test needed |
| OBS-04 (template) | `#section-buys` with table skeleton present in rendered HTML | static | `rtk pytest tests/test_web_dashboard.py::test_dashboard_renders_buys_section -x` | New test needed |
| OBS-05 (template) | `uplot.iife.min.js` script tag present; `loadPriceChart` function present in template | static | `rtk pytest tests/test_web_dashboard.py::test_uplot_served` (existing) + scan for function name | Partial |
| OBS-06/07/08 (template) | `#section-log-viewer` with `#log-buffer` and `#log-level-filter` present | static | `rtk pytest tests/test_web_dashboard.py::test_dashboard_renders_log_viewer_section -x` | New test needed |
| OBS-07 (JS contract) | `MAX_LOG_LINES = 500` constant and trim pattern appear in template | static grep | `rtk pytest tests/test_web_dashboard.py::test_log_dom_cap_constant -x` | New test needed |
| Phase 25 CSS guard | Zero hardcoded hex in components.css after adding new classes | static analysis | `rtk pytest tests/test_design_system.py::test_no_hardcoded_hex_in_components -x` | Exists; runs unchanged |
| Phase 25 XSS guard | No `innerHTML` on API data in new JS functions | static grep | `rtk pytest tests/test_web_dashboard.py::test_no_innerHTML_with_api_data -x` | Exists; runs unchanged |
| OBS-01 to 09 (visual) | Cards render correctly, charts display, follow scrolls, filter narrows logs | **manual UAT** | Browser: open dashboard, start bot, observe each surface | Not automatable |

### What Is NOT Automatable (Manual UAT)

The following require a running bot or browser interaction:

- Health card visual appearance: badge color, heartbeat age color band, card grid layout
- uPlot chart rendering: line appears for Amazon items, "No price history" text for non-Amazon
- Follow toggle: auto-scroll behavior, pause-on-scroll, resume-on-click
- Log level filter: changing dropdown live-filters the log content
- Search box: debounce behavior, substring match visible
- Dark mode: chart colors (from CSS tokens) adapt correctly
- Uptime: "Up 1h 23m" appears in header when bot runs for a minute

### Sampling Rate

- Per task commit: `rtk pytest tests/test_health.py tests/test_web_dashboard.py tests/test_design_system.py -x`
- Per wave merge: `rtk pytest`
- Phase gate: full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_health.py` — update `test_snapshot_public_keys_exact` + add `test_heartbeat_age_secs_fresh`, `test_heartbeat_age_secs_never`
- [ ] `tests/test_web_dashboard.py` — add `test_dashboard_renders_health_section`, `test_dashboard_renders_buys_section`, `test_dashboard_renders_log_viewer_section`, `test_log_dom_cap_constant`, `test_no_innerHTML_with_api_data` (existing, verify it covers new functions)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | All new endpoints are read-only; CSRF `check_origin` only on mutating routes (unchanged) |
| V5 Input Validation | yes | Level/search params from user controlled; already sanitized by `read_logs_filtered` server-side; no additional client-side validation needed |
| V6 Cryptography | no | — |

### Known Threat Patterns for Phase 28 Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| DOM-based XSS via log line content | Spoofing/Tampering | `span.textContent = lineText` (not innerHTML); existing CI guard |
| XSS via item name in chart container id | Spoofing | `id="chart-{link_b64}"` uses b64 of the URL (URL-safe chars only); no user-supplied name in id |
| Staleness value injection | Tampering | Server-computed; client only classifies (< 30 / < 60 / else); no eval() |
| Chart color injection via CSS token | Tampering | `getComputedStyle` reads declared CSS token — cannot be overridden by page content |
| `last_error` class name expansion | Information Disclosure | Already scrubbed to `exc.__class__.__name__` by `record_last_error()` in Phase 26; Phase 28 renders whatever the API returns |

## Sources

### Primary (HIGH confidence)

- `E:\repos\ShopPyBot\core\health.py` — HealthRegistry implementation; `_plugins` structure; `get_snapshot()` current key set; `import time` confirmed; `last_heartbeat` initialized to `0.0`
- `E:\repos\ShopPyBot\core\service.py` — `get_status()` payload shape: `{running, uptime_secs, plugins}`; `_start_time` is monotonic
- `E:\repos\ShopPyBot\web\routes\api.py` — All four endpoint signatures and return shapes confirmed: `/api/status`, `/api/logs`, `/api/history`, `/api/price-history/{link_b64}`; ISO timestamp returned as `"t"` field
- `E:\repos\ShopPyBot\web\templates\dashboard.html` — `#header-uptime` slot confirmed; `removeItem()` link_b64 encoding pattern confirmed; `pollStatus()`/`pollLogs()` structure confirmed; uPlot script tag at end of body confirmed
- `E:\repos\ShopPyBot\web\static\components.css` — Existing classes confirmed; zero hardcoded hex pattern enforced; `status-dot.running` and `.status-dot.stopped` exist; `.status-dot.error` does not yet exist
- `E:\repos\ShopPyBot\web\static\tokens.css` — All tokens confirmed: `--color-status-ok/warn/err/neutral`, `--color-accent`, `--color-text-muted`, all spacing and type tokens
- `E:\repos\ShopPyBot\web\static\vendor\uplot.iife.min.js` — Global variable name `var uPlot` confirmed from file header; version `1.6.32` confirmed
- `E:\repos\ShopPyBot\tests\test_health.py` — `test_snapshot_public_keys_exact` current expected key set confirmed; existing test patterns for `monkeypatch`-free unit tests confirmed
- `E:\repos\ShopPyBot\tests\test_web_dashboard.py` — Existing test patterns: `TestClient(create_app(mock_svc))`; `mock_svc.get_status.return_value` pattern; static HTML assertion patterns
- `E:\repos\ShopPyBot\tests\test_design_system.py` — `test_no_hardcoded_hex_in_components()` and `test_all_required_tokens_declared()` confirmed; these run unchanged and gate CSS additions
- `E:\repos\ShopPyBot\models.py` — `get_confirmed_orders_sync()` returns `(name, order_id, confirmed_at, checkout_attempts)`; `scraped_at` stored as ISO TEXT string confirmed from `orchestrator.py` `now_iso = datetime.now(timezone.utc).isoformat()`
- `E:\repos\ShopPyBot\.planning\phases\28-frontend-observability-surfaces\28-CONTEXT.md` — Locked decisions
- `E:\repos\ShopPyBot\.planning\phases\28-frontend-observability-surfaces\28-UI-SPEC.md` — Complete component specs, HTML structures, JS function signatures, CSS class definitions

### Secondary (MEDIUM confidence)

- `E:\repos\ShopPyBot\.planning\research\SUMMARY.md` Phase D section — Cross-confirmed architecture decisions; empty-state for non-Amazon price data; SUMMARY authored 2026-06-25 against same codebase

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all libraries verified by direct file reads; no new packages
- Architecture: HIGH — all data contracts verified from source (api.py, health.py, service.py, models.py, dashboard.html)
- Pitfalls: HIGH — ISO-to-Unix gap confirmed by tracing from `orchestrator.py` `now_iso` through `models.py` storage through `api.py` `"t": r[2]`; link_b64 confirmed by comparing `removeItem()` with `urlsafe_b64decode` in api.py
- uPlot API: HIGH — global name and instantiation signature confirmed from IIFE file; confirmed no default export wrapper

**Research date:** 2026-06-27
**Valid until:** 2026-07-27 (stable stack; no fast-moving dependencies)
