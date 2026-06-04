---
phase: 07-modular-core-service
plan: "03"
subsystem: main-shim
tags: [shim, BotService, delegation, wiring, MOD-02, MOD-03]
dependency_graph:
  requires: ["07-01", "07-02"]
  provides: ["main.py thin shim", "BotService delegation seam"]
  affects: ["main.py", "tests/test_main_wiring.py"]
tech_stack:
  added: []
  patterns: ["thin-shim", "front-end collects secrets, service receives params"]
key_files:
  created: []
  modified:
    - main.py
    - tests/test_main_wiring.py
decisions:
  - "main.py keeps getpass CVV collection in the front-end; BotService.run(cvv) receives it as a parameter"
  - "asyncio.run and async_main imports removed from main.py; run path now internal to core/service.py"
  - "test_main_wiring.py: delegation seam tests rewritten from main->async_main to main->BotService; CVV gate tests repointed, intent preserved"
metrics:
  duration_minutes: 5
  completed: "2026-06-04T03:25:35Z"
  tasks_completed: 2
  files_changed: 2
---

# Phase 07 Plan 03: Main.py BotService Shim Summary

main.py converted to a thin shim delegating the run path to BotService(cfg).run(cvv), preserving AppConfig validation, DB seed, and getpass CVV gate unchanged.

## What Was Built

**Task 1: Slim main.py into BotService-delegating shim (f51ccf1)**
- Replaced `from core.orchestrator import async_main` with `from core.service import BotService`
- Removed `import asyncio` (no longer needed; asyncio is internal to core/service.py)
- Replaced `asyncio.run(async_main(cfg, cvv))` with `BotService(cfg).run(cvv)`
- Pre-flight order preserved exactly: AppConfig validation -> initialize_db + add_items -> CVV gate -> BotService.run(cvv)
- collect_cvv() with getpass remains in main.py unchanged (SEC-02)

**Task 2: Update test_main_wiring.py to assert BotService delegation (d4eaa16)**
- Replaced `test_main_async_main_is_orchestrator` with `test_main_botservice_is_core_service` (asserts main.BotService is core.service.BotService)
- Replaced `test_main_calls_asyncio_run` with `test_main_delegates_to_botservice_run` (patches main.BotService, asserts run(cvv) called)
- Repointed CVV-gate tests: removed patches of main.async_main / main.asyncio.run, added patch.object(main_module, "BotService"); all CVV gate assertions preserved
- test_cvv_collected_when_needed now also asserts the collected CVV ("123") is forwarded to run()
- test_invalid_config_exits_with_1 kept verbatim (no run-path patches in that test)

## Test Results

- tests/test_main_wiring.py: 6/6 passed
- Full suite: 227 passed, 1 pre-existing warning (unrelated coroutine warning in test_plugin_amazon.py)
- Only test_main_wiring.py modified among existing test files

## Deviations from Plan

**1. [CHECKER_CORRECTION] All 5 run-path patches updated, not just 2**
- Found during: Pre-execution analysis
- Issue: 3 CVV-gate tests also patched main.async_main/main.asyncio.run; plan summary said "2 delegation tests" but checker correction required all 5
- Fix: Repointed all 5 tests; CVV gate intent fully preserved; coverage not weakened
- Files modified: tests/test_main_wiring.py
- Commit: d4eaa16

None otherwise - plan executed as written with the checker correction applied.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. CVV stays in getpass (hidden, not logged). No new trust boundaries added.

## Self-Check: PASSED

- main.py: exists, contains BotService, no async_main, no asyncio.run
- tests/test_main_wiring.py: exists, 6 tests, all pass
- Commits f51ccf1 and d4eaa16: verified in git log
