---
phase: 04-async-orchestrator
plan: "05"
subsystem: entry-point
tags: [async, main, orchestrator, wiring, cvv-gate, delegation]
dependency_graph:
  requires: ["04-03", "04-04"]
  provides: ["runnable async entry point via core.orchestrator.async_main"]
  affects: ["main.py", "tests/test_main_wiring.py"]
tech_stack:
  added: []
  patterns: ["thin entry-point delegation", "TDD red-green"]
key_files:
  created:
    - tests/test_main_wiring.py
  modified:
    - main.py
    - tests/test_utils.py
decisions:
  - "Removed make_tiny() and requests import: orchestrator logs full URL; TinyURL API call was sequential-loop-only dead code"
  - "Removed orphaned test_make_tiny: tested a now-deleted function; replaced with comment explaining the removal"
  - "Preserved writeLog import alongside setup_logger: main() start log retained for operational visibility"
metrics:
  duration: "~15 min"
  completed: "2026-06-03"
  tasks_completed: 1
  tasks_total: 2
  files_changed: 3
---

# Phase 4 Plan 5: Main Entry Point Wiring Summary

**One-liner:** main.py rewritten as a thin entry point that delegates to `core.orchestrator.async_main`, removing the sequential while-True loop while preserving the getpass CVV gate and AppConfig validation.

## What Was Built

Task 1 rewired `main.py` to import and call `core.orchestrator.async_main` instead of defining its own sequential loop. The pre-flight logic in `main()` is unchanged: AppConfig validation with `SystemExit(1)` on ValidationError, DB seed via `initialize_db()` + `add_items()`, and the test_mode-gated `collect_cvv()` call all remain exactly as before. `asyncio.run(async_main(cfg, cvv))` now exercises the full concurrent stack built in Plans 03-04.

Deleted from main.py: the local `async def async_main` (the sequential while-True loop), `make_tiny()`, and all imports that were only used by those two functions (`requests`, `PluginRegistry`, `get_items`, `play_notification_sound`, `play_buy_sound`, `play_available_sound`, `webbrowser`).

## Files Changed

| File | Change |
|------|--------|
| `main.py` | Removed local async_main loop + make_tiny + 7 unused imports; added `from core.orchestrator import async_main` |
| `tests/test_main_wiring.py` | Created: 6 tests covering delegation seam, asyncio.run call, CVV gate (test_mode true/false), ValidationError exit |
| `tests/test_utils.py` | Removed orphaned `test_make_tiny` (tested deleted function) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_utils.py::test_make_tiny broke when make_tiny was deleted**
- **Found during:** Full suite run after Task 1 implementation
- **Issue:** `test_make_tiny` referenced `main_module.requests` and `main_module.make_tiny`, both of which were removed as part of deleting the sequential loop
- **Fix:** Removed the orphaned test; replaced with a comment explaining the context (make_tiny was loop-only dead code; orchestrator logs full URLs)
- **Files modified:** `tests/test_utils.py`
- **Commit:** 84c0813

## Test Results

Full suite: 72 passed, 0 failed, 4 warnings (cosmetic RuntimeWarning about unawaited mock coroutine, not test failures).

Acceptance criteria verified:
- `grep "from core.orchestrator import async_main" main.py` -- hit on line 7
- `grep "async def async_main" main.py` -- no hit (local loop deleted)
- `grep "collect_cvv" main.py` -- hit (lines 11 and 49)
- `grep "AppConfig()" main.py` -- hit (line 28)
- `grep "SystemExit(1)" main.py` -- hit (line 31)
- `grep "while True" main.py` -- no hit

## Pending: Human Verify Checkpoint (Task 2)

Task 2 is a `checkpoint:human-verify` covering the live concurrency soak. It has NOT been auto-approved. See checkpoint details below.

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes introduced. The delegation seam is a pure code reorganization. T-04-17 (CVV via getpass, pre-asyncio.run) and T-04-18 (AppConfig validation) mitigations are confirmed present and unchanged.

## Self-Check: PASSED

- `main.py` exists and imports clean
- `tests/test_main_wiring.py` exists with 6 passing tests
- commit 84c0813 exists in git log
- No unexpected file deletions in commit
