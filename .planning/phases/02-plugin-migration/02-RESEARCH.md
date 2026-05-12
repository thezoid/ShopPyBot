# Phase 2: Plugin Migration - Research

**Researched:** 2026-05-12
**Domain:** Python plugin discovery (importlib), ABC subclass detection, URL routing, Selenium plugin refactor
**Confidence:** HIGH (codebase fully read; importlib/inspect patterns are stdlib stable; one MEDIUM area noted below)

## Summary (planner-actionable takeaways)

1. **The ABC needs a one-line edit before Phase 2 plans land.** `plugin_base.py:22` currently declares `domain_pattern: str = ""`. D-01 locks `domain_pattern: list[str]`. The first plan in Phase 2 (or a pre-task in plan 01) must change this attribute type and update `tests/test_plugin_base.py` accordingly. Skipping this will cause every subsequent plugin migration to silently violate the locked contract. [VERIFIED: read plugin_base.py + 02-CONTEXT.md D-01]
2. **Use `importlib.util.spec_from_file_location` + `module_from_spec` + `exec_module` for discovery.** It is the only one of the three viable approaches that does not require `plugins/` to be a Python package, does not mutate `sys.path`, and gives the registry full control over the module name (preventing `sys.modules` collisions). [CITED: docs.python.org/3/library/importlib.html#importing-a-source-file-directly]
3. **Subclass detection: `inspect.getmembers(module, inspect.isclass)` filtered by `issubclass(cls, RetailerPlugin) and cls.__module__ == module.__name__`.** The `__module__` check excludes the re-imported `RetailerPlugin` ABC itself and any other plugin classes imported from sibling files. Per CONTEXT.md D-02 ("one plugin class per file"), discovering more than one local subclass is a hard import-time error.
4. **URL matching must lower-case both sides and strip ports.** `urlparse("https://Amazon.Com:443/dp/X").netloc` is `"Amazon.Com:443"` (case preserved, port included). A `normalize_netloc` helper that lower-cases and strips `:port` is required for D-01 matching to behave correctly. [VERIFIED: docs.python.org/3/library/urllib.parse.html#urllib.parse.urlparse]
5. **Existing source is small and migrates cleanly.** `amazon_bot.py` is 192 lines (3 functions); `bestbuy_bot.py` is 73 lines (3 functions). BestBuy never calls `update_item_purchased()` — PLG-02 adds it inside `auto_buy()` after the place-order click, mirroring Amazon (`amazon_bot.py:184`). [VERIFIED: read both files]
6. **`main.py` poll loop refactor is ~15 lines.** Replace lines 124-129 (the `if "amazon.com" in link` chain) with `plugin = route_url(link, registry); plugin.check_availability(link) ...`. The two `_handle_amazon`/`_handle_bestbuy` helpers are deleted entirely. Login calls happen once between `build_driver` and the `while True:` loop.
7. **Phase 1 left `bestbuy_bot.py` untouched** (per 01-06-SUMMARY.md "Decisions"). It still uses positional `email/password/cvv` args (not the AppConfig instance). The migration must consume `self.platform_config.credentials` instead. Amazon already reads from `config.platforms['amazon'].credentials` so it migrates more directly.
8. **`PlatformConfig` schema has no `items` field.** Item URLs live at `app_config.available.items[*].link` — a flat list across all platforms. The Phase B coverage check (D-04) iterates that single list, not a per-platform structure. [VERIFIED: read config_schema.py lines 22-44]
9. **`config.py` is now an ImportError tripwire** (per 01-06-SUMMARY.md). Plugins MUST NOT `from config import config`. They receive `platform_config` via `__init__` per Phase 1 D-02.
10. **Driver construction inside `__init__` blocks at startup.** Two plugins discovered → two Chrome windows open before `main()` enters the polling loop. This is the locked behavior (PLG-03, D-02), but plans must call it out as a deliberate UX change vs. Phase 1's single shared driver.

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** `domain_pattern: list[str]` of hostname strings; matched via `urlparse(url).netloc.endswith(pattern)` per entry, lowercase compare. Empty list is a configuration error surfaced at import time.
- **D-02:** Hard cut. `amazon_bot.py` and `bestbuy_bot.py` are deleted after the new plugins pass import + smoke tests. No fallback path.
- **D-03:** Per-plugin opt-in login: each plugin declares `login_at_startup: bool = False` class attribute. Registry calls `.login()` on every plugin where `login_at_startup is True` once at startup, before the polling loop. Amazon and BestBuy both opt in.
- **D-04:** Two-phase load. Phase A: discover/import each `plugins/shopbot_plugin_*.py`; catch import errors, log warning, skip the failed file. Phase B: verify every URL in `app_config.available.items` has a matching plugin; hard-fail with actionable error if not.
- **Naming:** `plugins/shopbot_plugin_*.py` only. `example_plugin.py` is intentionally NOT auto-loaded (filename prefix mismatch). Hidden/dunder files ignored silently; other non-matching `.py` files emit a warning.
- **One plugin class per file.** Registry expects exactly one `RetailerPlugin` subclass per module.
- **Selenium retained** for Phase 2. The `build_driver` factory from Phase 1 is reused inside each plugin's `__init__`.
- **PLG-02:** BestBuy `update_item_purchased()` call goes inside `auto_buy()` after the place-order confirmation, mirroring Amazon (`amazon_bot.py:184`).
- **PLUGIN_DEV.md scope:** technical contract reference only. Higher-level community guidance defers to `CONTRIBUTING.md` in Phase 3.

### Claude's Discretion
- Registry module name and exact API shape (`plugin_registry.py` recommended).
- Whether the registry surfaces as a function call returning a list, or a module-level singleton.
- `example_plugin.py` body: working "echo" plugin vs. pure stubs.
- `PLUGIN_DEV.md` section depth.
- Plugin instantiation timing (at-discovery recommended; matches D-03 startup flow).

### Deferred Ideas (OUT OF SCOPE)
- Async/concurrent plugin polling (Phase 4)
- nodriver replacement (Phase 6)
- Plugin hot-reload, sandboxing, anti-detection difficulty ratings (v2 backlog)
- New platforms (Walmart, Target, GameStop, Square Enix, NewEgg) — Phase 6

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CORE-03 | Plugin registry auto-discovers `shopbot_plugin_*.py` via importlib; warns on non-matching `.py` files | Q1 (discovery pattern), Q2 (subclass detection), Q9 (anti-patterns) |
| CORE-04 | Registry routes item URLs via `domain_pattern` | Q3 (urlparse edge cases), Q6 (poll-loop refactor) |
| CORE-08 | `example_plugin.py` + `plugins/PLUGIN_DEV.md` | Q7, Q8 |
| PLG-01 | `plugins/shopbot_plugin_amazon.py` implements ABC; migrates all amazon_bot.py logic | Q4 (source shape), Q10 (Phase 1 touchpoints) |
| PLG-02 | `plugins/shopbot_plugin_bestbuy.py` implements ABC; fixes missing `update_item_purchased()` call | Q4 (call site identified) |
| PLG-03 | Each plugin owns its own WebDriver via `self.driver` in `__init__` | Q10 (build_driver wiring) |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Plugin file discovery | Registry module (`plugin_registry.py`) | filesystem | Single owner; main.py calls into it once at startup |
| Subclass extraction from imported module | Registry module | `inspect` stdlib | Same module owns load+extract to keep import-error handling local |
| URL → plugin routing | Registry module | `urllib.parse` | Helper `route_url(url, registry)` returns `RetailerPlugin | None` |
| Coverage check (Phase B of D-04) | Registry module | AppConfig consumer | Reads `app_config.available.items`, raises on miss |
| Plugin lifecycle (`__init__`, `login`) | Plugin classes | `driver.build_driver` | Plugins own driver per PLG-03 |
| Polling loop dispatch | `main.py` | Registry | main.py keeps the `while True:` loop; defers routing to registry |
| Purchase tracking | `models.update_item_purchased` | Plugin `auto_buy` | Plugin calls models directly after successful order |

---

## Q1: importlib plugin discovery pattern

**Recommendation: `importlib.util.spec_from_file_location` + `module_from_spec` + `exec_module`.**

### Comparison

| Approach | Requires `plugins/` to be a package | Mutates `sys.path` | Controls module name | Verdict |
|----------|-------------------------------------|---------------------|-----------------------|---------|
| `spec_from_file_location` + `exec_module` | No | No | Yes (caller-chosen) | ✅ Recommended |
| `pkgutil.iter_modules` + `import_module` | Yes (needs `__init__.py`) | Possibly (caller must add `plugins/` to path) | No (uses package.module) | ⚠️ Works but adds package boilerplate |
| `__import__` / bare `import_module` on a string | Yes | Yes | No | ❌ Rejected (sys.path mutation) |

### Reference implementation

```python
# plugin_registry.py
import importlib.util
import inspect
import sys
from pathlib import Path
from plugin_base import RetailerPlugin
from logger import writeLog

PLUGIN_PREFIX = "shopbot_plugin_"

def _load_module(path: Path):
    # Unique module name prevents sys.modules collisions if a plugin file
    # is named the same as a stdlib/third-party module (e.g. "shopbot_plugin_email").
    mod_name = f"shoppybot_plugins.{path.stem}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not build spec for {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module  # required for dataclasses / pickling inside the plugin
    spec.loader.exec_module(module)  # may raise; caller decides whether to skip or fail
    return module
```

### Pitfalls

1. **sys.modules pollution / collision.** Naming the module after the file stem alone (e.g. `shopbot_plugin_amazon`) can collide with a real top-level package on PyPI. Namespacing under `shoppybot_plugins.<stem>` avoids that. [CITED: docs.python.org/3/library/importlib.html#importing-a-source-file-directly]
2. **Double-load on re-discovery.** If `discover()` is called twice, `exec_module` runs the file twice, producing two distinct class objects that fail `is` comparison. Guard by checking `sys.modules` first, or only call `discover()` once at startup (recommended).
3. **`sys.path` mutation.** Tempting to do `sys.path.insert(0, plugins_dir)` and `import_module`. Don't — it pollutes the import namespace globally and breaks reproducibility in tests.

---

## Q2: Subclass detection inside an imported module

**Recommendation:**

```python
def _find_plugin_class(module) -> type[RetailerPlugin]:
    candidates = [
        cls for _, cls in inspect.getmembers(module, inspect.isclass)
        if issubclass(cls, RetailerPlugin)
        and cls is not RetailerPlugin
        and cls.__module__ == module.__name__
    ]
    if len(candidates) == 0:
        raise ImportError(f"{module.__name__}: no RetailerPlugin subclass found")
    if len(candidates) > 1:
        names = ", ".join(c.__name__ for c in candidates)
        raise ImportError(f"{module.__name__}: expected one plugin class, found {len(candidates)}: {names}")
    return candidates[0]
```

### Why each filter matters

| Filter | Without it |
|--------|-----------|
| `issubclass(cls, RetailerPlugin)` | Picks up unrelated classes defined in the file |
| `cls is not RetailerPlugin` | Returns the ABC itself if the plugin does `from plugin_base import RetailerPlugin` |
| `cls.__module__ == module.__name__` | Picks up plugin classes the file imported from sibling plugin files (cross-plugin contamination); also excludes the re-imported ABC even though identity already excludes it |

### Trap to avoid (HIGH severity)

**Identity of `RetailerPlugin` after `spec_from_file_location` is preserved.** Some early importlib trickery (loading the same module multiple times under different names) produces a NEW class object that is `issubclass(cls, RetailerPlugin)` False even though it looks identical. As long as the plugin module is loaded once and imports `from plugin_base import RetailerPlugin` (no re-loading of `plugin_base`), `issubclass` works. Plans must explicitly forbid plugins from re-importing `plugin_base` via file path. [CITED: docs.python.org/3/reference/import.html#submodules]

### One vs. many classes per file

CONTEXT.md D-02 ("one plugin class per file"): hard-fail on more than one. The reference implementation above does this. Do NOT silently take the first match — that creates a footgun where contributors copy-paste an example class and accidentally ship two plugins from one file.

---

## Q3: `urlparse().netloc` matching edge cases

`urlparse("https://Amazon.Com:443/dp/X").netloc` returns `"Amazon.Com:443"` — case preserved, port included, no normalization. [VERIFIED: docs.python.org/3/library/urllib.parse.html]

### Edge cases that affect `.endswith(pattern)`

| URL | Naive `.endswith("amazon.com")` | Issue |
|-----|---------------------------------|-------|
| `https://Amazon.Com/dp/X` | False | Case difference |
| `https://amazon.com:443/dp/X` | False | Port suffix breaks endswith |
| `https://www.amazon.com/dp/X` | True | OK — subdomain handled by endswith |
| `https://evilamazon.com/dp/X` | True | **False positive** — endswith matches without dot boundary |
| `https://amzn.to/abc` | False | Needs both `amazon.com` and `amzn.to` in domain_pattern list (D-01 supports this) |
| `https://amazon.com./dp/X` (trailing dot) | False | RFC-allowed trailing dot in FQDN |

### Recommended helper

```python
# plugin_registry.py
from urllib.parse import urlparse

def _normalize_netloc(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    # Strip optional port (":443", ":80"). userinfo "@" is also possible but not realistic for product URLs.
    if ":" in netloc:
        netloc = netloc.split(":", 1)[0]
    # Strip trailing dot (RFC 1034 FQDN form).
    if netloc.endswith("."):
        netloc = netloc[:-1]
    return netloc

def _matches(netloc: str, pattern: str) -> bool:
    p = pattern.lower().lstrip(".")
    # Anchor with leading dot to avoid evilamazon.com matching amazon.com.
    return netloc == p or netloc.endswith("." + p)
```

### Test rows (planner: turn these into pytest parametrize)

| URL | domain_pattern | expected |
|-----|----------------|----------|
| `https://www.amazon.com/dp/X` | `["amazon.com"]` | True |
| `https://Amazon.Com:443/dp/X` | `["amazon.com"]` | True |
| `https://evilamazon.com/dp/X` | `["amazon.com"]` | False |
| `https://amzn.to/abc` | `["amazon.com", "amzn.to"]` | True |
| `https://www.bestbuy.com/site/X.p` | `["amazon.com"]` | False |

### Confidence: HIGH for behavior, MEDIUM for "is this exhaustive"

I have not verified behavior for IDN/punycode hostnames (`xn--...`) — Amazon and BestBuy don't use them, but a future plugin might. Plans should note this as a known limitation and document that contributors must use ASCII (punycode) hostnames in `domain_pattern`.

---

## Q4: Existing source code shape

### `amazon_bot.py` (192 lines)

| Function | Lines | Migrates to | Notes |
|----------|-------|-------------|-------|
| `detect_captcha(driver)` | 10-17 | `AmazonPlugin.detect_captcha(self) -> bool` | Drop driver arg; use `self.driver`. Currently called from `main.py` (`_handle_amazon` line 53) AND from `check_amazon_item` (line 24) — the migration consolidates to a single ABC override. |
| `check_amazon_item(driver, url)` | 19-54 | `AmazonPlugin.check_availability(self, url)` | Add-to-cart OR buy-now button presence = available. Already has the CAPTCHA pause inline. Drop driver arg. |
| `amz_sign_in(driver, config)` | 56-121 | `AmazonPlugin.login(self, config)` | Reads `config.platforms['amazon'].credentials.email/.password`. Has TWO `input()` blocks (passkey, OTP) that block startup — preserve. |
| `auto_buy_amazon_item(driver, url, config, quantity, test_mode)` | 123-192 | `AmazonPlugin.auto_buy(self, url, config)` | Calls `amz_sign_in` then quantity→buy-now→place-order chain. Quantity comes from item, not arg — plugin can read it from the item lookup (see Q6). Calls `update_item_purchased(item_url)` on success (line 184). `test_mode` comes from `self.platform_config` or stays an `auto_buy` arg — planner decides. |

### `bestbuy_bot.py` (73 lines)

| Function | Lines | Migrates to | Notes |
|----------|-------|-------------|-------|
| `check_bestbuy_item(driver, url)` | 7-25 | `BestBuyPlugin.check_availability(self, url)` | Add-to-cart class-name presence check. Trivial port. |
| `bb_sign_in(driver, email, password)` | 27-38 | `BestBuyPlugin.login(self, config)` | Currently takes positional creds; new signature reads from `self.platform_config.credentials`. |
| `auto_buy_bestbuy_item(driver, url, email, password, cvv, quantity)` | 40-73 | `BestBuyPlugin.auto_buy(self, url, config)` | **PLG-02 fix:** insert `update_item_purchased(item_url)` immediately after line 71 (`writeLog("Order placed on BestBuy", "SUCCESS")`). |

### What does NOT migrate

- The `if "amazon.com" in link` / `if "bestbuy.com" in link` dispatcher in `main.py` (lines 124-127) and the `_handle_amazon` / `_handle_bestbuy` helpers (lines 50-89) — replaced by registry routing.
- `from amazon_bot import ...` / `from bestbuy_bot import ...` import block in `main.py` lines 19-20.
- The `detect_captcha(driver)` call sites in `main.py` line 53 — moves into the plugin's `check_availability`.
- `_deprecated/` folder content (called out in 01-CONTEXT.md as a scrub candidate; out of Phase 2 scope unless planner chooses to wrap in).

### Dead code / duplication

- `detect_captcha` is currently both a module-level function in `amazon_bot.py` AND called as part of `check_amazon_item`. The duplication is harmless but the migration should pick one location (recommend: as the ABC override only; have `check_availability` call `self.detect_captcha()`).
- BestBuy currently has no CAPTCHA detection. Leave the no-op default from `RetailerPlugin.detect_captcha` (returns False). Do NOT add a stub override.

---

## Q5: Plugin test patterns (no Chrome required)

### Discovery test pattern

Existing `tests/conftest.py` provides `tmp_path` via pytest builtin and `tmp_config_yml` fixture. Add a new fixture:

```python
# tests/conftest.py addition
@pytest.fixture
def tmp_plugins_dir(tmp_path):
    """Empty plugins/ dir for registry tests. Tests write plugin files into it."""
    d = tmp_path / "plugins"
    d.mkdir()
    return d
```

### Writing a minimal valid plugin from a test

```python
# tests/test_plugin_registry.py
def test_discover_finds_valid_plugin(tmp_plugins_dir):
    (tmp_plugins_dir / "shopbot_plugin_test.py").write_text(
        "from plugin_base import RetailerPlugin\n"
        "class TestPlugin(RetailerPlugin):\n"
        "    domain_pattern = ['test.example.com']\n"
        "    login_at_startup = False\n"
        "    def __init__(self, platform_config):\n"
        "        super().__init__(platform_config)\n"
        "        self.driver = None  # no real driver in tests\n"
        "    def check_availability(self, url): return False\n"
        "    def auto_buy(self, url, config): return False\n"
    )
    from plugin_registry import discover
    plugins = discover(tmp_plugins_dir, platform_configs={"test": None})
    assert len(plugins) == 1
    assert plugins[0].__class__.__name__ == "TestPlugin"
```

### Mocking `webdriver.Chrome` for plugin `__init__` tests

```python
def test_amazon_plugin_constructs_driver(monkeypatch):
    fake_driver = object()
    monkeypatch.setattr("driver.build_driver", lambda *a, **kw: fake_driver)
    from plugins.shopbot_plugin_amazon import AmazonPlugin
    p = AmazonPlugin(platform_config=...)
    assert p.driver is fake_driver
```

This requires the plugin to import `build_driver` via a path the test can monkeypatch — i.e. `from driver import build_driver` then call `build_driver(...)` (test patches the name in `driver` module). Patching `plugins.shopbot_plugin_amazon.build_driver` also works if the plugin does `from driver import build_driver`.

### Cross-plugin routing test

```python
@pytest.mark.parametrize("url,expected_class", [
    ("https://www.amazon.com/dp/X", "AmazonPlugin"),
    ("https://Amazon.Com:443/dp/X", "AmazonPlugin"),
    ("https://www.bestbuy.com/site/X.p", "BestBuyPlugin"),
    ("https://evilamazon.com/dp/X", type(None)),  # no match
])
def test_route_url(url, expected_class, registry_with_both_plugins):
    plugin = route_url(url, registry_with_both_plugins)
    assert (plugin.__class__.__name__ if plugin else None) == expected_class
```

Use a session-scoped fixture that monkeypatches `build_driver` once and constructs both plugins.

---

## Q6: `main.py` poll-loop refactor shape

### Before (`main.py` lines 117-129)

```python
while True:
    writeLog("Starting new iteration of item checks", "INFO")
    for item in get_items():
        name, link, auto_buy, quantity, purchased = item
        if purchased: ...; continue
        if "amazon.com" in link:
            _handle_amazon(driver, name, link, auto_buy, quantity, app_config, test_mode, open_browser)
        elif "bestbuy.com" in link:
            _handle_bestbuy(driver, name, link, auto_buy, quantity, app_config, cvvs, test_mode, open_browser)
        else:
            writeLog(f"Unsupported URL: {link}", "WARNING")
```

### After (recommended)

```python
from plugin_registry import discover, route_url, verify_coverage

# ... after collect_cvvs, before initialize_db ...
registry = discover(Path("plugins"), platform_configs=app_config.platforms, cvvs=cvvs)
verify_coverage(registry, app_config.available.items)  # raises if any URL has no plugin

for plugin in registry:
    if plugin.login_at_startup:
        plugin.login(app_config)

initialize_db()
# ... add_items ...

while True:
    writeLog("Starting new iteration of item checks", "INFO")
    for item in get_items():
        name, link, auto_buy, quantity, purchased = item
        if purchased:
            continue
        plugin = route_url(link, registry)
        if plugin is None:
            writeLog(f"Unsupported URL (no plugin): {link}", "WARNING")
            continue
        try:
            if plugin.check_availability(link):
                play_available_sound()
                writeLog(f"{name} is available: {make_tiny(link)}", "SUCCESS")
                if auto_buy and not test_mode:
                    plugin.auto_buy(link, app_config)
                    play_buy_sound()
                elif open_browser:
                    webbrowser.open(link)
        except Exception as e:
            writeLog(f"Plugin {type(plugin).__name__} raised on {link}: {e}", "ERROR")
            continue  # do not stop the loop on a single-URL failure
```

### Decisions encoded above

- **Discovery happens once, before the loop.** Two Chrome windows open at startup (one per plugin per PLG-03/D-02). Deliberate.
- **`verify_coverage` is between discovery and login.** Coverage check must precede login (don't waste time on a 30-second Amazon OTP if a typo'd BestBuy URL is going to crash the bot anyway).
- **Login calls happen after coverage check.** Per D-03 `login_at_startup` opt-in.
- **Loop catches plugin exceptions and continues** (mirrors current `try/except` behavior in `check_amazon_item` line 52). This is NOT a D-04 case (D-04 covers import-time isolation, not runtime). State explicitly in the plan that runtime plugin failures log + continue; do not abort the loop.
- **Quantity is no longer passed to `auto_buy`.** The ABC signature is `auto_buy(self, url, config)`. The plugin reads quantity by looking up the item in `config.available.items` by URL. Alternatively the planner can extend the ABC signature with `quantity: int` — but D-01 / Phase 1 D-01 lock the current signature, so the lookup approach is correct.

---

## Q7: PLUGIN_DEV.md outline (sections only, not content)

Per CONTEXT.md: "Phase 2 owns the technical contract reference. Higher-level 'how to contribute' lives in CONTRIBUTING.md (Phase 3) and should be linked, not duplicated."

Recommended outline:

1. **What is a plugin?** — one-paragraph intro; link forward to CONTRIBUTING.md placeholder.
2. **The contract** — `RetailerPlugin` ABC: required methods (`check_availability`, `auto_buy`), default no-op methods (`login`, `detect_captcha`), class attributes (`domain_pattern: list[str]`, `login_at_startup: bool`).
3. **File naming convention** — `plugins/shopbot_plugin_<name>.py`; one plugin class per file; `example_plugin.py` is the starter template (not auto-loaded).
4. **`domain_pattern` matching rules** — list of lowercase hostnames; `.endswith` with subdomain anchor; how to handle URL shorteners (multiple entries).
5. **Driver construction** — call `build_driver(driver_path, log_path)` in `__init__`; store on `self.driver`; do NOT use a shared global driver.
6. **Reading config** — `self.platform_config` is the per-platform slice (`AppConfig.platforms[<name>]`); never `from config import config`.
7. **Testing your plugin** — minimum: import test, `check_availability` with mock driver, `domain_pattern` parametrize for known URLs. Reference `tests/test_plugin_base.py` for ABC contract tests.
8. **`PLUGIN_API_VERSION`** — current value, what would trigger a v2 bump.
9. **Submitting** — link to CONTRIBUTING.md (Phase 3 placeholder line OK for now).

Keep total length under ~200 lines. Code blocks should reference `example_plugin.py` rather than re-inlining full examples.

---

## Q8: `example_plugin.py` shape

**Recommendation: working "echo" plugin against `https://httpbin.org/html` (or similar inert public endpoint).**

### Rationale

- Pure stubs with `pass` and `# TODO` comments invite copy-paste bugs (contributors don't learn the integration shape).
- A working example that hits `httpbin.org/html` and reports "available" if `<h1>` is present teaches: driver lifecycle, `urlparse` matching, `writeLog` calls, return value semantics — without requiring credentials or a real retailer.
- `auto_buy` returns False with a `writeLog("auto-buy not implemented for example", "INFO")` — demonstrating the "check-only plugin" pattern.
- `login_at_startup = False`, `login` uses the inherited no-op.

### Why not a local stub server

A fixture server (Flask, FastAPI) adds test dependencies and a teardown story. `httpbin.org` is well-known, stable, and contributors can read the URL and immediately understand the example. (HIGH confidence on httpbin stability — operated by Postman, [CITED: httpbin.org]).

### Shape

```python
# plugins/example_plugin.py
"""Example RetailerPlugin. NOT auto-discovered (filename prefix mismatch).
Copy to plugins/shopbot_plugin_<your_platform>.py to start a new plugin."""
from plugin_base import RetailerPlugin
from driver import build_driver
from logger import writeLog
# ~40 lines of working code with inline comments explaining each piece
```

The file lives at `plugins/example_plugin.py`. Discovery sees it, observes the filename does not start with `shopbot_plugin_`, and emits a single INFO log: `"Skipped example_plugin.py (not auto-loaded — copy to shopbot_plugin_<name>.py to enable)"`. This makes the skip behavior visible to first-time users.

---

## Q9: Anti-patterns to encode as `must_haves.truths`

1. **NEVER `from config import config` inside a plugin.** Phase 1 retired `config.py` as an ImportError tripwire. Plugins receive `platform_config` via `__init__`.
2. **NEVER construct a shared `driver` at module-import time.** PLG-03 requires `self.driver` built inside `__init__`. Module-level `driver = build_driver(...)` would open Chrome at `import` time during discovery — wrong lifecycle and unprovably testable.
3. **NEVER import `plugin_base.py` by file path** from inside a plugin. Always `from plugin_base import RetailerPlugin` (normal import). Re-loading `plugin_base` via importlib creates a different class object and breaks `issubclass`.
4. **NEVER `sys.path.insert(0, "plugins")`** in the registry. Use `spec_from_file_location` and namespace under `shoppybot_plugins.<stem>`.
5. **NEVER silently accept >1 plugin class per file.** CONTEXT.md D-02 locks "one class per file"; the registry must raise.
6. **NEVER pass `domain_pattern` as a single string** (legacy from the current ABC at `plugin_base.py:22`). D-01 locks list[str]. The plan that updates the ABC type annotation must precede or accompany the plugin migrations.
7. **NEVER stop the polling loop on a single plugin's runtime exception.** Log + continue.
8. **NEVER skip the Phase B coverage check.** D-04: a typo'd URL with no matching plugin must hard-fail at startup with an actionable error naming the URL and the expected plugin filename.
9. **NEVER call `update_item_purchased` from `check_availability`.** Only `auto_buy` should mark purchases (BestBuy's missing call is the PLG-02 fix; do not "fix forward" by marking-on-availability).
10. **NEVER pass a `dict` where `AppConfig` / `PlatformConfig` is expected.** Plugins consume the Pydantic instance directly; `.credentials.email` not `["credentials"]["email"]`.
11. **`amazon_bot.py` and `bestbuy_bot.py` MUST be deleted** at the end of Phase 2 (D-02 hard cut). The task that creates the corresponding plugin should also `git rm` the old file in the same commit, with `main.py` updated to no longer import it.

---

## Q10: Phase 1 integration touchpoints

### How plugins consume Phase 1 outputs

```python
# plugins/shopbot_plugin_amazon.py
from plugin_base import RetailerPlugin
from driver import build_driver
from logger import writeLog
from models import update_item_purchased
# selenium imports as needed for the migrated check/auto_buy logic

class AmazonPlugin(RetailerPlugin):
    domain_pattern: list[str] = ["amazon.com", "amzn.to"]
    login_at_startup: bool = True

    def __init__(self, platform_config, *, cvv: str | None = None, driver_path: str | None = None):
        super().__init__(platform_config)
        # cvv comes from collect_cvvs(); registry passes it in if needed.
        # driver_path comes from app_config.selenium.driver_path.
        self.cvv = cvv
        self.driver = build_driver(driver_path or "chromedriver.exe")

    def check_availability(self, url: str) -> bool:
        # ported from amazon_bot.check_amazon_item, driver -> self.driver
        ...
    def login(self, config) -> None:
        # ported from amazon_bot.amz_sign_in, reads config.platforms['amazon'].credentials
        ...
    def auto_buy(self, url: str, config) -> bool:
        # ported from amazon_bot.auto_buy_amazon_item; calls update_item_purchased on success
        ...
```

### Wiring questions answered

| Question | Answer |
|----------|--------|
| Where does `build_driver(driver_path, log_path)` get called? | Inside the plugin's `__init__`. The registry passes `driver_path` via a kwarg (it reads from `app_config.selenium.driver_path` at discovery time). |
| Where does `cvv` come into the plugin? | `collect_cvvs(app_config)` runs before discovery in `main.py`. The registry's `discover()` accepts a `cvvs: dict[str, str]` kwarg and passes the matching slice into each plugin's `__init__`. |
| Where does the plugin read credentials? | `self.platform_config.credentials.email` (and `.password`). `platform_config` is the `AppConfig.platforms[<plugin_name>]` slice, set by `super().__init__(platform_config)`. |
| Where does `writeLog` come from? | `from logger import writeLog` — module-level singleton, configured once by `main.py` via `configure(level)`. Plugins never call `configure()`. |
| Where does the plugin learn its own name? | Recommend: the plugin self-identifies via a `name: str = "amazon"` class attribute (used by registry to look up `app_config.platforms[name]` and `cvvs[name]`). Alternative: derive from filename stem (`shopbot_plugin_amazon.py` → `"amazon"`). Planner picks one and locks it in plan 01. |

### Discovery → instantiation flow

```python
# plugin_registry.py
def discover(plugins_dir: Path, *, app_config, cvvs: dict[str, str]) -> list[RetailerPlugin]:
    instances = []
    for path in sorted(plugins_dir.glob("*.py")):
        if path.name.startswith("_") or path.name == "__init__.py":
            continue
        if not path.stem.startswith(PLUGIN_PREFIX):
            writeLog(f"Skipped {path.name} (not auto-loaded)", "INFO")
            continue
        try:
            module = _load_module(path)
            cls = _find_plugin_class(module)
        except Exception as e:
            writeLog(f"Failed to load {path.name}: {e}", "WARNING")
            continue  # D-04 Phase A: lenient
        name = getattr(cls, "name", path.stem.removeprefix(PLUGIN_PREFIX))
        try:
            inst = cls(
                platform_config=app_config.platforms.get(name),
                cvv=cvvs.get(name),
                driver_path=app_config.selenium.driver_path,
            )
        except Exception as e:
            writeLog(f"Failed to instantiate {cls.__name__}: {e}", "WARNING")
            continue
        instances.append(inst)
    return instances
```

---

## Validation Architecture

Test framework: **pytest** (already installed per Phase 1 plan 01-01). Quick run: `pytest -x -q tests/test_plugin_registry.py`. Full suite: `pytest -x -q`.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (pinned in requirements.txt per 01-01) |
| Config file | `pytest.ini` (or `pyproject.toml [tool.pytest.ini_options]`) — verify in plan 01 |
| Quick run command | `pytest -x -q tests/test_plugin_registry.py` |
| Full suite command | `pytest -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| CORE-03 | Registry discovers `shopbot_plugin_*.py` files via importlib | unit | `pytest tests/test_plugin_registry.py::test_discover_finds_prefixed_files -x` | ❌ Wave 0 |
| CORE-03 | Registry warns on non-prefixed `.py` files (e.g. `example_plugin.py`) | unit | `pytest tests/test_plugin_registry.py::test_discover_skips_example_plugin -x` | ❌ Wave 0 |
| CORE-03 | Import error in one plugin does NOT crash discovery (D-04 Phase A) | unit | `pytest tests/test_plugin_registry.py::test_discover_lenient_on_import_error -x` | ❌ Wave 0 |
| CORE-03 | Hidden/dunder files silently ignored | unit | `pytest tests/test_plugin_registry.py::test_discover_ignores_dunder -x` | ❌ Wave 0 |
| CORE-04 | `route_url` returns correct plugin for amazon and bestbuy URLs | unit (parametrized) | `pytest tests/test_plugin_registry.py::test_route_url -x` | ❌ Wave 0 |
| CORE-04 | `route_url` returns None for unmatched URL | unit | `pytest tests/test_plugin_registry.py::test_route_url_no_match -x` | ❌ Wave 0 |
| CORE-04 | `_normalize_netloc` strips port + lowercase | unit | `pytest tests/test_plugin_registry.py::test_normalize_netloc -x` | ❌ Wave 0 |
| CORE-04 | `_matches` rejects evilamazon.com vs amazon.com (subdomain anchor) | unit | `pytest tests/test_plugin_registry.py::test_matches_subdomain_anchor -x` | ❌ Wave 0 |
| CORE-04 | `verify_coverage` raises on URL with no matching plugin (D-04 Phase B) | unit | `pytest tests/test_plugin_registry.py::test_verify_coverage_hard_fails -x` | ❌ Wave 0 |
| CORE-08 | `plugins/example_plugin.py` exists and contains `RetailerPlugin` subclass | source-grep | `pytest tests/test_docs.py::test_example_plugin_present -x` | ❌ Wave 0 (extends existing test_docs.py) |
| CORE-08 | `plugins/PLUGIN_DEV.md` exists and references required sections | source-grep | `pytest tests/test_docs.py::test_plugin_dev_md_sections -x` | ❌ Wave 0 |
| PLG-01 | `plugins/shopbot_plugin_amazon.py` exists, subclasses RetailerPlugin, declares amazon.com in domain_pattern | smoke import + attribute check | `pytest tests/test_plugins_amazon.py::test_amazon_plugin_contract -x` | ❌ Wave 0 |
| PLG-01 | `amazon_bot.py` no longer exists (D-02 hard cut) | source-grep | `pytest tests/test_main_smoke.py::test_amazon_bot_module_removed -x` | ❌ Wave 0 (extends existing) |
| PLG-02 | `plugins/shopbot_plugin_bestbuy.py` exists, subclasses RetailerPlugin, declares bestbuy.com | smoke import | `pytest tests/test_plugins_bestbuy.py::test_bestbuy_plugin_contract -x` | ❌ Wave 0 |
| PLG-02 | BestBuy auto_buy calls update_item_purchased on success | source-grep | `pytest tests/test_plugins_bestbuy.py::test_bestbuy_calls_update_item_purchased -x` | ❌ Wave 0 |
| PLG-02 | `bestbuy_bot.py` no longer exists | source-grep | `pytest tests/test_main_smoke.py::test_bestbuy_bot_module_removed -x` | ❌ Wave 0 |
| PLG-03 | Each plugin constructs self.driver in __init__ via build_driver | mocked unit | `pytest tests/test_plugins_amazon.py::test_amazon_plugin_owns_driver -x` | ❌ Wave 0 |
| PLG-03 | main.py no longer references a shared `driver` variable | source-grep | `pytest tests/test_main_smoke.py::test_main_uses_registry -x` | ❌ Wave 0 (extends existing) |
| ABC contract (preexisting CORE-01 amendment) | `RetailerPlugin.domain_pattern` annotation is `list[str]` not `str` | unit | `pytest tests/test_plugin_base.py::test_domain_pattern_is_list -x` | ❌ Wave 0 (extends existing) |

### Sampling Rate
- **Per task commit:** `pytest -x -q tests/test_plugin_registry.py tests/test_plugins_amazon.py tests/test_plugins_bestbuy.py`
- **Per wave merge:** `pytest -x -q` (full suite)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_plugin_registry.py` — covers CORE-03, CORE-04
- [ ] `tests/test_plugins_amazon.py` — covers PLG-01, PLG-03 (Amazon side)
- [ ] `tests/test_plugins_bestbuy.py` — covers PLG-02, PLG-03 (BestBuy side)
- [ ] `tests/test_docs.py` — EXTEND with example_plugin and PLUGIN_DEV.md checks (file already exists from Phase 1 plan 06)
- [ ] `tests/test_main_smoke.py` — EXTEND with module-removal and registry-usage checks (file exists)
- [ ] `tests/test_plugin_base.py` — EXTEND with `domain_pattern: list[str]` annotation test (file exists)
- [ ] `tests/conftest.py` — EXTEND with `tmp_plugins_dir` fixture
- Framework install: none — pytest already pinned per 01-01

---

## Pitfalls (encode as PLAN.md `must_haves.truths`)

1. The current `plugin_base.py` declares `domain_pattern: str = ""`. Phase 2 changes this to `list[str]` to match D-01. Update `plugin_base.py` AND `tests/test_plugin_base.py` in the first plan of Phase 2 (or as a precursor task) — every plugin depends on the corrected type.
2. `spec_from_file_location` is the discovery primitive. Do not use `sys.path` mutation or `pkgutil.iter_modules` (requires `plugins/__init__.py` which CONTEXT.md does not require).
3. Subclass detection uses three filters: `issubclass`, `is not RetailerPlugin`, and `__module__ == module.__name__`. Missing any of them leaks false positives.
4. URL matching MUST lowercase both sides AND strip ports AND anchor with a leading dot to reject `evilamazon.com` vs `amazon.com`.
5. `app_config.available.items` is the flat URL list (not per-platform). The Phase B coverage check iterates this single list.
6. Plugin `__init__` opens a Chrome window. Two plugins = two windows at startup. Tests MUST monkeypatch `build_driver` (otherwise pytest spawns Chrome).
7. `update_item_purchased(url)` is called from `auto_buy` ONLY, after the place-order click succeeds. BestBuy is missing this call today (PLG-02 fix at `bestbuy_bot.py:71`).
8. `bestbuy_bot.py` currently uses positional `(email, password, cvv)` args. The plugin version reads from `self.platform_config.credentials` and `self.cvv`.
9. Discovery is LENIENT on import error (log + skip, D-04 Phase A). Coverage check is STRICT (hard-fail, D-04 Phase B). Plans must not swap these.
10. The polling loop wraps `plugin.check_availability` and `plugin.auto_buy` in try/except. Runtime plugin exceptions log + continue; they do NOT crash the loop or trigger D-04 (which is import-time only).
11. `amazon_bot.py` and `bestbuy_bot.py` are DELETED (D-02). The plan that creates each plugin should `git rm` the old file in the same commit, and `main.py` import lines 19-20 are removed.
12. `config.py` is an ImportError tripwire (from Phase 1 plan 06). Plugins must never `from config import config`.
13. `example_plugin.py` is intentionally NOT discovered. Filename prefix mismatch causes a single INFO log; tests should assert that log is emitted and that no `ExamplePlugin` instance is in the returned registry.

---

## Recommended File Layout

```
plugin_base.py                          # EDIT: domain_pattern: str -> list[str]; add login_at_startup: bool = False default
plugin_registry.py                      # CREATE: discover, route_url, verify_coverage, _normalize_netloc, _matches, _load_module, _find_plugin_class
plugins/
├── shopbot_plugin_amazon.py            # CREATE: migrated from amazon_bot.py
├── shopbot_plugin_bestbuy.py           # CREATE: migrated from bestbuy_bot.py, PLG-02 fix
├── example_plugin.py                   # CREATE: working httpbin echo plugin, NOT auto-loaded
└── PLUGIN_DEV.md                       # CREATE: contributor contract reference (see Q7 outline)
amazon_bot.py                           # DELETE (D-02)
bestbuy_bot.py                          # DELETE (D-02)
main.py                                 # EDIT: remove _handle_amazon/_handle_bestbuy; call discover/verify_coverage/route_url
tests/
├── conftest.py                         # EDIT: add tmp_plugins_dir fixture
├── test_plugin_base.py                 # EDIT: assert domain_pattern: list[str] annotation
├── test_plugin_registry.py             # CREATE: discovery, routing, coverage, normalize_netloc, matches
├── test_plugins_amazon.py              # CREATE: contract + mocked driver tests for Amazon plugin
├── test_plugins_bestbuy.py             # CREATE: contract + mocked driver tests for BestBuy plugin, update_item_purchased call
├── test_main_smoke.py                  # EDIT: assert old modules deleted, registry imports present
└── test_docs.py                        # EDIT: assert example_plugin and PLUGIN_DEV.md exist with required content
```

Approximate plan count: **5 plans** (matches the "4-6 atomic plans" target from the objective).

| # | Plan | Files | Requirements |
|---|------|-------|--------------|
| 01 | ABC contract update + registry skeleton + tests | plugin_base.py, plugin_registry.py, tests/test_plugin_registry.py, tests/conftest.py, tests/test_plugin_base.py | CORE-03, CORE-04 (registry side), ABC type fix |
| 02 | Amazon plugin migration | plugins/shopbot_plugin_amazon.py, tests/test_plugins_amazon.py, delete amazon_bot.py, edit main.py | PLG-01, PLG-03 (Amazon) |
| 03 | BestBuy plugin migration + PLG-02 fix | plugins/shopbot_plugin_bestbuy.py, tests/test_plugins_bestbuy.py, delete bestbuy_bot.py, edit main.py | PLG-02, PLG-03 (BestBuy) |
| 04 | main.py poll-loop refactor (route_url integration, login orchestration, coverage check) | main.py, tests/test_main_smoke.py | CORE-03, CORE-04 (main side) |
| 05 | example_plugin.py + PLUGIN_DEV.md + docs tests | plugins/example_plugin.py, plugins/PLUGIN_DEV.md, tests/test_docs.py | CORE-08 |

Plan dependency graph:
- 01 has no deps (within Phase 2).
- 02 and 03 depend on 01 (registry exists, ABC type corrected).
- 04 depends on 02 AND 03 (both plugins must exist for main.py to route to them).
- 05 depends on 01 (PLUGIN_DEV.md references the corrected ABC).

Alternative split: combine 02+03 into a single "plugin migration" plan if the planner prefers larger units, dropping to 4 plans. Recommend keeping them separate because each touches a different retailer module + introduces a distinct bug fix (PLG-02), so commit history is cleaner with two atomic plans.

---

## Project Constraints (from CLAUDE.md)

- Functions under 30 lines; files under 300 lines (helpers in `plugin_registry.py` and individual plugin classes will need careful decomposition for `auto_buy` which is currently ~70 lines).
- Nesting max 3 levels.
- camelCase enforced for variables/functions; PascalCase for classes/types. (Note: existing code uses `snake_case` per convention — `CONVENTIONS.md` snake_case+verb-prefix takes precedence per Phase 1 CONTEXT.md `<code_context>`; CLAUDE.md is a global rule that the project-local conventions override per ".planning/codebase/CONVENTIONS.md".)
- No new dependencies needed — importlib, urllib.parse, inspect, pathlib are stdlib.
- Tests pass before commit. TDD RED→GREEN sequence (per Phase 1 precedent in 01-02-SUMMARY).
- No secrets in commits. (No new secrets in Phase 2.)

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | httpbin.org is stable enough to use as the target in `example_plugin.py` | Q8 | LOW — if it goes down, example plugin tests fail but contributor experience degrades from "working example" to "example that 503s". Mitigate by using `httpbin.org/html` (cacheable static endpoint) rather than dynamic endpoints. |
| A2 | The planner will keep plan-count at 5 (per layout table); 4 is acceptable if 02+03 merge | Recommended File Layout | LOW — orchestrator can rebalance |
| A3 | Plugins self-identify via filename stem rather than a `name` class attribute | Q10 | MEDIUM — if a plugin's `platforms.<name>` key in `config.yml` differs from its filename stem, the registry can't find its credentials. The planner should pick ONE source-of-truth and lock it. Recommendation: `name: str` class attribute, default to filename stem if not declared. |
| A4 | `tests/test_plugin_base.py` doesn't already assert `domain_pattern: str` type (which would force a test edit, not just an additive one) | Q9 truth #1 | LOW — verified by reading 01-02-SUMMARY.md test list (5 tests cover API version, abstract rejection, instantiation, no-op defaults — none check domain_pattern type). Plan 01 of Phase 2 ADDS a test rather than modifying existing assertions. |

## Open Questions

1. **Plugin name resolution.** Should plugins declare `name: str = "amazon"` as a class attribute, or should the registry derive `name = path.stem.removeprefix("shopbot_plugin_")`? (See A3.)
   - **Recommendation:** Both — `name` class attribute optional, defaults to filename-derived. This lets `shopbot_plugin_amazon_uk.py` declare `name = "amazon"` to share credentials with the US plugin, while still defaulting cleanly for simple cases.
2. **Test mode propagation.** Currently `main.py` reads `app_config.debug.test_mode` and passes it to `_handle_amazon`/`_handle_bestbuy`. The ABC signature `auto_buy(self, url, config)` lets the plugin read `config.debug.test_mode` itself. Confirm with planner that this is acceptable (vs. passing test_mode as an explicit kwarg).
3. **Quantity in `auto_buy`.** Amazon's old signature took `quantity`; the new ABC does not. The plugin must look up the matching item by URL in `config.available.items`. Confirm planner is OK with this O(n) lookup (n is small — typically <20 items).

## Environment Availability

Phase 2 introduces no new runtime dependencies. Selenium, webdriver_manager, pytest, pydantic-settings are all already pinned in Phase 1 (`requirements.txt` per plan 01-01). httpbin.org is reached at developer-test time only (running `example_plugin.py` end-to-end is optional — its tests can mock the HTTP layer).

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | All | ✓ (assumed per Phase 1 guard) | 3.11+ | — |
| pytest | All tests | ✓ (Phase 1) | pinned | — |
| selenium | Plugins (driver.py) | ✓ (Phase 1) | pinned | — |
| pydantic-settings | AppConfig consumption | ✓ (Phase 1) | pinned | — |
| importlib, inspect, urllib.parse, pathlib | Registry | ✓ (stdlib) | — | — |
| ChromeDriver | Plugin runtime (not tests, which mock) | ✓ at runtime | webdriver_manager auto-download | — |
| httpbin.org | example_plugin runtime demo only (not unit tests) | external | — | Tests mock `requests`/`selenium.get`; example becomes "see comment, run manually" if endpoint changes |

## Sources

### Primary (HIGH confidence — read in this session)
- `plugin_base.py` (lines 1-44) — current ABC contract; `domain_pattern: str = ""` requires update
- `config_schema.py` (lines 1-100) — `PlatformConfig`/`AvailableConfig`/`AppConfig` shape
- `driver.py` (lines 1-56) — `build_driver(driver_path, log_path)` signature
- `credentials.py` (lines 1-63) — `collect_cvvs(app_config) -> dict[str, str]`
- `logger.py` (lines 1-54) — `writeLog`, `configure`
- `amazon_bot.py` (lines 1-192) — three functions to migrate
- `bestbuy_bot.py` (lines 1-73) — three functions to migrate; missing `update_item_purchased` call
- `main.py` (lines 1-133) — polling loop and dispatch to refactor
- `models.py` (lines 1-59) — `update_item_purchased(link)`
- `tests/conftest.py` (lines 1-24) — existing fixtures
- `.planning/phases/02-plugin-migration/02-CONTEXT.md` — locked decisions
- `.planning/REQUIREMENTS.md` — 6 in-scope requirements
- `.planning/PROJECT.md` — drop-in plugin framework identity
- `.planning/phases/01-foundations-security/01-CONTEXT.md` — Phase 1 D-01 ABC signature lock
- `.planning/phases/01-foundations-security/01-02-plugin-abc-contract-SUMMARY.md` — what ABC tests already exist
- `.planning/phases/01-foundations-security/01-06-SUMMARY.md` — main.py wiring, config.py tripwire

### Secondary (CITED — Python docs, stable across versions)
- docs.python.org/3/library/importlib.html#importing-a-source-file-directly — `spec_from_file_location` canonical pattern
- docs.python.org/3/library/urllib.parse.html — `urlparse().netloc` behavior
- docs.python.org/3/library/inspect.html — `getmembers`, `isclass`
- docs.python.org/3/reference/import.html#submodules — module identity / `__module__`

### Tertiary (ASSUMED — training knowledge, flagged in Assumptions Log)
- httpbin.org stability (A1)

## Metadata

**Confidence breakdown:**
- Standard stack (stdlib): HIGH — pure Python, no new third-party deps
- Architecture (registry + plugins): HIGH — locked by CONTEXT.md decisions; read all relevant Phase 1 outputs
- Source migration shape: HIGH — both files read in full
- Pitfalls: HIGH — derived from concrete code reading + locked decisions
- IDN/punycode URL handling: MEDIUM — flagged as known limitation; not used by Amazon/BestBuy in practice

**Research date:** 2026-05-12
**Valid until:** 2026-06-11 (stable; the only volatility is if Phase 1 outputs are renamed/restructured before Phase 2 ships)
