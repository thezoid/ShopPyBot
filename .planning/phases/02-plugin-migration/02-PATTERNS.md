# Phase 2: Plugin Migration - Pattern Map

**Mapped:** 2026-06-02
**Files analyzed:** 9 new/modified files
**Analogs found:** 8 / 9

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `core/plugin_base.py` | ABC / base class | — (interface definition) | `core/plugin_base.py` (v1, in place) | self — revise in place |
| `core/registry.py` | service / orchestrator | request-response | `main.py` routing block (lines 131-194) | partial — same routing logic, no exact analog |
| `plugins/shopbot_plugin_amazon.py` | plugin / service | request-response | `amazon_bot.py` | exact |
| `plugins/shopbot_plugin_bestbuy.py` | plugin / service | request-response | `bestbuy_bot.py` | exact |
| `plugins/example_plugin.py` | plugin / utility | request-response | `amazon_bot.py` (structure) + `bestbuy_bot.py` | role-match (simplified stub) |
| `plugins/PLUGIN_DEV.md` | documentation | — | none (new doc) | no analog |
| `main.py` | entry point | event-driven loop | `main.py` (current, in place) | self — revise in place |
| `tests/test_plugin_base.py` | test | — | `tests/test_config_schema.py` (pattern) | role-match |
| `tests/test_registry.py` | test | — | `tests/test_config_schema.py` | role-match |

## Pattern Assignments

### `core/plugin_base.py` (ABC revision, v1 to v2)

**Analog:** `core/plugin_base.py` lines 1-30 (full file — revise in place)

**Current state to replace** (`core/plugin_base.py` lines 1-30):
```python
from abc import ABC, abstractmethod

PLUGIN_API_VERSION = 1

class RetailerPlugin(ABC):
    @abstractmethod
    def check_availability(self, url: str) -> bool: ...

    @abstractmethod
    def auto_buy(self, driver, url: str, config: dict) -> bool: ...

    def login(self, driver, config: dict) -> None:
        return None

    def detect_captcha(self, driver) -> bool:
        return False
```

**Target shape** (D-07, verbatim contract — implement exactly this):
```python
from abc import ABC, abstractmethod

PLUGIN_API_VERSION = 2  # bumped from 1; v1 subclasses are not compatible

class RetailerPlugin(ABC):
    """Base class for all retail platform plugins.

    Concrete plugins must implement check_availability and auto_buy.
    All other methods have working no-op defaults.
    """

    domain_patterns: list[str]  # class attribute; registry reads before __init__

    def __init__(self, config) -> None:
        self.config = config   # typed AppConfig passed by registry
        self.driver = None     # set by setup(); never in __init__ (nodriver constraint)

    async def setup(self) -> None:
        """Build the nodriver Browser. Registry awaits this after construction."""
        ...

    @abstractmethod
    async def check_availability(self, url: str) -> bool:
        """Return True if the item at url is in stock and purchasable."""
        ...

    @abstractmethod
    async def auto_buy(self, url: str) -> bool:
        """Attempt to purchase the item at url. Return True on success."""
        ...

    async def login(self) -> None:
        """Authenticate with the retail platform. No-op default."""
        return None

    async def detect_captcha(self) -> bool:
        """Return True if a CAPTCHA is present. No-op default."""
        return False

    async def teardown(self) -> None:
        """Close the browser. Registry calls at shutdown."""
        ...
```

**Key delta from v1:**
- `PLUGIN_API_VERSION` 1 to 2
- All abstract/default methods are now `async def`
- `driver` and `config` removed from method signatures (use `self.driver`, `self.config`)
- `__init__(self, config)` added
- `setup()` and `teardown()` added
- `domain_patterns: list[str]` class annotation added

---

### `core/registry.py` (new service, request-response)

**Analog:** `main.py` routing block (lines 131-194) for the routing logic; no analog for importlib discovery.

**Imports pattern** (model from `main.py` lines 1-18 and `core/config_schema.py` lines 1-13):
```python
import importlib.util
import inspect
from pathlib import Path
from urllib.parse import urlparse

from core.plugin_base import RetailerPlugin
from logger import writeLog
```

**Discovery pattern** (from RESEARCH.md Pattern 8 — use verbatim):
```python
def _discover_plugins(plugins_dir: Path) -> list[type[RetailerPlugin]]:
    found = []
    for path in plugins_dir.iterdir():
        if path.suffix != ".py":
            continue
        if not path.name.startswith("shopbot_plugin_"):
            writeLog(
                f"plugins/{path.name} does not match shopbot_plugin_*.py -- ignoring",
                "WARNING",
            )
            continue
        try:
            spec = importlib.util.spec_from_file_location(path.stem, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception as exc:
            writeLog(f"Failed to import {path.name}: {exc} -- skipping", "WARNING")
            continue
        for _name, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, RetailerPlugin) and obj is not RetailerPlugin:
                found.append(obj)
    return found
```

**URL routing pattern** (from `main.py` lines 138-160 — formalized version):
```python
def _route(self, url: str) -> RetailerPlugin | None:
    host = urlparse(url).hostname or ""
    for plugin in self._active_plugins:
        if any(p in host for p in plugin.domain_patterns):
            return plugin
    return None
```
This replaces `if "amazon.com" in link: ... elif "bestbuy.com" in link:` (main.py lines 138, 160).

**Lifecycle pattern** (from RESEARCH.md Pattern 9 and D-09):
```python
class PluginRegistry:
    def __init__(self, config, plugins_dir: Path) -> None:
        plugin_classes = _discover_plugins(plugins_dir)
        # Eagerly construct all plugins (cheap; reads domain_patterns for routing)
        self._all_plugins: list[RetailerPlugin] = [cls(config) for cls in plugin_classes]
        self._active_plugins: list[RetailerPlugin] = []

    async def setup_for_items(self, items) -> None:
        """Launch browser only for plugins with at least one matching item (D-09)."""
        needed: set[RetailerPlugin] = set()
        for item in items:
            plugin = self._route_class(item[1])  # route by link before active list exists
            if plugin:
                needed.add(plugin)
        for plugin in needed:
            try:
                await plugin.setup()
                self._active_plugins.append(plugin)
            except Exception as exc:
                writeLog(f"Plugin setup failed: {exc} -- skipping", "WARNING")

    async def teardown_all(self) -> None:
        for plugin in self._active_plugins:
            try:
                await plugin.teardown()
            except Exception as exc:
                writeLog(f"Plugin teardown error: {exc}", "WARNING")
```

**Error handling pattern:** Match `main.py` style — `writeLog(..., "WARNING")` for non-fatal, `writeLog(..., "ERROR")` for errors; never crash the bot on single plugin failure (log + skip).

---

### `plugins/shopbot_plugin_amazon.py` (plugin, request-response)

**Analog:** `amazon_bot.py` (entire file, 192 lines) — port all functions as methods of `AmazonPlugin(RetailerPlugin)`.

**Imports pattern** (from `amazon_bot.py` lines 1-8, translated to nodriver):
```python
import nodriver
from logger import writeLog
from models import update_item_purchased
from utils import play_notification_sound
from core.plugin_base import RetailerPlugin
```
Remove: `from selenium import webdriver`, `By`, `WebDriverWait`, `expected_conditions`, `time`.

**Class header and setup** (D-04, D-06, RESEARCH.md Pattern 1):
```python
class AmazonPlugin(RetailerPlugin):
    domain_patterns = ["amazon.com", "amazon.co.uk", "amazon.ca"]

    async def setup(self) -> None:
        # nodriver.start() MUST be awaited inside async context -- never in __init__
        # (Browser.__init__ raises RuntimeError if no running event loop)
        self.driver = await nodriver.start(headless=False)

    async def teardown(self) -> None:
        if self.driver:
            self.driver.stop()   # sync method; handles subprocess termination
            self.driver = None
```

**check_availability pattern** (from `amazon_bot.py::check_amazon_item` lines 19-54, translated):
```python
async def check_availability(self, url: str) -> bool:
    writeLog(f"Checking Amazon availability: {url}", "DEBUG")
    try:
        tab = await self.driver.get(url)
        captcha_present = await self.detect_captcha()
        if captcha_present:
            writeLog("CAPTCHA detected. Please solve it manually.", "WARNING")
            play_notification_sound()
            input("Press Enter after solving the CAPTCHA...")   # blocks; acceptable for Phase 2 sequential loop

        writeLog("Waiting for add-to-cart or buy-now button", "DEBUG")
        add_to_cart = await tab.select("#add-to-cart-button", timeout=10)
        buy_now = await tab.select("#buy-now-button", timeout=10)

        if add_to_cart or buy_now:
            writeLog("Item is available on Amazon", "SUCCESS")
            return True
        writeLog("Item is not available on Amazon", "INFO")
        return False
    except Exception as exc:
        writeLog(f"Error checking Amazon item: {exc}", "ERROR")
        return False
```

**detect_captcha pattern** (from `amazon_bot.py::detect_captcha` lines 10-17, translated — RESEARCH.md Pattern 6):
```python
async def detect_captcha(self) -> bool:
    tab = self.driver.main_tab
    element = await tab.find(
        "Enter the characters you see below",
        best_match=False,
        timeout=3,   # short: absence is the common case
    )
    return element is not None
```
Replace: `try: WebDriverWait(...).until(...); return True; except: return False`

**login pattern** (from `amazon_bot.py::amz_sign_in` lines 56-121, translated):
```python
async def login(self) -> None:
    email = self.config.platforms.amazon  # no email on AppConfig; read from env
    # SEC-01: credentials from env vars only
    import os
    email = os.environ.get("AMZ_EMAIL", "")
    password = os.environ.get("AMZ_PASSWORD", "")
    # ... navigate to sign-in URL, select("#ap_email"), send_keys, etc.
    # Selector mapping: By.ID "ap_email" -> "#ap_email"
    #                   By.ID "ap_password" -> "#ap_password"
    #                   By.ID "signInSubmit" -> "#signInSubmit"
    #                   By.ID "auth-mfa-form" -> "#auth-mfa-form"
```

**auto_buy pattern** (from `amazon_bot.py::auto_buy_amazon_item` lines 123-192, translated):
```python
async def auto_buy(self, url: str) -> bool:
    writeLog(f"Entering auto_buy for Amazon: {url}", "DEBUG")
    await self.login()
    try:
        tab = await self.driver.get(url)

        qty_dropdown = await tab.select(".a-button-dropdown", timeout=10)
        if not qty_dropdown:
            writeLog("Quantity dropdown not found", "ERROR")
            return False
        await qty_dropdown.click()

        qty = self.config.available.items[0].quantity  # registry must pass item quantity
        qty_option = await tab.select(f"#quantity_{qty - 1}", timeout=10)
        if not qty_option:
            writeLog(f"Quantity option {qty} not found", "ERROR")
            return False
        await qty_option.click()

        if self.config.debug.test_mode:
            writeLog("Test mode: pausing before buy-now", "DEBUG")
            input("Press Enter to continue...")

        buy_now = await tab.select("#buy-now-button", timeout=10)
        if not buy_now:
            writeLog("Buy-now button not found", "ERROR")
            return False
        await buy_now.click()

        place_order = await tab.select("#submitOrderButtonId", timeout=10)
        if not place_order:
            writeLog("Place order button not found", "ERROR")
            return False

        if not self.config.debug.test_mode:
            await place_order.click()
            writeLog("Order placed on Amazon", "SUCCESS")
            update_item_purchased(url)
            return True
        else:
            writeLog("Test mode: skipping submitOrderButton click", "SUCCESS")
            input("Press Enter to continue...")
            return False
    except Exception as exc:
        writeLog(f"Error during Amazon auto-buy: {exc}", "ERROR")
        return False
```

**Critical guard pattern** — always check None before calling methods (RESEARCH.md Pitfall 2):
```python
# WRONG (crashes with AttributeError on NoneType):
element = await tab.select("#foo")
await element.click()

# CORRECT:
element = await tab.select("#foo", timeout=10)
if not element:
    writeLog("Element #foo not found", "ERROR")
    return False
await element.click()
```

---

### `plugins/shopbot_plugin_bestbuy.py` (plugin, request-response)

**Analog:** `bestbuy_bot.py` (entire file, 73 lines) — same translation pattern as Amazon.

**Imports pattern** (from `bestbuy_bot.py` lines 1-6, translated):
```python
import os
import nodriver
from logger import writeLog
from models import update_item_purchased
from core.plugin_base import RetailerPlugin
```

**Class header and setup:**
```python
class BestBuyPlugin(RetailerPlugin):
    domain_patterns = ["bestbuy.com"]

    async def setup(self) -> None:
        self.driver = await nodriver.start(headless=False)

    async def teardown(self) -> None:
        if self.driver:
            self.driver.stop()
            self.driver = None
```

**check_availability pattern** (from `bestbuy_bot.py::check_bestbuy_item` lines 7-25, translated):
```python
async def check_availability(self, url: str) -> bool:
    writeLog(f"Checking BestBuy availability: {url}", "DEBUG")
    try:
        tab = await self.driver.get(url)
        writeLog("Waiting for add-to-cart button", "DEBUG")
        add_to_cart = await tab.select(".add-to-cart-button", timeout=10)
        if add_to_cart:
            writeLog("Item is available on BestBuy", "SUCCESS")
            return True
        writeLog("Item is not available on BestBuy", "INFO")
        return False
    except Exception as exc:
        writeLog(f"Error checking BestBuy item: {exc}", "ERROR")
        return False
```

**login pattern** (from `bestbuy_bot.py::bb_sign_in` lines 27-38, translated):
```python
async def login(self) -> None:
    # SEC-01: credentials from env vars only
    email = os.environ.get("BB_EMAIL", "")
    password = os.environ.get("BB_PASSWORD", "")
    if not email or not password:
        writeLog("BB_EMAIL or BB_PASSWORD not set", "ERROR")
        return
    tab = await self.driver.get("https://www.bestbuy.com/identity/signin")
    email_field = await tab.select("#fld-e", timeout=10)
    if email_field:
        await email_field.send_keys(email)
    pwd_field = await tab.select("#fld-p1", timeout=10)
    if pwd_field:
        await pwd_field.send_keys(password)
    submit = await tab.select(".cia-form__controls__submit", timeout=10)
    if submit:
        await submit.click()
    writeLog("Signed in to BestBuy", "INFO")
```

**auto_buy pattern** (from `bestbuy_bot.py::auto_buy_bestbuy_item` lines 40-73, translated — PLG-02 fix included):
```python
async def auto_buy(self, url: str) -> bool:
    writeLog(f"Entering auto_buy for BestBuy: {url}", "DEBUG")
    try:
        tab = await self.driver.get(url)
        add_to_cart = await tab.select(".add-to-cart-button", timeout=10)
        if not add_to_cart:
            writeLog("Add-to-cart button not found", "ERROR")
            return False
        await add_to_cart.click()
        writeLog("Added to cart on BestBuy", "INFO")

        tab = await self.driver.get("https://www.bestbuy.com/cart")

        qty_dropdown = await tab.select(".a-dropdown-prompt", timeout=10)
        # TODO: verify ".a-dropdown-prompt" is correct for BestBuy cart (suspicious Amazon-prefix class)
        if qty_dropdown:
            await qty_dropdown.click()

        # Selector from bestbuy_bot.py line 57-60: By.XPATH f"//a[@id='quantity_{quantity}']"
        qty = self.config.available.items[0].quantity  # registry must pass item quantity
        qty_option = await tab.select(f"#quantity_{qty}", timeout=10)
        if qty_option:
            await qty_option.click()

        checkout = await tab.select(".checkout-buttons__checkout", timeout=10)
        if not checkout:
            writeLog("Checkout button not found", "ERROR")
            return False
        await checkout.click()
        writeLog("Proceeded to checkout on BestBuy", "INFO")

        await self.login()

        cvv_field = await tab.select("#credit-card-cvv", timeout=10)
        if cvv_field and self._cvv:
            await cvv_field.send_keys(self._cvv)

        place_order = await tab.select(".button--place-order", timeout=10)
        if not place_order:
            writeLog("Place order button not found", "ERROR")
            return False
        await place_order.click()
        writeLog("Order placed on BestBuy", "SUCCESS")

        # PLG-02 FIX: call update_item_purchased -- was missing in bestbuy_bot.py line 71
        update_item_purchased(url)
        return True
    except Exception as exc:
        writeLog(f"Error during BestBuy auto-buy: {exc}", "ERROR")
        return False
```

**PLG-02 bug location (confirmed):** `bestbuy_bot.py` line 71 — after `writeLog("Order placed on BestBuy", "SUCCESS")` there is no `update_item_purchased()` call. The port MUST add it immediately after the place-order click log.

---

### `plugins/example_plugin.py` (plugin stub, request-response)

**Analog:** `amazon_bot.py` / `bestbuy_bot.py` (structural pattern only — use fictional retailer)

**Required structure** (RESEARCH.md Contributor Tooling section):
```python
import nodriver
from core.plugin_base import RetailerPlugin
from models import update_item_purchased
from logger import writeLog


class FakeShopPlugin(RetailerPlugin):
    """Example plugin for a fictional retailer. Copy this file as your starting point."""

    # domain_patterns: list of substrings matched against urlparse(url).hostname
    # Add more entries for multi-region domains, e.g. ["fakeshop.com", "fakeshop.co.uk"]
    domain_patterns = ["fakeshop.com"]

    async def setup(self) -> None:
        # Start an isolated Chrome process for this plugin.
        # nodriver.start() MUST be called from async context -- never in __init__.
        self.driver = await nodriver.start(headless=False)

    async def check_availability(self, url: str) -> bool:
        tab = await self.driver.get(url)
        # Replace "#add-to-cart" with the real CSS selector for this retailer's button.
        # tab.select() returns None if not found within timeout -- never raises.
        element = await tab.select("#add-to-cart", timeout=10)
        return element is not None

    async def auto_buy(self, url: str) -> bool:
        try:
            tab = await self.driver.get(url)
            # Step 1: Add to cart
            add_btn = await tab.select("#add-to-cart", timeout=10)
            if not add_btn:
                return False
            await add_btn.click()

            # Step 2: Navigate to checkout
            tab = await self.driver.get("https://www.fakeshop.com/checkout")

            # Step 3: Place order
            place_btn = await tab.select("#place-order", timeout=10)
            if not place_btn:
                return False
            await place_btn.click()

            writeLog("Order placed on FakeShop", "SUCCESS")
            # Always call update_item_purchased after a successful purchase.
            update_item_purchased(url)
            return True
        except Exception as exc:
            writeLog(f"FakeShop auto_buy error: {exc}", "ERROR")
            return False

    async def teardown(self) -> None:
        if self.driver:
            self.driver.stop()
            self.driver = None
```

---

### `main.py` (async entry point revision)

**Analog:** `main.py` (in place) — preserve everything except Selenium driver setup and sync loop.

**Imports to remove** (lines 7-10 and 12-13):
```python
# REMOVE these imports:
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from amazon_bot import check_amazon_item, auto_buy_amazon_item, detect_captcha
from bestbuy_bot import check_bestbuy_item, auto_buy_bestbuy_item
```

**Imports to add:**
```python
import asyncio
from pathlib import Path
from core.registry import PluginRegistry
```

**Preserve as-is** (lines 40-49):
```python
def collect_cvv():
    """Collect CVV via hidden input at runtime. Never echoes or stores to disk (SEC-02)."""
    try:
        cvv = getpass.getpass("Enter CVV (input hidden): ").strip()
    except getpass.GetPassWarning:
        print("WARNING: CVV echo suppression unavailable in this terminal", file=sys.stderr)
        raise SystemExit("Cannot collect CVV securely. Run in an interactive terminal.")
    if not cvv:
        raise SystemExit("CVV is required for auto-buy. Exiting.")
    return cvv
```

**Preserve config validation and CVV gate** (lines 55-129 pattern — keep sync, before asyncio.run):
```python
def main():
    # Sync pre-flight: config validation + credential collection run before event loop
    try:
        cfg = AppConfig()
    except ValidationError as e:
        print(f"Configuration error -- fix config.yml:\n{e}")
        raise SystemExit(1)

    # initialize DB (sync, keep before loop)
    initialize_db()
    items = [(i.name, i.link, i.auto_buy, i.quantity, False) for i in cfg.available.items]
    add_items(items)

    # CVV gate: sync + blocking; must stay outside asyncio.run() (D-03 note)
    needs_bb_autobuy = (
        not cfg.debug.test_mode
        and any("bestbuy.com" in i.link and i.auto_buy for i in cfg.available.items)
    )
    cvv = collect_cvv() if needs_bb_autobuy else None

    asyncio.run(async_main(cfg, cvv))
```

**Remove entirely** (lines 62-106): `get_chromedriver_path()`, Chrome `Options` setup, `Service` setup, `driver = webdriver.Chrome(...)`, and the CDP `navigator.webdriver` patch block.

**New async_main structure** (from RESEARCH.md Pattern 9):
```python
async def async_main(cfg, cvv) -> None:
    plugins_dir = Path(__file__).parent / "plugins"
    registry = PluginRegistry(cfg, plugins_dir)
    items = get_items()
    await registry.setup_for_items(items)
    try:
        while True:
            writeLog("Starting new iteration of item checks", "INFO")
            for item in get_items():
                name, link, auto_buy, quantity, purchased = item
                if purchased:
                    writeLog(f"{name} has already been purchased", "INFO")
                    continue
                plugin = registry.route(link)
                if not plugin:
                    writeLog(f"No plugin for URL: {link}", "WARNING")
                    continue
                available = await plugin.check_availability(link)
                if available:
                    play_available_sound()
                    writeLog(f"{name} is available", "SUCCESS")
                    if auto_buy:
                        success = await plugin.auto_buy(link)
                        if success:
                            play_buy_sound()
    except KeyboardInterrupt:
        pass
    finally:
        await registry.teardown_all()
```

---

### `tests/test_plugin_base.py` (test rewrite)

**Analog:** `tests/test_plugin_base.py` (current file, rewrite) + `tests/test_config_schema.py` (pytest patterns, lines 1-61)

**Import pattern** (from `tests/test_config_schema.py` lines 1-8 and `tests/test_plugin_base.py` lines 1-3):
```python
import pytest
from core.plugin_base import RetailerPlugin, PLUGIN_API_VERSION
```

**Version assertion to update** (from `tests/test_plugin_base.py` line 6):
```python
# OLD (must update):
def test_version_constant():
    assert PLUGIN_API_VERSION == 1

# NEW:
def test_version_constant():
    assert PLUGIN_API_VERSION == 2
```

**Async stub pattern** (replaces sync `Minimal` class in `tests/test_plugin_base.py` lines 25-33):
```python
class MinimalPlugin(RetailerPlugin):
    domain_patterns = ["example.com"]

    async def check_availability(self, url: str) -> bool:
        return True

    async def auto_buy(self, url: str) -> bool:
        return False
```

**Async test pattern** (for methods requiring `pytest-asyncio`):
```python
@pytest.mark.asyncio
async def test_login_noop():
    p = MinimalPlugin(config=None)
    result = await p.login()
    assert result is None

@pytest.mark.asyncio
async def test_detect_captcha_noop():
    p = MinimalPlugin(config=None)
    result = await p.detect_captcha()
    assert result is False
```

**Sync tests that remain sync** (ABC enforcement, no async needed):
```python
def test_incomplete_plugin_raises():
    class Incomplete(RetailerPlugin):
        pass
    with pytest.raises(TypeError):
        Incomplete(config=None)

def test_abstract_methods_enforced():
    class MissingBuy(RetailerPlugin):
        domain_patterns = ["x.com"]
        async def check_availability(self, url): return True
    with pytest.raises(TypeError):
        MissingBuy(config=None)
```

**pytest-asyncio smoke test** (run first in Wave 0 per RESEARCH.md Pitfall 5):
```python
@pytest.mark.asyncio
async def test_asyncio_smoke():
    pass  # If this fails, add asyncio_mode = "auto" to pyproject.toml
```

---

### `tests/test_registry.py` (new test file)

**Analog:** `tests/test_config_schema.py` (lines 1-61) for pytest fixture + tmp_path pattern.

**Imports and fixture pattern** (from `tests/conftest.py` lines 1-27 and `tests/test_config_schema.py`):
```python
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from core.plugin_base import RetailerPlugin
from core.registry import PluginRegistry
```

**tmp plugin directory fixture** (analogous to `conftest.py::tmp_config_yml` pattern):
```python
@pytest.fixture
def tmp_plugins_dir(tmp_path):
    """Return a plugins dir with one valid shopbot_plugin_*.py file."""
    plugin_code = '''
from core.plugin_base import RetailerPlugin
class FakePlugin(RetailerPlugin):
    domain_patterns = ["fake.com"]
    async def check_availability(self, url): return True
    async def auto_buy(self, url): return False
'''
    (tmp_path / "shopbot_plugin_fake.py").write_text(plugin_code)
    return tmp_path
```

**Non-matching file warning test** (CORE-03):
```python
def test_non_matching_py_warns(tmp_path, caplog):
    (tmp_path / "helper.py").write_text("# not a plugin")
    # registry construction triggers discovery; no plugins found, warning logged
    registry = PluginRegistry(config=None, plugins_dir=tmp_path)
    assert "does not match shopbot_plugin_*.py" in caplog.text
```

**Valid plugin discovery test** (CORE-03):
```python
def test_discovers_valid_plugin(tmp_plugins_dir):
    registry = PluginRegistry(config=None, plugins_dir=tmp_plugins_dir)
    assert len(registry._all_plugins) == 1
```

**Route by domain test** (CORE-04):
```python
def test_route_by_domain(tmp_plugins_dir):
    registry = PluginRegistry(config=None, plugins_dir=tmp_plugins_dir)
    registry._active_plugins = registry._all_plugins  # simulate setup done
    plugin = registry.route("https://www.fake.com/product/123")
    assert plugin is not None
    assert "fake.com" in plugin.domain_patterns
```

---

## Shared Patterns

### writeLog (logging)

**Source:** `logger.py` lines 26-47
**Apply to:** All plugin files, registry, revised main.py

```python
from logger import writeLog

# Level mapping: ALWAYS=0, ERROR=1, WARNING=2, SUCCESS=2, INFO=3, DEBUG=4, TRACE=5
writeLog("message", "INFO")     # operational messages
writeLog("message", "DEBUG")    # method entry / timing
writeLog("message", "ERROR")    # caught exceptions, failed DOM ops
writeLog("message", "WARNING")  # non-fatal: missing element, skipped plugin
writeLog("message", "SUCCESS")  # purchase complete, item available
```

### Error handling (log + return, never raise from plugin methods)

**Source:** `amazon_bot.py` lines 52-54, `bestbuy_bot.py` lines 23-25
**Apply to:** All plugin `check_availability` and `auto_buy` methods

```python
# Pattern: top-level try/except in each public method; log + return safe value
try:
    ...
except Exception as exc:
    writeLog(f"Error in <method>: {exc}", "ERROR")
    return False   # check_availability and auto_buy always return bool
```

### None guard before element interaction (nodriver-specific)

**Source:** RESEARCH.md Pitfall 2 (tab.select returns None, not exception)
**Apply to:** Every `tab.select()` and `tab.find()` call in all plugin files

```python
element = await tab.select("#selector", timeout=10)
if not element:
    writeLog("Selector #selector not found", "WARNING")
    return False   # or continue, depending on context
await element.click()  # only reached if element is not None
```

### Credential sourcing (env vars only)

**Source:** `main.py` lines 121-129, `amazon_bot.py` lines 57-59
**Apply to:** `shopbot_plugin_amazon.py::login`, `shopbot_plugin_bestbuy.py::login`

```python
# SEC-01: credentials from env vars only -- never from config.yml or hardcoded
import os
email = os.environ.get("BB_EMAIL", "")
password = os.environ.get("BB_PASSWORD", "")
if not email or not password:
    writeLog("BB_EMAIL or BB_PASSWORD not set -- skipping login", "ERROR")
    return
```

### update_item_purchased call site

**Source:** `models.py` lines 40-48; called correctly in `amazon_bot.py` line 184 (Amazon); missing in `bestbuy_bot.py` line 71 (PLG-02 bug)
**Apply to:** `auto_buy` in both plugin files, immediately after the place-order click log

```python
from models import update_item_purchased

# Call after successful place-order click, before return True:
writeLog("Order placed on <Platform>", "SUCCESS")
update_item_purchased(url)
return True
```

### Test fixture: tmp_config_yml

**Source:** `tests/conftest.py` lines 5-18
**Apply to:** Any new test that needs an AppConfig instance

```python
@pytest.fixture
def tmp_config_yml(tmp_path):
    cfg = {
        "debug": {"logging_level": 3, "test_mode": True},
        "available": {"timeout": 10, "items": []},
        "platforms": {"amazon": {"delay_seconds": 30.0}, "bestbuy": {"delay_seconds": 30.0}},
    }
    config_file = tmp_path / "config.yml"
    config_file.write_text(yaml.dump(cfg))
    return config_file
```

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `plugins/PLUGIN_DEV.md` | documentation | — | No markdown docs exist in the codebase; content is fully prescribed in RESEARCH.md Contributor Tooling section |

## Selector Reference (Planner/Executor Quick Lookup)

From RESEARCH.md migration map — verified against `amazon_bot.py` and `bestbuy_bot.py`:

| Platform | Operation | Old (Selenium) | New (nodriver CSS) |
|---|---|---|---|
| Amazon | Add-to-cart | `By.ID, "add-to-cart-button"` | `"#add-to-cart-button"` |
| Amazon | Buy-now | `By.ID, "buy-now-button"` | `"#buy-now-button"` |
| Amazon | Quantity dropdown | `By.CLASS_NAME, "a-button-dropdown"` | `".a-button-dropdown"` |
| Amazon | Quantity option n | `By.ID, f"quantity_{n-1}"` | `f"#quantity_{n-1}"` |
| Amazon | Place order | `By.ID, "submitOrderButtonId"` | `"#submitOrderButtonId"` |
| Amazon | Email | `By.ID, "ap_email"` | `"#ap_email"` |
| Amazon | Password | `By.ID, "ap_password"` | `"#ap_password"` |
| Amazon | Sign-in submit | `By.ID, "signInSubmit"` | `"#signInSubmit"` |
| Amazon | MFA form | `By.ID, "auth-mfa-form"` | `"#auth-mfa-form"` |
| Amazon | Account nav | `By.ID, "nav-link-accountList"` | `"#nav-link-accountList"` |
| Amazon | CAPTCHA text | XPath h4 contains | `await tab.find("Enter the characters you see below", timeout=3)` |
| BestBuy | Add-to-cart | `By.CLASS_NAME, "add-to-cart-button"` | `".add-to-cart-button"` |
| BestBuy | Email | `By.ID, "fld-e"` | `"#fld-e"` |
| BestBuy | Password | `By.ID, "fld-p1"` | `"#fld-p1"` |
| BestBuy | Sign-in submit | `By.CLASS_NAME, "cia-form__controls__submit"` | `".cia-form__controls__submit"` |
| BestBuy | Qty dropdown | `By.CLASS_NAME, "a-dropdown-prompt"` | `".a-dropdown-prompt"` (TODO: verify) |
| BestBuy | Qty option n | `By.XPATH, f"//a[@id='quantity_{n}']"` | `f"#quantity_{n}"` |
| BestBuy | Checkout | `By.CLASS_NAME, "checkout-buttons__checkout"` | `".checkout-buttons__checkout"` |
| BestBuy | CVV | `By.ID, "credit-card-cvv"` | `"#credit-card-cvv"` |
| BestBuy | Place order | `By.CLASS_NAME, "button--place-order"` | `".button--place-order"` |

## Metadata

**Analog search scope:** `E:\repos\ShopPyBot\` — all Python source files, tests, core modules
**Files scanned:** 12 source files read in full
**Analogs with real codebase match:** 8 / 9 (PLUGIN_DEV.md has no analog)
**Pattern extraction date:** 2026-06-02
