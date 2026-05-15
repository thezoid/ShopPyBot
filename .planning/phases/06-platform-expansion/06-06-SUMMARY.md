---
phase: 06-platform-expansion
plan: 06
subsystem: plugins/newegg
tags: [python, nodriver, newegg, risky-autobuy, wave-1]
requires:
  - plugin_base.RetailerPlugin (Plan 06-01)
  - plugin_registry.route_url (Plan 06-01)
  - driver.DEFAULT_USER_AGENTS (Plan 06-01)
provides:
  - plugins.shopbot_plugin_newegg.NeweggPlugin (PLG-08)
affects:
  - tests/test_plugins_newegg.py (RED -> GREEN)
tech-stack:
  added: []
  patterns:
    - "nodriver async lifecycle (open/check_availability/auto_buy/shutdown)"
    - "env-at-init risky-autobuy gate (SHOPBOT_ENABLE_RISKY_AUTOBUY)"
    - "inspect.isawaitable shutdown shim (O-3 fallback)"
key-files:
  created:
    - plugins/shopbot_plugin_newegg.py
  modified:
    - tests/test_plugins_newegg.py
decisions:
  - "Accepted default _ATC_SELECTOR='button#btnAddCart' per RESEARCH per-retailer table; live PDP verification deferred (TODO retained in source)."
  - "Mirrored SquareEnix structure for shutdown() inspect.isawaitable pattern per O-3 NEGATIVE resolution."
metrics:
  duration: ~10 minutes
  completed: 2026-05-15
  tasks: 2
  files_changed: 2
requirements: [PLG-08]
---

# Phase 06 Plan 06: NewEgg Plugin Summary

Implemented `NeweggPlugin` (PLG-08): nodriver-based async retailer plugin for newegg.com with env-gated risky auto-buy and inspect.isawaitable shutdown shim.

## What Shipped

- `plugins/shopbot_plugin_newegg.py` (110 lines): `NeweggPlugin(RetailerPlugin)` with `domain_pattern=["newegg.com"]`, `name="newegg"`, `login_at_startup=False`. Reads `SHOPBOT_ENABLE_RISKY_AUTOBUY` once in `__init__` and stores on `self._riskyAutoBuyEnabled`. async `open()` awaits `uc.start` with user-agent + `--disable-blink-features=AutomationControlled`. async `check_availability(url)` uses nodriver Tab API. async `auto_buy(url, config)` short-circuits with WARNING when env gate is off; otherwise runs ATC + checkout + place-order flow respecting `config.debug.test_mode`. async `shutdown()` uses `inspect.isawaitable()` to handle both sync (real nodriver 0.50.3) and async stop() shapes.
- `tests/test_plugins_newegg.py` (294 lines): full GREEN suite (23 tests) covering ABC contract, env gate on/off, env-read-once, AST grep for `os.environ.get` confined to `__init__`, no selenium / notifier imports, parametrized domain routing, `uc.start` call, headless passthrough, UA rotation, check_availability sentinel/None/error, shutdown None/async/sync/raises paths.

## Verification Results

- `python -c "from plugins.shopbot_plugin_newegg import NeweggPlugin; from plugin_base import RetailerPlugin; assert issubclass(NeweggPlugin, RetailerPlugin)"`: OK
- `grep -c "os.environ.get" plugins/shopbot_plugin_newegg.py`: 1
- `grep "selenium" plugins/shopbot_plugin_newegg.py`: no matches
- `python -m pytest -q tests/test_plugins_newegg.py`: 23 passed
- `python -m pytest -q --ignore=tests/test_plugins_walmart.py --ignore=tests/test_plugins_target.py --ignore=tests/test_plugins_gamestop.py --ignore=tests/test_plugins_squareenix.py --ignore=tests/test_utils.py`: 319 passed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `rtk pytest` shim invokes Python 3.14 (broken nodriver site-packages)**
- Found during: Task 2 verification
- Issue: `rtk pytest tests/test_plugins_newegg.py` failed because the rtk shim resolves to Python 3.14 user-site, where `nodriver/cdp/network.py` has an encoding-corrupt comment that raises `SyntaxError` on import. The same failure reproduces on the sibling Walmart and SquareEnix test files, confirming this is a pre-existing environment issue, not introduced by this plan.
- Fix: Invoked pytest via the project venv directly with `python -m pytest`, which uses Python 3.13.13 + working nodriver. All 23 newegg tests + 296 other suite tests pass.
- Files modified: none
- Commit: n/a (workaround only; pre-existing env issue logged for deferred-items)

### Out-of-Scope Deferred

- `tests/test_utils.py` collection error: `ImportError: cannot import name 'make_tiny' from 'utils'`. Pre-existing; unrelated to this plan. Logged for future resolution.
- `rtk pytest` shim Python version mismatch: needs out-of-band rtk config to bind to project venv, not user-global Python 3.14.

## Self-Check: PASSED

- FOUND: plugins/shopbot_plugin_newegg.py
- FOUND: tests/test_plugins_newegg.py
- FOUND: commit 248e1ab
