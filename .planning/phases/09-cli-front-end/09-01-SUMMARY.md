---
phase: 09-cli-front-end
plan: "01"
subsystem: CLI
tags: [cli, argparse, dispatch, botservice, tdd]
dependency_graph:
  requires: [core/service.py, core/credentials.py, core/config_schema.py]
  provides: [core/cli/, core/service.main(argv)]
  affects: [shoppybot entry point, main.py shim]
tech_stack:
  added: []
  patterns: [argparse set_defaults dispatch, parse_known_args test isolation, lazy fastapi import seam, getpass CVV gate]
key_files:
  created:
    - core/cli/__init__.py
    - core/cli/run.py
    - core/cli/setup.py
    - core/cli/items.py
    - core/cli/config_cmd.py
    - core/cli/web.py
    - tests/test_cli_run.py
    - tests/test_cli_setup.py
    - tests/test_cli_items.py
    - tests/test_cli_config.py
    - tests/test_cli_no_fastapi.py
    - tests/test_cli_mod02.py
  modified:
    - core/service.py
    - tests/test_service.py
    - tests/test_credentials.py
decisions:
  - "build_parser() in core/cli/__init__.py owns the parser; core/service.py:main() delegates to it"
  - "parse_known_args(argv) with explicit argv=None param; tests pass argv=[] to avoid sys.argv contamination"
  - "handle_setup stub handles --migrate branch for back-compat; full prompt body deferred to plan 09-02"
  - "run subcommand dispatches via sys.exit(args.func(...)) so test_cli_run.py catches SystemExit(0)"
  - "test_credentials.py::test_main_migrate_flag patched at core.cli.setup.migrate_from_env after module refactor"
metrics:
  duration: 12m
  completed: "2026-06-04"
  tasks: 3
  files: 15
---

# Phase 09 Plan 01: CLI Package Scaffold + Parser Dispatch Summary

argparse subcommand CLI package created with `core/cli/` layout, full parser dispatch wired to `BotService`, and 6 Wave-0 test scaffolds covering all phase-9 requirements.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Wave-0 CLI test scaffolds | 0286caa | 6 new test files |
| 2 | core/cli package: parser + handler stubs | 54b0ad2 | 6 new source files |
| 3 | handle_run + service.main() restructure | 3659558 | 3 modified files |

## What Was Built

`core/cli/` package with:
- `__init__.py`: `build_parser()` with full nested subparser tree and `set_defaults(func=...)` dispatch
- `run.py`: `handle_run(args, svc)` with CVV gate (bestbuy/test_mode logic, getpass, T-09-01/02)
- `setup.py`: `handle_setup` stub with `--migrate` branch operational; interactive body deferred to plan 09-02
- `items.py`: `handle_items_list/add/remove` stubs returning 0 (plan 09-03 fills bodies)
- `config_cmd.py`: `ALLOWLIST`, `_coerce`, `_atomic_yaml_write` plus `handle_config_show/set` stubs
- `web.py`: `handle_web` stub with lazy fastapi import seam (CLI-04 invariant)

`core/service.py:main()` restructured to `main(argv=None)` delegating to `build_parser()` + `parse_known_args(argv)` + subcommand dispatch.

Six Wave-0 test files cover all CLI requirements; non-plan-01 tests carry `@pytest.mark.skip(reason="plan 09-0X")` markers.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_run_subcommand_calls_botservice_run expected no SystemExit**
- Found during: Task 3
- Issue: `main(["run"])` dispatches via `sys.exit(args.func(...) or 0)` which raises `SystemExit(0)`. The initial test body did not handle this.
- Fix: Updated test to `pytest.raises(SystemExit)` and assert `code == 0`.
- Files modified: `tests/test_cli_run.py`
- Commit: 3659558

**2. [Rule 1 - Bug] test_main_constructs_service_and_runs used _FakeService without get_config()**
- Found during: Task 3
- Issue: The pre-existing `_FakeService` mock lacked `get_config()`. `handle_run` now calls `svc.get_config()` to determine the CVV gate, so the mock raised `AttributeError`.
- Fix: Added `get_config()` returning a minimal MagicMock config to `_FakeService`; also switched `main()` call to `main([])` to avoid sys.argv contamination (subparsers now validate choices strictly in Python 3.13).
- Files modified: `tests/test_service.py`
- Commit: 3659558

**3. [Rule 1 - Bug] test_main_migrate_flag patched wrong module boundary**
- Found during: Task 3
- Issue: `test_credentials.py::test_main_migrate_flag` patched `core.credentials.migrate_from_env`. The old inline `main()` imported `migrate_from_env` at call-time so the patch was effective. After the refactor, `handle_setup` in `core.cli.setup` imports it at module-level; the patch on `core.credentials` no longer reached the call site.
- Fix: Updated patch target to `core.cli.setup.migrate_from_env`.
- Files modified: `tests/test_credentials.py`
- Commit: 3659558

**4. [Rule 2 - Missing functionality] handle_setup stub needed --migrate branch for back-compat**
- Found during: Task 3
- Issue: The plan specified `handle_setup` as a stub returning 0, but the back-compat `--migrate` test requires the migrate path to be functional now (not deferred to plan 09-02).
- Fix: Added the `--migrate` branch to the stub so `shoppybot --migrate` prints migrated key names. Interactive prompt body remains deferred to plan 09-02.
- Files modified: `core/cli/setup.py`
- Commit: 3659558

## Known Stubs

| Stub | File | Reason |
|------|------|--------|
| `handle_setup` interactive prompts | `core/cli/setup.py` | Plan 09-02 implements credential prompt loop and backend-write |
| `handle_items_list/add/remove` | `core/cli/items.py` | Plan 09-03 implements table formatting and BotService delegation |
| `handle_config_show/set` | `core/cli/config_cmd.py` | Plan 09-02 implements YAML read/write and show output |
| `handle_web` full body | `core/cli/web.py` | Plan 09-04 implements web server; lazy import seam is already in place |

These stubs are intentional: each owning plan fills the body. The stubs return 0 so dispatch wiring tests pass now.

## Test Results

```
259 passed, 15 skipped, 1 xpassed -- full suite green
test_cli_run.py: 3 passed
test_cli_mod02.py: 1 passed
test_main_wiring.py: 6 passed (no regression)
Skipped: 13 skip-marked CLI tests deferred to plans 09-02/03/04
```

## Self-Check: PASSED

Files verified:
- core/cli/__init__.py: FOUND
- core/cli/run.py: FOUND
- core/cli/setup.py: FOUND
- core/cli/items.py: FOUND
- core/cli/config_cmd.py: FOUND
- core/cli/web.py: FOUND
- tests/test_cli_run.py: FOUND
- tests/test_cli_mod02.py: FOUND

Commits verified:
- 0286caa: FOUND
- 54b0ad2: FOUND
- 3659558: FOUND
