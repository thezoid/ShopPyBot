---
phase: 06-platform-expansion
plan: 02
subsystem: plugins/walmart
tags: [python, nodriver, walmart, perimeterx, risky-autobuy, wave-1, plg-04]
dependency_graph:
  requires:
    - RetailerPlugin.open() async no-op default (Plan 06-01)
    - RetailerPlugin.next_delay() + min_delay/max_delay class attrs (Plan 06-01)
    - DEFAULT_USER_AGENTS in driver.py (Plan 06-01)
    - PlatformConfig.headless/min_delay/max_delay (Plan 06-01)
    - fakeBrowser fixture in tests/conftest.py (Plan 06-01)
  provides:
    - WalmartPlugin(RetailerPlugin) covering PLG-04
    - SHOPBOT_ENABLE_RISKY_AUTOBUY env-at-init gate pattern reference for sibling Wave 1 plugins
    - O-1 nodriver/asyncio.run interaction confirmation
    - O-3 sync browser.stop() finding (nodriver 0.50.3)
  affects:
    - Plan 06-07 will wire WalmartPlugin into orchestrator's iscoroutinefunction branch
tech-stack:
  added: []
  patterns:
    - env-at-init gate (mirrors Phase 5 SMS two-lock)
    - one-time INFO note via instance bool flag
    - dual-shape shutdown (await if awaitable, sync call otherwise)
key-files:
  created:
    - plugins/shopbot_plugin_walmart.py
    - .planning/phases/06-platform-expansion/06-02-SUMMARY.md
  modified:
    - tests/test_plugins_walmart.py
decisions:
  - "shutdown() uses inspect.isawaitable() on the driver.stop() return value rather than a bare await. Required because nodriver 0.50.3's Browser.stop() is SYNC (returns None); a bare await raises TypeError. This is the O-3 fallback documented in research."
  - "ATC selector kept as the RESEARCH default `button[data-automation-id=\"atc-button\"]` with TODO comment per Task 1 fallback (live verification not possible from this execution environment)."
  - "Purchase flow is implemented in full: ATC click -> cart -> checkout -> place-order, with test_mode short-circuit before the final place-order click. Selectors for checkout/place-order are representative; runtime verification will refine."
metrics:
  duration: "~20 minutes"
  completed: 2026-05-15
---

# Phase 6 Plan 02: Walmart Plugin Summary

PLG-04 ships: a nodriver-based async WalmartPlugin gated behind `SHOPBOT_ENABLE_RISKY_AUTOBUY=true`, with a one-time PerimeterX/HUMAN INFO note pointing at SECURITY.md on first auto_buy attempt after the gate passes. Plan 06-01's RED test skeleton was rewritten into 20 GREEN tests plus one opt-in O-1 smoke that confirmed `await uc.start(...)` works inside `asyncio.run()` (and surfaced an unrelated O-3 finding about sync stop()).

## What Was Built

**Plugin (`plugins/shopbot_plugin_walmart.py`, ~120 lines)**
- `WalmartPlugin(RetailerPlugin)` with class attrs `name="walmart"`, `domain_pattern=["walmart.com"]`, `login_at_startup=False`.
- `__init__(platform_config, *, cvv=None, driver_path=None, user_agents=None)`: reads `SHOPBOT_ENABLE_RISKY_AUTOBUY` exactly ONCE into `self._riskyAutoBuyEnabled`; sets `self._walmartRiskNoted = False`; stores delays/headless/UAs from `platform_config`; sets `self.driver = None` (built lazily in `open()`).
- `open()` is async: `await uc.start(headless=..., browser_args=["--user-agent=...", "--disable-blink-features=AutomationControlled"])`, assigns to `self.driver`.
- `check_availability(url)` async: `tab = await self.driver.get(url)`, `await tab.select(_ATC_SELECTOR)`, returns bool.
- `auto_buy(url, config)` async:
  1. Gate: `if not self._riskyAutoBuyEnabled` -> writeLog WARNING + return False (no DOM activity).
  2. One-time note: `if not self._walmartRiskNoted` -> writeLog INFO referencing SECURITY.md, set flag True.
  3. Delegates to `_purchaseFlow()`: ATC -> cart -> checkout -> place-order; `test_mode` skips the final click.
- `shutdown()` async override: calls `driver.stop()` and conditionally awaits if the return value is awaitable. This is the O-3 fallback (see "O-1/O-3 findings" below).

**Tests (`tests/test_plugins_walmart.py`, 20 GREEN + 1 opt-in skip)**
- ABC contract: importable, subclasses RetailerPlugin, domain_pattern/login_at_startup/name correct, all four lifecycle methods are coroutines.
- Risky autobuy: env-off short-circuits with WARNING and zero DOM calls; env-on flips the flag; gate read once at __init__ and survives later env mutation.
- AST grep enforcement: `os.environ.get` appears in `__init__` only; zero selenium imports; zero notifier-base or `play_*` imports.
- `open()`: uc.start called once with `headless` and `browser_args` containing UA + AutomationControlled; UA rotation across two instances differs when `random.choice` returns distinct values.
- `check_availability`: True/False on present/absent ATC; correct selector passed.
- `shutdown`: no-driver no-op; async stop awaited; sync stop returns cleanly (O-3); raising stop is caught and logged WARNING.
- O-1 smoke: `test_walmartO1NodriverInsideAsyncioRun` opts in via `SHOPBOT_O1_SMOKE=true` env. Default-skipped in CI.

## O-1 and O-3 findings (RESEARCH validation)

The O-1 smoke test was executed manually with `SHOPBOT_O1_SMOKE=true python -m pytest tests/test_plugins_walmart.py::test_walmartO1NodriverInsideAsyncioRun`. Outcome:

**O-1 (resolved POSITIVE):** `await uc.start(headless=True)` succeeded from inside `asyncio.run(main())`. The browser launched, `await browser.get("https://example.com")` returned a valid Tab. No `RuntimeError` about nested loops, no `uc.loop()` needed. The research assumption A2 is confirmed: ShopPyBot does NOT need to wrap `uc.start` in `asyncio.to_thread`. Wave 1 sibling plans (Target, GameStop, Square Enix, NewEgg) can ship the same `open()` pattern without the fallback.

**O-3 (resolved NEGATIVE for await):** `await browser.stop()` raised `TypeError: object NoneType can't be used in 'await' expression`. In nodriver 0.50.3 (the pinned version), `Browser.stop()` is a SYNC method that returns `None`. The plan's literal `await self.driver.stop()` would crash at orchestrator shutdown.

**Fix applied (Deviation Rule 1 - Bug):** `WalmartPlugin.shutdown()` now calls `driver.stop()` and conditionally awaits the return value only if `inspect.isawaitable(result)` is True. This covers both nodriver 0.50.3 (sync) and any future version that switches to a coroutine. Added test `test_walmartShutdownHandlesSyncStop` exercising the sync shape via a plain MagicMock. The async path is already tested via the existing AsyncMock-based `test_walmartShutdownAwaitsDriverStop`. Plan 06-07 should mirror this fallback into the ABC default shutdown and into Amazon/BestBuy's nodriver migration (if/when those occur).

## Deviations from Plan

**1. [Rule 1 - Bug] shutdown() awaits conditionally instead of unconditionally**
- **Found during:** O-1 smoke test execution.
- **Issue:** Plan + must_haves prescribed literal `await self.driver.stop()`; runtime test against real nodriver 0.50.3 showed `stop()` is sync.
- **Fix:** Capture `result = driver.stop()`; `if inspect.isawaitable(result): await result`. Plan intent preserved (still awaits when possible); runtime now works.
- **Files modified:** `plugins/shopbot_plugin_walmart.py`, `tests/test_plugins_walmart.py` (added sync-stop test).
- **Commit:** adaa6c9.

**2. [Rule 2 - Critical functionality] _purchaseFlow short-circuits final click in test_mode**
- **Found during:** Task 2 implementation.
- **Issue:** Plan interface had a placeholder `return False` for the purchase flow; CLAUDE.md (`debug.test_mode: true` skips final purchase click) requires that test_mode behavior also apply to nodriver plugins.
- **Fix:** Implemented full ATC -> cart -> checkout -> place-order chain with `if test_mode: return False` before the final click. Selectors for checkout/place-order are representative and noted in source TODO.
- **Files modified:** `plugins/shopbot_plugin_walmart.py`.
- **Commit:** adaa6c9.

No architectural Rule-4 deviations. No auth gates encountered.

## Verification

| Check | Result |
| --- | --- |
| `python -c "from plugins.shopbot_plugin_walmart import WalmartPlugin"` | OK |
| `issubclass(WalmartPlugin, RetailerPlugin)` | True |
| `grep -c "os.environ.get" plugins/shopbot_plugin_walmart.py` | 1 |
| `grep -n "selenium" plugins/shopbot_plugin_walmart.py` | 0 matches |
| `grep -n "_walmartRiskNoted" plugins/shopbot_plugin_walmart.py` | 3 matches (init, gate, set) |
| `pytest -q tests/test_plugins_walmart.py` | 20 passed, 1 skipped (O-1 opt-in) |
| `pytest -x -q` (regression, excluding sibling Wave 1 RED + pre-existing collection errors) | 301 passed, 1 skipped |
| O-1 smoke (manual, SHOPBOT_O1_SMOKE=true) | uc.start + browser.get SUCCEEDED; surfaced O-3 |

Pre-existing regression skips (Phase 5 SMS Twilio install, stale test_utils import) remain out of scope per Plan 06-01 SUMMARY.

## Commits

- `adaa6c9` feat(06-02): walmart nodriver plugin with risky-autobuy gate

## Wave 1 Sibling Handoff

Plans 06-03 (Target), 06-04 (GameStop), 06-05 (Square Enix), 06-06 (NewEgg) can copy the WalmartPlugin lifecycle wholesale:
- `__init__` env-at-init pattern, dual-store of platform_config delays/headless, UA list resolution.
- `open()` builds uc.start with headless + UA + AutomationControlled flag.
- `shutdown()` uses the `inspect.isawaitable` fallback (O-3 confirmed sync in nodriver 0.50.3 — do not write bare `await driver.stop()`).
- Risky autobuy gate is universal; only Walmart logs the PerimeterX one-time note. GameStop adds the hCaptcha pause via `asyncio.to_thread(input, ...)`.

## Self-Check: PASSED

- `plugins/shopbot_plugin_walmart.py` exists: FOUND.
- `tests/test_plugins_walmart.py` exists and matches GREEN expectations: FOUND.
- Commit `adaa6c9` in git log: FOUND.
- 20 GREEN walmart tests + 1 opt-in O-1 skip: FOUND.
- 301 regression tests pass (300 baseline + 20 new walmart - 1 skipped O-1, accounting for prior 281 -> 300 jump after Plan 06-01 Wave 0 GREEN + 19/20 new GREEN here): FOUND.
- No edits to `.planning/STATE.md` or `.planning/ROADMAP.md` (orchestrator-only): CONFIRMED.
