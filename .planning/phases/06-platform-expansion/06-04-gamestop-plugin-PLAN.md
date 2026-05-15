---
phase: 06-platform-expansion
plan: 04
type: execute
wave: 1
depends_on: ["01"]
files_modified:
  - plugins/shopbot_plugin_gamestop.py
  - tests/test_plugins_gamestop.py
autonomous: true
requirements:
  - PLG-06
tags:
  - python
  - nodriver
  - gamestop
  - hcaptcha
  - risky-autobuy
  - wave-1

must_haves:
  truths:
    - "plugins/shopbot_plugin_gamestop.py defines `class GamestopPlugin(RetailerPlugin)` with class attrs `domain_pattern = ['gamestop.com']`, `login_at_startup = False`, `name = 'gamestop'` (D-01)"
    - "GamestopPlugin.__init__(self, platform_config, *, cvv=None, driver_path=None, user_agents=None) accepts the Plan 06-01 user_agents kwarg"
    - "GamestopPlugin.__init__ reads `SHOPBOT_ENABLE_RISKY_AUTOBUY` ONCE; stores on `self._riskyAutoBuyEnabled` (D-02). AST grep enforces single os.environ.get in __init__"
    - "GamestopPlugin.__init__ stores min_delay/max_delay/headless/userAgents from platform_config (D-03 + D-04 + ANTI-02)"
    - "GamestopPlugin.open() async: builds nodriver.Browser via `await uc.start(headless, browser_args=[UA, --disable-blink-features=AutomationControlled])` (RESEARCH Pattern 1)"
    - "GamestopPlugin.check_availability(url) async: `tab = await self.driver.get(url); btn = await tab.select(<GameStop ATC selector>); return btn is not None`. Representative selector `button.add-to-cart:not(:disabled)` per RESEARCH per-retailer table; executor verifies live PDP (RESEARCH Q3 + O-5)"
    - "GamestopPlugin.detect_captcha() async, overrides Phase 1 default. Checks for hCaptcha iframe (`iframe[src*='hcaptcha.com']`) OR widget container (`div[data-hcaptcha-widget-id]`) on the current tab. Returns True if either resolves. AST grep verifies it is a coroutine (`inspect.iscoroutinefunction is True`)"
    - "GamestopPlugin.auto_buy(url, config) async: if not self._riskyAutoBuyEnabled -> WARNING + return False. Then proceeds with ATC + checkout flow. If detect_captcha returns True mid-flow: `await asyncio.to_thread(input, 'GameStop CAPTCHA detected; solve in the browser and press Enter to continue')` (D-02 + Phase 4 D-02 pattern + RESEARCH Q6 + pitfall #7). The input() blocks only the worker thread, not the event loop"
    - "GamestopPlugin.shutdown() async: await self.driver.stop() override (D-01); try/except + WARNING on failure"
    - "GamestopPlugin imports do NOT include `selenium` or any selenium.* submodule (RESEARCH pitfall #1). AST grep verifies"
    - "GamestopPlugin imports do NOT include `from notifier_base` or `from utils import play_*` (RESEARCH pitfall #10). AST grep verifies"
    - "GamestopPlugin.auto_buy uses `asyncio.to_thread(input, ...)`, NOT a bare `input(...)`. AST grep enforces: no top-level Call to `input` outside `asyncio.to_thread`"
    - "All RED tests in tests/test_plugins_gamestop.py from Plan 06-01 now PASS"
    - "Full pytest suite remains green; other Wave 1 sibling test files remain RED for their plans"
  artifacts:
    - path: "plugins/shopbot_plugin_gamestop.py"
      provides: "GamestopPlugin (PLG-06) — nodriver, risky-autobuy gated, hCaptcha pause via asyncio.to_thread(input)"
      contains: "class GamestopPlugin"
      min_lines: 90
    - path: "tests/test_plugins_gamestop.py"
      provides: "GREEN tests for PLG-06 (ABC contract, env gate, CAPTCHA detection + pause via to_thread, no selenium imports)"
      min_lines: 60
  key_links:
    - from: "plugins/shopbot_plugin_gamestop.py"
      to: "os.environ.get"
      via: "SHOPBOT_ENABLE_RISKY_AUTOBUY read once in __init__"
      pattern: "os\\.environ\\.get\\([\"']SHOPBOT_ENABLE_RISKY_AUTOBUY"
    - from: "GamestopPlugin.auto_buy"
      to: "asyncio.to_thread"
      via: "wraps input() for CAPTCHA pause (Phase 4 D-02 pattern)"
      pattern: "asyncio\\.to_thread\\(\\s*input"
    - from: "GamestopPlugin.detect_captcha"
      to: "tab.select"
      via: "iframe[src*='hcaptcha.com'] OR div[data-hcaptcha-widget-id]"
      pattern: "hcaptcha"
---

<objective>
Wave 1 (parallel-safe): ship `plugins/shopbot_plugin_gamestop.py` covering PLG-06. nodriver async plugin mirroring WalmartPlugin contract + GameStop-specific hCaptcha detection that pauses via `await asyncio.to_thread(input, ...)` (Phase 4 D-02 pattern). Flip RED tests in tests/test_plugins_gamestop.py to GREEN.

Purpose: GameStop CAPTCHA is the in-phase blocker. Phase 4 D-02 locked the to_thread(input) pattern; this plan reuses it inside a plugin method. Because the orchestrator already invokes plugin methods, `await asyncio.to_thread(input, ...)` blocks only the GameStop worker thread; the event loop continues serving other plugins.

Output: plugins/shopbot_plugin_gamestop.py + GREEN tests/test_plugins_gamestop.py.

File ownership: this plan EXCLUSIVELY owns the two files above. Zero overlap with 06-02/03/05/06 or with main.py/plugin_base.py/plugin_registry.py/driver.py/config_schema.py.
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
@tests/test_plugins_gamestop.py
</context>

<interfaces>
Target `plugins/shopbot_plugin_gamestop.py`:

```python
"""GameStop retailer plugin (PLG-06).

nodriver-based async plugin. GameStop uses hCaptcha at checkout — detected via
iframe selector + widget container. On detection, the plugin pauses via
`await asyncio.to_thread(input, ...)` so the user solves the CAPTCHA in the
visible browser and presses Enter (Phase 4 D-02 pattern). Auto-buy gated behind
SHOPBOT_ENABLE_RISKY_AUTOBUY=true.

DOM selectors representative — executor verifies against live GameStop PDP at
implementation time per RESEARCH O-5.
"""
import asyncio
import os
import random

import nodriver as uc

from driver import DEFAULT_USER_AGENTS
from logger import writeLog
from plugin_base import RetailerPlugin

_ATC_SELECTOR = 'button.add-to-cart:not(:disabled)'
_HCAPTCHA_IFRAME = 'iframe[src*="hcaptcha.com"]'
_HCAPTCHA_WIDGET = 'div[data-hcaptcha-widget-id]'


class GamestopPlugin(RetailerPlugin):
    domain_pattern: list[str] = ["gamestop.com"]
    login_at_startup: bool = False
    name: str = "gamestop"

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
        self._tab = None

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
            writeLog(f"GamestopPlugin.check_availability error on {url}: {e}", "ERROR")
            return False

    async def detect_captcha(self) -> bool:
        if self._tab is None:
            return False
        try:
            iframe = await self._tab.select(_HCAPTCHA_IFRAME)
            if iframe is not None:
                return True
            widget = await self._tab.select(_HCAPTCHA_WIDGET)
            return widget is not None
        except Exception as e:
            writeLog(f"GamestopPlugin.detect_captcha error: {e}", "TRACE")
            return False

    async def auto_buy(self, url: str, config) -> bool:
        if not self._riskyAutoBuyEnabled:
            writeLog(
                "GameStop auto_buy skipped: set SHOPBOT_ENABLE_RISKY_AUTOBUY=true to enable",
                "WARNING",
            )
            return False
        try:
            self._tab = await self.driver.get(url)
            atc = await self._tab.select(_ATC_SELECTOR)
            if atc is None:
                return False
            # Executor implements: click ATC, navigate to checkout, then captcha check.
            if await self.detect_captcha():
                writeLog("GameStop CAPTCHA detected; pausing for manual solve", "WARNING")
                await asyncio.to_thread(
                    input,
                    "GameStop CAPTCHA detected; solve in the browser and press Enter to continue",
                )
            # Executor implements: place order after captcha pause.
            return False
        except Exception as e:
            writeLog(f"GamestopPlugin.auto_buy error on {url}: {e}", "ERROR")
            return False

    async def shutdown(self) -> None:
        driver = getattr(self, "driver", None)
        if driver is None:
            return
        try:
            await driver.stop()
        except Exception as e:
            writeLog(f"GamestopPlugin.shutdown: driver.stop raised: {e}", "WARNING")
```
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Verify GameStop selectors against live PDP and checkout flow</name>
  <files>tests/test_plugins_gamestop.py</files>
  <read_first>
    - .planning/phases/06-platform-expansion/06-RESEARCH.md Q6, Q3, O-5 (selector + hCaptcha verification)
  </read_first>
  <behavior>
    - ATC selector matches the live GameStop PDP add-to-cart button.
    - hCaptcha selectors (`iframe[src*="hcaptcha.com"]`, `div[data-hcaptcha-widget-id]`) reflect current hCaptcha embeds. If GameStop has switched to reCAPTCHA v2 or another vendor, update accordingly.
  </behavior>
  <action>
    1. Open https://www.gamestop.com/ and inspect an in-stock PDP. Record ATC selector.
    2. Walk through checkout (without completing) to surface the CAPTCHA. Inspect the CAPTCHA iframe and container element.
    3. Update `_ATC_SELECTOR`, `_HCAPTCHA_IFRAME`, `_HCAPTCHA_WIDGET` if different.
    4. If verification impossible, accept defaults + add TODO in source.
  </action>
  <verify>
    <automated>echo "GameStop selectors verified or accepted defaults"</automated>
  </verify>
  <done>GameStop selectors confirmed or replaced.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement GamestopPlugin (PLG-06) and drive RED tests to GREEN</name>
  <files>plugins/shopbot_plugin_gamestop.py, tests/test_plugins_gamestop.py</files>
  <read_first>
    - plugin_base.py (ABC after Plan 06-01)
    - driver.py (DEFAULT_USER_AGENTS)
    - tests/conftest.py (fakeBrowser fixture)
    - tests/test_plugins_gamestop.py (Plan 06-01 RED skeleton — REWRITTEN here)
    - .planning/phases/04-async-orchestrator/04-CONTEXT.md D-02 (asyncio.to_thread input pattern)
    - .planning/phases/06-platform-expansion/06-RESEARCH.md Q6, pitfall #7 (event loop stays responsive)
  </read_first>
  <behavior>
    - Imports succeed; subclass of RetailerPlugin; domain_pattern == ["gamestop.com"]; login_at_startup False; name "gamestop".
    - open / check_availability / auto_buy / detect_captcha / shutdown all coroutines (`inspect.iscoroutinefunction is True` for each).
    - Env on: _riskyAutoBuyEnabled is True; await auto_buy does NOT early-return.
    - Env off: await auto_buy returns False + WARNING "SHOPBOT_ENABLE_RISKY_AUTOBUY".
    - Env read ONCE in __init__.
    - AST grep: os.environ.get appears once; no selenium imports; no notifier_base/play_* imports.
    - AST grep: every `input(` Call in the file is inside an `asyncio.to_thread` call (no bare `input(...)`).
    - detect_captcha with self._tab = None: returns False (no AttributeError).
    - detect_captcha with fakeTab.select returning iframe sentinel for _HCAPTCHA_IFRAME: returns True.
    - detect_captcha with fakeTab.select returning None for iframe but a sentinel for widget: returns True.
    - detect_captcha with both selectors returning None: returns False.
    - auto_buy with env on + CAPTCHA present: `asyncio.to_thread(input, ...)` is awaited; monkeypatch input to return immediately; flow continues without blocking the event loop. Verify by running multiple plugin tasks in parallel via asyncio.gather and confirming non-blocking.
    - shutdown handles None driver and stop() raising.
  </behavior>
  <action>
    1. Create `plugins/shopbot_plugin_gamestop.py` with contents from <interfaces>. Substitute Task 1 verified selectors if different.

    2. Rewrite tests/test_plugins_gamestop.py to GREEN.
       - fakeBrowser fixture; `monkeypatch.setattr("plugins.shopbot_plugin_gamestop.uc.start", AsyncMock(return_value=fakeBrowser))`.
       - For CAPTCHA tests: build a fake tab whose .select returns sentinels keyed by selector arg (a dict-driven side_effect).
       - For the to_thread test: `monkeypatch.setattr("builtins.input", lambda prompt="": "")` so the synchronous input returns immediately when wrapped by asyncio.to_thread.

    3. Test cases:
       - test_gamestopPluginImportable
       - test_gamestopSubclassesRetailerPlugin
       - test_gamestopAbcContract (all 5 coroutines including detect_captcha)
       - test_gamestopRiskyAutobuyGateOff
       - test_gamestopRiskyAutobuyGateOn
       - test_gamestopEnvReadOnce
       - test_gamestopNoSeleniumImport (AST grep)
       - test_gamestopNoNotifierImport (AST grep)
       - test_gamestopInputWrappedInToThread (AST grep: walk Call nodes; any `input` Call must have an ancestor `asyncio.to_thread` Call)
       - test_gamestopDetectCaptchaIframe (sentinel for iframe selector -> True)
       - test_gamestopDetectCaptchaWidget (iframe None, widget sentinel -> True)
       - test_gamestopDetectCaptchaAbsent (both None -> False)
       - test_gamestopDetectCaptchaNullTab (self._tab None -> False, no exception)
       - test_gamestopCaptchaPauseNonBlocking: monkeypatch input to return ""; build PlatformConfig + fakeBrowser; setenv risky=true; build two GamestopPlugin instances; run `await asyncio.gather(p1.auto_buy(...), p2.auto_buy(...))` and assert both complete within a short timeout (proves the to_thread bridge keeps the event loop responsive)
       - test_gamestopCheckAvailability (sentinel + None)
       - test_gamestopOpenCallsUcStart
       - test_gamestopUaRotation
       - test_gamestopShutdownNoDriver, test_gamestopShutdownDriverStopRaises

    4. Run `rtk pytest -q tests/test_plugins_gamestop.py`. All GREEN.

    5. Run `rtk pytest -x -q --ignore=tests/test_plugins_walmart.py --ignore=tests/test_plugins_target.py --ignore=tests/test_plugins_squareenix.py --ignore=tests/test_plugins_newegg.py`. Pre-existing + Wave 0 + this plan GREEN.
  </action>
  <verify>
    <automated>python -c "from plugins.shopbot_plugin_gamestop import GamestopPlugin; from plugin_base import RetailerPlugin; assert issubclass(GamestopPlugin, RetailerPlugin)"</automated>
    <automated>rtk grep -c "os.environ.get" plugins/shopbot_plugin_gamestop.py</automated>
    <automated>rtk grep -n "selenium" plugins/shopbot_plugin_gamestop.py</automated>
    <automated>rtk grep -n "asyncio.to_thread" plugins/shopbot_plugin_gamestop.py</automated>
    <automated>rtk grep -n "hcaptcha" plugins/shopbot_plugin_gamestop.py</automated>
    <automated>rtk pytest -q tests/test_plugins_gamestop.py</automated>
    <automated>rtk pytest -x -q --ignore=tests/test_plugins_walmart.py --ignore=tests/test_plugins_target.py --ignore=tests/test_plugins_squareenix.py --ignore=tests/test_plugins_newegg.py</automated>
  </verify>
  <done>GamestopPlugin (PLG-06) implemented with hCaptcha pause via asyncio.to_thread(input); event loop stays responsive.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| SHOPBOT_ENABLE_RISKY_AUTOBUY env -> code | Risky autobuy gate |
| hCaptcha iframe (untrusted external) -> tab.select | hCaptcha is third-party but read-only via DOM; no execution path |
| stdin via input() -> code | User-controlled but only after explicit CAPTCHA prompt; no command injection surface |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-06-04-ACCIDENTAL-PURCHASE | Tampering (cost) | GamestopPlugin.auto_buy | mitigate | env-at-init gate; WARNING when off |
| T-06-04-CAPTCHA-DEADLOCK | Denial of Service | auto_buy input() pause | mitigate | `asyncio.to_thread(input, ...)` blocks only the GameStop worker thread; event loop continues serving other plugins (Phase 4 D-02 pattern) |
| T-06-04-DRIVER-LEAK | Resource leak | shutdown | mitigate | await self.driver.stop() in try/except |
| T-06-04-CAPTCHA-FALSE-POSITIVE | Denial of Service | detect_captcha | accept | Worst case: spurious pause that user resolves by pressing Enter; cost is one Enter keypress |
</threat_model>

<verification>
- `python -c "from plugins.shopbot_plugin_gamestop import GamestopPlugin; from plugin_base import RetailerPlugin; assert issubclass(GamestopPlugin, RetailerPlugin)"`
- `rtk grep -c "os.environ.get" plugins/shopbot_plugin_gamestop.py` returns 1
- `rtk pytest -q tests/test_plugins_gamestop.py` GREEN
</verification>

<success_criteria>
- GamestopPlugin subclass present
- domain_pattern == ["gamestop.com"]
- Env-gated auto_buy; detect_captcha (async); asyncio.to_thread(input) pause
- No selenium / notifier imports
- tests/test_plugins_gamestop.py GREEN
</success_criteria>

<output>
After completion, create `.planning/phases/06-platform-expansion/06-04-SUMMARY.md`
</output>
