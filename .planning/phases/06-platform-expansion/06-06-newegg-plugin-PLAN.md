---
phase: 06-platform-expansion
plan: 06
type: execute
wave: 1
depends_on: ["01"]
files_modified:
  - plugins/shopbot_plugin_newegg.py
  - tests/test_plugins_newegg.py
autonomous: true
requirements:
  - PLG-08
tags:
  - python
  - nodriver
  - newegg
  - risky-autobuy
  - wave-1

must_haves:
  truths:
    - "plugins/shopbot_plugin_newegg.py defines `class NeweggPlugin(RetailerPlugin)` with class attrs `domain_pattern = ['newegg.com']`, `login_at_startup = False`, `name = 'newegg'` (D-01)"
    - "NeweggPlugin.__init__(self, platform_config, *, cvv=None, driver_path=None, user_agents=None) accepts the Plan 06-01 user_agents kwarg"
    - "NeweggPlugin.__init__ reads `SHOPBOT_ENABLE_RISKY_AUTOBUY` ONCE; stores on `self._riskyAutoBuyEnabled` (D-02). AST grep enforces single os.environ.get in __init__"
    - "NeweggPlugin.__init__ stores min_delay/max_delay/headless/userAgents (D-03 + D-04 + ANTI-02)"
    - "NeweggPlugin.open() async: `await uc.start(headless, browser_args=[UA, --disable-blink-features=AutomationControlled])`"
    - "NeweggPlugin.check_availability(url) async: `tab = await self.driver.get(url); btn = await tab.select(<NewEgg ATC selector>); return btn is not None`. Representative selector `button#btnAddCart` per RESEARCH per-retailer table; executor verifies live PDP (RESEARCH Q3 + O-5)"
    - "NeweggPlugin.auto_buy(url, config) async: if not self._riskyAutoBuyEnabled -> WARNING + return False. Otherwise proceed with ATC + checkout flow"
    - "NeweggPlugin.shutdown() async: await self.driver.stop() override (D-01); try/except + WARNING on failure"
    - "NeweggPlugin imports do NOT include `selenium` or any selenium.* submodule (RESEARCH pitfall #1). AST grep verifies"
    - "NeweggPlugin imports do NOT include `from notifier_base` or `from utils import play_*` (RESEARCH pitfall #10). AST grep verifies"
    - "All RED tests in tests/test_plugins_newegg.py from Plan 06-01 now PASS"
    - "Full pytest suite remains green; other Wave 1 sibling test files remain RED for their plans"
  artifacts:
    - path: "plugins/shopbot_plugin_newegg.py"
      provides: "NeweggPlugin (PLG-08) — nodriver, risky-autobuy gated"
      contains: "class NeweggPlugin"
      min_lines: 75
    - path: "tests/test_plugins_newegg.py"
      provides: "GREEN tests for PLG-08 (ABC contract, env gate, no selenium imports)"
      min_lines: 50
  key_links:
    - from: "plugins/shopbot_plugin_newegg.py"
      to: "os.environ.get"
      via: "SHOPBOT_ENABLE_RISKY_AUTOBUY read once in __init__"
      pattern: "os\\.environ\\.get\\([\"']SHOPBOT_ENABLE_RISKY_AUTOBUY"
    - from: "NeweggPlugin.open"
      to: "nodriver.start"
      via: "await uc.start"
      pattern: "await\\s+uc\\.start"
---

<objective>
Wave 1 (parallel-safe): ship `plugins/shopbot_plugin_newegg.py` covering PLG-08. nodriver async plugin mirroring WalmartPlugin contract. Light bot detection on NewEgg, so headless is "probably OK"; default remains False per Plan 06-01 PlatformConfig.

Output: plugins/shopbot_plugin_newegg.py + GREEN tests/test_plugins_newegg.py.

File ownership: this plan EXCLUSIVELY owns the two files above. Zero overlap with 06-02/03/04/05 or with main.py/plugin_base.py/plugin_registry.py/driver.py/config_schema.py.
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
@driver.py
@logger.py
@tests/conftest.py
@tests/test_plugins_newegg.py
</context>

<interfaces>
Target `plugins/shopbot_plugin_newegg.py`:

```python
"""NewEgg retailer plugin (PLG-08).

nodriver-based async plugin. Light bot detection; headless feasible but default
remains False per Plan 06-01 PlatformConfig. Auto-buy gated behind
SHOPBOT_ENABLE_RISKY_AUTOBUY=true.

DOM selectors representative — executor verifies against live NewEgg PDP at
implementation time per RESEARCH O-5.
"""
import os
import random

import nodriver as uc

from driver import DEFAULT_USER_AGENTS
from logger import writeLog
from plugin_base import RetailerPlugin

_ATC_SELECTOR = 'button#btnAddCart'


class NeweggPlugin(RetailerPlugin):
    domain_pattern: list[str] = ["newegg.com"]
    login_at_startup: bool = False
    name: str = "newegg"

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
            writeLog(f"NeweggPlugin.check_availability error on {url}: {e}", "ERROR")
            return False

    async def auto_buy(self, url: str, config) -> bool:
        if not self._riskyAutoBuyEnabled:
            writeLog(
                "NewEgg auto_buy skipped: set SHOPBOT_ENABLE_RISKY_AUTOBUY=true to enable",
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
            writeLog(f"NeweggPlugin.auto_buy error on {url}: {e}", "ERROR")
            return False

    async def shutdown(self) -> None:
        driver = getattr(self, "driver", None)
        if driver is None:
            return
        try:
            await driver.stop()
        except Exception as e:
            writeLog(f"NeweggPlugin.shutdown: driver.stop raised: {e}", "WARNING")
```
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Verify NewEgg ATC selector against live PDP</name>
  <files>tests/test_plugins_newegg.py</files>
  <read_first>
    - .planning/phases/06-platform-expansion/06-RESEARCH.md Q3, O-5
  </read_first>
  <behavior>
    - The NewEgg ATC selector matches the current live PDP add-to-cart button.
  </behavior>
  <action>
    1. Open https://www.newegg.com/ and inspect an in-stock PDP.
    2. Record stable selector — `button#btnAddCart` vs `.product-buy button` vs newer pattern.
    3. Update `_ATC_SELECTOR` if different.
    4. If verification impossible, accept default + add TODO in source.
  </action>
  <verify>
    <automated>echo "NewEgg selector verified or accepted default"</automated>
  </verify>
  <done>NewEgg ATC selector confirmed or replaced.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement NeweggPlugin (PLG-08) and drive RED tests to GREEN</name>
  <files>plugins/shopbot_plugin_newegg.py, tests/test_plugins_newegg.py</files>
  <read_first>
    - plugin_base.py (ABC after Plan 06-01)
    - driver.py (DEFAULT_USER_AGENTS)
    - tests/conftest.py (fakeBrowser)
    - tests/test_plugins_newegg.py (Plan 06-01 RED skeleton — REWRITTEN)
  </read_first>
  <behavior>
    - Import succeeds; subclass of RetailerPlugin; domain_pattern == ["newegg.com"]; login_at_startup False; name "newegg".
    - All 4 lifecycle methods coroutines.
    - Env on -> _riskyAutoBuyEnabled True; await auto_buy proceeds.
    - Env off -> WARNING + auto_buy returns False.
    - Env read ONCE in __init__.
    - AST grep: os.environ.get appears once; no selenium imports; no notifier_base/play_* imports.
    - open() invokes uc.start with headless + UA browser_args.
    - UA rotation via monkeypatched random.choice.
    - check_availability via fakeBrowser sentinel/None.
    - shutdown handles None driver and stop() raising.
  </behavior>
  <action>
    1. Create `plugins/shopbot_plugin_newegg.py` with contents from <interfaces>. Substitute Task 1 verified selector if different.

    2. Rewrite tests/test_plugins_newegg.py to GREEN.
       - fakeBrowser + `monkeypatch.setattr("plugins.shopbot_plugin_newegg.uc.start", AsyncMock(return_value=fakeBrowser))`.

    3. Test cases:
       - test_neweggPluginImportable
       - test_neweggSubclassesRetailerPlugin
       - test_neweggAbcContract (4 coroutines)
       - test_neweggRiskyAutobuyGateOff
       - test_neweggRiskyAutobuyGateOn
       - test_neweggEnvReadOnce
       - test_neweggNoSeleniumImport (AST grep)
       - test_neweggNoNotifierImport (AST grep)
       - test_neweggDomainPattern (route_url for newegg.com -> match; off-domain -> None)
       - test_neweggOpenCallsUcStart
       - test_neweggUaRotation
       - test_neweggCheckAvailability (sentinel + None)
       - test_neweggShutdownNoDriver, test_neweggShutdownDriverStopRaises

    4. Run `rtk pytest -q tests/test_plugins_newegg.py`. All GREEN.

    5. Run `rtk pytest -x -q --ignore=tests/test_plugins_walmart.py --ignore=tests/test_plugins_target.py --ignore=tests/test_plugins_gamestop.py --ignore=tests/test_plugins_squareenix.py`. Pre-existing + Wave 0 + this plan GREEN.
  </action>
  <verify>
    <automated>python -c "from plugins.shopbot_plugin_newegg import NeweggPlugin; from plugin_base import RetailerPlugin; assert issubclass(NeweggPlugin, RetailerPlugin)"</automated>
    <automated>rtk grep -c "os.environ.get" plugins/shopbot_plugin_newegg.py</automated>
    <automated>rtk grep -n "selenium" plugins/shopbot_plugin_newegg.py</automated>
    <automated>rtk pytest -q tests/test_plugins_newegg.py</automated>
    <automated>rtk pytest -x -q --ignore=tests/test_plugins_walmart.py --ignore=tests/test_plugins_target.py --ignore=tests/test_plugins_gamestop.py --ignore=tests/test_plugins_squareenix.py</automated>
  </verify>
  <done>NeweggPlugin (PLG-08) implemented.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| SHOPBOT_ENABLE_RISKY_AUTOBUY env -> code | Risky autobuy gate |
| NewEgg DOM -> tab.select | Untrusted markup; nodriver returns DOM handles |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-06-06-ACCIDENTAL-PURCHASE | Tampering (cost) | NeweggPlugin.auto_buy | mitigate | env-at-init gate |
| T-06-06-DRIVER-LEAK | Resource leak | shutdown | mitigate | await self.driver.stop() in try/except |
</threat_model>

<verification>
- `python -c "from plugins.shopbot_plugin_newegg import NeweggPlugin; from plugin_base import RetailerPlugin; assert issubclass(NeweggPlugin, RetailerPlugin)"`
- `rtk grep -c "os.environ.get" plugins/shopbot_plugin_newegg.py` returns 1
- `rtk pytest -q tests/test_plugins_newegg.py` GREEN
</verification>

<success_criteria>
- NeweggPlugin subclass present
- domain_pattern == ["newegg.com"]
- Env-gated auto_buy
- No selenium / notifier imports
- tests/test_plugins_newegg.py GREEN
</success_criteria>

<output>
After completion, create `.planning/phases/06-platform-expansion/06-06-SUMMARY.md`
</output>
