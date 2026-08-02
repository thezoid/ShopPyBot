# Phase 28: Frontend Observability Surfaces - Pattern Map

**Mapped:** 2026-06-27
**Files analyzed:** 5 (3 modify, 1 modify-test, 1 new-test)
**Analogs found:** 5 / 5

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `web/templates/dashboard.html` | component (template + inline JS) | request-response + poll | `web/templates/dashboard.html` lines 187-306 (existing `pollStatus`, `pollLogs`, `loadItems`, `loadCredentials`, `removeItem`) | exact — same file, same patterns |
| `web/static/components.css` | config (design system) | n/a | `web/static/components.css` lines 56-107 (`.status-dot`, `.log-pre`, `.card`, `.btn`) | exact — same file, extend in-place |
| `core/health.py` | service (data store) | request-response | `core/health.py` lines 78-83 (`get_snapshot()`) + lines 31-33 (`heartbeat()`) | exact — same function to modify |
| `tests/test_health.py` | test | n/a | `tests/test_health.py` lines 101-106 (`test_snapshot_public_keys_exact`) + lines 18-20 (`test_heartbeat_sets_last_heartbeat`) | exact — same file, same test patterns |
| `tests/test_observability_ui.py` | test (new) | request-response | `tests/test_web_dashboard.py` lines 10-34 (client fixture + section heading assertions) | exact role match |

## Pattern Assignments

### `web/templates/dashboard.html` (template + inline JS, poll)

**Analog:** Same file — extend existing patterns in-place.

**Poll pattern** (lines 159-198): The `pollStatus` / `pollLogs` pair runs on `setInterval(fn, POLL_MS)` with `POLL_MS = 2000`. Phase 28 extends both. `pollStatus` gets two new calls — `renderUptime(data.uptime_secs)` and `renderHealthCards(data)` — inserted after the existing dot/label/button updates. `pollLogs` is rewritten to read filter control values and pass `?level=&search=&n=500`.

```javascript
// lines 155-198 — poll skeleton to extend
const POLL_MS = 2000;
let failCount = 0;

async function pollStatus() {
  try {
    const resp = await fetch('/api/status');
    const data = await resp.json();
    // ... existing status-dot / button updates ...
    // ADD after existing updates:
    // renderUptime(data.uptime_secs);
    // renderHealthCards(data);
    failCount = 0;
  } catch (e) {
    failCount++;
    if (failCount >= 3) { ... }
  }
}

async function pollLogs() {
  try {
    const resp = await fetch('/api/logs');           // extend: add ?level=&search=&n=500
    const data = await resp.json();
    document.getElementById('log-content').textContent = (data.logs || []).join('\n');
    // ADD: renderLogLines(data.logs || []);
  } catch (e) { /* silent */ }
}

setInterval(pollStatus, POLL_MS);
setInterval(pollLogs, POLL_MS);
pollStatus();
pollLogs();
```

**link_b64 pattern** (line 261): The `removeItem` function shows the exact URL-safe base64 encoding required by the Phase 26 endpoint. `loadPriceChart` must use the same pattern.

```javascript
// line 261 — canonical link_b64 encoding; copy verbatim for loadPriceChart
async function removeItem(link) {
  const b64 = btoa(unescape(encodeURIComponent(link))).replace(/\+/g,'-').replace(/\//g,'_');
  await fetch('/api/items/' + b64, {method: 'DELETE', ...});
  loadItems();
}
```

**makeCell / safe-DOM pattern** (lines 274-306): All API values go through `makeCell(text)` which sets `td.textContent`. The `loadItems` forEach shows the createElement chain for table rows. `loadConfirmedBuys` copies this pattern exactly.

```javascript
// lines 274-306 — safe-DOM table row construction
function makeCell(text) {
  const td = document.createElement('td');
  td.textContent = text;
  return td;
}

async function loadItems() {
  const resp = await fetch('/api/items');
  const data = await resp.json();
  const tbody = document.getElementById('items-tbody');
  tbody.innerHTML = '';                        // clear-only innerHTML is allowed
  if (!data.items || data.items.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" class="text-secondary">No items tracked yet...</td></tr>';
    return;
  }
  data.items.forEach(item => {
    const tr = document.createElement('tr');
    tr.appendChild(makeCell(item.name));
    // ... more makeCell calls ...
    tbody.appendChild(tr);
  });
}
```

**loadCredentials createElement chain** (lines 309-353): Shows how to build a richer DOM structure (multiple spans, nested divs, event listeners) without innerHTML. `renderHealthCards` and `renderLogLines` follow this same multi-element createElement pattern.

```javascript
// lines 309-353 — multi-element createElement pattern
async function loadCredentials() {
  const resp = await fetch('/api/credentials');
  const data = await resp.json();
  const container = document.getElementById('credentials-list');
  container.innerHTML = '';
  (data.credentials || []).forEach(cred => {
    const div = document.createElement('div');
    div.className = 'cred-row';
    const nameSpan = document.createElement('span');
    nameSpan.className = 'cred-name';
    nameSpan.textContent = cred.name;        // textContent always — never innerHTML on data
    // ... build more children ...
    div.appendChild(nameSpan);
    container.appendChild(div);
  });
}
```

**escHtml helper** (lines 267-271): Present but unused in Phase 25 (safe-DOM path avoids it). Phase 28 must also avoid it — all new code uses `textContent`.

```javascript
// lines 267-271 — escHtml exists but is NOT the pattern to copy for API data
function escHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}
// Phase 28 rule: use textContent, not escHtml + innerHTML
```

**Section order in HTML** (lines 41-135): New sections are inserted between existing `#section-controls` and `#section-credentials` per the UI-SPEC layout contract. The pattern is `<section class="card" id="section-{name}">` with an `<h2>` heading first.

```html
<!-- lines 41-57 — section card pattern to copy for new sections -->
<section class="card" id="section-controls">
  <h2>Controls</h2>
  ...
</section>
```

**uPlot script tag** (line 456): Already at end of body. `new uPlot(opts, data, el)` is invoked after this script loads. No changes to the tag position required; `loadPriceChart` calls uPlot after items are rendered, which is also post-load.

```html
<!-- line 456 — uPlot global already available at end of body -->
<script src="/static/vendor/uplot.iife.min.js"></script>
```

**header-uptime slot** (line 32): The `<span id="header-uptime" class="text-secondary">` is already in the DOM from Phase 25. `renderUptime` writes to it with `.textContent`.

```html
<!-- line 32 — existing uptime slot; set via textContent only -->
<span id="header-uptime" class="text-secondary"></span>
```

**Page-load call sequence** (lines 452-454): Phase 28 adds `loadConfirmedBuys()` to this block alongside the existing three calls.

```javascript
// lines 452-454 — one-shot load calls on page load
loadItems();
loadCredentials();
loadConfig();
// ADD: loadConfirmedBuys();
```

---

### `web/static/components.css` (design system extension)

**Analog:** Same file — append new rule blocks after line 179.

**Zero hardcoded hex invariant** (lines 1-3 file header comment): Every property in new classes must use `var(--xxx)`. The CI test `test_no_hardcoded_hex_in_components` scans the file after stripping comments.

```css
/* lines 1-3 — invariant enforced by CI */
/* No CDN. No @import url(). No external fonts. */
/* Zero hardcoded hex. All colors via var(--xxx). No :root block. No @import. */
```

**status-dot variants pattern** (lines 64-66): Phase 28 adds `.status-dot.error`. Copy the modifier pattern exactly.

```css
/* lines 64-66 — existing status-dot; Phase 28 adds .error variant */
.status-dot         { display: inline-block; width: 10px; height: 10px; border-radius: 50%; }
.status-dot.running { background: var(--color-status-ok); }
.status-dot.stopped { background: var(--color-status-neutral); }
/* ADD: .status-dot.error { background: var(--color-status-err); } */
```

**card pattern** (lines 34-40): New sections use `<section class="card">`. No new card class needed; `#section-health`, `#section-buys`, `#section-log-viewer` all inherit `.card`.

```css
/* lines 34-40 — .card base; reused for all three new sections */
.card {
  background:    var(--color-surface);
  border:        1px solid var(--color-border);
  border-radius: 4px;
  padding:       var(--space-lg);
  margin-bottom: var(--space-2xl);
}
```

**log-pre pattern** (lines 96-107): The new `.log-buffer` is structurally identical but taller (300px vs 200px), monospace-enforced, and uses the same token-only color/border pattern. Copy the property list, change `height` and class name.

```css
/* lines 96-107 — log-pre is the direct analog for .log-buffer */
.log-pre {
  font-size:     var(--text-sm);
  line-height:   var(--leading-ui);
  background:    var(--color-bg);
  border:        1px solid var(--color-border);
  border-radius: 4px;
  padding:       var(--space-sm);
  height:        200px;     /* .log-buffer uses 300px */
  overflow-y:    auto;
  white-space:   pre-wrap;
  word-break:    break-all;
}
/* .log-buffer: same properties, height: 300px, add font-family: monospace */
```

**btn / btn-sm / btn-accent pattern** (lines 75-89): `#btn-log-follow` and `#btn-log-refresh` reuse these classes. `.btn-accent` is the active-follow state. No new button classes needed.

```css
/* lines 75-89 — all button classes used by log viewer controls */
.btn          { min-height: 36px; padding: 0 var(--space-md); ... }
.btn-accent   { background: var(--color-accent); color: var(--color-accent-fg); }
.btn-sm       { min-height: 30px; padding: 0 var(--space-sm); font-size: var(--text-sm); }
```

**input pattern** (lines 139-160): `.log-controls select` and `input[type=text]` inherit from the existing input rules (min-height, border, border-radius, font-size, focus-visible ring). No new input rules needed for the filter controls; just add `select` to the existing input selector group if it is not present.

```css
/* lines 139-160 — existing input styles that log filter controls inherit */
input[type=text],
input[type=number],
input[type=password] {
  min-height:    36px;
  padding:       0 var(--space-md);
  border:        1px solid var(--color-border);
  border-radius: 4px;
  font-size:     var(--text-body);
  color:         var(--color-text);
  background:    var(--color-surface);
}
/* Add select { } with same properties for log-controls select */
```

**text-secondary** (line 178): Used for empty-state rows and loading placeholders. Already exists; no new class needed.

```css
/* line 178 — reused for all empty-state text */
.text-secondary { color: var(--color-text-muted); }
```

---

### `core/health.py` (service, modify get_snapshot)

**Analog:** Same file — `get_snapshot()` lines 78-83 and `heartbeat()` lines 31-33.

**get_snapshot current implementation** (lines 78-83): The method strips private keys (`_`-prefixed) via dict comprehension. Phase 28 adds `heartbeat_age_secs` as a computed field in the same dict comprehension using the `**{...}` merge + extra key pattern from the RESEARCH.md verified code.

```python
# lines 78-83 — current get_snapshot; Phase 28 adds heartbeat_age_secs
def get_snapshot(self) -> dict[str, dict]:
    """Return a deep copy of per-plugin records with private keys stripped."""
    return {
        name: {k: v for k, v in rec.items() if not k.startswith("_")}
        for name, rec in self._plugins.items()
    }

# Phase 28 replacement:
# def get_snapshot(self) -> dict[str, dict]:
#     now = time.monotonic()
#     return {
#         name: {
#             **{k: v for k, v in rec.items() if not k.startswith("_")},
#             "heartbeat_age_secs": (
#                 None if rec["last_heartbeat"] == 0.0
#                 else round(now - rec["last_heartbeat"], 1)
#             ),
#         }
#         for name, rec in self._plugins.items()
#     }
```

**time.monotonic import** (line 8): `import time` is already at the top. `heartbeat()` on line 33 uses `time.monotonic()` — the same call Phase 28 adds to `get_snapshot()`. No new import needed.

```python
# line 8 — time already imported
import time

# line 31-33 — time.monotonic() already used here; same call in get_snapshot
def heartbeat(self, name: str) -> None:
    self._ensure(name)
    self._plugins[name]["last_heartbeat"] = time.monotonic()
```

**last_heartbeat sentinel** (lines 19-29): `_ensure()` initializes `last_heartbeat` to `0.0`. Phase 28 uses `rec["last_heartbeat"] == 0.0` as the never-heartbeated sentinel to return `None` for `heartbeat_age_secs`.

```python
# lines 19-29 — _ensure shows 0.0 is the never-heartbeated sentinel
def _ensure(self, name: str) -> None:
    if name not in self._plugins:
        self._plugins[name] = {
            ...
            "last_heartbeat": 0.0,   # sentinel: never heartbeated
            ...
        }
```

---

### `tests/test_health.py` (test, modify + add)

**Analog:** Same file — `test_snapshot_public_keys_exact` (lines 101-106) and `test_heartbeat_sets_last_heartbeat` (lines 18-20).

**test_snapshot_public_keys_exact** (lines 101-106): Update `expected_keys` to include `"heartbeat_age_secs"`. The test structure (create registry, heartbeat once, get snapshot, assert exact key set) is unchanged.

```python
# lines 101-106 — update expected_keys set
def test_snapshot_public_keys_exact():
    reg = HealthRegistry()
    reg.heartbeat("PluginA")
    snap = reg.get_snapshot()
    expected_keys = {
        "status", "last_heartbeat", "consecutive_errors",
        "items_checked", "orders_confirmed", "last_error",
        # ADD:
        # "heartbeat_age_secs",
    }
    assert set(snap["PluginA"].keys()) == expected_keys
```

**test_heartbeat_sets_last_heartbeat pattern** (lines 18-20): New tests `test_heartbeat_age_secs_fresh` and `test_heartbeat_age_secs_never` follow this pattern — create registry, call heartbeat (or not), assert snapshot field. No monkeypatching needed; monotonic time advances naturally between heartbeat and get_snapshot calls.

```python
# lines 18-20 — pattern for new heartbeat_age_secs tests
def test_heartbeat_sets_last_heartbeat():
    reg = HealthRegistry()
    reg.heartbeat("PluginA")
    snap = reg.get_snapshot()
    assert snap["PluginA"]["last_heartbeat"] > 0.0

# New test pattern (copy structure):
# def test_heartbeat_age_secs_fresh():
#     reg = HealthRegistry()
#     reg.heartbeat("PluginA")
#     snap = reg.get_snapshot()
#     assert snap["PluginA"]["heartbeat_age_secs"] is not None
#     assert snap["PluginA"]["heartbeat_age_secs"] >= 0.0
#
# def test_heartbeat_age_secs_never():
#     reg = HealthRegistry()
#     reg._ensure("PluginA")          # registered but never heartbeated
#     snap = reg.get_snapshot()
#     assert snap["PluginA"]["heartbeat_age_secs"] is None
```

**test_snapshot_is_json_serializable** (lines 91-98): New `heartbeat_age_secs` is a float or None — both JSON-serializable. This test already covers the new field implicitly once `get_snapshot()` is updated; no change needed to it.

---

### `tests/test_observability_ui.py` (test, new file)

**Analog:** `tests/test_web_dashboard.py` — client fixture pattern (lines 10-22) and section heading assertions (lines 24-40).

**Client fixture** (lines 10-22): Copy exactly. `mock_svc.get_status.return_value` must include the fields the new render functions read — at minimum `{"running": False, "uptime_secs": 0, "plugins": {}}` to avoid KeyError in `renderHealthCards` / `renderUptime` client-side (though those are JS, the static HTML assertions only need the fixture to return a valid status for the Jinja render).

```python
# lines 10-22 — fixture pattern to copy verbatim
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

**Section heading assertion pattern** (lines 24-34): Each new section test: GET `/`, assert 200, assert section ID or heading copy present in `resp.text`.

```python
# lines 24-34 — assertion pattern for new section tests
def test_dashboard_renders_controls_section(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Controls" in resp.text

def test_dashboard_renders_items_section(client):
    resp = client.get("/")
    assert "Items" in resp.text
```

**test_no_innerHTML_with_api_data** (lines 216-235): This test reads `dashboard.html` from disk and regex-scans for interpolated `innerHTML` assignments. It runs unchanged and automatically covers new Phase 28 JS functions — no modification needed. New test file must NOT duplicate it.

```python
# lines 216-235 — existing guard; copy awareness only, do not duplicate
def test_no_innerHTML_with_api_data(client):
    import re, pathlib
    html = (pathlib.Path(__file__).parent.parent / "web" / "templates" / "dashboard.html").read_text(...)
    assign_pattern = re.compile(r'(?:inner|outer)HTML\s*=\s*[`\'"].*?\$\{', re.DOTALL)
    ...
    assert not matches
```

**pytest.importorskip** (line 3): Copy this guard. The new test file is also FastAPI-dependent.

```python
# line 3 — copy this guard to test_observability_ui.py
pytest.importorskip("fastapi")
```

---

## Shared Patterns

### Safe DOM (textContent / createElement)

**Source:** `web/templates/dashboard.html` lines 274-306 (`loadItems`) and lines 309-353 (`loadCredentials`)
**Apply to:** All new JS functions in `dashboard.html` — `renderHealthCards`, `loadConfirmedBuys`, `renderLogLines`, `appendLogLine`

Rule: API-sourced values go to `element.textContent = value`. The only allowed `innerHTML` assignment is a clear: `tbody.innerHTML = ''` or a static literal with no `${}` interpolation. The `test_no_innerHTML_with_api_data` CI regex will catch violations.

### Token-only CSS

**Source:** `web/static/components.css` lines 1-3 (file header) + every existing rule
**Apply to:** All new CSS classes in `components.css`

Rule: every property value that is a color or spacing must be `var(--xxx)`. No hex, no rgb(), no named colors. The CI test `test_no_hardcoded_hex_in_components` in `tests/test_design_system.py` enforces this on the whole file.

### Poll extension pattern

**Source:** `web/templates/dashboard.html` lines 159-198
**Apply to:** `pollStatus` (add `renderUptime` + `renderHealthCards` calls) and `pollLogs` (add filter params + call `renderLogLines`)

Rule: extend the existing `try/catch` block; do not replace the enclosing structure. Phase 29 replaces the poll with SSE by swapping only the data source, so render functions must remain separate from the fetch.

### TestClient fixture

**Source:** `tests/test_web_dashboard.py` lines 10-22
**Apply to:** `tests/test_observability_ui.py`

Copy the `mock_svc` / `client` fixture pair verbatim. Add `pytest.importorskip("fastapi")` at the top.

## No Analog Found

No files in Phase 28 are without a close codebase analog. uPlot instantiation (`new uPlot(opts, data, el)`) has no existing usage in the codebase, but it requires no analog — the API is fully specified in 28-UI-SPEC.md and 28-RESEARCH.md with verified code examples.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | — | — | All five files have exact or role-match analogs in the codebase |

## Metadata

**Analog search scope:** `web/templates/`, `web/static/`, `core/`, `tests/`
**Files read:** 5 source files
**Pattern extraction date:** 2026-06-27
