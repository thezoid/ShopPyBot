---
phase: 04-async-orchestrator
plan: "03"
subsystem: infra
tags: [asyncio, taskgroup, write-queue, sqlite3, stdin-listener, event-loop]

requires:
  - phase: 04-01
    provides: poll_interval config field, fake_plugin + event_shim fixtures
  - phase: 04-02
    provides: WAL context manager, get_items_sync, update_item_purchased_sync, plugins_for_items prerequisite

provides:
  - core/orchestrator.py with async_main, run_plugin, _write_queue_drain, _staggered_setup, _stdin_listener_thread
  - plugins_for_items() helper on PluginRegistry
  - 7 unit tests covering TaskGroup structure, 1.5s stagger, write-queue serialization, Event wakeup

affects:
  - 04-04 (Amazon plugin input() -> asyncio.Event migration depends on this orchestrator's Event wiring)
  - 05 (notifications phase builds on async_main entry point)
  - main.py (caller of async_main once wired up)

tech-stack:
  added: []
  patterns:
    - "asyncio.TaskGroup of per-plugin poll coroutines in one event loop (ASYNC-01)"
    - "1.5s staggered plugin driver init with per-init STAGGER log line (ASYNC-02)"
    - "Single asyncio.Queue drained by one _write_queue_drain task (ASYNC-05)"
    - "stdin listener thread via run_in_executor; events set only via call_soon_threadsafe (ASYNC-03)"
    - "run_in_executor used ONLY for sqlite3 calls and stdin readline; nodriver stays on loop"
    - "except* KeyboardInterrupt (PEP 654) for clean TaskGroup shutdown"
    - "write_queue.join(timeout=10) in finally before teardown_all (Pitfall 4 deadlock guard)"

key-files:
  created:
    - core/orchestrator.py
    - tests/test_orchestrator.py
  modified:
    - core/registry.py

key-decisions:
  - "plugins_for_items added as a pure helper on PluginRegistry rather than inlining the dedup logic in orchestrator; setup_for_items left untouched"
  - "run_plugin factors out _check_and_buy to keep each function under 30 lines (CLAUDE.md constraint)"
  - "utils imports (play_available_sound, play_buy_sound) placed inside _check_and_buy to avoid circular import risk at module level"
  - "STAGGER_SECS = 1.5 module constant; asyncio.sleep patched by name in tests for deterministic stagger verification"
  - "test_taskgroup_creates_per_plugin_tasks uses a _TrackingGroup shim instead of real TaskGroup to inspect task names without running the full poll loop"

patterns-established:
  - "TDD RED commit before GREEN: test(04-03) precedes feat(04-03)"
  - "All DB writes funnel through _write_queue_drain; plugins call write_queue.put, never update_item_purchased_sync directly"
  - "Security: _stdin_listener_thread reads only readline() line terminators; CVV stays in synchronous getpass scope before asyncio.run()"

requirements-completed: [ASYNC-01, ASYNC-02, ASYNC-05]

duration: 7min
completed: 2026-06-03
---

# Phase 04 Plan 03: Async Orchestrator Summary

**asyncio.TaskGroup orchestrator with 1.5s-staggered plugin driver init, single write-queue drain for serialized DB writes, and stdin-listener thread wiring asyncio.Events via call_soon_threadsafe**

## Performance

- **Duration:** 7 min
- **Started:** 2026-06-03T00:13:24Z
- **Completed:** 2026-06-03T00:20:04Z
- **Tasks:** 2 (Task 1: registry helper; Task 2: TDD orchestrator)
- **Files modified:** 3

## Accomplishments

- Added `plugins_for_items()` to `PluginRegistry` for deduped, order-preserving plugin selection without calling setup()
- Created `core/orchestrator.py` with all five required functions: `run_plugin`, `_write_queue_drain`, `_staggered_setup`, `_stdin_listener_thread`/`_start_stdin_listener`, `async_main`
- 7 unit tests prove TaskGroup structure, >=1.5s stagger spacing, write-queue serialization, task_done on error, and Event wakeup via call_soon_threadsafe

## Task Commits

Each task was committed atomically:

1. **Task 1: Add registry plugins_for_items helper** - `5443a0b` (feat)
2. **Task 2 RED: Failing orchestrator tests** - `6e20b6c` (test)
3. **Task 2 GREEN: Implement orchestrator** - `e962bcc` (feat)

**Plan metadata:** (docs commit to follow)

## Files Created/Modified

- `core/orchestrator.py` - Full concurrent orchestrator: TaskGroup, stagger, write queue, stdin listener
- `tests/test_orchestrator.py` - 7 unit tests covering all ASYNC-0{1,2,3,5} behaviors
- `core/registry.py` - Added `plugins_for_items()` helper method (15 lines)

## Decisions Made

- `_check_and_buy` factored out from `run_plugin` to stay within the 30-line function limit (CLAUDE.md). This helper handles the check/buy/sound/queue path and isolates all per-item exceptions.
- `utils` imports deferred inside `_check_and_buy` to avoid top-level circular import risk (utils -> logger -> config chain).
- `plugins_for_items` uses `id(plugin)` for dedup rather than equality, matching the intent: same object instance, not just same class.
- `_STAGGER_SECS = 1.5` as a named module constant makes the stagger value patchable by name in tests without patching `asyncio.sleep` globally.

## Deviations from Plan

None - plan executed exactly as written. The TDD loop proceeded as designed (RED commit, then GREEN). One minor test adjustment: `test_taskgroup_creates_per_plugin_tasks` was revised to close coroutines immediately inside the `_TrackingGroup` shim (avoiding unawaited-coroutine `RuntimeWarning` from mock internals). This is a test quality fix, not a plan deviation.

## Issues Encountered

None - all acceptance criteria met on first implementation pass.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes. `_stdin_listener_thread` reads only `sys.stdin.readline()` line terminators and sets asyncio.Events exclusively via `loop.call_soon_threadsafe` -- no credential handling. Existing threats T-04-08 through T-04-12 (from plan threat_model) are all mitigated as designed.

## Known Stubs

None. `core/orchestrator.py` is not wired into `main.py` yet -- that wiring is deferred to Plan 04-04 or 04-05 (when the Amazon plugin's input() calls are also migrated). The orchestrator is fully functional and independently tested; the `main.py` `async_main` replacement is a future plan task.

## Next Phase Readiness

- Plan 04-04 can now import `_staggered_setup`, `async_main`, and `run_plugin` from `core/orchestrator`; only needs to add `asyncio.Event` attrs to `AmazonPlugin` and wire `_wait_user_action`
- `main.py` can be updated to call `orchestrator.async_main` in place of its own `async_main` once Plan 04-04 completes
- Full suite at 60/60; no blockers

## Self-Check

Files exist:
- `core/orchestrator.py`: FOUND
- `core/registry.py` (plugins_for_items): FOUND
- `tests/test_orchestrator.py`: FOUND

Commits:
- `5443a0b`: FOUND (feat - registry helper)
- `6e20b6c`: FOUND (test - RED)
- `e962bcc`: FOUND (feat - GREEN)

Suite: 60 passed

## Self-Check: PASSED

---
*Phase: 04-async-orchestrator*
*Completed: 2026-06-03*
