---
phase: 19-db-schema-confirmation-detection
plan: "03"
subsystem: core/plugin_base
tags: [abc, plugin-api, buy, tdd]
dependency_graph:
  requires: []
  provides: [RetailerPlugin.get_active_tab]
  affects: [core/plugin_base.py, tests/test_plugin_base.py]
tech_stack:
  added: []
  patterns: [additive-concrete-abc-method, getattr-safe-default]
key_files:
  created: []
  modified:
    - core/plugin_base.py
    - tests/test_plugin_base.py
decisions:
  - get_active_tab is sync def (not async) -- returns a stored tab object, not an awaitable; orchestrator calls without await
  - PLUGIN_API_VERSION stays 2 (additive concrete method per BUY-03)
  - Default uses getattr(self.driver, "main_tab", None) for safe fallback when driver is None
  - Amazon/BestBuy overrides (_last_tab storage) deferred to Plan 04
metrics:
  duration: "~3 min"
  completed: "2026-06-11T20:48:57Z"
  tasks_completed: 1
  files_changed: 2
---

# Phase 19 Plan 03: get_active_tab() ABC Hook Summary

**One-liner:** Additive sync `get_active_tab()` concrete default on RetailerPlugin ABC returning `getattr(self.driver, "main_tab", None)` as the BUY-03 orchestrator contract hook.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1-RED | Add failing tests for get_active_tab() | 5dd9c0c | tests/test_plugin_base.py |
| 1-GREEN | Implement get_active_tab() on ABC | 1530f89 | core/plugin_base.py |

## What Was Built

`RetailerPlugin.get_active_tab()` is a concrete (non-abstract) sync method added immediately after `get_price` in `core/plugin_base.py`. The default body is:

```python
return getattr(self.driver, "main_tab", None)
```

This is the stable interface contract the orchestrator (Plan 04) will call after `auto_buy()` returns True to obtain the live confirmation tab. The 6 non-checkout plugins inherit this default unchanged; Amazon and BestBuy will override it in Plan 04 to return `self._last_tab`.

## TDD Gate Compliance

- RED commit (5dd9c0c): `test(19-03)` -- 3 new tests fail with AttributeError, 18 pass
- GREEN commit (1530f89): `feat(19-03)` -- all 21 tests pass, 585 total pass

## Acceptance Criteria Verification

- [x] `core/plugin_base.py` defines sync `def get_active_tab(self):` returning `getattr(self.driver, "main_tab", None)`
- [x] With `driver.main_tab` set, returns the tab object
- [x] With `driver=None`, returns None (no AttributeError)
- [x] `PLUGIN_API_VERSION == 2` asserted in test
- [x] No plugin file modified
- [x] Full suite green: 585 passed, 2 skipped

## Deviations from Plan

None -- plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None. T-19-07 disposition is `accept`: additive concrete method with a safe None default; no auth or sensitive data crosses the boundary; PLUGIN_API_VERSION unchanged.

## Self-Check: PASSED

- core/plugin_base.py: FOUND (modified)
- tests/test_plugin_base.py: FOUND (modified)
- Commit 5dd9c0c: FOUND
- Commit 1530f89: FOUND
