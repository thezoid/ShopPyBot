---
phase: 06-platform-expansion
plan: 05
type: execute
wave: 1
depends_on: ["01"]
files_modified:
  - plugins/shopbot_plugin_squareenix.py
  - tests/test_plugins_squareenix.py
autonomous: true
requirements:
  - PLG-07
tags:
  - python
  - nodriver
  - squareenix
  - risky-autobuy
  - wave-1

must_haves:
  truths:
    - "plugins/shopbot_plugin_squareenix.py defines `class SquareEnixPlugin(RetailerPlugin)` with class attrs `domain_pattern = ['square-enix.com', 'square-enix-games.com']`, `login_at_startup = False`, `name = 'squareenix'` (D-01 + CONTEXT canonical_refs)"
    - "SquareEnixPlugin.__init__(self, platform_config, *, cvv=None, driver_path=None, user_agents=None) accepts the Plan 06-01 user_agents kwarg"
    - "SquareEnixPlugin.__init__ reads `SHOPBOT_ENABLE_RISKY_AUTOBUY` ONCE; stores on `self._riskyAutoBuyEnabled` (D-02). AST grep enforces single os.environ.get in __init__"
    - "SquareEnixPlugin.__init__ stores min_delay/max_delay/headless/userAgents (D-03 + D-04 + ANTI-02)"
    - "SquareEnixPlugin.open() async: `await uc.start(headless, browser_args=[UA, --disable-blink-features=AutomationControlled])`"
    - "SquareEnixPlugin.check_availability(url) async: `tab = await self.driver.get(url); btn = await tab.select(<Square Enix ATC selector>); return btn is not None`. Representative selector `button.product-detail-add-to-cart` per RESEARCH per-retailer table; executor verifies live PDP (RESEARCH Q3 + O-5)"
    - "SquareEnixPlugin.auto_buy(url, config) async: if not self._riskyAutoBuyEnabled -> WARNING + return False. Otherwise proceed with ATC + checkout flow"
    - "SquareEnixPlugin.shutdown() async: await self.driver.stop() override (D-01); try/except + WARNING on failure"
    - "SquareEnixPlugin imports do NOT include `selenium` or any selenium.* submodule (RESEARCH pitfall #1). AST grep verifies"
    - "SquareEnixPlugin imports do NOT include `from notifier_base` or `from utils import play_*` (RESEARCH pitfall #10). AST grep verifies"
    - "All RED tests in tests/test_plugins_squareenix.py from Plan 06-01 now PASS"
    - "Full pytest suite remains green; other Wave 1 sibling test files remain RED for their plans"
  artifacts:
    - path: "plugins/shopbot_plugin_squareenix.py"
      provides: "SquareEnixPlugin (PLG-07) — nodriver, risky-autobuy gated"
      contains: "class SquareEnixPlugin"
      min_lines: 75
    - path: "tests/test_plugins_squareenix.py"
      provides: "GREEN tests for PLG-07 (ABC contract, env gate, dual-domain routing, no selenium imports)"
      min_lines: 50
  key_links:
    - from: "plugins/shopbot_plugin_squareenix.py"
      to: "os.environ.get"
      via: "SHOPBOT_ENABLE_RISKY_AUTOBUY read once in __init__"
      pattern: "os\\.environ\\.get\\([\"']SHOPBOT_ENABLE_RISKY_AUTOBUY"
    - from: "SquareEnixPlugin.open"
      to: "nodriver.start"
      via: "await uc.start"
      pattern: "await\\s+uc\\.start"
---

<objective>
Wave 1 (parallel-safe): ship `plugins/shopbot_plugin_squareenix.py` covering PLG-07. nodriver async plugin mirroring WalmartPlugin contract. Square Enix uses light Cloudflare protection (per RESEARCH per-retailer table), so headless is "probably OK"; default remains False per Plan 06-01 PlatformConfig.

The dual-domain pattern is the Square Enix-specific wrinkle: `domain_pattern` covers BOTH the .com storefront and the games subdomain.

Output: plugins/shopbot_plugin_squareenix.py + GREEN tests/test_plugins_squareenix.py.

File ownership: this plan EXCLUSIVELY owns the two files above. Zero overlap with 06-02/03/04/06 or with main.py/plugin_base.py/plugin_registry.py/driver.py/config_schema.py.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/06-platform-expansion/06-CONTEXT.md
@.planning/phases/06-platform-expansion/06-RESEARCH.md
@.planning/phases/06-platform-expansion/06-01-foundation-and-red-skeletons-PLAN.md
@.planning/phases/06-platform-expansion/06-02-walmart-plugin-PLAN.md
@plugin_base.py
@plugin_registry.py
@driver.py
@logger.py
@tests/conftest.py
@tests/test_plugins_squareenix.py
</context>

<interfaces>
Target `plugins/shopbot_plugin_squareenix.py`:

```python
"""Square Enix retailer plugin (PLG-07).

nodriver-based async plugin. Light Cloudflare protection in front of the
storefront; headless mode is feasible (default still False for safety).
Dual-domain pattern covers both square-enix.com (US store) and
square-enix-games.com (EU/games subdomain).

Auto-buy gated behind SHOPBOT_ENABLE_RISKY_AUTOBUY=true.

DOM selectors representative — executor verifies against live Square Enix PDP
at implementation time per RESEARCH O-5.
"""
import os
import random

import nodriver as uc

from driver import DEFAULT_USER_AGENTS
from logger import writeLog
from plugin_base import RetailerPlugin

_ATC_SELECTOR = 'button.product-detail-add-to-cart'


class SquareEnixPlugin(RetailerPlugin):
    domain_pattern: list[str] = ["square-enix.com", "square-enix-games.com"]
    login_at_startup: bool = False
    name: str = "squareenix"

    def __init__(self, platform_config, *, cvv=None, driver_path=None, user_agents=None):
        super().__init__(platform_config)
        self._riskyAutoBuyEnabled = (
            os.environ.get("SHOPBOT_ENABLE_RISKY_AUTOBUY", "").strip().lower() == "true"
        )
        self.min_delay = platform_config.min_delay
        self.max_delay = platform_config.max_delay
        self._headless = platform_config.headless
        self._userAgents = user_agents or DEFAULT_USER_AGENTS
        self.driver = None

    async def open(self) -> None:
        chosenUa = random.choice(self._userAgents)
        self.driver = await uc.start(
            headless=self._headless,
            browser_args=[
                f"--user-agent={chosenUa}",
                "--disable-blink-features=AutomationControlled",
            ],
        )

    async def check_availability(self, url: str) -> bool:
        try:
            tab = await self.driver.get(url)
            btn = await tab.select(_ATC_SELECTOR)
            return btn is not None
        except Exception as e:
            writeLog(f"SquareEnixPlugin.check_availability error on {url}: {e}", "ERROR")
            return False

    async def auto_buy(self, url: str, config) -> bool:
        if not self._riskyAutoBuyEnabled:
            writeLog(
                "Square Enix auto_buy skipped: set SHOPBOT_ENABLE_RISKY_AUTOBUY=true to enable",
                "WARNING",
            )
            return False
        try:
            tab = await self.driver.get(url)
            btn = await tab.select(_ATC_SELECTOR)
            if btn is None:
                return False
            # Executor implements: click ATC -> cart -> checkout -> place order.
            return False
        except Exception as e:
            writeLog(f"SquareEnixPlugin.auto_buy error on {url}: {e}", "ERROR")
            return False

    async def shutdown(self) -> None:
        driver = getattr(self, "driver", None)
        if driver is None:
            return
        try:
            await driver.stop()
        except Exception as e:
            writeLog(f"SquareEnixPlugin.shutdown: driver.stop raised: {e}", "WARNING")
```
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Verify Square Enix ATC selector and domain pattern</name>
  <files>tests/test_plugins_squareenix.py</files>
  <read_first>
    - .planning/phases/06-platform-expansion/06-RESEARCH.md Q3, O-5
  </read_first>
  <behavior>
    - The ATC selector reflects current Square Enix storefront DOM.
    - `domain_pattern` covers both the .com US storefront and the games EU subdomain (verify exact host).
  </behavior>
  <action>
    1. Load https://store.na.square-enix-games.com/ AND https://www.square-enix.com/. Inspect ATC button on each.
    2. Confirm host names — common patterns are `square-enix.com` plus `square-enix-games.com` OR `store.eu.square-enix-games.com` etc. Adjust `domain_pattern` to the verified set.
    3. Update `_ATC_SELECTOR` if different.
    4. If verification impossible, accept defaults + add TODO in source.
  </action>
  <verify>
    <automated>echo "Square Enix selector and domain pattern verified or accepted defaults"</automated>
  </verify>
  <done>Square Enix selectors confirmed or replaced.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement SquareEnixPlugin (PLG-07) and drive RED tests to GREEN</name>
  <files>plugins/shopbot_plugin_squareenix.py, tests/test_plugins_squareenix.py</files>
  <read_first>
    - plugin_base.py (ABC after Plan 06-01)
    - plugin_registry.py (route_url for dual-domain test)
    - driver.py (DEFAULT_USER_AGENTS)
    - tests/conftest.py (fakeBrowser)
    - tests/test_plugins_squareenix.py (Plan 06-01 RED skeleton — REWRITTEN)
  </read_first>
  <behavior>
    - Import succeeds; subclass of RetailerPlugin; domain_pattern is a list containing BOTH "square-enix.com" AND "square-enix-games.com" (or the Task 1 verified set, both entries present).
    - login_at_startup False; name "squareenix"; all five lifecycle methods coroutines.
    - Env on -> _riskyAutoBuyEnabled True; await auto_buy proceeds.
    - Env off -> WARNING + auto_buy returns False.
    - Env read ONCE in __init__.
    - AST grep: os.environ.get appears once; no selenium imports; no notifier_base/play_* imports.
    - route_url("https://www.square-enix.com/item/123", [instance]) matches the plugin.
    - route_url("https://store.na.square-enix-games.com/item/123", [instance]) matches the plugin.
    - route_url("https://example.com/item", [instance]) returns None.
    - open() invokes uc.start with headless + UA browser_args.
    - UA rotation via monkeypatched random.choice.
    - check_availability via fakeBrowser.select sentinel/None.
    - shutdown handles None driver and stop() raising.
  </behavior>
  <action>
    1. Create `plugins/shopbot_plugin_squareenix.py` with contents from <interfaces>. Substitute Task 1 verified selectors/domains if different.

    2. Rewrite tests/test_plugins_squareenix.py to GREEN.
       - fakeBrowser + monkeypatch.setattr("plugins.shopbot_plugin_squareenix.uc.start", AsyncMock(return_value=fakeBrowser)).
       - Use `from plugin_registry import route_url` for dual-domain routing tests.

    3. Test cases:
       - test_squareenixPluginImportable
       - test_squareenixSubclassesRetailerPlugin
       - test_squareenixAbcContract (all 4 coroutines)
       - test_squareenixRiskyAutobuyGateOff
       - test_squareenixRiskyAutobuyGateOn
       - test_squareenixEnvReadOnce
       - test_squareenixNoSeleniumImport (AST grep)
       - test_squareenixNoNotifierImport (AST grep)
       - test_squareenixDualDomainRouting: parametrize URLs across both domains; assert route_url returns the plugin instance; parametrize an off-domain URL; assert None.
       - test_squareenixOpenCallsUcStart
       - test_squareenixUaRotation
       - test_squareenixCheckAvailability (sentinel + None)
       - test_squareenixShutdownNoDriver, test_squareenixShutdownDriverStopRaises

    4. Run `rtk pytest -q tests/test_plugins_squareenix.py`. All GREEN.

    5. Run `rtk pytest -x -q --ignore=tests/test_plugins_walmart.py --ignore=tests/test_plugins_target.py --ignore=tests/test_plugins_gamestop.py --ignore=tests/test_plugins_newegg.py`. Pre-existing + Wave 0 + this plan GREEN.
  </action>
  <verify>
    <automated>python -c "from plugins.shopbot_plugin_squareenix import SquareEnixPlugin; from plugin_base import RetailerPlugin; assert issubclass(SquareEnixPlugin, RetailerPlugin)"</automated>
    <automated>rtk grep -c "os.environ.get" plugins/shopbot_plugin_squareenix.py</automated>
    <automated>rtk grep -n "selenium" plugins/shopbot_plugin_squareenix.py</automated>
    <automated>rtk pytest -q tests/test_plugins_squareenix.py</automated>
    <automated>rtk pytest -x -q --ignore=tests/test_plugins_walmart.py --ignore=tests/test_plugins_target.py --ignore=tests/test_plugins_gamestop.py --ignore=tests/test_plugins_newegg.py</automated>
  </verify>
  <done>SquareEnixPlugin (PLG-07) implemented with dual-domain routing.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| SHOPBOT_ENABLE_RISKY_AUTOBUY env -> code | Risky autobuy gate |
| Square Enix Cloudflare -> rate limit | Light protection; default delays sufficient |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-06-05-ACCIDENTAL-PURCHASE | Tampering (cost) | SquareEnixPlugin.auto_buy | mitigate | env-at-init gate |
| T-06-05-DRIVER-LEAK | Resource leak | shutdown | mitigate | await self.driver.stop() in try/except |
| T-06-05-DOMAIN-MISMATCH | Tampering (routing) | domain_pattern | mitigate | Two-entry domain_pattern verified at plan-time; route_url unit test asserts both hosts match |
</threat_model>

<verification>
- `python -c "from plugins.shopbot_plugin_squareenix import SquareEnixPlugin; from plugin_base import RetailerPlugin; assert issubclass(SquareEnixPlugin, RetailerPlugin)"`
- `rtk grep -c "os.environ.get" plugins/shopbot_plugin_squareenix.py` returns 1
- `rtk pytest -q tests/test_plugins_squareenix.py` GREEN
</verification>

<success_criteria>
- SquareEnixPlugin subclass present
- Dual-domain domain_pattern verified
- Env-gated auto_buy
- No selenium / notifier imports
- tests/test_plugins_squareenix.py GREEN
</success_criteria>

<output>
After completion, create `.planning/phases/06-platform-expansion/06-05-SUMMARY.md`
</output>
