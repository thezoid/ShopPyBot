---
phase: 02-plugin-migration
plan: "03"
subsystem: core/registry
tags: [plugin-registry, importlib, routing, lifecycle, CORE-03, CORE-04, D-09, D-10]
dependency_graph:
  requires: ["02-02"]
  provides: ["core/registry.py: PluginRegistry discovery+routing+lifecycle"]
  affects: ["main.py (Plan 05 drives registry)", "plugins/*.py (discovered by registry)"]
tech_stack:
  added: []
  patterns:
    - "importlib.util.spec_from_file_location for file-path plugin discovery (no sys.path mutation)"
    - "inspect.getmembers + issubclass filter for concrete subclass extraction"
    - "urlparse(url).hostname + any(p in host for p in patterns) for domain routing (D-10)"
    - "Eager instantiation, lazy setup() via setup_for_items (D-09)"
key_files:
  created:
    - path: "core/registry.py"
      description: "PluginRegistry: _discover_plugins, route, setup_for_items, teardown_all"
    - path: "tests/test_registry.py"
      description: "6 tests covering CORE-03 discovery+isolation, CORE-04 routing, D-09 lifecycle"
  modified: []
decisions:
  - "_route_all private helper routes against _all_plugins (not _active_plugins) during setup_for_items, enabling correct lazy-launch before the active list is populated"
  - "writeLog does not route through Python logging module (uses print()); tests monkeypatch core.registry.writeLog via unittest.mock.patch rather than caplog"
  - "plugins_dir.exists() guard added: missing plugins directory logs WARNING and returns empty list rather than raising FileNotFoundError"
metrics:
  duration: "~20 minutes"
  completed: "2026-06-03T00:23:00Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 0
---

# Phase 02 Plan 03: PluginRegistry Summary

PluginRegistry with importlib discovery, hostname routing, and D-09 lazy lifecycle: discovers all `shopbot_plugin_*.py` via `spec_from_file_location`, routes by `urlparse(url).hostname` substring match, and awaits `setup()` only for plugins with at least one matching item.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement PluginRegistry (discovery, routing, lifecycle) | fe4e4a7 | core/registry.py |
| 2 | Write tests/test_registry.py (CORE-03 + CORE-04 + lifecycle) | b74577f | tests/test_registry.py |

## Verification Results

- `python -c "from core.registry import PluginRegistry, _discover_plugins; print('ok')"` exits 0
- `python -m pytest tests/test_registry.py -q` exits 0 (6 passed)
- `python -m pytest tests/ -q` exits 0 (25 passed, +6 new; no regressions)
- `grep "except:" core/registry.py` returns no bare-except matches (only `except Exception`)

## Deviations from Plan

### Auto-added Missing Critical Functionality

**1. [Rule 2 - Missing Guard] Added plugins_dir.exists() check in _discover_plugins**
- **Found during:** Task 1 implementation
- **Issue:** Without the guard, calling `plugins_dir.iterdir()` on a missing directory raises `FileNotFoundError`, crashing the registry before any items are processed. The plan spec implies robustness ("never crash on a single bad plugin"), and a missing plugins dir is a recoverable condition for a personal bot.
- **Fix:** Added early return with WARNING log if `plugins_dir` does not exist.
- **Files modified:** core/registry.py
- **Commit:** fe4e4a7

**2. [Rule 2 - Internal Helper] Added _route_all to route against _all_plugins**
- **Found during:** Task 1 implementation of setup_for_items
- **Issue:** `route()` searches `_active_plugins`, but `setup_for_items` needs to identify needed plugins from `_all_plugins` before any plugin has been activated. Using `route()` directly would always find nothing.
- **Fix:** Added `_route_all(url)` private helper that mirrors `route()` but iterates `_all_plugins`. `setup_for_items` calls `_route_all`; the public `route()` remains over `_active_plugins` only.
- **Files modified:** core/registry.py
- **Commit:** fe4e4a7

## Known Stubs

None. Registry has no hardcoded placeholder values or TODO stubs that affect plan goal.

## Threat Flags

No new network endpoints, auth paths, or schema changes introduced. The `_discover_plugins`
trust boundary (T-02-04: importlib exec_module of local .py files) was pre-documented in the
plan threat model and is mitigated by the `shopbot_plugin_*` prefix filter plus `except Exception`
isolation per T-02-05.

## Self-Check: PASSED

- core/registry.py: EXISTS (committed fe4e4a7)
- tests/test_registry.py: EXISTS (committed b74577f)
- Commit fe4e4a7: FOUND in git log
- Commit b74577f: FOUND in git log
- Full test suite: 25 passed, 0 failures
