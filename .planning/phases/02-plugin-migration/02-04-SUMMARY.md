---
phase: 02-plugin-migration
plan: "04"
subsystem: plugins
tags: [amazon, bestbuy, nodriver, PLG-01, PLG-02, PLG-03, async]
dependency_graph:
  requires: ["02-02"]
  provides: [plugins/shopbot_plugin_amazon.py, plugins/shopbot_plugin_bestbuy.py]
  affects: [main.py (Plan 05 wires registry), tests/]
tech_stack:
  added: []
  patterns:
    - nodriver async Browser per plugin (D-04)
    - spec_from_file_location plugin loading (mirrors registry)
    - AsyncMock-driven unit tests with fake_browser fixture
key_files:
  created:
    - plugins/shopbot_plugin_amazon.py
    - plugins/shopbot_plugin_bestbuy.py
    - tests/test_plugin_amazon.py
    - tests/test_plugin_bestbuy.py
decisions:
  - "PLG-02: update_item_purchased(url) placed immediately after place-order success log in BestBuyPlugin.auto_buy"
  - "PLG-03: self.driver = None in __init__; nodriver.start() awaited in setup() per D-06"
  - "SEC-01: AMZ_EMAIL/AMZ_PASSWORD and BB_EMAIL/BB_PASSWORD read from os.environ only; never logged"
  - "_cvv threading contract: BestBuyPlugin.__init__ sets self._cvv = None; main.py (Plan 05) assigns plugin._cvv = cvv after setup_for_items()"
  - "Open Question 1 (current_url guard): skipped -- always navigate with driver.get(url)"
  - "Open Question 2 (BestBuy .a-dropdown-prompt): ported as-is with TODO comment for live verification"
metrics:
  duration: "~20 minutes"
  completed: "2026-06-02"
  tasks_completed: 2
  files_changed: 4
---

# Phase 2 Plan 04: Amazon + BestBuy nodriver Plugins Summary

Wave 2 delivers both platform plugins as nodriver async RetailerPlugin subclasses with full unit test coverage and the PLG-02 bug fix.

## What Was Built

AmazonPlugin and BestBuyPlugin each own an isolated nodriver Browser process (PLG-03) started in `async setup()`. All Selenium DOM operations are replaced with `tab.select`/`tab.find` with None-guards (RESEARCH Pitfall 2). No selenium imports remain in either plugin.

The PLG-02 bug (BestBuy repurchase on every loop iteration) is fixed: `update_item_purchased(url)` is now called immediately after the "Order placed on BestBuy" log, before `return True`.

## Task Results

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Port AmazonPlugin + tests | d3fa0df | plugins/shopbot_plugin_amazon.py, tests/test_plugin_amazon.py |
| 2 | Port BestBuyPlugin + PLG-02 fix + tests | 3833b50 | plugins/shopbot_plugin_bestbuy.py, tests/test_plugin_bestbuy.py |

## Test Coverage

- 9 tests for AmazonPlugin: ABC satisfaction, domain_patterns, no global driver, check_availability (True/False/bool type/never raises), detect_captcha (True/False)
- 9 tests for BestBuyPlugin: ABC satisfaction, domain_patterns, no global driver, _cvv default, check_availability (True/False/bool type/never raises), test_autobuy_calls_update_purchased (PLG-02)
- Full suite: 43 passed (was 25 before this plan)

## _cvv Threading Contract for Plan 05

BestBuyPlugin sets `self._cvv = None` in `__init__`. After `await registry.setup_for_items(items)`, main.py must locate the BestBuy plugin instance and assign its CVV:

```python
# In main.py async_main(), after setup_for_items:
if cvv:
    bb_plugin = registry.route("https://www.bestbuy.com/")
    if bb_plugin:
        bb_plugin._cvv = cvv
```

The CVV is collected via `getpass` before `asyncio.run()` (SEC-02; already the Phase-1 pattern). It is never logged or written to disk.

## Deviations from Plan

None. Plan executed exactly as written.

## Known Stubs

None. Both plugins wire real logic from the source bots. The `.a-dropdown-prompt` selector for BestBuy cart quantity has a TODO comment (Open Question 2 from RESEARCH) but the selector is the one validated in Phase-1 UAT -- it is not a stub, just flagged for live re-verification.

## Threat Flags

No new network endpoints, auth paths, or schema changes beyond what the plan specifies. All credentials remain env-var-only (T-02-08 closed). nodriver handles stealth architecturally (T-02-09 closed). Every tab.select result is None-guarded (T-02-10 closed).

## Self-Check

- plugins/shopbot_plugin_amazon.py: FOUND
- plugins/shopbot_plugin_bestbuy.py: FOUND
- tests/test_plugin_amazon.py: FOUND
- tests/test_plugin_bestbuy.py: FOUND
- Commit d3fa0df: FOUND
- Commit 3833b50: FOUND
- Full suite 43 passed: CONFIRMED

## Self-Check: PASSED
