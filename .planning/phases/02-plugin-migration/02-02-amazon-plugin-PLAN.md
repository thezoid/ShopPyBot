---
phase: 02-plugin-migration
plan: 02
type: execute
wave: 1
depends_on: ["01"]
files_modified:
  - plugins/shopbot_plugin_amazon.py
  - tests/test_plugins_amazon.py
autonomous: true
requirements:
  - PLG-01
  - PLG-03
tags:
  - plugin-migration
  - amazon
  - selenium
  - python

must_haves:
  truths:
    - "plugins/shopbot_plugin_amazon.py defines an AmazonPlugin subclass of RetailerPlugin"
    - "AmazonPlugin.domain_pattern equals ['amazon.com', 'amzn.to'] (covers product URLs and the official URL shortener)"
    - "AmazonPlugin.login_at_startup is True (D-03 opt-in: OTP flow runs once at startup)"
    - "AmazonPlugin.__init__ builds its own Selenium driver via driver.build_driver and stores it on self.driver (PLG-03)"
    - "AmazonPlugin.check_availability(url) preserves the add-to-cart OR buy-now button presence logic from amazon_bot.check_amazon_item"
    - "AmazonPlugin.detect_captcha() preserves the CAPTCHA XPATH check from amazon_bot.detect_captcha and is callable as an ABC override"
    - "AmazonPlugin.login(config) preserves the email + password + manual-passkey + OTP sequence from amazon_bot.amz_sign_in"
    - "AmazonPlugin.auto_buy(url, config) preserves quantity dropdown -> buy-now -> place-order chain and calls models.update_item_purchased(url) on success"
    - "AmazonPlugin reads quantity by looking up the matching item in config.available.items by URL (no quantity param on auto_buy)"
    - "AmazonPlugin reads test_mode from config.debug.test_mode (no test_mode param on auto_buy)"
    - "AmazonPlugin reads credentials from self.platform_config.credentials (.email, .password); never `from config import config`"
    - "Tests monkeypatch driver.build_driver so pytest does not spawn Chrome"
  artifacts:
    - path: "plugins/shopbot_plugin_amazon.py"
      provides: "AmazonPlugin migrated from amazon_bot.py"
      contains: "class AmazonPlugin(RetailerPlugin)"
      min_lines: 150
    - path: "tests/test_plugins_amazon.py"
      provides: "Contract + mocked-driver tests for AmazonPlugin"
      min_lines: 80
  key_links:
    - from: "plugins/shopbot_plugin_amazon.py"
      to: "plugin_base.RetailerPlugin"
      via: "class inheritance"
      pattern: "class AmazonPlugin\\(RetailerPlugin\\)"
    - from: "plugins/shopbot_plugin_amazon.py"
      to: "driver.build_driver"
      via: "called inside __init__"
      pattern: "build_driver"
    - from: "plugins/shopbot_plugin_amazon.py"
      to: "models.update_item_purchased"
      via: "called inside auto_buy after submitOrderButton click"
      pattern: "update_item_purchased"
---

<objective>
Migrate Amazon stock-check and purchase logic out of `amazon_bot.py` (192 lines, 4 functions) into `plugins/shopbot_plugin_amazon.py` as an `AmazonPlugin(RetailerPlugin)` subclass that conforms to the Phase 1 ABC and the Plan 01 amendments (PLG-01, PLG-03).

Purpose: After this plan, the Amazon flow is callable via `plugin.check_availability(url)` / `plugin.auto_buy(url, config)` against an instance constructed by the registry. Old `amazon_bot.py` remains in tree until Plan 04 (the main.py refactor wave) deletes it per D-02; this plan does NOT touch `main.py` or remove `amazon_bot.py` to keep wave-1 parallelism safe.

Output: `plugins/shopbot_plugin_amazon.py` and `tests/test_plugins_amazon.py`.
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
@amazon_bot.py
@driver.py
@logger.py
@models.py
@utils.py
@config_schema.py
</context>

<interfaces>
AmazonPlugin contract (final shape this plan produces):

```python
# plugins/shopbot_plugin_amazon.py
from plugin_base import RetailerPlugin
from driver import build_driver
from logger import writeLog
from models import update_item_purchased
from utils import play_notification_sound

class AmazonPlugin(RetailerPlugin):
    domain_pattern: list[str] = ["amazon.com", "amzn.to"]
    login_at_startup: bool = True
    name: str = "amazon"

    def __init__(self, platform_config, *, cvv: str | None = None, driver_path: str | None = None):
        super().__init__(platform_config)
        self.cvv = cvv
        self.driver = build_driver(driver_path or "chromedriver.exe")

    def check_availability(self, url: str) -> bool: ...
    def login(self, config) -> None: ...
    def auto_buy(self, url: str, config) -> bool: ...
    def detect_captcha(self) -> bool: ...
```

Lookups inside `auto_buy(url, config)` (resolves RESEARCH open questions 2 and 3):
- quantity: scan `config.available.items` for the entry whose `.link == url`; default 1 if not found.
- test_mode: read `config.debug.test_mode`.
- credentials: read `self.platform_config.credentials.email` / `.password`.

Migration mapping (from RESEARCH Q4 table):

| Old (`amazon_bot.py`) | New (`AmazonPlugin`) | Notes |
|-----------------------|----------------------|-------|
| `detect_captcha(driver)` lines 10-17 | `detect_captcha(self) -> bool` | Drop driver arg; use self.driver |
| `check_amazon_item(driver, url)` lines 19-54 | `check_availability(self, url) -> bool` | Calls self.detect_captcha() inline (removes the duplicate call site in current main.py line 53) |
| `amz_sign_in(driver, config)` lines 56-121 | `login(self, config) -> None` | Two `input()` calls preserved (passkey dismiss + OTP) |
| `auto_buy_amazon_item(driver, url, config, quantity, test_mode)` lines 123-192 | `auto_buy(self, url, config) -> bool` | quantity + test_mode no longer params; looked up from config. Returns True on success, False on any error path |

Functions must stay under 30 lines each (CLAUDE.md). The current `auto_buy_amazon_item` is ~70 lines — split it into small helpers (`_select_quantity`, `_click_buy_now`, `_place_order`) inside the plugin module.
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Write RED tests for AmazonPlugin contract + driver ownership</name>
  <files>tests/test_plugins_amazon.py</files>
  <read_first>
    - tests/test_plugin_base.py (existing ABC test patterns)
    - tests/test_plugin_registry.py (mock-driver fixture pattern from Plan 01)
    - .planning/phases/02-plugin-migration/02-RESEARCH.md (Q5 mocking recipe)
    - amazon_bot.py (current logic being migrated)
  </read_first>
  <behavior>
    - test_amazon_plugin_subclasses_retailer_plugin: issubclass(AmazonPlugin, RetailerPlugin)
    - test_amazon_plugin_domain_pattern: AmazonPlugin.domain_pattern == ["amazon.com", "amzn.to"]
    - test_amazon_plugin_login_at_startup_true: AmazonPlugin.login_at_startup is True
    - test_amazon_plugin_name_is_amazon: AmazonPlugin.name == "amazon"
    - test_amazon_plugin_owns_driver: monkeypatch build_driver to return sentinel; instantiate; assert plugin.driver is sentinel
    - test_amazon_plugin_construct_uses_platform_config: pass a dummy platform_config; assert self.platform_config is that object
    - test_amazon_plugin_check_availability_signature: inspect.signature(AmazonPlugin.check_availability).parameters keys == ['self', 'url']
    - test_amazon_plugin_auto_buy_signature: inspect.signature(AmazonPlugin.auto_buy).parameters keys == ['self', 'url', 'config']
    - test_amazon_plugin_detect_captcha_overridden: AmazonPlugin.detect_captcha is not RetailerPlugin.detect_captcha
    - test_amazon_plugin_calls_update_item_purchased_on_success: source-grep test asserting `update_item_purchased` appears in plugins/shopbot_plugin_amazon.py inside the auto_buy block (use ast to locate the call site under FunctionDef name="auto_buy")
    - test_amazon_plugin_no_config_singleton_import: source-grep asserting `from config import` does NOT appear in plugins/shopbot_plugin_amazon.py (anti-pattern from RESEARCH Q9.1)
  </behavior>
  <action>
    1. Create `tests/test_plugins_amazon.py`. Mock `build_driver` at module level for the
       construction tests:
       ```python
       import ast
       import inspect
       import pathlib
       import pytest

       PLUGIN_FILE = pathlib.Path("plugins/shopbot_plugin_amazon.py")


       @pytest.fixture
       def amazon_plugin_cls(monkeypatch):
           sentinel = object()
           monkeypatch.setattr("driver.build_driver", lambda *a, **kw: sentinel)
           from plugins.shopbot_plugin_amazon import AmazonPlugin
           return AmazonPlugin, sentinel


       def test_amazon_plugin_subclasses_retailer_plugin(amazon_plugin_cls):
           from plugin_base import RetailerPlugin
           cls, _ = amazon_plugin_cls
           assert issubclass(cls, RetailerPlugin)

       # ... (remaining 10 tests)
       ```

       For the source-grep tests, use `ast.parse(PLUGIN_FILE.read_text())` and walk for
       `Call(func=Name(id='update_item_purchased'))` inside a `FunctionDef(name='auto_buy')`.

       NOTE: `plugins/` is not a Python package today (no `__init__.py` and CONTEXT.md says it
       must NOT be one for registry semantics). Import the plugin module by file path using
       importlib in the test (mirror the registry pattern), OR use the registry's `_load_module`
       helper. Recommended: use `importlib.util.spec_from_file_location` directly in the fixture
       so tests do not depend on registry behavior:
       ```python
       import importlib.util
       spec = importlib.util.spec_from_file_location(
           "test_amazon_plugin_load", PLUGIN_FILE
       )
       module = importlib.util.module_from_spec(spec)
       spec.loader.exec_module(module)
       AmazonPlugin = module.AmazonPlugin
       ```

    2. Run `rtk pytest -x -q tests/test_plugins_amazon.py`. Must fail because
       `plugins/shopbot_plugin_amazon.py` does not exist yet (FileNotFoundError or
       ModuleNotFoundError).
  </action>
  <verify>
    <automated>rtk pytest -x tests/test_plugins_amazon.py 2>&1 | rtk grep -E "FileNotFoundError|ModuleNotFoundError|shopbot_plugin_amazon"</automated>
  </verify>
  <acceptance_criteria>
    - `tests/test_plugins_amazon.py` exists with the 11 tests listed in <behavior>
    - Every test uses monkeypatched `build_driver`; no test imports `selenium.webdriver`
    - `rtk pytest -x tests/test_plugins_amazon.py` exits non-zero (file-not-found state)
    - No real Chrome process spawned during test collection
  </acceptance_criteria>
  <done>Test file committed in RED state</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement AmazonPlugin (GREEN)</name>
  <files>plugins/shopbot_plugin_amazon.py</files>
  <read_first>
    - amazon_bot.py (full file — port logic literally; do not refactor behavior)
    - tests/test_plugins_amazon.py (RED tests from Task 1)
    - plugin_base.py (amended ABC from Plan 01)
    - models.py (update_item_purchased signature)
    - utils.py (play_notification_sound signature)
    - driver.py (build_driver signature)
    - .planning/phases/02-plugin-migration/02-RESEARCH.md (Q4 migration table; Q10 wiring)
  </read_first>
  <behavior>
    - All 11 tests in tests/test_plugins_amazon.py pass
    - Module imports only: plugin_base, driver, logger, models, utils, selenium.* (allowed for browser automation)
    - No `from config import config`; no `from amazon_bot import *`
    - Each method body decomposed so no function exceeds 30 lines
  </behavior>
  <action>
    1. Create directory `plugins/` if it does not exist. Do NOT create `plugins/__init__.py`
       (registry requires it to NOT be a package per RESEARCH Q1 pitfall).

    2. Create `plugins/shopbot_plugin_amazon.py`. Skeleton (fill in bodies from amazon_bot.py):
       ```python
       """Amazon retailer plugin (PLG-01, PLG-03).

       Migrated from amazon_bot.py per Phase 2 CONTEXT.md D-02.
       """
       import time

       from selenium.webdriver.common.by import By
       from selenium.webdriver.support import expected_conditions as EC
       from selenium.webdriver.support.ui import WebDriverWait

       from driver import build_driver
       from logger import writeLog
       from models import update_item_purchased
       from plugin_base import RetailerPlugin
       from utils import play_notification_sound


       AMAZON_SIGNIN_URL = (
           "https://www.amazon.com/ap/signin?openid.pape.max_auth_age=0&"
           "openid.return_to=https%3A%2F%2Fwww.amazon.com%2F%3Fref_%3Dnav_signin&"
           "openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&"
           "openid.assoc_handle=usflex&openid.mode=checkid_setup&"
           "openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&"
           "openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0"
       )


       class AmazonPlugin(RetailerPlugin):
           domain_pattern: list[str] = ["amazon.com", "amzn.to"]
           login_at_startup: bool = True
           name: str = "amazon"

           def __init__(self, platform_config, *, cvv=None, driver_path=None):
               super().__init__(platform_config)
               self.cvv = cvv
               self.driver = build_driver(driver_path or "chromedriver.exe")

           def detect_captcha(self) -> bool:
               try:
                   WebDriverWait(self.driver, 5).until(
                       EC.presence_of_element_located((
                           By.XPATH,
                           "//h4[contains(text(), 'Enter the characters you see below')]",
                       ))
                   )
                   return True
               except Exception:
                   return False

           def check_availability(self, url: str) -> bool:
               # Port amazon_bot.check_amazon_item logic; call self.detect_captcha()
               # instead of the module-level helper. Single call site (removes the
               # current duplicate in main.py line 53).
               ...

           def login(self, config) -> None:
               # Port amazon_bot.amz_sign_in. Read email/password from self.platform_config.
               ...

           def auto_buy(self, url: str, config) -> bool:
               quantity = self._lookup_quantity(url, config)
               test_mode = bool(config.debug.test_mode)
               self.login(config)
               return self._purchase_flow(url, quantity, test_mode)

           # Helpers (each under 30 lines):
           def _lookup_quantity(self, url, config) -> int: ...
           def _purchase_flow(self, url, quantity, test_mode) -> bool: ...
           def _select_quantity(self, quantity) -> bool: ...
           def _click_buy_now(self) -> bool: ...
           def _place_order(self, url, test_mode) -> bool: ...
       ```

    3. Port behaviors verbatim from `amazon_bot.py`:
       - `detect_captcha`: lines 10-17 (already shown above)
       - `check_availability`: lines 19-54. Call `self.detect_captcha()` instead of the bare function. Use `self.driver`. Drop the `driver` parameter from all WebDriverWait calls — replace with `self.driver`.
       - `login`: lines 56-121. Read `email = self.platform_config.credentials.email`, same for password. Preserve both `input()` calls (passkey dismiss line 89, OTP line 115). Preserve `play_notification_sound()` calls. The legacy code swallows the outer exception (line 120-121) — keep that behavior (return None, do not raise; the caller in main.py treats login as best-effort).
       - `auto_buy`: lines 123-192. Quantity dropdown -> quantity option -> buy-now -> place-order. On success (after `place_order_button.click()` line 182), call `update_item_purchased(url)` and return True. Return False on any error or when test_mode skips the click. Preserve the `input("Press Enter to continue...")` test-mode pauses.

    4. Quantity lookup (`_lookup_quantity`):
       ```python
       def _lookup_quantity(self, url, config) -> int:
           for item in config.available.items:
               if item.link == url:
                   return int(item.quantity)
           writeLog(f"No item entry found for {url}; defaulting quantity to 1", "WARNING")
           return 1
       ```

    5. Verify constraints:
       - `rtk find plugins/shopbot_plugin_amazon.py` exists
       - No `from config import config`
       - No top-level `driver = ...` (driver lives on `self`)
       - File length under 300 lines
       - Each function/method under 30 lines (split as shown above)

    6. Run `rtk pytest -x -q tests/test_plugins_amazon.py`. All 11 tests pass.

    7. Run full suite `rtk pytest -x -q` to confirm no regressions.

    Important: this plan does NOT delete `amazon_bot.py` and does NOT edit `main.py`. The legacy
    module continues to exist in parallel until Plan 04 performs the hard cut. This keeps Plan 02
    parallel-safe with Plan 03 (BestBuy) and Plan 05 (docs).
  </action>
  <verify>
    <automated>rtk pytest -x -q tests/test_plugins_amazon.py</automated>
    <automated>python -c "import importlib.util; spec = importlib.util.spec_from_file_location('amz', 'plugins/shopbot_plugin_amazon.py'); m = importlib.util.module_from_spec(spec); spec.loader.exec_module.__self__ if False else None; print('module file syntactically valid')"</automated>
    <automated>rtk grep -n "from config import" plugins/shopbot_plugin_amazon.py</automated>
    <automated>rtk grep -n "update_item_purchased" plugins/shopbot_plugin_amazon.py</automated>
    <automated>rtk pytest -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `plugins/shopbot_plugin_amazon.py` exists
    - `AmazonPlugin` subclasses `RetailerPlugin` with required class attributes set
    - All 11 tests in `tests/test_plugins_amazon.py` pass
    - No `from config import` anywhere in the file
    - `update_item_purchased(url)` is called inside `auto_buy` (or a helper invoked by it) on the success branch
    - File under 300 lines; no function over 30 lines
    - `amazon_bot.py` is UNCHANGED (deletion is Plan 04's job)
    - `main.py` is UNCHANGED (refactor is Plan 04's job)
    - Full test suite green
  </acceptance_criteria>
  <done>AmazonPlugin shipped, tests green, legacy modules untouched per wave-1 boundary</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| config.platforms.amazon.credentials -> Amazon login form | Email/password flow into selenium send_keys; risk of credentials in logs or in driver console output |
| Amazon page DOM -> plugin selectors | Hostile or changed page markup could mislead the availability check or trigger spurious purchases |
| update_item_purchased -> SQLite | Successful order must mark the item; failure mode is double-purchase if the call is skipped |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-2-PLG-01-CREDS | Information Disclosure | AmazonPlugin.login | mitigate | Credentials read from `self.platform_config.credentials` (Pydantic), never logged via writeLog (port preserves the existing pattern: only error context is logged, not password) |
| T-2-PLG-01-DBLBUY | Repudiation | AmazonPlugin.auto_buy | mitigate | `update_item_purchased(url)` is called immediately after `submitOrderButton.click()`; test asserts call site via AST grep |
| T-2-PLG-03-DRIVER | Spoofing | AmazonPlugin.__init__ | mitigate | Driver built via `build_driver` (Phase 1 hardened factory: SEC-03/04/05 already applied); plugin does not construct webdriver.Chrome directly |
| T-2-PLG-01-CAPTCHA | Tampering | check_availability | mitigate | CAPTCHA detection inline calls `self.detect_captcha()`; pauses with `input()` for manual solve (preserves Phase 1 behavior) |
| T-2-PLG-01-RUNTIME-EX | Denial of Service | auto_buy error paths | accept | Per-step try/except logs ERROR and returns; matches legacy behavior. main.py wraps the call in try/except (Plan 04). Runtime crash does not stop the polling loop |
</threat_model>

<verification>
- `rtk pytest -x -q tests/test_plugins_amazon.py` passes (11 tests)
- `rtk pytest -x -q` full suite passes (no Phase 1 regression)
- `rtk grep -c "@abstractmethod" plugins/shopbot_plugin_amazon.py` reports 0 (plugin implements, does not declare abstracts)
- `rtk grep -n "from config import" plugins/shopbot_plugin_amazon.py` reports 0 matches
- `rtk find plugins/__init__.py` returns nothing (must NOT exist)
- `amazon_bot.py` diff vs main shows no changes (this plan does not touch it)
</verification>

<success_criteria>
- PLG-01 satisfied: AmazonPlugin implements the ABC with all logic from amazon_bot.py migrated
- PLG-03 satisfied: AmazonPlugin owns its own `self.driver` constructed in `__init__`
- Plan 04 has a working AmazonPlugin to integrate with main.py and a green path for deleting amazon_bot.py
</success_criteria>

<output>
After completion, create `.planning/phases/02-plugin-migration/02-02-SUMMARY.md`
</output>
