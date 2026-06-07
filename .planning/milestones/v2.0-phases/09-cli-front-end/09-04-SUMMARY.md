---
phase: 09-cli-front-end
plan: "04"
subsystem: CLI
tags: [cli, fastapi, lazy-import, no-fastapi-guard, tdd]
dependency_graph:
  requires: [core/cli/web.py, core/service.py, tests/test_cli_no_fastapi.py]
  provides: [CLI-04 guard: fastapi-free CLI runtime]
  affects: [tests/test_cli_no_fastapi.py]
tech_stack:
  added: []
  patterns: [lazy try/except ImportError inside handler body, sys.modules None sentinel test idiom]
key_files:
  created: []
  modified:
    - tests/test_cli_no_fastapi.py
decisions:
  - "web.py lazy-import seam was already correct from plan 09-01 stub; no source change needed"
  - "test_run_works_without_fastapi wraps main(['run']) in pytest.raises(SystemExit) + assert code==0 -- mirrors test_cli_run.py pattern because run dispatches via sys.exit"
metrics:
  duration: 4m
  completed: "2026-06-04"
  tasks: 1
  files: 1
---

# Phase 09 Plan 04: web lazy-import seam + no-fastapi guard Summary

CLI-04 satisfied: unskipped the two no-fastapi guard tests; fixed the `SystemExit` handling in the run test to match the established `pytest.raises(SystemExit)` pattern; 274 passed, 0 skipped.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement web lazy-import seam + CLI-04 guard tests | 808fb84 | tests/test_cli_no_fastapi.py |

## What Was Built

`tests/test_cli_no_fastapi.py` unskipped with two active tests:

- `test_web_no_fastapi`: monkeypatches `sys.modules['fastapi'] = None`, deletes `core.cli.web` from `sys.modules` to force re-import, then asserts `handle_web` returns 1 and stderr contains `"pip install .[web]"`.
- `test_run_works_without_fastapi`: monkeypatches `sys.modules['fastapi'] = None`, wraps `main(["run"])` in `pytest.raises(SystemExit)`, asserts exit code 0 and `mock_svc.run.assert_called_once()`.

`core/cli/web.py` was already correct from the plan 09-01 stub: `import sys` at module level only, `try: import fastapi` inside `handle_web` body, `except ImportError` prints the `pip install .[web]` hint to stderr and returns 1. No changes were needed to the source file.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_run_works_without_fastapi raised SystemExit instead of asserting mock call**

- Found during: Task 1 (first run of tests)
- Issue: The plan stub called `main(["run"])` without a `pytest.raises` context, but `main(["run"])` dispatches via `sys.exit(args.func(...) or 0)` which raises `SystemExit(0)`. The assertion `mock_svc.run.assert_called_once()` was never reached.
- Fix: Wrapped `main(["run"])` in `pytest.raises(SystemExit)` and added `assert exc_info.value.code == 0` before the mock assertion. Identical to the pattern in `test_cli_run.py::test_run_subcommand_calls_botservice_run`.
- Files modified: `tests/test_cli_no_fastapi.py`
- Commit: 808fb84

## Test Results

```
274 passed, 0 skipped, 1 xpassed -- full suite green
test_cli_no_fastapi.py: 2 passed (was 2 skipped)
No skip markers remain in the CLI test suite
```

## Verification

AST guard confirmed: `python -c "import ast; t=ast.parse(open('core/cli/web.py').read()); assert not any(...);"` prints `no top-level fastapi`.

## Self-Check: PASSED

Files verified:
- tests/test_cli_no_fastapi.py: FOUND (modified)
- core/cli/web.py: FOUND (unchanged -- correct from 09-01)

Commits verified:
- 808fb84: FOUND
