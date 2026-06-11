---
phase: 18-safety-gate-config-foundation
plan: "02"
subsystem: core/plugin_base
tags: [safety-gate, abc, buy-guard, tdd]
dependency_graph:
  requires: [18-01]
  provides: [place_order_guarded on RetailerPlugin ABC]
  affects: [18-04 plugin reroutes, all future plugins]
tech_stack:
  added: []
  patterns: [concrete-async-method-on-ABC, getattr-safe-config-read, tdd-red-green]
key_files:
  created: []
  modified:
    - core/plugin_base.py
    - tests/test_plugin_base.py
decisions:
  - place_order_guarded placed after get_price, before login -- follows additive-concrete pattern
  - test_mode safe default is True (suppressed) via getattr fallback; missing config fails safe (T-18-06)
  - monitor_only safe default is False (not suppressed) consistent with DebugConfig field default
  - writeLog imported at module level in plugin_base.py, mirroring plugin file convention
  - PLUGIN_API_VERSION stays 2 -- additive concrete method, same pattern as get_price (PRICE-02)
metrics:
  duration: "267s (~4.5 min)"
  completed: "2026-06-11"
  tasks: 2
  files: 2
---

# Phase 18 Plan 02: place_order_guarded ABC Method Summary

**One-liner:** Concrete async `place_order_guarded(click_fn) -> bool` on `RetailerPlugin` ABC guards all place-order DOM clicks behind `test_mode`/`monitor_only` flags read getattr-safe from `self.config.debug`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Add failing tests for place_order_guarded | 8e12aa8 | tests/test_plugin_base.py |
| 2 (GREEN) | Implement place_order_guarded on ABC | 64a70b2 | core/plugin_base.py |

## What Was Built

`RetailerPlugin.place_order_guarded(self, click_fn) -> bool` is a concrete `async` method inserted between `get_price` and `login` in `core/plugin_base.py`. It:

- Reads `self.config.debug.test_mode` and `self.config.debug.monitor_only` via `getattr` chains that are safe against `None` config or missing `debug` attribute.
- When either flag is truthy: calls `writeLog("place-order suppressed (monitor_only/test_mode)", "INFO")` and returns `False` without awaiting `click_fn`.
- When both are `False`: `await click_fn()` then returns `True`.
- Never raises. Safe-default for missing config: `test_mode` defaults to `True` (suppressed), so a partial or absent config always blocks an order.

Three unit tests added to `tests/test_plugin_base.py` verify each branch (suppressed-by-test_mode, suppressed-by-monitor_only, allowed). All 559 tests pass.

## Deviations from Plan

None -- plan executed exactly as written.

## TDD Gate Compliance

- RED gate: commit `8e12aa8` (`test(18-02): add failing tests...`) -- confirmed AttributeError failure before implementation.
- GREEN gate: commit `64a70b2` (`feat(18-02): add place_order_guarded...`) -- all 3 new tests + 13 pre-existing tests pass (16 total in file).

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. `place_order_guarded` is purely an in-process guard method. T-18-04/T-18-05/T-18-06 mitigated as planned.

## Self-Check: PASSED

- `core/plugin_base.py` modified: confirmed (place_order_guarded + writeLog import present)
- `tests/test_plugin_base.py` modified: confirmed (3 new tests present)
- Commit `8e12aa8` exists: confirmed
- Commit `64a70b2` exists: confirmed
- `pytest tests/test_plugin_base.py -x -q`: 16 passed
- Full suite: 559 passed, 2 skipped
- `PLUGIN_API_VERSION == 2`: confirmed
