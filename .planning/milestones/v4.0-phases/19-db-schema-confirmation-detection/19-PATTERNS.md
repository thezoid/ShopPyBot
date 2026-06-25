# Phase 19: DB Schema + Confirmation Detection - Pattern Map

**Mapped:** 2026-06-11
**Files analyzed:** 8 (2 modified, 1 new module, 2 plugin overrides, 3 test files)
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `models.py` (ALTER block) | model/migration | CRUD | `models.py` lines 48-71 (price columns) | exact |
| `models.py` (update_item_confirmed_sync) | model/writer | CRUD | `models.py` `set_item_available_sync` lines 131-137 | exact |
| `core/confirmation.py` | utility/detector | request-response | `core/captcha.py` + `core/stealth.py` (pure-fn module with module-level map + helpers) | role-match |
| `core/orchestrator.py` (_try_auto_buy) | service/orchestrator | event-driven | `core/orchestrator.py` `_try_auto_buy` lines 182-193 | exact (modify in place) |
| `core/orchestrator.py` (_dispatch_write) | service/router | event-driven | `core/orchestrator.py` `_dispatch_write` lines 247-275 | exact (modify in place) |
| `core/plugin_base.py` (get_active_tab) | middleware/ABC hook | request-response | `core/plugin_base.py` `get_price` lines 72-79 | exact |
| `plugins/shopbot_plugin_amazon.py` | plugin | request-response | `plugins/shopbot_plugin_amazon.py` `auto_buy` lines 357-423 | exact (modify in place) |
| `plugins/shopbot_plugin_bestbuy.py` | plugin | request-response | `plugins/shopbot_plugin_bestbuy.py` `auto_buy` lines 249-308 | exact (modify in place) |
| `tests/test_models_confirmed.py` | test/migration | CRUD | `tests/test_price_history.py` lines 49-61 | exact |
| `tests/test_confirmation.py` | test/unit | request-response | `tests/conftest.py` `fake_browser` fixture + `tests/test_orchestrator.py` | role-match |

---

## Pattern Assignments

### `models.py` — ALTER TABLE block (idempotent migration)

**Analog:** `models.py` lines 48-71

**Exact migration pattern** (lines 48-71 — the `existing` set is built ONCE before all guards):
```python
# lines 48-52: build column set once
existing = {
    row[1]
    for row in conn.execute("PRAGMA table_info(items)").fetchall()
}
# lines 53-71: one guard per column, same `existing` snapshot
if "last_seen_available" not in existing:
    conn.execute(
        "ALTER TABLE items ADD COLUMN last_seen_available INTEGER NOT NULL DEFAULT 0"
    )
if "target_price" not in existing:
    conn.execute("ALTER TABLE items ADD COLUMN target_price INTEGER")
if "price_alert_armed" not in existing:
    conn.execute(
        "ALTER TABLE items ADD COLUMN price_alert_armed INTEGER NOT NULL DEFAULT 0"
    )
```

**Phase 19 block to append after line 71** (same pattern, same `existing` snapshot):
```python
# Phase 19: confirmation columns (BUY-03, BUY-04)
if "order_id" not in existing:
    conn.execute("ALTER TABLE items ADD COLUMN order_id TEXT")
if "confirmed_at" not in existing:
    conn.execute("ALTER TABLE items ADD COLUMN confirmed_at TEXT")
if "checkout_attempts" not in existing:
    conn.execute(
        "ALTER TABLE items ADD COLUMN checkout_attempts INTEGER NOT NULL DEFAULT 0"
    )
```

**Critical detail:** `NOT NULL DEFAULT 0` is required on `checkout_attempts` or Phase 21 arithmetic returns NULL on existing rows. The other two columns are nullable TEXT — this mirrors `target_price` (nullable) vs `price_alert_armed` (NOT NULL DEFAULT 0).

---

### `models.py` — update_item_confirmed_sync (new writer function)

**Analog:** `models.py` `set_item_available_sync` lines 131-137 and `update_item_purchased_sync` lines 92-95

**set_item_available_sync pattern** (multi-column UPDATE, parameterized):
```python
# lines 131-137
def set_item_available_sync(link: str, notified_at: str) -> None:
    """Set last_seen_available=1 and last_notified=notified_at (NOTIF-02)."""
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE items SET last_seen_available=1, last_notified=? WHERE link=?",
            (notified_at, link),
        )
```

**update_item_purchased_sync pattern** (single-column UPDATE):
```python
# lines 92-95
def update_item_purchased_sync(link):
    """Set purchased=1 for the item with the given link."""
    with get_db_connection() as conn:
        conn.execute("UPDATE items SET purchased=1 WHERE link=?", (link,))
```

**New function to add** (combine both patterns — three columns, parameterized):
```python
def update_item_confirmed_sync(link: str, order_id: str, confirmed_at: str) -> None:
    """Set purchased=1, order_id, and confirmed_at together (BUY-03/BUY-04).

    Provides the idempotency anchor for Phase 21 retry (BUY-05).
    """
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE items SET purchased=1, order_id=?, confirmed_at=? WHERE link=?",
            (order_id, confirmed_at, link),
        )
```

Place after `update_item_purchased_sync` (after line 95), before `add_items_sync`.

---

### `core/confirmation.py` (new module)

**Analog:** `core/captcha.py` (module-level constants + private helpers + one public function) and `core/stealth.py` (module-level data structures + pure utility functions)

**Module structure to copy from `core/captcha.py` lines 1-30:**
```python
"""Module docstring with BUY-03 requirement citation."""
from __future__ import annotations

import asyncio          # NOT used directly but conventional import
import urllib.parse
from datetime import datetime, timezone

_SETTLE_SECS = 3.0    # constant block like captcha.py _INITIAL_WAIT_SECS / _POLL_INTERVAL_SECS

_PLATFORM_MAP = { ... }  # module-level dict like captcha.py's _SUBMIT_URL / _RESULT_URL constants
```

**Private helper pattern from `core/captcha.py` `_submit_recaptcha` / `_poll_result`:**
```python
# Private helpers prefixed with _ ; no class needed; pure functions
async def _extract_order_id(tab, cfg: dict) -> str | None:
    ...

async def detect_order_confirmation(tab, platform: str) -> str | None:
    ...
```

**`writeLog` import style from `core/stealth.py`** — stealth.py does NOT import writeLog at module level; it is not needed there. In `core/confirmation.py`, import it inside the function body (same as orchestrator.py's deferred imports in `_build_event` line 48: `from notifications.base import NotificationEvent`).

**Full module skeleton** (derived from RESEARCH.md confirmed patterns):
```python
"""Order confirmation detection for post-checkout URL + DOM verification (BUY-03)."""
from __future__ import annotations

import urllib.parse
from datetime import datetime, timezone

_SETTLE_SECS = 3.0

_PLATFORM_MAP = {
    "AmazonPlugin": {
        "url_fragment": "/gp/buy/thankyou",
        "url_query_params": ["orderID", "orderId"],   # HIGH confidence -- UAT not yet done
        "selectors": ["#confirmedOrderId"],             # MEDIUM confidence -- UAT debt
    },
    "BestBuyPlugin": {
        "url_fragment": "/checkout/r/thank-you",
        "url_query_params": [],
        "selectors": [".thank-you-order-number"],       # MEDIUM confidence -- UAT debt
    },
}


async def _extract_order_id(tab, cfg: dict) -> str | None:
    ...


async def detect_order_confirmation(tab, platform: str) -> str | None:
    ...
```

---

### `core/orchestrator.py` — _try_auto_buy (modification)

**Analog:** `core/orchestrator.py` lines 182-193 (current body to modify)

**Current body** (lines 182-193):
```python
async def _try_auto_buy(plugin, name, link, write_queue, dispatcher) -> None:
    """Attempt auto-buy; dispatch purchased event and enqueue on success."""
    try:
        success = await plugin.auto_buy(link)
        if success:
            if dispatcher is not None:
                await dispatcher.notify(
                    _build_event(name, link, plugin.__class__.__name__, "purchased")
                )
            await write_queue.put(("purchased", link))
    except Exception as exc:
        writeLog(f"[{plugin.__class__.__name__}] auto_buy error: {exc}", "ERROR")
```

**Phase 19 replacement** — keep the same function signature, same try/except shell, insert confirmation detection between the dispatcher.notify call and the write_queue.put call. The `write_queue.put()` call must remain OUTSIDE any timeout context (PITFALLS #10):
```python
async def _try_auto_buy(plugin, name, link, write_queue, dispatcher) -> None:
    from core.confirmation import detect_order_confirmation
    from datetime import datetime, timezone
    try:
        success = await plugin.auto_buy(link)
        if success:
            if dispatcher is not None:
                await dispatcher.notify(
                    _build_event(name, link, plugin.__class__.__name__, "purchased")
                )
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
                    f"[{plugin.__class__.__name__}] confirmation not detected --"
                    " falling back to legacy purchased write",
                    "WARNING",
                )
                await write_queue.put(("purchased", link))
    except Exception as exc:
        writeLog(f"[{plugin.__class__.__name__}] auto_buy error: {exc}", "ERROR")
```

Also add `update_item_confirmed_sync` to the `from models import (...)` block at the top of orchestrator.py (lines 27-38).

---

### `core/orchestrator.py` — _dispatch_write (new branch)

**Analog:** `core/orchestrator.py` lines 247-275 (current `_dispatch_write` body)

**Multi-arg tuple branch pattern** (lines 266-269):
```python
elif tag == "set_available":
    link, ts = item[1], item[2]
    await loop.run_in_executor(None, set_item_available_sync, link, ts)
    writeLog(f"Marked available: {link}", "DEBUG")
```

**New branch to insert before the `else` at line 274:**
```python
elif tag == "confirmed":
    link, order_id, ts = item[1], item[2], item[3]
    await loop.run_in_executor(None, update_item_confirmed_sync, link, order_id, ts)
    writeLog(f"Order confirmed: {link} order_id={order_id}", "INFO")
```

Also update the docstring at lines 251-254 to add the new tag:
```
("confirmed", link, order_id, ts) -> update_item_confirmed_sync(link, order_id, ts)
```

---

### `core/plugin_base.py` — get_active_tab() ABC hook

**Analog:** `core/plugin_base.py` `get_price` lines 72-79

**get_price pattern** (additive concrete method, no-op default, PLUGIN_API_VERSION stays unchanged):
```python
# lines 72-79
async def get_price(self, url: str) -> int | None:
    """Return the current item price as integer cents, or None if unsupported.

    Default returns None (price monitoring unsupported for this plugin).
    PLUGIN_API_VERSION stays 2 -- additive non-abstract method (PRICE-02).
    Override in platform plugins that can scrape a live price.
    """
    return None
```

**New method to add after get_price** (sync, not async — tab objects are returned, not awaited):
```python
def get_active_tab(self):
    """Return the live tab for confirmation detection after auto_buy().

    Default returns driver.main_tab. Override in plugins that store the
    last-navigated tab explicitly (Amazon, BestBuy).
    PLUGIN_API_VERSION stays 2 -- additive concrete method (BUY-03).
    """
    return getattr(self.driver, "main_tab", None)
```

Note: `get_price` is `async def`; `get_active_tab` is sync `def` because it returns a stored object, not an awaitable. This distinction matters.

---

### `plugins/shopbot_plugin_amazon.py` — _last_tab storage

**Analog:** `plugins/shopbot_plugin_amazon.py` `auto_buy` lines 357-423

**Current final lines of auto_buy** (lines 415-423):
```python
            place_order = await tab.select("#submitOrderButtonId", timeout=10)
            if not place_order:
                writeLog("Place order button not found", "ERROR")
                return False

            return await self.place_order_guarded(place_order.click)
        except Exception as exc:
            writeLog(f"Error during Amazon auto-buy: {exc.__class__.__name__}", "ERROR")
            return False
```

**Phase 19 change** — insert `self._last_tab = tab` immediately before the `place_order_guarded` call:
```python
            place_order = await tab.select("#submitOrderButtonId", timeout=10)
            if not place_order:
                writeLog("Place order button not found", "ERROR")
                return False

            self._last_tab = tab  # BUY-03: expose confirmation page to orchestrator
            return await self.place_order_guarded(place_order.click)
```

**Override method to add** (after `auto_buy`, before `amz_sign_in` or next method):
```python
    def get_active_tab(self):
        """Return the tab last navigated by auto_buy(), or fall back to main_tab."""
        return getattr(self, "_last_tab", None) or getattr(self.driver, "main_tab", None)
```

---

### `plugins/shopbot_plugin_bestbuy.py` — _last_tab storage

**Analog:** `plugins/shopbot_plugin_bestbuy.py` `auto_buy` lines 249-308

**Current final lines of auto_buy** (lines 304-308):
```python
            place_order = await tab.select(".button--place-order", timeout=10)
            if not place_order:
                writeLog("Place order button not found", "ERROR")
                return False
            return await self.place_order_guarded(place_order.click)
```

**Phase 19 change:**
```python
            place_order = await tab.select(".button--place-order", timeout=10)
            if not place_order:
                writeLog("Place order button not found", "ERROR")
                return False
            self._last_tab = tab  # BUY-03: expose confirmation page to orchestrator
            return await self.place_order_guarded(place_order.click)
```

**Override method to add:**
```python
    def get_active_tab(self):
        """Return the tab last navigated by auto_buy(), or fall back to main_tab."""
        return getattr(self, "_last_tab", None) or getattr(self.driver, "main_tab", None)
```

---

### `tests/test_models_confirmed.py` (new test file)

**Analog:** `tests/test_price_history.py` lines 20-61 (migration + idempotency tests)

**Schema test pattern** (lines 35-46):
```python
def test_items_price_columns_added(tmp_data_dir):
    """initialize_db(delete=True) adds four new price columns to the items table."""
    models.initialize_db(delete=True)

    conn = sqlite3.connect(models.DB_PATH)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(items)").fetchall()}
    conn.close()

    assert "target_price" in cols
    assert "price_alert_armed" in cols
```

**Idempotency test pattern** (lines 49-61):
```python
def test_migration_idempotent(tmp_data_dir):
    """initialize_db() called twice does not raise or duplicate any column."""
    models.initialize_db(delete=True)  # fresh DB
    models.initialize_db()             # second call must not raise

    conn = sqlite3.connect(models.DB_PATH)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(items)").fetchall()]
    conn.close()

    assert cols.count("price_alert_armed") == 1
```

**v3.0-schema fixture pattern** — to test migration of an existing DB that lacks the new columns, create the pre-migration schema via raw SQL, then call `initialize_db()`:
```python
def test_migration_on_legacy_schema(tmp_data_dir):
    """initialize_db() on a DB that already has v3.0 schema adds the 3 new columns."""
    import sqlite3
    # Build schema WITHOUT the new columns (simulates v3.0 DB)
    conn = sqlite3.connect(models.DB_PATH)
    conn.execute(
        "CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT NOT NULL, "
        "link TEXT NOT NULL UNIQUE, auto_buy BOOLEAN NOT NULL, "
        "quantity INTEGER NOT NULL, purchased BOOLEAN NOT NULL DEFAULT 0)"
    )
    conn.commit()
    conn.close()

    models.initialize_db()  # must add columns without dropping table

    conn = sqlite3.connect(models.DB_PATH)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(items)").fetchall()}
    conn.close()
    assert "order_id" in cols
    assert "confirmed_at" in cols
    assert "checkout_attempts" in cols
```

**update_item_confirmed_sync test pattern** (mirrors `test_update_item_purchased` in `tests/test_models.py` lines 28-32):
```python
def test_update_item_confirmed(tmp_data_dir):
    models.initialize_db(delete=True)
    models.add_items_sync([("Widget", "https://ex.com/item", True, 1, False)])
    models.update_item_confirmed_sync("https://ex.com/item", "123-456", "2026-06-11T00:00:00+00:00")

    conn = sqlite3.connect(models.DB_PATH)
    row = conn.execute(
        "SELECT purchased, order_id, confirmed_at FROM items WHERE link=?",
        ("https://ex.com/item",),
    ).fetchone()
    conn.close()
    assert row[0] == 1
    assert row[1] == "123-456"
    assert row[2] == "2026-06-11T00:00:00+00:00"
```

---

### `tests/test_confirmation.py` (new test file)

**Analog for FakeTab fixture:** `tests/conftest.py` `fake_browser` fixture lines 73-97 (MagicMock pattern for nodriver objects)

**fake_browser pattern** (lines 84-96):
```python
fake_tab = MagicMock()
fake_tab.select = AsyncMock(return_value=fake_element)
fake_tab.evaluate = AsyncMock(return_value="normal page content")
fake_tab.main_tab = fake_tab
```

**FakeTab for confirmation tests** (simpler dataclass, not MagicMock — matches RESEARCH.md pattern):
```python
class FakeTab:
    def __init__(self, url: str, selector_map: dict):
        self.target = type("_T", (), {"url": url})()
        self._selector_map = selector_map

    async def sleep(self, t):
        pass  # skip settle

    async def select(self, selector, timeout=10):
        return self._selector_map.get(selector)


class FakeElement:
    def __init__(self, text: str):
        self.text = text
```

**Test structure pattern** (mirrors `test_price_history.py` — one assertion per requirement):
```python
import pytest
from core.confirmation import detect_order_confirmation

async def test_url_match_dom_hit():
    tab = FakeTab(
        url="https://amazon.com/gp/buy/thankyou?orderID=123-456-789",
        selector_map={"#confirmedOrderId": FakeElement("123-456-789")},
    )
    result = await detect_order_confirmation(tab, "AmazonPlugin")
    assert result == "123-456-789"

async def test_url_no_match():
    tab = FakeTab(url="https://amazon.com/product/B001", selector_map={})
    result = await detect_order_confirmation(tab, "AmazonPlugin")
    assert result is None

async def test_unknown_platform():
    tab = FakeTab(url="https://amazon.com/gp/buy/thankyou", selector_map={})
    result = await detect_order_confirmation(tab, "UnknownPlugin")
    assert result is None

async def test_url_match_dom_miss_returns_sentinel():
    tab = FakeTab(url="https://amazon.com/gp/buy/thankyou", selector_map={})
    result = await detect_order_confirmation(tab, "AmazonPlugin")
    assert result is not None
    assert result.startswith("CONFIRMED-")
```

**Orchestrator branch tests** (use `fake_plugin` from conftest + `asyncio.Queue`):
```python
async def test_orchestrator_confirmed_path(fake_plugin, tmp_data_dir):
    from core.orchestrator import _try_auto_buy
    plugin = fake_plugin(bought=True)
    plugin.get_active_tab = lambda: FakeTab(
        url="https://amazon.com/gp/buy/thankyou?orderID=123",
        selector_map={},
    )
    q = asyncio.Queue()
    await _try_auto_buy(plugin, "Widget", "https://amazon.com/...", q, None)
    item = q.get_nowait()
    assert item[0] == "confirmed"
    assert item[2].startswith("CONFIRMED-") or item[2] == "123"

async def test_orchestrator_fallback_path(fake_plugin, tmp_data_dir):
    from core.orchestrator import _try_auto_buy
    plugin = fake_plugin(bought=True)
    plugin.get_active_tab = lambda: FakeTab(url="https://amazon.com/product", selector_map={})
    q = asyncio.Queue()
    await _try_auto_buy(plugin, "Widget", "https://amazon.com/...", q, None)
    item = q.get_nowait()
    assert item[0] == "purchased"
```

---

## Shared Patterns

### DB write serialization (ASYNC-05)
**Source:** `core/orchestrator.py` `_dispatch_write` lines 260-265
**Apply to:** `update_item_confirmed_sync` call in `_dispatch_write` — always via `run_in_executor`
```python
await loop.run_in_executor(None, update_item_confirmed_sync, link, order_id, ts)
```
Never call `update_item_confirmed_sync` directly from a coroutine.

### get_db_connection context manager
**Source:** `models.py` lines 10-30
**Apply to:** `update_item_confirmed_sync` — use the same `with get_db_connection() as conn:` pattern. Do not create a raw `sqlite3.connect()` call.

### deferred inline imports
**Source:** `core/orchestrator.py` `_build_event` line 48, `_try_auto_buy` Phase 19 addition
**Apply to:** `core/confirmation.py` imports of `writeLog` — import inside function body, not at module top, to avoid circular import risk with `logger.py`.

### writeLog call style
**Source:** `core/orchestrator.py` lines 192, 269, 275
**Apply to:** All confirmation.py and orchestrator.py log calls
```python
writeLog(f"[ClassName] message: {value}", "WARNING")  # type string: INFO/DEBUG/WARNING/ERROR
```

### place_order_guarded return passthrough
**Source:** `plugins/shopbot_plugin_amazon.py` line 420, `plugins/shopbot_plugin_bestbuy.py` line 308
**Apply to:** Both plugins — `self._last_tab = tab` goes on the line BEFORE `return await self.place_order_guarded(...)`, never after (the return exits the function).

---

## No Analog Found

All files have close analogs. No files require falling back to RESEARCH.md patterns exclusively.

| File | Note |
|------|------|
| `core/confirmation.py` | No identical analog (no URL/DOM detector module exists). Module structure copied from `core/captcha.py`; tab API patterns from RESEARCH.md verified nodriver source. |

---

## Metadata

**Analog search scope:** `models.py`, `core/orchestrator.py`, `core/plugin_base.py`, `core/captcha.py`, `core/stealth.py`, `plugins/shopbot_plugin_amazon.py`, `plugins/shopbot_plugin_bestbuy.py`, `tests/test_price_history.py`, `tests/test_models.py`, `tests/conftest.py`
**Files scanned:** 10 source files read directly
**Pattern extraction date:** 2026-06-11
