# Stack Research

**Domain:** Python dashboard redesign + observability (FastAPI web UI, vendored frontend, SSE push)
**Researched:** 2026-06-25
**Confidence:** HIGH (all critical claims verified against official sources or PyPI)

## Context: What Already Exists

The existing web layer (v2.0 Phase 10) is a FastAPI 0.115.8 optional extra with:
- `create_app()` factory in `web/__init__.py` mounting `/static` and 4 routers
- Single Jinja2 template `web/templates/dashboard.html` with inline vanilla JS polling `/api/status` and `/api/logs` every 2s
- 182-line hand-written plain CSS in `web/static/dashboard.css` using informal hex tokens, no CSS variables
- Optional-extra deps pinned: `fastapi==0.115.8`, `uvicorn[standard]==0.30.6`, `jinja2==3.1.4`, `python-multipart==0.0.32`
- Zero package.json anywhere; zero CDN imports; localhost-bound CSRF (`web/security.py`)

The v4.1 milestone redesigns this layer. All additions must stay zero-Node, vendored-only.

## Recommended Stack

### Core Technologies (no version bumps required)

| Technology | Pinned Version | Purpose | Why Keep |
|------------|---------------|---------|----------|
| FastAPI | 0.115.8 (current pin) | ASGI app framework | No breaking changes needed for SSE via raw StreamingResponse — see SSE section |
| uvicorn[standard] | 0.30.6 (current pin) | ASGI server | Standard, asyncio-native; SSE works with raw StreamingResponse without changes |
| Jinja2 | 3.1.4 (current pin) | HTML template rendering for dashboard page | Only one template; already installed |
| python-multipart | 0.0.32 (current pin) | Form body parsing | Already installed; no change needed |

No Python dependency changes are required for the dashboard redesign. All new capability comes from vendored static assets and a new FastAPI SSE route.

### Frontend: Design System (vendored CSS)

**Approach: CSS custom properties (CSS variables) as design tokens in the existing `dashboard.css`.**

The existing `dashboard.css` is 182 lines using hardcoded hex values. Replace those hex values with CSS custom property references and define a token block at the top of the same file. No new file required; no build step.

Architecture:

```css
/* Tier 1: primitives (never referenced in components directly) */
:root {
  --color-blue-600: #2563eb;
  --color-red-600: #dc2626;
  --color-green-700: #16a34a;
  --color-gray-50: #f9fafb;
  --color-gray-100: #f3f4f6;
  --color-gray-200: #e5e7eb;
  --color-gray-300: #d1d5db;
  --color-gray-500: #6b7280;
  --color-gray-900: #111827;
  --color-white: #ffffff;
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-6: 24px;
  --space-8: 32px;
  --radius-sm: 4px;
  --radius-md: 6px;
  --font-size-xs: 12px;
  --font-size-sm: 13px;
  --font-size-base: 14px;
  --font-size-lg: 18px;
  --font-size-xl: 22px;
}

/* Tier 2: semantic tokens (referenced in components) */
:root {
  --color-bg: var(--color-gray-50);
  --color-surface: var(--color-white);
  --color-border: var(--color-gray-300);
  --color-text: var(--color-gray-900);
  --color-text-muted: var(--color-gray-500);
  --color-accent: var(--color-blue-600);
  --color-danger: var(--color-red-600);
  --color-success: var(--color-green-700);
  --color-status-running: var(--color-green-700);
  --color-status-stopped: var(--color-gray-500);
}

/* Tier 3: dark mode override (media query approach — zero JS needed) */
@media (prefers-color-scheme: dark) {
  :root {
    --color-bg: #0f172a;
    --color-surface: #1e293b;
    --color-border: #334155;
    --color-text: #f1f5f9;
    --color-text-muted: #94a3b8;
    /* accent/danger/success intentionally stay the same — already meet contrast */
  }
}
```

For manual toggle (user-clickable light/dark switch), add a `data-theme="dark"` attribute to `<html>` and add a second selector block alongside the media query. Both can coexist. The JS toggle stores the preference in `localStorage` and applies the attribute on load.

**Component vocabulary to add:**
- Health cards: `.health-card`, `.health-card--degraded`, `.health-card--ok` with border-left color coding
- Badge: `.badge`, `.badge--running`, `.badge--stopped`, `.badge--degraded`
- Log viewer enhancements: filter bar `.log-filter-bar`, level chips `.log-chip`, search input (reuse existing input styles)
- Chart container: `.chart-wrap` (flex container with min-height, overflow hidden)
- Stat row: `.stat-row`, `.stat-value`, `.stat-label` for order/buy history cards

**Result:** The entire design system lives in `web/static/dashboard.css`. One vendored file. No fonts to download. No `@import url()`. `prefers-color-scheme` has >95% browser support (all modern browsers, Chrome 76+, Firefox 67+, Safari 12.1+).

### Frontend: Charting (vendored JS)

**Recommendation: uPlot 1.6.32 (MIT, ~52 KB minified, ~15 KB gzipped).**

Vendor two files into `web/static/`:
- `uplot.iife.min.js` (~52 KB) — IIFE build, assigns `uPlot` to `window`
- `uplot.min.css` (~1 KB) — required companion stylesheet

Include in `dashboard.html`:
```html
<link rel="stylesheet" href="/static/uplot.min.css">
<script src="/static/uplot.iife.min.js"></script>
```

Then inline chart initialization in the dashboard JS:
```javascript
const chart = new uPlot(opts, [xTimestamps, yPrices], document.getElementById('chart-wrap'));
```

Why uPlot over alternatives:
- Purpose-built for time series (price history table is date + price pairs) — renders x-axis as timestamps natively
- Smallest footprint that gives real tooltips, zoom, and hover at ~52 KB min / ~15 KB gz
- MIT license, vendorable as two static files, no build step, no dependencies of its own
- Active maintenance: v1.6.32 released March 2025; v1.6.15 through v1.6.32 spans active ongoing development
- Canvas 2D rendering: no SVG DOM thrash, performant for 1K+ points

**For the sparse price-history case (Amazon-only today, PRICE-02):** uPlot renders gracefully with few points. Render a "No price data yet" placeholder `<div>` when the dataset is empty; swap to the uPlot canvas when data arrives. This avoids an empty axis.

**Charting alternatives evaluated:**

| Option | Size (min) | License | Verdict |
|--------|-----------|---------|---------|
| uPlot 1.6.32 | ~52 KB | MIT | RECOMMENDED: purpose-built time series, tiny, vendorable IIFE |
| Chart.js 4.5.0 | ~204 KB (umd.min) | MIT | Too large (4x uPlot); general-purpose, not time-series-optimized |
| Frappe Charts 1.6.3 | ~60 KB | MIT | Last release April 2022; effectively abandoned; do not add |
| Hand-rolled SVG polyline | 0 KB | n/a | Viable for a simple sparkline; no tooltips or zoom; needs coordinate scaling math per dataset |
| Pure-CSS bar chart | 0 KB | n/a | Good for simple per-item bar (e.g., checkout attempts count); no time axis; add as complement for non-time-series counts |

**For the price history chart: use uPlot.** For checkout-attempt counts or simple bar comparisons (ordinal, not time-series), a pure-CSS bar (`width: calc(var(--val) / var(--max) * 100%)`) is sufficient and adds zero bytes.

**Acquisition:** Download from the uPlot GitHub repo `dist/` directory:
- `https://github.com/leeoniya/uPlot/tree/master/dist`

Copy `uPlot.iife.min.js` and `uPlot.min.css` to `web/static/`. Rename to lowercase convention. Commit both files to the repo (each is small enough to track in git).

### Backend: SSE Push (replace 2s poll)

**Recommendation: Raw `StreamingResponse` with `text/event-stream` in FastAPI 0.115.8. Do NOT add sse-starlette. Do NOT upgrade FastAPI yet.**

FastAPI 0.115.8 already includes `StreamingResponse` from starlette. Wrapping an async generator that yields SSE-formatted strings is all that is needed.

**Why not upgrade to FastAPI 0.135 for native `fastapi.sse.EventSourceResponse`:**
- Native SSE (`from fastapi.sse import EventSourceResponse`) landed in FastAPI 0.135.0 (released March 2026; current latest is 0.138.0 as of June 2026)
- Upgrading from 0.115 to 0.135 crosses the 0.128.0 boundary where pydantic v1 shim support was removed and pydantic minimum was bumped to 2.7.0
- The project already uses pydantic 2.13.3 so the pydantic floor is not a blocker, but crossing 13 minor FastAPI versions mid-milestone is scope risk with 755 passing tests to re-validate
- The raw pattern below is functionally identical for this use case
- Defer the FastAPI upgrade to a dedicated dependency-refresh task

**Why not add sse-starlette 3.4.5:**
- Adds anyio as a new transitive dependency to the optional extras
- Requires starlette >= 0.41.3 (already satisfied by fastapi 0.115.8's starlette pin)
- The raw pattern covers all required use cases (status push, log tail push, health push) in ~20 lines per endpoint
- sse-starlette is well-maintained and production-stable; justified when you need fan-out channels, cooperative shutdown hooks, or multi-loop safety; those needs do not apply here (single uvicorn process, no thread-crossing)

**Raw SSE pattern for FastAPI 0.115.8:**

```python
import asyncio
import json
from fastapi import Request
from fastapi.responses import StreamingResponse
from web.routes.api import router

@router.get("/stream/status")
async def stream_status(request: Request):
    svc = request.app.state.svc

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                data = json.dumps(svc.get_status())
                yield f"event: status\ndata: {data}\n\n"
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
```

`request.is_disconnected()` is the correct starlette 0.41 idiom for disconnect detection; it surfaces the ASGI disconnect message without blocking. `Cache-Control: no-cache` prevents proxy buffering. `X-Accel-Buffering: no` is required for nginx-proxied setups.

**Named event types** — client listens with `EventSource.addEventListener`:
- `event: status` — bot running/stopped + plugin count (1s cadence)
- `event: health` — per-plugin liveness/heartbeat from `HealthRegistry` (5s cadence)
- `event: log` — single new log line appended (near real-time tail)

Three endpoints: `/api/stream/status`, `/api/stream/health`, `/api/stream/logs`. Each generator handles one concern and one cadence.

**Client side (no library):**

```javascript
const es = new EventSource('/api/stream/status');
es.addEventListener('status', e => {
  const data = JSON.parse(e.data);
  // update UI
});
es.onerror = () => { /* EventSource auto-reconnects; log to console only */ };
```

The browser `EventSource` API auto-reconnects after network drops. Remove the existing `setInterval` polling once SSE is wired. Keep the initial Jinja2 server-side render of `status.running` for first-paint so the page is not blank before the SSE connection opens.

**uvicorn event-loop safety:** uvicorn 0.30.6 (standard extras) runs a single asyncio event loop per process. `StreamingResponse` with an async generator runs entirely within that loop. There is no cross-thread concern here because the SSE generator only reads `svc.get_status()` (synchronous in-memory read) and calls `asyncio.sleep()`. The existing `asyncio.to_thread()` wrappers on `svc.start()` / `svc.stop()` are unaffected.

## Installation

No new Python packages. Vendor two JS/CSS files:

```text
Vendor files to copy into web/static/:
  uPlot.iife.min.js  -> web/static/uplot.iife.min.js  (~52 KB)
  uPlot.min.css      -> web/static/uplot.min.css       (~1 KB)
Source: https://github.com/leeoniya/uPlot/tree/master/dist

Python pyproject.toml [project.optional-dependencies] web block: unchanged
```

`pyproject.toml` `[web]` extras block stays identical:

```toml
[project.optional-dependencies]
web = [
    "fastapi==0.115.8",
    "uvicorn[standard]==0.30.6",
    "jinja2==3.1.4",
    "python-multipart==0.0.32",
]
```

## Alternatives Considered

| Decision | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| SSE implementation | Raw StreamingResponse (0 new deps) | sse-starlette 3.4.5 | Adds anyio dep; raw pattern sufficient for 3 endpoints |
| SSE implementation | Raw StreamingResponse on 0.115.8 | Upgrade to FastAPI 0.135 for native EventSourceResponse | Crosses 13 minor versions; pydantic compat boundary at 0.128; scope risk for cosmetics milestone |
| Charting | uPlot 1.6.32 (52 KB, MIT) | Chart.js 4.5.0 | umd.min is 204 KB — 4x larger; not time-series-optimized |
| Charting | uPlot 1.6.32 | Frappe Charts 1.6.3 | Last release April 2022; abandoned |
| Charting | uPlot 1.6.32 | Hand-rolled SVG | No tooltips/zoom; coordinate math required per dataset update |
| Design system | CSS custom properties in existing dashboard.css | Tailwind CSS | Requires Node/CDN; violates zero-Node constraint |
| Design system | CSS custom properties in existing dashboard.css | Open-Props (CDN) | External CDN; violates no-CDN constraint |
| Design system | CSS custom properties in existing dashboard.css | Pico CSS (vendored) | Another file; existing CSS is custom and small; Pico would conflict with existing component styles |
| Dark mode | @media prefers-color-scheme + optional data-theme attribute | JS-only theming | Media query works without JS; data-theme layer is additive for manual toggle |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Any npm/Node toolchain (Vite, Webpack, Rollup, esbuild) | Hard constraint: ZERO-NODE | Vendored pre-built dist files only |
| CDN script/link tags (unpkg.com, jsdelivr.net, cdnjs.com) | Hard constraint: no CDN; also fails offline use | Download, vendor into `web/static/`, commit |
| WebSockets | Bidirectional; requires reconnect state machine on client; more complex than needed for read-only push | SSE (EventSource): unidirectional push; browser auto-reconnects |
| D3.js | Large (70+ KB core); designed for primitive visualization not time series lines; steep API for this use case | uPlot for time series; pure CSS bars for ordinal counts |
| Frappe Charts | Last release April 2022; npm weekly downloads declining; issue tracker inactive | uPlot |
| Chart.js 4.x (umd.min) | 204 KB uncompressed; 4x uPlot for equivalent time series use | uPlot |
| sse-starlette | Adds anyio dep for no functional gain on 3 simple push endpoints | Raw StreamingResponse pattern (20 lines per endpoint) |
| FastAPI 0.135+ in this milestone | Crosses Pydantic compat boundary at 0.128; risk to 755-test suite for a cosmetics milestone | Raw StreamingResponse on current 0.115.8 pin; defer FastAPI upgrade |
| External fonts (Google Fonts CDN, FontAwesome CDN) | CDN; violates constraint | System font stack (already in place); Unicode code points for simple icons |
| Tailwind CSS, Bootstrap, Bulma | Require Node build or CDN | Extend existing dashboard.css with CSS token layer |
| HTMX | Adds another vendored JS file; the existing vanilla JS fetch pattern already handles all CRUD; HTMX would duplicate that | Keep existing fetch-based JS; add EventSource for push |

## Version Compatibility

| Package | Version | Compatible With | Notes |
|---------|---------|----------------|-------|
| fastapi | 0.115.8 | starlette ~=0.41, pydantic 2.x | Current pin; raw StreamingResponse SSE works; no change |
| uvicorn[standard] | 0.30.6 | asyncio event loop | SSE async generators run natively in single event loop |
| jinja2 | 3.1.4 | fastapi 0.115 | No change; already rendering one template |
| uPlot (vendored) | 1.6.32 | Chrome 76+, Firefox 67+, Safari 12+ | IIFE build; assigns `window.uPlot`; no bundler needed |
| sse-starlette | 3.4.5 (NOT adding) | starlette>=0.41.3, anyio>=3.6.2, Python>=3.10 | Documented for reference only; not being added |
| fastapi (native SSE) | 0.135.0+ (NOT upgrading now) | pydantic>=2.7.0 required from 0.128 | Native `fastapi.sse.EventSourceResponse`; defer to dep-refresh milestone |

## Sources

- https://pypi.org/project/fastapi/ — version history; 0.115.8 current pin confirmed; 0.135.0 released March 2026; 0.138.0 latest June 2026 (HIGH)
- https://fastapi.tiangolo.com/tutorial/server-sent-events/ — confirmed FastAPI 0.135.0 added `fastapi.sse.EventSourceResponse`; documented raw StreamingResponse pattern compatible with 0.115.x (HIGH)
- https://github.com/fastapi/fastapi/commit/22381558446c5d1ac376680a6581dd63b3a04119 — SSE feature commit merged into 0.135.0 (HIGH)
- https://pypi.org/project/sse-starlette/ — v3.4.5 released June 20, 2026; production stable; Python>=3.10 (HIGH)
- https://github.com/sysid/sse-starlette/blob/main/sse_starlette/sse.py — anyio imports confirmed; starlette>=0.41.3 requirement; uvicorn AppStatus introspection (HIGH)
- https://github.com/leeoniya/uPlot — v1.6.32 released March 2025; MIT license; IIFE dist at `/dist/uPlot.iife.min.js` (~52 KB per GitHub file view) (HIGH)
- https://cdn.jsdelivr.net/npm/chart.js@latest/dist/ — chart.umd.min.js confirmed 203.63 KB (HIGH)
- https://github.com/frappe/charts — last release v1.6.3 April 2022; last npm publish dated 2022 on snyk.io (MEDIUM)
- https://caniuse.com/prefers-color-scheme — >95% browser support; Chrome 76+, Firefox 67+, Safari 12.1+ (HIGH)
- https://claudiorimann.com/svg-charts-without-javascript-part-1/ — hand-rolled SVG polyline feasibility confirmed for 50-100 points; no JS tooltips/zoom available (MEDIUM)
- deepwiki.com/fastapi/fastapi/8.2-breaking-changes-and-migration — 0.128.0 Pydantic v1 shim removal; pydantic floor raised to 2.7.0 (MEDIUM — secondary source, consistent with PyPI release notes)

---
*Stack research for: ShopPyBot v4.1 Dashboard & Observability milestone*
*Researched: 2026-06-25*
