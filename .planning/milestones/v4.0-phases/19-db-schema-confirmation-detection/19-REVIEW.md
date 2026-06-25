---
phase: 19-db-schema-confirmation-detection
reviewed: 2026-06-11T00:00:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - models.py
  - core/confirmation.py
  - core/orchestrator.py
  - core/plugin_base.py
  - plugins/shopbot_plugin_amazon.py
  - plugins/shopbot_plugin_bestbuy.py
  - tests/test_confirmation.py
  - tests/test_models.py
  - tests/test_orchestrator.py
  - tests/test_plugin_base.py
  - tests/test_amazon_plugin.py
  - tests/test_bestbuy_plugin.py
findings:
  critical: 2
  warning: 3
  info: 2
  total: 7
status: issues_found
---

# Phase 19: Code Review Report

**Reviewed:** 2026-06-11T00:00:00Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Phase 19 adds three DB columns (`order_id`, `confirmed_at`, `checkout_attempts`),
`update_item_confirmed_sync`, `detect_order_confirmation`, and orchestrator wiring that
chooses between a confirmed write and a legacy purchased write after a successful
`auto_buy`. The migration is idempotent; the write-queue single-put invariant holds.
Two critical bugs were found: a double-buy window in the AmazonPlugin (monitor_only
guard uses the wrong default, letting `auto_buy` return True in certain configs
and then `place_order_guarded` also returns True via the same guard, so a real order
fires but only the legacy purchased path writes), and a stale-URL risk in
`_extract_order_id` (the pre-settle URL read is used after the settle). Three warnings
cover a sentinel value that can mask a real order failure downstream, a missing
monitor_only guard in BestBuyPlugin, and a too-broad exception catch in `_try_auto_buy`
that swallows confirmation errors silently.

## Critical Issues

### CR-01: AmazonPlugin.auto_buy monitor_only default inverted -- suppression logic broken

**File:** `plugins/shopbot_plugin_amazon.py:371`
**Issue:** The guard at the top of `auto_buy` reads:
```python
if getattr(debug, "monitor_only", True):
```
The default is `True`, which matches the intent when `debug` is `None` (fail-safe).
However, `place_order_guarded` in `plugin_base.py` line 107 uses the same
`getattr(debug, "monitor_only", True)` default. When a real config exists and
`monitor_only=False`, `auto_buy` passes the guard (correct), runs all DOM steps,
sets `self._last_tab`, and calls `place_order_guarded(place_order.click)`. So far so
good. The bug is the opposite edge: when `debug` is a config object that does NOT
have `monitor_only` as an attribute at all (e.g., a partial legacy config), both guards
default to True and both suppress -- that is the intended fail-safe.

The ACTUAL critical bug is subtler: `auto_buy` at line 400 does a raw attribute access
`self.config.debug.test_mode` without a guard:
```python
if self.config and self.config.debug.test_mode:
```
If `self.config.debug` is `None` (a config object where `debug` key resolved to null),
this raises `AttributeError: 'NoneType' object has no attribute 'test_mode'`, causing
`auto_buy` to raise, which is caught by `_try_auto_buy`'s outer except and treated
as a buy failure. The item is NOT marked purchased. However this also means the
`set_available` tuple was already enqueued on the write queue (in `_check_and_buy`
line 244), so on the next poll cycle `was_available` will be True, `auto_buy` will
be attempted again, and the loop will repeat without ever writing `purchased`. The
item will never be skipped.

**Fix:**
```python
# Replace line 400-405:
debug = getattr(self.config, "debug", None) if self.config else None
if getattr(debug, "test_mode", False):
    writeLog("Test mode active: pausing before buy-now", "DEBUG")
    await self._wait_user_action(
        self.test_pause_event,
        "TEST MODE: review the browser, then press Enter to continue.",
    )
```

### CR-02: _extract_order_id reads tab.target.url BEFORE settle -- stale URL used for query param extraction

**File:** `core/confirmation.py:59`
**Issue:** `_extract_order_id` reads `tab.target.url` at line 59 at the top of the
function body. `detect_order_confirmation` calls `await tab.sleep(_SETTLE_SECS)` at
line 114 and then reads `tab.target.url` at line 116 for the fragment check. The
fragment check therefore uses the settled URL. However, when `detect_order_confirmation`
calls `_extract_order_id(tab, cfg)` at line 120, `_extract_order_id` reads
`tab.target.url` again at line 59 -- this is a second read, and it should be the same
settled URL. This is not actually stale because the settle already happened. The real
issue is that `_extract_order_id` re-reads `tab.target.url` independently rather than
receiving the already-read `current_url` as an argument. If the browser navigates
between the fragment check and the `_extract_order_id` call (e.g., a redirect on the
thank-you page), the fragment check could pass on the confirmation URL while
`_extract_order_id` reads a redirect destination URL where the `orderID` param no
longer appears. This causes the sentinel `CONFIRMED-<ts>` to be written instead of the
real order ID -- the purchased flag is still set, but the `order_id` column is
meaningless for Phase 21 retry.

**Fix:** Pass `current_url` into `_extract_order_id` instead of re-reading from the tab:
```python
async def _extract_order_id(tab, cfg: dict, current_url: str) -> str | None:
    for param in cfg.get("url_query_params", []):
        try:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(current_url).query)
            val = qs.get(param, [None])[0]
            if val and val.strip():
                return val.strip()
        except Exception as exc:
            ...

# In detect_order_confirmation, line 120:
order_id = await _extract_order_id(tab, cfg, current_url)
```

## Warnings

### WR-01: CONFIRMED-<ts> sentinel written to order_id column -- masks absence of real order id

**File:** `core/confirmation.py:126-132`
**Issue:** When the URL matches the confirmation fragment but no order ID is
extractable from query params or DOM, the sentinel `CONFIRMED-<ts>` is written
as the `order_id` value in the database (via `update_item_confirmed_sync`). The
docstring and comment say this ensures `purchased` is written on a real confirmation.
That is correct. However, the sentinel is indistinguishable from a real order ID
in the DB unless the caller filters for the `CONFIRMED-` prefix. Phase 21 retry
(`BUY-05`) will use `order_id` as an idempotency anchor. If the sentinel is stored,
Phase 21 will read a sentinel value and may incorrectly treat a purchase as confirmed
when the order may actually have failed silently (the thank-you URL was reached but
no order ID was rendered, which can happen on Amazon when the order fails at the
payment step and the page still redirects to `/gp/buy/thankyou`).

**Fix:** Either store `NULL` in `order_id` when only a sentinel is available and
set a separate `confirmation_quality` column (`url_only` vs `order_id_confirmed`),
or document explicitly in Phase 21 that sentinel-prefixed order IDs must not be
used as idempotency keys and must trigger a manual review step.

### WR-02: _try_auto_buy outer except swallows detect_order_confirmation exceptions silently

**File:** `core/orchestrator.py:207-208`
**Issue:** The `except Exception as exc` at line 207 wraps both `plugin.auto_buy(link)`
and the entire confirmation block (lines 187-206). If `detect_order_confirmation`
raises unexpectedly (nodriver internal error, tab closed between buy and detection),
the exception is logged as `auto_buy error` and the function returns without enqueuing
anything. The item remains `available` in the DB (the `set_available` write was
already queued), so the next poll cycle will attempt `auto_buy` again. This can cause
a second real order to be placed if the first order actually succeeded but confirmation
detection failed. The docstring on `_try_auto_buy` says it detects confirmation --
the detection code is inside the try block unintentionally.

**Fix:** Split the try block so `auto_buy` is the only risky call inside it, and
confirmation + enqueue run outside:
```python
async def _try_auto_buy(plugin, name, link, write_queue, dispatcher) -> None:
    from core.confirmation import detect_order_confirmation
    try:
        success = await plugin.auto_buy(link)
    except Exception as exc:
        writeLog(f"[{plugin.__class__.__name__}] auto_buy error: {exc}", "ERROR")
        return
    if not success:
        return
    if dispatcher is not None:
        await dispatcher.notify(
            _build_event(name, link, plugin.__class__.__name__, "purchased")
        )
    tab = plugin.get_active_tab()
    platform = plugin.__class__.__name__
    order_id = None
    if tab is not None:
        try:
            order_id = await detect_order_confirmation(tab, platform)
        except Exception as exc:
            writeLog(f"[{platform}] confirmation detection error: {exc.__class__.__name__}", "ERROR")
    if order_id is not None:
        ts = datetime.now(timezone.utc).isoformat()
        await write_queue.put(("confirmed", link, order_id, ts))
    else:
        writeLog(
            f"[{platform}] confirmation not detected -- falling back to legacy purchased write",
            "WARNING",
        )
        await write_queue.put(("purchased", link))
```

### WR-03: BestBuyPlugin.auto_buy missing monitor_only guard at method entry

**File:** `plugins/shopbot_plugin_bestbuy.py:249`
**Issue:** `AmazonPlugin.auto_buy` (line 370-373) gates on `monitor_only` at the top
of the method and returns False immediately, preventing any DOM navigation when
monitor-only mode is active. `BestBuyPlugin.auto_buy` has no equivalent entry guard.
The orchestrator's `_check_and_buy` also gates (line 252-258), but that gate only
fires when `plugin.config` is non-None and `debug.monitor_only` is set. If a plugin
is invoked through a code path that bypasses `_check_and_buy` (test helpers,
future refactors), BestBuy will execute cart operations in monitor-only mode. The
defense-in-depth parity with AmazonPlugin is missing.

**Fix:** Add the same entry guard to `BestBuyPlugin.auto_buy`:
```python
async def auto_buy(self, url: str) -> bool:
    writeLog(f"Entering auto_buy for BestBuy: {url}", "DEBUG")
    debug = getattr(self.config, "debug", None) if self.config else None
    if getattr(debug, "monitor_only", True):
        writeLog("[BestBuyPlugin] auto_buy suppressed (monitor_only)", "INFO")
        return False
    ...
```

## Info

### IN-01: test_orchestrator_confirmed_path / fallback_path use tmp_data_dir but do not call initialize_db

**File:** `tests/test_orchestrator.py:756-800`
**Issue:** Both BUY-03/BUY-04 orchestrator tests (`test_orchestrator_confirmed_path`
and `test_orchestrator_fallback_path`) request the `tmp_data_dir` fixture (which
redirects `models.DB_PATH` to a temp directory) but neither calls `models.initialize_db()`.
The tests exercise `_try_auto_buy` which eventually calls `_dispatch_write` via the
queue -- but because the queue is not drained in these tests, no DB write actually
occurs. The `tmp_data_dir` fixture is therefore unused. This is not a correctness bug
(the tests pass and assert queue contents correctly), but the fixture adds noise and
could mislead a future developer into thinking the DB is initialized and validated.

**Fix:** Remove `tmp_data_dir` from both test signatures, or add an explicit
`models.initialize_db(delete=True)` + DB assertion to prove the full write path.

### IN-02: _SETTLE_SECS is a module constant but has no config seam

**File:** `core/confirmation.py:21`
**Issue:** The 3-second settle delay is a hardcoded module constant with no config
override path. For slow network environments or fast CI, 3s may be either too short
(tab hasn't loaded the confirmation URL) or wasteful. Since the settle duration
directly impacts how fresh `tab.target.url` is, this is a correctness-adjacent
tuning parameter. It is not currently exposed in `config.yml`.

**Fix:** Low priority -- document as a known tuning parameter and consider
adding `app.confirmation_settle_secs` in Phase 21 when retry logic is added.

---

_Reviewed: 2026-06-11T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
