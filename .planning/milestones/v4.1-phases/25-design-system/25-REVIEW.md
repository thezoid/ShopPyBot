---
phase: 25-design-system
reviewed: 2026-06-25T00:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - web/templates/dashboard.html
  - web/static/tokens.css
  - web/static/components.css
  - web/static/dashboard.css
  - tests/test_design_system.py
  - tests/test_web_dashboard.py
findings:
  critical: 2
  warning: 4
  info: 3
  total: 9
status: issues_found
---

# Phase 25: Code Review Report

**Reviewed:** 2026-06-25T00:00:00Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Phase 25 delivers a vendored CSS design-system (tokens + components + dashboard), an anti-FOUC inline script, and a DOM-safe XSS rewrite of `loadItems()` and `loadCredentials()`. The core XSS fix is correct: both functions use `createElement`/`textContent` exclusively on API-sourced data, and `loadConfig()` does the same. No external CDN URLs exist in any CSS file. The non-local banner is preserved. Two critical issues were found: a b64 URL-encode path collision in `removeItem` that silently fails for a class of real product URLs, and a stale docstring in `test_no_innerHTML_with_api_data` that describes a pre-fix state and would cause a false-RED signal on CI during bisect. Four warnings cover the theme-toggle icon/aria-label mismatch on cold load, a silent swallow of network errors in `loadItems`/`removeItem`/`loadConfig`, the SSR `data-link` attribute on the Remove button (unused and bypassed by the JS path), and the `dashboard.css` double-import of already-linked CSS files.


## Critical Issues

### CR-01: `removeItem` b64 encoding is not URL-safe -- trailing `=` padding in URL path

**File:** `web/templates/dashboard.html:255`

**Issue:** `btoa(...)` produces standard base64 which is padded with `=`. The code replaces `+` with `-` and `/` with `_` (correct), but does NOT strip the trailing `=` padding characters. The result is passed directly into a URL path segment: `/api/items/<b64>`. While RFC 3986 permits `=` in path segments, FastAPI's Starlette router percent-encodes or rejects certain characters depending on the path-parameter matcher, and more critically the `=` is not replaced by the replacement chain. For URLs whose byte-length mod 3 equals 1 (producing `==` padding), a real product URL like `https://www.amazon.com/test?a=1&b=2#frag` produces `...ZnJhZw==` in the path. This may cause a 404 from Starlette's path routing if the `=` chars are percent-encoded by `fetch` or the browser's request pipeline -- the server receives `%3D%3D` where the route expects only base64url alphabet characters. The DELETE silently calls `loadItems()` regardless of the response code (line 257), so the failure is invisible to the user and the item is not removed.

**Fix:** Strip padding before building the URL, or use a padding-free encoding throughout:
```javascript
async function removeItem(link) {
  const b64 = btoa(unescape(encodeURIComponent(link)))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');          // strip padding -- urlsafe_b64decode pads server-side
  const resp = await fetch('/api/items/' + b64, {
    method: 'DELETE',
    headers: {'Content-Type': 'application/json'},
  });
  if (!resp.ok) {
    // surface error to user
  }
  loadItems();
}
```
The server already uses `base64.urlsafe_b64decode` which accepts un-padded input (Python adds padding internally via `+ '=='`). Alternatively, add `+ '=' * (-len(link_b64) % 4)` to the server decode and keep client-side as-is, but the client fix is simpler.


### CR-02: `test_no_innerHTML_with_api_data` docstring describes stale pre-fix violations; test cannot catch future regressions in `loadConfig`

**File:** `tests/test_web_dashboard.py:219-235`

**Issue:** The test docstring says "Catches the two current violations: line 241 ... line 255 ..." and "This test is RED until Wave 2 replaces both with createElement/textContent." Wave 2 has already landed (the implementation is green). The stale docstring is misleading during bisect, but worse: the regex pattern only matches `innerHTML = <anything>${item.|cred.|data.|cfg.|resp.}`. It does NOT match a regression of the form `el.innerHTML += someVar` or `el.insertAdjacentHTML('beforeend', item.name)`. If someone introduced `insertAdjacentHTML` with API data, this test would not catch it. The test also does not cover `loadConfig()` at all (the pattern matches `cfg.` but `loadConfig` uses `v` from `Object.entries(data)` -- a regression using `${v}` would be missed). The test's false sense of completeness is a security quality defect.

Additionally, the `test_no_innerHTML_with_api_data` test name is categorized in the "RED until Wave 2" scaffold section (line 139) but the test currently passes (green) -- yet the scaffold comment overhead on lines 139-140 will be emitted by pytest's section skipping logic on older runners.

**Fix:** Update the docstring to reflect current state, and broaden the pattern to also catch `insertAdjacentHTML`:
```python
def test_no_innerHTML_with_api_data(client):
    """Regression: dashboard.html must not interpolate API data via innerHTML
    or insertAdjacentHTML. Covers loadItems, loadCredentials, and loadConfig."""
    import re, pathlib

    html = (pathlib.Path(__file__).parent.parent / "web" / "templates" / "dashboard.html").read_text(encoding="utf-8")

    # innerHTML with any interpolated variable
    inner_html_pattern = re.compile(
        r'innerHTML\s*=\s*.*?\$\{',
        re.DOTALL,
    )
    # insertAdjacentHTML with any interpolated variable
    adjacent_pattern = re.compile(
        r'insertAdjacentHTML\s*\(.*?\$\{',
        re.DOTALL,
    )
    assert not inner_html_pattern.search(html), "innerHTML with template literal found"
    assert not adjacent_pattern.search(html), "insertAdjacentHTML with template literal found"
```


## Warnings

### WR-01: Theme-toggle button initial icon/aria-label is mismatched when dark mode is active on cold load

**File:** `web/templates/dashboard.html:33-34`

**Issue:** The button is hardcoded in SSR HTML as `aria-label="Switch to dark mode"` with the sun icon `&#9728;` (U+2600). When the FOUC script fires (lines 5-12) and applies `data-theme="dark"` -- either from `localStorage` or `prefers-color-scheme` -- the button's label and icon are not updated until the user clicks it. On dark-mode cold load, the button says "Switch to dark mode" (wrong; should say "Switch to light mode") and shows a sun icon (wrong; should show a moon icon). The toggle handler on click computes `current` from `document.documentElement.dataset.theme`, so after one click the state is correct, but the initial render misleads the user.

**Fix:** Add an initializer after the theme-toggle handler to sync the button state:
```javascript
// Sync toggle button to initial theme after FOUC script runs
(function syncToggleBtn() {
  const initial = document.documentElement.dataset.theme || 'light';
  if (initial === 'dark') {
    toggleBtn.setAttribute('aria-label', 'Switch to light mode');
    toggleBtn.textContent = '☮'; // or '☾'
  }
})();
```
Or render the aria-label server-side -- but since the FOUC script runs before JS body, a JS-side sync immediately after the handler registration is sufficient.


### WR-02: `loadItems()`, `removeItem()`, and `loadConfig()` have no error handling -- network failures are invisible

**File:** `web/templates/dashboard.html:274-300` (loadItems), `web/templates/dashboard.html:254-258` (removeItem), `web/templates/dashboard.html:371-444` (loadConfig)

**Issue:** `loadItems()` awaits `fetch` and `resp.json()` with no `try/catch`. If the server is unreachable, the unhandled promise rejection is silently swallowed (no user feedback, no console error surfacing). `removeItem` calls `loadItems()` unconditionally after a DELETE regardless of the response status code -- if the DELETE returns 400/404/500, the item stays in the DB but the UI re-renders the current state with no error shown. `loadConfig` has the same uncaught-rejection pattern. By contrast, `pollStatus` has retry counting and user feedback -- `loadItems`/`loadConfig` should have equivalent guards.

**Fix:**
```javascript
async function loadItems() {
  try {
    const resp = await fetch('/api/items');
    if (!resp.ok) throw new Error('items fetch failed');
    const data = await resp.json();
    // ... existing render logic
  } catch (e) {
    document.getElementById('items-tbody').innerHTML =
      '<tr><td colspan="5" class="text-secondary">Failed to load items.</td></tr>';
  }
}

async function removeItem(link) {
  const b64 = btoa(unescape(encodeURIComponent(link)))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  try {
    const resp = await fetch('/api/items/' + b64, {method: 'DELETE', headers: {'Content-Type': 'application/json'}});
    if (!resp.ok) {
      // surface error -- for now, log or show inline feedback
      console.error('Remove failed:', resp.status);
      return;
    }
  } catch (e) {
    console.error('Remove network error:', e);
    return;
  }
  loadItems();
}
```


### WR-03: SSR `data-link` attribute on the Remove button is unused dead code and bypassed by the JS path

**File:** `web/templates/dashboard.html:82`

**Issue:** The SSR-rendered remove button has `data-link="{{ item[1] }}"` (line 82). This attribute is never read by any JavaScript. The JS-rendered path (`loadItems()`, lines 290-296) creates the button via `createElement` and wires the click to `removeItem(item.link)` via a closure -- it never reads `data-link`. The SSR button has no click handler at all (no event delegation is registered for `.btn-remove`). This means: (a) on initial cold load, before `loadItems()` fires, the SSR remove buttons are silently non-functional; (b) the `data-link` attribute holds the raw URL value including any special characters without click wiring. The SSR table is immediately replaced by `loadItems()` on DOMContentLoaded (line 446), so this is a brief window -- but the user sees the broken buttons flash before the JS replaces them.

**Fix:** Either (a) add event delegation on the `items-tbody` to handle `.btn-remove` clicks using the `data-link` attribute value, making SSR buttons functional before JS fires; or (b) replace the SSR item rows with a simpler static "Loading..." placeholder so the button-flash is not possible:
```html
<tbody id="items-tbody">
  <tr><td colspan="5" class="text-secondary">Loading...</td></tr>
</tbody>
```
This is the simpler fix given that `loadItems()` fires immediately.


### WR-04: `dashboard.css` double-imports already-linked CSS files, creating duplicate style application

**File:** `web/static/dashboard.css:4-5`

**Issue:** `dashboard.css` contains:
```css
@import "tokens.css";
@import "components.css";
```
The HTML template already links all three files separately (lines 17-19). When the browser processes `dashboard.css`, it fires additional requests for `tokens.css` and `components.css`, causing them to be fetched and applied twice. Modern browsers deduplicate identical stylesheets by URL, so visual breakage is unlikely, but the `@import` rules generate extra HTTP requests on first load (before caching). The comment at the top of `dashboard.css` says "layout + @imports for ShopPyBot dashboard", suggesting the intent was for `dashboard.css` to be the single entry point -- but the HTML `<link>` tags were added in addition rather than instead.

**Fix:** Either (a) remove the `@import` lines from `dashboard.css` and keep the three separate `<link>` tags (preferred, as it allows parallel loading); or (b) remove the two explicit `<link>` tags for `tokens.css` and `components.css` from the HTML and rely solely on `@import` inside `dashboard.css`. Option (a) is preferred: separate `<link>` tags load in parallel, while `@import` is sequential.


## Info

### IN-01: `escHtml()` helper is dead code with a misleading comment

**File:** `web/templates/dashboard.html:260-265`

**Issue:** The comment says "for unavoidable SVG string interpolation; unused in Phase 25". The function exists in the shipped artifact but is never called anywhere in the file. Dead code in a security-sensitive helper that exists specifically for XSS mitigation creates two risks: (a) future developers may incorrectly conclude it is the correct pattern to reach for when needing to inject HTML (it is not -- `createElement`/`textContent` is preferred); (b) it adds review surface area with no runtime value. `escHtml` itself is correct (textContent in, innerHTML out is the standard div-escape pattern), but dead code should not ship.

**Fix:** Remove the function if it has no Phase 25 use case. If it is retained for a future phase, move it to a shared module and import it rather than leaving it as unused inline JS.


### IN-02: `test_fouc_script_first_in_head` accesses a private attribute `_first_tag` of the parser class

**File:** `tests/test_web_dashboard.py:186`

**Issue:** The assertion `assert parser._first_tag == "script"` directly accesses a mangled-convention attribute (`_first_tag`) of an inner class. While this is a test-internal class and the risk is low, it is a style issue: the attribute should be exposed as a property (like `script_body` is on line 177) so the assertion reads as `parser.first_tag`. This is inconsistent with the class's own `script_body` property pattern.

**Fix:**
```python
@property
def first_tag(self):
    return self._first_tag
# ...
assert parser.first_tag == "script", ...
```


### IN-03: `test_no_external_urls_in_static` scans vendor files but the comment says vendor is excluded from review

**File:** `tests/test_web_dashboard.py:248-255`

**Issue:** The test uses `static_dir.glob("**/*.css")` which includes `web/static/vendor/uplot.min.css`. The review instructions note that vendored files are intentionally excluded from review, but this test scans them. If a future vendor CSS includes a comment-wrapped URL (e.g., `/* source: https://... */`), the comment-stripping regex would need to be correct. The current stripping regex (`re.sub(r'/\*.*?\*/', '', ..., re.DOTALL)`) is correct and non-greedy, so this is low-risk -- but intentionally scanning vendor files in a test meant for authored CSS is worth noting for maintainability clarity.

**Fix:** Scope the glob to exclude vendor: `static_dir.glob("*.css")` (top-level authored CSS only) or explicitly exclude: `[f for f in static_dir.glob("**/*.css") if "vendor" not in f.parts]`.

---

_Reviewed: 2026-06-25T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
