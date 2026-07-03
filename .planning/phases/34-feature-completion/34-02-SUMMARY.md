---
phase: 34-feature-completion
plan: 02
subsystem: observability
tags: [fastapi, jinja2, sse, log-filtering, plugin-registry]

# Dependency graph
requires:
  - phase: 34-feature-completion (34-01)
    provides: "Module-level ContextVar in logger.py guaranteeing every newly-written log line carries a [plugin] tag as the second bracket"
provides:
  - "read_logs_filtered(n, level, search, plugin) -- plugin filter AND-composed with level+search, filter-then-limit preserved"
  - "/api/logs plugin query param, whitelisted against a lowercase-alphanumeric regex before use"
  - "core/service.py list_plugins() platform_key field"
  - "#log-plugin-filter dashboard dropdown wired to the plugin query param, reusing existing select styling"
  - "SSE 'log' listener gated through a lineMatchesFilters() guard so live-tailed lines respect the active level/search/plugin filters (previously only the one-shot pollLogs snapshot was filtered)"
affects: ["35-audit-fixes-doc-hygiene (no direct dependency, but shares dashboard.html/api.py surface)"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Defense-in-depth query-param whitelist via re.fullmatch against a lowercase-alphanumeric regex, in preference to a per-request enum check that would require an async-to_thread-wrapped filesystem+importlib PluginRegistry scan on a hot-polled endpoint"
    - "Client-side pure guard function (lineMatchesFilters) mirroring the server's read_logs_filtered AND-composed level/plugin/search match, reused by both the SSE incremental path and (implicitly) the pollLogs snapshot semantics"

key-files:
  created: []
  modified:
    - web/log_reader.py
    - web/routes/api.py
    - web/routes/pages.py
    - core/service.py
    - web/templates/dashboard.html
    - tests/test_log_reader.py
    - tests/test_api_observability.py
    - tests/test_web_dashboard.py
    - tests/test_sse_wiring.py

key-decisions:
  - "Kept the generic re.fullmatch(r'[a-z0-9]+', ...) whitelist in web/routes/api.py rather than an enum check against list_plugins()'s live platform_key set -- an enum check would require a to_thread-wrapped filesystem+importlib PluginRegistry scan on every /api/logs request (a hot, frequently-polled endpoint), which the plan's own threat-model escape hatch permits avoiding when it 'materially complicates the route'"
  - "list_plugins() is offloaded via asyncio.to_thread in the dashboard page route (web/routes/pages.py) -- it constructs a PluginRegistry (filesystem scan + importlib per plugin file) and would otherwise block the event loop, matching the existing /logs|/history|/analytics to_thread convention"
  - "Live SSE log lines are filtered client-side via a small pure lineMatchesFilters(line, level, search, plugin) guard rather than server-side -- keeps the SSE producer (uvicorn _poll_loop) unaware of per-client filter state, consistent with the existing single-producer SSE architecture from Phase 27"

patterns-established:
  - "Client-side filter-parity guard: any future streamed-data feature with a corresponding filtered snapshot endpoint should mirror the snapshot's match logic client-side (lineMatchesFilters) rather than only filtering the initial backfill"

requirements-completed: [FC-01]

# Metrics
duration: 4min
completed: 2026-07-02
---

# Phase 34 Plan 02: /api/logs Plugin Filter + Dashboard Dropdown Summary

**`/api/logs` gained a whitelisted `plugin` query param that AND-composes with level+search on the `[plugin]` tag from 34-01, backing a new `#log-plugin-filter` dashboard dropdown that also gates live SSE-streamed log lines through the same match logic, completing the deferred half of OBS-08 (FC-01).**

## Performance

- **Duration:** ~4 min (3 commits, 21:06-21:10 local)
- **Started:** 2026-07-02T21:06:22-04:00
- **Completed:** 2026-07-02T21:09:51-04:00
- **Tasks:** 2 completed
- **Files modified:** 9 (2 source in Task 1, 3 source + 4 test files across both tasks)

## Accomplishments
- `web/log_reader.py:read_logs_filtered` gained a `plugin: str | None = None` trailing param; when set, keeps only lines containing `f"[{plugin}]"`, AND-composed with the existing level/search filters, filter-then-limit order preserved.
- `web/routes/api.py:/logs` accepts `plugin`, validates it against `re.fullmatch(r"[a-z0-9]+", ...)` (V5 defense-in-depth whitelist), drops invalid values to `None`, and passes it as the 4th positional to `asyncio.to_thread(read_logs_filtered, ...)`.
- `core/service.py:list_plugins()` now returns a `platform_key` key per plugin (never the class name -- `squareenix` stays underscore-free).
- `web/routes/pages.py`'s dashboard route now passes `plugins` into the template context, offloaded via `asyncio.to_thread(svc.list_plugins)` (refinement 1 -- avoids blocking the event loop on the filesystem+importlib PluginRegistry scan).
- `web/templates/dashboard.html` gained a `#log-plugin-filter` `<select>` in `.log-controls`, Jinja2-populated from `platform_key` values (skipping falsy ones), wired via `pollLogs()`'s `URLSearchParams` and a `change` listener mirroring the existing level dropdown. Zero new CSS -- reuses the existing `select` rule in `components.css`.
- Refinement 2 (FC-01 live-tail completion): added a pure `lineMatchesFilters(line, level, search, plugin)` JS guard mirroring `read_logs_filtered`'s AND-composed match logic; the SSE `'log'` event listener now calls it before `appendLogLine`, so streamed lines respect the active level/search/plugin filters instead of appending unconditionally (the pre-existing gap affected level+search too, not just the new plugin filter).

## Task Commits

Task 1 is TDD (test -> feat); Task 2 is a single auto commit:

1. **Task 1 RED: failing tests for the 4-arg read_logs_filtered contract + updated arity asserts** - `6c93c87` (test)
2. **Task 1 GREEN: plugin param on read_logs_filtered + validated /api/logs param** - `039f242` (feat)
3. **Task 2: platform_key + #log-plugin-filter dropdown + live-tail filter guard (refinements 1 & 2)** - `8543b57` (feat)

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified
- `web/log_reader.py` - `read_logs_filtered` gained the `plugin` param and its AND-composed filter block
- `web/routes/api.py` - `/logs` route gained `plugin` param + whitelist regex + updated `to_thread` call arity
- `web/routes/pages.py` - dashboard route passes `plugins` (via `asyncio.to_thread(svc.list_plugins)`) into the template context
- `core/service.py` - `list_plugins()` dicts gained a `platform_key` key
- `web/templates/dashboard.html` - `#log-plugin-filter` select, `pollLogs()` plugin param wiring, `lineMatchesFilters()` guard on the SSE `'log'` listener
- `tests/test_log_reader.py` - 3 new plugin-filter unit tests (plugin-only, compose-with-level+search, plugin=None passthrough)
- `tests/test_api_observability.py` - 2 arity asserts updated to the 4-arg form; 2 new tests (plugin-filter integration, invalid-plugin-param whitelist drop)
- `tests/test_web_dashboard.py` - 4 new tests (dropdown population from platform_key, falsy-platform_key skip, pollLogs plugin param wiring, change-listener wiring)
- `tests/test_sse_wiring.py` - 2 new tests (lineMatchesFilters presence, SSE log listener gates appendLogLine through it)

## Decisions Made
- Kept the generic lowercase-alphanumeric regex whitelist for the `plugin` query param rather than an enum check against the live `platform_key` set, per the plan's own threat-model escape hatch: an enum check would require a `to_thread`-wrapped `PluginRegistry` filesystem+importlib scan on every `/api/logs` request, a hot endpoint polled continuously by the dashboard and on every debounced search keystroke.
- `list_plugins()` offloaded via `asyncio.to_thread` in the page route (Refinement 1), consistent with the codebase's established `/logs`/`/history`/`/analytics` convention for any sync call that touches the filesystem or does non-trivial work off the request path.
- Live SSE log filtering implemented client-side (Refinement 2) via a small pure function rather than server-side per-client filtering, keeping the existing single-producer SSE architecture (`_poll_loop`) unchanged -- no new per-connection state on the server.

## Deviations from Plan

None beyond the 3 plan-checker refinements explicitly directed by the orchestrator and folded into the tasks above (to_thread wrap, live-tail filter completion, param whitelist evaluation). No Rule 1-4 auto-fixes were needed; the plan's `<action>` and `<acceptance_criteria>` blocks were implemented as written for both tasks.

### Refinements Applied

**1. [to_thread wrap]** Applied as specified: `web/routes/pages.py`'s dashboard route wraps `svc.list_plugins()` in `asyncio.to_thread(...)`.

**2. [complete FC-01 in live-tail]** Applied: added `lineMatchesFilters()` and gated the SSE `'log'` listener's `appendLogLine` call behind it. Verified via 2 new static-analysis tests in `tests/test_sse_wiring.py` (no JS test harness exists in this Zero-Node codebase, matching the existing `test_no_onmessage_for_named_events`-style pattern of asserting on rendered HTML/JS text).

**3. [param whitelist]** Evaluated: kept the generic `re.fullmatch(r"[a-z0-9]+", ...)` regex rather than an enum check, because the enum check would require a synchronous, filesystem+importlib-scanning `list_plugins()` call (wrapped in `asyncio.to_thread`) on every `/api/logs` request -- a hot, continuously-polled endpoint. The plan explicitly permits this: "If this materially complicates the route, the generic regex is acceptable per the threat model." Documented as a key decision above.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. Pure code change (stdlib `re`, existing `asyncio`/`fastapi`/`jinja2`, no new dependencies).

## Manual Verification

Read-verified the rendered `dashboard.html` output confirms:
- `#log-plugin-filter` renders inside `.log-controls` with `<option value="">All plugins</option>` as the default, followed by one `<option>` per `platform_key`.
- `pollLogs()` sets the `plugin` URLSearchParams entry only when the dropdown has a truthy value.
- The SSE `'log'` listener evaluates `lineMatchesFilters(p.line, level, search, plugin)` before calling `appendLogLine(p.line)`.

No `.venv` browser/live-socket verification performed (out of scope per the milestone's "pending live-environment testing = done" policy; SSE/EventSource live behavior remains tracked operator debt from Phase 27-29).

## Next Phase Readiness
- FC-01 is now genuinely complete: the `[plugin]` tag guarantee (34-01) plus the filter + dropdown + live-tail completion (34-02) together close the deferred half of OBS-08.
- Phase 34 (Feature Completion) is now fully complete: 34-01 (FC-01 tag), 34-02 (FC-01 filter/UI, this plan), 34-03 (FC-02 analytics) all landed.
- Full suite green: 923 passed, 2 skipped (baseline 912 + 11 net-new tests: 5 from Task 1, 6 from Task 2), no regressions.
- No blockers for Phase 35 (Audit-Fixes & Doc-Hygiene Cleanup), the milestone's closing phase.

---
*Phase: 34-feature-completion*
*Completed: 2026-07-02*

## Self-Check: PASSED

- FOUND: web/log_reader.py
- FOUND: web/routes/api.py
- FOUND: web/routes/pages.py
- FOUND: core/service.py
- FOUND: web/templates/dashboard.html
- FOUND: tests/test_log_reader.py
- FOUND: tests/test_api_observability.py
- FOUND: tests/test_web_dashboard.py
- FOUND: tests/test_sse_wiring.py
- FOUND commit: 6c93c87
- FOUND commit: 039f242
- FOUND commit: 8543b57
