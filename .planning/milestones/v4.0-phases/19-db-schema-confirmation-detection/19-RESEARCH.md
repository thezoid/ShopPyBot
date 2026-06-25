# Phase 19: DB Schema + Confirmation Detection - Research

**Researched:** 2026-06-11
**Domain:** SQLite schema migration, nodriver tab API, retail checkout confirmation detection
**Confidence:** MEDIUM (architecture HIGH; confirmation selectors MEDIUM/LOW pending live UAT)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- New `core/confirmation.py` with `async def detect_order_confirmation(tab, platform) -> str | None`.
- Add `get_active_tab()` hook to RetailerPlugin ABC (default returns `self.driver`/current tab).
- URL-first signal: Amazon `/gp/buy/thankyou`, BestBuy `/checkout/r/thank-you`.
- DOM order-number selector as backup.
- Settle delay: ~3s constant in `confirmation.py`, NOT a new CheckoutConfig field.
- Add `order_id TEXT`, `confirmed_at TEXT`, `checkout_attempts INTEGER DEFAULT 0` via idempotent ALTER TABLE.
- New write-queue tag `("confirmed", link, order_id, ts)` dispatched to `update_item_confirmed_sync`.
- Legacy `("purchased", link)` tag retained for fallback path.
- When confirmation NOT detected: log WARNING + fall back to legacy `purchased` write tag.
- `checkout_attempts` column added DEFAULT 0 but NOT incremented in Phase 19.
- Amazon + BestBuy implemented; other 5 plugins return None (legacy fallback).
- URL-confirm-without-id: use `"CONFIRMED-<ts>"` sentinel + log WARNING.
- `auto_buy()` signature stays `-> bool` (unchanged).
- PLUGIN_API_VERSION stays at 2 (additive hook).

### Claude's Discretion
- Exact DOM selector strings for order number (best-confidence from research; UAT debt).
- Settle delay exact value within ~3s guidance.
- Structure of the `get_active_tab()` default implementation.

### Deferred Ideas (OUT OF SCOPE)
- `checkout_attempts` increment strategy (Phase 21).
- Outcome analytics on BUY-04 records (future milestone).
- Live UAT of confirmation selectors (UAT debt, not blocking Phase 19).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BUY-03 | After `auto_buy` returns, orchestrator verifies a real placed order via URL + DOM signal with settle delay; `purchased` written only on confirmed order, never on button click | URL patterns confirmed HIGH; DOM selector strategy researched; orchestrator wiring pattern documented |
| BUY-04 | Bot records each checkout outcome with order id + timestamp; provides idempotency anchor for BUY-05 retry | DB schema migration pattern confirmed from models.py; write-queue tag pattern documented |
</phase_requirements>

## Summary

Phase 19 adds three new DB columns to the `items` table and introduces `core/confirmation.py`, which reads the live browser tab after `auto_buy()` returns True, applies a ~3s settle delay, and extracts an order ID from a URL path match or DOM selector. The orchestrator receives the order id and routes to a new `("confirmed", ...)` write-queue tag; failing that, it falls back to the legacy `("purchased", ...)` tag so no confirmation is silently dropped.

The nodriver API is well understood from direct code inspection of the installed `0.50.3` package. The confirmed pattern for reading the current tab URL is `tab.target.url` (sync, always up to date after `await tab` or `await tab.sleep(t)`) or `await tab.evaluate("window.location.href")` (async, always authoritative). The settle delay via `await tab.sleep(3)` is preferred because it also triggers `browser.update_targets()`, refreshing `tab.target.url` before the URL check.

Amazon confirmation URL pattern (`/gp/buy/thankyou`) is HIGH confidence from the STATE.md research flag and is consistent with public bot source code analysis. BestBuy confirmation URL (`/checkout/r/thank-you`) is HIGH confidence, verified from PhoenixBot source code via direct inspection. DOM order-number selectors for both are MEDIUM/LOW confidence and are tagged as UAT debt per the CONTEXT.md decision.

**Primary recommendation:** Use `await tab.sleep(3)` as settle, then `tab.target.url` for URL check (sync, no extra await), then `await tab.select(selector, timeout=5)` for DOM fallback. Structure `get_active_tab()` to return the tab object returned by the last `await self.driver.get(url)` call inside `auto_buy()`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| DB schema migration | Database/Storage | -- | ALTER TABLE is a DB-layer concern in `models.py` |
| Order confirmation detection | API/Backend (orchestrator) | Plugin (tab access) | Orchestrator owns the write decision; plugin exposes the live tab via hook |
| Write serialization | API/Backend (write queue) | -- | All DB writes go through `_write_queue_drain` (ASYNC-05) |
| Confirmation DOM/URL parsing | core/confirmation.py module | -- | Isolated module, no plugin coupling beyond tab API |
| Plugin tab exposure | Plugin tier | -- | `get_active_tab()` hook on ABC; plugin knows which tab is live |

## Standard Stack

No new external packages. All capabilities use the installed stack.

### Core (existing, no new installs)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| nodriver | 0.50.3 | Tab URL + DOM query API | Already installed; confirmed via `python -c "import nodriver; print(nodriver.__version__)"` |
| sqlite3 | stdlib | DB migration + write | Existing DB layer |
| asyncio | stdlib | Settle delay + async orchestration | Existing async model |

### No New Dependencies
This phase requires zero new package installs. [VERIFIED: direct inspection of installed packages]

## Package Legitimacy Audit

No new packages installed in this phase. Audit not applicable.

## Architecture Patterns

### System Architecture Diagram

```
auto_buy() returns True
       |
       v
_try_auto_buy (orchestrator)
       |
       +--- calls plugin.get_active_tab() --> live nodriver Tab object
       |
       v
detect_order_confirmation(tab, platform)  [core/confirmation.py]
       |
       +-- await tab.sleep(3)              [settle delay + update_targets()]
       |
       +-- check tab.target.url            [sync URL read]
       |       |
       |       +-- URL matches pattern?
       |               YES --> try DOM selector for order_id
       |                         |
       |                         +-- element found? --> return order_id str
       |                         +-- not found?    --> return "CONFIRMED-<ts>" sentinel
       |               NO  --> return None
       |
       v
orchestrator receives str | None
       |
       +-- order_id is not None:
       |       enqueue ("confirmed", link, order_id, ts)
       |       _dispatch_write --> update_item_confirmed_sync(link, order_id, ts)
       |           sets purchased=1, order_id, confirmed_at
       |
       +-- order_id is None:
               log WARNING
               enqueue ("purchased", link)   [legacy fallback]
               _dispatch_write --> update_item_purchased_sync(link)
```

### Recommended Project Structure

```
core/
├── confirmation.py        # NEW: detect_order_confirmation() + platform map
├── plugin_base.py         # ADD: get_active_tab() hook
├── orchestrator.py        # MODIFY: _try_auto_buy, _dispatch_write
models.py                  # MODIFY: initialize_db() ALTER TABLE block
                           #         + update_item_confirmed_sync()
plugins/
├── shopbot_plugin_amazon.py    # ADD: get_active_tab() override
├── shopbot_plugin_bestbuy.py   # ADD: get_active_tab() override
tests/
├── test_confirmation.py        # NEW
├── test_models_confirmed.py    # NEW (or extend test_models.py)
```

### Pattern 1: nodriver Tab URL Reading

**What:** After auto_buy(), the live tab is the page that `auto_buy` last navigated to. `tab.target.url` is a sync str field on the `cdp.target.TargetInfo` dataclass. It is refreshed when `browser.update_targets()` runs, which `await tab.sleep(t)` triggers automatically.

**Key API facts** (all VERIFIED: direct inspection of nodriver 0.50.3 source):
- `tab.target` is a `cdp.target.TargetInfo` dataclass with `.url: str` field [VERIFIED]
- `tab.target.url` is synchronous, no await required [VERIFIED]
- `await tab.sleep(t)` calls `browser.update_targets()` which refreshes `tab.target.url` [VERIFIED]
- `await tab.evaluate("window.location.href")` returns the authoritative current URL as str (always up to date) [VERIFIED]
- `await tab.select(selector, timeout=N)` returns an Element or None [VERIFIED]
- `element.text` is a str attribute on nodriver Element [VERIFIED: AmazonPlugin uses it at line 238]

**When to use:** After settle delay, `tab.target.url` is sufficient and avoids an extra CDP round-trip. For belt-and-suspenders, `await tab.evaluate("window.location.href")` is the fallback.

**Example:**
```python
# Source: direct nodriver 0.50.3 source inspection
async def detect_order_confirmation(tab, platform: str) -> str | None:
    import asyncio
    from datetime import datetime, timezone

    _SETTLE_SECS = 3.0

    # Settle: sleep triggers browser.update_targets() which refreshes tab.target.url
    await tab.sleep(_SETTLE_SECS)

    current_url = tab.target.url  # sync read, refreshed by sleep above
    platform_cfg = _PLATFORM_MAP.get(platform)
    if platform_cfg is None:
        return None  # unknown platform -- legacy fallback

    if platform_cfg["url_fragment"] not in current_url:
        return None  # URL does not match -- not on confirmation page

    # URL matched: try DOM order-id selector
    order_id = await _extract_order_id(tab, platform_cfg["selectors"])
    if order_id:
        return order_id

    # URL matched but no DOM id: use sentinel
    ts = datetime.now(timezone.utc).isoformat()
    return f"CONFIRMED-{ts}"
```

### Pattern 2: Idempotent ALTER TABLE Migration

**What:** The existing `initialize_db()` in `models.py` reads `PRAGMA table_info(items)` into a set, then guards each `ALTER TABLE ... ADD COLUMN` with `if "col_name" not in existing`. This is the established pattern from Phase 16.

**Exact pattern** (VERIFIED: direct read of models.py lines 48-71):

```python
# Source: models.py lines 48-71 (Phase 16 price columns)
existing = {
    row[1]
    for row in conn.execute("PRAGMA table_info(items)").fetchall()
}
if "target_price" not in existing:
    conn.execute("ALTER TABLE items ADD COLUMN target_price INTEGER")
if "price_drop_pct" not in existing:
    conn.execute("ALTER TABLE items ADD COLUMN price_drop_pct REAL")
```

**Phase 19 additions follow same pattern:**
```python
# Phase 19: confirmation columns (idempotent -- BUY-03, BUY-04)
if "order_id" not in existing:
    conn.execute("ALTER TABLE items ADD COLUMN order_id TEXT")
if "confirmed_at" not in existing:
    conn.execute("ALTER TABLE items ADD COLUMN confirmed_at TEXT")
if "checkout_attempts" not in existing:
    conn.execute(
        "ALTER TABLE items ADD COLUMN checkout_attempts INTEGER NOT NULL DEFAULT 0"
    )
```

**Critical detail:** The `existing` set is built ONCE from `PRAGMA table_info` before all the guards. All three `if` checks use the same `existing` snapshot. This is safe because each column add is an independent DDL, and SQLite auto-commits DDL within the connection's implicit transaction. [VERIFIED: models.py pattern]

### Pattern 3: Write-Queue Tag Routing

**What:** `_dispatch_write` in `orchestrator.py` uses a `tag = item[0]` switch on typed tuples. New `("confirmed", link, order_id, ts)` tag routes to `update_item_confirmed_sync`. The unknown-tag branch already logs a WARNING.

**Exact pattern** (VERIFIED: orchestrator.py lines 247-275):

```python
# Adding ("confirmed", link, order_id, ts) branch to _dispatch_write
elif tag == "confirmed":
    link, order_id, ts = item[1], item[2], item[3]
    await loop.run_in_executor(None, update_item_confirmed_sync, link, order_id, ts)
    writeLog(f"Order confirmed: {link} order_id={order_id}", "INFO")
```

**`update_item_confirmed_sync` signature:**
```python
def update_item_confirmed_sync(link: str, order_id: str, confirmed_at: str) -> None:
    """Set purchased=1, order_id, and confirmed_at together (BUY-03/BUY-04)."""
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE items SET purchased=1, order_id=?, confirmed_at=? WHERE link=?",
            (order_id, confirmed_at, link),
        )
```

### Pattern 4: get_active_tab() ABC Hook

**What:** Additive concrete method on `RetailerPlugin` ABC. Default returns `self.driver.main_tab` (the always-available Browser.main_tab). Amazon and BestBuy override to return the tab object that `auto_buy` last navigated to.

**The tab-capture problem:** `auto_buy()` in both plugins uses a local `tab` variable assigned by `await self.driver.get(url)`. That local is not stored on `self` after `auto_buy()` returns. Two options:

1. Store the tab on `self` at the end of `auto_buy()`: `self._last_tab = tab`
2. Return `self.driver.main_tab` and rely on the settle sleep to update it.

Option 2 is simpler (no state mutation), but carries a risk: if `auto_buy` opened a new tab, `main_tab` may not be the confirmation tab. Option 1 is safer and matches the CONTEXT.md intent for `get_active_tab()`.

**Recommended approach:** Store `self._last_tab = tab` before `return await self.place_order_guarded(...)` in both plugins. `get_active_tab()` returns `self._last_tab or self.driver.main_tab`.

**ABC default:**
```python
# Source: plugin_base.py addition (additive, PLUGIN_API_VERSION stays 2)
def get_active_tab(self):
    """Return the live tab for confirmation detection.

    Default returns driver.main_tab. Override in plugins that track the
    last-navigated tab explicitly (Amazon, BestBuy).
    """
    return getattr(self.driver, "main_tab", None)
```

**Plugin override (both Amazon and BestBuy):**
```python
def get_active_tab(self):
    """Return the tab last navigated by auto_buy(), or fall back to main_tab."""
    return getattr(self, "_last_tab", None) or getattr(self.driver, "main_tab", None)
```

### Pattern 5: _try_auto_buy Wiring

**Current** (orchestrator.py lines 182-193):
```python
async def _try_auto_buy(plugin, name, link, write_queue, dispatcher) -> None:
    try:
        success = await plugin.auto_buy(link)
        if success:
            if dispatcher is not None:
                await dispatcher.notify(...)
            await write_queue.put(("purchased", link))
    except Exception as exc:
        writeLog(f"[{plugin.__class__.__name__}] auto_buy error: {exc}", "ERROR")
```

**Phase 19 addition:**
```python
async def _try_auto_buy(plugin, name, link, write_queue, dispatcher) -> None:
    from core.confirmation import detect_order_confirmation
    from datetime import datetime, timezone
    try:
        success = await plugin.auto_buy(link)
        if success:
            if dispatcher is not None:
                await dispatcher.notify(...)
            # BUY-03: confirm before writing purchased
            tab = plugin.get_active_tab()
            platform = plugin.__class__.__name__
            order_id = None
            if tab is not None:
                order_id = await detect_order_confirmation(tab, platform)
            if order_id is not None:
                ts = datetime.now(timezone.utc).isoformat()
                await write_queue.put(("confirmed", link, order_id, ts))
            else:
                writeLog(
                    f"[{plugin.__class__.__name__}] confirmation not detected -- "
                    "falling back to legacy purchased write",
                    "WARNING",
                )
                await write_queue.put(("purchased", link))
    except Exception as exc:
        writeLog(f"[{plugin.__class__.__name__}] auto_buy error: {exc}", "ERROR")
```

**Note:** The `write_queue.put()` calls are OUTSIDE any timeout context (forward-compat with Phase 21/22 per PITFALLS #10 in STATE.md). The settle delay is INSIDE `detect_order_confirmation`, not wrapped by a timeout in `_try_auto_buy`.

### Anti-Patterns to Avoid

- **Reading `tab.target.url` without prior settle:** `tab.target.url` may still show the pre-confirmation page URL if `browser.update_targets()` has not run. Always `await tab.sleep(3)` first.
- **Storing `tab` as a closure inside `auto_buy` without assigning to `self`:** The orchestrator calls `get_active_tab()` after `auto_buy()` returns, so the tab must survive on `self._last_tab`.
- **Using `await tab` instead of `await tab.sleep(t)` for the settle:** `await tab` calls `tab.wait()` which calls `tab.sleep(0.5)`, which may not be long enough for the confirmation page to render.
- **Wrapping settle delay inside `asyncio.timeout` in `_try_auto_buy`:** The write must happen even if a future timeout fires (PITFALLS #10 in STATE.md).
- **Calling `update_item_confirmed_sync` directly from the plugin:** The write must go through the write queue (ASYNC-05).
- **Omitting the `checkout_attempts` column from the idempotent block:** It must be added with `NOT NULL DEFAULT 0` to avoid NULL constraint violations on existing rows.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| URL substring match | Custom URL parser | `platform_cfg["url_fragment"] in current_url` | Simple `in` check is sufficient; no regex needed |
| DB column existence check | Custom schema probe | `PRAGMA table_info(items)` set comprehension | Existing pattern in models.py; SQLite stdlib |
| Async DB call | Direct sync call in coroutine | `loop.run_in_executor(None, fn, *args)` | Existing pattern throughout orchestrator; preserves ASYNC-01 |
| Tab URL after navigation | Extra CDP call | `tab.target.url` after `await tab.sleep(3)` | Sleep already calls `update_targets()`; no extra round-trip |

## Confirmation Signal Research

### Amazon

**URL Pattern:** `https://www.amazon.com/gp/buy/thankyou/...` [ASSUMED based on STATE.md research flag and training knowledge; HIGH confidence per STATE.md annotation]

Confidence: HIGH that the path contains `/gp/buy/thankyou`. The fragment check `"/gp/buy/thankyou" in tab.target.url` is the primary signal.

**DOM Order Number Selectors (priority order):**

| Selector | Confidence | Source |
|----------|------------|--------|
| `#confirmedOrderId` | MEDIUM | [ASSUMED: training knowledge + STATE.md research flag] |
| `#widget-purchaseConfirmationStatus` | LOW | [ASSUMED: training knowledge] |
| `[data-testid="order-id"]` | LOW | [ASSUMED: training knowledge] |

**URL-embedded order ID:** Amazon confirmation URL sometimes contains `orderID=XXX-XXXXXXX-XXXXXXX` as a query param. Parsing `urllib.parse.urlparse(url).query` and extracting `orderID` is a HIGH-confidence fallback that does not depend on DOM layout.

```python
# Recommended: try URL query param first, then DOM
import urllib.parse
parsed = urllib.parse.urlparse(current_url)
params = urllib.parse.parse_qs(parsed.query)
order_id = params.get("orderID", [None])[0]
if not order_id:
    order_id = params.get("orderId", [None])[0]  # case variant
```

This is the most reliable signal short of DOM inspection. The URL format `https://www.amazon.com/gp/css/summary/edit.html?orderID=302-0010732-9069141` is documented in the Ajanth Selenium project README. [CITED: github.com/Ajanth/Selenium-Automation---Order-Products-from-Amazon README]

**Recommended strategy for Amazon:**
1. URL fragment check: `/gp/buy/thankyou` in URL (primary gate)
2. URL query param: `orderID` or `orderId` in query string (HIGH confidence order_id source)
3. DOM selector `#confirmedOrderId` (MEDIUM confidence fallback)
4. Sentinel `CONFIRMED-<ts>` if URL matched but no ID found

### BestBuy

**URL Pattern:** `https://www.bestbuy.com/checkout/r/thank-you` [VERIFIED: PhoenixBot source code check `'https://www.bestbuy.com/checkout/r/thank-you' in self.browser.current_url`]

Confidence: HIGH. The fragment check `"/checkout/r/thank-you" in tab.target.url` is the primary signal.

**DOM Order Number Selectors:**

| Selector | Confidence | Source |
|----------|------------|--------|
| `.thank-you-order-number` | MEDIUM | [ASSUMED: STATE.md research flag] |
| `[data-testid="order-number"]` | LOW | [ASSUMED: training knowledge] |
| `.order-confirmation-number` | LOW | [ASSUMED: training knowledge] |

No public bot code was found that extracts the BestBuy order number from the DOM. All existing bots checked (PhoenixBot, Agressive-Store-Bots, Konyanj0278) consider URL presence alone as success without extracting an order number. [CITED: github.com/Strip3s/PhoenixBot, github.com/TreborNamor/Agressive-Store-Bots, github.com/Konyanj0278/BestBuy-Automated-Checkout]

**Recommended strategy for BestBuy:**
1. URL fragment check: `/checkout/r/thank-you` in URL (primary gate, HIGH confidence)
2. DOM selector `.thank-you-order-number` (MEDIUM confidence fallback)
3. Sentinel `CONFIRMED-<ts>` if URL matched but no ID found

### Platform Map Structure

```python
# Source: core/confirmation.py (to be created)
_PLATFORM_MAP = {
    "AmazonPlugin": {
        "url_fragment": "/gp/buy/thankyou",
        "url_query_param": "orderID",          # try URL param before DOM
        "selectors": ["#confirmedOrderId"],     # [ASSUMED -- UAT required]
    },
    "BestBuyPlugin": {
        "url_fragment": "/checkout/r/thank-you",
        "url_query_param": None,
        "selectors": [".thank-you-order-number"],  # [ASSUMED -- UAT required]
    },
}
```

## Common Pitfalls

### Pitfall 1: Stale tab.target.url Without Settle

**What goes wrong:** `tab.target.url` returns the product page URL (pre-redirect) immediately after `auto_buy()` returns because `browser.update_targets()` has not run.
**Why it happens:** `update_targets()` is triggered by `await tab.sleep()` or explicitly. Just reading the attribute does not refresh it.
**How to avoid:** Always `await tab.sleep(3)` before reading `tab.target.url`. This calls `browser.update_targets()` internally.
**Warning signs:** URL check always fails; confirmation never detected; all orders fall back to legacy path.

### Pitfall 2: Tab Object Is Wrong Tab

**What goes wrong:** Amazon's buy-now flow opens new pages mid-checkout; `self.driver.main_tab` is still the product page, not the confirmation page.
**Why it happens:** `main_tab` is the first tab created at Browser startup and does not track navigation across redirects caused by the checkout flow.
**How to avoid:** Store `self._last_tab = tab` inside `auto_buy()` before `return await self.place_order_guarded(...)`. `get_active_tab()` returns `self._last_tab`.
**Warning signs:** URL check fails; tab shows product page URL.

### Pitfall 3: write_queue.put() Inside a Future Timeout Context

**What goes wrong:** Phase 22 wraps `_check_and_buy` in `asyncio.timeout`. If the timeout fires after `auto_buy()` returns True but before `write_queue.put()`, the DB write is orphaned.
**Why it happens:** `asyncio.timeout` cancels the coroutine at the next await point.
**How to avoid:** `write_queue.put()` in `_try_auto_buy` must remain OUTSIDE any timeout context. Per STATE.md PITFALLS #10: "write_queue.put() calls must be OUTSIDE the timeout context."
**Warning signs:** Purchased item not recorded in DB; item gets attempted again next cycle; potential double-buy.

### Pitfall 4: NULL Constraint on checkout_attempts

**What goes wrong:** `ALTER TABLE items ADD COLUMN checkout_attempts INTEGER` without `NOT NULL DEFAULT 0` leaves existing rows with NULL. If Phase 21 later does `checkout_attempts + 1`, NULL arithmetic returns NULL.
**Why it happens:** SQLite allows NULL for added columns unless DEFAULT is specified.
**How to avoid:** Use `ALTER TABLE items ADD COLUMN checkout_attempts INTEGER NOT NULL DEFAULT 0`.
**Warning signs:** Phase 21 increment fails silently; `checkout_attempts` stays NULL.

### Pitfall 5: Double-Buy From the Confirmation Path

**What goes wrong:** Both `("confirmed", ...)` and `("purchased", ...)` are enqueued for the same link.
**Why it happens:** Incorrect branching: both paths execute instead of one.
**How to avoid:** The `if order_id is not None ... else ...` structure in `_try_auto_buy` must be mutually exclusive. Only one `write_queue.put()` per successful `auto_buy()`.
**Warning signs:** `purchased=1` set twice; no crash but DB write is redundant (idempotent UPDATE so not catastrophic, but signals a logic error).

### Pitfall 6: `_last_tab` Not Set When auto_buy Returns False

**What goes wrong:** `self._last_tab` is set early in `auto_buy()`, then `auto_buy()` returns False. On the next successful run, `_last_tab` refers to the wrong (prior) tab.
**Why it happens:** `_last_tab` is only read when `auto_buy()` returns True, but if it was set in an error path, it may be stale.
**How to avoid:** Only set `self._last_tab = tab` immediately before the final `place_order_guarded()` call (the last navigation). If `auto_buy()` returns False, `_last_tab` is never updated in that call, so a prior stale value could be returned. Guard in `get_active_tab()`: check `_last_tab` is not None.
**Warning signs:** Confirmation detects the wrong order; order ID mismatch.

## Code Examples

### Full detect_order_confirmation Skeleton

```python
# Source: architecture derived from nodriver 0.50.3 source inspection + locked decisions
import asyncio
import urllib.parse
from datetime import datetime, timezone

_SETTLE_SECS = 3.0

_PLATFORM_MAP = {
    "AmazonPlugin": {
        "url_fragment": "/gp/buy/thankyou",
        "url_query_params": ["orderID", "orderId"],   # try URL param before DOM [ASSUMED]
        "selectors": ["#confirmedOrderId"],             # [ASSUMED -- UAT required]
    },
    "BestBuyPlugin": {
        "url_fragment": "/checkout/r/thank-you",
        "url_query_params": [],
        "selectors": [".thank-you-order-number"],       # [ASSUMED -- UAT required]
    },
}


async def _extract_order_id(tab, cfg: dict) -> str | None:
    """Try URL query params first, then DOM selectors. Return first non-empty str or None."""
    from logger import writeLog

    # URL query param extraction (Amazon orderID)
    current_url = tab.target.url
    for param in cfg.get("url_query_params", []):
        try:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(current_url).query)
            val = qs.get(param, [None])[0]
            if val and val.strip():
                return val.strip()
        except Exception:
            pass

    # DOM selector fallback
    for selector in cfg.get("selectors", []):
        try:
            element = await tab.select(selector, timeout=5)
            if element is None:
                continue
            text = (getattr(element, "text", None) or "").strip()
            if text:
                return text
        except Exception as exc:
            writeLog(
                f"[confirmation] selector {selector!r} error: {exc.__class__.__name__}",
                "DEBUG",
            )
    return None


async def detect_order_confirmation(tab, platform: str) -> str | None:
    """Detect order confirmation; return order id str or None.

    URL-first with DOM backup (BUY-03). Settle delay ensures tab.target.url
    is updated before the check. Unknown platforms return None (legacy fallback).
    """
    from logger import writeLog

    cfg = _PLATFORM_MAP.get(platform)
    if cfg is None:
        return None

    await tab.sleep(_SETTLE_SECS)  # triggers browser.update_targets()
    current_url = tab.target.url

    if cfg["url_fragment"] not in current_url:
        return None  # not on confirmation page

    order_id = await _extract_order_id(tab, cfg)
    if order_id:
        return order_id

    # URL matched but no order ID extractable -- use sentinel
    ts = datetime.now(timezone.utc).isoformat()
    writeLog(
        f"[confirmation] URL matched for {platform} but no order id found -- "
        f"using sentinel CONFIRMED-{ts}",
        "WARNING",
    )
    return f"CONFIRMED-{ts}"
```

### models.py update_item_confirmed_sync

```python
# Source: pattern from update_item_purchased_sync + Phase 19 new columns
def update_item_confirmed_sync(link: str, order_id: str, confirmed_at: str) -> None:
    """Set purchased=1, order_id, and confirmed_at together (BUY-03/BUY-04).

    Provides the idempotency anchor for Phase 21 retry (BUY-05): order_id
    is present iff the order was confirmed.
    """
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE items SET purchased=1, order_id=?, confirmed_at=? WHERE link=?",
            (order_id, confirmed_at, link),
        )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Mark purchased on button click | Mark confirmed only after URL+DOM verification | Phase 19 | Eliminates false purchased records on failed checkouts |
| Single `purchased` write tag | `confirmed` tag with order_id + `purchased` legacy fallback | Phase 19 | Provides idempotency anchor for Phase 21 retry |
| `self.driver.main_tab` direct access | `get_active_tab()` ABC hook | Phase 19 | Decouples orchestrator from plugin tab internals |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Amazon confirmation URL contains `/gp/buy/thankyou` path fragment | Confirmation Signal Research | Primary URL gate fails; all Amazon confirmations fall to sentinel; still no double-buy |
| A2 | `#confirmedOrderId` DOM selector exists on Amazon confirmation page | Confirmation Signal Research | DOM fallback fails; sentinel used; still no double-buy |
| A3 | `widget-purchaseConfirmationStatus` is a valid backup selector for Amazon | Confirmation Signal Research | Low risk; only used as tertiary |
| A4 | `.thank-you-order-number` DOM selector exists on BestBuy confirmation page | Confirmation Signal Research | DOM fallback fails; sentinel used; still no double-buy |
| A5 | 3s settle is sufficient for confirmation page to render after place_order_guarded | Common Pitfalls | Too short: URL check fails; all fall to sentinel; no double-buy; UAT debt |
| A6 | Amazon sets `orderID` query param on the thankyou URL | Confirmation Signal Research | URL param extraction returns None; DOM tried; still functions |

## Open Questions

1. **Amazon confirmation URL exact structure post-2025 checkout redesign**
   - What we know: `/gp/buy/thankyou` was the historical path; `orderID` as query param documented in Ajanth project README
   - What's unclear: Amazon redesigns checkout UI periodically; 1-Click and Buy-Now flows may differ
   - Recommendation: hardcode current values; flag for first live UAT run (UAT debt per CONTEXT.md)

2. **BestBuy order number DOM element in 2025/2026 markup**
   - What we know: zero public bots extract order number from the thank-you DOM; URL presence is the standard signal
   - What's unclear: exact CSS class/data-testid for the order number element
   - Recommendation: hardcode `.thank-you-order-number` as primary attempt; sentinel is acceptable fallback for MVP

3. **Tab reference across place_order_guarded redirect**
   - What we know: `await self.driver.get(url)` returns a Tab; redirects within that navigation stay on the same Tab object (nodriver Tab = browser view, not a URL snapshot)
   - What's unclear: if `place_order_guarded` triggers a redirect to a NEW Tab (e.g., pop-up), `_last_tab` may be the pre-redirect tab
   - Recommendation: use `self.driver.main_tab` as the fallback in `get_active_tab()` in case `_last_tab` navigation was on the main tab anyway

## Environment Availability

No new external dependencies. All tools already available.

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| nodriver | Tab URL + DOM query | Yes | 0.50.3 | -- |
| sqlite3 | DB migration | Yes | stdlib | -- |
| asyncio | Settle delay + orchestration | Yes | stdlib | -- |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest with asyncio_mode=auto (pytest-asyncio) |
| Config file | pyproject.toml (asyncio_mode=auto) |
| Quick run command | `pytest tests/test_confirmation.py tests/test_models_confirmed.py -x` |
| Full suite command | `pytest` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BUY-03 | `detect_order_confirmation` returns order_id when URL matches + DOM finds text | unit | `pytest tests/test_confirmation.py::test_url_match_dom_hit -x` | No -- Wave 0 |
| BUY-03 | `detect_order_confirmation` returns sentinel when URL matches but no DOM hit | unit | `pytest tests/test_confirmation.py::test_url_match_dom_miss -x` | No -- Wave 0 |
| BUY-03 | `detect_order_confirmation` returns None when URL does not match | unit | `pytest tests/test_confirmation.py::test_url_no_match -x` | No -- Wave 0 |
| BUY-03 | `detect_order_confirmation` returns None for unknown platform | unit | `pytest tests/test_confirmation.py::test_unknown_platform -x` | No -- Wave 0 |
| BUY-03 | `_try_auto_buy` enqueues `("confirmed", ...)` when order_id non-None | unit | `pytest tests/test_confirmation.py::test_orchestrator_confirmed_path -x` | No -- Wave 0 |
| BUY-03 | `_try_auto_buy` enqueues `("purchased", ...)` fallback when order_id is None | unit | `pytest tests/test_confirmation.py::test_orchestrator_fallback_path -x` | No -- Wave 0 |
| BUY-04 | `initialize_db` adds 3 columns idempotently on existing v3.0-schema DB | unit | `pytest tests/test_models_confirmed.py::test_migration_idempotent -x` | No -- Wave 0 |
| BUY-04 | `update_item_confirmed_sync` sets purchased=1, order_id, confirmed_at | unit | `pytest tests/test_models_confirmed.py::test_update_item_confirmed -x` | No -- Wave 0 |
| BUY-04 | `_dispatch_write("confirmed", ...)` routes to `update_item_confirmed_sync` | unit | `pytest tests/test_confirmation.py::test_dispatch_confirmed_tag -x` | No -- Wave 0 |
| BUY-04 | Re-running `initialize_db` on a schema that already has all 3 columns does not error | unit | `pytest tests/test_models_confirmed.py::test_migration_already_migrated -x` | No -- Wave 0 |

### Fake Tab Pattern for Unit Tests

```python
# Pattern for testing detect_order_confirmation without a real browser
class FakeTab:
    def __init__(self, url: str, selector_map: dict):
        self.target = type("FakeTarget", (), {"url": url})()
        self._selector_map = selector_map  # {selector: FakeElement or None}

    async def sleep(self, t):
        pass  # skip settle in tests

    async def select(self, selector, timeout=10):
        return self._selector_map.get(selector)

class FakeElement:
    def __init__(self, text: str):
        self.text = text
```

### Sampling Rate
- Per task commit: `pytest tests/test_confirmation.py tests/test_models_confirmed.py -x`
- Per wave merge: `pytest` (full suite, currently ~567 tests)
- Phase gate: Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_confirmation.py` -- covers BUY-03 (confirmation detection, orchestrator wiring)
- [ ] `tests/test_models_confirmed.py` -- covers BUY-04 (migration idempotency, update_item_confirmed_sync, dispatch tag)

*(No new framework needed -- asyncio_mode=auto already configured)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | -- |
| V3 Session Management | no | -- |
| V4 Access Control | no | -- |
| V5 Input Validation | yes | order_id from DOM/URL is used only as a stored string; not exec'd or logged with CVV; strip() to normalize |
| V6 Cryptography | no | -- |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| DOM text injection (e.g., page supplies malicious order_id) | Tampering | order_id stored as TEXT only; never eval'd, never used in SQL without parameterized query |
| Logging order_id that contains PII | Info Disclosure | Acceptable: order numbers are non-sensitive identifiers; do not log CVV alongside order_id (existing policy) |

**Security note:** Never log `self._cvv` adjacent to order confirmation logs. The confirmation log line `order_id={order_id}` is safe. The `_cvv` write happens in BestBuy `auto_buy()` before confirmation; they are in different code paths.

## Sources

### Primary (HIGH confidence)
- nodriver 0.50.3 source code (`Tab`, `Connection`, `Browser`) -- direct `inspect.getsource()` inspection; tab URL API, sleep/update_targets mechanism
- models.py lines 48-71 -- idempotent ALTER TABLE migration pattern (PRAGMA table_info guard)
- core/orchestrator.py lines 182-193, 247-275 -- `_try_auto_buy` and `_dispatch_write` patterns
- core/plugin_base.py -- `get_price` no-op default pattern for additive hook

### Secondary (MEDIUM confidence)
- STATE.md Research Flags section -- Amazon/BestBuy confirmation URL patterns + DOM selector candidates
- PhoenixBot/sites/bestbuy.py (github.com/Strip3s/PhoenixBot) -- BestBuy `/checkout/r/thank-you` URL pattern confirmed
- Ajanth/Selenium-Automation README -- Amazon order URL structure with `orderID` query param

### Tertiary (LOW confidence)
- Amazon DOM selectors (`#confirmedOrderId`, etc.) -- training knowledge, unverified; require live UAT
- BestBuy DOM selectors (`.thank-you-order-number`, etc.) -- training knowledge + STATE.md; require live UAT

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new packages; existing nodriver 0.50.3 API verified from source
- Architecture (migration pattern, write queue, ABC hook): HIGH -- all verified against existing code
- nodriver tab URL API: HIGH -- verified from `inspect.getsource()` of installed package
- BestBuy URL confirmation pattern: HIGH -- verified from PhoenixBot source code
- Amazon URL confirmation pattern: MEDIUM -- consistent across multiple sources but not directly verified from live page
- DOM selectors (both retailers): LOW -- unverified training knowledge; UAT required

**Research date:** 2026-06-11
**Valid until:** 2026-07-11 (DOM selectors may change on retailer updates; URL patterns more stable)
