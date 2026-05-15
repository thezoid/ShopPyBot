# Plugin Developer Guide

Technical contract reference for ShopPyBot retail plugins. This document defines
*what a plugin must look like* to be auto-discovered and routed by the
`plugin_registry`. For the meta workflow (fork, branch, code of conduct, PR
template) see `CONTRIBUTING.md` (Phase 3).

## What is a plugin?

A plugin is a single Python module under `plugins/` that defines exactly one
subclass of `RetailerPlugin` (the ABC declared in `plugin_base.py`). At startup,
the registry walks `plugins/`, imports every file matching the naming
convention, and instantiates each subclass. The polling loop then routes each
configured item URL to the matching plugin based on its `domain_pattern`.

The bot is plugin-first: `main.py` has no knowledge of Amazon, BestBuy, or any
other retailer. Adding support for a new platform means dropping a new file
into `plugins/`. No core edits required.

A working starter template lives at `plugins/example_plugin.py`. Copy it to
`plugins/shopbot_plugin_<your_platform>.py` and edit the bodies.

## The contract

Every plugin subclasses `plugin_base.RetailerPlugin`. The ABC declares:

Required abstract methods (you MUST override these):

| Method | Signature | Returns |
| ------ | --------- | ------- |
| `check_availability` | `(self, url: str) -> bool` | True if in stock |
| `auto_buy` | `(self, url: str, config) -> bool` | True on confirmed purchase |

Default no-op methods (override only if needed):

| Method | Signature | Default |
| ------ | --------- | ------- |
| `login` | `(self, config) -> None` | does nothing |
| `detect_captcha` | `(self) -> bool` | returns False |

Required class attributes:

| Attribute | Type | Notes |
| --------- | ---- | ----- |
| `domain_pattern` | `list[str]` | non-empty list of lowercase hostnames |
| `login_at_startup` | `bool` | True triggers a one-shot `.login()` call at startup |
| `name` | `str` | optional; defaults to filename-stem-minus-prefix |

ABC method signatures do NOT take a `driver` parameter. The driver lives on
`self.driver` and is built inside `__init__` (see "Driver construction" below).

## File naming convention

Files placed in `plugins/` follow three rules:

1. **Auto-loaded plugins:** filename starts with `shopbot_plugin_`, ends with
   `.py`. Example: `plugins/shopbot_plugin_amazon.py`.
2. **One plugin class per file.** The registry raises `ImportError` if a
   discovered module defines zero or more than one `RetailerPlugin` subclass.
   Helper functions and private classes are fine; only one concrete subclass.
3. **Other files are skipped.** Files starting with `_` or `__init__.py` are
   silently ignored. Other `.py` files that do NOT start with
   `shopbot_plugin_` emit an INFO log and are skipped. This is why
   `example_plugin.py` exists in `plugins/` without being auto-loaded.

To onboard a new platform: copy `plugins/example_plugin.py` to
`plugins/shopbot_plugin_<your_platform>.py`, change the class name, fill in the
bodies, declare your `domain_pattern`, and run the test suite.

## domain_pattern matching rules

`domain_pattern` is a `list[str]` of ASCII hostnames. Matching follows three
steps inside the registry:

1. Parse the item URL with `urllib.parse.urlparse` to extract the netloc.
2. Lowercase the netloc and strip the port (`amazon.com:443` becomes
   `amazon.com`) and any trailing FQDN dot.
3. For each entry in `domain_pattern`, return True if the normalized netloc
   equals the pattern OR ends with `"." + pattern`. This subdomain anchor
   prevents `evilamazon.com` from matching `amazon.com`.

Examples:

```
domain_pattern = ["amazon.com", "amzn.to"]   # matches Amazon US + the URL shortener
domain_pattern = ["bestbuy.com"]             # matches www.bestbuy.com and bestbuy.com
domain_pattern = ["httpbin.org"]             # the example plugin
```

Use multiple list entries for URL shorteners and per-region TLDs. Internationalized
hostnames must be punycode-encoded (ASCII) when listed.

## Driver construction

Each plugin owns its own Selenium WebDriver, built inside `__init__`:

```python
from driver import build_driver

class MyPlugin(RetailerPlugin):
    def __init__(self, platform_config, *, cvv=None, driver_path=None):
        super().__init__(platform_config)
        self.cvv = cvv
        self.driver = build_driver(driver_path or "chromedriver.exe")
```

`build_driver` is the locked factory from Phase 1. Do not call
`webdriver.Chrome(...)` directly: the factory wires logging, headless mode,
user-agent, and webdriver_manager auto-download.

Two discovered plugins means two Chrome windows open at startup. This is
deliberate (PLG-03): each plugin's driver is isolated so login state, cookies,
and CAPTCHAs do not leak across retailers.

## Reading config

Your plugin receives a per-platform configuration slice during instantiation.
Access it via `self.platform_config`:

```python
email = self.platform_config.credentials.email
password = self.platform_config.credentials.password
```

`platform_config` is the Pydantic `PlatformConfig` instance for your plugin's
`name`, looked up from `AppConfig.platforms[name]`. Never reach for the legacy
config singleton: `from config import config` was retired in Phase 1 and is now
an ImportError tripwire.

Item-level data (URL, quantity, auto-buy flag) lives on the `config` argument
passed to `auto_buy`. Look up the item by URL:

```python
def _lookup_quantity(self, url, config):
    for item in config.available.items:
        if item.link == url:
            return int(item.quantity)
    return 1
```

## Testing your plugin

Minimum coverage for a new plugin:

1. **Import test.** Confirm the module imports cleanly with selenium and
   `build_driver` stubbed. Patterns to copy: `tests/test_plugins_amazon.py`,
   `tests/test_plugins_bestbuy.py`.
2. **Contract test.** Assert the class subclasses `RetailerPlugin`, declares a
   non-empty `domain_pattern`, and defines `check_availability` and
   `auto_buy`. Patterns to copy: `tests/test_plugin_base.py`.
3. **Routing test.** Parametrize a few URLs against `route_url` from
   `plugin_registry` and assert your plugin is selected for in-domain URLs
   and rejected for off-domain URLs.
4. **Driver mock.** Use `monkeypatch.setattr(driver, "build_driver", lambda *a, **kw: sentinel)`
   so tests never spawn Chrome.

Run the full suite with `pytest -x -q` before opening a PR.

## PLUGIN_API_VERSION

`plugin_base.PLUGIN_API_VERSION` is currently `1`. The version is bumped when
the ABC contract changes in a way that breaks existing plugins. Examples that
would force a v2 bump:

* Adding a new abstract method (every plugin must override it).
* Changing a method signature (e.g. adding a required positional argument to
  `check_availability`).
* Changing `domain_pattern` type (e.g. from `list[str]` to a regex object).
* Removing or renaming a class attribute the registry depends on.

Cosmetic changes (docstrings, default no-op behavior) do not bump the version.
If you need a v2 contract, file an issue describing the migration path before
sending a PR.

## Submitting

Plugin contributions go through the standard PR workflow described in the
top-level `CONTRIBUTING.md` (lands in Phase 3). This guide is the *contract*
reference: how to satisfy the ABC and the registry. `CONTRIBUTING.md` is the
*process* reference: how to fork, branch, sign your commits, and respond to
review. The two documents are intentionally separate so this file stays a
stable technical spec.

When you open a PR for a new plugin, include:

* The plugin file at `plugins/shopbot_plugin_<name>.py`.
* A matching test file at `tests/test_plugins_<name>.py`.
* No edits to `main.py`, `plugin_registry.py`, or other plugins (changes there
  indicate the new plugin is reaching outside its boundary).

## Selenium vs nodriver: choosing a driver

ShopPyBot supports two browser-automation drivers behind the same `RetailerPlugin` ABC. Pick one when implementing a new plugin:

| Driver | When to use | Lifecycle |
|--------|-------------|-----------|
| Selenium (via `build_driver`) | Retailer needs manual OTP, passkey, or CAPTCHA-by-typing flows (Amazon-style). `self.driver = build_driver(driver_path, headless=..., user_agents=...)` in `__init__`. | Sync init in `__init__`; `shutdown()` default awaits `asyncio.to_thread(self.driver.quit)`. |
| nodriver (via `await uc.start`) | Retailer has strong anti-bot detection (PerimeterX, Akamai, HUMAN, hCaptcha). Async-native CDP-direct evades many fingerprint surfaces. | Build `self.driver` in `async def open(self)` (ABC default no-op); orchestrator awaits `open()` AFTER `__init__` AND BEFORE the next stagger sleep. Override `shutdown()` to `await self.driver.stop()`. |

### nodriver plugin checklist

1. `import nodriver as uc` at module top
2. `self.driver = None` in `__init__` (driver built in `open()`)
3. Override `async def open(self) -> None: self.driver = await uc.start(headless=..., browser_args=[f"--user-agent={ua}", "--disable-blink-features=AutomationControlled"])`
4. `check_availability` and `auto_buy` are `async def` and call `await self.driver.get(url)` and `await tab.select(...)`
5. Override `async def shutdown(self) -> None` to `await self.driver.stop()` with try/except plus WARNING (no shutdown can crash the orchestrator)
6. DO NOT import `selenium` or any `selenium.*` submodule
7. DO NOT import from `notifier_base` or call `play_*_sound` directly. Notifications fire via the orchestrator's `notification_queue`

### Risky auto-buy gate

Plugins that perform full auto-buy on retailers with aggressive anti-bot protection (Walmart, Target, GameStop, Square Enix, NewEgg) MUST gate the purchase flow behind the `SHOPBOT_ENABLE_RISKY_AUTOBUY` environment variable, read ONCE in `__init__`:

```python
def __init__(self, platform_config, *, cvv=None, driver_path=None, user_agents=None):
    super().__init__(platform_config)
    self._riskyAutoBuyEnabled = (
        os.environ.get("SHOPBOT_ENABLE_RISKY_AUTOBUY", "").strip().lower() == "true"
    )
    # ...

async def auto_buy(self, url, config):
    if not self._riskyAutoBuyEnabled:
        writeLog(
            "<Retailer> auto_buy skipped: set SHOPBOT_ENABLE_RISKY_AUTOBUY=true to enable",
            "WARNING",
        )
        return False
    # actual purchase flow
```

This mirrors the Phase 5 SMS two-lock pattern: cost-bearing actions require both a config opt-in (the item's `auto_buy: true`) AND an env opt-in (`SHOPBOT_ENABLE_RISKY_AUTOBUY=true`). Either alone keeps the plugin in check-only mode.

### Live-retailer integration tests are out of scope

Unit tests MUST mock `nodriver.start` via `AsyncMock(return_value=fakeBrowser)` (see `tests/conftest.py`'s `fakeBrowser` fixture). Spawning Chrome and hitting live retailer PDPs in CI is unreliable (rate limits, IP bans, page reflows) and unsafe (risk of triggering bot detection on the user's IP).

End-to-end verification against live retailers is a manual step the contributor performs at plan-time when writing the plugin.

### PLUGIN_API_VERSION stays at 1

The `open()` and `next_delay()` additions to `RetailerPlugin` in Phase 6 are non-abstract defaults (no-op plus `random.uniform(self.min_delay, self.max_delay)`). Existing Phase 2 plugins continue to work unmodified. Additive defaults do not bump the API version.

## Anti-patterns (Things NOT to do)

These patterns are rejected at code review or fail in the registry. They are
listed in the order you are most likely to hit them:

* **NEVER `from config import config`.** The singleton was retired in Phase 1.
  Read credentials from `self.platform_config.credentials` and item data from
  the `config` argument passed to `auto_buy`.
* **NEVER build a module-level driver.** Construct `self.driver` inside
  `__init__`. A module-level `driver = build_driver(...)` opens Chrome at
  import time, which breaks tests and contradicts PLG-03's per-plugin driver
  ownership.
* **NEVER `sys.path.insert(0, "plugins")`** from inside a plugin. The registry
  uses `importlib.util.spec_from_file_location` and namespaces every plugin
  under `shoppybot_plugins.<stem>`. Path mutation breaks that contract.
* **NEVER re-import `plugin_base` by file path.** Always use the normal
  `from plugin_base import RetailerPlugin`. Re-loading the ABC via importlib
  creates a different class object and breaks `issubclass`.
* **NEVER ship more than one `RetailerPlugin` subclass per file.** The
  registry rejects the import with a clear error. Move helper classes that
  inherit from `RetailerPlugin` into a separate (non-plugin-prefixed) module.
* **NEVER pass a single string for `domain_pattern`.** D-01 locks it as
  `list[str]`. A bare string would iterate character-by-character and match
  nothing useful.
* **NEVER call `update_item_purchased` from `check_availability`.** Only call
  it from `auto_buy` after a confirmed order. Marking on availability check
  silently retires items from the polling list without a real purchase.
* **NEVER swallow exceptions silently.** Catch, log via `writeLog`, and
  return a sensible default (False for availability, False for auto-buy). The
  polling loop wraps your calls in a try/except so a single-URL failure does
  not stop the bot.
* **NEVER print to stdout.** Use `writeLog(message, type)` from `logger`.
  Verbosity is centrally controlled by `debug.logging_level` in `config.yml`.
* **NEVER hardcode credentials.** All secrets come from `config.yml` via the
  Pydantic config schema. Plugin source files must be safe to commit publicly.
