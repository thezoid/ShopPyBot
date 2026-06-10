---
phase: 15-plugin-ecosystem-registry
plan: 02
subsystem: cli
tags: [plugins-list, cli, argparse, tdd, registry, json]

# Dependency graph
requires:
  - phase: 15-01
    provides: RetailerPlugin ABC with difficulty/requires_proxy/requires_captcha attrs

provides:
  - BotService.list_plugins() read-only accessor over registry._all_plugins
  - core/cli/plugins.py with handle_plugins_list + _format_plugins_table
  - shoppybot plugins list (aligned table); --json flag; bare plugins exits 2
  - 5 tests covering table, JSON, no-leaf-exit-2, empty, and no-network behavior

affects: [REG-03, 15-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Nested argparse subparser with _require_subcommand default for bare group exit 2"
    - "Local import inside BotService method to satisfy MOD-02 layering constraint"
    - "getattr defaults on plugin attrs for belt-and-suspenders guard"

key-files:
  created:
    - core/cli/plugins.py
    - tests/test_cli_plugins.py
  modified:
    - core/service.py
    - core/cli/__init__.py

key-decisions:
  - "PluginRegistry imported locally inside BotService.list_plugins() body (not at module top) to keep core.registry out of the CLI import path -- satisfies MOD-02 layering per T-15-04"
  - "_all_plugins read (not _active_plugins) because active list is empty until setup_for_items() runs; reading it at CLI time would return zero results (RESEARCH Pitfall 1)"
  - "getattr(plugin, 'difficulty', 'medium') etc. used as belt-and-suspenders guard; all 7 existing plugins already have the attrs from Plan 15-01 but the guard future-proofs against third-party plugins"

requirements-completed: [REG-03]

# Metrics
duration: 12min
completed: 2026-06-09
---

# Phase 15 Plan 02: CLI plugins list Command Summary

**BotService.list_plugins() + core/cli/plugins.py + shoppybot plugins list [--json]; bare plugins exits 2; no network call; 5 new tests, 492 total passing**

## Performance

- **Duration:** 12 min
- **Started:** 2026-06-09T22:00:00Z
- **Completed:** 2026-06-09T22:12:00Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Added `BotService.list_plugins()` to `core/service.py` -- constructs a fresh `PluginRegistry` locally (no browser, no network), reads `registry._all_plugins`, returns one dict per plugin with 5 keys: `name`, `domain_patterns`, `difficulty`, `requires_proxy`, `requires_captcha`
- Created `core/cli/plugins.py` with `_format_plugins_table()` (aligned 5-column table, "No plugins loaded." on empty) and `handle_plugins_list()` (prints table or JSON via `--json`); imports only `json`, `sys`, `BotService` (MOD-02 compliant)
- Updated `core/cli/__init__.py` to import `handle_plugins_list` and register a `plugins` nested subparser with a `list` leaf, `--json` flag, and `_require_subcommand` default so bare `shoppybot plugins` exits 2
- 5 new tests in `tests/test_cli_plugins.py`: table output, JSON output, no-leaf-exit-2, empty result, no-network assertion
- Full suite: 492 passed, 2 skipped (baseline 487 + 5 new)

## Task Commits

Each task was committed atomically:

1. **Task 1: Failing tests/test_cli_plugins.py scaffold (RED)** - `def6d82`
2. **Task 2: BotService.list_plugins() reading _all_plugins** - `220227a`
3. **Task 3: core/cli/plugins.py handler + plugins subparser (GREEN)** - `91d2e3c`

## Files Created/Modified

- `core/service.py` - Added `list_plugins()` method in the read-only accessors block; PluginRegistry imported locally inside the method body (MOD-02)
- `core/cli/plugins.py` - New module: `_format_plugins_table()` and `handle_plugins_list()`; no `core.registry` import
- `core/cli/__init__.py` - Added `from core.cli.plugins import handle_plugins_list` and `plugins` nested subparser block with `list` leaf and `--json` flag
- `tests/test_cli_plugins.py` - 5 CLI tests: table, JSON, no-leaf-exit-2, empty, no-network

## Decisions Made

- `PluginRegistry` imported locally inside `BotService.list_plugins()` body (not at module top-level) to keep `core.registry` out of the CLI import chain -- satisfies MOD-02 (T-15-04 mitigation).
- `_all_plugins` is read, not `_active_plugins` (empty until `setup_for_items()` runs). Reading `_active_plugins` at CLI time would always return zero results (RESEARCH Pitfall 1).
- `getattr(plugin, "difficulty", "medium")` etc. used as belt-and-suspenders guards; all 7 existing plugins already have the attrs from Plan 15-01, but this future-proofs against third-party plugins.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Threat Surface Scan

T-15-04 (Tampering via MOD-02 layering) mitigated as planned: `core/cli/plugins.py` has zero imports of `core.registry` (grep-verified). T-15-05 (DoS via network call) mitigated: `list_plugins()` reads only `_all_plugins` with no `setup()` or browser calls; `test_plugins_list_no_network` asserts no socket is constructed during the CLI path.

## Self-Check: PASSED

- `core/cli/plugins.py` exists: FOUND
- `core/service.py` contains `def list_plugins`: FOUND
- `core/cli/__init__.py` contains `handle_plugins_list` and `plugins`: FOUND
- `tests/test_cli_plugins.py` exists with 5 tests: FOUND
- `core/cli/plugins.py` does not import `core.registry`: VERIFIED (grep shows only docstring mention)
- Commit `def6d82` exists: FOUND
- Commit `220227a` exists: FOUND
- Commit `91d2e3c` exists: FOUND
- Full suite 492 passed, 2 skipped: VERIFIED
