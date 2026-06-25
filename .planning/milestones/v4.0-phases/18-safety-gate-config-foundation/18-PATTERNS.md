# Phase 18: Safety Gate + Config Foundation - Pattern Map

**Mapped:** 2026-06-11
**Files analyzed:** 12 (7 plugin reroutes + 3 core edits + 1 CLI file + 1 new test file)
**Analogs found:** 12 / 12

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `core/config_schema.py` (DebugConfig + CheckoutConfig + AppConfig) | config model | transform | `core/config_schema.py` WalmartPlatformConfig + CaptchaConfig (same file) | exact |
| `core/plugin_base.py` (place_order_guarded) | ABC concrete method | request-response | `core/plugin_base.py` _handle_ban / get_price (same file) | exact |
| `core/orchestrator.py` (monitor-only gate) | orchestrator gate | request-response | `core/orchestrator.py` `if auto_buy:` block L236 (same file) | exact |
| `core/cli/__init__.py` (--monitor-only flag) | CLI config | request-response | `core/cli/__init__.py` --auto-buy / --json flags (same file) | exact |
| `core/cli/run.py` (monitor_only mutation) | CLI handler | request-response | `core/cli/run.py` CFG.debug.test_mode read + needs_cvv gate (same file) | exact |
| `core/cli/config_cmd.py` (ALLOWLIST entry) | CLI config | transform | `core/cli/config_cmd.py` "test_mode" ALLOWLIST entry L18-20 (same file) | exact |
| `plugins/shopbot_plugin_amazon.py` | plugin reroute | request-response | `plugins/shopbot_plugin_amazon.py` L412-425 (same file, before state) | exact |
| `plugins/shopbot_plugin_bestbuy.py` | plugin reroute | request-response | `plugins/shopbot_plugin_bestbuy.py` L304-311 (same file, before state) | exact |
| `plugins/shopbot_plugin_walmart.py` | plugin reroute | request-response | `plugins/shopbot_plugin_bestbuy.py` L304-311 (BestBuy no-guard pattern) | role-match |
| `plugins/shopbot_plugin_target.py` | plugin reroute | request-response | `plugins/shopbot_plugin_bestbuy.py` L304-311 (BestBuy no-guard pattern) | role-match |
| `plugins/shopbot_plugin_gamestop.py` | plugin reroute | request-response | `plugins/shopbot_plugin_bestbuy.py` L304-311 (BestBuy no-guard pattern) | role-match |
| `plugins/shopbot_plugin_newegg.py` | plugin reroute | request-response | `plugins/shopbot_plugin_bestbuy.py` L304-311 (BestBuy no-guard pattern) | role-match |
| `plugins/shopbot_plugin_squareenix.py` | plugin reroute | request-response | `plugins/shopbot_plugin_bestbuy.py` L304-311 (BestBuy no-guard pattern) | role-match |
| `tests/test_safety_gate.py` (new) | test | event-driven | `tests/test_orchestrator.py` + `tests/test_plugin_base.py` | role-match |

## Pattern Assignments

### `core/config_schema.py` -- DebugConfig field addition

**Analog:** `core/config_schema.py` lines 61-64 (DebugConfig, existing)

**Existing DebugConfig** (lines 61-64):
```python
class DebugConfig(BaseModel):
    logging_level: int = 5
    test_mode: bool = True
```

**After change -- add one field:**
```python
class DebugConfig(BaseModel):
    logging_level: int = 5
    test_mode: bool = True
    monitor_only: bool = False   # NEW: BUY-01; default False per CONTEXT.md (not True)
```

**Key constraint:** Default is `False`, not `True`. RESEARCH.md Pitfall 6 documents a STATE.md inconsistency that says True -- CONTEXT.md wins; use `False`.

---

### `core/config_schema.py` -- CheckoutConfig new model

**Analog:** `core/config_schema.py` WalmartPlatformConfig + CaptchaConfig for Field(ge=) and enabled-by-default=False pattern.

**Field(ge=) analog** (lines 89-92, WalmartPlatformConfig):
```python
class WalmartPlatformConfig(BaseModel):
    min_delay: float = Field(default=8.0, ge=0.0)
    max_delay: float = Field(default=15.0, ge=0.0)
    headless: bool = True
    user_agents: list[str] = Field(default_factory=list)
```

**New CheckoutConfig to write** (place after CaptchaConfig class, before AppConfig):
```python
class CheckoutConfig(BaseModel):
    """Checkout timing and retry tuning. Consumed by Phases 21/22/24.

    All fields are numeric scalars with lower bounds (ge) only -- no @field_validator needed.
    """
    item_timeout_secs: int = Field(default=120, ge=1)
    step_timeout_secs: int = Field(default=30, ge=1)
    max_cart_retries: int = Field(default=3, ge=0)
    backoff_base: float = Field(default=2.0, ge=0.0)
    backoff_jitter: float = Field(default=0.5, ge=0.0)
    alert_on_errors: int = Field(default=3, ge=0)
```

Note: No `@field_validator` needed. ProxyConfig uses it for URL structure validation (complex). CheckoutConfig fields are all numeric scalars -- `Field(ge=N)` alone handles validation at model instantiation.

---

### `core/config_schema.py` -- AppConfig wiring

**Analog:** `core/config_schema.py` lines 280-281 (captcha field declaration):
```python
    proxy: ProxyConfig = ProxyConfig()
    captcha: CaptchaConfig = CaptchaConfig()
```

**After change -- insert checkout after captcha:**
```python
    proxy: ProxyConfig = ProxyConfig()
    captcha: CaptchaConfig = CaptchaConfig()
    checkout: CheckoutConfig = CheckoutConfig()   # NEW: placed after captcha (lines 281-282)
```

RESEARCH.md Pitfall 5: must be a declared class attribute or `extra="ignore"` silently drops YAML key.

---

### `core/plugin_base.py` -- place_order_guarded concrete method

**Analog:** `core/plugin_base.py` _handle_ban (lines 43-55) and get_price (lines 71-78) -- both are concrete non-abstract async methods that read `self.config` and use `getattr` for safety.

**_handle_ban pattern** (lines 43-55) -- concrete method, reads self attributes safely:
```python
def _handle_ban(self, body_text: str) -> bool:
    if not _is_ban_response(0, body_text):
        return False
    proxy = getattr(self, "_proxy", None)
    pool = getattr(self, "_pool", None)
    if proxy and pool:
        pool.record_failure(proxy)
    return True
```

**get_price pattern** (lines 71-78) -- concrete no-op with docstring noting PLUGIN_API_VERSION stays 2:
```python
async def get_price(self, url: str) -> int | None:
    """Return the current item price as integer cents, or None if unsupported.

    Default returns None (price monitoring unsupported for this plugin).
    PLUGIN_API_VERSION stays 2 -- additive non-abstract method (PRICE-02).
    Override in platform plugins that can scrape a live price.
    """
    return None
```

**New place_order_guarded to write** (insert after get_price, before login):
```python
async def place_order_guarded(self, click_fn) -> bool:
    """Invoke click_fn only when test_mode and monitor_only are both False.

    Returns True when the click fires, False when suppressed.
    Never raises. PLUGIN_API_VERSION stays 2 (additive concrete method, BUY-02).
    """
    debug = getattr(self.config, "debug", None) if self.config else None
    test_mode = getattr(debug, "test_mode", True)
    monitor_only = getattr(debug, "monitor_only", False)
    if test_mode or monitor_only:
        writeLog(
            "place-order suppressed (monitor_only/test_mode)",
            "INFO",
        )
        return False
    await click_fn()
    return True
```

**Import required:** `writeLog` is already imported at the top of plugin files that use it; `plugin_base.py` does NOT currently import `writeLog`. Add `from logger import writeLog` to `plugin_base.py` imports.

---

### `core/orchestrator.py` -- monitor-only gate in _check_and_buy

**Analog:** `core/orchestrator.py` lines 236-237 (the exact insertion point) plus the early-return guard pattern at lines 231-234:

**Existing early-return guard pattern** (lines 230-237):
```python
    elif not available and was_available:
        await write_queue.put(("clear_available", link))
        return
    elif not available:
        return

    if auto_buy:
        await _try_auto_buy(plugin, name, link, write_queue, dispatcher)
```

**After change -- insert monitor_only gate inside `if auto_buy:` block:**
```python
    if auto_buy:
        if plugin.config.debug.monitor_only:
            writeLog(
                f"[{plugin.__class__.__name__}] monitor-only: skipping auto_buy for {name}",
                "INFO",
            )
            return
        await _try_auto_buy(plugin, name, link, write_queue, dispatcher)
```

Gate placement constraint: the `if plugin.config.debug.monitor_only:` check goes INSIDE the `if auto_buy:` block so that the item name is in scope for the log message and stock-availability alerts (dispatched at lines 224-229) still fire before this point.

---

### `core/cli/__init__.py` -- --monitor-only flag on run subparser

**Analog:** `core/cli/__init__.py` --auto-buy flag (lines 76-79) and --json flag (lines 132-138) -- both use `action="store_true"`, `default=False`, `dest=` pattern.

**--auto-buy analog** (lines 76-79):
```python
    add_p.add_argument(
        "--auto-buy",
        action="store_true",
        default=False,
        help="Enable auto-buy when available.",
    )
```

**New argument to add on run_p** (insert after `run_p.set_defaults(func=handle_run)` at line 41):
```python
    run_p.add_argument(
        "--monitor-only",
        action="store_true",
        default=False,
        dest="monitor_only",
        help="Run in monitor-only mode: check availability and alert but never place orders.",
    )
```

`dest="monitor_only"` is needed because argparse converts `--monitor-only` to `monitor_only` automatically, but explicit `dest` makes the downstream `args.monitor_only` reference unambiguous.

---

### `core/cli/run.py` -- handle_run monitor_only mutation

**Analog:** `core/cli/run.py` lines 20-27 (existing cfg.debug.test_mode read + needs_cvv gate):

**Existing handle_run** (lines 11-38):
```python
def handle_run(args, svc) -> int:
    cfg = svc.get_config()
    needs_cvv = (
        not cfg.debug.test_mode
        and any(
            "bestbuy.com" in item.link and item.auto_buy
            for item in cfg.available.items
        )
    )
    cvv = None
    if needs_cvv:
        try:
            cvv = getpass.getpass("Enter CVV (input hidden): ").strip() or None
        except (EOFError, getpass.GetPassWarning):
            print(
                "WARNING: CVV echo suppression unavailable in this terminal",
                file=sys.stderr,
            )
            return 1
    svc.run(cvv)
    return 0
```

**After change -- mutate cfg before needs_cvv, add monitor_only to cvv gate:**
```python
def handle_run(args, svc) -> int:
    cfg = svc.get_config()
    if getattr(args, "monitor_only", False):
        cfg.debug.monitor_only = True
    needs_cvv = (
        not cfg.debug.test_mode
        and not cfg.debug.monitor_only   # monitor-only also skips CVV prompt
        and any(
            "bestbuy.com" in item.link and item.auto_buy
            for item in cfg.available.items
        )
    )
    # ... rest unchanged
```

Mutation pattern: `cfg.debug.monitor_only = True` is valid because `DebugConfig` is a plain `BaseModel` (mutable by default in Pydantic v2, no `model_config` frozen). Confirmed by existing `cfg.debug.test_mode` read pattern. `cfg` is the already-constructed `AppConfig` instance from `svc.get_config()` -- do NOT re-construct AppConfig.

---

### `core/cli/config_cmd.py` -- ALLOWLIST entry

**Analog:** `core/cli/config_cmd.py` lines 17-20 (existing ALLOWLIST with test_mode):

**Existing ALLOWLIST** (lines 17-20):
```python
ALLOWLIST: dict[str, tuple[str, type]] = {
    "test_mode": ("debug", bool),
    "logging_level": ("debug", int),
}
```

**After change -- add monitor_only entry:**
```python
ALLOWLIST: dict[str, tuple[str, type]] = {
    "test_mode": ("debug", bool),
    "logging_level": ("debug", int),
    "monitor_only": ("debug", bool),   # NEW: BUY-01; enables `shoppybot config set monitor_only true`
}
```

The tuple structure `(yaml_section, python_type)` is consumed verbatim by `handle_config_set` at line 89: `section, typ = ALLOWLIST[key]`. The bool coercion is already implemented in `_coerce` for `test_mode`; `monitor_only` reuses it.

---

### `plugins/shopbot_plugin_amazon.py` -- place_order_guarded reroute

**Analog:** Same file, lines 406-425 (before state -- the code being replaced).

**Before state** (lines 406-425):
```python
            writeLog("Attempting to find place order button", "INFO")
            place_order = await tab.select("#submitOrderButtonId", timeout=10)
            if not place_order:
                writeLog("Place order button not found", "ERROR")
                return False

            if not test_mode:
                await place_order.click()
                writeLog("Order placed on Amazon", "SUCCESS")
                return True
            else:
                writeLog(
                    "Test mode active: skipping submitOrderButton click",
                    "SUCCESS",
                )
                await self._wait_user_action(
                    self.test_pause_event,
                    "TEST MODE: order review complete. Press Enter to continue.",
                )
                return False
```

**After state -- replace lines 412-425 entirely:**
```python
            writeLog("Attempting to find place order button", "INFO")
            place_order = await tab.select("#submitOrderButtonId", timeout=10)
            if not place_order:
                writeLog("Place order button not found", "ERROR")
                return False

            return await self.place_order_guarded(place_order.click)
```

The `test_pause_event` wait at lines 421-425 is intentionally dropped. RESEARCH.md Pitfall 2 documents this explicitly: `place_order_guarded` replaces the ad-hoc gate entirely. The separate test-mode pause at lines 393-398 (before buy-now click) is NOT changed.

Also remove the now-unused `test_mode = self.config.debug.test_mode if self.config else True` line at L391 -- it is no longer referenced after replacing lines 412-425.

---

### `plugins/shopbot_plugin_bestbuy.py` -- place_order_guarded reroute

**Analog:** Same file, lines 304-311 (the confirmed no-guard gap, BUY-02).

**Before state** (lines 304-311):
```python
            place_order = await tab.select(".button--place-order", timeout=10)
            if not place_order:
                writeLog("Place order button not found", "ERROR")
                return False
            await place_order.click()
            writeLog("Order placed on BestBuy", "SUCCESS")
            # ASYNC-05: return True; orchestrator enqueues write_queue.put(url).
            return True
```

**After state -- replace lines 308-311:**
```python
            place_order = await tab.select(".button--place-order", timeout=10)
            if not place_order:
                writeLog("Place order button not found", "ERROR")
                return False
            return await self.place_order_guarded(place_order.click)
```

The `writeLog("Order placed on BestBuy", "SUCCESS")` and the hardcoded `return True` are both replaced. The guard returns True only when the click fires.

---

### `plugins/shopbot_plugin_walmart.py` -- place_order_guarded reroute

**Analog:** BestBuy no-guard pattern above. Trigger at lines 189-195.

**Selector:** `[data-testid="place-order-button"]` (line 189)

**Before state** (lines 189-195, reconstructed from RESEARCH):
```python
            place_order = await tab.select('[data-testid="place-order-button"]', timeout=10)
            if not place_order:
                writeLog("Place order button not found", "ERROR")
                return False
            await place_order.click()
            # ...
            return True
```

**After state:**
```python
            place_order = await tab.select('[data-testid="place-order-button"]', timeout=10)
            if not place_order:
                writeLog("Place order button not found", "ERROR")
                return False
            return await self.place_order_guarded(place_order.click)
```

---

### `plugins/shopbot_plugin_target.py` -- place_order_guarded reroute

**Analog:** BestBuy no-guard pattern. Trigger at lines 191-198.

**Selector:** `[data-test="placeOrder"]` (line 191)

Replace `await place_order.click()` (line 195) and the following `return True` (line 197) with `return await self.place_order_guarded(place_order.click)`.

---

### `plugins/shopbot_plugin_gamestop.py` -- place_order_guarded reroute

**Analog:** BestBuy no-guard pattern. Trigger at lines 190-199.

**Selector:** `button.place-order` (line 192)

Replace `await place_order.click()` (line 196) and the following `return True` (line 198) with `return await self.place_order_guarded(place_order.click)`.

---

### `plugins/shopbot_plugin_newegg.py` -- place_order_guarded reroute

**Analog:** BestBuy no-guard pattern. Trigger at lines 205-215.

**Selectors:** `.btn-primary.btn-wide` first, then text-find "Place Order" (lines 206-208)

Replace `await place_order.click()` (line 212) and the following `return True` (line 214) with `return await self.place_order_guarded(place_order.click)`.

---

### `plugins/shopbot_plugin_squareenix.py` -- place_order_guarded reroute

**Analog:** BestBuy no-guard pattern. Trigger at lines 196-206.

**Selectors:** `[data-testid="place-order-button"]` first, then text-find "Place Order" (lines 197-199)

Replace `await place_order.click()` (line 203) and the following `return True` (line 205) with `return await self.place_order_guarded(place_order.click)`.

---

### `tests/test_safety_gate.py` -- new test file

**Analog:** `tests/test_orchestrator.py` (asyncio, write_queue mock, fake_plugin fixture) + `tests/test_plugin_base.py` (MinimalPlugin stub, sync and async tests).

**Imports pattern** (from test_orchestrator.py lines 1-21):
```python
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from core.orchestrator import _check_and_buy
```

**fake_plugin fixture usage** (from tests/conftest.py lines 124-153):
```python
# conftest.py provides fake_plugin as a factory fixture:
def _build(domains=None, available=True, bought=False, config=None):
    class _FakePlugin(RetailerPlugin):
        domain_patterns = domains or ["fake.example.com"]
        async def check_availability(self, url: str) -> bool: return available
        async def auto_buy(self, url: str) -> bool: return bought
    instance = _FakePlugin(config=config)
    instance.setup = AsyncMock()
    instance.teardown = AsyncMock()
    return instance
```

**write_queue mock pattern** (from test_orchestrator.py context):
```python
write_queue = asyncio.Queue()
# ... run _check_and_buy or auto_buy ...
assert write_queue.empty(), "No purchase writes expected"
# OR: assert not any(item[0] == "purchased" for item in list(write_queue._queue))
```

**MinimalPlugin stub pattern** (from tests/test_plugin_base.py lines 13-23):
```python
class MinimalPlugin(RetailerPlugin):
    domain_patterns = ["example.com"]
    async def check_availability(self, url: str) -> bool: return True
    async def auto_buy(self, url: str) -> bool: return False
```

**Async test structure** (asyncio_mode=auto; no `@pytest.mark.asyncio` decorator needed):
```python
async def test_place_order_guarded_suppressed_test_mode():
    """place_order_guarded returns False + does not call click_fn when test_mode=True."""
    cfg = MagicMock()
    cfg.debug.test_mode = True
    cfg.debug.monitor_only = False
    plugin = MinimalPlugin(config=cfg)
    click_fn = AsyncMock()

    result = await plugin.place_order_guarded(click_fn)

    assert result is False
    click_fn.assert_not_called()
```

**7-plugin monitor_only CI test sketch:**
```python
async def test_all_plugins_monitor_only_no_purchase_write(fake_plugin):
    """BUY-02: all 7 plugins with monitor_only=True produce zero purchase-queue writes."""
    write_queue = asyncio.Queue()
    cfg = MagicMock()
    cfg.debug.monitor_only = True
    cfg.debug.test_mode = False   # isolate monitor_only gate
    cfg.available.items = []

    plugin = fake_plugin(domains=["fake.example.com"], available=True, bought=True, config=cfg)
    await _check_and_buy(plugin, "Item", "https://fake.example.com/item", True, write_queue)

    # No ("purchased", ...) tuple should be in the queue
    items = []
    while not write_queue.empty():
        items.append(write_queue.get_nowait())
    assert not any(isinstance(i, tuple) and i[0] == "purchased" for i in items)
```

Note: The full 7-plugin integration test must load real plugin classes via importlib and attach a fake_browser. The sketch above uses fake_plugin for the orchestrator gate; a separate test should load real plugin classes to verify the BUY-02 `place_order_guarded` call site.

---

## Shared Patterns

### writeLog call style
**Source:** `core/orchestrator.py` (all existing writeLog calls), `plugins/shopbot_plugin_amazon.py`
**Apply to:** `place_order_guarded()` in plugin_base.py, monitor-only gate log in orchestrator.py

```python
# Two-arg form: writeLog(message_str, level_str)
writeLog(f"[{plugin.__class__.__name__}] monitor-only: skipping auto_buy for {name}", "INFO")
writeLog("place-order suppressed (monitor_only/test_mode)", "INFO")
```

### getattr safety for optional config attributes
**Source:** `core/plugin_base.py` _handle_ban (lines 50-53) and place_order_guarded design
**Apply to:** `place_order_guarded()` implementation

```python
debug = getattr(self.config, "debug", None) if self.config else None
test_mode = getattr(debug, "test_mode", True)    # safe default: True = suppressed
monitor_only = getattr(debug, "monitor_only", False)  # safe default: False = not suppressed
```

### Pydantic v2 Field(ge=) numeric bounds
**Source:** `core/config_schema.py` WalmartPlatformConfig (lines 89-92)
**Apply to:** All CheckoutConfig fields

```python
min_delay: float = Field(default=8.0, ge=0.0)
max_delay: float = Field(default=15.0, ge=0.0)
```

### ALLOWLIST tuple: (yaml_section, python_type)
**Source:** `core/cli/config_cmd.py` lines 17-20
**Apply to:** monitor_only ALLOWLIST entry

```python
"test_mode": ("debug", bool),    # exact pattern to copy for monitor_only
```

### AppConfig default-instance field declaration
**Source:** `core/config_schema.py` lines 273-281
**Apply to:** `checkout: CheckoutConfig = CheckoutConfig()` in AppConfig

```python
    proxy: ProxyConfig = ProxyConfig()
    captcha: CaptchaConfig = CaptchaConfig()
    # Insert: checkout: CheckoutConfig = CheckoutConfig()
```

## No Analog Found

All files have strong analogs. No entries.

## Per-Plugin Reroute Summary Table

| Plugin | File | Method | Trigger Lines | Selector | Before | After |
|--------|------|--------|---------------|----------|--------|-------|
| Amazon | shopbot_plugin_amazon.py | auto_buy L357 | L406-425 | `#submitOrderButtonId` | if/else test_mode block L412-425 | `return await self.place_order_guarded(place_order.click)` |
| BestBuy | shopbot_plugin_bestbuy.py | auto_buy L249 | L304-311 | `.button--place-order` | `await place_order.click(); return True` L308-311 | `return await self.place_order_guarded(place_order.click)` |
| Walmart | shopbot_plugin_walmart.py | auto_buy L148 | L189-195 | `[data-testid="place-order-button"]` | `await place_order.click(); return True` L192+195 | same reroute |
| Target | shopbot_plugin_target.py | auto_buy L150 | L191-198 | `[data-test="placeOrder"]` | `await place_order.click(); return True` L195+197 | same reroute |
| GameStop | shopbot_plugin_gamestop.py | auto_buy L150 | L190-199 | `button.place-order` | `await place_order.click(); return True` L196+198 | same reroute |
| Newegg | shopbot_plugin_newegg.py | auto_buy L163 | L205-215 | `.btn-primary.btn-wide` / "Place Order" | `await place_order.click(); return True` L212+214 | same reroute |
| SquareEnix | shopbot_plugin_squareenix.py | auto_buy L154 | L196-206 | `[data-testid="place-order-button"]` / "Place Order" | `await place_order.click(); return True` L203+205 | same reroute |

## Critical Pitfall Index (from RESEARCH.md)

| # | File | What to Avoid |
|---|------|---------------|
| P1 | plugin_base.py | `place_order_guarded` MUST be `async def`; all click_fns are async coroutines |
| P2 | shopbot_plugin_amazon.py | Drop lines 412-425 entirely including test_pause_event wait -- do NOT preserve it |
| P3 | core/cli/run.py | DebugConfig is mutable BaseModel; `cfg.debug.monitor_only = True` is valid direct assignment |
| P4 | tests/test_safety_gate.py | Mock `write_queue` as asyncio.Queue; assert no `("purchased", ...)` tuples enqueued |
| P5 | core/config_schema.py | `checkout` MUST be a declared class attribute in AppConfig or YAML key is silently ignored |
| P6 | core/config_schema.py | `monitor_only: bool = False` -- NOT True; CONTEXT.md overrides STATE.md on this |
| P7 | core/cli/config_cmd.py | Add `"monitor_only": ("debug", bool)` to ALLOWLIST or `config set monitor_only` fails |

## Metadata

**Analog search scope:** core/, plugins/, tests/
**Files read directly:** core/plugin_base.py, core/config_schema.py, core/orchestrator.py, core/cli/__init__.py, core/cli/run.py, core/cli/config_cmd.py, plugins/shopbot_plugin_amazon.py (L350-428), plugins/shopbot_plugin_bestbuy.py (L295-314), tests/conftest.py, tests/test_orchestrator.py (L1-80), tests/test_plugin_base.py
**Pattern extraction date:** 2026-06-11
