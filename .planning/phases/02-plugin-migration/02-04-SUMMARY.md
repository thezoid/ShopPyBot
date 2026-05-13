---
phase: 02-plugin-migration
plan: 04
subsystem: integration
tags: [integration, main, hard-cut, python, plugin-registry]
requirements_completed: [CORE-03, CORE-04, PLG-01, PLG-02]
dependency_graph:
  requires:
    - 02-01 (plugin_registry discover/route_url/verify_coverage)
    - 02-02 (AmazonPlugin)
    - 02-03 (BestBuyPlugin)
  provides:
    - "main.py driven entirely by the plugin registry"
    - "Zero references to amazon_bot or bestbuy_bot anywhere in source"
  affects:
    - main.py
    - amazon_bot.py (deleted)
    - bestbuy_bot.py (deleted)
    - tests/test_main_smoke.py
tech_stack:
  added: []
  patterns:
    - "Plugin-registry dispatch (discover -> verify_coverage -> route_url)"
    - "Per-iteration try/except isolation around plugin calls (T-2-CORE-03-LOOP)"
    - "Startup login loop iterating registry plugins with login_at_startup=True (D-03)"
key_files:
  created:
    - .planning/phases/02-plugin-migration/deferred-items.md
  modified:
    - main.py
    - tests/test_main_smoke.py
  deleted:
    - amazon_bot.py
    - bestbuy_bot.py
decisions:
  - "D-02 hard cut executed: legacy bots removed via git rm; no _deprecated fallback"
  - "Extracted _seed_items and _poll_loop helpers to keep main() at 22 lines (CLAUDE.md 30-line cap)"
  - "play_notification_sound import dropped (orphaned after _handle_amazon removal); function remains in utils.py for any future caller"
metrics:
  tasks: 2
  files_modified: 4
  commits:
    - 3591629 test(02-04) RED smoke tests for plugin registry integration and legacy hard cut
    - 336d315 feat(02-04) route polling via plugin registry; hard-cut amazon_bot.py and bestbuy_bot.py
  smoke_tests_added: 10
  smoke_tests_total: 17
  completed_date: 2026-05-12
---

# Phase 2 Plan 04: Main Integration and Legacy Cut Summary

Atomically swapped main.py to drive the polling loop via the plugin registry and deleted the legacy amazon_bot.py and bestbuy_bot.py modules per D-02. After this plan, the bot has zero direct knowledge of Amazon or BestBuy: everything routes through plugin_registry.discover, verify_coverage, and route_url.

## What Shipped

* **main.py rewritten** to call `discover(Path("plugins"), app_config=app_config, cvvs=cvvs)`, then `verify_coverage(registry, app_config.available.items)`, then the D-03 startup login loop (`for plugin in registry: if plugin.login_at_startup: plugin.login(app_config)`), then the poll loop dispatching each item via `route_url(link, registry)`.
* **_poll_one helper** wraps `plugin.check_availability` and `plugin.auto_buy` in try/except, logs ERROR and continues. This is the runtime isolation called out in T-2-CORE-03-LOOP: a single-URL DOM failure or driver crash cannot crash the polling loop.
* **_seed_items + _poll_loop helpers** added so `main()` stays at 22 lines (under CLAUDE.md 30-line cap). Every function in main.py is now under 30 lines.
* **amazon_bot.py and bestbuy_bot.py deleted** via `git rm` (D-02 hard cut, no `_deprecated/` preservation).
* **tests/test_main_smoke.py extended** with 10 new tests covering AST assertions on registry calls, login_at_startup wiring, absence of legacy helpers, and filesystem-level removal of the legacy modules.

## Verification

* `rtk pytest -x -q tests/test_main_smoke.py`: 17 passed (10 new + 7 Phase 1 invariants retained)
* `python -c "import ast; ast.parse(open('main.py').read())"`: exits 0
* `rg "from amazon_bot|from bestbuy_bot|amazon.com..in link|bestbuy.com..in link" main.py`: 0 matches
* `rg "plugin_registry|route_url|verify_coverage|discover" main.py`: 5 matches across import, discover call, verify_coverage call, and route_url call inside `_poll_loop`
* `git status` confirms amazon_bot.py and bestbuy_bot.py staged as deleted
* Full suite outside the pre-existing broken files: 116 passed

## Function Size Audit

| Function | Lines | Cap | Status |
|----------|-------|-----|--------|
| get_chromedriver_path | 13 | 30 | ok |
| make_tiny | 4 | 30 | ok |
| _poll_one | 27 | 30 | ok |
| _seed_items | 6 | 30 | ok |
| _poll_loop | 14 | 30 | ok |
| main | 22 | 30 | ok |

main.py total: 121 lines (under 300-line cap).

## Deviations from Plan

### Test scope adjustment

The Phase 1 test `test_imports_build_driver` (asserting `from driver import build_driver` in main.py) was removed because Plan 02-04 explicitly removes the top-level `build_driver` call: each plugin now constructs its own driver via `__init__` per PLG-03. The Phase 1 invariant no longer holds and the plan's `<interfaces>` section locks this in. The Phase 1 test `test_no_old_app_credential_reads` was tightened to scan only `main.py` since `amazon_bot.py` and `bestbuy_bot.py` no longer exist.

Both adjustments are Rule 3 (auto-fix blocking issues): the legacy tests would have failed against the deliberate post-cut state, blocking the GREEN gate.

### Auto-fixed: main() exceeded 30-line cap

After the first cut of the rewrite, `main()` measured 40 lines, exceeding the CLAUDE.md function-size constraint that the plan's acceptance criteria explicitly cite. Rule 1 (auto-fix bug: violated constraint): extracted `_seed_items` and `_poll_loop` helpers, bringing `main()` to 22 lines.

### Deferred (out of scope)

See `.planning/phases/02-plugin-migration/deferred-items.md` for two pre-existing broken tests (`tests/test_utils.py` and `tests/test_models.py`) introduced in commit `0177274`, before Phase 1. These were not touched. They block running pytest without `--ignore` flags but are not regressions from this plan.

## Requirements Closed

* **CORE-03** (plugin discovery wired through main.py): satisfied. `discover` called once at startup; lenient-on-import behavior reaches the polling loop.
* **CORE-04** (URL routing replaces hardcoded dispatch): satisfied. `route_url` replaces the `if "amazon.com" in link` chain.
* **PLG-01** (Amazon plugin live, legacy module deleted): finalized. `amazon_bot.py` removed; Amazon URLs route through `AmazonPlugin`.
* **PLG-02** (BestBuy plugin live, legacy module deleted): finalized. `bestbuy_bot.py` removed; BestBuy URLs route through `BestBuyPlugin` with the PLG-02 fix from Plan 03 now live.

D-02 hard cut complete. D-03 wiring live.

## TDD Gate Compliance

* RED gate: commit `3591629` (test commit, 10 failing assertions verified)
* GREEN gate: commit `336d315` (feat commit, all 17 smoke tests passing)

Both gates present in git log in the correct order.

## Self-Check: PASSED

Files claimed to be created or modified:
* main.py: FOUND
* tests/test_main_smoke.py: FOUND
* .planning/phases/02-plugin-migration/deferred-items.md: FOUND
* amazon_bot.py: MISSING (intentional, per D-02 hard cut)
* bestbuy_bot.py: MISSING (intentional, per D-02 hard cut)

Commits claimed:
* 3591629: FOUND
* 336d315: FOUND
