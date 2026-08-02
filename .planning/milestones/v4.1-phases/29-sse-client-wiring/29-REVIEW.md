---
phase: 29-sse-client-wiring
reviewed: 2026-06-27T00:00:00Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - web/templates/dashboard.html
  - web/static/components.css
findings:
  critical: 2
  warning: 3
  info: 2
  total: 7
status: issues_found
---

# Phase 29: Code Review Report

**Reviewed:** 2026-06-27
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

## Summary

Phase 29 wires EventSource to `/api/events`, consuming named `status` and `log` events,
with `onopen`/`onerror` driving a connection indicator. The SSE branch, feature-detect
guard, DOM-cap path, and CSS token usage are structurally sound. Two blockers exist:
unguarded `JSON.parse` in both SSE event handlers (crash on malformed frame), and shared
`_lastLogLine` state that causes the no-dup guard to fire incorrectly after any batch
repaint, silently dropping the first matching SSE log event. Three warnings cover missing
error handling in `loadItems`/`removeItem`/`loadCredentials`/`loadConfig`, and a
`setIndicator` else-branch that swallows unexpected states.

## Critical Issues

### CR-01: Unguarded JSON.parse in SSE event handlers -- uncaught SyntaxError on malformed frame

**File:** `web/templates/dashboard.html:603-604`
**Issue:** Both SSE event handlers call `JSON.parse(e.data)` without a try/catch. A
truncated SSE frame (server restart, proxy buffer flush, any non-JSON data) throws a
`SyntaxError` that is uncaught. The exception does not close the EventSource but it does
abort mid-handler execution -- `renderStatus` may update partial UI state before the
throw, and the error is invisible to the user (indicator stays 'live').

**Fix:**
```js
es.addEventListener('status', function(e) {
  try {
    renderStatus(JSON.parse(e.data));
  } catch (_) { /* malformed frame; next push will correct state */ }
});
es.addEventListener('log', function(e) {
  try {
    var p = JSON.parse(e.data);
    appendLogLine(p.line);
    maybeScrollToBottom();
  } catch (_) { /* discard unparseable log frame */ }
});
```

### CR-02: Shared _lastLogLine sentinel corrupted by batch renderLogLines -- SSE events silently dropped

**File:** `web/templates/dashboard.html:500-513, 522-535`
**Issue:** `appendLogLine` checks `if (lineText === _lastLogLine) return` and then sets
`_lastLogLine = lineText` before appending. `renderLogLines` calls `appendLogLine` in a
loop over the batch, so after any batch repaint (initial load, filter change, manual
refresh) `_lastLogLine` is left pointing at the last line of the batch. Any subsequent
SSE `log` event whose `.line` matches that final batch line is silently suppressed.

This is a real loss: log lines frequently repeat structure (e.g., a recurring check-item
line with identical text). The user triggers a filter refresh, the SSE event for that
same line arrives immediately after, and it is dropped with no indication.

`renderLogLines` also clears `bufferEl.innerHTML = ''` but does NOT reset `_lastLogLine`,
making the sentinel stale across repaints.

**Fix:**
```js
function renderLogLines(lines) {
  var bufferEl = document.getElementById('log-buffer');
  bufferEl.innerHTML = '';
  _lastLogLine = '';          // <-- reset sentinel on full repaint
  if (!lines || lines.length === 0) {
    ...
  }
  lines.forEach(function(line) { appendLogLine(line); });
  maybeScrollToBottom();
}
```

## Warnings

### WR-01: loadItems, loadCredentials, loadConfig have no error handling

**File:** `web/templates/dashboard.html:692-738, 741-806, 809-882`
**Issue:** All three async loaders call `await fetch(...)` and `await resp.json()` without
try/catch. A network error or non-JSON response produces an unhandled promise rejection.
This is inconsistent with `loadConfirmedBuys` (line 405) which wraps the same pattern in
try/catch and renders a user-visible error row. The add-item form calls `loadItems()` on
success (line 662) -- a subsequent network error silently leaves the list stale.

**Fix:** Wrap each loader's body in try/catch matching the `loadConfirmedBuys` pattern.
For `loadItems`, at minimum:
```js
async function loadItems() {
  try {
    const resp = await fetch('/api/items');
    const data = await resp.json();
    ...
  } catch (e) {
    // render an error row or log to console -- do not silently fail
    const tbody = document.getElementById('items-tbody');
    tbody.innerHTML = '<tr><td colspan="5" class="text-secondary">Failed to load items.</td></tr>';
  }
}
```

### WR-02: removeItem has no response-ok check and no error handling

**File:** `web/templates/dashboard.html:672-676`
**Issue:** `removeItem` fires `loadItems()` unconditionally after `await fetch(DELETE)`,
regardless of HTTP status. If the server returns a 404 or 500, the item list refreshes
as if the delete succeeded, potentially showing the item still present (confusing) or
missing (incorrect). The unhandled rejection on network failure is also inconsistent with
`saveCredential` (line 793) which checks `resp.ok`.

**Fix:**
```js
async function removeItem(link) {
  try {
    const b64 = btoa(unescape(encodeURIComponent(link))).replace(/\+/g,'-').replace(/\//g,'_');
    const resp = await fetch('/api/items/' + b64, {method: 'DELETE', headers: {'Content-Type': 'application/json'}});
    if (!resp.ok) { /* optionally surface error */ }
    loadItems();
  } catch (e) {
    /* surface to user or log */
  }
}
```

### WR-03: setIndicator else-branch swallows unknown states

**File:** `web/templates/dashboard.html:347-357`
**Issue:** `setIndicator` uses `if (state === 'live') ... else { reconnecting }`. Any
unexpected string (future third state, typo) silently renders the "Reconnecting" label
and the warn-colored dot, which is misleading. A latent correctness issue as the
indicator grows.

**Fix:**
```js
function setIndicator(state) {
  var dot = document.getElementById('sse-dot');
  var label = document.getElementById('sse-label');
  if (state === 'live') {
    dot.className = 'status-dot running';
    label.textContent = 'Live';
  } else if (state === 'reconnecting') {
    dot.className = 'status-dot reconnecting';
    label.textContent = 'Reconnecting';
  } else {
    dot.className = 'status-dot stopped';
    label.textContent = '';
  }
}
```

## Info

### IN-01: _lastLogLine not reset between consecutive renderLogLines calls (redundant with CR-02 root)

**File:** `web/templates/dashboard.html:486, 522`
**Issue:** The module-level `_lastLogLine = ''` initializer is set once at page load.
There is no reset on full-buffer repaint, making the sentinel persist across all batch
and SSE paths. Beyond the CR-02 failure mode, this means the sentinel carries state
across entirely independent rendering contexts (filter changes, log level switches). The
fix in CR-02 resolves this.

### IN-02: uplot external script loaded after </body> -- fragile async ordering

**File:** `web/templates/dashboard.html:884, 889`
**Issue:** `loadItems()` is called on line 884 inside the main `<script>` block. It
calls `loadPriceChart`, which calls `new uPlot(...)` on line 481. The `uplot.iife.min.js`
`<script>` tag is on line 889, after `</body>`. Because `loadPriceChart` is async
(awaits a fetch), `uPlot` is almost always defined in time. However, if the API response
is cached and resolves before the external script is parsed, `uPlot is not defined` will
throw. The script tag should be placed before the main `<script>` block, or in `<head>`
with `defer`.

_Reviewed: 2026-06-27_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
