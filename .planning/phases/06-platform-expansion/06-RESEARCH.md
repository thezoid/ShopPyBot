# Phase 6: Platform Expansion - Research

**Researched:** 2026-05-15
**Domain:** async browser automation (nodriver) + per-platform anti-detection + Pydantic schema extension
**Confidence:** HIGH on infra mechanics (nodriver API, build_driver headless, schema fields, jitter wiring); MEDIUM on retailer-specific DOM selectors (must be re-verified at plan time, retailers reflow their pages); LOW on PerimeterX/Akamai bypass success rates (probabilistic, depend on session history not just code).

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** All 5 new plugins use nodriver. Amazon/BestBuy stay on Selenium. ABC stays driver-agnostic (no type constraint on `self.driver`). nodriver pinned in requirements.txt. `build_driver` is NOT used by nodriver plugins. nodriver `shutdown()` calls `await self.driver.stop()` (overrides Phase 4 D-04 default which uses `asyncio.to_thread(driver.quit)`).
- **D-02:** All 5 plugins ship full auto-buy, gated at runtime by `SHOPBOT_ENABLE_RISKY_AUTOBUY=true` env var. Read ONCE in `__init__` (env-at-init pattern, mirrors Phase 5 D-04 SMS two-lock). Stored on `self._riskyAutoBuyEnabled: bool`. Without env: `auto_buy` logs WARNING via writeLog and returns False. `check_availability` is unaffected. CAPTCHA flow uses `await asyncio.to_thread(input, "...")` per Phase 4 D-02. Walmart additionally logs one-time INFO about PerimeterX risk on first `auto_buy` call (via `self._walmartRiskNoted` flag).
- **D-03:** `min_delay: float` and `max_delay: float` live on `PlatformConfig`. Defaults `min_delay=3.0`, `max_delay=8.0`. Plugin's `__init__` reads them into `self.min_delay`/`self.max_delay`. New non-abstract `RetailerPlugin.next_delay() -> float` returns `random.uniform(self.min_delay, self.max_delay)`. Orchestrator `poll_plugin` in main.py switches from `await asyncio.wait_for(stop_event.wait(), timeout=app_config.app.delay)` to using `plugin.next_delay()`.
- **D-04:** `build_driver(driver_path, log_path="logs/chromedriver.log", headless: bool = False)`. `headless=True` adds `--headless=new` (NOT bare `--headless`). `PlatformConfig.headless: bool = False`. nodriver plugins do NOT call `build_driver`; they pass `headless=` through to `uc.start()`.

### Claude's Discretion
- ANTI-02 UA rotation shape — recommend `app.user_agents: list[str] | None = None` (with bundled default), `random.choice` per `build_driver` call.
- Plugin name resolution — Phase 2 D-04 convention (filename stem, `shopbot_plugin_` prefix removed).
- `domain_pattern` per plugin — research recommendations below.
- Test strategy — mock-driver smoke + DOM-parse unit + ABC contract; integration tests out of scope, flagged in PLUGIN_DEV.md.
- nodriver async lifecycle handling — research recommendation below (open() pattern).
- GameStop CAPTCHA flow timing — confirmed via Phase 4 D-02 pattern.
- UA list source — bundled default (5-10 strings) + config override.
- nodriver+Selenium coexistence in `discover_async` — research confirms additive change.

### Deferred Ideas (OUT OF SCOPE)
- Walmart PerimeterX/HUMAN deep bypass (flag risk only).
- Target Akamai deep bypass (flag risk only).
- nodriver swap for Amazon/BestBuy.
- Per-plugin proxy rotation.
- Mobile UA strings.
- Session cookie persistence across restarts.
- Plugin-level retry policy.
- Check-only override UI (env-var gate covers it).

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PLG-04 | Walmart plugin (availability + auto-buy, PerimeterX/HUMAN risk) | Q1, Q3, Q4 |
| PLG-05 | Target plugin (availability; checkout experimental, Akamai) | Q1, Q3, Q5 |
| PLG-06 | GameStop plugin (availability + auto-buy, CAPTCHA) | Q1, Q3, Q6 |
| PLG-07 | Square Enix plugin (availability + auto-buy) | Q1, Q3 |
| PLG-08 | NewEgg plugin (availability + auto-buy) | Q1, Q3 |
| ANTI-01 | Per-platform check interval with random jitter | Q9 |
| ANTI-02 | Rotating user-agent strings from configurable list | Q8 |
| ANTI-03 | Headless mode toggle per platform | Q7, Q11 |

## Summary

Phase 6 introduces a second driver family (nodriver, async-native CDP) alongside the existing Selenium plugins, plus three anti-detection knobs. The work is mechanically straightforward but has one sharp asymmetry: nodriver's `uc.start()` is a coroutine, while `RetailerPlugin.__init__` is sync. The cleanest way to bridge this is a new non-abstract `async def open(self)` hook on the ABC that nodriver plugins override and `discover_async` awaits after instantiation. This is an additive, non-breaking ABC change — `PLUGIN_API_VERSION` stays at 1.

**Actionable bullets:**

1. **Pin nodriver==0.50.3** in requirements.txt. [VERIFIED: pypi.org/project/nodriver/ via WebSearch 2026-05-15]. Requires Python >=3.9; we already require 3.11.
2. **Use `import nodriver as uc; browser = await uc.start(headless=False, browser_args=[...])`** — `uc.start` IS a coroutine; `browser.get(url)` returns a Tab; `browser.stop()` terminates. [CITED: ultrafunkamsterdam.github.io/nodriver/nodriver/quickstart.html]
3. **Use `uc.loop().run_until_complete(...)` is NOT what we do.** Author's docs warn `asyncio.run` "never worked for him," but ShopPyBot already runs inside `asyncio.run(main())` (main.py:319). The fix: do NOT call `uc.loop()`; instead call `await uc.start(...)` from inside an already-running event loop. Nodriver's loop helper is only needed for top-level scripts that don't already have an event loop. Tests confirm at integration time. [ASSUMED: based on doc reading; needs smoke verification before Wave 1 ends — flagged as Open Question O-1]
4. **Add `async def open(self) -> None` to `RetailerPlugin`** as a non-abstract no-op default. nodriver plugins override it to `await uc.start(...)` and assign `self.driver = browser`. Selenium plugins inherit the no-op (they build their driver in sync `__init__`). `discover_async` is amended to `await inst.open()` after each `_load_and_instantiate(...)` call, BEFORE the next stagger sleep. Driver init happens within the staggered window, not on top of it. Additive, non-breaking: `PLUGIN_API_VERSION` stays at 1.
5. **Extend `build_driver(driver_path, log_path, headless=False)`** — when `True`, append `--headless=new`. The legacy `--headless` flag is detectable by Akamai/PerimeterX; `--headless=new` (Chrome 109+) survives most casual fingerprinting. Phase 1 tests extended to assert the exact `--headless=new` substring.
6. **`PlatformConfig` gains three fields:** `min_delay: float = 3.0`, `max_delay: float = 8.0`, `headless: bool = False`. Add Pydantic `@model_validator(mode="after")` asserting `min_delay <= max_delay` and both > 0. PlatformConfig currently only has `enabled` and `credentials` — Walmart/Target/etc. have no credentials at v1 (the bot doesn't sign in to those for check-only). Either: (a) make `credentials` Optional, or (b) introduce a `PlatformCredentials | None` field. Recommend (a) — minimal schema change, every retailer can omit credentials if it doesn't need login. Phase 1 only used credentials for Amazon/BestBuy; nothing else depended on them being required.
7. **`AppConfig` gains optional `app.user_agents: list[str] | None = None`** with a bundled default list (defined in `driver.py`). `build_driver` picks `random.choice` per call. nodriver plugins read the same list (via `app_config.app.user_agents or driver.DEFAULT_USER_AGENTS`) and pass `--user-agent=<chosen>` via `browser_args`.
8. **Bundle ~6 desktop Chrome UAs covering Chrome 130-140 across Win10/Win11/macOS** in `driver.py` as `DEFAULT_USER_AGENTS: list[str]`. Single source of truth: when `app.user_agents` is None, both Selenium and nodriver use this same list. No mobile, no obsolete.
9. **Add `RetailerPlugin.next_delay(self) -> float`** non-abstract default returning `random.uniform(self.min_delay, self.max_delay)`. Plugins set `self.min_delay`/`self.max_delay` in `__init__` from `platform_config`. Default values from `PlatformConfig` guarantee they exist even if user config omits them.
10. **Orchestrator change in main.py poll_plugin:** replace `delay = app_config.app.delay` + `await asyncio.wait_for(stop_event.wait(), timeout=delay)` with `await asyncio.wait_for(stop_event.wait(), timeout=plugin.next_delay())`. Compute delay fresh each iteration (jitter is per-poll, not per-startup). `app.delay` becomes a fallback only if a plugin's `next_delay()` is somehow missing (it won't be — ABC provides a default).
11. **Amazon headless incompatibility:** Amazon's `_handle_mfa` and `login` use `input()` to gate the user reading the OTP from the Amazon screen. Headless Amazon = user can't see the OTP. AmazonPlugin must read `platform_config.headless` in `__init__` and raise `ValueError("AmazonPlugin does not support headless mode: OTP requires visual access to the browser")` when `headless and login_at_startup`. This is a clear startup error per the discover_async error-handling contract (logs WARNING and skips Amazon).
12. **Walmart auto_buy uses one-time risk warning:** `self._walmartRiskNoted = False` in `__init__`; on first `auto_buy` call after the risky-autobuy gate passes, log INFO ("Walmart auto_buy attempt: PerimeterX/HUMAN may block; see SECURITY.md") and set to True. Subsequent calls skip the log.
13. **GameStop CAPTCHA detection:** GameStop has historically used hCaptcha for checkout. Inside `detect_captcha`, look for the hCaptcha iframe selector (`iframe[src*="hcaptcha.com"]`) or container (`div[data-hcaptcha-widget-id]`). When found: trigger Phase 4 D-02 pattern — `await asyncio.to_thread(input, "GameStop CAPTCHA detected; solve in the browser and press Enter")`. The `input()` runs inside `asyncio.to_thread` so only the worker thread blocks; the event loop stays responsive. [ASSUMED: hCaptcha is the current vendor; verify selectors at implementation time]
14. **Plan layout (research recommendation):** 7 plans across 3 waves. Wave 0 = foundation (1 plan, RED-only test infrastructure + schema/ABC/factory changes); Wave 1 = the 5 plugins in parallel (5 plans, zero file overlap); Wave 2 = orchestrator integration + docs (1 plan). Detailed audit below.
15. **Test strategy for nodriver plugins:** All 5 plugin test files use `monkeypatch.setattr("nodriver.start", AsyncMock(return_value=fakeBrowser))` to avoid spawning Chrome. Unit tests for DOM-parse helpers feed fake HTML. ABC-contract smoke test instantiates and verifies attrs. SHOPBOT_ENABLE_RISKY_AUTOBUY gate tested with `monkeypatch.setenv` for both on and off. Live retailer integration is OUT OF SCOPE, documented in PLUGIN_DEV.md.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| URL → plugin routing | plugin_registry | — | Already locked Phase 2; no change |
| Selenium driver build | driver.py (factory) | — | Phase 1 contract; extended with headless/UA |
| nodriver driver build | individual plugin `open()` | — | nodriver is async-native; no shared factory |
| Per-platform poll interval | RetailerPlugin.next_delay() default | PlatformConfig.min/max_delay | Plugin owns "when to next poll"; config owns "what range" |
| UA rotation | driver.py for Selenium / plugin.open() for nodriver | AppConfig.app.user_agents | Same source list; two consumption points |
| Headless toggle | build_driver kwarg (Selenium) / uc.start kwarg (nodriver) | PlatformConfig.headless | Per-platform; not global |
| Risky autobuy gate | plugin.__init__ reads env once | — | env-at-init pattern (Phase 5 D-04 analog) |
| CAPTCHA pause | plugin.detect_captcha + asyncio.to_thread(input) | — | Phase 4 D-02 pattern |
| Plugin lifecycle (open) | RetailerPlugin.open() default no-op | discover_async awaits it | New ABC method, additive |

## Standard Stack

### Core (new)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| nodriver | 0.50.3 | Async-native, CDP-direct browser automation | Official successor to undetected-chromedriver; far better PerimeterX/Akamai evasion than Selenium [VERIFIED: pypi.org/project/nodriver/] |

### Already pinned (no change)
selenium 4.43.0, pydantic 2.13.3, pydantic-settings[yaml] 2.14.0, pytest 8.3.4, pytest-asyncio 1.3.0 — unchanged.

### Version verification

Latest stable nodriver: 0.50.3, released 2026-05-13 [VERIFIED: WebSearch on pypi.org/project/nodriver/ via libraries.io snapshot]. Pin exact version per INFRA-01.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| nodriver | undetected-chromedriver | Deprecated; same author moved to nodriver. Selenium-based, sync, worse against modern fingerprinting |
| nodriver | playwright + stealth plugin | Heavier install; sync API leaks into our async orchestrator; stealth plugins are cat-and-mouse |
| nodriver | zendriver | Active fork of nodriver but smaller community, fewer Stack Overflow answers [CITED: pypi.org/project/zendriver/] |

**Installation:** add `nodriver==0.50.3` to requirements.txt (single line).

## Architecture Patterns

### System Architecture Diagram

```
   config.yml (PlatformConfig.min_delay/max_delay/headless + AppConfig.app.user_agents)
                          │
                          ▼
                 ┌────────────────┐
                 │   AppConfig    │  (Pydantic)
                 └────────┬───────┘
                          │ per-platform slice
                          ▼
           ┌──────────────────────────────────┐
           │ discover_async(plugins_dir, ...) │
           │  for each *.py:                  │
           │    sleep(1.5) if not first  ◄────┼─── stagger straddles BOTH
           │    inst = to_thread(_load...)    │    Selenium build_driver
           │    await inst.open()        ◄────┼─── AND nodriver uc.start()
           └──────────────────────────────────┘
                          │
                          ▼
                ┌──────────────────────┐
                │ RetailerPlugin (ABC) │
                │  abstract:           │
                │    check_availability│
                │    auto_buy          │
                │  default no-op:      │
                │    login             │
                │    detect_captcha    │
                │    open       (NEW)  │
                │    next_delay (NEW)  │
                │    shutdown          │
                └─────────┬────────────┘
                          │
            ┌─────────────┼────────────────────┐
            ▼             ▼                    ▼
       Selenium      nodriver               (mix)
       Amazon        Walmart    Target     GameStop   SquareEnix   NewEgg
       BestBuy       (build via   (build via uc.start, browser_args=[--user-agent=..., --headless=new?])
                      build_driver(headless, user_agent))
                          │
                          ▼  poll_plugin in main.py:
                          ▼   await asyncio.wait_for(
                                stop_event.wait(),
                                timeout=plugin.next_delay()   # was app.delay
                              )

  Env: SHOPBOT_ENABLE_RISKY_AUTOBUY  →  plugin.__init__  →  self._riskyAutoBuyEnabled
                                                              │
                                                              ▼
                                                 auto_buy: early-return if False
```

### Recommended Project Structure
```
plugins/
├── shopbot_plugin_amazon.py        # Selenium (existing)
├── shopbot_plugin_bestbuy.py       # Selenium (existing)
├── shopbot_plugin_walmart.py       # nodriver (PLG-04, risky autobuy + PerimeterX risk note)
├── shopbot_plugin_target.py        # nodriver (PLG-05, default headless=False)
├── shopbot_plugin_gamestop.py      # nodriver (PLG-06, hCaptcha pause)
├── shopbot_plugin_squareenix.py    # nodriver (PLG-07)
├── shopbot_plugin_newegg.py        # nodriver (PLG-08)
├── example_plugin.py               # unchanged; Selenium template
└── PLUGIN_DEV.md                   # extended with nodriver section

tests/
├── test_plugins_walmart.py
├── test_plugins_target.py
├── test_plugins_gamestop.py
├── test_plugins_squareenix.py
├── test_plugins_newegg.py
├── test_driver_setup.py            # extended for headless + UA rotation
├── test_plugin_base.py             # extended for open() + next_delay() defaults
├── test_config_schema.py           # extended for new PlatformConfig fields
├── test_registry_stagger.py        # extended for open() ordering
└── test_orchestrator.py            # extended for plugin.next_delay() call
```

### Pattern 1: nodriver plugin skeleton
**What:** new RetailerPlugin subclass that builds its browser asynchronously inside `open()`.
**When to use:** any new retailer that benefits from CDP-direct (PerimeterX, Akamai, HUMAN).
**Example:**
```python
# Source: plugin_base.py + nodriver quickstart [CITED: ultrafunkamsterdam.github.io/nodriver/nodriver/quickstart.html]
import os
import random
import nodriver as uc

from driver import DEFAULT_USER_AGENTS
from logger import writeLog
from plugin_base import RetailerPlugin


class WalmartPlugin(RetailerPlugin):
    domain_pattern: list[str] = ["walmart.com"]
    login_at_startup: bool = False
    name: str = "walmart"

    def __init__(self, platform_config, *, cvv=None, driver_path=None):
        super().__init__(platform_config)
        self._riskyAutoBuyEnabled = (
            os.environ.get("SHOPBOT_ENABLE_RISKY_AUTOBUY", "").strip().lower() == "true"
        )
        self._walmartRiskNoted = False
        self.min_delay = platform_config.min_delay
        self.max_delay = platform_config.max_delay
        self._headless = platform_config.headless
        self._userAgents = (
            getattr(getattr(platform_config, "_app", None), "user_agents", None)
            or DEFAULT_USER_AGENTS
        )
        self.driver = None  # opened in async open()

    async def open(self) -> None:
        ua = random.choice(self._userAgents)
        self.driver = await uc.start(
            headless=self._headless,
            browser_args=[f"--user-agent={ua}", "--disable-blink-features=AutomationControlled"],
        )

    async def check_availability(self, url: str) -> bool:
        tab = await self.driver.get(url)
        add_btn = await tab.select('button[data-automation-id="atc-button"]')
        return add_btn is not None

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
        # ... actual purchase flow
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

**Note on `check_availability` async-ness:** existing Selenium plugins have a SYNC `check_availability`. The orchestrator already invokes them via `asyncio.to_thread(plugin.check_availability, link)` (main.py:165). For nodriver plugins, `check_availability` MUST be a coroutine — calling `asyncio.to_thread` on a coroutine does NOT await it. The orchestrator needs a small `inspect.iscoroutinefunction(plugin.check_availability)` branch to either `await plugin.check_availability(link)` directly or `await asyncio.to_thread(plugin.check_availability, link)`. Same for `auto_buy`. This is the only orchestrator change beyond `next_delay()`. Tests added in Plan 7 (Wave 2).

### Pattern 2: discover_async with open() hook
**What:** after instantiation, await the optional `open()` method to let nodriver plugins finish async driver construction within the stagger window.
**Example:**
```python
# Source: plugin_registry.py (Phase 4 D-04 amended)
async def discover_async(plugins_dir, *, app_config, cvvs, stagger_seconds=DEFAULT_STAGGER_SECONDS):
    instances: list[RetailerPlugin] = []
    paths = list(_iter_plugin_paths(plugins_dir))
    for index, path in enumerate(paths):
        if index > 0:
            await asyncio.sleep(stagger_seconds)
        inst = await asyncio.to_thread(_load_and_instantiate, path, app_config, cvvs)
        if inst is None:
            continue
        try:
            await inst.open()       # NEW: default no-op for Selenium, real driver for nodriver
        except Exception as e:
            writeLog(f"{type(inst).__name__}.open() raised: {e}; skipping", "WARNING")
            continue                # do NOT add to registry if open failed
        instances.append(inst)
    return instances
```

### Anti-Patterns to Avoid

- **NEVER call `uc.start()` from inside `__init__`** via `asyncio.run(...)`. `__init__` runs inside `asyncio.to_thread(_load_and_instantiate, ...)` which is itself a worker thread of an already-running asyncio.run. Nested `asyncio.run` is undefined behavior and will likely raise `RuntimeError: asyncio.run() cannot be called from a running event loop` once the worker thread inherits any loop reference. Use the `open()` hook instead.
- **NEVER mark `check_availability` sync on a nodriver plugin.** Calling `await self.driver.get(...)` from a sync method fails immediately. Sync vs async per plugin is fine, but the orchestrator MUST branch on `inspect.iscoroutinefunction` (Pattern 1 note above).
- **NEVER share a single `nodriver.Browser` across plugins.** Same isolation rationale as PLG-03 (per-plugin driver). Each plugin's `open()` builds its own.
- **NEVER read `SHOPBOT_ENABLE_RISKY_AUTOBUY` inside `auto_buy`.** Env-at-init only. Phase 5 D-04 locked this pattern for SMS; mirror it. Tests assert env reads happen in `__init__`.
- **NEVER pass `--headless` alone to Chrome.** Always `--headless=new`. The legacy flag is fingerprinted; the new flag survives more checks.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Anti-detection browser launcher | Custom Chrome options stew | nodriver | CDP-direct + maintained anti-detection patches |
| Async-to-sync bridging | Manual loop.run_until_complete | `asyncio.to_thread` (already in orchestrator) | Standard, plays nice with TaskGroup |
| Random user-agent picker | Custom rotation cache | `random.choice(list)` per `build_driver`/`uc.start` call | Stateless; matches CONTEXT pitfall 8 |
| CAPTCHA solver | Bypass code or vision model | `await asyncio.to_thread(input, ...)` pause | Phase 4 D-02 locked the pattern; same here |
| Per-platform jitter | Custom timing loop | `random.uniform(min, max)` per poll | Single line; covered by Pydantic min<=max validator |

**Key insight:** Phase 6 is mostly "wire existing patterns together" plus one new library. The only novel pattern is the `open()` lifecycle hook to bridge sync `__init__` with async `uc.start`.

## Runtime State Inventory

> Phase 6 is NOT a rename/refactor phase. It adds new files and extends three existing files (`plugin_base.py`, `plugin_registry.py`, `driver.py`, `config_schema.py`, `main.py`, `plugins/PLUGIN_DEV.md`). No runtime data migrations required.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — Phase 6 adds new plugins; SQLite schema unchanged (items table reused) | None |
| Live service config | None — no external services have ShopPyBot-side identifiers | None |
| OS-registered state | None — no Task Scheduler / pm2 / systemd entries | None |
| Secrets/env vars | NEW env var `SHOPBOT_ENABLE_RISKY_AUTOBUY=true` (opt-in only; absent = check-only) | Document in `SECURITY.md` and `CONTRIBUTING.md` (or PLUGIN_DEV.md) |
| Build artifacts | None — pip install of nodriver pulls Chrome binary on first run; no stale artifacts | None |

## Common Pitfalls

These map 1:1 to CONTEXT.md pitfalls 1-10 plus three new ones surfaced by research. The planner SHOULD encode all 13 as `must_haves.truths`.

1. **Mixed-driver registry has NO ABC type constraint on `self.driver`.** nodriver plugins assign `nodriver.Browser`; Selenium plugins assign `selenium.webdriver.Chrome`. Tests verify nodriver plugins import cleanly even when selenium import is missing, and vice versa. (CONTEXT pitfall 1)
2. **`SHOPBOT_ENABLE_RISKY_AUTOBUY` read in `__init__`, NOT in `auto_buy`.** Stored on `self._riskyAutoBuyEnabled`. Tests assert env reads happen at instantiation, not method call. (CONTEXT pitfall 2)
3. **`build_driver(headless=True)` emits exactly `--headless=new`,** NOT `--headless` alone. Test asserts the exact flag string. (CONTEXT pitfall 3)
4. **`PlatformConfig.min_delay <= max_delay`, both > 0.** Pydantic `@model_validator(mode="after")` enforces. Tests cover violation cases. (CONTEXT pitfall 4)
5. **`uc.start()` is async and MUST be awaited from a running event loop.** Use the new `RetailerPlugin.open()` hook called from `discover_async` AFTER instantiation, BEFORE the next stagger sleep. Tests assert `open()` is awaited exactly once per nodriver plugin instance. (CONTEXT pitfall 5 — clarified by research)
6. **Walmart `auto_buy` logs the PerimeterX risk INFO note exactly once per plugin instance,** controlled by `self._walmartRiskNoted` boolean flag. Tests assert one log on first call, zero on subsequent. (CONTEXT pitfall 6)
7. **GameStop CAPTCHA `input()` blocks only the worker thread,** because the plugin method is invoked via `asyncio.to_thread` from the orchestrator. The event loop continues to service the other 6 plugins. Tests verify this with a fake input. (CONTEXT pitfall 7)
8. **UA rotation: `random.choice(user_agents)` on EACH `build_driver` call and EACH nodriver `open()` call,** not cached at module load. Tests instantiate two plugins back-to-back, force different `random.choice` returns, and assert the two recorded UAs differ. (CONTEXT pitfall 8)
9. **Amazon plugin raises ValueError when `platform_config.headless and login_at_startup`** during `__init__`. Clear error: "AmazonPlugin does not support headless mode: OTP requires visual access." `discover_async` catches and logs WARNING per existing D-04 Phase A. Tests assert the exact ValueError. (CONTEXT pitfall 9)
10. **NewEgg / SquareEnix / GameStop integrate Phase 5 notifications via the orchestrator's queue puts,** never via plugin-level notifier calls. Tests assert no `from notifier_base` or `from utils import play_*` imports inside the 5 new plugin files. (CONTEXT pitfall 10)
11. **NEW: nodriver `check_availability` and `auto_buy` are coroutines, not sync.** Orchestrator branches on `inspect.iscoroutinefunction(plugin.check_availability)` to either `await plugin.check_availability(link)` or `await asyncio.to_thread(plugin.check_availability, link)`. Test covers both branches. The branch is internal to `_poll_once` and `_attempt_purchase`.
12. **NEW: `RetailerPlugin.open()` failures during `discover_async` MUST NOT add the plugin to the registry.** A nodriver plugin whose `uc.start()` raises is functionally dead. Log WARNING and skip (same D-04 Phase A semantics as instantiation failure). Test asserts a broken `open()` is logged + skipped + registry doesn't include it.
13. **NEW: `RetailerPlugin.next_delay()` default uses self.min_delay / self.max_delay,** which plugins SET FROM `platform_config` in `__init__`. If a plugin forgets to set them (a contributor bug), `next_delay()` raises `AttributeError`. Recommend ABC has `min_delay: float = 3.0` and `max_delay: float = 8.0` as class attrs so the default sticks even if a subclass forgets. Tests assert a minimal plugin subclass that doesn't touch min_delay/max_delay still has working `next_delay()`.

## Per-Retailer DOM and Risk Notes

| Retailer | Stock signal (planning hint) | Anti-detection layer | Headless feasible? |
|----------|------------------------------|----------------------|---------------------|
| Walmart  | `button[data-automation-id="atc-button"]` or text "Add to cart" present | PerimeterX / HUMAN Security | Risky; default False |
| Target   | `button[data-test="orderPickupButton"]` or "Add to cart" enabled | Akamai Bot Manager | NO — default False, warn if True |
| GameStop | `button.add-to-cart:not(:disabled)` or "Add to cart" | hCaptcha at checkout (likely) | Risky; default False |
| Square Enix | `button.product-detail-add-to-cart` or text "ADD TO CART" | Cloudflare (light) | Probably OK; default False but headless can be opt-in |
| NewEgg | `button#btnAddCart` or `.product-buy button` enabled | Light bot detection | Probably OK; default False |

[ASSUMED: all five selector hints — retailers reflow their pages frequently. Plan-time verification REQUIRED before encoding into plugin source. Document this expectation in PLUGIN_DEV.md.]

`domain_pattern` recommendations:
- Walmart: `["walmart.com"]`
- Target: `["target.com"]`
- GameStop: `["gamestop.com"]`
- Square Enix: `["square-enix.com", "store.eu.square-enix-games.com"]` (planner verifies the EU host; could just be `["square-enix-games.com", "square-enix.com"]`)
- NewEgg: `["newegg.com"]`

## Detailed Research Q&A

### Q1: nodriver API + async lifecycle

`uc.start(headless: bool = False, user_data_dir: str = None, browser_executable_path: str = None, browser_args: list[str] = None, lang: str = None, sandbox: bool = True)` — IS a coroutine; must be awaited. Returns a `Browser` object. [CITED: ultrafunkamsterdam.github.io/nodriver/nodriver/quickstart.html]

Navigation: `tab = await browser.get(url, new_tab=False, new_window=False)` returns a `Tab`. Selection: `await tab.select(css_selector)` returns a single element or None; `await tab.select_all(...)` returns a list. Text-based: `await tab.find(text, best_match=True)`. CDP-direct: no By/WebDriverWait pattern; tab methods are direct CDP queries.

Shutdown: `await browser.stop()` per nodriver docs. (Note: nodriver also exposes `browser.stop()` as a sync property in some examples; treat as `await browser.stop()` — verify at integration time, fallback to non-await if needed.)

**Critical:** the nodriver docs say "since asyncio.run never worked (for me)" and recommend `uc.loop().run_until_complete(main())`. This applies to TOP-LEVEL scripts. ShopPyBot already runs inside `asyncio.run(main())` in main.py:319 — we MUST NOT call `uc.loop()` (it would try to install a new policy). Just `await uc.start(...)` from inside our already-running loop. This is the standard pattern when an async library is consumed by a larger asyncio app. If integration testing reveals issues (e.g., nodriver tries to install its own loop policy), the fallback is to wrap `uc.start` in a thread executor — but that defeats the async-native advantage. Flagged as Open Question O-1; smoke-test in Wave 1 first plugin.

**Recommended pattern (final):** RetailerPlugin gains `async def open(self) -> None` defaulting to no-op. nodriver plugins override. `discover_async` calls `await inst.open()` after instantiation. ALTERNATIVE — `asyncio.run(self._async_init())` inside `__init__` — is the anti-pattern and rejected.

### Q2: nodriver+Selenium coexistence in `discover_async`

The 1.5s stagger from Phase 4 ASYNC-02 covers chromedriver TCP-bind windows. nodriver also spawns Chrome via CDP and benefits from the same stagger. The current `discover_async` does instantiation under `asyncio.to_thread` (because Selenium `__init__` is blocking) — sleep is BEFORE each path past the first.

The amendment: after `_load_and_instantiate`, call `await inst.open()`. The stagger now straddles the entire driver-construction window for BOTH Selenium plugins (sync, inside `_load_and_instantiate`) and nodriver plugins (async, inside `open()`). Test: assert `open()` called between instantiation and the next stagger sleep.

ABC change is ADDITIVE: new non-abstract method with default no-op. `PLUGIN_API_VERSION` stays at 1. The PLUGIN_DEV.md "what bumps the version" rules explicitly allow this ("Cosmetic changes (docstrings, default no-op behavior) do not bump the version" — and adding a non-abstract method with a no-op default is functionally equivalent).

### Q3: Per-retailer DOM patterns

Summarized in the table above. Each plugin's plan should NOT lock the exact selector in the plan text — the implementation task verifies and codes it. Plans encode the contract (must return bool, must handle the unavailable case, must log via writeLog) not the selector. This keeps plans resilient to retailer page reflows.

### Q4: PerimeterX/HUMAN detection on Walmart

PerimeterX combines TLS fingerprint, mouse-movement heuristics, WebGL/Canvas fingerprint, and request rhythm. nodriver evades many of these via CDP-direct (no Selenium WebDriver protocol leak, no automation flags) but NOT TLS fingerprint (browser-level, not driver-level).

Realistic expectation: nodriver passes the initial page render check on Walmart. Multi-step auto-buy flows (add-to-cart → checkout → place-order) cross more detection surfaces; success is probabilistic, not guaranteed. Phase 6 ships full auto-buy gated behind the env var per D-02 + the one-time INFO note per pitfall 6. Deep mitigation is deferred (CONTEXT defer item). [ASSUMED: based on training knowledge + nodriver documentation claims; needs real-world validation by users]

### Q5: Akamai bot detection on Target

REQUIREMENTS.md PLG-05 calls out "Akamai blocks headless Selenium consistently." nodriver in non-headless mode: high chance Target check works. nodriver in headless mode: Akamai detects headless via multiple signals (window dimensions, plugin presence, hardware concurrency). Recommendation: Target plugin's PlatformConfig.headless default stays False; the plugin's `__init__` logs a WARNING if `headless=True` is set ("Target plugin: headless mode often blocked by Akamai; expect failures"). Auto-buy explicitly marked experimental in plugin docstring per PLG-05 wording.

### Q6: GameStop CAPTCHA

hCaptcha is the most likely service (industry trend 2024-2026; harder to bypass than reCAPTCHA v2). Detection selector candidates: `iframe[src*="hcaptcha.com"]`, `div[data-hcaptcha-widget-id]`, or fallback text search via `await tab.find("Verify you are human", best_match=True)`.

On detection: `await asyncio.to_thread(input, "GameStop CAPTCHA detected; solve in the browser and press Enter to continue")`. The `input()` reads from the controlling terminal's stdin; works whether the bot was launched in foreground or via a TTY-attached background. Headless mode invalidates this (user can't see the puzzle). Recommend GameStop plugin warns if `headless=True` AND auto-buy enabled.

### Q7: `--headless=new` vs deprecated `--headless`

Chrome 109 (released Jan 2023) introduced `--headless=new` as the modern headless mode. The legacy `--headless` is detectable because it presents a different rendering pipeline (no GPU, no plugins). `--headless=new` uses the same renderer as headed Chrome with the window hidden — far harder to detect.

Plan asserts `build_driver(headless=True)` produces options containing exactly `"--headless=new"`. Test grep: `assert "--headless=new" in [arg for arg in opts.arguments]`. Reject any test that asserts only the substring `"--headless"` (it would pass for the legacy flag too).

### Q8: UA rotation

Bundled default list in `driver.py`:
```python
DEFAULT_USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
]
```
[ASSUMED: real Chrome 138/140 UA strings — verified at plan-time against caniuse/whatismybrowser]

`AppConfig.app.user_agents: list[str] | None = None` (Pydantic Optional list). When None, build_driver and nodriver plugins fall back to `DEFAULT_USER_AGENTS`. `random.choice(...)` per call, NOT cached. The existing `driver.py:CHROME_UA` constant remains for backward-compat ref but `build_driver` switches to using `random.choice(get_user_agents(app_config))`.

Plumbing question: `build_driver` currently takes only `driver_path` and `log_path`. To get the UA list it needs `app_config` access. Two options: (a) plumb `app_config` through to `build_driver` (breaks the existing call-site signature; needs every plugin updated); (b) accept `user_agents: list[str] | None = None` kwarg defaulting to `DEFAULT_USER_AGENTS`. Recommend (b) — minimal blast radius, default-friendly. Plugins that want config rotation pass it via `build_driver(driver_path, user_agents=self.platform_config._app.user_agents)` or similar. **Open Question O-2: where does the plugin's `__init__` get app-level config?** It currently only receives `platform_config` (one PlatformConfig slice). The plumbing already exists via `cvv` kwarg in `_instantiate` — recommend extending `_instantiate` to also pass `app_config` to nodriver plugins (or, simpler, just `user_agents: list[str] | None`). Planner picks.

### Q9: Per-platform jitter

`RetailerPlugin` gains class-level defaults `min_delay: float = 3.0` and `max_delay: float = 8.0` (pitfall 13 — defensive default in case plugin forgets to set instance attrs). Plugin's `__init__` overrides via `self.min_delay = platform_config.min_delay; self.max_delay = platform_config.max_delay`. New non-abstract method:

```python
def next_delay(self) -> float:
    return random.uniform(self.min_delay, self.max_delay)
```

`main.py:poll_plugin` change:
```python
# Before:
delay = app_config.app.delay
while not stop_event.is_set():
    ...
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=delay)
    except asyncio.TimeoutError:
        pass

# After:
while not stop_event.is_set():
    ...
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=plugin.next_delay())
    except asyncio.TimeoutError:
        pass
```

`app.delay` becomes a default-only safety net (ABC defaults from min/max take over). Optionally deprecate `app.delay` in a future phase; for v1 it stays as the fallback so legacy configs still work.

Pydantic validator on PlatformConfig:
```python
@model_validator(mode="after")
def validate_delay_range(self) -> "PlatformConfig":
    if self.min_delay <= 0 or self.max_delay <= 0:
        raise ValueError("min_delay and max_delay must be > 0")
    if self.min_delay > self.max_delay:
        raise ValueError(f"min_delay ({self.min_delay}) must be <= max_delay ({self.max_delay})")
    return self
```

### Q10: Test strategy

Each new plugin gets a test file with 4-6 tests:
1. **Module import.** Imports cleanly with nodriver/selenium stubs.
2. **ABC contract.** Subclass of RetailerPlugin; non-empty `domain_pattern`; defines required methods.
3. **Routing.** Parametrized URLs against `route_url`; in-domain match, off-domain reject.
4. **Risky autobuy gate (env-on).** Set env, instantiate, assert `self._riskyAutoBuyEnabled is True`, call `auto_buy`, assert it doesn't early-return.
5. **Risky autobuy gate (env-off).** Unset env, instantiate, call `auto_buy`, assert returns False and logs WARNING.
6. **(Walmart only)** One-time risk note: call auto_buy with env on twice, assert INFO log appears once.
7. **(GameStop only)** CAPTCHA pause: monkeypatch `input` to return immediately; assert flow continues. Confirms the to_thread bridge works.

Driver mock: `monkeypatch.setattr("nodriver.start", AsyncMock(return_value=fakeBrowser))` where `fakeBrowser` is a `unittest.mock.AsyncMock` shaped object with `.get`, `.stop`, etc. Live retailer integration tests OUT OF SCOPE — note in PLUGIN_DEV.md.

### Q11: Amazon headless incompatibility

```python
# In AmazonPlugin.__init__ (Plan 7 wires this in):
if platform_config.headless and self.login_at_startup:
    raise ValueError(
        "AmazonPlugin does not support headless mode: OTP requires visual access to the browser. "
        "Set platforms.amazon.headless: false (or omit) to use Amazon."
    )
```

Test: `pytest.raises(ValueError, match="headless mode")` when constructing with `PlatformConfig(headless=True)`. The discover_async machinery already catches `__init__` exceptions and logs WARNING + skips (Phase 2 D-04 Phase A) — so a user who configures `platforms.amazon.headless: true` sees a clear log line and Amazon is skipped from the registry. `verify_coverage` then fails loudly if any item URL was Amazon-bound.

### Q12: Plan layout (atomic, file-overlap audited)

**Wave 0 (sequential, foundation) — 1 plan**

**Plan 06-01: foundation-and-red-skeletons**
Scope: pin nodriver, add PlatformConfig new fields + Pydantic validator, extend build_driver with headless + user_agents kwargs, add RetailerPlugin.open() and next_delay() defaults, add DEFAULT_USER_AGENTS to driver.py, extend discover_async to await open() with skip-on-failure, write RED tests covering all of the above (no plugin tests yet).

Files touched:
- `requirements.txt`
- `plugin_base.py`
- `plugin_registry.py`
- `driver.py`
- `config_schema.py`
- `tests/test_plugin_base.py` (extended)
- `tests/test_registry_stagger.py` (extended)
- `tests/test_driver_setup.py` (extended)
- `tests/test_config_schema.py` (extended)
- NEW: `tests/test_plugins_walmart.py` etc. (RED skeletons only — import-error tests)

Blocks Wave 1.

**Wave 1 (parallel, 5 plugins) — 5 plans, zero file overlap**

Each plan creates exactly ONE new plugin file and ONE new test file. Zero edits to shared files. Editing main.py, plugin_registry.py, plugin_base.py, driver.py, config_schema.py is FORBIDDEN inside Wave 1 plans — those landed in Wave 0.

| Plan | New file | New test | Touches anything else? |
|------|----------|----------|------------------------|
| 06-02 walmart-plugin | `plugins/shopbot_plugin_walmart.py` | `tests/test_plugins_walmart.py` (RED → GREEN) | No |
| 06-03 target-plugin | `plugins/shopbot_plugin_target.py` | `tests/test_plugins_target.py` | No |
| 06-04 gamestop-plugin | `plugins/shopbot_plugin_gamestop.py` | `tests/test_plugins_gamestop.py` | No |
| 06-05 squareenix-plugin | `plugins/shopbot_plugin_squareenix.py` | `tests/test_plugins_squareenix.py` | No |
| 06-06 newegg-plugin | `plugins/shopbot_plugin_newegg.py` | `tests/test_plugins_newegg.py` | No |

Overlap audit: **PASS.** Each plugin file is unique; each test file is unique; no Wave 1 plan touches main.py, plugin_base.py, plugin_registry.py, driver.py, or config_schema.py. The Wave 0 RED skeletons in `tests/test_plugins_<retailer>.py` get OVERWRITTEN by each Wave 1 plan owning that file — declare ownership in the Wave 0 plan's footer.

**Wave 2 (sequential, integration) — 1 plan**

**Plan 06-07: orchestrator-integration-and-docs**
- `main.py`: switch `poll_plugin` from `app.delay` to `plugin.next_delay()`; add `inspect.iscoroutinefunction` branches for async `check_availability` and `auto_buy`.
- `plugins/shopbot_plugin_amazon.py`: add headless+login_at_startup ValueError guard.
- `plugins/PLUGIN_DEV.md`: add "Selenium vs nodriver" section, link to nodriver docs, document `SHOPBOT_ENABLE_RISKY_AUTOBUY`, document live-integration-tests-are-out-of-scope policy.
- `tests/test_orchestrator.py`: extend with `next_delay()` call assertion + async-coroutine-branch tests.
- `tests/test_plugins_amazon.py`: add the headless guard test.

Total: 7 plans, 3 waves, all Wave 1 plans run in parallel with zero overlap.

### Q13: nodriver lifecycle in discover_async

Confirmed above (Q2). Additive ABC change, `PLUGIN_API_VERSION` stays at 1. Tests for the lifecycle ordering live in `tests/test_registry_stagger.py` (extended).

## Project Constraints (from CLAUDE.md)

- Functions under 30 lines, files under 300 lines, nesting depth max 3 — all current shop_py_bot files comply; new plugin files SHOULD comply (each plugin file expected to be ~150 lines).
- Variable/function naming: camelCase (e.g., `riskyAutoBuyEnabled`, `walmartRiskNoted`, `userAgents`). Class names: PascalCase.
- No emojis in any output. No em dashes. No horizontal rules (`---`, `***`, `___`).
- All shell commands prefixed with `rtk`.
- Approval gates: commit/push, destructive ops — orchestrator handles via commit_docs gate.
- Validate all external input server-side: config validated via Pydantic at startup.
- No silent exception swallowing: log via writeLog + return False (already the plugin convention).
- "Type | File | Change Summary" table + proposed commit message + explicit yes/no awaited BEFORE any git commit/push. (researcher does not commit; orchestrator handles via gsd-sdk commit.)

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3.4 + pytest-asyncio 1.3.0 |
| Config file | `pytest.ini` (assumed present from Phase 1; verify at plan time) |
| Quick run command | `pytest tests/test_plugins_<retailer>.py -x -q` |
| Full suite command | `pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| PLG-04 | Walmart plugin subclasses ABC, autobuy gated | unit + smoke | `pytest tests/test_plugins_walmart.py -x` | ❌ Wave 0 RED |
| PLG-05 | Target plugin subclasses ABC, headless warn | unit + smoke | `pytest tests/test_plugins_target.py -x` | ❌ Wave 0 RED |
| PLG-06 | GameStop plugin + CAPTCHA pause via to_thread | unit + smoke + integration mock | `pytest tests/test_plugins_gamestop.py -x` | ❌ Wave 0 RED |
| PLG-07 | Square Enix plugin subclasses ABC, autobuy gated | unit + smoke | `pytest tests/test_plugins_squareenix.py -x` | ❌ Wave 0 RED |
| PLG-08 | NewEgg plugin subclasses ABC, autobuy gated | unit + smoke | `pytest tests/test_plugins_newegg.py -x` | ❌ Wave 0 RED |
| ANTI-01 | next_delay returns uniform(min,max); orchestrator uses it | unit + integration | `pytest tests/test_plugin_base.py tests/test_orchestrator.py -x` | ✅ extend |
| ANTI-02 | random.choice per call; user_agents config wired | unit | `pytest tests/test_driver_setup.py::test_userAgentRotation -x` | ✅ extend |
| ANTI-03 | --headless=new flag emitted; PlatformConfig.headless wired | unit | `pytest tests/test_driver_setup.py::test_headlessNewFlag -x` | ✅ extend |

### Sampling Rate
- **Per task commit:** `pytest tests/<single-file>.py -x -q`
- **Per wave merge:** `pytest tests/test_plugins_*.py tests/test_plugin_base.py tests/test_registry_stagger.py tests/test_driver_setup.py tests/test_config_schema.py -q`
- **Phase gate:** Full `pytest -q` green before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_plugins_walmart.py` — RED skeleton covering PLG-04
- [ ] `tests/test_plugins_target.py` — RED skeleton covering PLG-05
- [ ] `tests/test_plugins_gamestop.py` — RED skeleton covering PLG-06
- [ ] `tests/test_plugins_squareenix.py` — RED skeleton covering PLG-07
- [ ] `tests/test_plugins_newegg.py` — RED skeleton covering PLG-08
- [ ] Shared fixture for `fakeBrowser` (nodriver AsyncMock) in `tests/conftest.py` if not already present
- [ ] Existing tests extended (test_plugin_base, test_registry_stagger, test_driver_setup, test_config_schema, test_orchestrator) — Wave 0 adds RED assertions; Wave 1/2 turns them GREEN

## Security Domain

`security_enforcement` is implicit (no .planning/config.json override observed). ShopPyBot's threat model is dominated by retailer-side bot detection rather than classic ASVS web-app threats; nevertheless, applicable ASVS categories:

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (Amazon/BestBuy + 5 new retailers) | Credentials from env vars (SEC-01); no plaintext in config.yml |
| V3 Session Management | partial | Per-plugin driver isolation (PLG-03) prevents session leak |
| V4 Access Control | no | Local-only bot, no multi-tenant; out of scope |
| V5 Input Validation | yes | Pydantic strict (`extra=forbid`) validates config.yml |
| V6 Cryptography | no (no crypto operations performed locally) | N/A — TLS handled by browser; never roll own |
| V7 Error Handling | yes | writeLog convention; swallow + log + return sensible default |
| V14 Configuration | yes | env-at-init for risky ops; opt-in two-lock for SMS (Phase 5), opt-in env for autobuy (Phase 6) |

### Known Threat Patterns for retail-automation stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Account ban from accidental purchase | Repudiation (user can't undo) | `SHOPBOT_ENABLE_RISKY_AUTOBUY` env gate + WARNING log |
| Credential exposure via committed config.yml | Information Disclosure | Phase 1 SEC-01: env vars only; config.yml is gitignored |
| Auto-buy on wrong item from data corruption | Tampering | Items keyed by URL with unique constraint; SQLite WAL mode |
| Headless detection → blocked → bot stuck | Denial of Service | Amazon ValueError guard; other plugins log WARNING |
| CAPTCHA blocks all plugins forever | Denial of Service | Per-plugin CAPTCHA pause via `asyncio.to_thread(input)`; other plugins keep running |
| PerimeterX/Akamai signal sharing | Information Disclosure (about bot) | Per-plugin browser isolation; UA rotation; nodriver CDP-direct |
| TOS violation lawsuit | Legal | SECURITY.md disclaimer (Phase 3 / SEC-06) |

## Open Questions

1. **O-1: nodriver in an already-running asyncio.run loop.** nodriver docs recommend `uc.loop().run_until_complete(...)` for top-level. ShopPyBot is already inside `asyncio.run(main())`. Recommendation: just `await uc.start(...)` from inside the existing loop and skip `uc.loop()` entirely. Smoke-test in Wave 1's first plugin (Walmart). If issues surface, fallback is `await asyncio.to_thread(...)` wrapping a sync helper that uses `uc.loop()` — but that defeats async-native. PLANNER: encode in Walmart plan's plan-checker as a "first integration smoke" verification step. [ASSUMED resolution; needs Wave 1 confirmation]

2. **O-2: Plugin __init__ signature for app-level config access.** Current signature: `__init__(self, platform_config, *, cvv=None, driver_path=None)`. To rotate UAs from `app.user_agents`, nodriver plugins need access to the app-level user agent list. Two options:
   - (a) Extend `_instantiate` in plugin_registry.py to pass `user_agents` kwarg directly (small surgical addition).
   - (b) Pass entire `app_config` to plugin `__init__` (bigger surface, more flexibility).
   
   Recommend (a) — least blast radius. Plan 06-01 owns this signature change.

3. **O-3: nodriver `Browser.stop()` — coroutine or sync?** Docs are inconsistent. Confirm at integration time; the AmazonPlugin pattern of `getattr(driver, "stop", None)` with try/await/sync fallback handles both cases. Encoded in shutdown override.

4. **O-4: Where does Walmart's PerimeterX risk note live?** SECURITY.md (Phase 3) currently notes the risk; the runtime INFO log refers users to SECURITY.md. If SECURITY.md was not actually created in Phase 3 (verify Phase 3 SUMMARY), the planner should add a stub or change the log destination to PLUGIN_DEV.md.

5. **O-5: Selectors per retailer.** All 5 selector hints in this research are ASSUMED. Plan-time must include a 5-minute manual verification step (load the retailer's PDP for a known in-stock item and a known OOS item, eyeball the differentiating selector). Encode this verification as the first task in each Wave 1 plan.

6. **O-6: `app.delay` deprecation.** Phase 6 D-03 moves polling cadence to `plugin.next_delay()`. `app.delay` becomes vestigial. Recommend: keep for backwards compat in this phase; flag deprecation in a future phase. Planner decides whether to emit a one-time INFO log when `app.delay` is still set.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | runtime | ✓ (assumed; project pins >=3.11) | system-dependent | — |
| Chrome browser | Selenium + nodriver | required at runtime; not installed in CI | — | None — required for live execution; mock at test time |
| chromedriver | Selenium | autodownloaded via webdriver_manager (main.py:53) | — | webdriver_manager fallback |
| pytest, pytest-asyncio | tests | ✓ (in requirements.txt) | 8.3.4 / 1.3.0 | — |
| nodriver | new in Phase 6 | NOT YET INSTALLED | 0.50.3 (recommend pin) | None — must pip install before Wave 1 |

**Missing dependencies with no fallback:** nodriver (Plan 06-01 installs).

**Missing dependencies with fallback:** none.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | nodriver 0.50.3 is current stable as of 2026-05-15 | Summary, Standard Stack | Pin a different exact version; trivial fix |
| A2 | `await uc.start(...)` works from inside an existing `asyncio.run(main())` loop without calling `uc.loop()` | Q1, Pattern 1, O-1 | If wrong: wrap `uc.start` in a thread executor or refactor main.py to use `uc.loop().run_until_complete`. Discover in Wave 1's first plugin smoke test. |
| A3 | `await browser.stop()` is the canonical nodriver shutdown (coroutine) | Q1, Pattern 1, O-3 | If sync: wrap with hasattr check in shutdown override; works either way |
| A4 | Walmart uses `button[data-automation-id="atc-button"]` for add-to-cart | Per-retailer table, Q3 | Selector changes: plan-time verification step in Wave 1 plan |
| A5 | Target uses `button[data-test="orderPickupButton"]` | Per-retailer table, Q3 | Same as A4 |
| A6 | GameStop uses hCaptcha for checkout (vs reCAPTCHA v2) | Q6, Pitfall 7 | Different selector; detect_captcha update only |
| A7 | Square Enix selectors `button.product-detail-add-to-cart` | Per-retailer table | Same as A4 |
| A8 | NewEgg selectors `button#btnAddCart` or `.product-buy button` | Per-retailer table | Same as A4 |
| A9 | `domain_pattern` for Square Enix should cover both .com and the EU games host | Q3 | Add/remove entries; trivial |
| A10 | Chrome 138/140 UA strings are accurate for desktop | Q8 | Refresh to latest UAs at plan-time; cosmetic |
| A11 | PerimeterX evades partially via nodriver but auto-buy multi-step success is probabilistic | Q4 | Realistic expectation; sets user expectation; no code change |
| A12 | Akamai blocks headless even with `--headless=new` | Q5 | Target plugin's "warn on headless" guidance becomes "block on headless"; cosmetic |
| A13 | `inspect.iscoroutinefunction` is the right branching mechanism for async/sync plugin methods | Pattern 1 note, Pitfall 11 | Use `asyncio.iscoroutinefunction` instead; identical behavior |

## Sources

### Primary (HIGH confidence)
- `.planning/phases/06-platform-expansion/06-CONTEXT.md` — locked decisions D-01..D-04 + 10 pitfalls
- `.planning/REQUIREMENTS.md` — PLG-04..08, ANTI-01..03 wording
- `plugin_base.py`, `plugin_registry.py`, `driver.py`, `config_schema.py`, `main.py`, `plugins/shopbot_plugin_amazon.py`, `plugins/example_plugin.py`, `notifiers/shopbot_notifier_sms.py`, `plugins/PLUGIN_DEV.md`, `requirements.txt` — current source of truth read this session
- Phase 4-04 and Phase 5-06 SUMMARY.md — recent locked patterns (stagger + notification fan-out)
- [nodriver quickstart](https://ultrafunkamsterdam.github.io/nodriver/nodriver/quickstart.html) — uc.start signature, tab.select API, browser.stop, `uc.loop()` vs `asyncio.run` warning
- [nodriver PyPI](https://pypi.org/project/nodriver/) — version 0.50.3 confirmed via WebSearch

### Secondary (MEDIUM confidence)
- [Web Scraping with Nodriver: How to Scrape Undetected in 2026 — Oxylabs](https://oxylabs.io/blog/nodriver-web-scraping) — usage patterns, headless mode
- [Scraping with Nodriver: Step by Step Tutorial — ScrapingBee](https://www.scrapingbee.com/blog/nodriver-tutorial/) — browser_args, headless usage
- [How to Use Nodriver for Web Scraping — ZenRows](https://www.zenrows.com/blog/nodriver) — proxy auth, browser_args examples

### Tertiary (LOW confidence)
- Per-retailer DOM selectors (table) — ASSUMED based on general knowledge of these sites; plan-time manual verification REQUIRED
- GameStop CAPTCHA vendor (hCaptcha vs reCAPTCHA) — likely hCaptcha per industry trends; verify at implementation time

## Metadata

**Confidence breakdown:**
- Standard stack & version: HIGH (verified on pypi + libraries.io)
- nodriver async API: HIGH (verified against official quickstart docs)
- nodriver + existing asyncio.run interaction: MEDIUM (one assumption A2 flagged for Wave 1 smoke validation)
- Schema/factory/ABC mechanics: HIGH (all locked by D-01..D-04 + read in source)
- Per-retailer DOM selectors: LOW (ASSUMED; verify at plan time)
- Anti-detection success rates (PerimeterX, Akamai): LOW (probabilistic by nature)
- Plan layout overlap audit: HIGH (file paths verified)

**Research date:** 2026-05-15
**Valid until:** 2026-06-14 for infra mechanics; 2026-05-29 for selector-related claims (retailer pages reflow frequently)
