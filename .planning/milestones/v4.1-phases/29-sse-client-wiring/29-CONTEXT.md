# Phase 29: SSE Client Wiring - Context

**Gathered:** 2026-06-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the dashboard's 2-second polling loop with a single persistent
`EventSource('/api/events')` connection: health cards + log panel update live from
SSE `status`/`log` events, a polling fallback activates where `EventSource` is
unavailable, and a "Live / Reconnecting" indicator shows connection state. Frontend
(dashboard.html JS) only — the SSE endpoint (Phase 27) and the render functions
(Phase 28) already exist. Covers SSE-01.

**UI note:** the only new UI is the small Live/Reconnecting indicator (a token-colored
dot + label in the sticky header). It extends the already-approved Phase 25/28 design
system, so no separate UI-SPEC is generated for this phase (documented deviation; the
design-system + safe-DOM contracts from Phase 25/28 govern it).

</domain>

<decisions>
## Implementation Decisions

### EventSource Dispatch & Polling Replacement
- Use named-event listeners: `es.addEventListener('status', …)` and
  `es.addEventListener('log', …)` (Phase 27 broadcasts `event: status` / `event: log`).
- Refactor the existing `pollStatus()` body into a pure `renderStatus(data)` that updates
  the start/stop buttons + status dot/label AND calls `renderHealthCards(data)` +
  `renderUptime(data.uptime_secs)`. Both the SSE `status` handler and the polling fallback
  call `renderStatus(data)` (single source of truth).
- When SSE is active, do NOT start the `setInterval` polls — the persistent stream is the
  sole live-update source (criterion 1: no polling requests when SSE connected).
- Payloads: `status` event data = the `/api/status` JSON shape; `log` event data =
  `{line: "..."}` → `appendLogLine(line)`.

### Reconnect, Fallback, Live Indicator
- Feature-detect: `if (typeof EventSource !== 'undefined')` wire SSE; ELSE keep the
  existing `setInterval` `pollStatus`/`pollLogs` fallback. Neither path throws (criterion 5).
- Rely on EventSource's native auto-reconnect (server sends `retry: 3000`); do NOT add a
  manual reconnect/backoff loop. `onerror` → indicator "Reconnecting"; `onopen` → "Live".
- "Live / Reconnecting" indicator: a small element in the sticky header (near
  `#header-uptime`) — a status dot + label, colored with existing tokens
  (`--color-status-ok` for Live, `--color-status-warn` for Reconnecting). Built via
  createElement/textContent / existing `.status-dot` + `.badge` patterns; zero hardcoded hex.

### Log Backfill & No-Duplicates (criterion 3)
- On page load: one-shot `/api/logs` render (`renderLogLines`) for history + one-shot
  `/api/status` paint (`renderStatus`) for immediate state — then SSE drives updates.
- SSE `log` events call `appendLogLine` for new lines only (Phase 27's `tail_log_lines`
  cursor sends incremental lines, not full re-tails).
- No-dup guard: track the last rendered log line; `appendLogLine` skips appending a line
  identical to the immediately-preceding one (handles the backfill/stream boundary so each
  line appears once — criterion 3).

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `web/templates/dashboard.html` — `pollStatus()`/`pollLogs()` (~2s `setInterval`),
  `renderHealthCards`/`renderUptime`/`renderLogLines`/`appendLogLine`/`logLevelClass`
  (Phase 28, pure render fns ready for SSE), `maybeScrollToBottom`, `#header-uptime` slot,
  the start/stop button enable/disable logic inside `pollStatus`.
- `GET /api/events` (Phase 27) emits `event: status` (every ~1s) + `event: log` ({line})
  + `: keep-alive` + `retry: 3000`.
- `web/static/components.css` — `.status-dot`/`.badge` + status tokens for the indicator.

### Established Patterns
- Safe DOM (createElement/textContent), zero hardcoded hex, token-driven (Phase 25/28 guards).
- Phase 28 render functions are deliberately separate from their fetch/poll triggers, so
  Phase 29 swaps the trigger (poll → SSE) without touching render logic.

### Integration Points
- `web/templates/dashboard.html` — add the EventSource wiring + `renderStatus` refactor +
  feature-detect fallback + the Live/Reconnecting indicator element + no-dup guard.
- `web/static/components.css` — small indicator styling if not covered by existing classes.

### Guards To Respect
- `test_no_innerHTML_with_api_data` (safe DOM), `test_no_hardcoded_hex_in_components`,
  MC-4 banner, the SSE tests (Phase 27) and observability_ui tests (Phase 28) must stay green.

</code_context>

<specifics>
## Specific Ideas

- Research SUMMARY Phase E: EventSource auto-reconnects — do NOT add a manual reconnect on
  top; replace the 2s poll LAST so rollback is trivial (revert EventSource code, polling resumes).
- Verification is largely manual UAT (DevTools shows one text/event-stream replacing two
  polls; live updates within 1-2s; clean reconnect on tab close/reopen). Automatable surface:
  the EventSource wiring + feature-detect + indicator + no-dup guard exist in the template;
  safe-DOM/hex guards stay green; a unit test can assert the fallback branch + that
  renderStatus is shared.

</specifics>

<deferred>
## Deferred Ideas

- SSE for price charts — out of scope (price scrapes sparse; on-demand REST suffices).
- FastAPI 0.135 native EventSourceResponse — future dep-refresh milestone.
- Multi-day log browsing, log-level count badges, order deep-links — future (OBSX).

</deferred>
