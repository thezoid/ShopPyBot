---
phase: 02-plugin-migration
plan: 02
subsystem: plugin-framework
tags:
  - plugin-migration
  - amazon
  - selenium
  - python
dependency_graph:
  requires:
    - plugin_base.py (Phase 2 Plan 01: amended ABC with list[str] domain_pattern + login_at_startup)
    - driver.build_driver (Phase 1)
    - logger.writeLog (Phase 1)
    - models.update_item_purchased (legacy SQLite layer)
    - utils.play_notification_sound (legacy pygame helper)
    - config_schema.AppConfig.platforms['amazon'].credentials (Phase 1)
  provides:
    - "plugins/shopbot_plugin_amazon.py exporting AmazonPlugin(RetailerPlugin)"
    - "AmazonPlugin.domain_pattern = ['amazon.com', 'amzn.to']"
    - "AmazonPlugin.login_at_startup = True"
    - "AmazonPlugin.name = 'amazon'"
    - "AmazonPlugin.__init__ builds self.driver via build_driver (PLG-03)"
    - "AmazonPlugin.check_availability / login / auto_buy / detect_captcha"
  affects:
    - Plan 02-04 (main.py refactor): can route amazon URLs via registry to AmazonPlugin
    - Plan 02-04 (cleanup): owns deletion of amazon_bot.py (NOT this plan)
tech_stack:
  added: []
  patterns:
    - "Helper-method decomposition for >30 line legacy functions"
    - "self.driver ownership inside plugin (no module-level driver, no driver param on ABC methods)"
    - "Pydantic-instance credential access (self.platform_config.credentials.email)"
    - "sys.modules stubbing for selenium + pygame so plugin tests run without those deps"
key_files:
  created:
    - plugins/shopbot_plugin_amazon.py
    - tests/test_plugins_amazon.py
  modified: []
decisions:
  - "D-01 honored: domain_pattern is list of hostnames covering amazon.com + amzn.to"
  - "D-03 honored: login_at_startup = True (Amazon OTP runs once at startup)"
  - "auto_buy decomposed into _lookup_quantity / _purchase_flow / _select_quantity / _click_buy_now / _place_order so each method stays under 30 lines per CLAUDE.md"
  - "login decomposed into _already_signed_in / _enter_email / _enter_password / _click_signin / _handle_mfa for the same reason"
  - "Two input() prompts preserved verbatim from legacy amz_sign_in (passkey dismiss + OTP entry)"
  - "Test mode pauses preserved (input prompts before buy-now and before / instead of place-order click)"
  - "amazon_bot.py NOT deleted and main.py NOT modified: Plan 02-04 owns the hard cut to keep Wave 1 parallel-safe"
metrics:
  duration_minutes: 18
  completed_date: 2026-05-12
  task_count: 2
  file_count: 2
requirements:
  - PLG-01
  - PLG-03
---

# Phase 2 Plan 02: Amazon Plugin Migration Summary

Migrated `amazon_bot.py` (192 lines, 4 functions) into `plugins/shopbot_plugin_amazon.py` as an `AmazonPlugin(RetailerPlugin)` subclass conforming to the Phase 1 ABC and the Plan 02-01 amendments. AmazonPlugin owns its own Selenium driver (PLG-03), reads credentials from the Pydantic `platform_config` slice, and calls `update_item_purchased(url)` on a successful place-order. Legacy `amazon_bot.py` and `main.py` are intentionally untouched: Plan 02-04 owns the hard cut.

## What Shipped

**`plugins/shopbot_plugin_amazon.py` (249 lines, under 300 cap):**
- Class attributes: `domain_pattern = ["amazon.com", "amzn.to"]`, `login_at_startup = True`, `name = "amazon"`
- `__init__(platform_config, *, cvv=None, driver_path=None)` calls `super().__init__` then `build_driver(driver_path or "chromedriver.exe")` and stores the result on `self.driver`
- `detect_captcha(self) -> bool` ports the CAPTCHA XPATH check from `amazon_bot.detect_captcha`; replaces the bare `except:` with `except Exception as e` + TRACE log per CLAUDE.md no-silent-swallow rule
- `check_availability(self, url)` ports `check_amazon_item`; calls `self.detect_captcha()` inline (single call site)
- `login(self, config)` ports `amz_sign_in`; reads credentials from `self.platform_config.credentials.email/.password`; preserves both `input()` prompts (passkey dismiss line 96, OTP line 100); preserves the outer try/except return-None behavior so the polling loop is unaffected by login failure
- `auto_buy(self, url, config)` ports `auto_buy_amazon_item`; resolves quantity by scanning `config.available.items` for matching link; reads `test_mode` from `config.debug.test_mode`; calls `update_item_purchased(url)` immediately after `submitOrderButton.click()` on the success branch
- Helpers: `_handle_captcha_if_present`, `_find_button`, `_already_signed_in`, `_enter_email`, `_enter_password`, `_click_signin`, `_handle_mfa`, `_lookup_quantity`, `_purchase_flow`, `_select_quantity`, `_click_buy_now`, `_place_order` (each under 30 lines)

**`tests/test_plugins_amazon.py` (200 lines):**
- 11 tests covering: subclass relationship, `domain_pattern`, `login_at_startup`, `name`, driver ownership (sentinel via monkeypatched `build_driver`), `platform_config` storage, `check_availability` / `auto_buy` signatures, `detect_captcha` override, AST grep for `update_item_purchased` call site, anti-pattern grep for `from config import`
- Tests stub `selenium.*`, `pygame`, and the `driver` module via `sys.modules` injection so they run in environments missing those packages (Wave 0 SUMMARY flagged selenium/pygame as not installed in the worktree env)
- No real Chrome process spawned during collection or execution

## Verification

- `rtk pytest -x tests/test_plugins_amazon.py` exits 0 with 11 passed
- `rtk pytest tests/test_plugin_base.py tests/test_plugin_registry.py tests/test_plugins_amazon.py` exits 0 with 37 passed (no regression in Plan 02-01 tests)
- `rtk grep -n "from config import" plugins/shopbot_plugin_amazon.py` reports 0 matches
- `rtk grep "update_item_purchased" plugins/shopbot_plugin_amazon.py` reports 2 matches (import + call site)
- `python -c "import ast; ..."` confirms every function/method is under 30 lines (max 22 in `_select_quantity`)
- `rtk git diff --stat amazon_bot.py` reports no changes
- `rtk find plugins/__init__.py` returns nothing (package boundary preserved)

## Commits

| Hash    | Type | Description                                                            |
| ------- | ---- | ---------------------------------------------------------------------- |
| 84acd82 | test | RED tests for AmazonPlugin contract + driver ownership                 |
| dbd8d19 | feat | implement AmazonPlugin migrating amazon_bot.py logic (GREEN)           |

## Deviations from Plan

**1. [Rule 2 - Correctness] Replaced bare `except:` and `except: pass` patterns with `except Exception as e` + TRACE / WARNING log.**
- **Found during:** Task 2 (porting `amazon_bot.detect_captcha` and `_handle_mfa`).
- **Issue:** The legacy `detect_captcha` uses a bare `except:` returning False; the MFA prompt path uses a bare `except:` writing a "warning" log without context. CLAUDE.md forbids silent exception swallowing.
- **Fix:** Both sites now bind the exception and log it at TRACE (CAPTCHA absence is expected and noisy) or WARNING (MFA absence is the legacy log level). Return values preserved verbatim.
- **Files modified:** plugins/shopbot_plugin_amazon.py
- **Commit:** dbd8d19
- **Rule:** Rule 2 (CLAUDE.md hard constraint)

**2. [Rule 3 - Blocking] Test loader stubs `selenium.*` and `pygame` via `sys.modules` rather than monkeypatching `driver.build_driver` only.**
- **Found during:** Task 1 RED run.
- **Issue:** The plan's reference fixture monkeypatches `driver.build_driver`, which still requires `import driver as driver_mod` to succeed. The worktree env does not have selenium installed (called out in Plan 02-01 SUMMARY "Out-of-Scope Failures Observed"), so `driver.py` raises `ModuleNotFoundError: selenium` at import time before any monkeypatch can apply. Same problem for `utils.py` (imports pygame).
- **Fix:** The test loader injects minimal `types.ModuleType` stubs for `selenium`, `selenium.webdriver`, `selenium.webdriver.common.by`, `selenium.webdriver.support`, `selenium.webdriver.support.ui`, `selenium.webdriver.support.expected_conditions`, `pygame`, `pygame.mixer`, and the `driver` module into `sys.modules` via `monkeypatch.setitem` before loading the plugin. Selenium and pygame are still required at runtime; they are only stubbed for testing.
- **Files modified:** tests/test_plugins_amazon.py
- **Commit:** 84acd82
- **Rule:** Rule 3 (blocking environment gap)

**3. [Rule 2 - Correctness] AST test accepts `update_item_purchased` call anywhere inside `AmazonPlugin` class, not strictly inside `auto_buy`.**
- **Found during:** Task 1 RED design.
- **Issue:** The plan's `must_haves.truths` says the call must be inside `auto_buy`, but because `auto_buy` was decomposed (Deviation: helper methods) the actual call lives in `_place_order`. A strict `inside FunctionDef name=auto_buy` walk would force re-inlining and violate the 30-line cap.
- **Fix:** The AST walk targets the `AmazonPlugin` ClassDef and accepts the call in any contained method. Combined with the architectural rule that `_place_order` is only reachable from `auto_buy → _purchase_flow → _place_order`, this preserves the threat-model intent (T-2-PLG-01-DBLBUY: call site verified in code).
- **Files modified:** tests/test_plugins_amazon.py
- **Commit:** 84acd82
- **Rule:** Rule 2 (CLAUDE.md function-length constraint)

## Threat Model Coverage

| Threat ID            | Disposition | Mitigation Implemented                                                                                                  |
| -------------------- | ----------- | ----------------------------------------------------------------------------------------------------------------------- |
| T-2-PLG-01-CREDS     | mitigate    | Credentials sourced from `self.platform_config.credentials.email/.password`; no writeLog call ever emits the password   |
| T-2-PLG-01-DBLBUY    | mitigate    | `update_item_purchased(url)` is the first statement after `place_btn.click()` in `_place_order` (success branch only)   |
| T-2-PLG-03-DRIVER    | mitigate    | `__init__` calls `build_driver` (Phase 1 hardened factory); plugin never imports webdriver.Chrome directly              |
| T-2-PLG-01-CAPTCHA   | mitigate    | `_handle_captcha_if_present` calls `self.detect_captcha()`; manual `input()` pause preserved                            |
| T-2-PLG-01-RUNTIME-EX| accept      | Per-step try/except logs ERROR and returns False or None; matches legacy behavior; Plan 02-04 wraps the call site       |

## Out-of-Scope Failures Observed (Not Fixed)

Same pre-existing environment gaps Plan 02-01 documented:
- `tests/test_utils.py`, `tests/test_driver_setup.py`, `tests/test_models.py` still fail collection or assertions because `selenium`, `pygame`, and the `data/` directory are absent from this worktree's Python environment.

These are inherited environment issues, not regressions from this plan. The plan-scoped suite (`tests/test_plugin_base.py tests/test_plugin_registry.py tests/test_plugins_amazon.py`) is fully green at 37 passed.

## TDD Gate Compliance

- RED gate satisfied: commit 84acd82 (`test(02-02)`) introduces 11 failing tests before any implementation exists (FileNotFoundError on the plugin path).
- GREEN gate satisfied: commit dbd8d19 (`feat(02-02)`) makes all 11 tests pass with the plugin implementation.
- REFACTOR gate: no separate refactor commit; helper decomposition was applied inline during GREEN to satisfy the CLAUDE.md 30-line cap.

## Self-Check: PASSED

Created files verified:
- plugins/shopbot_plugin_amazon.py: FOUND (249 lines)
- tests/test_plugins_amazon.py: FOUND (200 lines)

Untouched files verified (per plan boundary):
- amazon_bot.py: UNCHANGED (no diff vs HEAD~2)
- main.py: UNCHANGED
- plugin_base.py: UNCHANGED (Plan 02-01 owned the amendment)
- plugin_registry.py: UNCHANGED

Commits verified:
- 84acd82: FOUND in git log (test RED)
- dbd8d19: FOUND in git log (feat GREEN)
