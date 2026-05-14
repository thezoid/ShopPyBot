---
phase: 04-async-orchestrator
plan: 03
subsystem: plugin-contract
tags: [python, abc, asyncio, shutdown, plugin-contract]
requires:
  - plugin_base.RetailerPlugin (Phase 1 D-01, Phase 2 D-03)
  - logger.writeLog
provides:
  - RetailerPlugin.shutdown async default (D-04)
  - tests/test_plugin_shutdown.py GREEN
affects:
  - Plan 04-05 orchestrator finally-block can now await plugin.shutdown()
tech-stack:
  added: [asyncio.to_thread for blocking driver.quit]
  patterns: [non-abstract default with getattr guard, exception-swallow + WARNING log]
key-files:
  created: []
  modified:
    - plugin_base.py
    - tests/test_plugin_shutdown.py
    - tests/test_plugin_base.py
decisions:
  - D-04 implemented as non-abstract async default so existing Amazon and BestBuy plugins inherit unchanged
  - PLUGIN_API_VERSION stays at 1 (additive change, non-breaking)
metrics:
  duration: ~10min
  completed: 2026-05-14
  tasks: 2
  files: 3
---

# Phase 4 Plan 03: Plugin ABC Async Shutdown Summary

One-liner: Added non-abstract `async def shutdown` default to RetailerPlugin that awaits `asyncio.to_thread(self.driver.quit)` with a `getattr` driver guard and exception swallow, unblocking the Plan 04-05 orchestrator finally-block cleanup.

## What Changed

- `plugin_base.py`: added `import asyncio`, `from logger import writeLog`, and an `async def shutdown(self) -> None` concrete method. Default body uses `getattr(self, "driver", None)` to no-op when the driver is unset, then `await asyncio.to_thread(driver.quit)` wrapped in try/except that logs at WARNING and swallows. PLUGIN_API_VERSION still equals 1.
- `tests/test_plugin_shutdown.py`: replaced the Plan 04-01 RED skeleton with five GREEN tests: coroutine assertion, default driver.quit via to_thread, no-driver no-op, exception swallow, and subclass-overrides-and-calls-super.
- `tests/test_plugin_base.py`: appended one new test `test_shutdownIsAsyncCoroutineFunction`. Existing 8 tests unchanged.
- Amazon and BestBuy plugin source files (`plugins/shopbot_plugin_amazon.py`, `plugins/shopbot_plugin_bestbuy.py`) were NOT modified. Both inherit the default shutdown (verified via grep: zero `def shutdown` matches under `plugins/`).

## Tasks and Commits

| Task | Name | Commit |
|------|------|--------|
| 1 | Add async shutdown default to RetailerPlugin ABC | 0b03721 |
| 2 | Flip test_plugin_shutdown.py to GREEN; extend test_plugin_base.py | a10684a |

## Verification

- `python -c "from plugin_base import RetailerPlugin, PLUGIN_API_VERSION; import inspect; assert PLUGIN_API_VERSION == 1; assert inspect.iscoroutinefunction(RetailerPlugin.shutdown)"` exits 0
- `python -m pytest tests/test_plugin_shutdown.py tests/test_plugin_base.py -v` shows 14 passed (5 shutdown + 9 plugin_base)
- `grep "def shutdown\|async def shutdown" plugins/` returns 0 matches
- Full suite (excluding pre-existing Plan 04-01 RED skeletons for orchestrator/purchase_writer/registry_stagger/utils): 178 passed, no regressions

## Deviations from Plan

None. Plan executed exactly as written.

## Threat Mitigations Confirmed

- T-04-03-SYNC-OVERRIDE: covered by `test_shutdownIsAsyncCoroutineFunction` and `test_shutdownIsCoroutineFunction`
- T-04-03-QUIT-HANG: mitigation in place via `asyncio.to_thread`; bounded shutdown deferred to Plan 04-05 outer timeout
- T-04-03-EXC-PROPAGATION: covered by `test_shutdownSwallowsDriverQuitException`
- T-04-03-MISSING-DRIVER: covered by `test_shutdownNoDriverAttribute`
- T-04-03-API-VERSION-BUMP: `test_api_version_is_one` already asserts PLUGIN_API_VERSION == 1

## Known Stubs

None.

## Self-Check: PASSED

- plugin_base.py: FOUND, contains `async def shutdown`, `asyncio.to_thread`, `PLUGIN_API_VERSION: int = 1`
- tests/test_plugin_shutdown.py: FOUND, 5 GREEN tests
- tests/test_plugin_base.py: FOUND, +1 new test
- Commit 0b03721: FOUND
- Commit a10684a: FOUND
- plugins/ shutdown overrides: NONE (correct)
