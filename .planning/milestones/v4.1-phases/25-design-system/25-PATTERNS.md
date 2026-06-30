# Phase 25: Design System - Pattern Map

**Mapped:** 2026-06-25
**Files analyzed:** 7 (new/modified)
**Analogs found:** 7 / 7

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `web/static/tokens.css` | config (CSS custom properties) | static | `web/static/dashboard.css` (`:root` block + color/spacing values) | role-match (new file, extracts from analog) |
| `web/static/components.css` | utility (CSS component rules) | static | `web/static/dashboard.css` (component rules, lines 27-181) | role-match (new file, migrates from analog) |
| `web/static/dashboard.css` (refactored) | config (layout + @imports) | static | `web/static/dashboard.css` (lines 1-25: reset + layout) | exact (same file, reduced in scope) |
| `web/templates/dashboard.html` (modified) | template | request-response | `web/templates/dashboard.html` (existing) | exact (same file, extended) |
| `web/static/vendor/uplot.iife.min.js` | vendor (binary asset) | static | no analog | none (new vendor dir) |
| `web/static/vendor/uplot.min.css` | vendor (binary asset) | static | no analog | none (new vendor dir) |
| `tests/test_design_system.py` | test (static file assertions) | batch (file grep) | `tests/test_web_dashboard.py` (file-content grep pattern at lines 87-98, 114-135) | role-match |
| `tests/test_web_dashboard.py` (additions) | test (template assertions) | request-response | `tests/test_web_dashboard.py` (existing tests) | exact (same file, additions only) |

---

## Pattern Assignments

### `web/static/tokens.css` (config, static)

**Analog:** `web/static/dashboard.css`

**What to extract:** All hardcoded hex values, font-family, and numeric scale values become
token declarations. The file contains ONLY `:root` and `[data-theme="dark"]` blocks.

**Source values from analog** (`web/static/dashboard.css` lines 1-14, full file):

```css
/* Light-mode values currently hardcoded in dashboard.css: */
color: #111827;           /* -> --color-text */
background: #f5f5f5;      /* -> --color-bg */
background: #ffffff;      /* -> --color-surface */
border: 1px solid #d1d5db; /* -> --color-border */
background: #2563eb;      /* -> --color-accent */
background: #dc2626;      /* -> --color-destructive */
background: #16a34a;      /* -> --color-status-ok */
background: #6b7280;      /* -> --color-status-neutral */
background: #fee2e2;      /* -> --color-destructive-subtle */
color: #6b7280;           /* -> --color-text-muted */
font-size: 14px;          /* -> --text-body */
font-size: 12px;          /* -> --text-sm */
font-size: 22px;          /* -> --text-xl */
font-size: 18px;          /* -> --text-lg */
padding: 32px 16px;       /* -> --space-xl (32px), --space-md (16px) */
padding: 24px;            /* -> --space-lg */
margin-bottom: 48px;      /* -> --space-2xl */
gap: 8px;                 /* -> --space-sm */
gap: 4px;                 /* -> --space-xs */
```

**Target structure for tokens.css** (from UI-SPEC.md, fully specified):

```css
/* web/static/tokens.css */
/* NO selector rules. Only custom property declarations. */

:root {
  /* Spacing scale (4px base) */
  --space-xs:  4px;
  --space-sm:  8px;
  --space-md:  16px;
  --space-lg:  24px;
  --space-xl:  32px;
  --space-2xl: 48px;
  --space-3xl: 64px;

  /* Typography */
  --text-sm:         12px;
  --text-body:       14px;
  --text-lg:         18px;
  --text-xl:         22px;
  --weight-normal:   400;
  --weight-semibold: 600;
  --leading-tight:   1.2;
  --leading-body:    1.5;
  --leading-ui:      1.4;
  --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;

  /* Light mode colors */
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

---

### `web/static/components.css` (utility, static)

**Analog:** `web/static/dashboard.css` (lines 27-181 — all component rules)

**Constraint:** Zero hardcoded hex values. Every color reference must be `var(--xxx)`.
Zero `:root` blocks. Does not `@import` anything.

**Source rules to migrate** (from `web/static/dashboard.css`):

Banner (lines 27-34):
```css
/* BEFORE (dashboard.css line 29-33): */
.banner-warning {
  background: #fee2e2;
  border-bottom: 1px solid #dc2626;
  color: #dc2626;
  font-weight: 600;
  padding: 12px 16px;
}

/* AFTER (components.css): */
.banner-warning {
  background:    var(--color-destructive-subtle);
  border-bottom: 1px solid var(--color-destructive);
  color:         var(--color-destructive);
  font-weight:   var(--weight-semibold);
  padding:       var(--space-sm) var(--space-md);
}
```

Card (lines 37-43):
```css
/* BEFORE: */
.card {
  background: #ffffff;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  padding: 24px;
  margin-bottom: 48px;
}

/* AFTER: */
.card {
  background:    var(--color-surface);
  border:        1px solid var(--color-border);
  border-radius: 4px;
  padding:       var(--space-lg);
  margin-bottom: var(--space-2xl);
}
```

Buttons (lines 77-102):
```css
/* BEFORE: */
.btn {
  min-height: 36px; padding: 0 16px; border: none; border-radius: 4px;
  font-size: 14px; font-weight: 600; cursor: pointer;
}
.btn-accent      { background: #2563eb; color: #ffffff; }
.btn-destructive { background: #dc2626; color: #ffffff; }
.btn-sm          { min-height: 30px; padding: 0 12px; font-size: 13px; }
.btn-text-destructive { background: none; border: none; color: #dc2626; cursor: pointer; font-size: 14px; padding: 0; }

/* AFTER: */
.btn {
  min-height:    36px;
  padding:       0 var(--space-md);
  border:        none;
  border-radius: 4px;
  font-size:     var(--text-body);
  font-weight:   var(--weight-semibold);
  cursor:        pointer;
}
.btn:disabled        { opacity: 0.4; cursor: not-allowed; }
.btn-accent          { background: var(--color-accent); color: var(--color-accent-fg); }
.btn-destructive     { background: var(--color-destructive); color: var(--color-destructive-fg); }
.btn-sm              { min-height: 30px; padding: 0 var(--space-sm); font-size: var(--text-sm); }
.btn-text-destructive { background: none; border: none; color: var(--color-destructive); cursor: pointer; font-size: var(--text-body); padding: 0; }
```

Input focus ring (new in components.css — not in current dashboard.css):
```css
input[type=text]:focus-visible,
input[type=number]:focus-visible,
input[type=password]:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
}
```

Status dots (lines 67-75):
```css
/* BEFORE: */
.status-dot.running  { background: #16a34a; }
.status-dot.stopped  { background: #6b7280; }

/* AFTER: */
.status-dot          { display: inline-block; width: 10px; height: 10px; border-radius: 50%; }
.status-dot.running  { background: var(--color-status-ok); }
.status-dot.stopped  { background: var(--color-status-neutral); }
```

Log panel (lines 107-118):
```css
/* BEFORE: */
.log-pre {
  font-size: 12px; line-height: 1.4; background: #f5f5f5;
  border: 1px solid #d1d5db; border-radius: 4px; padding: 8px;
  height: 200px; overflow-y: auto; white-space: pre-wrap; word-break: break-all;
}

/* AFTER: */
.log-pre {
  font-size:    var(--text-sm);
  line-height:  var(--leading-ui);
  background:   var(--color-bg);
  border:       1px solid var(--color-border);
  border-radius: 4px;
  padding:      var(--space-sm);
  height:       200px;
  overflow-y:   auto;
  white-space:  pre-wrap;
  word-break:   break-all;
}
```

Feedback (lines 177-181):
```css
/* BEFORE: */
.field-error { font-size: 12px; color: #dc2626; line-height: 1.4; }
.field-feedback { font-size: 12px; line-height: 1.4; }
.field-feedback.success { color: #16a34a; }
.field-feedback.error   { color: #dc2626; }
.text-secondary { color: #6b7280; }

/* AFTER: */
.field-error            { font-size: var(--text-sm); color: var(--color-destructive); line-height: var(--leading-ui); }
.field-feedback         { font-size: var(--text-sm); line-height: var(--leading-ui); }
.field-feedback.success { color: var(--color-status-ok); }
.field-feedback.error   { color: var(--color-destructive); }
.text-secondary         { color: var(--color-text-muted); }
```

New component for Phase 25 (not in current file):
```css
/* .app-header — sticky top bar */
.app-header {
  position:       sticky;
  top:            0;
  z-index:        100;
  display:        flex;
  align-items:    center;
  justify-content: space-between;
  padding:        0 var(--space-md);
  height:         48px;
  background:     var(--color-surface);
  border-bottom:  1px solid var(--color-border);
}
```

---

### `web/static/dashboard.css` (refactored — layout + @imports only)

**Analog:** `web/static/dashboard.css` lines 1-25 (current reset + layout block)

**What stays in dashboard.css after refactor** — the reset, body base, layout, and
responsive breakpoint. The component rules move to components.css.

**Current layout rules to preserve** (lines 1-25):
```css
/* web/static/dashboard.css — lines 1-25 (layout rules, stays here) */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 14px;
  font-weight: 400;
  line-height: 1.5;
  color: #111827;
  background: #f5f5f5;
}

.container {
  max-width: 900px;
  margin: 0 auto;
  padding: 32px 16px;
}

@media (max-width: 640px) {
  .container { padding: 16px; }
}
```

**Target structure after refactor:**
```css
/* web/static/dashboard.css — layout only after Phase 25 */
@import "tokens.css";
@import "components.css";

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: var(--font-family);
  font-size:   var(--text-body);
  font-weight: var(--weight-normal);
  line-height: var(--leading-body);
  color:       var(--color-text);
  background:  var(--color-bg);
}

.container {
  max-width: 900px;
  margin:    0 auto;
  padding:   var(--space-xl) var(--space-md);
}

@media (max-width: 640px) {
  .container { padding: var(--space-md); }
}
```

---

### `web/templates/dashboard.html` (modified)

**Analog:** `web/templates/dashboard.html` (all 369 lines — same file, additions and fixes)

**Head block change — FOUC script + new CSS links** (currently lines 1-8):
```html
<!-- BEFORE (lines 1-8): -->
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ShopPyBot Dashboard</title>
  <link rel="stylesheet" href="/static/dashboard.css">
</head>

<!-- AFTER: FOUC script FIRST, then split CSS links, then uPlot: -->
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
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ShopPyBot Dashboard</title>
  <link rel="stylesheet" href="/static/tokens.css">
  <link rel="stylesheet" href="/static/components.css">
  <link rel="stylesheet" href="/static/dashboard.css">
  <link rel="stylesheet" href="/static/vendor/uplot.min.css">
</head>
```

**Header bar insertion — add before `.container` div** (currently line 17):
```html
<!-- Insert before <div class="container"> (currently line 17): -->
<header class="app-header">
  <span class="app-header-title">ShopPyBot</span>
  <span id="header-uptime" class="text-secondary"></span>
  <button type="button" id="theme-toggle" class="btn"
          aria-label="Switch to dark mode">&#9728;</button>
</header>

<!-- uPlot vendor script at end of <body> (before closing </body>): -->
<script src="/static/vendor/uplot.iife.min.js"></script>
```

**XSS fix — loadItems() current broken code** (line 241):
```javascript
// BEFORE (dashboard.html line 241 — XSS):
tr.innerHTML = `<td>${item.name}</td><td>${item.link}</td><td>${item.auto_buy ? 'Yes' : 'No'}</td><td>${item.quantity}</td><td><button class="btn-text-destructive" type="button" onclick="removeItem('${item.link.replace(/'/g, "\\'")}')">Remove Item</button></td>`;

// AFTER (safe DOM construction):
function makeCell(text) {
  const td = document.createElement('td');
  td.textContent = text;
  return td;
}

data.items.forEach(item => {
  const tr = document.createElement('tr');
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

**XSS fix — loadCredentials() current broken code** (lines 255-263):
```javascript
// BEFORE (dashboard.html lines 255-263 — XSS):
div.innerHTML = `
  <span class="cred-name">${cred.name}</span>
  <span class="cred-status ${cred.is_set ? '' : 'text-secondary'}">${cred.is_set ? 'Set' : 'Not set'}</span>
  <div class="cred-form">
    <input type="password" placeholder="Enter new value" id="cred-input-${cred.name}" autocomplete="new-password">
    <button type="button" class="btn btn-accent btn-sm" onclick="saveCredential('${cred.name}')">Save Credential</button>
    <span class="field-feedback" id="cred-fb-${cred.name}"></span>
  </div>`;

// AFTER (safe DOM construction):
(data.credentials || []).forEach(cred => {
  const div = document.createElement('div');
  div.className = 'cred-row';

  const nameSpan = document.createElement('span');
  nameSpan.className = 'cred-name';
  nameSpan.textContent = cred.name;

  const statusSpan = document.createElement('span');
  statusSpan.className = cred.is_set ? 'cred-status' : 'cred-status text-secondary';
  statusSpan.textContent = cred.is_set ? 'Set' : 'Not set';

  const credForm = document.createElement('div');
  credForm.className = 'cred-form';

  const input = document.createElement('input');
  input.type = 'password';
  input.placeholder = 'Enter new value';
  input.id = 'cred-input-' + cred.name;
  input.autocomplete = 'new-password';

  const saveBtn = document.createElement('button');
  saveBtn.type = 'button';
  saveBtn.className = 'btn btn-accent btn-sm';
  saveBtn.textContent = 'Save Credential';
  saveBtn.addEventListener('click', () => saveCredential(cred.name));

  const fb = document.createElement('span');
  fb.className = 'field-feedback';
  fb.id = 'cred-fb-' + cred.name;

  credForm.appendChild(input);
  credForm.appendChild(saveBtn);
  credForm.appendChild(fb);
  div.appendChild(nameSpan);
  div.appendChild(statusSpan);
  div.appendChild(credForm);
  container.appendChild(div);
});
```

**Theme toggle JS — add to `<script>` block in `<body>`:**
```javascript
// Theme toggle wiring (add near top of existing <script> block):
const toggleBtn = document.getElementById('theme-toggle');
toggleBtn.addEventListener('click', () => {
  const current = document.documentElement.dataset.theme || 'light';
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  localStorage.setItem('theme', next);
  toggleBtn.setAttribute('aria-label', next === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
  toggleBtn.textContent = next === 'dark' ? '☾' : '☀';
});
```

**Jinja2 + static file patterns to preserve** (lines 10-15, 117):

The `{% if is_non_local %}` conditional and the `.banner-warning` div text must be
preserved verbatim — MC-4 test checks for `"reachable beyond localhost"` and
`"banner-warning"` class. The `<script>` block at end of `<body>` is the location
for all JS (the FOUC init script in `<head>` is the only `<head>` script).

---

### `tests/test_design_system.py` (test, batch/file-grep)

**Analog:** `tests/test_web_dashboard.py`

**Import pattern** (lines 1-6 of test_web_dashboard.py):
```python
"""test_web_dashboard.py: dashboard page rendering tests (Wave 0 scaffold)."""
import pytest
pytest.importorskip("fastapi")

from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
```

**File-grep test pattern** (from test_web_dashboard.py lines 114-135 — asserts on
static template content using string search, not HTTP):
```python
def test_dashboard_no_platform_config_toggles(client):
    """GET / must NOT render per-platform enable checkboxes."""
    resp = client.get("/")
    html = resp.text
    assert 'id="cfg-amazon"' not in html
```

**Target pattern for test_design_system.py** (file-read + regex, no HTTP client needed):
```python
"""test_design_system.py: CSS file static analysis and vendor file existence tests."""
import re
import pathlib

ROOT = pathlib.Path(__file__).parent.parent


def test_no_hardcoded_hex_in_components():
    """components.css must contain zero hardcoded hex or rgb() color values."""
    css = (ROOT / "web" / "static" / "components.css").read_text(encoding="utf-8")
    # Strip comments before scanning
    css_no_comments = re.sub(r'/\*.*?\*/', '', css, flags=re.DOTALL)
    hex_pattern = re.compile(r'(?<![a-zA-Z0-9_-])#[0-9a-fA-F]{3,6}\b')
    rgb_pattern = re.compile(r'rgb\(')
    assert not hex_pattern.search(css_no_comments), "Hardcoded hex found in components.css"
    assert not rgb_pattern.search(css_no_comments), "Hardcoded rgb() found in components.css"


def test_all_required_tokens_declared():
    """tokens.css must declare all --color-* and --space-* tokens from UI-SPEC."""
    css = (ROOT / "web" / "static" / "tokens.css").read_text(encoding="utf-8")
    required = [
        "--color-bg", "--color-surface", "--color-border", "--color-text",
        "--color-text-muted", "--color-accent", "--color-accent-fg",
        "--color-destructive", "--color-destructive-fg", "--color-destructive-subtle",
        "--color-status-ok", "--color-status-neutral", "--color-status-warn",
        "--color-status-err",
        "--space-xs", "--space-sm", "--space-md", "--space-lg",
        "--space-xl", "--space-2xl",
        "--text-sm", "--text-body", "--text-lg", "--text-xl",
        "--weight-normal", "--weight-semibold",
        "--font-family",
    ]
    for token in required:
        assert token in css, f"Token {token!r} not declared in tokens.css"


def test_uplot_vendor_files_exist():
    """uPlot 1.6.32 vendor files must exist at web/static/vendor/."""
    js_path  = ROOT / "web" / "static" / "vendor" / "uplot.iife.min.js"
    css_path = ROOT / "web" / "static" / "vendor" / "uplot.min.css"
    assert js_path.exists(),  f"Missing: {js_path}"
    assert css_path.exists(), f"Missing: {css_path}"
```

---

### `tests/test_web_dashboard.py` (additions — existing file)

**Analog:** `tests/test_web_dashboard.py` (all existing tests — same file)

**Fixture pattern to reuse** (lines 10-21 — same `client` fixture applies to new tests):
```python
@pytest.fixture
def mock_svc():
    svc = MagicMock()
    svc.get_status.return_value = {"running": False}
    svc.list_items.return_value = []
    return svc

@pytest.fixture
def client(mock_svc):
    from web import create_app
    return TestClient(create_app(mock_svc))
```

**Text-presence assertion pattern** (lines 24-46 — used for CSS link and FOUC checks):
```python
def test_dashboard_renders_controls_section(client):
    """GET / renders the Controls section heading."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Controls" in resp.text
```

**New tests to add** (copy import/fixture style from existing file):
```python
def test_fouc_script_first_in_head(client):
    """FOUC inline script must be the first child of <head>."""
    from html.parser import HTMLParser
    # ...parse resp.text, verify first element inside <head> is <script>
    # containing 'localStorage'

def test_css_link_order_in_head(client):
    """tokens.css, components.css, dashboard.css <link> elements must be present."""
    resp = client.get("/")
    assert '/static/tokens.css' in resp.text
    assert '/static/components.css' in resp.text
    assert '/static/dashboard.css' in resp.text

def test_no_innerHTML_with_api_data(client):
    """CI regression: dashboard.html must not interpolate API data via innerHTML."""
    import re, pathlib
    html = pathlib.Path("web/templates/dashboard.html").read_text(encoding="utf-8")
    pattern = re.compile(r'innerHTML\s*=\s*.*\$\{(item\.|cred\.|data\.|cfg\.|resp\.)')
    matches = pattern.findall(html)
    assert not matches, f"innerHTML with API data found: {matches}"

def test_no_external_urls_in_static(client):
    """No CSS file in web/static/ may reference an external URL."""
    import pathlib
    for css_file in pathlib.Path("web/static").glob("*.css"):
        content = css_file.read_text(encoding="utf-8")
        assert 'url(http' not in content, f"External URL in {css_file}"
        assert '@import url(' not in content, f"External @import in {css_file}"

def test_uplot_served(client):
    """uPlot vendor JS must be served from /static/vendor/uplot.iife.min.js."""
    resp = client.get("/static/vendor/uplot.iife.min.js")
    assert resp.status_code == 200
```

---

## Shared Patterns

### Existing test fixture (apply to all new tests in test_web_dashboard.py)
**Source:** `tests/test_web_dashboard.py` lines 10-21
All new `test_web_dashboard.py` tests receive the `client` fixture — no new fixture
setup needed. The `mock_svc` fixture provides `get_status` and `list_items`.

### Static file path convention
**Source:** `web/templates/dashboard.html` line 7 (`href="/static/dashboard.css"`)
All static asset hrefs use `/static/` prefix. Vendor assets use `/static/vendor/`.
The FastAPI `StaticFiles` mount at `/static/` serves all subdirectories including
`vendor/` without additional configuration.

### Jinja2 template conditional pattern
**Source:** `web/templates/dashboard.html` lines 10-15
```html
{% if is_non_local %}
<div class="banner-warning">...</div>
{% endif %}
```
The `is_non_local` flag comes from `app.state.is_non_local` (set in `create_app`).
No change to this pattern in Phase 25 — preserve verbatim including the exact banner
text (`"reachable beyond localhost"`).

### textContent / DOM manipulation pattern (existing, extend)
**Source:** `web/templates/dashboard.html` lines 130-147 (pollStatus) and 294-334
(loadConfig — already uses createElement throughout)

The `loadConfig()` function (lines 289-362) already uses `createElement` + `textContent`
correctly. Use it as the within-file reference for how to build DOM safely:
```javascript
// loadConfig() at lines 294-320 — the correct pattern already in the codebase:
const label = document.createElement('label');
label.textContent = k;
label.htmlFor = 'cfg-' + k;
input = document.createElement('input');
input.type = 'text';
input.value = String(v);   // String() coercion, not interpolation
input.id = 'cfg-' + k;
input.dataset.key = k;
```

### Error handling in async fetch (existing, preserve)
**Source:** `web/templates/dashboard.html` lines 163-181 (bot controls)
```javascript
btn.disabled = true;
try {
  await fetch('/api/bot/start', {method: 'POST', headers: {'Content-Type': 'application/json'}});
} finally {
  btn.disabled = false;
}
```
All new event handlers added for the theme toggle follow the same `try/finally`
disabled-state guard pattern. (Theme toggle has no async fetch, but the JS wiring
style — `addEventListener` not `onclick=` attribute — is the pattern to copy.)

### No-CDN comment convention
**Source:** `web/static/dashboard.css` lines 1-2
```css
/* web/static/dashboard.css: vendored minimal CSS for ShopPyBot dashboard */
/* No CDN. No @import url(). No external fonts. */
```
Preserve this header in the refactored `dashboard.css`. Add equivalent comment to
`tokens.css` and `components.css`.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `web/static/vendor/uplot.iife.min.js` | vendor binary | static | No vendor directory exists yet; no analog for vendored JS in the codebase |
| `web/static/vendor/uplot.min.css` | vendor binary | static | Same — no `web/static/vendor/` directory exists |

For these files: download from `https://github.com/leeoniya/uPlot/tree/1.6.32/dist`,
rename to lowercase (`uplot.iife.min.js`, `uplot.min.css`), commit. No code to
pattern from — executor should follow RESEARCH.md Pitfall 2 (filename casing) and
Pitfall 3 (verify path matches `<script src>` in template).

---

## Metadata

**Analog search scope:** `web/static/`, `web/templates/`, `tests/`
**Files read:** `web/static/dashboard.css` (181 lines), `web/templates/dashboard.html`
  (369 lines), `tests/test_web_dashboard.py` (135 lines), `tests/test_web_security.py`
  (139 lines)
**Pattern extraction date:** 2026-06-25
