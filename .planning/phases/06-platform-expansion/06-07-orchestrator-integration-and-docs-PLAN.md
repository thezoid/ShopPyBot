---
phase: 06-platform-expansion
plan: 07
type: execute
wave: 2
depends_on: ["01", "02", "03", "04", "05", "06"]
files_modified:
  - main.py
  - plugins/shopbot_plugin_amazon.py
  - plugins/shopbot_plugin_bestbuy.py
  - plugins/PLUGIN_DEV.md
  - tests/test_orchestrator.py
  - tests/test_plugins_amazon.py
autonomous: true
requirements:
  - ANTI-01
  - ANTI-03
  - PLG-04
  - PLG-05
  - PLG-06
  - PLG-07
  - PLG-08
tags:
  - python
  - asyncio
  - orchestrator
  - integration
  - docs
  - wave-2

must_haves:
  truths:
    - "main.py poll_plugin replaces `delay = app_config.app.delay` + `await asyncio.wait_for(stop_event.wait(), timeout=delay)` with `await asyncio.wait_for(stop_event.wait(), timeout=plugin.next_delay())`. The delay is recomputed FRESH each iteration via plugin.next_delay() so jitter is per-poll, not per-startup (D-03 + RESEARCH Q9). AST grep verifies the new pattern is present AND the old `app_config.app.delay` reference inside poll_plugin is removed"
    - "main.py _poll_once branches on `inspect.iscoroutinefunction(plugin.check_availability)`: when True -> `await plugin.check_availability(link)`; when False -> `await asyncio.to_thread(plugin.check_availability, link)` (RESEARCH pitfall #11 + Pattern 1 note). Test covers both branches"
    - "main.py _attempt_purchase branches on `inspect.iscoroutinefunction(plugin.auto_buy)`: when True -> `await plugin.auto_buy(link, app_config)`; when False -> `await asyncio.to_thread(plugin.auto_buy, link, app_config)` (RESEARCH pitfall #11). Test covers both branches"
    - "main.py imports `inspect` at the top of the file (single new import)"
    - "plugins/shopbot_plugin_amazon.py __init__ raises `ValueError` with message containing 'AmazonPlugin does not support headless mode' AND 'OTP requires visual access' when `platform_config.headless is True AND self.login_at_startup is True` (RESEARCH Q11 + pitfall #9). The check happens BEFORE `build_driver` is called so a misconfigured Amazon never spawns a headless Chrome"
    - "plugins/shopbot_plugin_amazon.py __init__ passes `headless=platform_config.headless` AND `user_agents=user_agents` to `build_driver` (uses the Plan 06-01 extended factory). The user_agents kwarg was added to amazon/bestbuy __init__ in Plan 06-01 as a forward-compat no-op; this plan wires it through (D-04 + ANTI-02 + ANTI-03)"
    - "plugins/shopbot_plugin_bestbuy.py __init__ passes `headless=platform_config.headless` AND `user_agents=user_agents` to `build_driver` (D-04 + ANTI-02 + ANTI-03)"
    - "plugins/PLUGIN_DEV.md gains a new section `## Selenium vs nodriver: choosing a driver` documenting: (a) when to pick Selenium (Amazon-style flows with manual OTP/CAPTCHA; uses build_driver factory); (b) when to pick nodriver (PerimeterX/Akamai retailers; async-native via open() hook); (c) the open() lifecycle hook contract; (d) the SHOPBOT_ENABLE_RISKY_AUTOBUY env-var contract for plugins that do auto_buy on aggressive anti-bot retailers; (e) live-retailer integration tests are OUT OF SCOPE — contributors must mock nodriver.start AsyncMock in unit tests (RESEARCH Q10)"
    - "plugins/PLUGIN_DEV.md notes that PLUGIN_API_VERSION is still 1 (additive open() + next_delay() ABC changes do not bump the version per Phase 2 D-02 wording)"
    - "tests/test_plugins_amazon.py gains a new test `test_amazonHeadlessLoginRaises` asserting __init__ raises ValueError when headless=True AND login_at_startup=True. Existing Amazon tests stay green"
    - "tests/test_orchestrator.py gains: (1) test_pollPluginUsesNextDelay — fake plugin records `next_delay` calls; assert called at least once per poll iteration; (2) test_pollOnceAwaitsAsyncCheck — fake nodriver-style plugin with `async def check_availability`; assert orchestrator awaits it directly (NOT via asyncio.to_thread); (3) test_pollOnceToThreadSyncCheck — fake selenium-style plugin with sync `def check_availability`; assert orchestrator wraps via asyncio.to_thread; (4) test_attemptPurchaseAwaitsAsyncAutoBuy + test_attemptPurchaseToThreadSyncAutoBuy mirror (2)/(3) for auto_buy"
    - "Full Phase 1-6 pytest suite is GREEN after this plan lands. All 5 plugins routable via verify_coverage when their URLs appear in config.yml. All 8 Phase 6 requirements (PLG-04..08 + ANTI-01..03) satisfied"
    - "ANTI-01 satisfied: per-platform jitter via plugin.next_delay() in poll_plugin"
    - "ANTI-02 satisfied: app.user_agents threads through build_driver (Selenium) and uc.start browser_args (nodriver); random.choice per call"
    - "ANTI-03 satisfied: build_driver(headless) + uc.start(headless) honor PlatformConfig.headless; Amazon raises clear ValueError when headless conflicts with OTP login"
  artifacts:
    - path: "main.py"
      provides: "Orchestrator using plugin.next_delay() + iscoroutinefunction branches for async/sync plugin methods"
      contains: "iscoroutinefunction"
      min_lines: 200
    - path: "plugins/shopbot_plugin_amazon.py"
      provides: "Amazon plugin with headless-login conflict ValueError and headless/user_agents passthrough to build_driver"
      contains: "AmazonPlugin does not support headless mode"
    - path: "plugins/shopbot_plugin_bestbuy.py"
      provides: "BestBuy plugin with headless/user_agents passthrough to build_driver"
    - path: "plugins/PLUGIN_DEV.md"
      provides: "Selenium vs nodriver guidance + SHOPBOT_ENABLE_RISKY_AUTOBUY contract + open() lifecycle + live-test scope note"
      contains: "Selenium vs nodriver"
    - path: "tests/test_orchestrator.py"
      provides: "Tests for next_delay() integration + iscoroutinefunction branches"
    - path: "tests/test_plugins_amazon.py"
      provides: "Test for headless+login ValueError guard"
  key_links:
    - from: "main.poll_plugin"
      to: "plugin.next_delay"
      via: "await asyncio.wait_for(stop_event.wait(), timeout=plugin.next_delay())"
      pattern: "plugin\\.next_delay\\(\\)"
    - from: "main._poll_once"
      to: "inspect.iscoroutinefunction"
      via: "branch async plugin.check_availability vs to_thread sync"
      pattern: "iscoroutinefunction\\(plugin\\.check_availability"
    - from: "main._attempt_purchase"
      to: "inspect.iscoroutinefunction"
      via: "branch async plugin.auto_buy vs to_thread sync"
      pattern: "iscoroutinefunction\\(plugin\\.auto_buy"
    - from: "plugins/shopbot_plugin_amazon.py.__init__"
      to: "ValueError"
      via: "headless + login_at_startup conflict guard"
      pattern: "AmazonPlugin does not support headless mode"
    - from: "plugins/shopbot_plugin_amazon.py"
      to: "build_driver"
      via: "headless + user_agents kwargs passed through"
      pattern: "build_driver\\(.*headless"
---

<objective>
Wave 2 integration: tie Plan 06-01's foundation + the five Wave 1 plugins into the running orchestrator. Three surgical changes to `main.py`: (1) replace `app.delay` with `plugin.next_delay()` for per-platform jitter (ANTI-01); (2) branch `_poll_once` and `_attempt_purchase` on `inspect.iscoroutinefunction` so async nodriver plugins are awaited directly while sync Selenium plugins continue via `asyncio.to_thread` (RESEARCH pitfall #11). Wire Amazon and BestBuy to read `platform_config.headless` + `user_agents` and pass them to `build_driver` (ANTI-02 + ANTI-03). Add the Amazon headless+login_at_startup ValueError guard (RESEARCH Q11). Extend PLUGIN_DEV.md with a Selenium-vs-nodriver section.

Purpose: This is the final Phase 6 plan. After it lands, all 7 plugins (Amazon, BestBuy, Walmart, Target, GameStop, Square Enix, NewEgg) run in the same TaskGroup with per-platform jitter, the orchestrator transparently handles both async (nodriver) and sync (Selenium) plugin methods, headless is per-platform configurable, and the 5 phase exit criteria from ROADMAP.md Phase 6 are testable.

Output: extended main.py + Amazon ValueError guard + BestBuy/Amazon build_driver passthrough + PLUGIN_DEV.md nodriver section + extended tests/test_orchestrator.py + new test_plugins_amazon.py test.
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
@.planning/phases/06-platform-expansion/06-03-target-plugin-PLAN.md
@.planning/phases/06-platform-expansion/06-04-gamestop-plugin-PLAN.md
@.planning/phases/06-platform-expansion/06-05-squareenix-plugin-PLAN.md
@.planning/phases/06-platform-expansion/06-06-newegg-plugin-PLAN.md
@main.py
@plugin_base.py
@plugin_registry.py
@driver.py
@config_schema.py
@plugins/shopbot_plugin_amazon.py
@plugins/shopbot_plugin_bestbuy.py
@plugins/PLUGIN_DEV.md
@tests/test_orchestrator.py
@tests/test_plugins_amazon.py
</context>

<interfaces>
Target `main.py` changes (only the three diffs that matter — leave the rest intact):

```python
import inspect  # NEW

async def _poll_once(plugin, app_config, purchase_queue, notification_queue, open_browser):
    items = await asyncio.to_thread(get_items)
    for name, link, autoBuy, _qty, purchased in items:
        if purchased:
            continue
        matched = route_url(link, [plugin])
        if matched is None:
            continue
        try:
            if inspect.iscoroutinefunction(plugin.check_availability):
                available = await plugin.check_availability(link)
            else:
                available = await asyncio.to_thread(plugin.check_availability, link)
        except Exception as e:
            writeLog(f"{plugin.name}: check_availability raised on {link}: {e}", "ERROR")
            continue
        # ... rest unchanged

async def _attempt_purchase(plugin, link, name, app_config, purchase_queue, notification_queue):
    try:
        if inspect.iscoroutinefunction(plugin.auto_buy):
            await plugin.auto_buy(link, app_config)
        else:
            await asyncio.to_thread(plugin.auto_buy, link, app_config)
        # ... purchase_queue.put + notification_queue.put unchanged

async def poll_plugin(plugin, app_config, purchase_queue, notification_queue, stop_event):
    open_browser = getattr(app_config, "open_browser", False)
    while not stop_event.is_set():
        try:
            await _poll_once(plugin, app_config, purchase_queue, notification_queue, open_browser)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            writeLog(f"{plugin.name}: unexpected error: {e}", "ERROR")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=plugin.next_delay())
        except asyncio.TimeoutError:
            pass
```

Target `plugins/shopbot_plugin_amazon.py` __init__ changes:

```python
class AmazonPlugin(RetailerPlugin):
    domain_pattern: list[str] = ["amazon.com", "amzn.to"]
    login_at_startup: bool = True
    name: str = "amazon"

    def __init__(self, platform_config, *, cvv=None, driver_path=None, user_agents=None):
        super().__init__(platform_config)
        if platform_config.headless and self.login_at_startup:
            raise ValueError(
                "AmazonPlugin does not support headless mode: OTP requires "
                "visual access to the browser. Set platforms.amazon.headless: "
                "false (or omit) to use Amazon."
            )
        self.cvv = cvv
        self.driver = build_driver(
            driver_path or "chromedriver.exe",
            headless=platform_config.headless,
            user_agents=user_agents,
        )
```

Target `plugins/shopbot_plugin_bestbuy.py` __init__ changes (mirror Amazon but no ValueError guard):

```python
def __init__(self, platform_config, *, cvv=None, driver_path=None, user_agents=None):
    super().__init__(platform_config)
    self.cvv = cvv
    self.driver = build_driver(
        driver_path or "chromedriver.exe",
        headless=platform_config.headless,
        user_agents=user_agents,
    )
```

Target `plugins/PLUGIN_DEV.md` new section (append after existing contributor sections):

```markdown
## Selenium vs nodriver: choosing a driver

ShopPyBot supports two browser-automation drivers behind the same `RetailerPlugin` ABC. Pick one when implementing a new plugin:

| Driver | When to use | Lifecycle |
|--------|-------------|-----------|
| Selenium (via `build_driver`) | Retailer needs manual OTP / passkey / CAPTCHA-by-typing flows (Amazon-style). `self.driver = build_driver(driver_path, headless=..., user_agents=...)` in `__init__`. | Sync init in `__init__`; `shutdown()` default awaits `asyncio.to_thread(self.driver.quit)`. |
| nodriver (via `await uc.start`) | Retailer has strong anti-bot detection (PerimeterX, Akamai, HUMAN, hCaptcha). Async-native CDP-direct evades many fingerprint surfaces. | Build `self.driver` in `async def open(self)` (ABC default no-op); orchestrator awaits `open()` AFTER `__init__` AND BEFORE the next stagger sleep. Override `shutdown()` to `await self.driver.stop()`. |

### nodriver plugin checklist

1. `import nodriver as uc` at module top
2. `self.driver = None` in `__init__` (driver built in `open()`)
3. Override `async def open(self) -> None: self.driver = await uc.start(headless=..., browser_args=[f"--user-agent={ua}", "--disable-blink-features=AutomationControlled"])`
4. `check_availability` and `auto_buy` are `async def` and call `await self.driver.get(url)` and `await tab.select(...)`
5. Override `async def shutdown(self) -> None` to `await self.driver.stop()` with try/except + WARNING (no shutdown can crash the orchestrator)
6. DO NOT import `selenium` or any selenium.* submodule
7. DO NOT import from `notifier_base` or call `play_*_sound` directly — notifications fire via the orchestrator's `notification_queue`

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

The `open()` and `next_delay()` additions to `RetailerPlugin` in Phase 6 are non-abstract defaults (no-op + `random.uniform(self.min_delay, self.max_delay)`). Existing Phase 2 plugins continue to work unmodified. Additive defaults do not bump the API version.
```
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Wire orchestrator + Amazon headless guard (next_delay + iscoroutinefunction branches + headless/UA passthrough)</name>
  <files>main.py, plugins/shopbot_plugin_amazon.py, plugins/shopbot_plugin_bestbuy.py, tests/test_orchestrator.py, tests/test_plugins_amazon.py</files>
  <read_first>
    - main.py (current poll_plugin, _poll_once, _attempt_purchase)
    - plugins/shopbot_plugin_amazon.py (current __init__)
    - plugins/shopbot_plugin_bestbuy.py (current __init__)
    - plugin_base.py (Plan 06-01 next_delay default)
    - driver.py (Plan 06-01 build_driver headless + user_agents kwargs)
    - tests/test_orchestrator.py (existing GREEN Phase 4-5 tests to extend)
    - tests/test_plugins_amazon.py (existing GREEN tests to extend)
    - .planning/phases/06-platform-expansion/06-RESEARCH.md Q9, Q11, pitfall #9, pitfall #11
  </read_first>
  <behavior>
    - poll_plugin no longer references `app_config.app.delay`; calls `plugin.next_delay()` fresh each iteration.
    - _poll_once awaits async check_availability directly when `inspect.iscoroutinefunction(plugin.check_availability)` is True; wraps in `asyncio.to_thread` otherwise.
    - _attempt_purchase mirrors the same branch for auto_buy.
    - main.py imports `inspect` at top of file (single new import).
    - AmazonPlugin(platform_config, ...) with platform_config.headless=True AND login_at_startup=True raises ValueError with message containing both "AmazonPlugin does not support headless mode" AND "OTP requires visual access".
    - AmazonPlugin __init__ passes headless + user_agents kwargs to build_driver.
    - BestBuyPlugin __init__ passes headless + user_agents kwargs to build_driver.
    - tests/test_plugins_amazon.py: test_amazonHeadlessLoginRaises monkeypatches build_driver to a stub, builds PlatformConfig(headless=True, credentials=...), instantiates AmazonPlugin, asserts ValueError raised with the expected substrings AND build_driver was NEVER called (guard fires BEFORE build_driver).
    - tests/test_orchestrator.py extensions:
      - test_pollPluginUsesNextDelay: fake plugin records next_delay() calls; run poll_plugin briefly with a stop_event that fires after one iteration; assert next_delay called at least once.
      - test_pollOnceAwaitsAsyncCheck: fake plugin with `async def check_availability` returning False; _poll_once runs; assert check_availability called via await (no to_thread). Use a sentinel that AsyncMock vs Mock distinguishes.
      - test_pollOnceToThreadSyncCheck: fake plugin with sync `def check_availability` returning False; _poll_once runs; assert called via to_thread (introspect via asyncio's running tasks or by wrapping to_thread with a recorder).
      - test_attemptPurchaseAwaitsAsyncAutoBuy + test_attemptPurchaseToThreadSyncAutoBuy: mirror the above for auto_buy.
    - All existing Phase 4 + Phase 5 orchestrator tests stay GREEN (no regressions).
  </behavior>
  <action>
    1. Edit main.py:
       - Add `import inspect` at the top (in the existing import block).
       - Inside `_poll_once`: replace the existing `await asyncio.to_thread(plugin.check_availability, link)` line with the if/else branch on `inspect.iscoroutinefunction(plugin.check_availability)` per <interfaces>.
       - Inside `_attempt_purchase`: replace the existing `await asyncio.to_thread(plugin.auto_buy, link, app_config)` line with the if/else branch on `inspect.iscoroutinefunction(plugin.auto_buy)`.
       - Inside `poll_plugin`: remove the `delay = app_config.app.delay` line; change `await asyncio.wait_for(stop_event.wait(), timeout=delay)` to `await asyncio.wait_for(stop_event.wait(), timeout=plugin.next_delay())`.

    2. Edit plugins/shopbot_plugin_amazon.py __init__:
       - Add `user_agents=None` kwarg (already added in Plan 06-01 as forward-compat; if not present, add now).
       - Insert the headless+login_at_startup ValueError guard BEFORE the existing `self.driver = build_driver(...)` line.
       - Update the build_driver call to pass `headless=platform_config.headless, user_agents=user_agents`.

    3. Edit plugins/shopbot_plugin_bestbuy.py __init__:
       - Add `user_agents=None` kwarg if not already present.
       - Update the build_driver call to pass `headless=platform_config.headless, user_agents=user_agents`.

    4. Extend tests/test_plugins_amazon.py with `test_amazonHeadlessLoginRaises`:
       - monkeypatch `plugins.shopbot_plugin_amazon.build_driver` to a Mock that raises if called.
       - Build PlatformConfig(headless=True, credentials=PlatformCredentials(email="x", password="x"), min_delay=3, max_delay=8).
       - `with pytest.raises(ValueError, match="headless mode"):` instantiate AmazonPlugin.
       - Assert build_driver Mock.call_count == 0 (guard fires before build).

    5. Extend tests/test_orchestrator.py with the 5 new tests per <behavior>. Use the existing fakePluginFactory + introspection helpers; for to_thread vs await distinction, wrap `asyncio.to_thread` with a recording shim in a monkeypatch and inspect.

    6. Run `rtk pytest -q tests/test_plugins_amazon.py tests/test_orchestrator.py`. All GREEN (new + existing).

    7. Run `rtk pytest -q`. Full Phase 1-6 suite GREEN — including all 5 plugin test files from Wave 1 (Walmart, Target, GameStop, SquareEnix, NewEgg).
  </action>
  <verify>
    <automated>rtk grep -n "^import inspect" main.py</automated>
    <automated>rtk grep -n "iscoroutinefunction(plugin.check_availability" main.py</automated>
    <automated>rtk grep -n "iscoroutinefunction(plugin.auto_buy" main.py</automated>
    <automated>rtk grep -n "plugin.next_delay()" main.py</automated>
    <automated>rtk grep -n "app_config.app.delay" main.py</automated>
    <automated>rtk grep -n "AmazonPlugin does not support headless mode" plugins/shopbot_plugin_amazon.py</automated>
    <automated>rtk grep -n "build_driver(.*headless" plugins/shopbot_plugin_amazon.py plugins/shopbot_plugin_bestbuy.py</automated>
    <automated>rtk pytest -q tests/test_plugins_amazon.py tests/test_orchestrator.py</automated>
    <automated>rtk pytest -q</automated>
  </verify>
  <done>Orchestrator branches on iscoroutinefunction; jitter is per-platform via plugin.next_delay(); Amazon raises clear ValueError on headless+login conflict; Amazon/BestBuy thread headless + UA through build_driver. Phase 1-6 suite GREEN.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Extend PLUGIN_DEV.md with Selenium-vs-nodriver guidance section</name>
  <files>plugins/PLUGIN_DEV.md</files>
  <read_first>
    - plugins/PLUGIN_DEV.md (existing contributor sections — append below them)
    - .planning/phases/06-platform-expansion/06-RESEARCH.md Q10 (live-test scope) + Pattern 1 + Pattern 2
  </read_first>
  <behavior>
    - PLUGIN_DEV.md gains a "## Selenium vs nodriver: choosing a driver" section.
    - The section documents: the driver-choice table; the nodriver checklist; the SHOPBOT_ENABLE_RISKY_AUTOBUY gate pattern with code example; the live-retailer-integration-tests-out-of-scope policy; and the PLUGIN_API_VERSION = 1 stability note.
    - No emojis. No em dashes. No horizontal rules. No mention of Hermes/Openclaw (global instruction).
    - Section anchors are stable (markdown headings use `## ` and `### `).
  </behavior>
  <action>
    1. Read existing plugins/PLUGIN_DEV.md to find a logical insertion point (after the existing plugin template / before any "Testing" section).
    2. Append the new section verbatim from the <interfaces> block.
    3. Run `rtk grep -n "Selenium vs nodriver" plugins/PLUGIN_DEV.md` and confirm the heading exists.
    4. Run `rtk grep -n "SHOPBOT_ENABLE_RISKY_AUTOBUY" plugins/PLUGIN_DEV.md` and confirm the gate doc is present.
    5. Run `rtk grep -n "PLUGIN_API_VERSION" plugins/PLUGIN_DEV.md` and confirm the stability note is present.
    6. Verify no horizontal rules introduced (`rtk grep -n "^---$" plugins/PLUGIN_DEV.md` should match only existing frontmatter if present, no new occurrences).
  </action>
  <verify>
    <automated>rtk grep -n "Selenium vs nodriver" plugins/PLUGIN_DEV.md</automated>
    <automated>rtk grep -n "SHOPBOT_ENABLE_RISKY_AUTOBUY" plugins/PLUGIN_DEV.md</automated>
    <automated>rtk grep -n "Live-retailer integration tests" plugins/PLUGIN_DEV.md</automated>
    <automated>rtk grep -n "PLUGIN_API_VERSION" plugins/PLUGIN_DEV.md</automated>
  </verify>
  <done>PLUGIN_DEV.md documents the dual-driver contract, risky-autobuy gate, live-test scope, and ABC stability. Contributors can read this and ship a new nodriver plugin without touching core.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Orchestrator -> plugin.next_delay() | Plugin-controlled float; bounded by Plan 06-01 PlatformConfig validator (min_delay > 0, min_delay <= max_delay) |
| platform_config.headless -> AmazonPlugin __init__ | Misconfiguration would silently break OTP; guarded by explicit ValueError |
| inspect.iscoroutinefunction branch | Routing decision per-call; no untrusted input drives it (plugin author owns the method definition) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-06-07-DELAY-ZERO | Denial of Service (tight loop) | poll_plugin next_delay | mitigate | Plan 06-01 PlatformConfig validator rejects min_delay <= 0; next_delay always returns > 0 |
| T-06-07-AMAZON-HEADLESS-SILENT | Denial of Service (hung login) | AmazonPlugin __init__ | mitigate | Explicit ValueError before build_driver; user sees clear error, not a hung headless Chrome |
| T-06-07-COROUTINE-MIS-BRANCH | Tampering (functional) | _poll_once / _attempt_purchase | mitigate | inspect.iscoroutinefunction is the standard library detection; tests cover both branches with fake plugins |
| T-06-07-DOC-OUTDATED | Information Disclosure (contributor misled) | PLUGIN_DEV.md | accept | Doc maintenance is ongoing; Phase 6 section reflects current contract; future phases update if ABC changes |
</threat_model>

<verification>
- `rtk grep -n "plugin.next_delay()" main.py` matches the new wait_for line
- `rtk grep -n "iscoroutinefunction" main.py` matches both _poll_once and _attempt_purchase
- `rtk grep -n "AmazonPlugin does not support headless mode" plugins/shopbot_plugin_amazon.py` matches the guard
- `rtk grep -n "Selenium vs nodriver" plugins/PLUGIN_DEV.md` matches the new section
- `rtk pytest -q` runs the FULL Phase 1-6 suite GREEN
</verification>

<success_criteria>
- main.py uses plugin.next_delay() per-iteration (ANTI-01)
- main.py branches on inspect.iscoroutinefunction for check_availability and auto_buy
- AmazonPlugin raises ValueError on headless+login conflict (ANTI-03)
- AmazonPlugin and BestBuyPlugin thread headless + user_agents to build_driver (ANTI-02 + ANTI-03)
- PLUGIN_DEV.md documents Selenium-vs-nodriver, risky-autobuy gate, live-test scope, PLUGIN_API_VERSION stability
- tests/test_orchestrator.py extended with 5 new GREEN tests
- tests/test_plugins_amazon.py extended with headless guard test
- Full Phase 1-6 pytest suite GREEN
- All 8 Phase 6 requirements (PLG-04..08 + ANTI-01..03) satisfied across the 7 plans
</success_criteria>

<output>
After completion, create `.planning/phases/06-platform-expansion/06-07-SUMMARY.md`
</output>
