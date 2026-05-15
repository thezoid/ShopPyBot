---
phase: 06-platform-expansion
plan: 07
subsystem: orchestrator+plugins+docs
tags: [python, asyncio, orchestrator, integration, docs, wave-2]
requires:
  - 06-01 (RetailerPlugin.open + next_delay defaults)
  - 06-02..06-06 (5 Wave 1 plugins land first)
  - driver.build_driver headless + user_agents kwargs (06-01)
provides:
  - main.py orchestrator branches on inspect.iscoroutinefunction for async/sync plugin methods
  - per-platform jitter via plugin.next_delay() in poll_plugin
  - Amazon headless+OTP guard (ValueError before build_driver)
  - Amazon + BestBuy thread headless + user_agents through build_driver
  - PLUGIN_DEV.md Selenium-vs-nodriver section + risky-autobuy gate doc
affects:
  - main.py poll loop cadence (per-plugin not global)
  - Amazon and BestBuy driver construction
tech-stack:
  added: []
  patterns:
    - inspect.iscoroutinefunction branch routing for sync vs async plugin methods
    - getattr(platform_config, "headless", False) defensive read for stub-friendly tests
    - additive ABC defaults (open + next_delay) without PLUGIN_API_VERSION bump
key-files:
  created:
    - .planning/phases/06-platform-expansion/06-07-SUMMARY.md
    - .planning/phases/06-platform-expansion/deferred-items.md
  modified:
    - main.py (import inspect; iscoroutinefunction branches in _poll_once and _attempt_purchase; poll_plugin uses plugin.next_delay)
    - plugins/shopbot_plugin_amazon.py (headless+OTP ValueError guard; build_driver passthrough)
    - plugins/shopbot_plugin_bestbuy.py (build_driver headless + user_agents passthrough)
    - plugins/PLUGIN_DEV.md (Selenium vs nodriver section, risky-autobuy gate, live-test scope, PLUGIN_API_VERSION note)
    - tests/test_orchestrator.py (next_delay + iscoroutinefunction branch tests)
    - tests/test_plugins_amazon.py (headless guard test + user_agents passthrough test)
    - tests/test_plugins_bestbuy.py (headless + user_agents passthrough test)
decisions:
  - Used getattr(platform_config, "headless", False) instead of attribute access so existing test stubs (_DummyPlatform without headless attr) keep passing without modification
  - Kept app.delay key in AppSettings as inert legacy fallback per Researcher O-6; orchestrator no longer reads it directly
  - Ran full suite excluding tests/test_utils.py which has a pre-existing ImportError unrelated to this plan (logged in deferred-items.md)
metrics:
  duration: ~15min
  completed: 2026-05-15
  tasks: 2
  commits: 3
  files-modified: 7
---

# Phase 6 Plan 7: Orchestrator Integration and Docs Summary

Final Phase 6 plan: wire the foundation plus five Wave 1 plugins into the running orchestrator. Three surgical main.py changes (next_delay, iscoroutinefunction-branched check_availability, iscoroutinefunction-branched auto_buy) plus Amazon and BestBuy driver construction updates plus PLUGIN_DEV.md guidance.

## What changed

main.py:
1. Added `import inspect` at top of file.
2. `_poll_once` now branches on `inspect.iscoroutinefunction(plugin.check_availability)`: async plugins are awaited directly; sync Selenium plugins still go via `asyncio.to_thread`.
3. `_attempt_purchase` mirrors the same branch for `plugin.auto_buy`.
4. `poll_plugin` removed `delay = app_config.app.delay` and now calls `plugin.next_delay()` fresh on each iteration so jitter is per-platform and per-poll.

plugins/shopbot_plugin_amazon.py:
1. `__init__` now raises `ValueError` with substrings "AmazonPlugin does not support headless mode" and "OTP requires visual access" when `platform_config.headless is True` AND `login_at_startup` is True. Guard fires BEFORE `build_driver` so a misconfigured Amazon never spawns a headless Chrome.
2. `build_driver` call now passes `headless=platform_config.headless` and `user_agents=user_agents` kwargs.

plugins/shopbot_plugin_bestbuy.py:
1. `build_driver` call now passes `headless=platform_config.headless` and `user_agents=user_agents` kwargs (no guard: BestBuy login is non-interactive).

plugins/PLUGIN_DEV.md gained a `## Selenium vs nodriver: choosing a driver` section covering: driver-choice table, nodriver checklist, SHOPBOT_ENABLE_RISKY_AUTOBUY gate with code example, live-test scope policy, PLUGIN_API_VERSION stability note.

## Commits

- 492c11b test(06-07): RED failing tests for next_delay, iscoroutinefunction, headless guard
- 9f8e53b feat(06-07): wire next_delay, iscoroutinefunction branches, amazon headless guard
- 44271d6 docs(06-07): add Selenium-vs-nodriver guidance and risky autobuy gate section

## Tests added

tests/test_orchestrator.py:
- test_pollPluginUsesNextDelay: fake plugin records next_delay() calls; asserts called at least once per poll iteration.
- test_pollOnceAwaitsAsyncCheck: async check_availability is awaited directly (recorder confirms it does NOT pass through asyncio.to_thread).
- test_pollOnceToThreadSyncCheck: sync check_availability is wrapped via asyncio.to_thread.
- test_attemptPurchaseAwaitsAsyncAutoBuy and test_attemptPurchaseToThreadSyncAutoBuy mirror for auto_buy.
- test_mainImportsInspect, test_mainUsesIscoroutinefunctionForCheck, test_mainUsesIscoroutinefunctionForAutoBuy, test_pollPluginNoLongerReadsAppDelay: AST/source greps over main.py.

tests/test_plugins_amazon.py:
- test_amazonHeadlessLoginRaises: asserts ValueError with both required substrings and confirms build_driver Mock was never called.
- test_amazonPassesHeadlessAndUserAgentsToBuildDriver: asserts kwargs reach build_driver.

tests/test_plugins_bestbuy.py:
- test_bestbuyPassesHeadlessAndUserAgentsToBuildDriver: asserts kwargs reach build_driver.

## Test results

`pytest -q --ignore=tests/test_utils.py`: 423 passed, 1 skipped, 1 warning.

tests/test_utils.py has a pre-existing ImportError (`cannot import name 'make_tiny' from 'utils'`) that predates this plan. Verified via `git stash` plus rerun. Logged in `deferred-items.md`.

## Deviations from Plan

### Auto-fixed Issues

None. Plan executed as written.

### Deviations from spec (low risk)

1. **defensive getattr on platform_config.headless** instead of direct attribute access in Amazon and BestBuy __init__. Rationale: existing Amazon and BestBuy test fixtures (`_DummyPlatform`) do not declare a `headless` attr. Direct `platform_config.headless` would AttributeError on every existing test. Using `getattr(platform_config, "headless", False)` keeps the existing test suite GREEN with zero edits to those stubs while still satisfying the headless+OTP guard contract for production config (Pydantic PlatformConfig always has headless). The new headless-guard test explicitly provides a `_HeadlessPlatform` with `headless = True`, so the guard remains exercised.

## Requirements satisfied

- ANTI-01: per-platform jitter via `plugin.next_delay()` in poll_plugin (was Plan 06-01 default).
- ANTI-02: `user_agents` threads through `build_driver` (Amazon, BestBuy) where Phase 6 random.choice already lives in driver.py.
- ANTI-03: `headless` honored by `build_driver`; Amazon raises clear ValueError when headless conflicts with OTP login.
- PLG-04..08 (Walmart, Target, GameStop, Square Enix, NewEgg) already satisfied by Wave 1 plans; this plan completes the orchestrator wiring so the 5 new plugins coexist with Amazon and BestBuy under a single TaskGroup.

## TDD Gate Compliance

Plan does not have `type: tdd` at the plan level (type: execute), but individual tasks used `tdd="true"`. Gate sequence verified:
- 492c11b test(06-07) RED: 10 failing tests confirmed
- 9f8e53b feat(06-07) GREEN: all 48 targeted tests pass
- 44271d6 docs(06-07): documentation, no separate refactor commit needed

## Self-Check: PASSED

Verified:
- main.py contains `import inspect` (line 26): FOUND
- main.py contains `iscoroutinefunction(plugin.check_availability` and `iscoroutinefunction(plugin.auto_buy`: FOUND
- main.py contains `plugin.next_delay()` and NO `app_config.app.delay`: FOUND
- plugins/shopbot_plugin_amazon.py contains `AmazonPlugin does not support headless mode`: FOUND
- plugins/shopbot_plugin_bestbuy.py build_driver kwargs include headless: FOUND
- plugins/PLUGIN_DEV.md contains `Selenium vs nodriver`, `SHOPBOT_ENABLE_RISKY_AUTOBUY`, `Live-retailer integration tests`, `PLUGIN_API_VERSION`: FOUND
- Commits 492c11b, 9f8e53b, 44271d6 in git log: FOUND
