---
phase: 04-async-orchestrator
plan: 01
subsystem: test-infra
tags:
  - python
  - pytest
  - pytest-asyncio
  - test-infra
  - wave-0
  - async
requirements:
  - ASYNC-01
  - ASYNC-02
  - ASYNC-03
  - ASYNC-04
  - ASYNC-05
dependency_graph:
  requires:
    - "Phase 1: RetailerPlugin ABC, pytest infrastructure"
    - "Phase 2: plugin_registry.discover, route_url"
  provides:
    - "pytest-asyncio installed and configured (asyncio_mode=auto)"
    - "shared async fixtures: tmpDbPath, appConfigStub, fakePluginFactory"
    - "RED skeleton tests covering ASYNC-01..05 + D-04"
  affects:
    - "Wave 1 plans (04-02 models WAL, 04-03 plugin shutdown + registry stagger) drive RED to GREEN"
    - "Wave 2 plan 04-04 (orchestrator) drives orchestrator + writer RED to GREEN"
tech_stack:
  added:
    - "pytest-asyncio==1.3.0 (dev)"
  patterns:
    - "RED skeleton via import-time failure: importing not-yet-existent symbols raises ImportError at collect time, which pytest reports as ERROR (unambiguous RED signal)"
    - "ast.parse assertions for cross-cutting structural invariants (no bare input() inside async def, executor configured before TaskGroup)"
    - "tracking-sleep monkeypatch pattern records asyncio.sleep durations without slowing the test suite"
key_files:
  created:
    - path: "tests/test_orchestrator.py"
      purpose: "RED tests for ASYNC-01 (TaskGroup isolation) + ASYNC-03 (input via to_thread, executor ordering)"
    - path: "tests/test_purchase_writer.py"
      purpose: "RED tests for ASYNC-05 (queue drain, task_done on failure)"
    - path: "tests/test_registry_stagger.py"
      purpose: "RED tests for ASYNC-02 (1.5s stagger; no sleep before first plugin)"
    - path: "tests/test_models_wal.py"
      purpose: "RED tests for ASYNC-04 (WAL journal mode, busy_timeout, context manager rollback)"
    - path: "tests/test_plugin_shutdown.py"
      purpose: "RED tests for D-04 (async shutdown coroutine, default driver.quit, no-driver no-op)"
  modified:
    - path: "requirements.txt"
      change: "pin pytest-asyncio==1.3.0 after the existing pytest pin"
    - path: "pyproject.toml"
      change: "add asyncio_mode=auto and asyncio_default_fixture_loop_scope=function to [tool.pytest.ini_options]"
    - path: "tests/conftest.py"
      change: "extend with tmpDbPath, appConfigStub, fakePluginFactory fixtures"
    - path: ".gitignore"
      change: "ignore data/*.db-wal and data/*.db-shm SQLite WAL sidecar files"
decisions:
  - "Set asyncio_default_fixture_loop_scope = function (Rule 2 deviation): pytest-asyncio 1.3.0 emits a PytestDeprecationWarning if unset. Setting it now matches the documented future default and silences the warning so CI signal stays clean."
  - "Used import-at-top RED pattern: each test file imports the not-yet-existent symbol at module scope. pytest reports the collection-time ImportError as ERROR, which is the unambiguous Wave 0 RED signal. Tests inside the file are skipped due to the collection error; Wave 1/2 GREEN plans add the symbol and the tests start running."
  - "Used ast.parse for structural assertions in test_orchestrator.py rather than runtime checks. This catches refactors that would otherwise silently re-introduce blocking input() inside async def bodies."
metrics:
  duration_minutes: 12
  completed: "2026-05-14T14:52:44Z"
  tasks_completed: 2
  files_created: 5
  files_modified: 4
  commits:
    - hash: "6c0fd36"
      message: "chore(04-01): install pytest-asyncio and add async fixtures"
    - hash: "ed68a0d"
      message: "test(04-01): add RED skeleton tests for ASYNC-01..05 + D-04"
---

# Phase 4 Plan 01: async-test-infra Summary

Wave 0 test scaffolding for Phase 4. Pinned pytest-asyncio 1.3.0, configured pytest auto-mode, added three shared async fixtures, and shipped five RED skeleton test files (13 new tests) that fail by design until Waves 1 and 2 land the production code.

## What Shipped

### Dependency and configuration

- `requirements.txt`: appended `pytest-asyncio==1.3.0` directly after `pytest==8.3.4`. Version was already installed in the user site-packages; confirmed via `python -c "import pytest_asyncio; print(pytest_asyncio.__version__)"`.
- `pyproject.toml`: added `asyncio_mode = "auto"` and `asyncio_default_fixture_loop_scope = "function"` inside the existing `[tool.pytest.ini_options]` block.
- `.gitignore`: ignored `data/*.db-wal` and `data/*.db-shm` before WAL mode lands in Plan 04-02. Patterns are redundant with the existing `data/*` line but explicit for the security audit trail (T-04-01-WAL-COMMIT).

### Shared fixtures (tests/conftest.py)

- `tmpDbPath`: monkeypatches `models.DB_PATH` to a tmp_path file for per-test DB isolation.
- `appConfigStub`: minimal AppConfig-shaped object with `debug`, `app.delay = 0.0`, `openBrowser`, and an empty `available.items` list.
- `fakePluginFactory`: builds RetailerPlugin subclasses with configurable check/auto_buy behavior (return value, exception raising) and a MagicMock driver. Records call counts via `checkCalls` and `autoBuyCalls`.

### RED skeleton tests (13 total)

| File | Tests | Requirement | RED mechanism |
|------|-------|-------------|---------------|
| tests/test_orchestrator.py | 3 | ASYNC-01, ASYNC-03 | ImportError on `poll_plugin`, `purchase_writer` |
| tests/test_purchase_writer.py | 2 | ASYNC-05 | ImportError on `purchase_writer` |
| tests/test_registry_stagger.py | 2 | ASYNC-02 | ImportError on `discover_async` |
| tests/test_models_wal.py | 3 | ASYNC-04 | ImportError on `_connect` |
| tests/test_plugin_shutdown.py | 3 | D-04 | AttributeError on `RetailerPlugin.shutdown` |

Four files fail at collection (ImportError on not-yet-existent symbols). One file (test_plugin_shutdown.py) collects successfully and fails at execution because `RetailerPlugin.shutdown` does not exist. Both are valid RED signals.

## Verification

```
$ python -m pytest tests/test_orchestrator.py tests/test_purchase_writer.py \
    tests/test_registry_stagger.py tests/test_models_wal.py \
    tests/test_plugin_shutdown.py
ERROR tests/test_orchestrator.py     (ImportError: poll_plugin, purchase_writer)
ERROR tests/test_purchase_writer.py  (ImportError: purchase_writer)
ERROR tests/test_registry_stagger.py (ImportError: discover_async)
ERROR tests/test_models_wal.py       (ImportError: _connect)
FAILED test_plugin_shutdown.py::test_shutdownIsCoroutine (AssertionError)
FAILED test_plugin_shutdown.py::test_defaultShutdownQuitsDriver (AttributeError)
FAILED test_plugin_shutdown.py::test_shutdownNoDriverAttribute (AttributeError)

$ python -m pytest --ignore=tests/test_utils.py \
    --ignore=tests/test_orchestrator.py \
    --ignore=tests/test_purchase_writer.py \
    --ignore=tests/test_registry_stagger.py \
    --ignore=tests/test_models_wal.py \
    --ignore=tests/test_plugin_shutdown.py
167 passed
```

Pre-existing Phase 1/2/3 test suite remains green (167 passed).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Added asyncio_default_fixture_loop_scope to pyproject.toml**

- **Found during:** Task 1 verification (baseline pytest run)
- **Issue:** pytest-asyncio 1.3.0 emits `PytestDeprecationWarning: The configuration option "asyncio_default_fixture_loop_scope" is unset.` on every test run. Without an explicit setting, future pytest-asyncio releases will change the default and may break test behavior silently.
- **Fix:** Set `asyncio_default_fixture_loop_scope = "function"` (the documented future default) in pyproject.toml's `[tool.pytest.ini_options]` block.
- **Files modified:** pyproject.toml
- **Commit:** 6c0fd36

### Deferred Issues

**1. tests/test_utils.py imports a deleted symbol**

- **Found during:** Task 1 baseline pytest run.
- **Issue:** `tests/test_utils.py` does `from utils import make_tiny`, but `make_tiny` was moved into `main.py` during Phase 2. The file fails at collection with ImportError. This is pre-existing breakage from before Phase 4 and is out of scope for this plan per the executor scope-boundary rule.
- **Disposition:** Logged here for future cleanup. Suggested fix: delete `tests/test_utils.py` (the symbol it tested moved out of utils.py) or rewrite it to test the new `main.make_tiny` location. Not blocking Wave 1/2.

**2. data/ directory missing from worktree**

- **Found during:** Task 1 baseline pytest run.
- **Issue:** `tests/test_models.py` opens `data/shop_py_bot.db` directly (no tmp_path), which fails with `sqlite3.OperationalError: unable to open database file` if `data/` does not exist. Pre-existing fragility from before Phase 4.
- **Disposition:** Created the `data/` directory locally to unblock the baseline run; this is already in .gitignore so nothing was committed. The cleaner fix (have test_models.py use the new tmpDbPath fixture) is a 04-02 concern when WAL mode lands. Not blocking Wave 1/2.

## Threat Model Compliance

T-04-01-WAL-COMMIT mitigation shipped: `.gitignore` now lists `data/*.db-wal` and `data/*.db-shm` before Plan 04-02 introduces WAL mode. Even with the existing `data/*` catch-all, the explicit pattern serves as an audit-trail marker.

T-04-01-FIXTURE-SHADOW mitigation shipped: new fixtures use camelCase (`tmpDbPath`, `appConfigStub`, `fakePluginFactory`) while existing fixtures use snake_case (`clean_env`, `tmp_config_yml`, `tmp_plugins_dir`). Zero name collisions; full pre-existing test suite remains green.

T-04-01-PARTIAL-INSTALL: accepted per plan; install verified via `import pytest_asyncio; print(__version__)`.

## TDD Gate Compliance

- RED gate: commit `ed68a0d` (`test(04-01): add RED skeleton tests for ASYNC-01..05 + D-04`)
- GREEN gate: deferred to Waves 1 and 2 (04-02 covers ASYNC-04 RED tests, 04-03 covers ASYNC-02 + D-04, 04-04 covers ASYNC-01/03/05). This is by design: Wave 0 ships ONLY the RED tests; the GREEN production code is Wave 1 and Wave 2's responsibility.

## Known Stubs

None. All five test files are functional test code that fail by design, not stubs. The plan-level intent is that they remain failing until the named downstream plans implement the production code.

## Handoff to Wave 1/2

Each Wave 1/2 plan should run a focused pytest invocation against its target RED file as the canonical signal of GREEN-phase completion:

- 04-02 (models WAL): `python -m pytest tests/test_models_wal.py`
- 04-03 (registry stagger + plugin shutdown): `python -m pytest tests/test_registry_stagger.py tests/test_plugin_shutdown.py`
- 04-04 (orchestrator + writer): `python -m pytest tests/test_orchestrator.py tests/test_purchase_writer.py`

Wave 1/2 plans should NOT replace these test files wholesale. They MAY extend them with additional cases (GREEN-phase tests for happy paths, edge cases, regression). They MUST keep every RED skeleton assertion intact.

## Self-Check: PASSED

- FOUND: tests/test_orchestrator.py
- FOUND: tests/test_purchase_writer.py
- FOUND: tests/test_registry_stagger.py
- FOUND: tests/test_models_wal.py
- FOUND: tests/test_plugin_shutdown.py
- FOUND: requirements.txt (pytest-asyncio==1.3.0 line present)
- FOUND: pyproject.toml (asyncio_mode = "auto")
- FOUND: tests/conftest.py (tmpDbPath, appConfigStub, fakePluginFactory)
- FOUND: .gitignore (db-wal, db-shm)
- FOUND: commit 6c0fd36
- FOUND: commit ed68a0d
