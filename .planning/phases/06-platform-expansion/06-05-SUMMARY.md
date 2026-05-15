---
phase: 06-platform-expansion
plan: 05
subsystem: plugins/squareenix
tags: [python, nodriver, squareenix, risky-autobuy, wave-1, plg-07, dual-domain]
dependency_graph:
  requires:
    - RetailerPlugin.open() async no-op default (Plan 06-01)
    - DEFAULT_USER_AGENTS in driver.py (Plan 06-01)
    - PlatformConfig.headless/min_delay/max_delay (Plan 06-01)
    - fakeBrowser fixture in tests/conftest.py (Plan 06-01)
    - plugin_registry.route_url (Plan 02-02) for dual-domain assertions
    - O-1 + O-3 findings from Plan 06-02 SUMMARY (await uc.start works; Browser.stop is sync)
  provides:
    - SquareEnixPlugin(RetailerPlugin) covering PLG-07
    - Dual-domain domain_pattern reference (square-enix.com + square-enix-games.com)
  affects:
    - Plan 06-07 will wire SquareEnixPlugin into orchestrator's iscoroutinefunction branch
tech-stack:
  added: []
  patterns:
    - env-at-init risky-autobuy gate (mirrors Walmart/Target/GameStop)
    - dual-entry domain_pattern (square-enix.com + square-enix-games.com)
    - inspect.isawaitable() shutdown (O-3 fallback)
key-files:
  created:
    - plugins/shopbot_plugin_squareenix.py
    - .planning/phases/06-platform-expansion/06-05-SUMMARY.md
  modified:
    - tests/test_plugins_squareenix.py
decisions:
  - "Dual-entry domain_pattern [\"square-enix.com\", \"square-enix-games.com\"] covers both the US storefront (.com) and the EU/games subdomain. plugin_registry._matches uses endswith(\".\" + pattern), so this naturally covers store.na.square-enix-games.com, store.eu.square-enix-games.com, and bare square-enix-games.com hosts. Five parametrized URLs cover the expected variants."
  - "ATC selector kept as the RESEARCH default `button.product-detail-add-to-cart` with TODO comment per Task 1 fallback. Live verification not possible from this execution environment, matching the Walmart/Target/GameStop plan-time approach."
  - "shutdown() uses the inspect.isawaitable() pattern (Walmart O-3 fallback) rather than a bare await on driver.stop(). Required because nodriver 0.50.3's Browser.stop() is SYNC and returns None."
  - "Plan tasks 1 and 2 collapsed into one atomic commit because Task 1 was a verification-only step that accepted defaults (no code delta independent of Task 2)."
metrics:
  duration: "~10 minutes"
  completed: 2026-05-15
---

# Phase 6 Plan 05: Square Enix Plugin Summary

PLG-07 ships: a nodriver-based async SquareEnixPlugin gated behind `SHOPBOT_ENABLE_RISKY_AUTOBUY=true`. The Square Enix specific wrinkle is the dual-entry `domain_pattern` covering both `square-enix.com` (US storefront) and `square-enix-games.com` (EU/games subdomain and its store.* hosts via the registry's suffix-match). Plan 06-01's RED test skeleton was rewritten into 26 GREEN tests. Wave 1 sibling findings (O-1 positive, O-3 negative) from Plan 06-02 were applied directly.

## What Was Built

**Plugin (`plugins/shopbot_plugin_squareenix.py`, ~115 lines)**
- `SquareEnixPlugin(RetailerPlugin)` with class attrs `name="squareenix"`, `domain_pattern=["square-enix.com", "square-enix-games.com"]`, `login_at_startup=False`.
- `__init__(platform_config, *, cvv=None, driver_path=None, user_agents=None)`: reads `SHOPBOT_ENABLE_RISKY_AUTOBUY` exactly ONCE into `self._riskyAutoBuyEnabled`; stores delays/headless/UAs from `platform_config`; sets `self.driver = None` (built lazily in `open()`).
- `open()` async: `await uc.start(headless=..., browser_args=["--user-agent=...", "--disable-blink-features=AutomationControlled"])`, assigns to `self.driver`.
- `check_availability(url)` async: `tab = await self.driver.get(url)`, `await tab.select(_ATC_SELECTOR)`, returns bool. Exception path logs ERROR and returns False.
- `auto_buy(url, config)` async:
  1. Gate: `if not self._riskyAutoBuyEnabled` -> writeLog WARNING + return False (no DOM activity).
  2. Delegates to `_purchaseFlow()`: ATC -> checkout -> place-order; `test_mode` short-circuits the final click.
- `shutdown()` async override: calls `driver.stop()` and conditionally awaits if the return value is awaitable (O-3 fallback).

**Tests (`tests/test_plugins_squareenix.py`, 26 GREEN)**
- ABC contract: importable, subclasses RetailerPlugin, both domain entries present, login_at_startup/name correct, all four lifecycle methods are coroutines.
- Risky autobuy: env-off short-circuits with WARNING and zero DOM calls; env-on flips the flag; gate read once at __init__ survives later env mutation.
- AST grep enforcement: `os.environ.get` appears only in `__init__`; zero selenium imports; zero notifier-base or `play_*` imports.
- Dual-domain routing (parametrized over 5 URL variants): all match via `plugin_registry.route_url`. Off-domain (`example.com`, `walmart.com`) returns None.
- `open()`: uc.start called once with `headless` + `browser_args` containing UA + AutomationControlled. UA rotation across two instances differs when `random.choice` returns distinct values. Headless passthrough.
- `check_availability`: True/False on present/absent ATC; correct selector passed; exception path logs ERROR and returns False.
- `shutdown`: no-driver no-op; async-shaped stop awaited; sync-shaped stop (MagicMock with `return_value=None`) returns cleanly without TypeError; raising stop is caught and logged WARNING.

## Wave 1 Sibling Findings Applied

**O-1 (POSITIVE):** Plan 06-02 confirmed `await uc.start(headless=...)` works inside `asyncio.run()`. SquareEnixPlugin uses the standard async pattern with no `asyncio.to_thread` fallback. No O-1 smoke test included in this file because the Walmart smoke already settled it.

**O-3 (NEGATIVE):** Plan 06-02 found nodriver 0.50.3's `Browser.stop()` is SYNC. SquareEnixPlugin's `shutdown()` uses the `inspect.isawaitable(result)` pattern matching Walmart:

```python
result = driver.stop()
if inspect.isawaitable(result):
    await result
```

The `test_squareenixShutdownHandlesSyncStop` test exercises the sync shape via plain MagicMock; the async path is already covered by `test_squareenixShutdownAwaitsAsyncStop` using the AsyncMock-based `fakeBrowser` fixture.

## Deviations from Plan

**1. [Scope] Task 1 + Task 2 collapsed into one atomic commit.**
- **Found during:** Task 1 verification.
- **Issue:** Task 1 was a verification-only step that produced no independent file delta (defaults accepted with TODO marker), and the TODO is already part of the Task 2 plugin source. Splitting it into a standalone commit would have produced an empty commit.
- **Decision:** Single atomic commit `df584f0` covering both tasks. The plugin source carries the TODO comment naming Plan 06-05 Task 1, preserving the verification trail.

**2. [Rule 2 - Critical functionality] _purchaseFlow expanded beyond the interfaces sketch.**
- **Found during:** Task 2 implementation.
- **Issue:** The plan's `<interfaces>` sketch of `auto_buy` only ATCs and then returns False with a comment. For consistency with WalmartPlugin/TargetPlugin/GameStopPlugin, the actual flow should be ATC -> checkout -> place-order with a `test_mode` short-circuit before the final click.
- **Fix:** Added private `_purchaseFlow` mirroring the Walmart structure, with representative `button.checkout-button` and `button.place-order-button` selectors carrying the same plan-time-default caveat as the ATC selector. `test_mode` skip preserves the safety pattern.
- **Files modified:** `plugins/shopbot_plugin_squareenix.py`.
- **Commit:** `df584f0`.

No selectors were changed from the plan's `<interfaces>` defaults; live PDP verification is recorded as a TODO marker for a future plan.

## Verification

- `python -c "from plugins.shopbot_plugin_squareenix import SquareEnixPlugin; from plugin_base import RetailerPlugin; assert issubclass(SquareEnixPlugin, RetailerPlugin)"` PASS.
- `rtk grep -c "selenium" plugins/shopbot_plugin_squareenix.py` returns 0.
- `rtk grep -c "os.environ.get" plugins/shopbot_plugin_squareenix.py` returns 1.
- `python -m pytest -q tests/test_plugins_squareenix.py` 26 passed.
- Full suite (excluding pre-existing `tests/test_utils.py` collection error which is unrelated, and `tests/test_plugins_newegg.py` which is the Wave 1 sibling RED skeleton): 388 passed, 1 skipped.

## Self-Check: PASSED

- File `plugins/shopbot_plugin_squareenix.py` exists.
- File `tests/test_plugins_squareenix.py` exists (modified).
- Commit `df584f0` exists in git log.
