---
phase: 09-cli-front-end
plan: "03"
subsystem: CLI
tags: [cli, argparse, botservice, items, ast-guard, tdd]
dependency_graph:
  requires:
    - phase: 09-01
      provides: core/cli/ package scaffold, items.py stubs, test_cli_items.py stubs, test_cli_mod02.py
    - phase: 09-02
      provides: handle_setup + handle_config fully implemented; main working tree HEAD
  provides:
    - core/cli/items.py fully implemented (list/add/remove over BotService)
    - tests/test_cli_items.py active (4 tests unskipped)
    - tests/test_cli_mod02.py active AST guard (MOD-02 enforced)
  affects: [CLI-03, MOD-02, phase 09-04]
tech-stack:
  added: []
  patterns:
    - _format_items_table: compute per-column widths from max(header, cell) then left-justify
    - list-before-delete: list_items() lookup before remove_item() to recover name and detect missing URL
    - sys.exit(func() or 0) dispatch requires pytest.raises(SystemExit) in tests
    - AST-walk guard scanning core/cli/*.py for forbidden import names (MOD-02)
key-files:
  created: []
  modified:
    - core/cli/items.py
    - tests/test_cli_items.py
key-decisions:
  - "Test scaffold for items list/add/remove needed pytest.raises(SystemExit) since main() calls sys.exit(func() or 0) for all dispatched subcommands -- consistent with test_cli_run.py pattern"
  - "MOD-02 guard (test_cli_mod02.py) was already fully implemented in plan 09-01; no changes required in plan 09-03"
patterns-established:
  - "Pattern: items remove calls list_items() first to retrieve name and detect absent URL; exits 1 with stderr on miss (T-09-11)"
  - "Pattern: all dispatched CLI tests catch SystemExit(0) via pytest.raises()"
requirements-completed: [CLI-03, MOD-02]
duration: 4min
completed: "2026-06-04"
---

# Phase 09 Plan 03: Items List/Add/Remove + MOD-02 Guard Summary

**Items subcommand fully wired over BotService with aligned table, name-on-remove, exit-1-on-miss, and MOD-02 AST guard enforcing no CLI module bypasses BotService**

## Performance

- **Duration:** 4 min
- **Started:** 2026-06-04T17:55:00Z
- **Completed:** 2026-06-04T17:55:30Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `handle_items_list` prints a left-justified aligned text table (Name/URL/Auto-Buy/Qty/Purchased) or "No items tracked."
- `handle_items_add` maps argparse flags directly to `BotService.add_item(name, url, auto_buy, quantity)` with defaults (auto_buy=False, quantity=1)
- `handle_items_remove` looks up name via `list_items()` before deleting; prints name on success, exits 1 to stderr on unknown URL
- MOD-02 AST guard active: `test_cli_mod02.py` scans all `core/cli/*.py` files for forbidden imports (orchestrator, registry, models, sync functions) -- passes clean

## Task Commits

1. **Task 1: Implement items list/add/remove over BotService** - `03eb58d` (feat)

**Plan metadata:** (pending final commit)

## Files Created/Modified

- `core/cli/items.py` - Full implementation: `_format_items_table`, `handle_items_list`, `handle_items_add`, `handle_items_remove`
- `tests/test_cli_items.py` - Unskipped all 4 tests; fixed SystemExit(0) handling for dispatch

## Decisions Made

- Test scaffold written in plan 09-01 did not catch `SystemExit(0)` because `main()` calls `sys.exit(func() or 0)` for all dispatched subcommands. Updated tests to use `pytest.raises(SystemExit)` with `code == 0` assertion -- consistent with `test_cli_run.py::test_run_subcommand_calls_botservice_run` pattern.
- `test_cli_mod02.py` was already fully implemented (active, not stub) in plan 09-01. No edits needed for Task 2.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_cli_items.py scaffold missing SystemExit(0) catch**
- **Found during:** Task 1 (run items tests)
- **Issue:** `main(["items", "list"])`, `main(["items", "add", ...])`, and `main(["items", "remove", ...])` all go through `sys.exit(args.func(...) or 0)` which raises `SystemExit(0)`. The plan 09-01 stubs did not include `pytest.raises(SystemExit)`, so all three tests failed with `SystemExit: 0`.
- **Fix:** Wrapped the three calls in `pytest.raises(SystemExit)` and asserted `code == 0`. Pattern matches `test_cli_run.py::test_run_subcommand_calls_botservice_run`.
- **Files modified:** `tests/test_cli_items.py`
- **Verification:** All 4 tests pass.
- **Committed in:** `03eb58d`

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Fix was necessary for correct test behavior. No scope creep.

## Issues Encountered

None beyond the SystemExit bug above.

## User Setup Required

None - no external service configuration required.

## Test Results

```
272 passed, 2 skipped, 1 xpassed -- full suite green
test_cli_items.py: 4 passed (all unskipped)
test_cli_mod02.py: 1 passed (active AST guard)
```

## Self-Check: PASSED

Files verified:
- core/cli/items.py: FOUND
- tests/test_cli_items.py: FOUND
- tests/test_cli_mod02.py: FOUND (unchanged, already active)

Commits verified:
- 03eb58d: FOUND

## Next Phase Readiness

- CLI-03 fully satisfied: items list/add/remove all route through BotService with correct defaults
- MOD-02 boundary enforced by active AST guard across entire core/cli/ package
- Plan 09-04 (web handler) is the final plan in this phase; lazy fastapi seam already in place from 09-01

---
*Phase: 09-cli-front-end*
*Completed: 2026-06-04*
