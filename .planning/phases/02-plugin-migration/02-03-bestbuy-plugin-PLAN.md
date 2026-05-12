---
phase: 02-plugin-migration
plan: 03
type: execute
wave: 1
depends_on: ["01"]
files_modified:
  - plugins/shopbot_plugin_bestbuy.py
  - tests/test_plugins_bestbuy.py
autonomous: true
requirements:
  - PLG-02
  - PLG-03
tags:
  - plugin-migration
  - bestbuy
  - selenium
  - python

must_haves:
  truths:
    - "plugins/shopbot_plugin_bestbuy.py defines a BestBuyPlugin subclass of RetailerPlugin"
    - "BestBuyPlugin.domain_pattern equals ['bestbuy.com']"
    - "BestBuyPlugin.login_at_startup is True (D-03 opt-in: existing behavior preserved)"
    - "BestBuyPlugin.__init__ builds its own Selenium driver via driver.build_driver and stores it on self.driver (PLG-03)"
    - "BestBuyPlugin.check_availability(url) preserves the add-to-cart class-name presence logic from bestbuy_bot.check_bestbuy_item"
    - "BestBuyPlugin.login(config) preserves the email+password sign-in from bestbuy_bot.bb_sign_in but reads creds from self.platform_config.credentials instead of positional args"
    - "BestBuyPlugin.auto_buy(url, config) preserves the add-to-cart -> cart -> quantity -> checkout -> CVV -> place-order chain from bestbuy_bot.auto_buy_bestbuy_item"
    - "BestBuyPlugin.auto_buy calls models.update_item_purchased(url) after the place-order click (PLG-02: the missing call is added)"
    - "BestBuyPlugin reads quantity by looking up the matching item in config.available.items by URL"
    - "BestBuyPlugin reads test_mode from config.debug.test_mode and skips the final place-order click in test_mode"
    - "BestBuyPlugin reads cvv from self.cvv (set by registry from collect_cvvs(app_config) result)"
    - "BestBuyPlugin does not detect_captcha (uses inherited no-op default returning False) — BestBuy has no CAPTCHA flow today"
    - "Tests monkeypatch driver.build_driver so pytest does not spawn Chrome"
  artifacts:
    - path: "plugins/shopbot_plugin_bestbuy.py"
      provides: "BestBuyPlugin migrated from bestbuy_bot.py with PLG-02 update_item_purchased fix"
      contains: "class BestBuyPlugin(RetailerPlugin)"
      min_lines: 100
    - path: "tests/test_plugins_bestbuy.py"
      provides: "Contract + mocked-driver tests for BestBuyPlugin including PLG-02 verification"
      min_lines: 80
  key_links:
    - from: "plugins/shopbot_plugin_bestbuy.py"
      to: "plugin_base.RetailerPlugin"
      via: "class inheritance"
      pattern: "class BestBuyPlugin\\(RetailerPlugin\\)"
    - from: "plugins/shopbot_plugin_bestbuy.py"
      to: "driver.build_driver"
      via: "called inside __init__"
      pattern: "build_driver"
    - from: "plugins/shopbot_plugin_bestbuy.py"
      to: "models.update_item_purchased"
      via: "called inside auto_buy after place-order click (PLG-02 fix)"
      pattern: "update_item_purchased"
---

<objective>
Migrate BestBuy stock-check and purchase logic out of `bestbuy_bot.py` (73 lines, 3 functions) into `plugins/shopbot_plugin_bestbuy.py` as a `BestBuyPlugin(RetailerPlugin)` subclass, AND fix the longstanding PLG-02 bug: `update_item_purchased()` is never called after a BestBuy purchase today, allowing the bot to re-buy the same item on the next polling cycle.

Purpose: Same wave-1 boundary as Plan 02 (Amazon). After this plan, BestBuy is callable as a plugin, the missing purchase tracking call is added, and the legacy module remains in tree until Plan 04 deletes it per D-02. This plan does NOT touch `main.py` or remove `bestbuy_bot.py` — that is Plan 04's atomic cut.

Output: `plugins/shopbot_plugin_bestbuy.py` and `tests/test_plugins_bestbuy.py`.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/02-plugin-migration/02-CONTEXT.md
@.planning/phases/02-plugin-migration/02-RESEARCH.md
@.planning/phases/02-plugin-migration/02-01-registry-and-abc-amendment-PLAN.md
@plugin_base.py
@bestbuy_bot.py
@driver.py
@logger.py
@models.py
@config_schema.py
</context>

<interfaces>
BestBuyPlugin contract (final shape this plan produces):

```python
# plugins/shopbot_plugin_bestbuy.py
from plugin_base import RetailerPlugin
from driver import build_driver
from logger import writeLog
from models import update_item_purchased

class BestBuyPlugin(RetailerPlugin):
    domain_pattern: list[str] = ["bestbuy.com"]
    login_at_startup: bool = True
    name: str = "bestbuy"

    def __init__(self, platform_config, *, cvv: str | None = None, driver_path: str | None = None):
        super().__init__(platform_config)
        self.cvv = cvv
        self.driver = build_driver(driver_path or "chromedriver.exe")

    def check_availability(self, url: str) -> bool: ...
    def login(self, config) -> None: ...
    def auto_buy(self, url: str, config) -> bool: ...
    # detect_captcha intentionally NOT overridden — inherited no-op returns False
```

Migration mapping (from RESEARCH Q4 BestBuy table):

| Old (`bestbuy_bot.py`) | New (`BestBuyPlugin`) | Notes |
|------------------------|------------------------|-------|
| `check_bestbuy_item(driver, url)` lines 7-25 | `check_availability(self, url) -> bool` | Drop driver arg, use self.driver |
| `bb_sign_in(driver, email, password)` lines 27-38 | `login(self, config) -> None` | Read creds from `self.platform_config.credentials` (drops positional args) |
| `auto_buy_bestbuy_item(driver, url, email, password, cvv, quantity)` lines 40-73 | `auto_buy(self, url, config) -> bool` | Read quantity from `config.available.items[]`, cvv from `self.cvv`, test_mode from `config.debug.test_mode`; **PLG-02 fix**: call `update_item_purchased(url)` after place-order click line 71 |

The legacy `auto_buy_bestbuy_item` calls `bb_sign_in` mid-flow (line 65). New version delegates to `self.login(config)` at the same point in the chain. With `login_at_startup = True` and main.py calling `.login()` at startup (Plan 04), the mid-flow login becomes a no-op-if-already-signed-in OR a re-auth if the session expired; preserving the legacy call site keeps behavioral parity with `bestbuy_bot.py:65` until Phase 3+ refactors session handling.

Quantity lookup is identical to AmazonPlugin's pattern (`config.available.items` scan by URL match).
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Write RED tests for BestBuyPlugin contract + PLG-02 fix verification</name>
  <files>tests/test_plugins_bestbuy.py</files>
  <read_first>
    - tests/test_plugin_base.py (existing ABC test patterns)
    - tests/test_plugins_amazon.py (Plan 02 RED tests — parallel structure; use the same mocking recipe)
    - .planning/phases/02-plugin-migration/02-RESEARCH.md (Q5 mocking, Q4 BestBuy mapping)
    - bestbuy_bot.py (current logic; note line 71 is where update_item_purchased was missing)
  </read_first>
  <behavior>
    - test_bestbuy_plugin_subclasses_retailer_plugin: issubclass(BestBuyPlugin, RetailerPlugin)
    - test_bestbuy_plugin_domain_pattern: BestBuyPlugin.domain_pattern == ["bestbuy.com"]
    - test_bestbuy_plugin_login_at_startup_true: BestBuyPlugin.login_at_startup is True
    - test_bestbuy_plugin_name_is_bestbuy: BestBuyPlugin.name == "bestbuy"
    - test_bestbuy_plugin_owns_driver: monkeypatched build_driver returns sentinel; plugin.driver is sentinel
    - test_bestbuy_plugin_check_availability_signature: parameters == ['self', 'url']
    - test_bestbuy_plugin_auto_buy_signature: parameters == ['self', 'url', 'config']
    - test_bestbuy_plugin_detect_captcha_not_overridden: BestBuyPlugin.detect_captcha is RetailerPlugin.detect_captcha (inherits the no-op)
    - test_bestbuy_plugin_calls_update_item_purchased_on_success: AST-walk plugins/shopbot_plugin_bestbuy.py; assert `Call(func=Name(id='update_item_purchased'))` appears inside the FunctionDef named `auto_buy` (this is the PLG-02 fix assertion)
    - test_bestbuy_plugin_login_reads_credentials_from_platform_config: AST-walk plugins/shopbot_plugin_bestbuy.py; assert `self.platform_config.credentials.email` and `.password` attribute access appear inside the FunctionDef named `login`
    - test_bestbuy_plugin_no_config_singleton_import: source-grep `from config import` is absent
    - test_bestbuy_plugin_no_positional_credential_args: AST-walk; assert `login` and `auto_buy` do NOT have parameters named `email`, `password`, or `cvv` (the old positional shape is forbidden)
  </behavior>
  <action>
    1. Create `tests/test_plugins_bestbuy.py`. Use the same import-by-file-path fixture as Plan
       02 since `plugins/` is not a package:
       ```python
       import ast
       import importlib.util
       import inspect
       import pathlib
       import pytest

       PLUGIN_FILE = pathlib.Path("plugins/shopbot_plugin_bestbuy.py")


       @pytest.fixture
       def bestbuy_plugin_cls(monkeypatch):
           sentinel = object()
           monkeypatch.setattr("driver.build_driver", lambda *a, **kw: sentinel)
           spec = importlib.util.spec_from_file_location(
               "test_bestbuy_plugin_load", PLUGIN_FILE
           )
           module = importlib.util.module_from_spec(spec)
           spec.loader.exec_module(module)
           return module.BestBuyPlugin, sentinel
       ```

    2. The PLG-02 fix test (most important for this plan) must concretely assert the call exists
       inside `auto_buy`. Pattern:
       ```python
       def test_bestbuy_plugin_calls_update_item_purchased_on_success():
           tree = ast.parse(PLUGIN_FILE.read_text())
           for node in ast.walk(tree):
               if isinstance(node, ast.FunctionDef) and node.name == "auto_buy":
                   for sub in ast.walk(node):
                       if (isinstance(sub, ast.Call)
                           and isinstance(sub.func, ast.Name)
                           and sub.func.id == "update_item_purchased"):
                           return
                   pytest.fail("auto_buy does not call update_item_purchased — PLG-02 regression")
           pytest.fail("auto_buy method not found")
       ```

    3. Write all 12 tests listed under <behavior>.

    4. Run `rtk pytest -x -q tests/test_plugins_bestbuy.py` — must fail with file-not-found
       (plugin module does not exist yet).
  </action>
  <verify>
    <automated>rtk pytest -x tests/test_plugins_bestbuy.py 2>&1 | rtk grep -E "FileNotFoundError|ModuleNotFoundError|shopbot_plugin_bestbuy"</automated>
  </verify>
  <acceptance_criteria>
    - `tests/test_plugins_bestbuy.py` exists with 12 tests
    - PLG-02 fix test (`test_bestbuy_plugin_calls_update_item_purchased_on_success`) present and structured to AST-walk the `auto_buy` definition
    - Every test uses monkeypatched build_driver; no test spawns Chrome
    - `rtk pytest -x tests/test_plugins_bestbuy.py` exits non-zero
  </acceptance_criteria>
  <done>Test file committed in RED state</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement BestBuyPlugin with PLG-02 fix (GREEN)</name>
  <files>plugins/shopbot_plugin_bestbuy.py</files>
  <read_first>
    - bestbuy_bot.py (full file — port logic literally)
    - tests/test_plugins_bestbuy.py (RED tests from Task 1)
    - plugin_base.py (amended ABC)
    - models.py (update_item_purchased signature)
    - driver.py (build_driver signature)
    - .planning/phases/02-plugin-migration/02-RESEARCH.md (Q4 BestBuy mapping, pitfall 7 on line 71)
  </read_first>
  <behavior>
    - All 12 tests in tests/test_plugins_bestbuy.py pass
    - PLG-02 fix verified: update_item_purchased(url) is called inside auto_buy after the place-order click on the success path
    - Module imports only: plugin_base, driver, logger, models, selenium.*
    - detect_captcha is NOT overridden (intentional per RESEARCH Q4 — BestBuy has no CAPTCHA today)
  </behavior>
  <action>
    1. Confirm `plugins/` directory exists (Plan 02 will create it first if run in parallel; if Plan 02 has not landed yet at execution time, create it here — `rtk find plugins/` and mkdir if missing). Do NOT create `plugins/__init__.py`.

    2. Create `plugins/shopbot_plugin_bestbuy.py`:
       ```python
       """BestBuy retailer plugin (PLG-02, PLG-03).

       Migrated from bestbuy_bot.py per Phase 2 CONTEXT.md D-02.

       PLG-02 fix: legacy bestbuy_bot.auto_buy_bestbuy_item did not call
       update_item_purchased() after a successful order, so the bot would
       attempt to re-buy the item every polling cycle. This implementation
       calls update_item_purchased(url) immediately after the place-order
       click on the success branch.
       """
       from selenium.webdriver.common.by import By
       from selenium.webdriver.support import expected_conditions as EC
       from selenium.webdriver.support.ui import WebDriverWait

       from driver import build_driver
       from logger import writeLog
       from models import update_item_purchased
       from plugin_base import RetailerPlugin


       SIGNIN_URL = "https://www.bestbuy.com/identity/signin"


       class BestBuyPlugin(RetailerPlugin):
           domain_pattern: list[str] = ["bestbuy.com"]
           login_at_startup: bool = True
           name: str = "bestbuy"

           def __init__(self, platform_config, *, cvv=None, driver_path=None):
               super().__init__(platform_config)
               self.cvv = cvv
               self.driver = build_driver(driver_path or "chromedriver.exe")

           def check_availability(self, url: str) -> bool:
               # Port from bestbuy_bot.check_bestbuy_item lines 7-25.
               writeLog(f"Entering check_availability for URL: {url}", "DEBUG")
               try:
                   self.driver.get(url)
                   button = WebDriverWait(self.driver, 10).until(
                       EC.presence_of_element_located(
                           (By.CLASS_NAME, "add-to-cart-button")
                       )
                   )
                   if button:
                       writeLog("Item is available on BestBuy", "SUCCESS")
                       return True
                   return False
               except Exception as e:
                   writeLog(f"Error checking BestBuy item: {e}", "ERROR")
                   return False

           def login(self, config) -> None:
               # Port from bestbuy_bot.bb_sign_in lines 27-38.
               writeLog("Entering BestBuyPlugin.login", "DEBUG")
               try:
                   email = self.platform_config.credentials.email
                   password = self.platform_config.credentials.password
                   self.driver.get(SIGNIN_URL)
                   WebDriverWait(self.driver, 10).until(
                       EC.presence_of_element_located((By.ID, "fld-e"))
                   ).send_keys(email)
                   self.driver.find_element(By.ID, "fld-p1").send_keys(password)
                   self.driver.find_element(
                       By.CLASS_NAME, "cia-form__controls__submit"
                   ).click()
                   writeLog("Signed in to BestBuy", "INFO")
               except Exception as e:
                   writeLog(f"Error during BestBuy sign-in: {e}", "ERROR")

           def auto_buy(self, url: str, config) -> bool:
               quantity = self._lookup_quantity(url, config)
               test_mode = bool(config.debug.test_mode)
               try:
                   self._add_to_cart(url)
                   self._set_cart_quantity(quantity)
                   self._proceed_to_checkout()
                   self.login(config)
                   self._enter_cvv()
                   return self._place_order(url, test_mode)
               except Exception as e:
                   writeLog(f"Error during BestBuy auto-buy: {e}", "ERROR")
                   return False

           def _lookup_quantity(self, url, config) -> int:
               for item in config.available.items:
                   if item.link == url:
                       return int(item.quantity)
               writeLog(
                   f"No item entry found for {url}; defaulting quantity to 1",
                   "WARNING",
               )
               return 1

           def _add_to_cart(self, url: str) -> None:
               self.driver.get(url)
               WebDriverWait(self.driver, 10).until(
                   EC.presence_of_element_located(
                       (By.CLASS_NAME, "add-to-cart-button")
                   )
               ).click()
               writeLog("Added to cart on BestBuy", "INFO")

           def _set_cart_quantity(self, quantity: int) -> None:
               self.driver.get("https://www.bestbuy.com/cart")
               WebDriverWait(self.driver, 10).until(
                   EC.presence_of_element_located(
                       (By.CLASS_NAME, "a-dropdown-prompt")
                   )
               ).click()
               WebDriverWait(self.driver, 10).until(
                   EC.presence_of_element_located(
                       (By.XPATH, f"//a[@id='quantity_{quantity}']")
                   )
               ).click()

           def _proceed_to_checkout(self) -> None:
               self.driver.find_element(
                   By.CLASS_NAME, "checkout-buttons__checkout"
               ).click()
               writeLog("Proceeded to checkout on BestBuy", "INFO")

           def _enter_cvv(self) -> None:
               WebDriverWait(self.driver, 10).until(
                   EC.presence_of_element_located((By.ID, "credit-card-cvv"))
               ).send_keys(self.cvv or "")

           def _place_order(self, url: str, test_mode: bool) -> bool:
               if test_mode:
                   writeLog(
                       "Test mode active: Skipping final place-order click on BestBuy",
                       "INFO",
                   )
                   return False
               self.driver.find_element(
                   By.CLASS_NAME, "button--place-order"
               ).click()
               writeLog("Order placed on BestBuy", "SUCCESS")
               update_item_purchased(url)  # PLG-02 fix
               return True
       ```

    3. Constraint checks:
       - Every method/function under 30 lines (the decomposition above keeps each under that limit)
       - File under 300 lines
       - No `from config import config`
       - `detect_captcha` is NOT defined on the class (inherits the no-op default from RetailerPlugin)
       - PLG-02: `update_item_purchased(url)` appears in `_place_order` (which is called by `auto_buy`) on the success branch only

    4. Run `rtk pytest -x -q tests/test_plugins_bestbuy.py`. All 12 tests pass.

    5. Run full suite `rtk pytest -x -q`.

    This plan does NOT delete `bestbuy_bot.py` and does NOT edit `main.py`. Plan 04 owns those.
  </action>
  <verify>
    <automated>rtk pytest -x -q tests/test_plugins_bestbuy.py</automated>
    <automated>rtk grep -n "from config import" plugins/shopbot_plugin_bestbuy.py</automated>
    <automated>rtk grep -n "update_item_purchased" plugins/shopbot_plugin_bestbuy.py</automated>
    <automated>python -c "import ast; t = ast.parse(open('plugins/shopbot_plugin_bestbuy.py').read()); assert not any(isinstance(n, ast.FunctionDef) and n.name == 'detect_captcha' for n in ast.walk(t)), 'detect_captcha must NOT be overridden'; print('OK')"</automated>
    <automated>rtk pytest -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `plugins/shopbot_plugin_bestbuy.py` exists
    - `BestBuyPlugin` subclasses `RetailerPlugin` with `domain_pattern = ["bestbuy.com"]`, `login_at_startup = True`, `name = "bestbuy"`
    - All 12 tests in `tests/test_plugins_bestbuy.py` pass
    - `update_item_purchased(url)` is called on the success branch of `auto_buy` (PLG-02 satisfied)
    - `detect_captcha` is NOT overridden in the class body
    - No `from config import` anywhere in the file
    - File under 300 lines; no method over 30 lines
    - `bestbuy_bot.py` is UNCHANGED
    - `main.py` is UNCHANGED
    - Full test suite green
  </acceptance_criteria>
  <done>BestBuyPlugin shipped with PLG-02 fix, tests green, legacy modules untouched</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| config.platforms.bestbuy.credentials -> BestBuy login form | Email/password flow into selenium send_keys |
| cvv (runtime input via getpass) -> credit-card-cvv field | CVV must never be logged or persisted |
| BestBuy page DOM -> plugin selectors | Class-name based selectors are brittle to BestBuy template changes |
| update_item_purchased -> SQLite | PLG-02 root cause: missing call enabled double-purchase |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-2-PLG-02-DBLBUY | Repudiation | BestBuyPlugin.auto_buy | mitigate | `update_item_purchased(url)` call added inside `_place_order` on success branch; AST test asserts the call exists; this is the PLG-02 root fix |
| T-2-PLG-02-CVV | Information Disclosure | _enter_cvv | mitigate | `self.cvv` read from `getpass`-collected dict (Phase 1 SEC-02); never written to writeLog. The `self.cvv or ""` fallback prevents an unset CVV from raising on `.send_keys(None)` |
| T-2-PLG-02-CREDS | Information Disclosure | BestBuyPlugin.login | mitigate | Credentials read from `self.platform_config.credentials`, not passed positionally; never logged |
| T-2-PLG-03-DRIVER | Spoofing | BestBuyPlugin.__init__ | mitigate | Driver built via `build_driver` (Phase 1 hardened factory); plugin does not construct webdriver.Chrome directly |
| T-2-PLG-02-TESTMODE | Tampering | _place_order | mitigate | `test_mode` short-circuits before the place-order click; returns False so the caller does NOT mark the item purchased (test_mode never triggers update_item_purchased) |
</threat_model>

<verification>
- `rtk pytest -x -q tests/test_plugins_bestbuy.py` passes (12 tests)
- `rtk pytest -x -q` full suite passes
- `rtk grep -n "update_item_purchased" plugins/shopbot_plugin_bestbuy.py` reports at least 1 match
- `rtk grep -n "from config import" plugins/shopbot_plugin_bestbuy.py` reports 0 matches
- `rtk find plugins/__init__.py` returns nothing
- `bestbuy_bot.py` diff vs main shows no changes (Plan 04 handles deletion)
</verification>

<success_criteria>
- PLG-02 satisfied: BestBuyPlugin implements the ABC AND adds the missing `update_item_purchased(url)` call after a successful order
- PLG-03 satisfied: BestBuyPlugin owns its own `self.driver` constructed in `__init__`
- Plan 04 has a working BestBuyPlugin to integrate with main.py and a green path for deleting bestbuy_bot.py
</success_criteria>

<output>
After completion, create `.planning/phases/02-plugin-migration/02-03-SUMMARY.md`
</output>
