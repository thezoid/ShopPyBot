---
phase: 06-platform-expansion
plan: 02
type: execute
wave: 1
depends_on: ["01"]
files_modified:
  - plugins/shopbot_plugin_walmart.py
  - tests/test_plugins_walmart.py
autonomous: true
requirements:
  - PLG-04
tags:
  - python
  - nodriver
  - walmart
  - perimeterx
  - risky-autobuy
  - wave-1

must_haves:
  truths:
    - "plugins/shopbot_plugin_walmart.py defines `class WalmartPlugin(RetailerPlugin)` with class attrs `domain_pattern = ['walmart.com']`, `login_at_startup = False`, `name = 'walmart'` (D-01 + CONTEXT canonical_refs)"
    - "WalmartPlugin.__init__(self, platform_config, *, cvv=None, driver_path=None, user_agents=None) accepts the foundation-plan `user_agents` kwarg from _instantiate (Plan 06-01 contract)"
    - "WalmartPlugin.__init__ reads `os.environ.get('SHOPBOT_ENABLE_RISKY_AUTOBUY', '').strip().lower() == 'true'` ONCE and stores on `self._riskyAutoBuyEnabled` (D-02 env-at-init, mirrors Phase 5 SMS pattern). AST grep enforces: os.environ.get appears ONLY in __init__, never in auto_buy or check_availability"
    - "WalmartPlugin.__init__ initializes `self._walmartRiskNoted = False` (one-time PerimeterX INFO log gate per CONTEXT pitfall #6 / RESEARCH pitfall #6)"
    - "WalmartPlugin.__init__ stores `self.min_delay = platform_config.min_delay` and `self.max_delay = platform_config.max_delay` from PlatformConfig (D-03)"
    - "WalmartPlugin.__init__ stores `self._headless = platform_config.headless` and `self._userAgents = user_agents or DEFAULT_USER_AGENTS` (D-04 + ANTI-02). DOES NOT call uc.start in __init__ (RESEARCH anti-pattern: never asyncio.run inside __init__)"
    - "WalmartPlugin.open() is async, calls `self.driver = await uc.start(headless=self._headless, browser_args=[f'--user-agent={random.choice(self._userAgents)}', '--disable-blink-features=AutomationControlled'])`. Called ONCE by discover_async after instantiation (RESEARCH Q1, Q2)"
    - "WalmartPlugin.check_availability(url) is async. Calls `tab = await self.driver.get(url)` then `await tab.select(<Walmart ATC selector>)`. Returns True when the selector resolves to a non-None element. Plan-time selector verification: representative `button[data-automation-id='atc-button']` per RESEARCH per-retailer table; executor MUST verify against the live Walmart PDP before locking the selector (RESEARCH Q3 + O-5)"
    - "WalmartPlugin.auto_buy(url, config) is async. First check: if not self._riskyAutoBuyEnabled -> writeLog WARNING 'Walmart auto_buy skipped: set SHOPBOT_ENABLE_RISKY_AUTOBUY=true to enable'; return False. Then: if not self._walmartRiskNoted -> writeLog INFO 'Walmart auto_buy: PerimeterX/HUMAN may block automation; see SECURITY.md' AND set self._walmartRiskNoted = True. Then proceed with purchase flow (add-to-cart -> checkout -> place-order) using `await tab.select` / `await element.click` (D-02 + RESEARCH pitfall #6 + #12)"
    - "WalmartPlugin.shutdown() is async, overrides Phase 4 default. Calls `await self.driver.stop()` (D-01 nodriver API). Wraps in try/except: failures log WARNING and swallow (no shutdown can crash the orchestrator's gather)"
    - "WalmartPlugin imports do NOT include `selenium` or any selenium.* submodule (RESEARCH pitfall #1: nodriver plugins import cleanly without selenium present). AST grep verifies"
    - "WalmartPlugin imports do NOT include `from notifier_base` or `from utils import play_*` (RESEARCH pitfall #10: notifications fire via orchestrator queue, never plugin-level)"
    - "Walmart auto_buy is gated by the env var: when off, no DOM interaction happens and the WARNING fires"
    - "When env is on AND auto_buy is called twice: INFO PerimeterX note appears exactly ONCE; second call skips the note (self._walmartRiskNoted gate)"
    - "All RED tests in tests/test_plugins_walmart.py from Plan 06-01 now PASS"
    - "Full pytest suite remains green across Phase 1-6 (no regressions); other Wave 1 sibling test files (target/gamestop/squareenix/newegg) remain RED for their plans"
  artifacts:
    - path: "plugins/shopbot_plugin_walmart.py"
      provides: "WalmartPlugin (PLG-04) — nodriver, risky-autobuy gated, one-time PerimeterX INFO note"
      contains: "class WalmartPlugin"
      min_lines: 80
    - path: "tests/test_plugins_walmart.py"
      provides: "GREEN tests for PLG-04 (ABC contract, env gate, one-time risk note, domain pattern, no selenium imports)"
      min_lines: 60
  key_links:
    - from: "plugins/shopbot_plugin_walmart.py"
      to: "os.environ.get"
      via: "SHOPBOT_ENABLE_RISKY_AUTOBUY read once in __init__"
      pattern: "os\\.environ\\.get\\([\"']SHOPBOT_ENABLE_RISKY_AUTOBUY"
    - from: "WalmartPlugin.open"
      to: "nodriver.start"
      via: "await uc.start(headless, browser_args)"
      pattern: "await\\s+uc\\.start"
    - from: "WalmartPlugin.shutdown"
      to: "self.driver.stop"
      via: "await self.driver.stop() override"
      pattern: "await\\s+self\\.driver\\.stop"
    - from: "WalmartPlugin.auto_buy"
      to: "self._walmartRiskNoted"
      via: "one-time PerimeterX INFO note gate"
      pattern: "_walmartRiskNoted"
---

<objective>
Wave 1 (parallel-safe): ship `plugins/shopbot_plugin_walmart.py` covering PLG-04. Async-native nodriver plugin: builds its `nodriver.Browser` in the new `open()` lifecycle hook (Plan 06-01 contract); reads `SHOPBOT_ENABLE_RISKY_AUTOBUY` ONCE at `__init__`; gates auto_buy behind the env var; logs the PerimeterX risk INFO note exactly once per instance via `self._walmartRiskNoted`. Flip RED tests in tests/test_plugins_walmart.py to GREEN.

Purpose: Walmart is the highest-risk retailer in Phase 6 (PerimeterX/HUMAN). The env gate + one-time INFO note pattern keep the failure mode loud-but-safe: users opting in to risky autobuy see exactly one warning per session pointing at SECURITY.md, NOT a log flood.

Output: plugins/shopbot_plugin_walmart.py + GREEN tests/test_plugins_walmart.py.

File ownership: this plan EXCLUSIVELY owns the two files above. No edits to main.py, plugin_base.py, plugin_registry.py, driver.py, or config_schema.py — those landed in Plan 06-01.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/06-platform-expansion/06-CONTEXT.md
@.planning/phases/06-platform-expansion/06-RESEARCH.md
@.planning/phases/06-platform-expansion/06-01-foundation-and-red-skeletons-PLAN.md
@plugin_base.py
@config_schema.py
@driver.py
@logger.py
@tests/conftest.py
@tests/test_plugins_walmart.py
@plugins/shopbot_plugin_amazon.py
</context>

<interfaces>
Target `plugins/shopbot_plugin_walmart.py`:

```python
"""Walmart retailer plugin (PLG-04).

nodriver-based async plugin. PerimeterX/HUMAN risk is documented in SECURITY.md
and logged once per instance on first auto_buy attempt. Risky auto_buy is gated
behind SHOPBOT_ENABLE_RISKY_AUTOBUY=true (D-02 mirrors Phase 5 SMS two-lock pattern).

DOM selectors representative — executor verifies against live Walmart PDP at
implementation time per RESEARCH O-5.
"""
import os
import random

import nodriver as uc

from driver import DEFAULT_USER_AGENTS
from logger import writeLog
from plugin_base import RetailerPlugin

_ATC_SELECTOR = 'button[data-automation-id="atc-button"]'


class WalmartPlugin(RetailerPlugin):
    domain_pattern: list[str] = ["walmart.com"]
    login_at_startup: bool = False
    name: str = "walmart"

    def __init__(self, platform_config, *, cvv=None, driver_path=None, user_agents=None):
        super().__init__(platform_config)
        self._riskyAutoBuyEnabled = (
            os.environ.get("SHOPBOT_ENABLE_RISKY_AUTOBUY", "").strip().lower() == "true"
        )
        self._walmartRiskNoted = False
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
            atc = await tab.select(_ATC_SELECTOR)
            return atc is not None
        except Exception as e:
            writeLog(f"WalmartPlugin.check_availability error on {url}: {e}", "ERROR")
            return False

    async def auto_buy(self, url: str, config) -> bool:
        if not self._riskyAutoBuyEnabled:
            writeLog(
                "Walmart auto_buy skipped: set SHOPBOT_ENABLE_RISKY_AUTOBUY=true to enable",
                "WARNING",
            )
            return False
        if not self._walmartRiskNoted:
            writeLog(
                "Walmart auto_buy: PerimeterX/HUMAN may block automation; see SECURITY.md",
                "INFO",
            )
            self._walmartRiskNoted = True
        try:
            tab = await self.driver.get(url)
            atc = await tab.select(_ATC_SELECTOR)
            if atc is None:
                return False
            # Executor implements: click ATC, navigate to cart, checkout, place order.
            # Each click via `await element.click()`; intermediate waits via `await tab.select(...)`.
            return False  # placeholder until executor wires the full flow
        except Exception as e:
            writeLog(f"WalmartPlugin.auto_buy error on {url}: {e}", "ERROR")
            return False

    async def shutdown(self) -> None:
        driver = getattr(self, "driver", None)
        if driver is None:
            return
        try:
            await driver.stop()
        except Exception as e:
            writeLog(f"WalmartPlugin.shutdown: driver.stop raised: {e}", "WARNING")
```
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Verify Walmart ATC DOM selector against live PDP</name>
  <files>tests/test_plugins_walmart.py</files>
  <read_first>
    - .planning/phases/06-platform-expansion/06-RESEARCH.md Q3, O-5 (selector verification mandate)
  </read_first>
  <behavior>
    - The Walmart add-to-cart selector encoded in `_ATC_SELECTOR` (default: `button[data-automation-id="atc-button"]`) reflects the CURRENT live Walmart PDP add-to-cart button.
    - If the live page now uses a different selector (e.g., `[data-testid="..."]`, `data-cy="..."`, or a text-based match), the constant is updated AND the test reflects the verified selector.
  </behavior>
  <action>
    1. Manually open https://www.walmart.com/ and load any item PDP (preferably one in stock and one out of stock). Use browser devtools to inspect the "Add to cart" button.
    2. Record the most stable selector. Preference order: data-automation-id > data-testid > role+name > class. Avoid id (Walmart reuses generic ids).
    3. If different from `button[data-automation-id="atc-button"]`, update `_ATC_SELECTOR` in <interfaces> for the implementation task AND record the verified selector in the test file as a module-level constant `EXPECTED_ATC_SELECTOR`.
    4. If verification is impossible at execution time (offline, blocked), accept the default selector and add a TODO comment in the source file: `# TODO: re-verify against live Walmart PDP — see Plan 06-02 Task 1`.
    5. No file edit needed unless the selector changed; if it changed, this task pre-stages the constant inside tests/test_plugins_walmart.py so Task 2 picks it up.
  </action>
  <verify>
    <automated>echo "Selector verification recorded in tests/test_plugins_walmart.py or accepted default"</automated>
  </verify>
  <done>Walmart ATC selector either confirmed accurate or replaced with verified equivalent.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement WalmartPlugin (PLG-04) and drive RED tests to GREEN</name>
  <files>plugins/shopbot_plugin_walmart.py, tests/test_plugins_walmart.py</files>
  <read_first>
    - plugin_base.py (RetailerPlugin ABC after Plan 06-01 changes: open(), next_delay(), min_delay/max_delay class attrs)
    - config_schema.py (PlatformConfig with min_delay/max_delay/headless + Optional credentials)
    - driver.py (DEFAULT_USER_AGENTS constant)
    - tests/conftest.py (fakeBrowser fixture from Plan 06-01)
    - tests/test_plugins_walmart.py (RED skeleton from Plan 06-01 — to be REWRITTEN here)
    - plugins/shopbot_plugin_amazon.py (Selenium template reference — DO NOT import selenium in Walmart)
    - .planning/phases/06-platform-expansion/06-RESEARCH.md Pattern 1 (full nodriver plugin skeleton)
  </read_first>
  <behavior>
    - `from plugins.shopbot_plugin_walmart import WalmartPlugin` succeeds with nodriver installed.
    - issubclass(WalmartPlugin, RetailerPlugin); domain_pattern == ["walmart.com"]; login_at_startup is False; name == "walmart".
    - `inspect.iscoroutinefunction(WalmartPlugin.open) is True`.
    - `inspect.iscoroutinefunction(WalmartPlugin.check_availability) is True`.
    - `inspect.iscoroutinefunction(WalmartPlugin.auto_buy) is True`.
    - `inspect.iscoroutinefunction(WalmartPlugin.shutdown) is True`.
    - With env SHOPBOT_ENABLE_RISKY_AUTOBUY unset: instance._riskyAutoBuyEnabled is False; await auto_buy(url, config) returns False AND WARNING with "set SHOPBOT_ENABLE_RISKY_AUTOBUY=true" captured.
    - With env SHOPBOT_ENABLE_RISKY_AUTOBUY=true: instance._riskyAutoBuyEnabled is True; await auto_buy(url, config) does NOT early-return on the env gate.
    - With env on, calling auto_buy twice: INFO log "PerimeterX" fires exactly once; self._walmartRiskNoted toggles False -> True after first call.
    - Env vars are read ONCE in __init__: setting env after instantiation does NOT change instance._riskyAutoBuyEnabled.
    - AST grep: os.environ.get appears exactly ONCE in the file, inside __init__.
    - AST grep: no `import selenium` or `from selenium` anywhere in the file.
    - AST grep: no `from notifier_base` and no `play_available_sound`/`play_buy_sound`/`play_notification_sound` references (RESEARCH pitfall #10).
    - shutdown() with self.driver = None returns cleanly (no AttributeError).
    - shutdown() with a fakeBrowser whose .stop() raises -> WARNING log fires, no exception propagates.
    - check_availability uses `await self.driver.get(url)` and `await tab.select(...)`; selector value matches the verified ATC selector from Task 1.
    - open() builds `uc.start` with browser_args containing `--user-agent=<UA>` AND `--disable-blink-features=AutomationControlled`; `headless=platform_config.headless` is passed through.
    - UA passed to uc.start is `random.choice(user_agents or DEFAULT_USER_AGENTS)` — monkeypatch random.choice to verify rotation.
    - File stays under 200 lines; every function under 30 lines; nesting depth max 3.
  </behavior>
  <action>
    1. Create `plugins/shopbot_plugin_walmart.py` with the contents from <interfaces>. Replace `_ATC_SELECTOR` with the Task 1 verified selector if different.

    2. Rewrite tests/test_plugins_walmart.py to GREEN. Build test infrastructure:
       - Use the `fakeBrowser` fixture from tests/conftest.py (Plan 06-01).
       - `monkeypatch.setattr("plugins.shopbot_plugin_walmart.uc.start", AsyncMock(return_value=fakeBrowser))` so `await open()` returns the fakeBrowser without spawning Chrome.
       - `monkeypatch.setenv` / `monkeypatch.delenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", raising=False)` per test.
       - Build PlatformConfig with explicit min_delay=3, max_delay=8, headless=False, credentials=None.
       - Capture writeLog calls via a fixture that monkeypatches `logger.writeLog` to record args.

    3. Test cases (replacing the Plan 06-01 RED skeleton):
       - test_walmartPluginImportable: import succeeds.
       - test_walmartSubclassesRetailerPlugin: issubclass + domain_pattern + login_at_startup + name attrs correct.
       - test_walmartAbcContract: open / check_availability / auto_buy / shutdown all coroutines.
       - test_walmartRiskyAutobuyGateOff: delenv; instantiate; await open(); await auto_buy(url, cfg) -> returns False; WARNING captured with "SHOPBOT_ENABLE_RISKY_AUTOBUY".
       - test_walmartRiskyAutobuyGateOn: setenv true; instantiate; assert _riskyAutoBuyEnabled is True.
       - test_walmartRiskNoteLoggedOnce: setenv true; await open(); call auto_buy twice; assert INFO with "PerimeterX" appears exactly ONCE; assert self._walmartRiskNoted is True after first call.
       - test_walmartEnvReadOnce: setenv; instantiate; delenv; assert _riskyAutoBuyEnabled is True still; AST grep on the source file asserts `os.environ.get` Call appears only in __init__ scope.
       - test_walmartNoSeleniumImport: parse the source file AST; walk Import / ImportFrom; assert no module name starts with "selenium".
       - test_walmartNoNotifierImport: AST grep — no ImportFrom with module "notifier_base" or "utils" with `play_*` names.
       - test_walmartOpenCallsUcStart: monkeypatch uc.start to AsyncMock; await open(); assert called once with headless=False AND browser_args containing the chosen UA prefix AND "--disable-blink-features=AutomationControlled".
       - test_walmartUaRotation: monkeypatch random.choice to return distinct UAs across two instances; assert uc.start receives DIFFERENT --user-agent= args per build.
       - test_walmartCheckAvailability: fakeBrowser.select returns a sentinel object; await check_availability(url) -> True. fakeBrowser.select returns None -> False.
       - test_walmartShutdownNoDriver: instance.driver = None; await shutdown(); no exception, no log spam.
       - test_walmartShutdownDriverStopRaises: fakeBrowser.stop raises RuntimeError; await shutdown(); WARNING logged; no exception propagates.

    4. Run `rtk pytest -q tests/test_plugins_walmart.py`. All GREEN.

    5. Run `rtk pytest -x -q --ignore=tests/test_plugins_target.py --ignore=tests/test_plugins_gamestop.py --ignore=tests/test_plugins_squareenix.py --ignore=tests/test_plugins_newegg.py`. Pre-existing + Wave 0 + this plan green; other Wave 1 sibling RED files remain RED for their plans.
  </action>
  <verify>
    <automated>python -c "from plugins.shopbot_plugin_walmart import WalmartPlugin; from plugin_base import RetailerPlugin; assert issubclass(WalmartPlugin, RetailerPlugin)"</automated>
    <automated>rtk grep -c "os.environ.get" plugins/shopbot_plugin_walmart.py</automated>
    <automated>rtk grep -n "selenium" plugins/shopbot_plugin_walmart.py</automated>
    <automated>rtk grep -n "_walmartRiskNoted" plugins/shopbot_plugin_walmart.py</automated>
    <automated>rtk grep -n "await\s\+self\.driver\.stop" plugins/shopbot_plugin_walmart.py</automated>
    <automated>rtk pytest -q tests/test_plugins_walmart.py</automated>
    <automated>rtk pytest -x -q --ignore=tests/test_plugins_target.py --ignore=tests/test_plugins_gamestop.py --ignore=tests/test_plugins_squareenix.py --ignore=tests/test_plugins_newegg.py</automated>
  </verify>
  <done>WalmartPlugin (PLG-04) implemented. Plan 06-07 (Wave 2) will wire it into the orchestrator's iscoroutinefunction branch.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| SHOPBOT_ENABLE_RISKY_AUTOBUY env -> code | Single source of truth for risky autobuy; missing => check-only mode |
| Walmart PDP DOM (untrusted external) -> tab.select | Untrusted attacker-controlled markup could theoretically inject HTML; nodriver returns DOM handles, not raw strings |
| Walmart PerimeterX detection -> behavioral signal | Bot may be flagged + banned; documented risk via one-time INFO note |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-06-02-ACCIDENTAL-PURCHASE | Tampering (cost) | WalmartPlugin.auto_buy | mitigate | env-at-init gate (SHOPBOT_ENABLE_RISKY_AUTOBUY); WARNING fires when off; D-02 pattern |
| T-06-02-ACCOUNT-BAN | Repudiation | WalmartPlugin.auto_buy multi-step flow | accept | Documented via one-time INFO note pointing at SECURITY.md; deep PerimeterX bypass deferred per CONTEXT defer item |
| T-06-02-DRIVER-LEAK | Resource leak | WalmartPlugin.shutdown | mitigate | shutdown() override calls await self.driver.stop() in try/except; orchestrator wraps in asyncio.shield |
| T-06-02-LOG-FLOOD | Denial of Service (log volume) | WalmartPlugin.auto_buy INFO note | mitigate | self._walmartRiskNoted gate; INFO fires exactly once per plugin instance |
</threat_model>

<verification>
- `python -c "from plugins.shopbot_plugin_walmart import WalmartPlugin; from plugin_base import RetailerPlugin; assert issubclass(WalmartPlugin, RetailerPlugin)"`
- `rtk grep -c "os.environ.get" plugins/shopbot_plugin_walmart.py` returns 1
- `rtk grep -n "selenium" plugins/shopbot_plugin_walmart.py` returns no matches
- `rtk pytest -q tests/test_plugins_walmart.py` shows all GREEN
- `rtk pytest -x -q --ignore=tests/test_plugins_target.py --ignore=tests/test_plugins_gamestop.py --ignore=tests/test_plugins_squareenix.py --ignore=tests/test_plugins_newegg.py` GREEN
</verification>

<success_criteria>
- WalmartPlugin subclass of RetailerPlugin present in plugins/
- domain_pattern == ["walmart.com"]; login_at_startup False; name "walmart"
- SHOPBOT_ENABLE_RISKY_AUTOBUY read once at __init__
- One-time PerimeterX INFO note via self._walmartRiskNoted
- open() uses await uc.start with headless + UA browser_args
- shutdown() override uses await self.driver.stop()
- No selenium imports; no plugin-level notifier imports
- tests/test_plugins_walmart.py fully GREEN
</success_criteria>

<output>
After completion, create `.planning/phases/06-platform-expansion/06-02-SUMMARY.md`
</output>
