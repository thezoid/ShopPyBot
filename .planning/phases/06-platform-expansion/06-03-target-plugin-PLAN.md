---
phase: 06-platform-expansion
plan: 03
type: execute
wave: 1
depends_on: ["01"]
files_modified:
  - plugins/shopbot_plugin_target.py
  - tests/test_plugins_target.py
autonomous: true
requirements:
  - PLG-05
tags:
  - python
  - nodriver
  - target
  - akamai
  - risky-autobuy
  - wave-1

must_haves:
  truths:
    - "plugins/shopbot_plugin_target.py defines `class TargetPlugin(RetailerPlugin)` with class attrs `domain_pattern = ['target.com']`, `login_at_startup = False`, `name = 'target'` (D-01)"
    - "TargetPlugin.__init__(self, platform_config, *, cvv=None, driver_path=None, user_agents=None) accepts the Plan 06-01 user_agents kwarg"
    - "TargetPlugin.__init__ reads `SHOPBOT_ENABLE_RISKY_AUTOBUY` ONCE; stores on `self._riskyAutoBuyEnabled` (D-02). AST grep enforces single os.environ.get in __init__ only"
    - "TargetPlugin.__init__ stores min_delay/max_delay from platform_config (D-03), headless and userAgents (D-04 + ANTI-02)"
    - "TargetPlugin.__init__ when `platform_config.headless is True`: writeLog WARNING 'Target plugin: headless mode often blocked by Akamai; expect failures' (RESEARCH Q5). Plugin still constructs successfully (warning, not error)"
    - "TargetPlugin.open() async: `self.driver = await uc.start(headless=self._headless, browser_args=[--user-agent, --disable-blink-features=AutomationControlled])` (RESEARCH Pattern 1)"
    - "TargetPlugin.check_availability(url) async: `tab = await self.driver.get(url); btn = await tab.select(<Target ATC selector>); return btn is not None`. Representative selector `button[data-test='orderPickupButton']` per RESEARCH per-retailer table; executor verifies against live PDP at implementation time (RESEARCH Q3 + O-5)"
    - "TargetPlugin.auto_buy(url, config) async: if not self._riskyAutoBuyEnabled -> WARNING + return False. Otherwise proceed with experimental checkout flow. Module docstring labels auto-buy EXPERIMENTAL per PLG-05 requirement wording (D-02 + Akamai risk)"
    - "TargetPlugin.shutdown() async: await self.driver.stop() override (D-01); try/except + WARNING on failure"
    - "TargetPlugin imports do NOT include `selenium` or any selenium.* submodule (RESEARCH pitfall #1). AST grep verifies"
    - "TargetPlugin imports do NOT include `from notifier_base` or `from utils import play_*` (RESEARCH pitfall #10). AST grep verifies"
    - "Module docstring contains the substring 'EXPERIMENTAL' near the auto-buy description (PLG-05 wording requirement)"
    - "All RED tests in tests/test_plugins_target.py from Plan 06-01 now PASS"
    - "Full pytest suite remains green across Phase 1-6 (no regressions); other Wave 1 sibling test files remain RED for their plans"
  artifacts:
    - path: "plugins/shopbot_plugin_target.py"
      provides: "TargetPlugin (PLG-05) — nodriver, risky-autobuy gated, headless Akamai warning"
      contains: "class TargetPlugin"
      min_lines: 75
    - path: "tests/test_plugins_target.py"
      provides: "GREEN tests for PLG-05 (ABC contract, env gate, headless warning, no selenium imports)"
      min_lines: 50
  key_links:
    - from: "plugins/shopbot_plugin_target.py"
      to: "os.environ.get"
      via: "SHOPBOT_ENABLE_RISKY_AUTOBUY read once in __init__"
      pattern: "os\\.environ\\.get\\([\"']SHOPBOT_ENABLE_RISKY_AUTOBUY"
    - from: "TargetPlugin.__init__"
      to: "writeLog"
      via: "Akamai headless WARNING when platform_config.headless is True"
      pattern: "Akamai"
    - from: "TargetPlugin.open"
      to: "nodriver.start"
      via: "await uc.start"
      pattern: "await\\s+uc\\.start"
---

<objective>
Wave 1 (parallel-safe): ship `plugins/shopbot_plugin_target.py` covering PLG-05. nodriver async plugin mirroring the WalmartPlugin contract; key Target-specific addition is a startup WARNING when `platform_config.headless is True` because Akamai consistently blocks headless. Module docstring labels auto-buy EXPERIMENTAL per PLG-05.

Purpose: Target's Akamai layer is the harshest in Phase 6 for headless. The warning lets users keep `headless=False` defaults safely while making the failure mode explicit when they opt in.

Output: plugins/shopbot_plugin_target.py + GREEN tests/test_plugins_target.py.

File ownership: this plan EXCLUSIVELY owns the two files above. Zero overlap with 06-02/04/05/06 or with main.py/plugin_base.py/plugin_registry.py/driver.py/config_schema.py.
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
@config_schema.py
@driver.py
@logger.py
@tests/conftest.py
@tests/test_plugins_target.py
</context>

<interfaces>
Target `plugins/shopbot_plugin_target.py`:

```python
"""Target retailer plugin (PLG-05).

nodriver-based async plugin. Akamai Bot Manager consistently blocks headless
Selenium AND fingerprints headless Chrome; nodriver in non-headless mode is the
recommended posture. Auto-buy is EXPERIMENTAL per PLG-05 (Akamai may block
mid-flow); gated behind SHOPBOT_ENABLE_RISKY_AUTOBUY=true.

DOM selectors representative — executor verifies against live Target PDP at
implementation time per RESEARCH O-5.
"""
import os
import random

import nodriver as uc

from driver import DEFAULT_USER_AGENTS
from logger import writeLog
from plugin_base import RetailerPlugin

_ATC_SELECTOR = 'button[data-test="orderPickupButton"]'


class TargetPlugin(RetailerPlugin):
    domain_pattern: list[str] = ["target.com"]
    login_at_startup: bool = False
    name: str = "target"

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
        if self._headless:
            writeLog(
                "Target plugin: headless mode often blocked by Akamai; expect failures",
                "WARNING",
            )

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
            writeLog(f"TargetPlugin.check_availability error on {url}: {e}", "ERROR")
            return False

    async def auto_buy(self, url: str, config) -> bool:
        if not self._riskyAutoBuyEnabled:
            writeLog(
                "Target auto_buy skipped: set SHOPBOT_ENABLE_RISKY_AUTOBUY=true to enable",
                "WARNING",
            )
            return False
        try:
            tab = await self.driver.get(url)
            btn = await tab.select(_ATC_SELECTOR)
            if btn is None:
                return False
            # EXPERIMENTAL: executor implements ATC -> cart -> checkout -> place order.
            return False
        except Exception as e:
            writeLog(f"TargetPlugin.auto_buy error on {url}: {e}", "ERROR")
            return False

    async def shutdown(self) -> None:
        driver = getattr(self, "driver", None)
        if driver is None:
            return
        try:
            await driver.stop()
        except Exception as e:
            writeLog(f"TargetPlugin.shutdown: driver.stop raised: {e}", "WARNING")
```
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Verify Target ATC DOM selector against live PDP</name>
  <files>tests/test_plugins_target.py</files>
  <read_first>
    - .planning/phases/06-platform-expansion/06-RESEARCH.md Q3, O-5 (selector verification mandate)
  </read_first>
  <behavior>
    - The Target ATC selector encoded in `_ATC_SELECTOR` (default: `button[data-test="orderPickupButton"]`) reflects the current live Target PDP "Add to cart" or "Pick up" button.
    - If the live page uses a different selector, the constant is updated AND test recorded.
  </behavior>
  <action>
    1. Open https://www.target.com/ and load an item PDP (in-stock + OOS). Use devtools.
    2. Record stable selector: data-test > data-testid > role+name > class.
    3. Update `_ATC_SELECTOR` in <interfaces> if different.
    4. If verification impossible, accept the default and add TODO in source.
  </action>
  <verify>
    <automated>echo "Selector verification recorded in tests/test_plugins_target.py or accepted default"</automated>
  </verify>
  <done>Target selector confirmed or replaced.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement TargetPlugin (PLG-05) and drive RED tests to GREEN</name>
  <files>plugins/shopbot_plugin_target.py, tests/test_plugins_target.py</files>
  <read_first>
    - plugin_base.py (Plan 06-01 ABC additions)
    - config_schema.py (PlatformConfig fields)
    - driver.py (DEFAULT_USER_AGENTS)
    - tests/conftest.py (fakeBrowser fixture)
    - tests/test_plugins_target.py (Plan 06-01 RED skeleton — to be REWRITTEN)
    - plugins/shopbot_plugin_walmart.py if landed (Wave 1 sibling — DO NOT import from it; just structural reference)
    - .planning/phases/06-platform-expansion/06-RESEARCH.md Q5 (Akamai headless), Pattern 1
  </read_first>
  <behavior>
    - `from plugins.shopbot_plugin_target import TargetPlugin` succeeds.
    - issubclass(TargetPlugin, RetailerPlugin); domain_pattern == ["target.com"]; login_at_startup False; name "target".
    - open / check_availability / auto_buy / shutdown all coroutines.
    - Env on: instance._riskyAutoBuyEnabled is True; await auto_buy does NOT early-return on env gate.
    - Env off: await auto_buy returns False AND WARNING "SHOPBOT_ENABLE_RISKY_AUTOBUY" fires.
    - headless=True at __init__: WARNING with "Akamai" substring fires. Plugin still constructs.
    - headless=False at __init__: no Akamai WARNING fires.
    - Env read ONCE in __init__: setting env after instantiation does not change state.
    - AST grep: os.environ.get appears exactly ONCE; no selenium imports; no notifier_base/play_* imports.
    - Module docstring contains "EXPERIMENTAL" (PLG-05 wording).
    - shutdown with driver=None returns cleanly; shutdown with stop() raising logs WARNING and swallows.
    - check_availability via fakeBrowser: select returns sentinel -> True; select returns None -> False; select raises -> ERROR log + returns False.
    - open() calls uc.start with headless=platform_config.headless + browser_args containing UA + disable-blink-features arg.
    - UA rotation: monkeypatch random.choice; two instances get different --user-agent args.
  </behavior>
  <action>
    1. Create `plugins/shopbot_plugin_target.py` with contents from <interfaces>. Substitute the Task 1 verified selector if different.

    2. Rewrite tests/test_plugins_target.py to GREEN. Use the fakeBrowser fixture + `monkeypatch.setattr("plugins.shopbot_plugin_target.uc.start", AsyncMock(return_value=fakeBrowser))`.

    3. Test cases:
       - test_targetPluginImportable
       - test_targetSubclassesRetailerPlugin
       - test_targetAbcContract (all 4 coroutines)
       - test_targetRiskyAutobuyGateOff (delenv; auto_buy returns False + WARNING)
       - test_targetRiskyAutobuyGateOn (setenv; _riskyAutoBuyEnabled is True)
       - test_targetHeadlessAkamaiWarning (headless=True; WARNING with "Akamai" captured)
       - test_targetHeadlessFalseNoWarning (headless=False; no Akamai WARNING)
       - test_targetEnvReadOnce
       - test_targetNoSeleniumImport (AST grep)
       - test_targetNoNotifierImport (AST grep)
       - test_targetExperimentalDocstring (assert "EXPERIMENTAL" in TargetPlugin.__module__.__doc__ or in module docstring)
       - test_targetOpenCallsUcStart
       - test_targetUaRotation (monkeypatch random.choice; two instances; different --user-agent args)
       - test_targetCheckAvailability (sentinel + None paths)
       - test_targetShutdownNoDriver, test_targetShutdownDriverStopRaises

    4. Run `rtk pytest -q tests/test_plugins_target.py`. All GREEN.

    5. Run `rtk pytest -x -q --ignore=tests/test_plugins_walmart.py --ignore=tests/test_plugins_gamestop.py --ignore=tests/test_plugins_squareenix.py --ignore=tests/test_plugins_newegg.py`. Pre-existing + Wave 0 + this plan GREEN; other Wave 1 RED files remain RED.
  </action>
  <verify>
    <automated>python -c "from plugins.shopbot_plugin_target import TargetPlugin; from plugin_base import RetailerPlugin; assert issubclass(TargetPlugin, RetailerPlugin)"</automated>
    <automated>rtk grep -c "os.environ.get" plugins/shopbot_plugin_target.py</automated>
    <automated>rtk grep -n "selenium" plugins/shopbot_plugin_target.py</automated>
    <automated>rtk grep -n "Akamai" plugins/shopbot_plugin_target.py</automated>
    <automated>rtk grep -n "EXPERIMENTAL" plugins/shopbot_plugin_target.py</automated>
    <automated>rtk pytest -q tests/test_plugins_target.py</automated>
    <automated>rtk pytest -x -q --ignore=tests/test_plugins_walmart.py --ignore=tests/test_plugins_gamestop.py --ignore=tests/test_plugins_squareenix.py --ignore=tests/test_plugins_newegg.py</automated>
  </verify>
  <done>TargetPlugin (PLG-05) implemented; headless Akamai warning emitted; EXPERIMENTAL flag in docstring.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| SHOPBOT_ENABLE_RISKY_AUTOBUY env -> code | Risky autobuy gate |
| Target Akamai detection -> ban risk | Documented via WARNING when headless and via EXPERIMENTAL docstring |
| Target PDP DOM -> tab.select | Untrusted markup; nodriver returns DOM handles |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-06-03-ACCIDENTAL-PURCHASE | Tampering (cost) | TargetPlugin.auto_buy | mitigate | env-at-init gate; WARNING when off |
| T-06-03-AKAMAI-HEADLESS-BAN | Denial of Service | TargetPlugin.__init__ headless path | mitigate | Startup WARNING when headless=True flags the risk; user keeps headless=False by default |
| T-06-03-DRIVER-LEAK | Resource leak | TargetPlugin.shutdown | mitigate | await self.driver.stop() in try/except |
</threat_model>

<verification>
- `python -c "from plugins.shopbot_plugin_target import TargetPlugin; from plugin_base import RetailerPlugin; assert issubclass(TargetPlugin, RetailerPlugin)"`
- `rtk grep -c "os.environ.get" plugins/shopbot_plugin_target.py` returns 1
- `rtk pytest -q tests/test_plugins_target.py` GREEN
</verification>

<success_criteria>
- TargetPlugin subclass present
- domain_pattern == ["target.com"]
- Env-gated auto_buy; Akamai headless warning; EXPERIMENTAL docstring
- No selenium / notifier imports
- tests/test_plugins_target.py GREEN
</success_criteria>

<output>
After completion, create `.planning/phases/06-platform-expansion/06-03-SUMMARY.md`
</output>
