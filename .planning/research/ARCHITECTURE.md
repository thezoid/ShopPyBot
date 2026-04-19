# Architecture Patterns

**Domain:** Python shopping bot — plugin framework + async browser automation
**Researched:** 2026-04-19
**Confidence:** HIGH (plugin patterns, config), MEDIUM (async/driver strategy)

---

## Recommended Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                          main.py                            │
│  asyncio event loop — orchestrates per-platform workers     │
└────────────┬───────────────────────────────────────────────-┘
             │ discovers & loads
             ▼
┌─────────────────────────┐      ┌────────────────────────────┐
│   plugin_registry.py    │      │        config.py           │
│  importlib scan of      │      │  Pydantic AppConfig model  │
│  plugins/*.py           │      │  loaded once at startup    │
│  validates ABC contract │      └────────────────────────────┘
└────────────┬────────────┘
             │ one instance per platform
             ▼
┌──────────────────────────────────────────────────────────────┐
│                     RetailerPlugin (ABC)                     │
│  check_availability(url) → bool                             │
│  auto_buy(driver, url, config) → bool                       │
│  login(driver, config) → None                               │
│  detect_captcha(driver) → bool                              │
│  domain_pattern: str  (class attribute, e.g. "amazon.com")  │
└──────────────┬───────────────────────────────────────────────┘
               │ implemented by
     ┌─────────┼─────────────┐
     ▼         ▼             ▼
 AmazonPlugin BestBuyPlugin WalmartPlugin …
 (plugins/amazon.py) …     (community drops)

     Each plugin owns its own WebDriver instance
     (created by the orchestrator, passed in at call time)

┌──────────────────────────────────────────────────────────────┐
│                   notification/                              │
│   dispatcher.py  ← NotifierABC                              │
│   discord.py     ← DiscordNotifier                          │
│   email.py       ← EmailNotifier                            │
│   sms.py         ← SmsNotifier                              │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                      models.py                               │
│   (unchanged — sqlite3 CRUD, already proven)                │
└──────────────────────────────────────────────────────────────┘
```

---

## Question 1: Plugin Interface — ABC vs Protocol

**Recommendation: Abstract Base Class (ABC), not Protocol.**

Rationale for this specific project:

- Community contributors need *runtime enforcement*. If a plugin author forgets to implement `auto_buy`, the bot must fail loudly at load time with a clear `TypeError: Can't instantiate abstract class ...` message, not silently at 2 AM when an item goes live.
- ABC prevents partial implementations from being registered. Protocol only catches errors at static analysis time (mypy), which contributors likely won't run.
- ABC supports shared concrete helper methods (e.g., a default `detect_captcha` implementation that subclasses can override). Protocol has no mechanism for shared base behavior.
- The interface is narrow (4 methods) so the verbosity cost of `@abstractmethod` decorators is negligible.

```python
# core/plugin_base.py
from abc import ABC, abstractmethod
from selenium.webdriver.remote.webdriver import WebDriver

class RetailerPlugin(ABC):
    """Drop-in interface for retail platform integrations.

    Subclass this, implement all four methods, and place the .py file
    in the plugins/ directory. The bot discovers and registers it automatically.
    """

    # Required class attribute — used for URL routing
    domain_pattern: str  # e.g. "amazon.com", "bestbuy.com"

    @abstractmethod
    def check_availability(self, url: str) -> bool:
        """Return True if the item at url is in stock and purchasable."""

    @abstractmethod
    def auto_buy(self, driver: WebDriver, url: str, config: dict) -> bool:
        """Attempt purchase. Return True if order confirmed. No-op stub is valid."""

    @abstractmethod
    def login(self, driver: WebDriver, config: dict) -> None:
        """Authenticate the session. Called before auto_buy if needed."""

    @abstractmethod
    def detect_captcha(self, driver: WebDriver) -> bool:
        """Return True if a CAPTCHA challenge is present on the current page."""
```

The `domain_pattern` class attribute is intentionally *not* abstract — ABCs cannot enforce class attributes, so validation happens in the registry at load time (see plugin discovery below). This is the established pattern from frameworks like mkdocs plugins.

---

## Question 2: Async + Selenium — One Driver Per Platform

**Recommendation: asyncio event loop + `loop.run_in_executor` + one dedicated WebDriver per platform plugin instance.**

Selenium is fundamentally synchronous and not thread-safe across a shared instance. The correct concurrency model is:

- One `ThreadPoolExecutor` thread per active platform plugin
- Each thread owns its own WebDriver for its entire lifetime (created at startup, not per-check)
- asyncio orchestrates the threads via `loop.run_in_executor`, allowing the main loop to remain async while Selenium calls block their own threads

```
asyncio event loop
    │
    ├─ run_in_executor(thread_amazon)  → AmazonPlugin.check_availability(url)
    ├─ run_in_executor(thread_bestbuy) → BestBuyPlugin.check_availability(url)
    └─ run_in_executor(thread_walmart) → WalmartPlugin.check_availability(url)
```

**Do not share a WebDriver across threads.** The current codebase uses one shared `driver` instance and passes it into every bot function. This must be inverted: each plugin instance holds its own `self.driver` created during plugin initialization.

**Why not Playwright?** Playwright has native async support and is strictly better for new projects. However, the existing Amazon and BestBuy automation is proven Selenium code. Rewriting both platform automations to Playwright while simultaneously adding the plugin framework is two risky changes at once. Recommend: keep Selenium for phase 1 (plugin framework + async), defer Playwright migration to a later phase if performance becomes a concern.

**Driver lifecycle:**

```python
# core/orchestrator.py (simplified)
import asyncio
from concurrent.futures import ThreadPoolExecutor

class Orchestrator:
    def __init__(self, plugins: list[RetailerPlugin]):
        self._plugins = plugins
        self._executor = ThreadPoolExecutor(max_workers=len(plugins))

    async def check_all(self, items: list[Item]) -> list[AvailabilityResult]:
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(self._executor, plugin.check_availability, item.url)
            for item in items
            for plugin in self._plugins
            if plugin.domain_pattern in item.url
        ]
        return await asyncio.gather(*tasks)
```

Each plugin's `__init__` creates and stores its own `WebDriver`. The orchestrator never touches individual drivers — it only calls the plugin interface methods.

---

## Question 3: Notification Dispatcher

**Recommendation: Strategy pattern with a `NotifierABC` base and a `NotificationDispatcher` that holds a list of registered notifiers.**

```python
# notification/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class NotificationEvent:
    item_name: str
    url: str
    platform: str
    event_type: str  # "available" | "purchased" | "captcha"

class NotifierABC(ABC):
    @abstractmethod
    def send(self, event: NotificationEvent) -> None:
        """Deliver notification. Raise on unrecoverable failure."""
```

```python
# notification/dispatcher.py
class NotificationDispatcher:
    def __init__(self, notifiers: list[NotifierABC]):
        self._notifiers = notifiers

    def notify(self, event: NotificationEvent) -> None:
        for notifier in self._notifiers:
            try:
                notifier.send(event)
            except Exception as e:
                # Log failure, continue to next channel — one bad notifier
                # must not suppress the others
                writeLog(f"Notifier {type(notifier).__name__} failed: {e}", "ERROR")
```

Concrete implementations:

```
notification/
    base.py          — NotifierABC, NotificationEvent dataclass
    dispatcher.py    — NotificationDispatcher
    discord.py       — DiscordNotifier (HTTP POST to webhook URL)
    email_notifier.py — EmailNotifier (smtplib, no third-party dep needed)
    sms.py           — SmsNotifier (Twilio REST API)
    sound.py         — SoundNotifier (wraps existing utils.play_available_sound)
```

The `SoundNotifier` wraps the existing `play_available_sound()` so the current audio behavior is preserved as just another notifier channel, not special-cased logic in the orchestrator.

Dispatcher is built from config at startup:

```python
notifiers = []
if config.notifications.discord.enabled:
    notifiers.append(DiscordNotifier(config.notifications.discord.webhook_url))
if config.notifications.email.enabled:
    notifiers.append(EmailNotifier(config.notifications.email))
notifiers.append(SoundNotifier())  # always enabled
dispatcher = NotificationDispatcher(notifiers)
```

This decouples the orchestrator from any knowledge of channels. Adding SMS later is one new file + one config key.

---

## Question 4: Config Schema Evolution

**Recommendation: Pydantic v2 models as the schema layer, loading from the existing YAML file, with additive-only field additions to avoid breaking existing user configs.**

Current flat config:
```yaml
app:
  amz_email: ...
  bb_email: ...
```

Target per-platform config:
```yaml
platforms:
  amazon:
    email: ...
    password: ...
    delays:
      check_interval_seconds: 5
  bestbuy:
    email: ...
    password: ...
    cvv: ...
notifications:
  discord:
    enabled: true
    webhook_url: "https://discord.com/api/webhooks/..."
  email:
    enabled: false
```

**Migration strategy:**

1. Define Pydantic v2 `BaseModel` classes for the full target schema with `model_config = ConfigDict(extra='ignore')` — this silently drops unknown old keys rather than erroring.
2. Add a `load_config()` that reads YAML and validates with the Pydantic model, printing actionable errors on schema violations.
3. At phase start, provide both `sample.config.yml` (new format) and a one-time migration note in the README. There are only a handful of personal users, so no automated migrator is needed.
4. Never remove a top-level key between minor versions — deprecate by keeping it with `model_config` ignoring or aliasing it.

```python
# core/config_schema.py
from pydantic import BaseModel, ConfigDict
from typing import Optional

class AmazonConfig(BaseModel):
    email: str
    password: str
    delays: DelayConfig = DelayConfig()

class PlatformsConfig(BaseModel):
    amazon: Optional[AmazonConfig] = None
    bestbuy: Optional[BestBuyConfig] = None

class AppConfig(BaseModel):
    model_config = ConfigDict(extra='ignore')  # survive old keys
    platforms: PlatformsConfig
    notifications: NotificationsConfig = NotificationsConfig()
    debug: DebugConfig = DebugConfig()
    available: AvailableConfig
```

Pydantic's error messages ("field required", "value is not a valid email") are the user-visible validation layer. No custom validation framework needed.

---

## Question 5: Plugin Discovery

**Recommendation: `importlib` + directory scan + ABC subclass check. No entry_points, no naming conventions.**

The PyPA entry_points pattern (used by pytest, mkdocs) requires the plugin to be an installed package. That's wrong for this project — contributors drop a `.py` file directly. Use `importlib.util.spec_from_file_location` instead:

```python
# core/plugin_registry.py
import importlib.util
import inspect
from pathlib import Path
from core.plugin_base import RetailerPlugin

def discover_plugins(plugins_dir: Path) -> dict[str, RetailerPlugin]:
    """Scan plugins/ directory, load modules, register valid RetailerPlugin subclasses."""
    registry: dict[str, RetailerPlugin] = {}

    for path in plugins_dir.glob("*.py"):
        if path.name.startswith("_"):
            continue  # skip __init__.py, _helpers.py
        spec = importlib.util.spec_from_file_location(path.stem, path)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            writeLog(f"Failed to load plugin {path.name}: {e}", "ERROR")
            continue

        for name, obj in inspect.getmembers(module, inspect.isclass):
            if (issubclass(obj, RetailerPlugin)
                    and obj is not RetailerPlugin
                    and hasattr(obj, "domain_pattern")):
                instance = obj()
                registry[obj.domain_pattern] = instance
                writeLog(f"Registered plugin: {name} -> {obj.domain_pattern}", "INFO")

    return registry
```

Routing in the orchestrator then replaces the current `if "amazon.com" in link / elif "bestbuy.com" in link` chain with:

```python
plugin = next((p for pattern, p in registry.items() if pattern in item.url), None)
if plugin is None:
    writeLog(f"No plugin for URL: {item.url}", "WARNING")
    continue
```

This is O(n plugins) per item check — acceptable for the scale (7-10 platforms). No need for a trie or regex router at this stage.

---

## Component Boundaries

| Component | Responsibility | Communicates With | Location |
|-----------|---------------|-------------------|----------|
| `main.py` | Process entry, bootstrap, asyncio loop start | Orchestrator, config loader | `main.py` |
| `core/orchestrator.py` | Async task dispatch, item-to-plugin routing, result handling | PluginRegistry, NotificationDispatcher, models | `core/` |
| `core/plugin_base.py` | RetailerPlugin ABC definition only | Nothing (no imports from project) | `core/` |
| `core/plugin_registry.py` | Scan plugins/, validate, instantiate, register | plugin_base, all plugins/ | `core/` |
| `core/config_schema.py` | Pydantic AppConfig model, load_config() | yaml, pydantic | `core/` |
| `plugins/amazon.py` | Amazon availability + purchase automation | selenium, plugin_base | `plugins/` |
| `plugins/bestbuy.py` | BestBuy availability + purchase automation | selenium, plugin_base | `plugins/` |
| `notification/base.py` | NotifierABC, NotificationEvent dataclass | Nothing | `notification/` |
| `notification/dispatcher.py` | Fan-out to registered notifiers, swallow per-channel errors | NotifierABC | `notification/` |
| `notification/discord.py` | HTTP POST to Discord webhook | requests, notification/base | `notification/` |
| `notification/email_notifier.py` | SMTP send | smtplib, notification/base | `notification/` |
| `notification/sms.py` | Twilio REST call | twilio, notification/base | `notification/` |
| `notification/sound.py` | Wrap existing pygame audio | pygame, notification/base | `notification/` |
| `models.py` | SQLite CRUD — unchanged | sqlite3 | root (move to `core/` later) |
| `logger.py` | Colorized logging — keep, fix re-read bug | colorama | root (move to `core/` later) |

**Strict rule: plugins/ files import only from `core/plugin_base` and stdlib/selenium.** They must not import from `notification/`, `models`, or `core/orchestrator`. The orchestrator calls them; they don't call back.

---

## Data Flow (Target)

**Startup sequence:**

```
main()
  → load_config() → AppConfig (Pydantic-validated)
  → discover_plugins(Path("plugins/")) → registry dict
  → for each plugin: plugin.__init__() creates its own WebDriver
  → build NotificationDispatcher from config.notifications
  → initialize_db()
  → add_items() seeds SQLite from config.available.items
  → Orchestrator(registry, dispatcher, db)
  → asyncio.run(orchestrator.run_loop())
```

**Per-cycle check (async):**

```
orchestrator.run_loop()
  → get_items() from SQLite
  → filter out purchased items
  → for each unpurchased item, find matching plugin
  → asyncio.gather(run_in_executor(plugin.check_availability, url) for each)
  → for available results:
      → dispatcher.notify(NotificationEvent(available))
      → if item.auto_buy: run_in_executor(plugin.auto_buy, driver, url, config)
          → plugin.login() if not authenticated
          → complete purchase flow
          → update_item_purchased(url)
          → dispatcher.notify(NotificationEvent(purchased))
  → await asyncio.sleep(config.available.check_interval_seconds)
```

**CAPTCHA handling (changed):** The current `input()` blocking call inside Selenium code must be replaced. In the async model, blocking the thread pool thread with `input()` blocks that platform's worker for an unknown duration but does not block other platforms — an improvement over the current all-or-nothing block. However, the preferred approach is to emit a `NotificationEvent(captcha)` and log a prominent warning, then skip that item on the current cycle. Human-in-the-loop CAPTCHA solving can be a later feature if needed.

---

## Suggested Build Order

Dependencies drive the order. Nothing can be built in parallel until its dependencies exist.

### Phase 1: Foundations (no parallelism)

1. **`core/plugin_base.py`** — RetailerPlugin ABC. Zero dependencies on anything else in the project. Every other component depends on this. Build first.

2. **`core/config_schema.py`** — Pydantic AppConfig with new per-platform structure. Must exist before plugins can be initialized (they need config). No dependency on plugin_base.

3. **`core/plugin_registry.py`** — Depends on plugin_base. Needs to exist before orchestrator.

### Phase 2: Plugin Migrations (can proceed once Phase 1 done)

4. **`plugins/amazon.py`** — Refactor existing `amazon_bot.py` to implement RetailerPlugin. Depends on plugin_base. Self-contained Selenium code.

5. **`plugins/bestbuy.py`** — Same refactor for `bestbuy_bot.py`. Parallel with amazon.py refactor.

6. **Fix the BestBuy `update_item_purchased` gap** — Must happen during step 5. Currently BestBuy never marks items purchased after a buy.

### Phase 3: Async Orchestrator

7. **`core/orchestrator.py`** — Depends on plugin_registry (to receive registry), models (for get_items/add_items), notification/dispatcher. This is where asyncio + ThreadPoolExecutor lives.

8. **`main.py` rewrite** — Slim bootstrap that wires everything together. Depends on orchestrator, config, registry.

### Phase 4: Notification System

9. **`notification/base.py` + `notification/dispatcher.py`** — No project dependencies. Can be built any time after Phase 1 but must exist before orchestrator wires it in.

10. **`notification/sound.py`** — Wrap existing `utils.play_available_sound`. Build first as smoke test of the notifier pattern.

11. **`notification/discord.py`** — HTTP POST. Simplest new channel, use as the template for email/SMS.

12. **`notification/email_notifier.py`** and **`notification/sms.py`** — Build after discord.py pattern is established.

### Phase 5: New Plugins

13. **`plugins/walmart.py`**, `plugins/target.py`, etc. — Each is independent. Contributors can work in parallel. The registry discovers them automatically.

### Dependency Graph Summary

```
plugin_base
    ├── plugin_registry
    │       └── orchestrator
    │               └── main (rewrite)
    ├── plugins/amazon
    ├── plugins/bestbuy
    └── plugins/walmart …

config_schema
    └── orchestrator
            └── main (rewrite)

notification/base
    ├── notification/dispatcher
    │       └── orchestrator
    ├── notification/sound
    ├── notification/discord
    ├── notification/email
    └── notification/sms

models (unchanged)
    └── orchestrator
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Shared WebDriver Across Plugins

**What:** Passing a single `driver` into plugin methods, as the current code does.
**Why bad:** Selenium WebDriver is not thread-safe. Concurrent plugin checks will race on `driver.get()`, corrupting each other's page state.
**Instead:** Each plugin instance owns `self.driver`, created in `plugin.__init__()` using the same options currently in `main.py`.

### Anti-Pattern 2: Plugin Importing From Orchestrator or Models

**What:** A plugin calling `update_item_purchased()` directly (as `amazon_bot.py` currently does).
**Why bad:** Creates a circular dependency (orchestrator → plugin → orchestrator-owned model). Also leaks the purchase-tracking concern into the plugin.
**Instead:** Plugins return `bool` from `auto_buy`. The orchestrator owns the `update_item_purchased` call.

### Anti-Pattern 3: Re-reading Config on Every Logger Call

**What:** `logger.py` currently re-reads `config.yml` on every `writeLog()` call to get the log level.
**Why bad:** Disk I/O on every log statement; also breaks when config is Pydantic-validated (file may not match schema at import time).
**Instead:** Pass log level once to `setup_logger()` at startup. Module-level singleton is fine.

### Anti-Pattern 4: sys.stdout Suppression in main()

**What:** Lines 68-75 in current `main.py` redirect stdout/stderr to `/dev/null` to suppress ChromeDriver console noise, then restore them.
**Why bad:** If an exception occurs between suppress and restore, stdout stays dead for the process. Also incompatible with the async orchestrator where driver creation moves into plugin `__init__`.
**Instead:** Suppress ChromeDriver noise via `Service(log_output=subprocess.DEVNULL)` in the Selenium Service constructor.

### Anti-Pattern 5: Config Loaded Twice at Import Time

**What:** `config.py` calls `load_config()` at module import (line 4), and `main()` calls it again independently.
**Why bad:** Two reads of the same file; any mismatch (e.g., file changes between reads) goes undetected. The module-level `config` is a global that can be mutated.
**Instead:** `load_config()` is called once in `main()`, returns a validated `AppConfig` object, and is passed explicitly to every component that needs it (dependency injection, not global import).

---

## Scalability Considerations

| Concern | At 5 platforms (target) | At 20 platforms | At 50 platforms |
|---------|------------------------|-----------------|-----------------|
| Browser memory | 5 Chrome instances (~500MB total) — fine | 20 instances (~2GB) — acceptable | 50 instances — needs driver pooling or Playwright |
| Thread count | 5 threads in executor — trivial | 20 threads — fine | 50 threads — consider asyncio-native browser lib |
| SQLite contention | Single-writer, multi-reader — fine | Fine (read-heavy workload) | Fine |
| Plugin discovery time | ~50ms at startup — negligible | ~100ms — negligible | Still negligible |
| Config complexity | Flat per-platform sections — readable | Still readable | May want per-platform config files |

For the stated scope (7-10 platforms), the ThreadPoolExecutor-per-plugin model with one driver per plugin is correct and does not need a driver pool.

---

## Sources

- Python Packaging User Guide — Creating and Discovering Plugins: https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/
- ABC vs Protocol analysis: https://sinavski.com/post/1_abc_vs_protocols/ | https://levelup.gitconnected.com/python-interfaces-choose-protocols-over-abc-3982e112342e
- Concurrent Selenium with ThreadPoolExecutor: https://testdriven.io/blog/building-a-concurrent-web-scraper-with-python-and-selenium/
- asyncio + run_in_executor for blocking calls: https://superfastpython.com/threadpoolexecutor-vs-asyncio/
- Playwright vs Selenium 2025: https://www.browserless.io/blog/playwright-vs-selenium-2025-browser-automation-comparison
- Pydantic YAML config validation: https://betterprogramming.pub/validating-yaml-configs-made-easy-with-pydantic-594522612db5
- Notification dispatcher / strategy pattern: https://medium.com/interview-simplified/designing-a-beautifully-extensible-notification-service-in-python-c58e4ea49dc7
- pytest pluggy hook architecture: https://medium.com/@garzia.luke/developing-plugin-architecture-with-pluggy-8eb7bdba3303
