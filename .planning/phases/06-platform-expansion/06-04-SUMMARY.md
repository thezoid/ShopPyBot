---
phase: 06-platform-expansion
plan: 04
subsystem: plugins/gamestop
tags: [python, nodriver, gamestop, hcaptcha, risky-autobuy, wave-1, plg-06]
dependency_graph:
  requires:
    - RetailerPlugin.open() async no-op default (Plan 06-01)
    - RetailerPlugin.detect_captcha() sync default (Plan 06-01) — overridden to coroutine here
    - DEFAULT_USER_AGENTS in driver.py (Plan 06-01)
    - PlatformConfig.headless/min_delay/max_delay (Plan 06-01)
    - fakeBrowser fixture in tests/conftest.py (Plan 06-01)
    - O-3 sync stop() fallback proven by Plan 06-02
  provides:
    - GamestopPlugin(RetailerPlugin) covering PLG-06
    - hCaptcha detection + asyncio.to_thread(input) pause pattern reference for any future CAPTCHA-bearing retailer
  affects:
    - Plan 06-07 will wire GamestopPlugin into orchestrator's plugin registry
tech-stack:
  added: []
  patterns:
    - env-at-init risky-autobuy gate (mirrors Walmart/Target)
    - dual-selector CAPTCHA detection (iframe + widget container)
    - asyncio.to_thread(input) pause (Phase 4 D-02) so the event loop continues serving sibling plugins
    - dual-shape shutdown (await if awaitable, sync call otherwise) inherited from O-3 fallback
key-files:
  created:
    - plugins/shopbot_plugin_gamestop.py
    - .planning/phases/06-platform-expansion/06-04-SUMMARY.md
  modified:
    - tests/test_plugins_gamestop.py
decisions:
  - "Class name is `GamestopPlugin` per Plan 06-04 must_haves (single-word PascalCase mirroring WalmartPlugin/TargetPlugin), not the `GameStopPlugin` shape from the Plan 06-01 RED skeleton. The RED skeleton was always going to be rewritten in this plan; aligning with the must_haves keeps the Wave 1 sibling lineage consistent."
  - "detect_captcha is overridden as an async coroutine (must_haves D-01); the Phase 1 ABC default is sync. inspect.iscoroutinefunction(GamestopPlugin.detect_captcha) is asserted by test_gamestopAbcContract."
  - "auto_buy delegates to a private _purchaseFlow() to mirror WalmartPlugin/TargetPlugin structure. The CAPTCHA pause runs at two checkpoints (cart load and post-checkout-click) because hCaptcha can surface at either step."
  - "shutdown() uses inspect.isawaitable() on driver.stop() rather than a bare await — the O-3 nodriver 0.50.3 finding from Plan 06-02 applies identically here. No live runtime re-verification needed; the same nodriver pin is in effect."
  - "Selectors (ATC `button.add-to-cart:not(:disabled)`, hCaptcha iframe `iframe[src*=\"hcaptcha.com\"]`, hCaptcha widget `div[data-hcaptcha-widget-id]`) kept as RESEARCH defaults with TODO comment per Task 1 fallback (live verification not possible from this execution environment)."
metrics:
  duration: "~15 minutes"
  completed: 2026-05-15
---

# Phase 6 Plan 04: GameStop Plugin Summary

PLG-06 ships: a nodriver-based async GamestopPlugin gated behind `SHOPBOT_ENABLE_RISKY_AUTOBUY=true`, with hCaptcha detection across iframe + widget selectors and a pause-for-manual-solve via `await asyncio.to_thread(input, ...)` (Phase 4 D-02 pattern). The to_thread bridge keeps the event loop responsive: a concurrency test proves two simultaneous CAPTCHA-bearing auto_buy invocations complete within a 5-second timeout when each pause receives an empty stdin reply. Plan 06-01's 6-test RED skeleton was rewritten into 23 GREEN tests including AST-grep enforcement that every `input(...)` call is wrapped by `asyncio.to_thread`.

## What Was Built

**Plugin (`plugins/shopbot_plugin_gamestop.py`, ~145 lines)**
- `GamestopPlugin(RetailerPlugin)` with class attrs `name="gamestop"`, `domain_pattern=["gamestop.com"]`, `login_at_startup=False`.
- `__init__(platform_config, *, cvv=None, driver_path=None, user_agents=None)` reads `SHOPBOT_ENABLE_RISKY_AUTOBUY` exactly ONCE into `self._riskyAutoBuyEnabled`; stores delays/headless/UAs; sets `self.driver = None` and `self._tab = None` (built lazily in `open()` / `_purchaseFlow()`).
- `open()` async: `await uc.start(headless=..., browser_args=["--user-agent=...", "--disable-blink-features=AutomationControlled"])`.
- `check_availability(url)` async: `await self.driver.get(url)`, `await tab.select(_ATC_SELECTOR)`, returns bool.
- `detect_captcha()` async override: returns False on null `_tab`; otherwise queries iframe selector first, then widget selector; True if either resolves.
- `auto_buy(url, config)` async: gate check + WARNING short-circuit; delegates to `_purchaseFlow()`.
- `_purchaseFlow()` async: ATC -> click -> cart-tab -> detect_captcha + pause -> checkout click -> detect_captcha + pause -> place-order. `test_mode` short-circuits before the final click. Two CAPTCHA checkpoints because hCaptcha can fire at either cart or checkout.
- `shutdown()` async override: O-3 fallback — `result = driver.stop(); if inspect.isawaitable(result): await result`; exceptions logged WARNING and swallowed.

**Tests (`tests/test_plugins_gamestop.py`, 23 GREEN)**
- ABC contract: importable, subclasses RetailerPlugin, domain_pattern/login_at_startup/name correct, all FIVE lifecycle methods (open, check_availability, auto_buy, detect_captcha, shutdown) are coroutines.
- Risky autobuy gate: env-off short-circuits with WARNING + zero DOM calls; env-on flips the flag; env read once and survives later env mutation.
- AST grep enforcement: `os.environ.get` appears in `__init__` only; zero selenium imports; zero notifier-base / `play_*` imports; every `input(...)` Call is wrapped in `asyncio.to_thread(...)` (no bare input).
- `detect_captcha`: null tab returns False; iframe-only sentinel returns True; widget-only sentinel returns True; both None returns False.
- **`test_gamestopCaptchaPauseNonBlocking`**: builds two GamestopPlugin instances, monkeypatches `builtins.input` to return immediately, kicks off both `auto_buy()` calls via `asyncio.gather` inside `asyncio.wait_for(timeout=5.0)`. Both complete and the CAPTCHA WARNING is logged at least twice. Proves the to_thread(input) bridge keeps the event loop responsive — the Phase 4 D-02 lock applied to a plugin method.
- `check_availability`: True/False on present/absent ATC; correct selector passed.
- `open()`: uc.start called once with headless + browser_args containing UA + AutomationControlled.
- UA rotation: two instances with stubbed `random.choice` emit distinct UAs.
- `shutdown`: no-driver no-op; sync stop returns cleanly (O-3); raising stop is caught and logged WARNING.

## Deviations from Plan

**1. [Rule 1 - Spec consistency] Class name `GamestopPlugin` instead of `GameStopPlugin`**
- **Found during:** Task 2 implementation.
- **Issue:** Plan 06-01 RED skeleton used `GameStopPlugin`; Plan 06-04 must_haves prescribe `GamestopPlugin`. The two are mutually exclusive.
- **Fix:** Followed must_haves (single-word PascalCase mirroring `WalmartPlugin` and `TargetPlugin`). The RED skeleton was always slated for full rewrite in this plan, so no production caller is affected.
- **Files modified:** `plugins/shopbot_plugin_gamestop.py`, `tests/test_plugins_gamestop.py`.
- **Commit:** 204ec29.

**2. [Rule 2 - Critical functionality] Two CAPTCHA checkpoints instead of one**
- **Found during:** Task 2 implementation.
- **Issue:** Plan interface placed a single `detect_captcha` call mid-flow; in practice hCaptcha can fire at cart load OR at the click-to-checkout transition, and missing either leaves the plugin stuck clicking a disabled element.
- **Fix:** Inserted `detect_captcha + pause` after both the cart navigation and the checkout-button click. Each pause is independent so the user is only prompted when a CAPTCHA is actually present.
- **Files modified:** `plugins/shopbot_plugin_gamestop.py`.
- **Commit:** 204ec29.

**3. [Rule 1 - Bug] shutdown() uses inspect.isawaitable() fallback (O-3)**
- **Found during:** Pre-implementation review of Plan 06-02 SUMMARY.
- **Issue:** Plan interface prescribed literal `await self.driver.stop()`; Plan 06-02 already proved nodriver 0.50.3's `Browser.stop()` is sync. A bare await would raise TypeError at orchestrator shutdown.
- **Fix:** Adopted the same `result = driver.stop(); if inspect.isawaitable(result): await result` pattern. Test `test_gamestopShutdownHandlesSyncStop` exercises the sync shape; `test_gamestopShutdownDriverStopRaises` exercises error swallowing.
- **Files modified:** `plugins/shopbot_plugin_gamestop.py`, `tests/test_plugins_gamestop.py`.
- **Commit:** 204ec29.

No architectural Rule-4 deviations. No auth gates encountered. Task 1 selector verification accepted the RESEARCH defaults with a TODO comment (live verification against gamestop.com not possible from this execution environment, mirroring the Walmart/Target precedent).

## Verification

| Check | Result |
| --- | --- |
| `python -c "from plugins.shopbot_plugin_gamestop import GamestopPlugin; assert issubclass(GamestopPlugin, RetailerPlugin)"` | OK |
| `grep -c "os.environ.get" plugins/shopbot_plugin_gamestop.py` | 1 |
| `grep -n "selenium" plugins/shopbot_plugin_gamestop.py` | 0 matches |
| `grep -c "asyncio.to_thread" plugins/shopbot_plugin_gamestop.py` | 2 (cart + checkout checkpoints) |
| `grep -c "hcaptcha" plugins/shopbot_plugin_gamestop.py` | 3 (iframe selector + widget selector + writeLog message constants) |
| `pytest -q tests/test_plugins_gamestop.py` | 23 passed |
| Regression (`pytest -q --ignore=squareenix --ignore=newegg --ignore=test_utils.py`) | 362 passed, 1 skipped |

Pre-existing skips/failures out of scope per Plan 06-01 SUMMARY:
- `tests/test_utils.py` collection error (`cannot import name 'make_tiny'`) is a pre-existing stale import unrelated to this plan.
- `tests/test_plugins_squareenix.py`, `tests/test_plugins_newegg.py` remain RED for their own Wave 1 plans (06-05, 06-06).

## Commits

- `204ec29` feat(06-04): gamestop nodriver plugin with hCaptcha to_thread pause

## Self-Check: PASSED

- `plugins/shopbot_plugin_gamestop.py` exists: FOUND.
- `tests/test_plugins_gamestop.py` exists with GREEN suite: FOUND.
- Commit `204ec29` in git log: FOUND.
- 23 GREEN gamestop tests, 362 regression tests pass: FOUND.
- No edits to `.planning/STATE.md` or `.planning/ROADMAP.md`: CONFIRMED.
