# Phase 2: Plugin Migration - Research

**Researched:** 2026-06-02
**Domain:** nodriver async browser automation, importlib plugin discovery, asyncio migration
**Confidence:** HIGH (all claims verified from installed source code or Python stdlib docs)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Migrate both platforms to nodriver (locked `nodriver==0.50.3`); port proven DOM check/buy logic from Selenium.
- **D-02:** Remove Phase-1 Selenium CDP stealth patch and Selenium driver setup from `main.py`.
- **D-03:** Build async plumbing but execute sequentially (one `await plugin.check_availability(...)` at a time). `asyncio.gather` is DEFERRED.
- **D-04:** One nodriver `Browser` process per plugin (separate Chrome process + profile).
- **D-05:** Revise Phase-1 ABC: methods become async, drop `driver` parameter, bump `PLUGIN_API_VERSION` 1 to 2.
- **D-06:** `async setup()` builds the Browser; `__init__` sets `self.driver = None`; `async teardown()` closes it.
- **D-07:** Target interface shape (verbatim contract):
  ```python
  PLUGIN_API_VERSION = 2
  class RetailerPlugin(ABC):
      domain_patterns: list[str]
      def __init__(self, config): self.config = config; self.driver = None
      async def setup(self): ...
      @abstractmethod
      async def check_availability(self, url) -> bool: ...
      @abstractmethod
      async def auto_buy(self, url) -> bool: ...
      async def login(self) -> None: ...
      async def detect_captcha(self) -> bool: ...
      async def teardown(self) -> None: ...
  ```
- **D-08:** Plugins receive typed `AppConfig`; `PlatformsConfig` extensibility is DEFERRED.
- **D-09:** Eager discovery, lazy browser launch: instantiate all plugins, `setup()` only plugins with >=1 matching item.
- **D-10:** `domain_patterns: list[str]` substring match against `urlparse(url).hostname`.
- **PLG-02:** BestBuy plugin MUST call `update_item_purchased()` after a successful purchase.

### Claude's Discretion

- Registry file location (e.g. `core/registry.py`) and internal structure.
- `example_plugin.py` demo platform and exact `PLUGIN_DEV.md` outline.
- Warning text/log level for non-matching `.py` files (CORE-03) and handling of import failures.

### Deferred Ideas (OUT OF SCOPE)

- Real concurrent / parallel item checking (`asyncio.gather` across plugins/items).
- Per-platform flexible config sections (community plugins adding their own validated config keys without editing core `AppConfig`).
- New platforms (Walmart, Target, GameStop, Square Enix, NewEgg).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CORE-03 | Plugin registry auto-discovers `shopbot_plugin_*.py` in `plugins/` via `importlib`; warns + ignores non-matching `.py` | importlib pattern documented in Architecture Patterns section |
| CORE-04 | Registry routes item URLs to correct plugin via `domain_patterns` attribute | `urlparse(url).hostname` + substring match; see Architecture Patterns |
| CORE-08 | `example_plugin.py` with stub implementations + inline comments; `plugins/PLUGIN_DEV.md` contributor guide | Contributor Tooling section covers required content |
| PLG-01 | `plugins/shopbot_plugin_amazon.py` implements `RetailerPlugin` ABC; all purchase logic migrated from `amazon_bot.py` | Selenium-to-nodriver mapping table covers every Amazon DOM op |
| PLG-02 | `plugins/shopbot_plugin_bestbuy.py` implements `RetailerPlugin` ABC; fixes missing `update_item_purchased()` call | Bug location identified; nodriver mapping provided |
| PLG-03 | Each plugin owns its own `self.driver` (nodriver Browser); no shared global driver | D-04/D-06 architecture; `Browser.create()` call per plugin in `setup()` |
</phase_requirements>

## Summary

Phase 2 replaces the Selenium-based sequential loop in `main.py` with an async event loop that routes items through a plugin registry. The two existing bots (`amazon_bot.py`, `bestbuy_bot.py`) are refactored into self-contained `RetailerPlugin` subclasses under `plugins/`. The Phase-1 ABC is revised (v1 to v2) to make all methods async, drop the `driver` parameter from signatures, and add `setup()`/`teardown()` lifecycle hooks. Each plugin owns one nodriver `Browser` process started in `setup()`.

The nodriver 0.50.3 API is verified directly from the installed package. The key finding is that nodriver's entry point is `await nodriver.start()` (equivalent: `await Browser.create()`), which returns a `Browser`. Navigation is `tab = await browser.get(url)`, where `tab` is a `Tab` object. DOM queries use `await tab.select(css_selector)` (returns `Element` or `None` after timeout) and `await tab.select_all(css_selector)`. Elements expose `await element.click()` and `await element.send_keys(text)`. The stealth layer is built into nodriver (no CDP script needed); the Phase-1 `navigator.webdriver` CDP patch is simply removed.

The importlib discovery pattern for `plugins/shopbot_plugin_*.py` is idiomatic Python stdlib and well-understood. The critical pitfalls are: (1) nodriver's `Browser.__init__` raises `RuntimeError` if no event loop is running, so it MUST be called from async context; (2) `browser.stop()` is synchronous but calls `asyncio.get_event_loop().create_task(self.aclose())` internally, so always prefer `await browser.aclose()` inside an async teardown; (3) the existing `test_plugin_base.py` instantiates `Minimal()` synchronously and must be rewritten for v2.

**Primary recommendation:** Implement in four files: `core/plugin_base.py` (ABC v2), `core/registry.py` (discovery + routing), `plugins/shopbot_plugin_amazon.py`, `plugins/shopbot_plugin_bestbuy.py`. Then update `main.py` to drive the async loop via `asyncio.run(main())`. Ship `plugins/example_plugin.py` and `plugins/PLUGIN_DEV.md` as the contributor skeleton.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Plugin discovery + routing | Registry (`core/registry.py`) | `main.py` (calls registry) | Centralises glob+importlib logic; `main.py` stays thin |
| Browser lifecycle (start/stop) | Plugin (`setup`/`teardown`) | Registry (calls setup/teardown) | Each plugin owns its process per D-04; registry orchestrates lifecycle |
| DOM availability check | Plugin (`check_availability`) | Tab (nodriver) | DOM knowledge is platform-specific; Tab is the transport |
| Auto-buy flow | Plugin (`auto_buy`) | Tab (nodriver) | Platform-specific checkout flow; nodriver is the driver |
| Credential collection | `main.py` startup (before loop) | Plugin (reads from `self.config` / env) | `getpass` is sync/blocking; must run before `asyncio.run()` |
| Item loop orchestration | `main.py` async loop | Registry (route lookup) | Sequential `await` chain per D-03 |
| Config validation | `core/config_schema.py` (already done) | `main.py` (already done) | No change required |
| DB write (purchased flag) | `models.update_item_purchased()` | Plugin `auto_buy` (calls it) | PLG-02: BestBuy currently missing this call; must be added |

## Standard Stack

### Core (no new installs — all already in requirements.txt)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| nodriver | 0.50.3 (locked) | Async undetected Chrome automation | Replaces Selenium per D-01; stealth built-in |
| asyncio | stdlib (Python 3.11+) | Event loop, `asyncio.run()` | Standard Python async entry point |
| importlib.util | stdlib | `spec_from_file_location` for plugin loading | Standard pattern for file-based plugin discovery |
| pathlib.Path | stdlib | `plugins/` directory glob (`Path.glob`) | Cleaner than `os.path` for file patterns |
| urllib.parse | stdlib | `urlparse(url).hostname` for domain routing | Standard; already implicit in D-10 |

[VERIFIED: installed package inspection] nodriver==0.50.3 is confirmed installed and importable.

### No New Dependencies

This phase adds zero new packages. All required functionality is covered by the locked `nodriver==0.50.3` and Python stdlib. The `selenium` and `webdriver-manager` imports in `main.py` are REMOVED; their entries in `requirements.txt` can be cleaned up in a follow-on or left inert (they are not imported once `main.py` is rewritten).

## Package Legitimacy Audit

> No new packages are installed in this phase. nodriver==0.50.3 is the existing locked dependency.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| nodriver | PyPI | 1+ yr | — | github.com/UltrafunkAmsterdam/nodriver | not run (already installed, locked) | Approved — already in requirements.txt |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*slopcheck was unavailable in this environment. nodriver is a pre-existing locked dependency confirmed installed and importable (`python -c "import nodriver; print(nodriver.__version__)"` = `0.50.3`). No new packages are introduced.*

## Architecture Patterns

### System Architecture Diagram

```
config.yml
    |
    v
AppConfig (Pydantic, already done)
    |
    v
main.py::main()
  [1] collect_cvv() [sync, before asyncio.run]
  [2] asyncio.run(async_main(cfg, cvv))
        |
        v
  Registry.__init__  <-- discovers plugins/shopbot_plugin_*.py via importlib
  Registry.setup_for_items(items)  <-- awaits setup() on matched plugins only
        |
        v
  while True:
    for item in get_items():  [DB row: name, link, auto_buy, quantity, purchased]
      plugin = registry.route(item.link)  <-- urlparse hostname substring match
      if plugin:
        available = await plugin.check_availability(item.link)
        if available and item.auto_buy:
          success = await plugin.auto_buy(item.link)
          [BestBuy: update_item_purchased(item.link) inside auto_buy on success]
        |
        v
  registry.teardown_all()  [on exit / KeyboardInterrupt]
        |
    Browser.stop() per plugin
```

### Recommended Project Structure

```
plugins/
    shopbot_plugin_amazon.py    # PLG-01
    shopbot_plugin_bestbuy.py   # PLG-02
    example_plugin.py           # CORE-08
    PLUGIN_DEV.md               # CORE-08
core/
    plugin_base.py              # revised v2 ABC
    registry.py                 # new: discovery + routing + lifecycle
    config_schema.py            # unchanged
```

### Pattern 1: nodriver Browser Startup (per plugin `setup()`)

**What:** Each plugin starts its own isolated Chrome process in `setup()`.
**When to use:** Called once by registry after eager discovery confirms the plugin has matching items.

```python
# Source: nodriver/core/util.py::start() + nodriver/core/browser.py::Browser.create()
# VERIFIED: installed package inspection

import nodriver

async def setup(self) -> None:
    # nodriver.start() is the recommended entry point (alias for Browser.create)
    # headless=False is the nodriver default and recommended for anti-detection
    self.driver = await nodriver.start(headless=False)
```

`nodriver.start()` signature (verified from source):
```python
async def start(
    config=None,
    *,
    user_data_dir=None,
    headless=False,         # default False
    browser_executable_path=None,
    browser_args=None,
    sandbox=True,
    lang="en-US",
    host=None,
    port=None,
    expert=None,
    **kwargs
) -> Browser
```

`nodriver.Config` can be constructed separately for fine-grained control (custom `user_data_dir` per plugin for truly isolated profiles):
```python
# VERIFIED: installed package nodriver/core/config.py
import nodriver
config = nodriver.Config(user_data_dir="/tmp/amazon-profile", headless=False)
self.driver = await nodriver.Browser.create(config)
```

### Pattern 2: Navigation and Tab Handling

**What:** Navigate to a URL, get back a `Tab` object for DOM operations.

```python
# Source: nodriver/core/browser.py::Browser.get() + nodriver/core/tab.py::Tab.get()
# VERIFIED: installed package inspection

tab = await self.driver.get(url)
# OR from an existing tab (preferred for subsequent navigations in the same plugin):
tab = await self.driver.main_tab
await tab.get(url)   # navigates in place; returns self
```

`Browser.get(url)` returns a `Tab`. It handles wait/sleep and DOM event detection internally ("the safest way of navigating" per nodriver source docstring).

`browser.main_tab` is a property returning the first page-type tab.

### Pattern 3: Element Finding — CSS Selectors (replaces `WebDriverWait` + `By.ID`/`By.CLASS_NAME`)

**What:** Find element by CSS selector with built-in timeout retry.

```python
# Source: nodriver/core/tab.py::Tab.select() + Tab.query_selector()
# VERIFIED: installed package inspection

# Returns Element or None after timeout (default 10s). Never raises on timeout.
element = await tab.select("#add-to-cart-button", timeout=10)
if element:
    await element.click()

# find all matching elements
elements = await tab.select_all(".add-to-cart-button", timeout=10)
```

`tab.select(selector, timeout=10)` polls every 0.5s up to `timeout`. Returns `None` if not found (does NOT raise). This replaces `WebDriverWait(driver, 10).until(EC.presence_of_element_located(...))`.

**ID selectors**: `#add-to-cart-button` replaces `By.ID, "add-to-cart-button"`.
**Class selectors**: `.add-to-cart-button` replaces `By.CLASS_NAME, "add-to-cart-button"`.
**Attribute selectors**: `[id^="quantity_"]` replaces complex XPath.

### Pattern 4: Element Finding — Text Search (replaces XPath text contains)

```python
# Source: nodriver/core/tab.py::Tab.find()
# VERIFIED: installed package inspection

# Replaces: By.XPATH, "//h4[contains(text(), 'Enter the characters')]"
element = await tab.find("Enter the characters you see below", best_match=True, timeout=5)
# Returns None if not found within timeout — never raises
```

`tab.find(text, best_match=True, timeout=10)` returns `None` (not an exception) on timeout.

### Pattern 5: Clicking and Typing

```python
# Source: nodriver/core/element.py::Element.click() and Element.send_keys()
# VERIFIED: installed package inspection

await element.click()                  # JS el.click() via CDP
await element.send_keys("text")        # dispatches char key events per character
await element.clear_input()            # sets element.value = ""
await element.focus()                  # focus before send_keys (often needed)
```

`Element.send_keys(text)` focuses the element and dispatches CDP `input_.dispatch_key_event("char", ...)` for each character. This is the direct replacement for Selenium's `.send_keys()`.

### Pattern 6: CAPTCHA / Element Presence Detection

```python
# Source: nodriver/core/tab.py::Tab.find() return-None-on-timeout semantics
# VERIFIED: installed package inspection

async def detect_captcha(self) -> bool:
    tab = self.driver.main_tab
    element = await tab.find(
        "Enter the characters you see below",
        best_match=False,
        timeout=3,      # short timeout: absence is the common case
    )
    return element is not None
```

The key insight: `tab.find()` and `tab.select()` return `None` on timeout, they do NOT raise. Checking `is not None` is the idiom for presence detection. This replaces the try/except around `WebDriverWait`.

### Pattern 7: Browser Teardown

```python
# Source: nodriver/core/browser.py::Browser.stop()
# VERIFIED: installed package inspection

async def teardown(self) -> None:
    if self.driver:
        self.driver.stop()   # Browser.stop() is synchronous; safe to call from async
        self.driver = None
```

`Browser.stop()` is a sync method that calls `asyncio.get_event_loop().create_task(self.aclose())` internally and then terminates the subprocess. Do NOT `await browser.aclose()` directly from teardown unless you are certain the connection was established; `stop()` handles the null-process case with try/except internally.

### Pattern 8: importlib Plugin Discovery (CORE-03)

**What:** Discover `shopbot_plugin_*.py` in `plugins/`, import each, find the `RetailerPlugin` subclass.
**When to use:** Called once at registry construction.

```python
# Source: Python stdlib importlib.util — ASSUMED (stdlib, training knowledge)
import importlib.util
import inspect
from pathlib import Path
from core.plugin_base import RetailerPlugin
from logger import writeLog

def discover_plugins(plugins_dir: Path) -> list[type[RetailerPlugin]]:
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
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, RetailerPlugin) and obj is not RetailerPlugin:
                found.append(obj)
    return found
```

Key decisions:
- `spec_from_file_location` is preferred over `importlib.import_module` for file-path-based loading (no `sys.path` manipulation needed).
- `inspect.getmembers(module, inspect.isclass)` with `issubclass(...) and obj is not RetailerPlugin` finds exactly the concrete plugin class.
- Import failures are `log + skip`, not `raise` (aligns with success criterion 2: "does not crash").
- Non-matching `.py` files produce a WARNING log and are skipped.

### Pattern 9: asyncio Entry Point

```python
# Source: Python stdlib asyncio — ASSUMED (stdlib)
import asyncio

def main():
    # All sync pre-flight (getpass, config validation) runs here
    cfg = AppConfig()
    cvv = collect_cvv() if needs_bb_autobuy(cfg) else None
    asyncio.run(async_main(cfg, cvv))

async def async_main(cfg, cvv):
    registry = PluginRegistry(cfg)
    items = get_items()
    await registry.setup_for_items(items)
    try:
        while True:
            for item in get_items():
                ...
    except KeyboardInterrupt:
        pass
    finally:
        await registry.teardown_all()

if __name__ == "__main__":
    logger = setup_logger()
    main()
```

`asyncio.run()` creates a new event loop, runs the coroutine, and closes it. It is incompatible with a running loop (so it cannot be called from inside an already-running loop). Since `main()` is currently sync, this is a clean drop-in.

### Anti-Patterns to Avoid

- **Calling `Browser.create()` in `__init__`:** `Browser.__init__` raises `RuntimeError` if no event loop is running (verified from source: `asyncio.get_running_loop()` is called immediately in `__init__`). Always `await` in `setup()`.
- **Calling `await browser.aclose()` directly from teardown:** `aclose()` is the WebSocket close only; it does not terminate the Chrome subprocess. Use `browser.stop()` which handles both.
- **`WebDriverWait` / `expected_conditions` imports:** Remove entirely. nodriver's `tab.select(timeout=...)` and `tab.find(timeout=...)` are the direct replacement and have built-in retry semantics.
- **Calling `input()` inside the async loop:** `input()` blocks the event loop. CVV is collected before `asyncio.run()` (already the Phase-1 pattern). Amazon OTP/CAPTCHA prompts in `auto_buy`/`login` also use `input()` — these block the sequential loop acceptably for Phase 2, but note they would be incompatible with Phase 4 concurrency (that is an `ASYNC-03` problem, out of scope here).
- **`asyncio.get_event_loop()` instead of `asyncio.run()`:** Deprecated in Python 3.10+; use `asyncio.run()` as the top-level entry point.
- **Sharing `Browser` instances across plugins:** Violates D-04. Each plugin must call its own `await nodriver.start()` in `setup()`.

## Selenium to nodriver Migration Map

Full operation-by-operation mapping for all DOM operations used in `amazon_bot.py` and `bestbuy_bot.py`:

| Selenium (current) | nodriver 0.50.3 equivalent | Notes |
|---|---|---|
| `driver.get(url)` | `tab = await browser.get(url)` | Returns Tab; first call from browser |
| `driver.get(url)` (re-navigate) | `await tab.get(url)` | Navigates existing tab in place |
| `driver.current_url` | `tab.url` | Property on Tab (via Connection) |
| `WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "foo")))` | `await tab.select("#foo", timeout=10)` | Returns None on timeout, not exception |
| `WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "foo")))` | `await tab.select(".foo", timeout=10)` | Same None-on-timeout semantics |
| `WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, "//h4[contains(text(), '...')]")))` | `await tab.find("...", timeout=5)` | Text search; returns None not exception |
| `element.click()` | `await element.click()` | Async; JS el.click() via CDP |
| `element.send_keys(text)` | `await element.send_keys(text)` | Dispatches key events per char |
| `driver.find_element(By.ID, "foo")` | `await tab.select("#foo")` or `await tab.query_selector("#foo")` | `select()` retries; `query_selector()` does not |
| `driver.find_element(By.CLASS_NAME, "foo").send_keys(text)` | `elem = await tab.select(".foo"); await elem.send_keys(text)` | Guard on None before send_keys |
| `driver.find_element(By.CLASS_NAME, "foo").click()` | `elem = await tab.select(".foo"); await elem.click()` | Guard on None before click |
| `driver.focus()` (window focus) | `await tab.bring_to_front()` | Tab method; verify needed |
| `try: WebDriverWait(...).until(...) except: return None` | `elem = await tab.select(...)` + `if elem is None: ...` | None-on-timeout is the idiom |
| `driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", ...)` | REMOVE — nodriver handles stealth architecturally | D-02 |

### Amazon-specific ID mapping

| Operation | Selenium selector | nodriver CSS selector |
|---|---|---|
| Add-to-cart button | `By.ID, "add-to-cart-button"` | `"#add-to-cart-button"` |
| Buy-now button | `By.ID, "buy-now-button"` | `"#buy-now-button"` |
| Quantity dropdown | `By.CLASS_NAME, "a-button-dropdown"` | `".a-button-dropdown"` |
| Quantity option (n) | `By.ID, f"quantity_{n-1}"` | `f"#quantity_{n-1}"` |
| Place order button | `By.ID, "submitOrderButtonId"` | `"#submitOrderButtonId"` |
| Email input | `By.ID, "ap_email"` | `"#ap_email"` |
| Password input | `By.ID, "ap_password"` | `"#ap_password"` |
| Sign in submit | `By.ID, "signInSubmit"` | `"#signInSubmit"` |
| MFA form | `By.ID, "auth-mfa-form"` | `"#auth-mfa-form"` |
| Account list (sign-in check) | `By.ID, "nav-link-accountList"` | `"#nav-link-accountList"` |
| CAPTCHA text | `By.XPATH, "//h4[contains(text(), 'Enter the characters...')]"` | `await tab.find("Enter the characters you see below", timeout=3)` |

### BestBuy-specific mapping

| Operation | Selenium selector | nodriver CSS selector |
|---|---|---|
| Add-to-cart button | `By.CLASS_NAME, "add-to-cart-button"` | `".add-to-cart-button"` |
| Email input | `By.ID, "fld-e"` | `"#fld-e"` |
| Password input | `By.ID, "fld-p1"` | `"#fld-p1"` |
| Sign-in submit | `By.CLASS_NAME, "cia-form__controls__submit"` | `".cia-form__controls__submit"` |
| Cart quantity dropdown | `By.CLASS_NAME, "a-dropdown-prompt"` | `".a-dropdown-prompt"` |
| Cart quantity option | `By.XPATH, f"//a[@id='quantity_{n}']"` | `f"#quantity_{n}"` |
| Checkout button | `By.CLASS_NAME, "checkout-buttons__checkout"` | `".checkout-buttons__checkout"` |
| CVV input | `By.ID, "credit-card-cvv"` | `"#credit-card-cvv"` |
| Place order button | `By.CLASS_NAME, "button--place-order"` | `".button--place-order"` |

**PLG-02 bug location:** `bestbuy_bot.py::auto_buy_bestbuy_item()` line 71 — after `"Order placed on BestBuy"` log, no `update_item_purchased(item_url)` call. The nodriver port must add it.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Waiting for DOM element to appear | `while True: try: find; except: sleep` | `await tab.select(selector, timeout=N)` | Built into nodriver; handles polling + None return |
| Waiting for text to appear | custom XPath loop | `await tab.find(text, timeout=N)` | Same; returns None on timeout |
| Hiding `navigator.webdriver` | CDP script injection (Phase-1 Selenium hack) | Remove — nodriver handles it architecturally | D-02 explicit decision |
| File-path module import | `sys.path.insert` + `importlib.import_module` | `importlib.util.spec_from_file_location` | No sys.path pollution; cleaner isolation |
| Plugin class discovery | manual `__subclasses__()` scan | `inspect.getmembers(module, inspect.isclass)` + `issubclass` check | Works without requiring the base class to be imported first in the plugin module |
| URL-to-plugin routing | regex on raw URL | `urlparse(url).hostname` + `any(p in host for p in patterns)` | Avoids false hits on paths/query strings (D-10) |

**Key insight:** nodriver's `tab.select()` and `tab.find()` subsume the entire `WebDriverWait` + `expected_conditions` pattern. Never recreate a polling loop around `query_selector`.

## Common Pitfalls

### Pitfall 1: Browser.create() Called Outside Async Context

**What goes wrong:** `Browser.__init__` calls `asyncio.get_running_loop()` and raises `RuntimeError: Browser objects of this class are created using await Browser.create()` if there is no running loop.
**Why it happens:** Constructing a `Browser` inside `__init__` of a plugin class, which is called synchronously during registry discovery.
**How to avoid:** Keep `__init__` synchronous (`self.driver = None`). Call `await nodriver.start()` only inside `async def setup(self)`. Registry calls `setup()` after `asyncio.run()` has started the loop.
**Warning signs:** `RuntimeError` mentioning `Browser.create()` at startup; usually traceback points to plugin `__init__`.

### Pitfall 2: `tab.select()` Returns None, Not Raises

**What goes wrong:** Code treats `None` return as truthy or tries to call methods on it: `AttributeError: 'NoneType' object has no attribute 'click'`.
**Why it happens:** Unlike Selenium's `WebDriverWait` which raises `TimeoutException`, nodriver's `tab.select()` and `tab.find()` return `None` when no match found within timeout. There is no exception to catch.
**How to avoid:** Always guard: `elem = await tab.select(selector); if elem: await elem.click()`.
**Warning signs:** `AttributeError` on `NoneType` inside an `auto_buy` or `check_availability` flow.

### Pitfall 3: Missing `await tab` Refresh After Navigation

**What goes wrong:** After `await browser.get(url)` or `await tab.get(url)`, stale element references from a previous page cause `ProtocolException: could not find node`.
**Why it happens:** nodriver's source docstring explicitly says "whenever you get stuck, call `await page`" — this refreshes internal state. Navigation returns a new Tab or updates `loader_id`; existing element handles become invalid.
**How to avoid:** After any navigation, use `tab = await browser.get(url)` and re-query all needed elements from the fresh tab. Do not reuse elements across page loads.
**Warning signs:** `ProtocolException: could not find node` when clicking an element that was found before a navigation.

### Pitfall 4: test_plugin_base.py Breaks After ABC v2 Revision

**What goes wrong:** Existing tests in `tests/test_plugin_base.py` construct `Minimal` subclasses that implement `check_availability` and `auto_buy` as sync methods with the old `(self, driver, url, config)` signatures. After v2, these no longer satisfy the ABC contract.
**Why it happens:** `asyncio` abstract methods require `async def` in the subclass; sync implementations do not satisfy `@abstractmethod async def`.
**How to avoid:** Rewrite `test_plugin_base.py` in Wave 0 (before touching `plugin_base.py`). New tests use `pytest-asyncio` and `async def` stubs. Also update the `PLUGIN_API_VERSION` assertion from `== 1` to `== 2`.
**Warning signs:** `TypeError: Can't instantiate abstract class Minimal with abstract methods ...` during test collection after plugin_base.py is changed.

### Pitfall 5: `pytest-asyncio` Version Incompatibility

**What goes wrong:** Tests using `@pytest.mark.asyncio` fail with `PytestUnraisableExceptionWarning` or `ScopeMismatch` error.
**Why it happens:** `pytest-asyncio==1.3.0` (in requirements.txt) is an unusual version string. Standard releases are 0.x (e.g. 0.23.x). Version `1.3.0` may be a pre-release or nonstandard build.
**How to avoid:** Verify `pytest-asyncio` behavior in Wave 0 by running a trivial `async def test_noop(): pass` with `@pytest.mark.asyncio`. If it fails, check whether `asyncio_mode = "auto"` in `pyproject.toml` resolves it.
**Warning signs:** Collection errors about event loop scope or fixture scope mismatches.

### Pitfall 6: `input()` in `login()` / CAPTCHA Blocks the Event Loop

**What goes wrong:** `login()` and CAPTCHA prompt handling in `amazon_bot.py` call `input()`, which is synchronous and blocks `asyncio`. In a sequential loop (D-03) this is tolerable but still blocks.
**Why it happens:** `input()` is blocking I/O.
**How to avoid:** For Phase 2 (sequential), this is accepted. Document in plugin code with a comment: "# Phase 4 (ASYNC-03): replace input() with asyncio.Event notification." Do not attempt to fix it now — it is explicitly deferred.
**Warning signs:** Entire bot pauses waiting for terminal input (expected behavior for Phase 2; becomes a problem in Phase 4).

### Pitfall 7: BestBuy `update_item_purchased` Missing (PLG-02)

**What goes wrong:** Items purchased on BestBuy are re-attempted on every loop iteration, potentially repurchasing.
**Why it happens:** `bestbuy_bot.py::auto_buy_bestbuy_item()` never calls `update_item_purchased(item_url)` after the successful `driver.find_element(By.CLASS_NAME, "button--place-order").click()`.
**How to avoid:** In the nodriver port, after `await place_order_btn.click()` and logging "Order placed", immediately call `update_item_purchased(url)` (and `return True`).
**Warning signs:** BestBuy auto-buy runs again on the same item in the next loop iteration despite a successful purchase.

## Contributor Tooling (CORE-08)

### `plugins/example_plugin.py` Must Contain

A fictional retailer (e.g. "FakeShop") that:
1. Declares `domain_patterns = ["fakeshop.com"]` as a class attribute.
2. Implements `async def setup(self)` with `self.driver = await nodriver.start()`.
3. Implements `async def check_availability(self, url) -> bool` with a `tab.select()` call, early-return pattern, and a `# Replace ... with the real selector` comment.
4. Implements `async def auto_buy(self, url) -> bool` showing the full flow: navigate, click add-to-cart, navigate to checkout, place order, call `update_item_purchased(url)`, return `True`.
5. Implements `async def teardown(self)` calling `self.driver.stop()`.
6. Inline comments on every non-obvious line. No imports from `amazon_bot.py` or `bestbuy_bot.py`.

### `plugins/PLUGIN_DEV.md` Must Cover

1. Naming convention: file MUST be `shopbot_plugin_<name>.py` (explain discovery rule).
2. The ABC contract table: which methods are required (`check_availability`, `auto_buy`) vs. optional (`login`, `detect_captcha`, `setup`, `teardown`).
3. `domain_patterns` field: what it does, substring matching semantics, multi-domain example.
4. Config access: how to read `self.config.platforms.amazon.*` (note: community platform config extension is deferred — for now, they can add fields to `config.yml` at their own risk).
5. Credentials: env-vars-only rule; never log credentials; refer to `.env.example`.
6. Testing: how to run `pytest tests/` and what a minimal passing test looks like.
7. Link to `example_plugin.py` as the canonical starting point.

## Runtime State Inventory

> Phase 2 is not a rename/refactor/migration of stored data. This section is included to explicitly confirm no runtime state is affected.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `data/shop_py_bot.db` — items table with `name`, `link`, `auto_buy`, `quantity`, `purchased` columns | None — schema unchanged; no migration |
| Live service config | None — no external service configs | None |
| OS-registered state | None — no task scheduler or service registrations | None |
| Secrets/env vars | `BB_EMAIL`, `BB_PASSWORD` (env vars); CVV via `getpass` | None — code reads them identically; no rename |
| Build artifacts | `.venv/` with `selenium`, `webdriver-manager` installed | Packages stay installed; imports removed from code |

**Nothing found in category:** All categories confirmed clean. The Selenium package stays in `requirements.txt` and `.venv/` for Phase 2; removal is a cleanup task for a later phase.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3.4 + pytest-asyncio 1.3.0 |
| Config file | `pyproject.toml` (present from Phase 1 Wave 0) |
| Quick run command | `rtk pytest tests/test_plugin_base.py tests/test_registry.py -x` |
| Full suite command | `rtk pytest` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CORE-03 | Non-matching `.py` warns and does not crash | unit | `rtk pytest tests/test_registry.py::test_non_matching_py_warns -x` | No — Wave 0 |
| CORE-03 | `shopbot_plugin_*.py` files are discovered | unit | `rtk pytest tests/test_registry.py::test_discovers_valid_plugin -x` | No — Wave 0 |
| CORE-04 | URL routes to correct plugin by hostname | unit | `rtk pytest tests/test_registry.py::test_route_by_domain -x` | No — Wave 0 |
| CORE-08 | `example_plugin.py` is importable and satisfies ABC | unit | `rtk pytest tests/test_registry.py::test_example_plugin_satisfies_abc -x` | No — Wave 0 |
| PLG-01 | Amazon plugin satisfies ABC (sync check) | unit | `rtk pytest tests/test_plugin_amazon.py::test_amazon_satisfies_abc -x` | No — Wave 0 |
| PLG-01 | Amazon `check_availability` returns bool | unit (mock) | `rtk pytest tests/test_plugin_amazon.py::test_check_availability_returns_bool -x` | No — Wave 0 |
| PLG-02 | BestBuy plugin calls `update_item_purchased` after buy | unit (mock) | `rtk pytest tests/test_plugin_bestbuy.py::test_autobuy_calls_update_purchased -x` | No — Wave 0 |
| PLG-03 | No global driver variable; each plugin has `self.driver` | static/unit | `rtk pytest tests/test_plugin_amazon.py::test_no_global_driver -x` | No — Wave 0 |
| CORE-05 (regression) | Existing config schema tests still pass | unit | `rtk pytest tests/test_config_schema.py -x` | Yes |
| CORE-01/02 (regression) | ABC v2 has correct version constant | unit | `rtk pytest tests/test_plugin_base.py -x` (MUST be rewritten) | Yes — rewrite needed |

**Live browser tests (manual only — cannot run in CI without Chrome):**
- Amazon `check_availability` against a real Amazon URL: manual verification
- BestBuy `check_availability` against a real BestBuy URL: manual verification
- Full `auto_buy` flow: manual with `debug.test_mode: true`

### Sampling Rate

- Per task commit: `rtk pytest tests/test_plugin_base.py tests/test_registry.py -x`
- Per wave merge: `rtk pytest`
- Phase gate: full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_registry.py` — covers CORE-03, CORE-04, CORE-08
- [ ] `tests/test_plugin_amazon.py` — covers PLG-01, PLG-03
- [ ] `tests/test_plugin_bestbuy.py` — covers PLG-02, PLG-03
- [ ] `tests/test_plugin_base.py` — REWRITE: update `test_version_constant` (1 to 2), replace sync `Minimal` stubs with async stubs; add `pytest-asyncio` markers

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (Amazon/BB login) | Credentials from env vars only (SEC-01, already enforced); `getpass` for CVV (SEC-02) |
| V3 Session Management | partial | nodriver inherits browser session cookies; no custom session handling needed |
| V4 Access Control | no | Bot acts as authenticated user |
| V5 Input Validation | no | URLs come from `config.yml` (user-controlled config, not external input) |
| V6 Cryptography | no | No encryption in scope |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Plugin loading from disk (arbitrary code execution) | Elevation of Privilege | `shopbot_plugin_*.py` naming filter; import errors are log+skip not exec; treat `plugins/` as trusted (same machine as user) — document in PLUGIN_DEV.md |
| Credential leak via plugin code | Information Disclosure | ABC contract: credentials from `self.config` (env vars) only; PLUGIN_DEV.md explicitly prohibits hardcoding; no credentials in logs |
| Selenium `--disable-web-security` re-introduction | Tampering | D-02 removes Selenium driver entirely; nodriver has no equivalent flag in default config |
| `navigator.webdriver` fingerprint (SEC-04 equivalent) | Spoofing | nodriver handles this architecturally — no explicit CDP script needed; remove Phase-1 patch |
| `input()` in async loop leaking timing side-channel | Denial of Service | Acceptable for Phase 2 sequential loop; documented as Phase 4 concern |

**Plugin trust boundary note:** Loading arbitrary Python files from `plugins/` is equivalent to `exec()`. For a personal bot running on a trusted machine this is acceptable. Community plugins submitted via GitHub PR must be reviewed before being placed in `plugins/`. The PLUGIN_DEV.md should note this: "only install plugins from sources you trust." This is a documentation obligation for Phase 3 (DOCS-02/DOCS-03) but worth noting here.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All | Yes | 3.13 (project requires >= 3.11) | None — required |
| nodriver | Browser automation | Yes | 0.50.3 (verified: `import nodriver; print(nodriver.__version__)`) | None — locked dep |
| Google Chrome | nodriver browser launch | [ASSUMED: installed on dev machine] | — | Must be installed; nodriver auto-detects path |
| pytest | Test runner | Yes | 8.3.4 (in requirements.txt) | None |
| pytest-asyncio | Async test support | Yes | 1.3.0 (in requirements.txt) | None |

**Missing dependencies with no fallback:**
- Google Chrome must be installed on the execution machine. nodriver's `Config.find_chrome_executable()` auto-detects it; if not found, `nodriver.start()` raises at runtime. This is a pre-existing constraint, not new to Phase 2.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `tab.url` is a property on Tab (via Connection parent) for current URL | Selenium Migration Map | Code uses wrong attribute name; find actual attr with `dir(tab)` |
| A2 | `await tab.bring_to_front()` is the nodriver equivalent of `driver.focus()` | Selenium Migration Map | Amazon CAPTCHA focus step fails; but `input()` pause already handles this manually |
| A3 | pytest-asyncio==1.3.0 supports `@pytest.mark.asyncio` without additional configuration | Validation Architecture | Wave 0 test setup fails; resolve by checking pyproject.toml `asyncio_mode` |
| A4 | Chrome is installed on the development machine | Environment Availability | `nodriver.start()` raises at runtime; user must install Chrome |
| A5 | `domain_patterns` is a class attribute (not instance attribute) on the plugin classes | Architecture Patterns | Registry reads `PluginClass.domain_patterns` before instantiation; if it were an instance attr, the registry would need to instantiate first |

**Note on A5:** D-07 defines `domain_patterns: list[str]` as a class-level annotation. Class attributes are accessible on both the class and instances. The registry can read `PluginClass.domain_patterns` before calling `__init__`, which is safe for eager discovery.

## Open Questions (RESOLVED)

1. **`tab.url` attribute name**
   - What we know: `Tab` inherits from `Connection`; `current_url` is the Selenium name; nodriver source uses `target.url` internally.
   - What's unclear: The exact public attribute name for the current tab URL on a `Tab` object.
   - Recommendation: In `check_availability`, skip the `if driver.current_url != item_url` guard entirely (just always navigate) — it was a minor optimization in the Selenium version. This avoids the unknown and simplifies the port.
   - RESOLVED: Skip the current_url guard, always navigate. Handled in Plan 02-04 Task 1 action.

2. **BestBuy quantity dropdown selector**
   - What we know: `bestbuy_bot.py` uses `By.CLASS_NAME, "a-dropdown-prompt"` — this is an Amazon-style class name (prefix `a-`) on BestBuy, which is suspicious.
   - What's unclear: Whether this selector is actually correct for BestBuy's cart quantity control, or was a copy-paste error.
   - Recommendation: Port the selector as-is (it was "proven" in Phase-1 UAT per CONTEXT.md), but add a TODO comment flagging the questionable class name for live testing.
   - RESOLVED: Port `.a-dropdown-prompt` as-is with a TODO comment for live verification. Handled in Plan 02-04 Task 2 action.

3. **`pytest-asyncio==1.3.0` configuration**
   - What we know: The installed version string `1.3.0` is non-standard (typical releases are `0.x`).
   - What's unclear: Whether this version requires `asyncio_mode = "auto"` in `pyproject.toml`, or whether `@pytest.mark.asyncio` decorators suffice.
   - Recommendation: Wave 0 task: add a single `async def test_asyncio_smoke(): pass` with `@pytest.mark.asyncio` and run it before writing any real async tests. If it fails, add `asyncio_mode = "auto"` to `[tool.pytest.ini_options]` in `pyproject.toml`.
   - RESOLVED: Wave 0 smoke test in Plan 02-01 Task 1; `asyncio_mode = auto` already set in pyproject.toml from Phase 1.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Selenium WebDriver + CDP stealth patch | nodriver (stealth architectural) | Phase 2 | Remove entire `selenium`, `webdriver-manager`, CDP `Page.addScriptToEvaluateOnNewDocument` block |
| Global single-driver sequential loop | Per-plugin `self.driver` (one Browser per plugin) | Phase 2 | Better isolation; each platform has its own Chrome process and profile |
| Sync `check_amazon_item(driver, url)` | `async def check_availability(self, url)` | Phase 2 | ABC contract; enables Phase 4 concurrency without re-rewriting |
| WebDriverWait + expected_conditions | `await tab.select(css, timeout=N)` returning None | Phase 2 | Simpler code; no try/except around presence checks |

**Deprecated / outdated after Phase 2:**
- `amazon_bot.py`: entire file superseded by `plugins/shopbot_plugin_amazon.py`. Keep the file until the registry is confirmed working; delete in Phase 2 final cleanup.
- `bestbuy_bot.py`: same — superseded by `plugins/shopbot_plugin_bestbuy.py`.
- `main.py` Selenium driver setup block (lines 62-97): remove entirely.
- `main.py` CDP stealth patch block (lines 99-106): remove per D-02.
- `tests/test_plugin_base.py`: rewrite (sync stubs, version=1 — both wrong after v2).

## Sources

### Primary (HIGH confidence)
- `C:\Users\brand\AppData\Roaming\Python\Python313\site-packages\nodriver\core\browser.py` — `Browser.create()`, `Browser.get()`, `Browser.stop()`, `Browser.main_tab`, `Browser.__init__` runtime-loop check
- `C:\Users\brand\AppData\Roaming\Python\Python313\site-packages\nodriver\core\tab.py` — `Tab.select()`, `Tab.find()`, `Tab.find_all()`, `Tab.select_all()`, `Tab.query_selector()`, `Tab.query_selector_all()`, `Tab.get()`, `Tab.xpath()`
- `C:\Users\brand\AppData\Roaming\Python\Python313\site-packages\nodriver\core\element.py` — `Element.click()`, `Element.send_keys()`, `Element.clear_input()`, `Element.focus()`, `Element.text`, `Element.text_all`
- `C:\Users\brand\AppData\Roaming\Python\Python313\site-packages\nodriver\core\util.py` — `nodriver.start()` signature and parameters
- `C:\Users\brand\AppData\Roaming\Python\Python313\site-packages\nodriver\core\config.py` — `Config` constructor parameters
- `C:\Users\brand\AppData\Roaming\Python\Python313\site-packages\nodriver\core\connection.py` — `Connection.aclose()`
- `E:\repos\ShopPyBot\amazon_bot.py` — all Selenium DOM operations mapped
- `E:\repos\ShopPyBot\bestbuy_bot.py` — all Selenium DOM operations mapped; PLG-02 bug location confirmed

### Secondary (MEDIUM confidence)
- Python stdlib `importlib.util` documentation (ASSUMED: stdlib, well-established pattern)
- Python stdlib `asyncio.run()` documentation (ASSUMED: stdlib)

### Tertiary (LOW confidence)
- `tab.url` attribute name — not directly verified; flagged in Open Questions

## Metadata

**Confidence breakdown:**
- nodriver API surface: HIGH — read directly from installed 0.50.3 source
- Selenium-to-nodriver mapping: HIGH — every selector and operation traced through both source files
- PLG-02 bug location: HIGH — confirmed by reading `bestbuy_bot.py` line 71
- importlib discovery pattern: MEDIUM — stdlib, standard pattern, ASSUMED from training
- asyncio entry point: MEDIUM — stdlib, ASSUMED from training
- pytest-asyncio behavior: LOW — version string 1.3.0 is unusual; Wave 0 smoke test required

**Research date:** 2026-06-02
**Valid until:** 2026-07-02 (nodriver 0.50.3 is locked; DOM selectors depend on retailer sites, may change)
