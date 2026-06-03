# Plugin Development Guide

This guide covers everything you need to build a working ShopPyBot plugin for a
new retailer. You should not need to read any core source files. Start from the
example, follow the naming rule, implement two required methods, and run the tests.

## Quick Start

Copy `plugins/example_plugin.py` to a new file following the naming convention
below. Replace the FakeShop selectors with your retailer's real CSS selectors.
Run the test suite to confirm your plugin loads and satisfies the contract.

## 1. Naming Convention

Your plugin file MUST be named:

```
plugins/shopbot_plugin_<name>.py
```

The registry discovers plugins by scanning `plugins/` for files that match the
`shopbot_plugin_*.py` pattern. Any `.py` file in that directory that does NOT
match the pattern is logged as a warning and ignored. It will never be loaded.

Correct names: `shopbot_plugin_walmart.py`, `shopbot_plugin_gamestop.py`
Incorrect names: `walmart.py`, `my_plugin.py`, `example_plugin.py`

Note: `example_plugin.py` is intentionally named to NOT match the pattern. It
is a template for contributors and is never loaded by the registry at runtime.

## 2. ABC Contract

Your class must subclass `RetailerPlugin` from `core.plugin_base`:

```python
from core.plugin_base import RetailerPlugin

class MyShopPlugin(RetailerPlugin):
    domain_patterns = ["myshop.com"]

    async def check_availability(self, url: str) -> bool:
        ...

    async def auto_buy(self, url: str) -> bool:
        ...
```

All methods are `async`. The two abstract methods are required. All other methods
have working defaults and are optional to override.

| Method | Required | Signature | Default |
|--------|----------|-----------|---------|
| `check_availability` | yes | `async (self, url: str) -> bool` | none (abstract) |
| `auto_buy` | yes | `async (self, url: str) -> bool` | none (abstract) |
| `setup` | no | `async (self) -> None` | no-op |
| `teardown` | no | `async (self) -> None` | no-op |
| `login` | no | `async (self) -> None` | returns None |
| `detect_captcha` | no | `async (self) -> bool` | returns False |

Override `setup` to start your browser and `teardown` to close it:

```python
async def setup(self) -> None:
    # nodriver.start() MUST be called from async context, never in __init__
    self.driver = await nodriver.start(headless=False)

async def teardown(self) -> None:
    if self.driver:
        self.driver.stop()   # sync; terminates the Chrome subprocess
        self.driver = None
```

## 3. domain_patterns

`domain_patterns` is a class attribute (a list of strings). The registry routes
any URL to your plugin when any string in the list is a substring of the URL
hostname. Matching uses `urlparse(url).hostname`, not the raw URL string, so
path and query-string values cannot cause false matches.

```python
# Single domain
domain_patterns = ["myshop.com"]

# Multi-region retailer: cover all hostnames with one list
domain_patterns = ["myshop.com", "myshop.co.uk", "myshop.ca", "myshop.de"]
```

The pattern is a substring match, so `"myshop.com"` matches both `www.myshop.com`
and `checkout.myshop.com`. Prefer the shortest unambiguous suffix.

## 4. Selecting DOM Elements

ShopPyBot uses `nodriver` (0.50.3) for browser automation. Element selection is
async and returns `None` when the element is not found within the timeout. It
does not raise an exception on timeout.

```python
tab = await self.driver.get(url)

# CSS selectors: prefix with # for ID, . for class
element = await tab.select("#add-to-cart-button", timeout=10)
if not element:
    # Element not found -- item is unavailable or selector is wrong
    return False
await element.click()

# Always get a fresh tab reference after navigating
tab = await self.driver.get("https://www.myshop.com/checkout")
```

Selector conversion from Selenium:
- `By.ID, "foo"` becomes `"#foo"`
- `By.CLASS_NAME, "foo"` becomes `".foo"`

## 5. Config Access

The registry passes an `AppConfig` instance to your plugin as `self.config`. You
can read the global settings via:

```python
self.config.debug.test_mode       # True skips the final purchase click
self.config.debug.logging_level   # 0=ALWAYS only, 5=TRACE
```

Platform-specific settings for Amazon and BestBuy live under
`self.config.platforms.amazon.*` and `self.config.platforms.bestbuy.*`.

Limitation: the current `AppConfig` schema has fixed fields for amazon and
bestbuy only. Adding config keys for a new community platform requires editing
`core/config_schema.py`. Flexible per-platform config sections are deferred to a
future phase. For now, put any platform-specific values in environment variables
(see section 6 below).

## 6. Credentials: Environment Variables Only

Never hardcode credentials in your plugin file. Never read them from `config.yml`.
Never log their values. Store all secrets in environment variables and read them
at runtime:

```python
import os

email = os.environ.get("MYSHOP_EMAIL", "")
password = os.environ.get("MYSHOP_PASSWORD", "")
if not email or not password:
    writeLog("MYSHOP_EMAIL or MYSHOP_PASSWORD not set -- skipping login", "ERROR")
    return
```

Copy `.env.example` in the project root to `.env` and add your keys there.
The `.env` file is gitignored; never commit it.

## 7. Calling update_item_purchased

After a successful purchase, call `update_item_purchased(url)` to mark the item
in the database so the bot does not attempt to buy it again on the next loop
iteration:

```python
from models import update_item_purchased

# Inside auto_buy, after the place-order click succeeds:
writeLog("Order placed on MyShop", "SUCCESS")
update_item_purchased(url)
return True
```

Omitting this call causes the bot to re-attempt the purchase every loop. This is
a known bug in the original BestBuy code (fixed in the current BestBuy plugin).

## 8. Testing Your Plugin

Run the full test suite to confirm no regressions:

```sh
python -m pytest tests/ -q
```

For a quick ABC-compliance check, add a test modeled on the example:

```python
import importlib.util
from pathlib import Path
from core.plugin_base import RetailerPlugin

_PATH = Path(__file__).parent.parent / "plugins" / "shopbot_plugin_myshop.py"

def test_myshop_satisfies_abc():
    spec = importlib.util.spec_from_file_location("shopbot_plugin_myshop", _PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    cls = module.MyShopPlugin
    assert issubclass(cls, RetailerPlugin)
    instance = cls(config=None)
    assert instance.driver is None
    assert "myshop.com" in instance.domain_patterns
```

See `tests/test_example_plugin.py` for the full reference implementation of this
pattern.

## 9. Trust and Security

Loading a plugin file is equivalent to executing it. Only install plugin files
from sources you trust: plugins you wrote yourself, or plugins reviewed by the
project maintainers in a pull request. The full community plugin policy will be
documented in CONTRIBUTING.md and SECURITY.md (planned for a later phase).

Key rules for any plugin you write or accept:
- No credentials in source code or config.yml (env vars only, section 6).
- Do not log credential values at any log level.
- Do not add new runtime dependencies without a project-level review.
