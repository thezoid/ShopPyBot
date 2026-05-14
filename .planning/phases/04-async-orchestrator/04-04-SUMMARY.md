---
phase: 04-async-orchestrator
plan: 04
subsystem: plugin-registry
tags:
  - python
  - asyncio
  - plugin-registry
  - stagger
  - discovery
requires:
  - plugin_registry.discover (Phase 2)
  - asyncio (stdlib)
provides:
  - plugin_registry.discover_async
  - plugin_registry.DEFAULT_STAGGER_SECONDS
  - plugin_registry._iter_plugin_paths
  - plugin_registry._load_and_instantiate
affects:
  - main.py (Plan 04-05 will switch to discover_async)
tech-stack:
  patterns:
    - asyncio.sleep before driver construction (Pitfall 7)
    - asyncio.to_thread offload for blocking Selenium init
    - shared helper extraction (sync + async share _iter_plugin_paths and _load_and_instantiate)
key-files:
  modified:
    - plugin_registry.py
    - tests/test_registry_stagger.py
decisions:
  - Sleep happens BEFORE each plugin past the first, never after; locks in Pitfall 7
  - Per path-iteration sleep contract (failed loads still trigger stagger for next)
  - Sync discover() preserved for backwards compat; Plan 04-05 switches main.py
metrics:
  duration: 7m
  completed: 2026-05-14
requirements:
  - ASYNC-02
---

# Phase 04 Plan 04: registry-discover-async-stagger Summary

Added `async def discover_async()` to plugin_registry.py with a 1.5s `asyncio.sleep` that fires BEFORE each successive plugin's instantiation, satisfying ASYNC-02 and CONTEXT Pitfall 7 (sleep straddles the chromedriver TCP bind window, not the post-construction quiet period). Sync `discover()` and its 11 existing tests remain bit-identical via shared helpers.

## What Was Built

**plugin_registry.py changes:**
- Added `import asyncio` and `DEFAULT_STAGGER_SECONDS: float = 1.5` constant.
- Extracted two helpers from the old sync `discover` body:
  - `_iter_plugin_paths(plugins_dir)`: generator that yields sorted plugin paths, logging+skipping non-conforming names.
  - `_load_and_instantiate(path, app_config, cvvs)`: load + class-find + instantiate; returns instance or None; logs WARNING on either failure (D-04 Phase A).
- Refactored sync `discover()` to call the two helpers in a tiny loop. Public signature and observable behavior unchanged. All 11 existing tests still green.
- Added `discover_async(plugins_dir, *, app_config, cvvs, stagger_seconds=DEFAULT_STAGGER_SECONDS)`. Each iteration past the first awaits `asyncio.sleep(stagger_seconds)` BEFORE calling `_load_and_instantiate`. The instantiate call runs via `asyncio.to_thread(...)` because plugin `__init__` invokes blocking Selenium driver construction.

**tests/test_registry_stagger.py changes:**
- Replaced the Wave 0 RED skeleton (2 failing tests) with 4 GREEN tests:
  - `test_staggerBetweenTwoPlugins`: two plugins yield exactly one 1.5s sleep recorded.
  - `test_firstPluginNoSleep`: single plugin yields zero sleeps.
  - `test_staggerOverride`: `stagger_seconds=0.25` threaded through; three plugins yield two 0.25 sleeps.
  - `test_failedInstantiationStillStaggersNext`: a broken plugin between two valid ones still produces two stagger sleeps (locks in the per-path-iteration contract).
- `fakeAsyncSleep` fixture monkeypatches `plugin_registry.asyncio.sleep` specifically (not global `asyncio.sleep`) to avoid affecting pytest-asyncio internals.

## Verification

| Check | Result |
|-------|--------|
| `python -c "from plugin_registry import discover_async, DEFAULT_STAGGER_SECONDS; ..."` | OK (coroutine function; constant 1.5) |
| `pytest tests/test_plugin_registry.py` | 18 passed (sync discover regression-free) |
| `pytest tests/test_registry_stagger.py` | 4 passed (all GREEN) |
| Full suite minus pre-existing Wave 0 RED skeletons (test_orchestrator, test_purchase_writer, test_utils, test_models_wal, test_plugin_shutdown) | 172 passed |
| plugin_registry.py line count | 199 (under 300) |
| Longest function (discover_async) | 16 lines (under 30) |

## Commits

| Hash | Type | Description |
|------|------|-------------|
| 97263e5 | feat | add discover_async with 1.5s pre-instantiation stagger |
| ffca54b | test | GREEN stagger tests for discover_async (ASYNC-02) |

## Deviations from Plan

None. Plan executed exactly as written.

The pre-existing collection errors in `tests/test_orchestrator.py`, `tests/test_purchase_writer.py`, `tests/test_utils.py`, `tests/test_models_wal.py`, and `tests/test_plugin_shutdown.py` are RED skeletons left by other Wave 0 plans for Plans 04-02 / 04-03 / 04-05 to turn GREEN. They are out of scope for 04-04 and were intentionally ignored during verification.

## Threat Mitigations Applied

| Threat ID | Mitigation |
|-----------|------------|
| T-04-04-PORT-RACE | `await asyncio.sleep(1.5)` before each successive `_load_and_instantiate`; asserted by `test_staggerBetweenTwoPlugins` |
| T-04-04-LOOP-STALL | `_load_and_instantiate` wrapped in `asyncio.to_thread(...)` inside `discover_async` |
| T-04-04-SYNC-REGRESSION | Sync `discover` refactor preserved bit-identical behavior; 18 existing tests green |
| T-04-04-STAGGER-AFTER | `test_firstPluginNoSleep` asserts zero leading sleeps before the first plugin |
| T-04-04-SLEEP-OMISSION | All four GREEN tests assert exact sleep counts and durations |

## Known Stubs

None.

## Follow-ups

- Plan 04-05 (Wave 2) switches `main.py` from sync `discover()` to `await discover_async()`.
- Once 04-05 lands and orchestrator tests turn GREEN, sync `discover()` can stay or be removed in a future cleanup; keeping it costs nothing (it now just delegates to the shared helpers).

## Self-Check: PASSED

- plugin_registry.py: FOUND
- tests/test_registry_stagger.py: FOUND
- Commit 97263e5: FOUND
- Commit ffca54b: FOUND
