---
phase: 02-plugin-migration
plan: 03
subsystem: plugin-framework
tags:
  - plugin-migration
  - bestbuy
  - selenium
  - python
dependency_graph:
  requires:
    - plugin_base.py (Phase 2 Plan 01 amended ABC)
    - driver.build_driver (Phase 1)
    - logger.writeLog (Phase 1)
    - models.update_item_purchased (legacy SQLite layer)
    - config_schema.AppConfig.platforms['bestbuy'].credentials (Phase 1)
  provides:
    - "plugins/shopbot_plugin_bestbuy.py exporting BestBuyPlugin(RetailerPlugin)"
    - "BestBuyPlugin.domain_pattern = ['bestbuy.com']"
    - "BestBuyPlugin.login_at_startup = True"
    - "BestBuyPlugin.name = 'bestbuy'"
    - "BestBuyPlugin.__init__ builds self.driver via build_driver (PLG-03)"
    - "BestBuyPlugin.check_availability / login / auto_buy"
    - "PLG-02 fix: update_item_purchased(url) called after successful place-order"
  affects:
    - Plan 02-04 (main.py refactor): can route bestbuy URLs via registry to BestBuyPlugin
    - Plan 02-04 (cleanup): owns deletion of bestbuy_bot.py (NOT this plan)
tech_stack:
  added: []
  patterns:
    - "Helper-method decomposition for auto_buy (each method under 30 lines)"
    - "self.driver ownership inside plugin (no driver param on ABC methods)"
    - "Pydantic-instance credential access (self.platform_config.credentials.email)"
    - "sys.modules stubbing for selenium so plugin tests run without selenium installed"
    - "detect_captcha intentionally NOT overridden (BestBuy has no CAPTCHA flow today)"
key_files:
  created:
    - plugins/shopbot_plugin_bestbuy.py
    - tests/test_plugins_bestbuy.py
  modified: []
decisions:
  - "D-01 honored: domain_pattern = ['bestbuy.com'] (single hostname)"
  - "D-03 honored: login_at_startup = True (deliberate behavior change from legacy mid-flow-only sign-in)"
  - "Mid-flow self.login(config) call preserved inside auto_buy as no-op-if-signed-in safety net (parity with bestbuy_bot.py:65 until Phase 3+ refactors session handling)"
  - "PLG-02 fix: update_item_purchased(url) called inside _place_order on the success branch only (test_mode short-circuit returns False before the call)"
  - "auto_buy decomposed into _lookup_quantity / _add_to_cart / _set_cart_quantity / _proceed_to_checkout / _enter_cvv / _place_order to keep every method under 30 lines"
  - "detect_captcha NOT overridden: inherits no-op default from RetailerPlugin per RESEARCH Q4 (no CAPTCHA flow exists in legacy bestbuy_bot.py)"
  - "self.cvv or '' fallback in _enter_cvv: prevents send_keys(None) crash if CVV was never collected"
  - "bestbuy_bot.py NOT deleted and main.py NOT modified: Plan 02-04 owns the hard cut to keep Wave 1 parallel-safe"
metrics:
  duration_minutes: 6
  completed_date: 2026-05-12
  task_count: 2
  file_count: 2
requirements:
  - PLG-02
  - PLG-03
---

# Phase 2 Plan 03: BestBuy Plugin Migration Summary

Migrated `bestbuy_bot.py` (73 lines, 3 functions) into `plugins/shopbot_plugin_bestbuy.py` as a `BestBuyPlugin(RetailerPlugin)` subclass, AND fixed the longstanding PLG-02 bug where `update_item_purchased(url)` was never called after a successful BestBuy purchase (allowing the bot to re-buy the same item every polling cycle). The new plugin owns its own Selenium driver (PLG-03), reads credentials from the Pydantic `platform_config` slice, and inherits the no-op `detect_captcha` default. Legacy `bestbuy_bot.py` and `main.py` are intentionally untouched: Plan 02-04 owns the hard cut.

## What Shipped

`plugins/shopbot_plugin_bestbuy.py` (148 lines, well under 300 cap):
- Class attributes: `domain_pattern = ["bestbuy.com"]`, `login_at_startup = True`, `name = "bestbuy"`
- `__init__(platform_config, *, cvv=None, driver_path=None)` calls `super().__init__` then `build_driver(driver_path or "chromedriver.exe")` and stores the result on `self.driver`
- `check_availability(self, url)` ports `check_bestbuy_item` (CLASS_NAME `add-to-cart-button` presence with 10s WebDriverWait)
- `login(self, config)` ports `bb_sign_in`; reads credentials from `self.platform_config.credentials.email/.password`; outer try/except logs ERROR on failure to preserve polling-loop resilience
- `auto_buy(self, url, config)` ports `auto_buy_bestbuy_item`; preserves the chain: add-to-cart, cart, quantity dropdown, checkout, mid-flow `self.login(config)`, CVV entry, place-order; calls `update_item_purchased(url)` after the place-order click (PLG-02 fix)
- Helpers: `_lookup_quantity`, `_add_to_cart`, `_set_cart_quantity`, `_proceed_to_checkout`, `_enter_cvv`, `_place_order` (each under 30 lines, max 12 lines)
- `detect_captcha` is NOT overridden: inherits no-op default returning False
- Module constants: `SIGNIN_URL`, `CART_URL` (extracted from inline strings for readability)

`tests/test_plugins_bestbuy.py` (208 lines):
- 12 tests covering: subclass relationship, `domain_pattern`, `login_at_startup`, `name`, driver ownership (sentinel via monkeypatched `build_driver`), `check_availability` / `auto_buy` signatures, `detect_captcha` NOT overridden (inheritance check), AST grep for PLG-02 fix, AST walk asserting `login` reads `self.platform_config.credentials.email/.password`, anti-pattern grep for `from config import`, AST guard against legacy positional credential parameters
- Tests stub `selenium.*` and the `driver` module via `sys.modules` injection so they run without selenium installed (same recipe Plan 02-02 used)
- No real Chrome process spawned during collection or execution

## Verification

- `rtk pytest -x tests/test_plugins_bestbuy.py` exits 0 with 12 passed
- `rtk pytest tests/test_plugin_base.py tests/test_plugin_registry.py tests/test_plugins_amazon.py tests/test_plugins_bestbuy.py` exits 0 with 49 passed (no regression in Plans 02-01 / 02-02)
- `rtk grep "from config import" plugins/shopbot_plugin_bestbuy.py` reports 0 matches
- `rtk grep "update_item_purchased" plugins/shopbot_plugin_bestbuy.py` reports 4 matches (docstring x2, import, call site)
- AST check confirms `detect_captcha` is NOT defined on the class (inherits from RetailerPlugin)
- `rtk git diff --stat bestbuy_bot.py main.py` reports no changes

## Commits

| Hash    | Type | Description                                                       |
| ------- | ---- | ----------------------------------------------------------------- |
| 9b717c5 | test | RED tests for BestBuyPlugin contract + PLG-02 fix                 |
| 574fb1c | feat | implement BestBuyPlugin with PLG-02 update_item_purchased fix     |

## Deviations from Plan

1. [Rule 3 - Blocking] Test loader stubs `selenium.*` and the `driver` module via `sys.modules` rather than only monkeypatching `driver.build_driver`.
- Found during: Task 1 RED design (carried forward from Plan 02-02 deviation 2).
- Issue: The plan's reference fixture monkeypatches `driver.build_driver`, which still requires successfully importing `driver` first. The worktree env has selenium installed but driver.py top-level imports remain noisy; matching the Plan 02-02 stub recipe keeps Bestbuy tests environment-symmetric with Amazon tests.
- Fix: `_install_selenium_stubs` + `_install_driver_stub` inject minimal `types.ModuleType` entries into `sys.modules` via `monkeypatch.setitem` before loading the plugin.
- Files modified: tests/test_plugins_bestbuy.py
- Commit: 9b717c5
- Rule: Rule 3 (blocking environment gap, plus parity with Plan 02-02)

2. [Rule 2 - Correctness] AST PLG-02 test accepts `update_item_purchased` call anywhere inside `BestBuyPlugin` class, not strictly inside `auto_buy`.
- Found during: Task 1 RED design.
- Issue: The plan `must_haves.truths` says the call must be inside `auto_buy`, but to keep `auto_buy` under the 30-line CLAUDE.md cap the actual call site is in `_place_order`. A strict "inside FunctionDef name=auto_buy" walk would force re-inlining.
- Fix: AST walk targets the `BestBuyPlugin` ClassDef and accepts the call in any contained method. `_place_order` is only reachable from `auto_buy`, so threat-model intent (T-2-PLG-02-DBLBUY) is preserved.
- Files modified: tests/test_plugins_bestbuy.py
- Commit: 9b717c5
- Rule: Rule 2 (CLAUDE.md function-length constraint)

## Threat Model Coverage

| Threat ID            | Disposition | Mitigation Implemented                                                                                                  |
| -------------------- | ----------- | ----------------------------------------------------------------------------------------------------------------------- |
| T-2-PLG-02-DBLBUY    | mitigate    | `update_item_purchased(url)` is the first statement after `place_btn.click()` in `_place_order` (success branch only). AST test asserts the call exists |
| T-2-PLG-02-CVV       | mitigate    | `self.cvv` read from runtime getpass; never logged. `self.cvv or ""` fallback prevents `.send_keys(None)` crash         |
| T-2-PLG-02-CREDS     | mitigate    | Credentials read from `self.platform_config.credentials.email/.password`, never positional, never logged                |
| T-2-PLG-03-DRIVER    | mitigate    | `__init__` calls `build_driver` (Phase 1 hardened factory); plugin never imports webdriver.Chrome directly              |
| T-2-PLG-02-TESTMODE  | mitigate    | `_place_order` short-circuits in test_mode BEFORE the place-order click AND returns False, so `update_item_purchased` is never reached in test_mode |

## Out-of-Scope Failures Observed (Not Fixed)

None observed in plan-scoped suite (49 passed). Pre-existing environment gaps in unrelated test files (per Plan 02-01 / 02-02 SUMMARYs) were not investigated this plan.

## TDD Gate Compliance

- RED gate satisfied: commit 9b717c5 (`test(02-03)`) introduces 12 failing tests before any implementation exists (FileNotFoundError on the plugin path).
- GREEN gate satisfied: commit 574fb1c (`feat(02-03)`) makes all 12 tests pass with the plugin implementation.
- REFACTOR gate: no separate refactor commit needed; helper decomposition was applied inline during GREEN to satisfy CLAUDE.md 30-line cap.

## Self-Check: PASSED

Created files verified:
- plugins/shopbot_plugin_bestbuy.py: FOUND (148 lines)
- tests/test_plugins_bestbuy.py: FOUND (208 lines)

Untouched files verified (per plan boundary):
- bestbuy_bot.py: UNCHANGED (no diff vs HEAD~2)
- main.py: UNCHANGED
- plugin_base.py: UNCHANGED
- plugin_registry.py: UNCHANGED

Commits verified:
- 9b717c5: FOUND in git log (test RED)
- 574fb1c: FOUND in git log (feat GREEN)
