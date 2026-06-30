# Phase 25: Design System - Research

**Researched:** 2026-06-25
**Domain:** Vendored CSS design system, light/dark theming, XSS DOM fix, uPlot vendor
**Confidence:** HIGH

## Summary

Phase 25 is a pure front-end refactor with zero Python changes. All decisions are
locked in CONTEXT.md and 25-UI-SPEC.md. Research confirms the implementation is
entirely executable with the existing stack (FastAPI 0.115.8 / Jinja2 3.1.4 / Python
3.13.13 / pytest 8.3.4) and two vendored static files.

The work decomposes into four self-contained operations, each verifiable in isolation:
(1) Create `tokens.css` and `components.css`, reduce `dashboard.css` to layout only;
(2) Add the inline FOUC-prevention script as the first `<head>` child and wire the
theme toggle button in the sticky `<header>`;
(3) Fix the XSS at `loadItems()` line 241 and `loadCredentials()` line 255 using
`createElement`/`textContent`, with a CI grep assertion blocking regression;
(4) Download and commit `uPlot.iife.min.js` and `uPlot.min.css` from the 1.6.32
release to `web/static/vendor/`.

The MC-4 test (`test_banner_renders_when_non_local` in `tests/test_web_dashboard.py`)
is the acceptance gate for the non-local banner. It checks for `"reachable beyond
localhost"` text and `"banner-warning"` CSS class in the rendered HTML. No change to
`web/routes/pages.py` or `web/security.py` is needed; the template's Jinja2
conditional is untouched.

**Primary recommendation:** Execute in wave order: tokens/components CSS files first,
then FOUC + header, then XSS fix + CI grep, then uPlot vendor. Each wave can be
committed and tested independently.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Design tokens (color, spacing, type) | Frontend Static | -- | Pure CSS custom properties; zero server involvement |
| Light/dark theme switching | Browser/Client | -- | `data-theme` on `<html>`, `localStorage`, `matchMedia`; no server state |
| FOUC prevention | Browser/Client | Frontend Server (Jinja2) | Inline script lives in the Jinja2 template `<head>`; execution is client-side |
| XSS fix (safe DOM construction) | Browser/Client | -- | `createElement`/`textContent` replaces `innerHTML` in client JS |
| Non-local banner visibility | Frontend Server (Jinja2) | -- | `{% if is_non_local %}` conditional is server-side template rendering |
| CSRF origin check | API/Backend | -- | `check_origin` FastAPI dependency; unchanged in this phase |
| uPlot vendor file serving | CDN/Static | -- | `StaticFiles` mount at `/static/`; no app code involved |

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Design System Structure and Tokens**
- 3-file CSS split: `tokens.css` (`:root` light + dark blocks), `components.css`
  (component rules using only `var(--xxx)`), `dashboard.css` reduced to layout +
  `@import` of the other two.
- Semantic token naming (`--color-bg`, `--color-surface`, `--color-text`,
  `--color-accent`, `--space-md`, etc.) over raw palette scales.
- Keep system font stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`)
  at 14px base. Zero external/vendored fonts (hard milestone constraint).
- 4px-based spacing scale (4/8/16/24/32) and 4px border-radius.

**Theming (Light/Dark)**
- `data-theme` attribute on `<html>` + `prefers-color-scheme` auto default +
  persisted manual override in localStorage (UI-02 mandate).
- FOUC prevention: inline `<script>` as the FIRST child of `<head>` that reads
  localStorage and sets `data-theme` before any CSS paints.
- Theme toggle is a small button in a sticky top header bar; icon via unicode or
  inline SVG (no icon font).
- Default when no stored preference: follow `prefers-color-scheme` (auto).

**Visual Direction and Density**
- Clean, minimal, utilitarian aesthetic.
- Keep blue accent (`#2563eb`) with a dark-mode variant; retain green/amber/red
  semantic status colors.
- Single-column layout, max-width 900px, centered; add a sticky top status/header
  bar that hosts the theme toggle and reserves space for uptime (preps OBS-09).
- Comfortable density (14px type, 8px paddings).

**Charts and Security Scope**
- Vendor uPlot 1.6.32 (MIT, ~52KB IIFE + ~1KB CSS) to `web/static/vendor/`
  (`uplot.iife.min.js` + `uplot.min.css`), committed to the repo.
- XSS scope: fix `loadItems()` `innerHTML` bug AND `loadCredentials()` `innerHTML`
  usages; add `escHtml()` helper for any unavoidable SVG string interpolation.
- Existing MC-4 test is a done-condition; add a CI grep assertion blocking
  `innerHTML =` on API-sourced data.

### Claude's Discretion

None documented in CONTEXT.md for this phase. The UI-SPEC.md and CONTEXT.md together
specify every implementation detail including exact token values, copy, and component
rules.

### Deferred Ideas (OUT OF SCOPE)

- Actual observability surfaces (health cards, charts, log viewer) -- Phase 28.
- SSE wiring and live updates -- Phases 27/29.
- Per-item price capture for non-Amazon plugins (PRC-01) -- future milestone.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UI-01 | Redesigned dashboard built on a coherent vendored design system (CSS custom-property tokens + reusable component classes) with no external fonts, CDN, or Node build | Confirmed: 3-file CSS split pattern, all token values in UI-SPEC.md; no new build tooling needed |
| UI-02 | Light and dark theme -- auto via `prefers-color-scheme` plus persisted manual toggle (`data-theme` on `<html>`) -- with no FOUC on page load | Confirmed: inline sync script pattern in UI-SPEC.md FOUC contract; `data-theme` attribute selector drives CSS; `matchMedia` + `localStorage` wiring documented |
| UI-03 | All API-sourced values render via safe DOM construction (`textContent`/`createElement`, never `innerHTML`); items-table XSS at `dashboard.html` fixed | Confirmed: XSS at line 241 (`tr.innerHTML` with `${item.name}`, `${item.link}`) and line 255 (`div.innerHTML` with `${cred.name}`) verified by direct code inspection; fix pattern documented in UI-SPEC.md |
| UI-04 | Non-local access warning banner and CSRF origin protections remain visible and intact after redesign (verified by existing MC-4 test) | Confirmed: MC-4 test is `test_banner_renders_when_non_local` in `tests/test_web_dashboard.py`; checks `"reachable beyond localhost"` text and `"banner-warning"` class; zero Python changes in this phase guarantees CSRF gate is untouched |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| CSS Custom Properties | CSS Level 4 (all browsers) | Design tokens -- `--color-*`, `--space-*`, `--text-*` | Native browser feature; zero dependencies; survives theme swap without JS |
| `data-theme` attribute selector | CSS attribute selectors | Theme variant switching | Couples cleanly to `<html data-theme="dark">`; no class namespace collision |
| `localStorage` | Web Storage API | Persisting manual theme choice | Synchronous read in inline script prevents FOUC; survives page reload |
| `window.matchMedia` | CSSOM | OS-level dark preference detection | `prefers-color-scheme: dark` media query; available in all target browsers |

No external packages. No npm. No CDN. All CSS is authored and committed directly.

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| uPlot IIFE build | 1.6.32 (MIT) | Time-series chart; vendored for Phase 28 price charts | Loaded from `/static/vendor/uplot.iife.min.js`; not used in Phase 25 render, just vendored for later |
| pytest | 8.3.4 | Test runner for CI assertions | Existing test suite; grep assertion for `innerHTML` added here |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| CSS custom properties | Sass/Less variables | Sass requires Node; custom properties are native and dynamic (change at runtime without JS rebuild) |
| `data-theme` attribute | `.dark` body class | Attribute is more semantically explicit; avoids class naming collisions |
| uPlot 1.6.32 IIFE | fnando/sparkline (~1KB SVG) | sparkline has no tooltips; uPlot is already decided (locked); fnando was the alternative if tooltips were skippable |
| Inline FOUC script | Server-set cookie + SSR theme | Cookie approach adds a server round-trip and complicates caching; inline script is one-liner and zero overhead |

**Installation:** No npm install. Files are downloaded from GitHub releases and committed.

```bash
# uPlot 1.6.32 -- download from GitHub release, verify SHA, commit
# Source: https://github.com/leeoniya/uPlot/tree/1.6.32/dist
# Files: dist/uPlot.iife.min.js, dist/uPlot.min.css
# Target: web/static/vendor/uplot.iife.min.js, web/static/vendor/uplot.min.css
```

**Version verification:**

uPlot 1.6.32 confirmed available at GitHub release tag 1.6.32. [VERIFIED: github.com/leeoniya/uPlot/tree/1.6.32/dist] Filenames in the dist directory: `uPlot.iife.min.js` and `uPlot.min.css`. Note: GitHub uses uppercase `P` in `uPlot.iife.min.js` -- vendor file should be committed as-is or renamed to match the template reference. The UI-SPEC.md and ROADMAP reference `uplot.iife.min.js` (lowercase). The `<script src>` in the template must match whichever name is committed.

## Package Legitimacy Audit

No packages are installed in Phase 25. uPlot is vendored as a static file committed
directly from the official GitHub release, not installed via any registry.

| Asset | Source | Age | License | Method | Disposition |
|-------|--------|-----|---------|--------|-------------|
| `uPlot.iife.min.js` 1.6.32 | github.com/leeoniya/uPlot release tag | 2022+ project | MIT | Direct GitHub download | Approved -- commit to repo |
| `uPlot.min.css` 1.6.32 | github.com/leeoniya/uPlot release tag | same | MIT | Direct GitHub download | Approved -- commit to repo |

**Registry safety gate:** Not applicable. No npm, PyPI, or other registry is used. Files are committed from GitHub at a pinned tag. Executor must verify SHA matches the 1.6.32 tag before committing (per UI-SPEC.md Registry Safety section).

## Architecture Patterns

### System Architecture Diagram

```
Browser (page load)
  |
  +-- <head> inline sync <script>  -- reads localStorage + matchMedia
  |     sets document.documentElement.dataset.theme
  |     (runs BEFORE any CSS is fetched -- no FOUC)
  |
  +-- <link> tokens.css            -- :root { light tokens }
  |                                   [data-theme="dark"] { dark overrides }
  |
  +-- <link> components.css        -- .card, .btn, .btn-accent, etc. using var(--xxx)
  |
  +-- <link> dashboard.css         -- layout only: .container, .app-header, @import
  |
  +-- Jinja2 server-rendered HTML
        |
        +-- {% if is_non_local %}  -- server decides; banner in HTML or not
        |     .banner-warning      -- styled via --color-destructive tokens
        |
        +-- <header class="app-header">
        |     left: "ShopPyBot" label
        |     center: <span id="header-uptime"> (empty in Phase 25)
        |     right: <button id="theme-toggle"> (unicode sun/moon)
        |
        +-- <div class="container">
              .card sections (Controls, Items, Credentials, Config)
              -- all JS DOM construction uses createElement/textContent
              -- no innerHTML on API-sourced values

JS theme toggle (client)
  click --> toggle dataset.theme --> localStorage.setItem('theme', value)
```

### Recommended Project Structure

```
web/static/
  tokens.css          # :root light + [data-theme="dark"] blocks ONLY
  components.css      # All component rules using var(--xxx) ONLY
  dashboard.css       # Layout + @import "tokens.css"; @import "components.css";
  vendor/
    uplot.iife.min.js # uPlot 1.6.32 IIFE build (~52KB)
    uplot.min.css     # uPlot companion CSS (~1KB)
web/templates/
  dashboard.html      # Modified: FOUC script, header bar, XSS-safe JS, CSS link order
```

### Pattern 1: CSS Token Split

**What:** Three files with strict role separation. `tokens.css` declares ALL custom
properties and NOTHING else. `components.css` uses ONLY `var(--xxx)` -- zero hardcoded
hex. `dashboard.css` handles layout and `@import`s the other two.

**When to use:** Always in Phase 25. Every color reference in `components.css` must
trace to a token.

**Example:**
```css
/* tokens.css */
:root {
  --color-bg:      #f5f5f5;
  --color-surface: #ffffff;
  --color-border:  #d1d5db;
  --color-text:    #111827;
  --color-accent:  #2563eb;
  /* ... full list in UI-SPEC.md Color Tokens section */
}

[data-theme="dark"] {
  --color-bg:      #0f172a;
  --color-surface: #1e293b;
  --color-border:  #334155;
  --color-text:    #f1f5f9;
  --color-accent:  #3b82f6;
  /* ... dark overrides only */
}

/* components.css */
.card {
  background:    var(--color-surface);
  border:        1px solid var(--color-border);
  border-radius: 4px;
  padding:       var(--space-lg);
  margin-bottom: var(--space-2xl);
}

.btn-accent {
  background: var(--color-accent);
  color:      var(--color-accent-fg);
}
```

### Pattern 2: FOUC-Safe Theme Init

**What:** Synchronous inline script as the absolute first child of `<head>`, before
any `<link>` element. Sets `data-theme` on `<html>` before the browser requests CSS.

**When to use:** The FOUC inline script is the ONLY inline `<script>` in `<head>`.
All other JS remains in the `<body>` or at end of `<body>`.

**Example:**
```html
<head>
  <script>
    (function() {
      var t = localStorage.getItem('theme');
      if (t === 'dark' || t === 'light') {
        document.documentElement.dataset.theme = t;
      } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        document.documentElement.dataset.theme = 'dark';
      }
    })();
  </script>
  <link rel="stylesheet" href="/static/tokens.css">
  <link rel="stylesheet" href="/static/components.css">
  <link rel="stylesheet" href="/static/dashboard.css">
</head>
```

No `data-theme` is set if the user has no preference and OS prefers light. The
`:root` block is the light default -- attribute absence = light mode.

### Pattern 3: Safe DOM Construction (XSS Fix)

**What:** Replace `innerHTML = template_literal` with `createElement` + `textContent`
assignment for all API-sourced values.

**When to use:** Everywhere API data enters the DOM. Not needed for fully static
string literals with no API values interpolated.

**Example -- loadItems() fix:**
```javascript
// BEFORE (broken -- XSS):
tr.innerHTML = `<td>${item.name}</td><td>${item.link}</td>...`;

// AFTER (safe):
function makeCell(text) {
  const td = document.createElement('td');
  td.textContent = text;
  return td;
}

data.items.forEach(item => {
  const tr = document.createElement('tr');
  tr.dataset.link = item.link;
  tr.appendChild(makeCell(item.name));
  tr.appendChild(makeCell(item.link));
  tr.appendChild(makeCell(item.auto_buy ? 'Yes' : 'No'));
  tr.appendChild(makeCell(String(item.quantity)));

  const tdAction = document.createElement('td');
  const btn = document.createElement('button');
  btn.className = 'btn-text-destructive';
  btn.type = 'button';
  btn.textContent = 'Remove Item';
  btn.addEventListener('click', () => removeItem(item.link));
  tdAction.appendChild(btn);
  tr.appendChild(tdAction);

  tbody.appendChild(tr);
});
```

**escHtml helper** (for unavoidable SVG string interpolation only -- not needed in Phase 25):
```javascript
function escHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}
```

### Pattern 4: Theme Toggle Wiring

**What:** Button in sticky header reads current `data-theme`, toggles it, persists
to `localStorage`, and updates `aria-label`.

```javascript
const toggleBtn = document.getElementById('theme-toggle');

toggleBtn.addEventListener('click', () => {
  const current = document.documentElement.dataset.theme || 'light';
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  localStorage.setItem('theme', next);
  toggleBtn.setAttribute('aria-label', next === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
  toggleBtn.textContent = next === 'dark' ? '☾' : '☀'; // ☾ or ☀
});
```

### Anti-Patterns to Avoid

- **`@import url('https://...')`:** Any external URL in CSS breaks the zero-CDN constraint and will fail security review.
- **`innerHTML` with template literals containing API data:** The exact bug being fixed. Post-fix, the CI grep assertion must block regression.
- **`onclick="funcName(value)"` attribute on dynamically created elements:** Injects values into an HTML attribute string; replace with `addEventListener`.
- **Hardcoded hex in `components.css`:** Every color must be a `var(--xxx)` call. Hardcoded hex breaks dark mode.
- **FOUC script as external file (`<script src=...>`):** Defeats the purpose -- the browser must fetch it before executing, introducing a round-trip. Must be inline.
- **Multiple `<script>` blocks in `<head>`:** Only the FOUC init script belongs in `<head>`. All other JS stays at end of `<body>`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTML-safe string escaping | Custom regex replace | `createElement` + `textContent` | `textContent` is the browser's own escaping; regex is incomplete and brittle |
| Theme detection | Manual `document.cookie` parser | `localStorage.getItem` + `window.matchMedia` | Standard Web Storage API; synchronous; no server round-trip |
| Chart rendering | `<canvas>` or SVG polyline by hand | Vendored uPlot 1.6.32 | uPlot handles scale, axes, tooltips, time formatting; hand-rolled charts will be incomplete |
| CSS variable fallback | JavaScript-polyfill for CSS variables | Native CSS custom properties | All modern browsers (Chrome 49+, Firefox 31+, Safari 10+) support them natively; no polyfill needed for a localhost operator tool |

**Key insight:** The browser's own DOM APIs (`textContent`, `createElement`) are
the correct XSS mitigation -- they enforce HTML escaping by definition. Any string
substitution approach (regex, escape function applied to `innerHTML`) is an
incomplete substitute.

## Common Pitfalls

### Pitfall 1: FOUC Script Not First in `<head>`
**What goes wrong:** Theme flashes from light to dark on page load. Visible flicker.
**Why it happens:** If any `<link>` precedes the inline script, the browser fetches
and begins applying `:root` light CSS before the script sets `data-theme="dark"`.
**How to avoid:** The inline `<script>` is the LITERAL first child of `<head>`, before
`<meta charset>` even. Order: `<script>` then `<meta>` then `<link>` elements.
**Warning signs:** Dark mode users see a white flash lasting ~50-200ms on cold load.

### Pitfall 2: uPlot Path Mismatch (ROADMAP vs CONTEXT.md)
**What goes wrong:** MC verification for Success Criterion 5 fails if the served
path does not match what the criterion checks.
**Why it happens:** The ROADMAP criterion references `web/static/uplot.min.js` +
`web/static/uplot.min.css` (root of static mount). The CONTEXT.md and UI-SPEC.md
reference `web/static/vendor/uplot.iife.min.js` + `web/static/vendor/uplot.min.css`
(subdir). These are different paths.
**How to avoid:** The UI-SPEC.md Done-Condition 5 specifies `web/static/vendor/` paths
explicitly. The planner should use the `vendor/` subdir paths and note in the PLAN
that the ROADMAP criterion wording is loose -- what matters is the file is served
with no CDN reference, not the exact path. If a MC-4 style test is added for this
criterion, it should match the `vendor/` paths.
**Warning signs:** `GET /static/vendor/uplot.iife.min.js` returns 404 if the
`StaticFiles` mount does not serve subdirectories (it does -- FastAPI `StaticFiles`
serves all paths under the mount point including subdirectories).

### Pitfall 3: `innerHTML` Regression After Fix
**What goes wrong:** A future edit reintroduces `innerHTML` with API data, re-opening
the XSS vector silently.
**Why it happens:** Template string `innerHTML` is the natural reflex for DOM building.
Without an automated guard, regressions slip through.
**How to avoid:** Add a pytest test that greps `dashboard.html` for the pattern
`innerHTML\s*=.*\$\{(item\.|cred\.|data\.)` and fails if found. This is a done-condition for Phase 25 close (UI-SPEC.md XSS Fix Contract).
**Warning signs:** CI is green but the DOM builds a `<b>bold</b>` item name as a real
bold element, not literal text.

### Pitfall 4: `loadCredentials` XSS Overlooked
**What goes wrong:** Only `loadItems()` is fixed; `loadCredentials()` line ~255 still
uses `div.innerHTML` with `${cred.name}` interpolated.
**Why it happens:** The XSS is most obvious in `loadItems()`; the credential row
builder uses the same pattern but is less prominent.
**How to avoid:** The fix scope in CONTEXT.md explicitly covers both functions.
**Warning signs:** A credential named `<img src=x onerror=alert(1)>` executes JS on
dashboard load.

### Pitfall 5: Non-local Banner Copy Changed (MC-4 Dependency)
**What goes wrong:** `test_banner_renders_when_non_local` fails because the text
`"reachable beyond localhost"` was modified during the redesign.
**Why it happens:** Restyling the banner is tempting; the copy looks informal.
**How to avoid:** The UI-SPEC.md Copywriting Contract marks this string as
"MUST NOT be changed (MC-4 test dependency)". Do not alter the banner text.
**Warning signs:** `pytest tests/test_web_dashboard.py::test_banner_renders_when_non_local` fails.

### Pitfall 6: Hardcoded Hex Values Leak into `components.css`
**What goes wrong:** Dark mode does not apply to components that still use hardcoded
hex -- they stay light-mode colored in dark theme.
**Why it happens:** Copy-paste from the existing `dashboard.css` without substituting
the token variable.
**How to avoid:** After writing `components.css`, grep for any `#` hex or `rgb()`
literal. Zero should remain.
**Warning signs:** `.btn-accent` stays `#2563eb` instead of `#3b82f6` in dark mode.

### Pitfall 7: `wrapper.innerHTML = ''` Kept for Config (Safe) vs Items (Unsafe)
**What goes wrong:** Over-fixing `wrapper.innerHTML = ''` (which clears the container
with no API data) wastes time; under-fixing `tr.innerHTML = ...` (which interpolates
API data) leaves XSS open.
**Why it happens:** The fix scope is not always obvious -- `innerHTML = ''` with no
interpolation is safe.
**How to avoid:** The rule is: `innerHTML` assigned a string containing API-sourced
values (`${item.name}`, `${cred.name}`, etc.) must be replaced. Static `innerHTML =
''` or `innerHTML = '<tr>...</tr>'` with no interpolation may remain.
**Warning signs:** CI grep with pattern `innerHTML\s*=\s*.*\$\{(item\.|cred\.|data\.)` catches the dangerous cases; `innerHTML = ''` does not match.

## Code Examples

Verified patterns from official sources and direct codebase inspection:

### Full FOUC Init Script (from UI-SPEC.md)
```html
<!-- Source: 25-UI-SPEC.md FOUC Prevention Contract -->
<head>
  <script>
    (function() {
      var t = localStorage.getItem('theme');
      if (t === 'dark' || t === 'light') {
        document.documentElement.dataset.theme = t;
      } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        document.documentElement.dataset.theme = 'dark';
      }
    })();
  </script>
  <link rel="stylesheet" href="/static/tokens.css">
  <link rel="stylesheet" href="/static/components.css">
  <link rel="stylesheet" href="/static/dashboard.css">
</head>
```

### Header Bar HTML
```html
<!-- Source: 25-UI-SPEC.md Header Bar Contract -->
<header class="app-header">
  <span class="app-header-title">ShopPyBot</span>
  <span id="header-uptime" class="text-secondary"></span>
  <button type="button" id="theme-toggle" class="btn"
          aria-label="Switch to dark mode">&#9728;</button>
</header>
```

### CI Grep Assertion for XSS Regression (pytest)
```python
# Source: 25-UI-SPEC.md XSS Fix Contract -- CI assertion
import re, pathlib

def test_no_innerHTML_with_api_data():
    """Block innerHTML assignments that interpolate API-sourced variables."""
    html = pathlib.Path("web/templates/dashboard.html").read_text(encoding="utf-8")
    pattern = re.compile(r'innerHTML\s*=\s*.*\$\{(item\.|cred\.|data\.|cfg\.|resp\.)')
    matches = pattern.findall(html)
    assert not matches, f"innerHTML with API data found: {matches}"
```

### tokens.css Skeleton (key color tokens)
```css
/* Source: 25-UI-SPEC.md Color Tokens sections */
:root {
  /* spacing */
  --space-xs: 4px; --space-sm: 8px; --space-md: 16px;
  --space-lg: 24px; --space-xl: 32px; --space-2xl: 48px;
  /* typography */
  --text-sm: 12px; --text-body: 14px; --text-lg: 18px; --text-xl: 22px;
  --weight-normal: 400; --weight-semibold: 600;
  --leading-tight: 1.2; --leading-body: 1.5; --leading-ui: 1.4;
  --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  /* light colors */
  --color-bg:                 #f5f5f5;
  --color-surface:            #ffffff;
  --color-border:             #d1d5db;
  --color-text:               #111827;
  --color-text-muted:         #6b7280;
  --color-accent:             #2563eb;
  --color-accent-fg:          #ffffff;
  --color-destructive:        #dc2626;
  --color-destructive-fg:     #ffffff;
  --color-destructive-subtle: #fee2e2;
  --color-status-ok:          #16a34a;
  --color-status-neutral:     #6b7280;
  --color-status-warn:        #d97706;
  --color-status-err:         #dc2626;
}

[data-theme="dark"] {
  --color-bg:                 #0f172a;
  --color-surface:            #1e293b;
  --color-border:             #334155;
  --color-text:               #f1f5f9;
  --color-text-muted:         #94a3b8;
  --color-accent:             #3b82f6;
  --color-accent-fg:          #ffffff;
  --color-destructive:        #ef4444;
  --color-destructive-fg:     #ffffff;
  --color-destructive-subtle: #450a0a;
  --color-status-ok:          #22c55e;
  --color-status-neutral:     #64748b;
  --color-status-warn:        #f59e0b;
  --color-status-err:         #ef4444;
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single `dashboard.css` with hardcoded hex | 3-file split: tokens + components + layout | Phase 25 | Enables dark mode without any JS; tokens drive all color decisions |
| `innerHTML` template string for DOM building | `createElement` + `textContent` | Phase 25 | Closes XSS vector; `<b>bold</b>` in item name renders as literal text |
| No theme support (light only) | `data-theme` attribute + `prefers-color-scheme` auto | Phase 25 | Operator comfort for night-time use; persisted preference survives reload |
| No sticky header | `<header class="app-header">` sticky top | Phase 25 | Establishes slot for OBS-09 uptime (Phase 28) and SSE Live indicator (Phase 29) |

**Deprecated/outdated in this codebase after Phase 25:**
- Hardcoded hex in CSS: replaced by token variables
- `onclick="funcName(value)"` attribute pattern on dynamic elements: replaced by `addEventListener`

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `StaticFiles` mount at `/static/` serves subdirectories including `vendor/` without additional configuration | Pitfall 2, Architecture | If wrong, uPlot files at `/static/vendor/` return 404; fix is to move files to `/static/` root or update StaticFiles mount path |
| A2 | The FOUC inline script as FIRST child of `<head>` (before even `<meta charset>`) is valid HTML and executes synchronously in all target browsers | Architecture, Pitfall 1 | If a browser defers the script, FOUC occurs; risk is LOW -- this is a well-documented pattern |
| A3 | uPlot 1.6.32 IIFE file is named `uPlot.iife.min.js` (uppercase P) on the GitHub release; template reference uses lowercase `uplot.iife.min.js` | Standard Stack | Case mismatch causes 404 on case-sensitive filesystems (Linux); Windows is case-insensitive so may not surface in dev; commit with consistent lowercase name |

## Open Questions

1. **uPlot filename casing**
   - What we know: GitHub dist directory lists `uPlot.iife.min.js` (capital P). UI-SPEC.md references `uplot.iife.min.js` (lowercase). [VERIFIED: github.com/leeoniya/uPlot/tree/1.6.32/dist]
   - What's unclear: The deploy target (Windows dev) is case-insensitive, but if this repo ever runs on Linux, a case mismatch causes 404.
   - Recommendation: Commit the file as `uplot.iife.min.js` (all lowercase, matching the template `<script src>`) regardless of the download filename. Rename on download before committing.

2. **ROADMAP vs UI-SPEC path for uPlot**
   - What we know: ROADMAP Success Criterion 5 says `web/static/uplot.min.js` + `web/static/uplot.min.css` (no vendor subdir). UI-SPEC.md Done-Condition 5 says `web/static/vendor/uplot.iife.min.js` + `web/static/vendor/uplot.min.css`.
   - What's unclear: Which path does the MC verification script (if any) actually check?
   - Recommendation: Follow the UI-SPEC.md Done-Condition 5 (`vendor/` subdir) as the more specific and recent artifact. Add a note in PLAN.md that the ROADMAP criterion is satisfied by any no-CDN path under the static mount.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | pytest test suite | Yes | 3.13.13 | -- |
| pytest | CI assertions, existing tests | Yes | 8.3.4 | -- |
| FastAPI | `TestClient` for MC-4 test | Yes | 0.115.8 | -- |
| Jinja2 | Template rendering | Yes | 3.1.4 | -- |
| Node.js | Build tooling | NOT USED | present but irrelevant | -- (hard constraint: no Node build) |
| Browser | Manual FOUC/theme verification | implicit | -- | Can test OS dark-mode pref via system settings |
| curl | Manual static file verification | available on Windows Git Bash | -- | Use browser DevTools network panel |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None. All required tools are present.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3.4 |
| Config file | `pytest.ini` or inferred from `pyproject.toml` (check repo root) |
| Quick run command | `pytest tests/test_web_dashboard.py tests/test_web_security.py -x -q` |
| Full suite command | `pytest -x -q` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UI-01 | Dashboard renders with `tokens.css`, `components.css`, `dashboard.css` linked in `<head>` | unit (HTTP GET /, check link hrefs) | `pytest tests/test_web_dashboard.py -k "css" -x` | Wave 0 gap |
| UI-01 | `components.css` contains zero hardcoded hex values | unit (file grep) | `pytest tests/test_design_system.py -k "no_hardcoded_hex" -x` | Wave 0 gap |
| UI-01 | `tokens.css` declares all required `--color-*` and `--space-*` tokens | unit (file grep) | `pytest tests/test_design_system.py -k "token_declarations" -x` | Wave 0 gap |
| UI-02 | FOUC inline script is the first child of `<head>` | unit (HTML parse) | `pytest tests/test_web_dashboard.py -k "fouc" -x` | Wave 0 gap |
| UI-02 | FOUC script reads `localStorage` and sets `data-theme` | manual | open browser, set dark theme, reload, observe no flash | -- |
| UI-02 | Theme toggle persists across reloads | manual | browser localStorage inspection | -- |
| UI-03 | `loadItems()` uses only `createElement`/`textContent` -- no `innerHTML` with API data | unit (file grep / CI assertion) | `pytest tests/test_web_dashboard.py -k "no_innerHTML_with_api_data" -x` | Wave 0 gap |
| UI-03 | Item named `<b>bold</b>` renders as literal text in the table | manual | add item via form, inspect DOM | -- |
| UI-04 | Non-local banner renders `"reachable beyond localhost"` and `"banner-warning"` class | unit (existing MC-4) | `pytest tests/test_web_dashboard.py::test_banner_renders_when_non_local -x` | YES |
| UI-04 | Banner absent in local mode | unit (existing) | `pytest tests/test_web_dashboard.py::test_banner_absent_when_local -x` | YES |
| UI-04 | CSRF POST from evil origin returns 403 | unit (existing) | `pytest tests/test_web_security.py::test_csrf_rejected -x` | YES |
| UI-01 | `web/static/vendor/uplot.iife.min.js` served by StaticFiles | unit (GET request) | `pytest tests/test_web_dashboard.py -k "uplot" -x` | Wave 0 gap |

### Sampling Rate

- **Per task commit:** `pytest tests/test_web_dashboard.py tests/test_web_security.py -x -q`
- **Per wave merge:** `pytest -x -q` (full suite)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_design_system.py` -- CSS file static analysis tests:
  - `test_no_hardcoded_hex_in_components` -- grep `components.css` for `#[0-9a-fA-F]{3,6}` or `rgb()`
  - `test_all_required_tokens_declared` -- grep `tokens.css` for each `--color-*` and `--space-*` token from UI-SPEC.md
  - `test_uplot_vendor_files_exist` -- assert `web/static/vendor/uplot.iife.min.js` and `web/static/vendor/uplot.min.css` exist
- [ ] `tests/test_web_dashboard.py` additions:
  - `test_fouc_script_first_in_head` -- parse HTML, verify `<head>` first child is `<script>` containing `localStorage`
  - `test_css_link_order_in_head` -- verify `tokens.css`, `components.css`, `dashboard.css` link elements present
  - `test_no_innerHTML_with_api_data` -- grep `dashboard.html` for `innerHTML\s*=.*\$\{(item\.|cred\.|data\.)`
  - `test_no_external_urls_in_static` -- grep CSS files for `url(http` or `@import url(`

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | unchanged; no auth in this phase |
| V3 Session Management | no | unchanged |
| V4 Access Control | no | CSRF gate unchanged; no Python changes |
| V5 Input Validation | yes | `textContent`/`createElement` for all DOM insertion of API data |
| V6 Cryptography | no | no crypto in this phase |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Stored XSS via item name / item link in items table | Tampering | `createElement` + `textContent` exclusively; CI grep assertion blocks regression |
| Stored XSS via credential name in credentials list | Tampering | same `createElement` + `textContent` fix in `loadCredentials()` |
| Self-XSS via theme toggle aria-label | Tampering | Low risk: value is hardcoded string constant, not API data; `setAttribute('aria-label', constant)` is safe |
| CDN supply-chain injection | Spoofing | No CDN; all files committed to repo at pinned versions |
| CSRF on write endpoints | Tampering | `check_origin` dependency unchanged; zero Python changes in this phase |

## Sources

### Primary (HIGH confidence)

- `E:\repos\ShopPyBot\.planning\phases\25-design-system\25-CONTEXT.md` -- locked decisions
- `E:\repos\ShopPyBot\.planning\phases\25-design-system\25-UI-SPEC.md` -- complete implementation contract
- `E:\repos\ShopPyBot\.planning\research\SUMMARY.md` -- project-level research, Phase A section
- `E:\repos\ShopPyBot\web\templates\dashboard.html` -- direct inspection; XSS locations confirmed at lines 241, 255
- `E:\repos\ShopPyBot\web\static\dashboard.css` -- direct inspection; 181 lines, all hardcoded hex confirmed
- `E:\repos\ShopPyBot\tests\test_web_dashboard.py` -- MC-4 test confirmed at `test_banner_renders_when_non_local`
- `E:\repos\ShopPyBot\tests\test_web_security.py` -- CSRF tests confirmed
- github.com/leeoniya/uPlot/tree/1.6.32/dist -- dist filenames confirmed: `uPlot.iife.min.js`, `uPlot.min.css` [VERIFIED: WebFetch]

### Secondary (MEDIUM confidence)

- MDN Web Docs: CSS Custom Properties, `localStorage`, `matchMedia` -- standard Web APIs, stable [ASSUMED: training knowledge, well-established APIs]
- FOUC prevention inline script pattern -- widely documented; specific implementation from UI-SPEC.md is authoritative [CITED: 25-UI-SPEC.md]

### Tertiary (LOW confidence)

None. All critical claims sourced from locked project artifacts or direct code inspection.

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH -- no new packages; existing stack confirmed by `pip show`
- Architecture: HIGH -- all decisions locked in CONTEXT.md + UI-SPEC.md; confirmed by direct inspection of existing files
- Pitfalls: HIGH -- XSS locations confirmed by direct grep; FOUC pattern sourced from UI-SPEC.md; uPlot path discrepancy surfaced by cross-referencing ROADMAP vs UI-SPEC
- Test map: HIGH -- existing MC-4 tests confirmed present and content-verified; Wave 0 gaps identified precisely

**Research date:** 2026-06-25
**Valid until:** 2026-07-25 (stable domain; no fast-moving dependencies)
