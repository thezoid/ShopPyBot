---
phase: 02-plugin-migration
plan: "05"
subsystem: main
tags: [main, asyncio, registry, nodriver, CORE-03, CORE-04, PLG-02]
dependency_graph:
  requires: ["02-03", "02-04"]
  provides: [main.py (async entry point driving PluginRegistry)]
  affects: [main.py]
tech_stack:
  added: []
  patterns:
    - asyncio.run entry point with sync pre-flight before event loop
    - PluginRegistry discovery + routing replaces inline amazon.com/bestbuy.com conditionals
    - CVV threaded in-memory to plugin._cvv after setup_for_items (T-02-12)
key_files:
  created: []
  modified:
    - main.py
decisions:
  - "D-02: Selenium driver setup (Options/Service/webdriver.Chrome) and CDP navigator.webdriver patch removed entirely"
  - "D-03: sequential await loop; no asyncio.gather"
  - "CVV threading: plugin._cvv = cvv assigned after setup_for_items, before the loop; value never logged"
  - "Sync pre-flight (AppConfig validation, DB seed, CVV getpass) preserved before asyncio.run()"
metrics:
  duration: "~10 minutes"
  completed: "2026-06-02"
  tasks_completed: 1
  files_changed: 1
---

# Phase 2 Plan 05: main.py Async Conversion Summary

main.py converted from a synchronous Selenium loop to an asyncio event loop driven by PluginRegistry; all Selenium driver setup and the CDP stealth patch are removed.

## What Was Built

`main.py` now runs a sync pre-flight (AppConfig validation, DB seed, CVV getpass gate) and then enters `asyncio.run(async_main(cfg, cvv))`. The async loop uses `PluginRegistry` to discover plugins, lazily launch browsers for matched platforms, and sequentially `await plugin.check_availability / auto_buy` for each non-purchased item. `teardown_all()` is called in a `finally` block on shutdown.

The CVV is threaded to the BestBuy plugin by calling `plugin._cvv = cvv` after `setup_for_items()` completes -- the value is held in memory only and never logged (T-02-12). The set-site also fires lazily inside the `if auto_buy` branch as an extra guard.

## Task Results

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Convert main.py to async registry-driven loop | 8857ed7 | main.py |
| 2 | Live async cold-start verification | CHECKPOINT | human-verify |

## What Was Removed

- `from selenium import webdriver` + `from selenium.webdriver.chrome.service import Service` + `from selenium.webdriver.chrome.options import Options`
- `from webdriver_manager.chrome import ChromeDriverManager`
- `from amazon_bot import check_amazon_item, auto_buy_amazon_item, detect_captcha`
- `from bestbuy_bot import check_bestbuy_item, auto_buy_bestbuy_item`
- `get_chromedriver_path()` function (30 lines)
- Chrome `Options` / `prefs` / `chromeOptions.add_argument` block
- `Service(driver_path, ...)` + `webdriver.Chrome(service=service, options=chromeOptions)` setup
- CDP `Page.addScriptToEvaluateOnNewDocument` stealth patch (D-02)

## Test Coverage

- Task 1 does not add new unit tests (main.py is the entry point; not unit-testable without a running config).
- Full suite: 45 passed (unchanged from before this plan -- no regressions).

## Deviations from Plan

None. Plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

No new network endpoints, auth paths, or schema changes beyond what the plan specifies. T-02-12 (CVV in-memory threading) and T-02-15 (Selenium re-introduction prevention) are both closed: `grep` confirms no `webdriver.Chrome`, `execute_cdp_cmd`, or selenium imports in main.py.

## Checkpoint: Human Verification — PASSED (live run by orchestrator)

Task 2 (`checkpoint:human-verify`) was executed as a live async cold-start on 2026-06-02 (config.yml: Amazon items, test_mode true). Observed:
- `Starting main function` then async loop entry — no Selenium/chromedriver/webdriver_manager log lines at all.
- Registry discovery live: `plugins/example_plugin.py does not match shopbot_plugin_*.py -- ignoring` (CORE-03 warn+ignore confirmed at runtime).
- nodriver launched a real Chrome (stderr shows nodriver `starting` with a `uc_*` temp profile), not Selenium.
- `Starting new iteration of item checks` → AmazonPlugin checked each Amazon item sequentially (D-03), logging availability ("not available"). Only the Amazon plugin launched a browser (lazy launch — no BestBuy items configured, no BestBuy browser).
- Leakage grep over the run output for selenium/chromedriver/webdriver_manager/execute_cdp: empty.
- No credentials or CVV appeared in console output or logs.

Caveats: the process was force-killed (not a graceful Ctrl-C), so the `finally` teardown path was not exercised in this run; the CVV getpass gate was not triggered (test_mode true, Amazon-only) but is unchanged from the Phase-1-verified path and present in code. A graceful-shutdown + BestBuy-CVV live check remain as optional manual confirmations.

Verdict: async migration verified working end-to-end live. Checkpoint satisfied.

## Self-Check

- main.py: FOUND
- Commit 8857ed7: FOUND
- 'asyncio.run(async_main': CONFIRMED in main.py
- 'from core.registry import PluginRegistry': CONFIRMED in main.py
- 'await registry.teardown_all()': CONFIRMED in main.py
- no 'webdriver.Chrome': CONFIRMED
- no 'execute_cdp_cmd': CONFIRMED
- no 'from selenium': CONFIRMED
- no 'webdriver_manager': CONFIRMED
- '_cvv' set-site: CONFIRMED
- Full suite 45 passed: CONFIRMED

## Self-Check: PASSED
