# Phase 29: SSE Client Wiring — Research

**Researched:** 2026-06-27
**Domain:** Browser-side EventSource API, polling-to-SSE migration, feature-detect fallback
**Confidence:** HIGH

## Summary

Phase 29 is a pure JavaScript refactor of `web/templates/dashboard.html`. All server-side work
(the `/api/events` endpoint, `SseHub`, `_poll_loop`, `tail_log_lines` cursor, reconnect via
`retry: 3000`) is complete in Phases 27 and 28. The sole deliverable here is wiring the browser to
that stream.

The current template has two `setInterval` calls (lines 571-574): `setInterval(pollStatus, 2000)`
and `setInterval(pollLogs, 2000)`, plus immediate `pollStatus()` and `pollLogs()` calls on load.
`pollStatus()` (lines 321-355) contains both the render logic (status dot/label, start/stop button
state, `renderHealthCards`, `renderUptime`) and the fetch. `pollLogs()` (lines 536-555) fetches
`/api/logs` and calls `renderLogLines`. Phase 29 surgically replaces these two intervals with one
`EventSource('/api/events')` while preserving all render logic unchanged.

The three main risks are all mechanical: (1) `renderStatus` must carry the button enable/disable
logic currently embedded in `pollStatus` -- nothing in the SSE `status` handler can skip that; (2)
the no-dup guard must be added to `appendLogLine` before SSE is wired (the backfill from
`/api/logs` on load and the first SSE `log` event can deliver overlapping lines); (3) the
Live/Reconnecting indicator element must be added to the sticky header HTML before the JS wiring
references its id.

No new packages. No Python changes. pytest is the test runner.

**Primary recommendation:** Refactor `pollStatus` body into `renderStatus(data)` first (zero
observable change, full test coverage stays green), wire SSE second, add indicator third. Each step
is independently committable.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| SSE event dispatch | Browser/Client | -- | `EventSource` is a browser API; server contract already live |
| Live health-card updates | Browser/Client | -- | `renderHealthCards` (Phase 28) accepts status payload; SSE triggers it |
| Live log append | Browser/Client | -- | `appendLogLine` (Phase 28) accepts one line; SSE `log` event triggers it |
| Polling fallback | Browser/Client | -- | `typeof EventSource` feature-detect; else existing `setInterval` resumes |
| Live/Reconnecting indicator | Browser/Client | -- | `onopen`/`onerror` callbacks update DOM element in sticky header |
| Backfill on load | Browser/Client | API/Backend | One-shot `GET /api/status` + `GET /api/logs` before SSE takes over |
| Reconnect timing (3s) | API/Backend | Browser/Client | Server `retry: 3000` frame controls delay; browser obeys natively |

## Standard Stack

### Core (no new additions)

| Asset | Source | Purpose |
|-------|--------|---------|
| `EventSource` (native) | Browser Web API | Persistent SSE connection; auto-reconnect |
| `/api/events` | Phase 27 (`web/routes/sse.py`) | Emits `event: status` + `event: log` frames |
| `dashboard.html` JS | Phase 28 | `renderHealthCards`, `renderUptime`, `renderLogLines`, `appendLogLine`, `maybeScrollToBottom` |
| `components.css` | Phase 28 | `.status-dot`, `.badge`, status tokens for indicator |

**No new Python packages. No npm. No CDN.** [VERIFIED: 29-CONTEXT.md locked decision]

### Existing Functions (reused, not rewritten)

| Function | Lines (dashboard.html) | Phase 29 role |
|----------|------------------------|---------------|
| `renderHealthCards(statusPayload)` | 235-303 | Called from new `renderStatus(data)` |
| `renderUptime(uptimeSecs)` | 314-316 | Called from new `renderStatus(data)` |
| `renderLogLines(lines)` | 497-510 | Called once on load for backfill |
| `appendLogLine(lineText)` | 477-488 | Called per SSE `log` event (+ no-dup guard added here) |
| `maybeScrollToBottom()` | 490-495 | Unchanged |
| `pollStatus()` | 321-355 | Body extracted to `renderStatus(data)`; function kept as polling fallback wrapper |
| `pollLogs()` | 536-555 | Kept as polling fallback; removed from `setInterval` when SSE active |
| `logFollowEnabled`, `logSearchTimer` | 463-569 | Unchanged; filter controls still wire to `pollLogs` for manual refresh |

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE reconnect loop | Manual `setTimeout` reconnect in `onerror` | Native `EventSource` auto-reconnect | Server sends `retry: 3000`; browser reconnects automatically; manual loop on top would double-reconnect |
| Duplicate-line detection | Full hash set of all lines | Last-line string compare | Hash set grows unbounded; last-line is sufficient for the backfill/stream boundary (sequential cursor guarantees no out-of-order delivery) |
| SSE polyfill | Custom `XHR`-based EventSource | `typeof EventSource` feature-detect + `setInterval` fallback | The existing poll is already written; polyfill overhead unwarranted for a localhost single-operator tool |

## Architecture Patterns

### System Architecture Diagram

```
Page Load
  |
  +-- fetch /api/status  --->  renderStatus(data)   [immediate paint]
  +-- fetch /api/logs    --->  renderLogLines(lines) [backfill paint]
  |
  +-- typeof EventSource !== 'undefined'?
        YES ---> new EventSource('/api/events')
        |         |
        |         +-- onopen  --->  setIndicator('live')
        |         +-- onerror --->  setIndicator('reconnecting')
        |         |
        |         +-- addEventListener('status', e)
        |         |     JSON.parse(e.data) ---> renderStatus(data)
        |         |
        |         +-- addEventListener('log', e)
        |               JSON.parse(e.data).line ---> [no-dup guard] ---> appendLogLine(line)
        |                                                                 maybeScrollToBottom()
        |
        NO  ---> setInterval(pollStatus, 2000)
                 setInterval(pollLogs, 2000)
                 [same behavior as Phase 28; no JS error]
```

### Surgical Change Map

The changes touch exactly these locations in `dashboard.html`:

1. **HTML: sticky header** (lines 30-35): add `<span id="sse-indicator">` between
   `#header-uptime` and `#theme-toggle`. Uses `textContent` only. Token colors for dot.

2. **JS: `renderStatus(data)` extraction** (after line 319, before `pollStatus`): new pure
   function that contains the current `pollStatus` body (lines 324-345) minus the `fetch` call.
   `pollStatus` becomes a thin wrapper: `fetch(...).then(data => renderStatus(data))`.

3. **JS: no-dup guard in `appendLogLine`** (line 477 area): add `var _lastLogLine = ''` module
   variable; at top of `appendLogLine`, `if (lineText === _lastLogLine) return;` then
   `_lastLogLine = lineText;`.

4. **JS: SSE wiring block** (replace lines 571-574): the two `setInterval` + immediate calls
   become the feature-detect block described in the diagram above.

5. **JS: `setIndicator(state)` helper**: pure function; takes `'live'` or `'reconnecting'`;
   updates `#sse-indicator` dot class and label text using `textContent` only. Zero hex.

### Pattern 1: Named Event Listener

The `/api/events` stream uses SSE named events (`event: status\n`, `event: log\n`). Named events
require `addEventListener`, not `onmessage`. `onmessage` only fires for frames with NO `event:`
field. [CITED: https://html.spec.whatwg.org/multipage/server-sent-events.html#dispatchMessage]

```javascript
// Source: HTML Living Standard §9.2.7; confirmed against web/routes/sse.py frame format
var es = new EventSource('/api/events');

es.addEventListener('status', function(e) {
  renderStatus(JSON.parse(e.data));
});

es.addEventListener('log', function(e) {
  var payload = JSON.parse(e.data);
  appendLogLine(payload.line);
  maybeScrollToBottom();
});

es.onopen = function() { setIndicator('live'); };
es.onerror = function() { setIndicator('reconnecting'); };
```

Server frame format (from `web/sse_hub.py` line 54):
```
event: status\ndata: {"running": true, "uptime_secs": 42, "plugins": {...}}\n\n
event: log\ndata: {"line": "[INFO] 2026-06-27 12:00:00 — Bot started"}\n\n
```

`e.data` is the string after `data:` with leading space stripped by the browser. Always
`JSON.parse(e.data)` before use. [CITED: MDN EventSource docs — confirmed matching server format]

### Pattern 2: Feature Detect + Fallback

```javascript
// Source: HTML Living Standard §9.2 (EventSource browser support)
// [ASSUMED] typeof check is canonical cross-browser guard
if (typeof EventSource !== 'undefined') {
  var es = new EventSource('/api/events');
  // ... SSE wiring ...
} else {
  // Existing polling behavior — already written in Phase 28
  setInterval(pollStatus, POLL_MS);
  setInterval(pollLogs, POLL_MS);
  pollStatus();
  pollLogs();
}
```

No `setInterval` calls when SSE is active. The backfill fetch calls (`pollStatus()` /
`pollLogs()` as one-shots before the SSE block) are executed regardless of path.

### Pattern 3: No-Dup Guard

```javascript
// Placement: top of appendLogLine (dashboard.html line 477 area)
var _lastLogLine = '';

function appendLogLine(lineText) {
  if (lineText === _lastLogLine) return;   // skip exact duplicate of immediately-preceding line
  _lastLogLine = lineText;
  // ... rest of existing appendLogLine body ...
}
```

Why last-line compare is sufficient: `tail_log_lines(cursor)` sends lines starting at cursor
position; the backfill `renderLogLines` renders lines 0..N-1; the first SSE `log` event
continues from cursor N. The only overlap scenario is the final backfill line and the first SSE
event for the same line. Identical adjacent lines from actual log output are legitimately filtered
too -- acceptable given this is a tail viewer, not an analytics sink. [ASSUMED: cursor delivery
guarantees no out-of-order; confirmed by reading `web/sse_hub.py` `_poll_loop` cursor logic]

### Pattern 4: Live/Reconnecting Indicator

```html
<!-- Add to .app-header, between #header-uptime and #theme-toggle -->
<span id="sse-indicator" class="sse-indicator" aria-live="polite">
  <span class="status-dot" id="sse-dot"></span>
  <span id="sse-label" class="text-secondary"></span>
</span>
```

```javascript
function setIndicator(state) {
  var dot   = document.getElementById('sse-dot');
  var label = document.getElementById('sse-label');
  if (state === 'live') {
    dot.className   = 'status-dot running';   // --color-status-ok via existing class
    label.textContent = 'Live';
  } else {
    dot.className   = 'status-dot stopped';   // --color-status-warn per CONTEXT decision
    label.textContent = 'Reconnecting';
  }
}
```

Note: `--color-status-warn` is referenced in the CONTEXT as the Reconnecting color, but
`status-dot.stopped` maps to `--color-status-neutral`. A one-liner CSS addition is needed in
`components.css` if the spec requires amber (warn) for Reconnecting:

```css
/* components.css addition — if reconnecting requires warn color */
.status-dot.reconnecting { background: var(--color-status-warn); }
```

Then use `dot.className = 'status-dot reconnecting'` for the Reconnecting state. The planner
should resolve this: use `.stopped` (neutral/gray) or add `.reconnecting` (amber). The
`test_no_hardcoded_hex_in_components` guard will catch any accidental hex in this addition.

### Anti-Patterns to Avoid

- **`es.onmessage` for named events:** Named events (`event: status`) never fire `onmessage`.
  Always use `es.addEventListener('status', cb)` and `es.addEventListener('log', cb)`.
- **Manual reconnect loop in `onerror`:** `onerror` fires on reconnect attempts too. Adding a
  `setTimeout(() => new EventSource(...))` creates a second EventSource alongside the native
  one. Native reconnect is automatic; `onerror` is for indicator-only.
- **Starting `setInterval` when SSE active:** Criterion 1 requires zero poll requests while SSE
  is connected. The feature-detect gate (either SSE OR polling, not both) enforces this.
- **`innerHTML` for indicator text:** Violates `test_no_innerHTML_with_api_data` (it scans the
  whole template file). Use `textContent`.
- **Calling `renderLogLines` on every SSE log event:** `renderLogLines` does `innerHTML = ''`
  then re-renders all lines. SSE `log` events call only `appendLogLine` + `maybeScrollToBottom`.

## Exact Current Poll Structure (line reference)

Lines cited from `dashboard.html` as-read on 2026-06-27:

| Element | Line(s) | Notes |
|---------|---------|-------|
| `POLL_MS = 2000` | 204 | Reuse as fallback constant |
| `failCount` | 205 | Keep for polling error path |
| `pollStatus()` definition | 321-355 | Extract body into `renderStatus(data)` |
| `renderHealthCards` called inside pollStatus | 341 | Moves to `renderStatus` |
| `renderUptime` called inside pollStatus | 340 | Moves to `renderStatus` |
| `failCount` reset / error path | 342-354 | Stays inside `pollStatus` catch block |
| `pollLogs()` definition | 536-555 | Keep as-is; only removed from `setInterval` |
| Filter-control IIFE (`log-level-filter` etc.) | 557-569 | Unchanged; still calls `pollLogs()` |
| `setInterval(pollStatus, POLL_MS)` | 571 | REMOVE (SSE path) or KEEP (fallback path) |
| `setInterval(pollLogs, POLL_MS)` | 572 | REMOVE (SSE path) or KEEP (fallback path) |
| `pollStatus()` (immediate call) | 573 | Replace with one-shot backfill fetch |
| `pollLogs()` (immediate call) | 574 | Replace with one-shot backfill fetch |
| `appendLogLine` definition | 477-488 | Add no-dup guard at top |
| `MAX_LOG_LINES = 500` | 319 | Unchanged |

**Key constraint:** `pollStatus` catch block updates `#log-content` (line 347:
`document.getElementById('log-content').textContent = 'Connection lost — retrying...'`). This
is an old `<pre id="log-content">` element still in the Controls card (line 55). It is NOT the
`#log-buffer` log viewer. The SSE error path does not need to replicate this; `setIndicator`
handles connection state for SSE. The `#log-content` update is polling-path-only.

## Common Pitfalls

### Pitfall 1: `onmessage` vs named event listeners
**What goes wrong:** `es.onmessage` is never called for `event: status` / `event: log` frames.
The browser routes named events only to listeners registered with `addEventListener(name, cb)`.
The stream appears connected (`onopen` fires) but no updates render.
**Why it happens:** MDN examples often show `onmessage` for unnamed events; this stream uses
named events exclusively.
**How to avoid:** Always `es.addEventListener('status', cb)` and `es.addEventListener('log', cb)`.
**Warning signs:** `onopen` fires, indicator shows Live, but health cards never update.

### Pitfall 2: Double reconnect from manual onerror handler
**What goes wrong:** Adding `es.onerror = () => { setTimeout(() => new EventSource(...), 3000) }`
creates a second EventSource. Native reconnect already fires; you get two concurrent streams.
**Why it happens:** `onerror` fires during reconnect wait too (EventSource CONNECTING state), so
the manual loop races native reconnect.
**How to avoid:** `onerror` is for indicator update only. No `new EventSource` inside it.
**Warning signs:** DevTools Network shows two simultaneous `text/event-stream` connections.

### Pitfall 3: Skipping `renderStatus` extraction
**What goes wrong:** If the SSE `status` handler duplicates the button-state logic from
`pollStatus` inline, the two paths drift. Future changes must be made twice.
**Why it happens:** It looks simpler to inline the handler body.
**How to avoid:** Extract `renderStatus(data)` first, before wiring SSE. Both paths call it.
**Warning signs:** Start/Stop button state correct on poll but stale on SSE update (or vice versa).

### Pitfall 4: `renderLogLines` on every SSE log event
**What goes wrong:** `renderLogLines` clears `innerHTML = ''` then re-renders. Calling it on
every incremental SSE line flickers the buffer and loses scroll position.
**Why it happens:** It is the existing "render logs" function; feels natural to call on each event.
**How to avoid:** SSE `log` events call only `appendLogLine` (which respects the 500-line DOM cap
and the no-dup guard). `renderLogLines` is one-shot for backfill only.

### Pitfall 5: No-dup guard too broad
**What goes wrong:** A strict guard comparing ALL previous lines (hash set) rejects legitimate
repeated lines ("Bot loop tick") that are genuinely consecutive.
**Why it happens:** Trying to deduplicate the entire history.
**How to avoid:** Last-line compare only. If `lineText === _lastLogLine`, skip. This prevents
the backfill/stream boundary overlap (the one real duplicate source) without suppressing valid
repeated log entries across non-consecutive time.

### Pitfall 6: Indicator element missing before JS references it
**What goes wrong:** `document.getElementById('sse-dot')` returns `null` if the HTML element
is not yet in the template when `setIndicator` is called on `onopen`.
**Why it happens:** JS wiring added before the HTML element is added to the template.
**How to avoid:** Add the `<span id="sse-indicator">` HTML to the header first; JS wiring second.

### Pitfall 7: `test_no_hardcoded_hex_in_components` failure
**What goes wrong:** Adding a `.status-dot.reconnecting` rule with a hardcoded hex color fails
the existing CSS guard in `test_design_system.py`.
**How to avoid:** Use only `var(--color-status-warn)` in any CSS addition. Verify the rule has
no `#` or `rgb()` literals before committing.

### Pitfall 8: `test_no_innerHTML_with_api_data` scope
**What goes wrong:** The regex scans the entire `dashboard.html` file including the SSE wiring
block. Any `innerHTML = \`...\${...\`` in the new code fails the guard.
**How to avoid:** Use `textContent` for all indicator/status updates. The indicator label
text (`'Live'`, `'Reconnecting'`) is static string literal, not API data, but the pattern
still applies for consistency.

## Validation Architecture

`nyquist_validation: true` in `.planning/config.json`.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (project-standard; `pytest.ini` or `pyproject.toml`) |
| Config file | see project root |
| Quick run | `rtk pytest tests/test_web_dashboard.py tests/test_observability_ui.py tests/test_design_system.py -x` |
| Full suite | `rtk pytest` |

### Phase 29 — Automatable vs Manual UAT Split

#### Automatable (static template assertions via `TestClient GET /`)

These can be new tests in `tests/test_web_dashboard.py` or a new `tests/test_sse_wiring.py`:

| ID | Behavior | Test type | Command | Notes |
|----|----------|-----------|---------|-------|
| W29-A1 | Template contains `EventSource` string | Static string | `assert "EventSource" in resp.text` | Confirms wiring code present |
| W29-A2 | Template contains `addEventListener('status'` | Static string | `assert "addEventListener('status'" in resp.text` | Named listener present |
| W29-A3 | Template contains `addEventListener('log'` | Static string | `assert "addEventListener('log'" in resp.text` | Named listener present |
| W29-A4 | Template contains `typeof EventSource` | Static string | `assert "typeof EventSource" in resp.text` | Feature-detect present |
| W29-A5 | Template contains `renderStatus` | Static string | `assert "renderStatus" in resp.text` | Shared render fn present |
| W29-A6 | Template contains `_lastLogLine` | Static string | `assert "_lastLogLine" in resp.text` | No-dup guard present |
| W29-A7 | Template contains `id="sse-indicator"` or `id="sse-dot"` | Static string | `assert 'id="sse-indicator"' in resp.text` | Indicator element present |
| W29-A8 | `test_no_innerHTML_with_api_data` still green | Regression | existing test | No new innerHTML sinks |
| W29-A9 | `test_no_hardcoded_hex_in_components` still green | Regression | existing test | Any new CSS uses tokens only |
| W29-A10 | MC-4 banner test still green | Regression | `test_banner_renders_when_non_local` | Header change did not drop banner |
| W29-A11 | `setInterval` not present in SSE code path | Static scan | regex check that `setInterval` not called outside the `else` fallback branch | Criterion 1: no polling when SSE active |

W29-A11 requires a regex that confirms both `setInterval` calls are inside the `else` branch of
the feature-detect. Approach: extract the JS block from the template and assert the
`setInterval` strings are only present after an `else {` or `} else {` that follows
`typeof EventSource`.

#### Inherently Manual UAT (DevTools / live observation)

| Criterion | Why manual | How to verify |
|-----------|------------|---------------|
| One `text/event-stream` replaces two polls (criterion 1) | Requires live network tab; `TestClient` is synchronous HTTP | DevTools Network: confirm single persistent stream, no `api/status` or `api/logs` periodic requests |
| Health cards update within 1-2s of bot start/stop (criterion 2) | Requires live bot + SSE push timing | Start/stop via UI; observe card status dot change without reload |
| Log lines appear exactly once (criterion 3) | Requires live SSE stream + backfill overlap observation | Reload page; verify lines visible before SSE connects; no duplicate on stream attach |
| Tab close/reopen clean reconnect (criterion 4) | Requires tab lifecycle | Close tab; reopen; DevTools: one new stream, previous connection closed server-side |
| No `EventSource` support falls back cleanly (criterion 5) | Requires patching `EventSource` in browser | DevTools console: `window.EventSource = undefined`; reload; observe poll requests resume |

#### Wave 0 Gaps

- [ ] `tests/test_sse_wiring.py` — new file covering W29-A1 through W29-A11
  - Alternative: add to `tests/test_web_dashboard.py` under a `# Phase 29` section
  - All assertions are `TestClient GET /` + string/regex checks; no async machinery needed
- [ ] No framework install needed (pytest already installed)
- [ ] No fixture changes needed (existing `client` fixture from `test_web_dashboard.py` works)

### Sampling Rate

- Per task commit: `rtk pytest tests/test_web_dashboard.py tests/test_observability_ui.py tests/test_design_system.py -x`
- Per wave merge: `rtk pytest`
- Phase gate: full suite green before `/gsd:verify-work`

## Package Legitimacy Audit

No new packages in this phase. Frontend-only change to an existing template file.
Package Legitimacy Gate: skipped (no new installs).

## Environment Availability

| Dependency | Required By | Available | Notes |
|------------|------------|-----------|-------|
| Python / pytest | Test suite | Confirmed (prior phases ran) | No version check needed |
| Browser with EventSource | Manual UAT | All modern browsers | IE11 needs polyfill — out of scope for localhost tool |
| FastAPI dev server | Manual UAT | Confirmed (Phase 28 verified) | `python main.py` |

Step 2.6 SKIPPED for automated test environment: no new external tools.

## Runtime State Inventory

Not a rename/refactor/migration phase. No stored data, live service config, OS registrations,
secrets, or build artifacts reference the changed code. The only affected file is
`web/templates/dashboard.html` (served on each page load; no caching layer).

**Nothing found in any category** -- verified: the template is rendered fresh on each `GET /`.

## Security Domain

`security_enforcement` not explicitly disabled. Checking applicable ASVS categories.

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No auth change; CSRF guard unchanged |
| V3 Session Management | No | No session change |
| V4 Access Control | No | `/api/events` is read-only GET; no CSRF guard required (matches existing posture) |
| V5 Input Validation | No | No new user input; indicator text is static literals |
| V6 Cryptography | No | No crypto |

No new threat surface. `EventSource` connections are same-origin (localhost), read-only,
no cookies or headers beyond what the browser sends automatically. The existing `check_origin`
guard on POST/DELETE endpoints is unaffected. [VERIFIED: web/routes/sse.py line 9 confirms no
`Depends(check_origin)` on the SSE endpoint, matching the security posture of `/api/status`]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|-----------------|--------------|--------|
| Two `setInterval` polls @ 2s | Single `EventSource` persistent stream | Phase 29 (this phase) | Sub-second delivery; halves poll requests; native reconnect |
| `pollStatus` contains render logic | `renderStatus(data)` pure fn shared by SSE + fallback | Phase 29 (this phase) | Single source of truth for status DOM updates |

## Open Questions

1. **Reconnecting indicator color: neutral or amber?**
   - What we know: CONTEXT says `--color-status-warn` for Reconnecting; but the existing
     `.status-dot.stopped` class uses `--color-status-neutral` (gray).
   - What's unclear: Should the planner add `.status-dot.reconnecting` rule to `components.css`
     (amber) or reuse `.stopped` (gray)?
   - Recommendation: Add `.status-dot.reconnecting { background: var(--color-status-warn); }`
     to `components.css` and use it for the Reconnecting state. This matches CONTEXT intent and
     the `test_no_hardcoded_hex_in_components` guard will validate it uses a token.

2. **Backfill one-shot: use existing `pollStatus()`/`pollLogs()` or direct `fetch`?**
   - What we know: `pollStatus()` already fetches `/api/status` and calls `renderStatus`.
     `pollLogs()` already fetches `/api/logs` and calls `renderLogLines`.
   - What's unclear: Is it cleaner to call them directly (one-shot, no interval) or inline
     equivalent fetch calls?
   - Recommendation: Call `pollStatus()` and `pollLogs()` directly as one-shots before the
     `if (typeof EventSource)` block. Reuses tested paths, zero new code.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Last-line compare is sufficient for no-dup guard (sequential cursor, no out-of-order SSE delivery) | Pattern 3 | If SSE delivery is out-of-order, some lines could duplicate; verify with Phase 27 `_poll_loop` cursor logic |
| A2 | `typeof EventSource` is the canonical feature-detect | Pattern 2 | Low risk; this is universally documented; EventSource is fully supported in all non-IE11 browsers |

## Sources

### Primary (HIGH confidence)

- `web/templates/dashboard.html` (read 2026-06-27) -- line-level structure of pollStatus/pollLogs/setInterval/all render functions
- `web/routes/sse.py` (read 2026-06-27) -- exact SSE frame format, retry:3000, named events
- `web/sse_hub.py` (read 2026-06-27) -- broadcast format `event: {name}\ndata: {json}\n\n`
- `web/static/components.css` (read 2026-06-27) -- existing `.status-dot`, `.badge`, token usage
- `web/static/tokens.css` (read 2026-06-27) -- `--color-status-ok`, `--color-status-warn` available
- `tests/test_web_dashboard.py` (read 2026-06-27) -- test patterns; `test_no_innerHTML_with_api_data` regex scope
- `tests/test_design_system.py` (read 2026-06-27) -- `test_no_hardcoded_hex_in_components` scope
- `.planning/phases/29-sse-client-wiring/29-CONTEXT.md` (read 2026-06-27) -- all locked decisions
- `.planning/research/SUMMARY.md` Phase E section (read 2026-06-27) -- EventSource reconnect guidance

### Secondary (MEDIUM confidence)

- HTML Living Standard §9.2.7 (EventSource `dispatchMessage` algorithm) -- named event routing to `addEventListener` not `onmessage`
- MDN EventSource API -- `e.data` field, `onopen`/`onerror` callbacks

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH -- all assets are existing code read directly
- Architecture: HIGH -- exact line numbers cited from current dashboard.html
- Pitfalls: HIGH -- derived from reading actual code and existing test guards
- Validation split: HIGH -- automatable assertions derived from existing test patterns

**Research date:** 2026-06-27
**Valid until:** Phase 29 plan execution (template is stable; no external dependencies)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- Use named-event listeners: `es.addEventListener('status', ...)` and `es.addEventListener('log', ...)`
- Refactor `pollStatus()` body into pure `renderStatus(data)` that updates start/stop buttons AND calls `renderHealthCards` + `renderUptime`
- Both SSE `status` handler and polling fallback call `renderStatus(data)` (single source of truth)
- When SSE is active: do NOT start `setInterval` polls
- Feature-detect: `if (typeof EventSource !== 'undefined')` wire SSE; ELSE keep existing `setInterval` fallback
- Rely on EventSource native auto-reconnect (server sends `retry: 3000`); do NOT add a manual reconnect/backoff loop
- `onerror` -> indicator "Reconnecting"; `onopen` -> "Live"
- Live/Reconnecting indicator: small element in sticky header near `#header-uptime`; `.status-dot` + `.badge` patterns; `--color-status-ok` for Live, `--color-status-warn` for Reconnecting; zero hardcoded hex
- On page load: one-shot `/api/logs` render + one-shot `/api/status` paint, then SSE drives updates
- SSE `log` events call `appendLogLine` for new lines only
- No-dup guard: track last rendered log line; `appendLogLine` skips a line identical to immediately-preceding one
- Frontend-only, no new packages, no Python changes

### Claude's Discretion

- Exact indicator HTML structure (single `<span>` vs nested dot+label elements)
- Whether `.status-dot.reconnecting` is added to `components.css` or `.stopped` class is reused
- Exact test file name for Phase 29 assertions (`test_sse_wiring.py` vs appending to `test_web_dashboard.py`)

### Deferred Ideas (OUT OF SCOPE)

- SSE for price charts
- FastAPI 0.135 native `EventSourceResponse`
- Multi-day log browsing, log-level count badges, order deep-links
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SSE-01 | Dashboard receives live status and log updates over a single SSE stream (`/api/events`), replacing the 2-second polling loop | Named-event listeners wire `status` -> `renderStatus`, `log` -> `appendLogLine`; feature-detect fallback satisfies "unavailable" case; server stream already live from Phase 27 |
</phase_requirements>
