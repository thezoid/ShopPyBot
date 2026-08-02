---
phase: 34-feature-completion
reviewed: 2026-07-02T00:00:00Z
depth: deep
files_reviewed: 13
files_reviewed_list:
  - logger.py
  - core/orchestrator.py
  - web/log_reader.py
  - web/routes/api.py
  - web/routes/pages.py
  - core/service.py
  - core/analytics.py
  - models.py
  - web/templates/dashboard.html
  - tests/test_analytics.py
  - tests/test_api_observability.py
  - tests/test_log_reader.py
  - tests/test_logger.py
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: resolved
resolved: 2026-07-02T00:00:00Z
---

# Phase 34: Code Review Report

**Reviewed:** 2026-07-02
**Depth:** deep (cross-file: logger.py -> orchestrator.py -> web/log_reader.py/api.py -> dashboard.html; core/analytics.py -> core/service.py -> web/routes/api.py -> dashboard.html)
**Files Reviewed:** 13 source files (backend + template), 4 test files cross-checked
**Status:** issues_found (no BLOCKER-tier defects; 3 WARNING-tier behavioral/coverage gaps)
**Resolved:** 2026-07-02 -- all 6 findings (WR-01, WR-02, WR-03, IN-01, IN-02, IN-03) fixed and committed; see per-finding "Resolution" notes below. Full suite: 932 passed, 2 skipped (baseline 923 passed + 9 new tests).

## Summary

Reviewed the Phase 34 diff (`61efdf2..HEAD`): the `[plugin]` log-tag ContextVar (logger.py/orchestrator.py), the `/api/logs` plugin filter (web/log_reader.py/api.py), the outcome-analytics pipeline (core/analytics.py, models.py, core/service.py, `/api/analytics`), and the dashboard markup/JS (plugin dropdown, analytics view, `lineMatchesFilters` SSE guard).

Core correctness claims hold up: the level bracket stays first in every `writeLog` code path (print and file), the `ContextVar` default correctly covers the web-tier/startup path, `compute_analytics` guards every division and is safe on an empty dataset, all current timestamp writers use `datetime.now(timezone.utc).isoformat()` consistently (no naive/aware subtraction risk), the `/api/analytics` response never carries `link`/credential data (verified against the exact code path, not just the mocked test), the plugin whitelist regex is anchored via `fullmatch` and cannot ReDoS or inject bracket characters, filter-then-limit is preserved in `read_logs_filtered`, and every new DOM write in dashboard.html uses `textContent`/`createElement` — no XSS sink was introduced.

The most significant finding (WR-01) is a genuine gap in the log-tag feature's stated goal: DB-write confirmation log lines (`Order confirmed`, `Marked purchased`, `Marked available`, `Cleared available`) are emitted from a separate, permanently `[core]`-tagged asyncio task and can never be found via the new plugin filter, even though they are arguably the highest-value lines an operator would want to filter per-plugin. Two further WARNING-tier gaps concern a dropdown/tag inconsistency for plugins without an explicit `platform_key`, and a real test-coverage hole in `BotService.get_analytics()`'s link->platform resolution glue (only the pure function and a fully-mocked route are tested).

## Warnings

### WR-01: DB-write confirmation log lines are always tagged `[core]`, never the originating plugin -- RESOLVED

**File:** `core/orchestrator.py:609-672` (writeLog calls at 621, 628, 632, 636, 640, 653, 670); root cause at `core/orchestrator.py:800`
**Issue:** `set_log_plugin()` is called once, as the first statement of `supervise()` (orchestrator.py:112), and is correctly isolated per plugin task since `asyncio.TaskGroup.create_task` copies the calling context. However, `_dispatch_write` (the function that logs "Marked purchased: ...", "Order confirmed: ... order_id=...", "Marked available: ...", "Cleared available: ...", and "DB write failed for ...") only ever runs inside the `_write_queue_drain` task:
```python
tg.create_task(_write_queue_drain(write_queue), name="write-queue-drain")
```
This task is created directly under `async_main`'s own context (which never calls `set_log_plugin`), so its `_current_plugin` ContextVar is permanently `"core"` for the lifetime of the process, regardless of which plugin's write is being drained. `_flush_write_queue` (the post-TaskGroup drain-remainder path) has the same problem.
Concretely: filtering the dashboard Log Viewer to `plugin=amazon` will show "AVAILABLE" and item-check lines (correctly plugin-tagged, since those run inside `supervise`'s own task via `run_plugin`/`_check_and_buy`), but will **never** show "Order confirmed: https://amazon.../... order_id=..." or "Marked purchased: ..." for that same purchase — those always appear only under the `[core]` filter (or no filter). This directly undermines the FC-01 feature for the log lines an operator is most likely to want to filter by plugin (buy confirmations).
**Fix:** Thread the resolved plugin tag through the write-queue item tuple (e.g. `("confirmed", link, order_id, ts, plugin_tag)`) and call `set_log_plugin(plugin_tag)` at the top of `_dispatch_write`, or emit the plugin-tagged `writeLog` call from inside the caller's own task (e.g. `_enqueue_buy_result`, which already runs inside `supervise`'s task) before/instead of doing it in `_dispatch_write`.

**Resolution:** Added `PluginRegistry.platform_of(link)` (core/registry.py), sharing the hostname-match logic with `core/service.py:get_analytics`. Threaded an optional `registry` parameter through `_write_queue_drain` -> `_flush_write_queue` -> `_dispatch_write` (core/orchestrator.py); `_dispatch_write` now calls `set_log_plugin(registry.platform_of(link))` before every write's `writeLog` call, falling back to `"core"` on a `None` registry or an unresolvable link (never raises). TDD RED->GREEN: `tests/test_orchestrator.py::test_dispatch_confirmed_tags_owning_plugin_not_core` (+2 fallback/threading tests). Commits: `f9b0250` (RED), `a762307` (GREEN).

### WR-02: Plugins without `platform_key` get a log tag they can never select in the dashboard dropdown -- RESOLVED

**File:** `core/orchestrator.py:112`, `core/service.py:139` and `184`, `web/templates/dashboard.html:200-208`
**Issue:** `supervise()` and `BotService.get_analytics()`'s `domain_map` both fall back to `plugin.__class__.__name__.lower()` when `platform_key` is unset (`getattr(plugin, "platform_key", None) or plugin.__class__.__name__.lower()` / `type(plugin).__name__.lower()`), so a plugin without `platform_key` (e.g. any third-party plugin written from the `plugins/example_plugin.py` template, which defines no `platform_key` at all) still gets a real, non-`core` log tag and a real analytics bucket. However `BotService.list_plugins()` returns the raw, un-fallback'd value (`"platform_key": getattr(plugin, "platform_key", None)` -> `None`), and the dashboard template explicitly skips falsy values:
```jinja
{% for p in plugins %}
  {% if p.platform_key %}
  <option value="{{ p.platform_key }}">{{ p.platform_key }}</option>
  {% endif %}
{% endfor %}
```
Result: that plugin's log lines and analytics bucket exist and are correctly, consistently tagged, but there is no dropdown option to select them — the operator would have to already know the exact lowercased class name and hand-edit the `?plugin=` query string.
**Fix:** Either (a) make `list_plugins()` apply the same fallback (`getattr(plugin, "platform_key", None) or type(plugin).__name__.lower()`) so the dropdown always offers every tag that can actually appear in a log line, or (b) require `platform_key` on all plugins (including updating `example_plugin.py`/`PLUGIN_DEV.md`) and drop the class-name fallback everywhere so untagged plugins are a visible `[core]`-only gap instead of a silent, unreachable tag.

**Resolution:** Took option (a). Extracted the fallback into `core/registry._plugin_tag(plugin)` (shared with the WR-01 fix and `supervise()`); `list_plugins()` now returns `_plugin_tag(plugin)` instead of the raw `getattr(plugin, "platform_key", None)`, so the dropdown option always matches the actual log/analytics tag. Tests: `tests/test_service.py::test_list_plugins_platform_key_fallback_matches_logger_tag` + regression guard for the explicit-`platform_key` case. Commit: `700b99e`.

### WR-03: `BotService.get_analytics()`'s link->platform_key glue has zero direct test coverage -- RESOLVED

**File:** `core/service.py:120-159`, `models.py:119-133`
**Issue:** `tests/test_analytics.py` exercises `core.analytics.compute_analytics` directly with a hand-rolled `platform_of` lambda (no DB, no registry). `tests/test_api_observability.py::test_get_analytics_aggregate_only_no_link_leak` and `test_get_analytics_empty_dataset` exercise the `/api/analytics` route with `mock_svc.get_analytics` fully replaced by a `MagicMock`. No test exists that calls the real `BotService.get_analytics()` and asserts on its output — the code that (a) builds `domain_map` from `registry._all_plugins`, (b) zips `get_order_analytics_rows_sync()`'s tuple rows into dicts via the hardcoded `columns` tuple, and (c) resolves hostnames via `urlparse` is entirely unverified by the test suite. A future edit that reorders either the `SELECT` in `models.get_order_analytics_rows_sync()` or the `columns` tuple in `core/service.py` (they must stay in lockstep) would silently swap fields (e.g. `confirmed_at` read as `checkout_attempts`) and produce wrong `success_rate`/`avg_time_to_checkout_secs` values with no test failure. (Manually verified correct as of this review: `SELECT name, link, order_id, confirmed_at, checkout_attempts, place_order_attempted_at, purchased` matches `columns = ("name", "link", "order_id", "confirmed_at", "checkout_attempts", "place_order_attempted_at", "purchased")` exactly.)
**Fix:** Add an integration test that seeds a real (or fixture) `items` table via `models.get_order_analytics_rows_sync()`/`get_db_connection`, calls the real `BotService.get_analytics()`, and asserts on the resulting `success_rate`/`avg_time_to_checkout_secs` — catching column-order drift and platform-resolution regressions that the current pure-function + fully-mocked-route tests cannot see.

**Resolution:** Added `tests/test_service.py::test_get_analytics_end_to_end_real_db_and_registry` -- seeds a real temp DB via the `models` sync writers (`add_items_sync`, `mark_place_order_attempted_sync`, `update_item_confirmed_sync`) with an Amazon row and a BestBuy row, calls the real `BotService.get_analytics()` (real `PluginRegistry` against the real `plugins/` dir, real SQL), and asserts overall + per-plugin `attempted`/`confirmed`/`success_rate`/`avg_time_to_checkout_secs` plus no-link-leak end-to-end. Plus `test_get_analytics_empty_db_returns_safe_defaults` for the empty-DB path. `get_analytics()` was also refactored to call the new `registry.platform_of()` (WR-01) instead of a duplicated inline closure. Commit: `700b99e`.

## Info

### IN-01: `CONFIRMED-` sentinel prefix duplicated as an independent string literal -- RESOLVED

**File:** `core/analytics.py:19`, `core/confirmation.py:32`
**Issue:** `core/analytics.py` defines `_SENTINEL_PREFIX = "CONFIRMED-"` as its own module-level constant rather than importing `core.confirmation._CONFIRMED_SENTINEL_PREFIX` (also `"CONFIRMED-"`). The two currently agree, but nothing enforces that they stay in sync — a future rename of the sentinel prefix in `core/confirmation.py` (the actual writer) would silently break `_is_confirmed()`'s exclusion logic in `core/analytics.py` (the reader), inflating the reported success rate by counting unverified sentinel orders as confirmed.
**Fix:** Import the constant from `core/confirmation.py` (or hoist it to a shared module) instead of redefining it.

**Resolution:** `core/analytics.py` now does `from core.confirmation import _CONFIRMED_SENTINEL_PREFIX as _SENTINEL_PREFIX` instead of redefining the literal; `core/confirmation.py` has no DB/fastapi imports either, so this preserves `core/analytics.py`'s purity claim. Test: `tests/test_analytics.py::test_sentinel_prefix_imported_from_confirmation_not_redefined` asserts identity (`is`), not just equality. Commit: `e93c4fd`.

### IN-02: `pollAnalytics()` fetches once on load and is never re-polled -- RESOLVED

**File:** `web/templates/dashboard.html:511-528`, `739`
**Issue:** `pollStatus()` and `pollLogs()` are both driven continuously (via SSE `status`/`log` events, or the `setInterval` polling fallback when `EventSource` is unavailable). `pollAnalytics()` is called exactly once, in the one-shot backfill block (`pollAnalytics();` at line 739), and is never referenced again — not from the SSE handlers, not from the watchdog fallback `setInterval`, not from any other `setInterval`. The Analytics section will silently go stale for the entire browser session (a purchase could complete and the success-rate/time-to-checkout cards would not update) unless the operator manually reloads the page.
**Fix:** Either wire `pollAnalytics()` into the existing `POLL_MS` fallback timer / a periodic SSE-triggered refresh, or (if intentionally on-load-only) rename to `loadAnalytics()` to match the `loadItems`/`loadCredentials`/`loadConfig`/`loadConfirmedBuys` one-shot naming convention already used elsewhere in the same file, so the name doesn't imply live refresh it doesn't have.

**Resolution:** Took the first option, with an independent cadence rather than reusing `POLL_MS`: added `ANALYTICS_POLL_MS` (30s -- analytics changes slowly) and `setInterval(pollAnalytics, ANALYTICS_POLL_MS)` alongside the existing one-shot backfill call, unconditional of the SSE/no-SSE branch (analytics has no SSE event type). Zero-Node, no new deps. Commit: `ddcd002`.

### IN-03: Plugin log filter matches `[plugin]` as a free-floating substring, not a positional tag -- RESOLVED

**File:** `web/log_reader.py:52-54`, `web/templates/dashboard.html:621`
**Issue:** Both the server (`tag = f"[{plugin}]"; tag in line`) and the client (`line.indexOf('[' + plugin + ']') === -1`) match the plugin tag anywhere in the line, not specifically at the documented "second bracket" position. A log line whose free-text message body happens to contain a literal `[amazon]`-shaped substring (e.g. an error message that echoes another plugin's tag, or a message mentioning a plugin name in brackets) would incorrectly match the `amazon` filter even when `[core]` or a different plugin is the actual tag. Low likelihood given current message contents, but worth a positional check (`line.split(']')[1] == '[' + plugin` or a small regex anchored to the known `[LEVEL][plugin][ts]` prefix) if message bodies ever start embedding bracketed text.
**Fix:** Not urgent; consider anchoring the match to the actual second-bracket position if this becomes a real false-positive source.

**Resolution:** Anchored anyway (low-risk, high-value fix). Added `_plugin_tag_matches(line, plugin)` in `web/log_reader.py` (checks `line.startswith(f"[{plugin}]", first_close + 1)` where `first_close` is the index of the first `]`) and mirrored the identical positional check in `dashboard.html`'s `lineMatchesFilters`. Test: `tests/test_log_reader.py::test_read_logs_filtered_plugin_does_not_match_substring_in_message` -- a `[bestbuy]`-tagged line whose message body contains a literal `[amazon]` substring no longer matches `plugin=amazon`. Commit: `ac104f0`.

---

_Reviewed: 2026-07-02_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
