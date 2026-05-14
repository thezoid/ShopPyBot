---
phase: 04-async-orchestrator
plan: 01
type: execute
wave: 0
depends_on: []
files_modified:
  - requirements.txt
  - pyproject.toml
  - .gitignore
  - tests/conftest.py
  - tests/test_orchestrator.py
  - tests/test_purchase_writer.py
  - tests/test_registry_stagger.py
  - tests/test_models_wal.py
  - tests/test_plugin_shutdown.py
autonomous: true
requirements:
  - ASYNC-01
  - ASYNC-02
  - ASYNC-03
  - ASYNC-04
  - ASYNC-05
tags:
  - python
  - pytest
  - pytest-asyncio
  - test-infra
  - wave-0
  - async

must_haves:
  truths:
    - "pytest-asyncio==1.3.0 is pinned in requirements.txt and importable"
    - "pyproject.toml [tool.pytest.ini_options] declares asyncio_mode = \"auto\" so async def test_* runs without a per-test decorator"
    - "tests/conftest.py provides shared async fixtures: tmp_db_path, app_config_stub, fake_plugin_factory"
    - "RED skeleton test files exist for all five async requirements (orchestrator, purchase_writer, registry stagger, models WAL, plugin shutdown)"
    - "Every RED skeleton test currently fails because the implementation it asserts on does not yet exist (NotImplementedError, ImportError, or AttributeError raised)"
    - ".gitignore covers data/*.db-wal and data/*.db-shm so WAL sidecar files cannot be committed"
    - "All pre-existing Phase 1/2/3 tests still pass (no regressions)"
  artifacts:
    - path: "requirements.txt"
      provides: "pytest-asyncio dev dependency pinned"
      contains: "pytest-asyncio==1.3.0"
    - path: "pyproject.toml"
      provides: "asyncio_mode=auto pytest configuration"
      contains: "asyncio_mode"
    - path: "tests/conftest.py"
      provides: "Shared async fixtures (tmp_db_path, app_config_stub, fake_plugin_factory)"
      min_lines: 40
    - path: "tests/test_orchestrator.py"
      provides: "RED skeleton tests for ASYNC-01 and ASYNC-03 (poll_plugin, purchase_writer wiring, to_thread(input))"
      min_lines: 40
    - path: "tests/test_purchase_writer.py"
      provides: "RED skeleton tests for ASYNC-05 (queue drain, task_done on failure)"
      min_lines: 30
    - path: "tests/test_registry_stagger.py"
      provides: "RED skeleton tests for ASYNC-02 (1.5s stagger between plugins, no sleep before first)"
      min_lines: 30
    - path: "tests/test_models_wal.py"
      provides: "RED skeleton tests for ASYNC-04 (WAL mode, busy_timeout, context manager rollback)"
      min_lines: 30
    - path: "tests/test_plugin_shutdown.py"
      provides: "RED skeleton tests for D-04 (async shutdown, default driver.quit, no-driver no-op)"
      min_lines: 30
  key_links:
    - from: "pyproject.toml"
      to: "pytest-asyncio"
      via: "[tool.pytest.ini_options] asyncio_mode setting"
      pattern: "asyncio_mode"
    - from: "tests/conftest.py"
      to: "fake_plugin_factory"
      via: "pytest fixture exported for orchestrator + shutdown tests"
      pattern: "fake_plugin_factory"
---

<objective>
Wave 0: install pytest-asyncio, configure auto-mode pytest, ship shared async fixtures, and write RED skeleton test files for every Phase 4 requirement so Waves 1 and 2 have a deterministic failing-test target to drive against.

Purpose: Phase 4 spans models.py, plugin_base.py, plugin_registry.py, and main.py. Three plans run in parallel in Wave 1 and a heavy plan runs in Wave 2. Without Wave 0 test scaffolding, each downstream plan would have to invent its own test patterns, which fragments the test suite and undercuts TDD. This plan ships every new test file in RED state with one failing test per ASYNC-* requirement so Wave 1/2 plans flip them to GREEN by writing the production code.

Output: pinned dev dep, pytest auto-mode config, shared fixtures, five new test files with RED skeletons, gitignore update.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/04-async-orchestrator/04-CONTEXT.md
@.planning/phases/04-async-orchestrator/04-RESEARCH.md
@.planning/phases/02-plugin-migration/02-01-SUMMARY.md
@.planning/phases/01-foundations-security/01-01-test-infra-and-pinned-deps-SUMMARY.md
@requirements.txt
@pyproject.toml
@tests/conftest.py
@plugin_base.py
@plugin_registry.py
@models.py
</context>

<interfaces>
Target `pyproject.toml` addition (append, do not replace existing block):

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

If the existing file already has `[tool.pytest.ini_options]`, add `asyncio_mode = "auto"` inside it. Keep all other keys.

Target `tests/conftest.py` fixture additions (extend existing file):

```python
import asyncio
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock
from typing import Any, Callable

import pytest

from plugin_base import RetailerPlugin


@pytest.fixture
def tmpDbPath(tmp_path, monkeypatch):
    """Redirect models.DB_PATH to a per-test sqlite file."""
    dbPath = tmp_path / "shop_py_bot.db"
    monkeypatch.setattr("models.DB_PATH", str(dbPath))
    return dbPath


@pytest.fixture
def appConfigStub():
    """Minimal AppConfig-shaped namespace for orchestrator tests."""
    class _Debug:
        loggingLevel = 0
        testMode = True
    class _App:
        delay = 0.0  # zero delay so tests don't hang
    class _Cfg:
        debug = _Debug()
        app = _App()
        openBrowser = False
        available = type("_A", (), {"items": []})()
    return _Cfg()


@pytest.fixture
def fakePluginFactory() -> Callable[..., RetailerPlugin]:
    """Build minimal RetailerPlugin subclasses with controllable behavior."""
    def _make(*, name: str = "fake",
             checkReturns: bool = False,
             checkRaises: Exception | None = None,
             autoBuyRaises: Exception | None = None):
        class _FakePlugin(RetailerPlugin):
            domain_pattern = [f"{name}.example"]
            def __init__(self):
                super().__init__(platform_config=None)
                self.driver = MagicMock()
                self.checkCalls = 0
                self.autoBuyCalls = 0
            def check_availability(self, url: str) -> bool:
                self.checkCalls += 1
                if checkRaises is not None:
                    raise checkRaises
                return checkReturns
            def auto_buy(self, url: str, config) -> bool:
                self.autoBuyCalls += 1
                if autoBuyRaises is not None:
                    raise autoBuyRaises
                return True
        inst = _FakePlugin()
        inst.name = name
        return inst
    return _make
```

`requirements.txt` delta: add ONE line after the existing `pytest==8.3.4` line:

```
pytest-asyncio==1.3.0
```

`.gitignore` delta (append if not already present):

```
# SQLite WAL sidecar files (transient transaction data; never commit)
data/*.db-wal
data/*.db-shm
```

RED skeleton test files: each new test file imports the symbol it expects to exist and asserts behavior. The import or call MUST fail today (e.g. `from main import poll_plugin` -> ImportError because poll_plugin does not exist yet). That ImportError-at-collect counts as RED for the matching requirement.
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Install pytest-asyncio, configure auto mode, extend conftest, add .gitignore entries</name>
  <files>requirements.txt, pyproject.toml, .gitignore, tests/conftest.py</files>
  <read_first>
    - requirements.txt (current pins; see existing lines for pytest==8.3.4)
    - pyproject.toml (current [tool.pytest.ini_options] block if any)
    - tests/conftest.py (current shared fixtures from Phase 1)
    - .planning/phases/04-async-orchestrator/04-RESEARCH.md (sections: Wave 0 Gaps, Sample test patterns)
    - .planning/phases/01-foundations-security/01-01-test-infra-and-pinned-deps-SUMMARY.md (existing conftest structure)
  </read_first>
  <behavior>
    - `rtk pytest --collect-only -q` succeeds (no collection errors) AFTER skeleton files in Task 2 land. For THIS task alone, validate by running `rtk pytest -x -q` over the existing test suite (Phase 1/2/3 tests) and confirming zero regressions.
    - `python -c "import pytest_asyncio; print(pytest_asyncio.__version__)"` prints `1.3.0`.
    - `pyproject.toml` contains a `[tool.pytest.ini_options]` block with `asyncio_mode = "auto"`.
    - `tests/conftest.py` exposes `tmpDbPath`, `appConfigStub`, and `fakePluginFactory` fixtures importable via pytest's standard auto-discovery.
    - `.gitignore` contains both `data/*.db-wal` and `data/*.db-shm` patterns.
  </behavior>
  <action>
    1. Open `requirements.txt`. Append a single line `pytest-asyncio==1.3.0` directly after the existing `pytest==8.3.4` line. Do not reorder other lines. Run `rtk pip install -r requirements.txt` to install the new dep into the active venv.

    2. Open `pyproject.toml`. If `[tool.pytest.ini_options]` already exists, add `asyncio_mode = "auto"` inside it. If not, append the block shown in <interfaces>. Preserve any existing `testpaths` value (default to `["tests"]` if none).

    3. Open `tests/conftest.py`. Extend (do not replace) the existing file by appending the three fixtures shown in <interfaces>: `tmpDbPath`, `appConfigStub`, `fakePluginFactory`. Use camelCase for fixture names and inner attributes per CLAUDE.md. Imports go at the top of the file under existing imports.

    4. Open `.gitignore`. Search for `data/*.db-wal`. If absent, append the two-line WAL pattern block from <interfaces> at the end of the file with a leading blank line. Do not remove or reorder existing entries.

    5. Run `rtk pytest -x -q` over the existing suite. ALL pre-existing tests must still pass. Any regression here means the new conftest fixtures shadow an existing fixture; rename to disambiguate.

    6. Run `rtk pytest --version` to confirm pytest-asyncio plugin is loaded (pytest auto-discovers the plugin once installed; if version output does not show pytest-asyncio listed in the plugins line, the install failed).
  </action>
  <verify>
    <automated>rtk pip show pytest-asyncio</automated>
    <automated>rtk grep -n "asyncio_mode" pyproject.toml</automated>
    <automated>rtk grep -n "fakePluginFactory\|appConfigStub\|tmpDbPath" tests/conftest.py</automated>
    <automated>rtk grep -n "db-wal\|db-shm" .gitignore</automated>
    <automated>rtk pytest -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `pytest-asyncio==1.3.0` line present in requirements.txt (exactly one pin, no duplicates)
    - `asyncio_mode = "auto"` set inside `[tool.pytest.ini_options]` of pyproject.toml
    - tests/conftest.py exposes the three new fixtures with camelCase names
    - .gitignore covers data/*.db-wal and data/*.db-shm
    - Existing pytest suite remains green
    - Output of `rtk pip show pytest-asyncio` shows `Version: 1.3.0`
  </acceptance_criteria>
  <done>Async test framework installed, configured, and fixtures available for downstream RED tests</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Write RED skeleton tests for all five Phase 4 requirements</name>
  <files>tests/test_orchestrator.py, tests/test_purchase_writer.py, tests/test_registry_stagger.py, tests/test_models_wal.py, tests/test_plugin_shutdown.py</files>
  <read_first>
    - tests/conftest.py (fixtures from Task 1)
    - .planning/phases/04-async-orchestrator/04-RESEARCH.md (Sample test patterns; Phase Requirements -> Test Map)
    - main.py (current state; poll_plugin and purchase_writer DO NOT yet exist; this is expected)
    - plugin_base.py (current ABC; async shutdown does not yet exist)
    - plugin_registry.py (current discover; discover_async does not yet exist)
    - models.py (current sync layer; no WAL, no context manager)
  </read_first>
  <behavior>
    Each of the five new test files contains 2-3 RED tests targeting the requirements listed below. EVERY test must fail today, either at collection (ImportError because the imported symbol does not yet exist) or at execution (AttributeError / NotImplementedError on stub call). Failing at collection IS the intended RED state for symbols that do not yet exist.

    `tests/test_orchestrator.py` (covers ASYNC-01, ASYNC-03):
      - test_pluginCrashIsolated: import `poll_plugin` from main; spin two fake plugins inside a TaskGroup, one raising RuntimeError, verify the good plugin keeps being polled. EXPECTED FAIL: ImportError on `from main import poll_plugin`.
      - test_inputBridgedViaToThread: ast.parse main.py; assert no bare `input(` Call node exists inside any `async def` body. Allowed: `await asyncio.to_thread(input, ...)`. EXPECTED FAIL: current main.py main() is sync; once it becomes async without to_thread wrapping, this catches regressions. Today this passes trivially because main() is sync; the test must explicitly assert that `main` is an `AsyncFunctionDef` AND no bare input exists, so it FAILS today.
      - test_executorConfiguredBeforeTaskGroup: ast.parse main.py; locate the call to `loop.set_default_executor` and locate the `async with asyncio.TaskGroup() as tg`; assert set_default_executor line number < TaskGroup line number. EXPECTED FAIL: neither call exists in main.py yet.

    `tests/test_purchase_writer.py` (covers ASYNC-05):
      - test_writerDrainsQueue: import `purchase_writer` from main; put two URLs on a queue; monkey-patch `models.update_item_purchased` to record calls; assert both URLs flushed in order. EXPECTED FAIL: ImportError.
      - test_taskDoneOnFailure: same setup, but monkey-patch update_item_purchased to raise; assert queue.join() returns within 1 second (task_done was called in the finally block). EXPECTED FAIL: ImportError.

    `tests/test_registry_stagger.py` (covers ASYNC-02):
      - test_staggerBetweenPlugins: import `discover_async` from plugin_registry; monkey-patch `asyncio.sleep` to record sleep durations; build two stub `shopbot_plugin_*.py` files in tmp_path; call discover_async; assert recorded sleeps == [1.5] (one sleep between two plugins). EXPECTED FAIL: ImportError on discover_async.
      - test_firstPluginNoSleep: same setup with a single plugin; assert sleeps == [] (no sleep before first plugin). EXPECTED FAIL: ImportError.

    `tests/test_models_wal.py` (covers ASYNC-04):
      - test_journalModeIsWal: use `tmpDbPath` fixture; call `initialize_db(delete=True)`; open a fresh sqlite3 connection; assert `PRAGMA journal_mode` returns `wal`. EXPECTED FAIL: current models.py does not set WAL.
      - test_busyTimeoutApplied: any function in models that opens a connection (e.g. add_items via inspection of the _connect helper); assert the connection's busy_timeout PRAGMA is >= 5000ms after a write call. EXPECTED FAIL: no _connect helper exists; busy_timeout never set.
      - test_contextManagerRollback: import `_connect` from models; use it as a context manager; raise inside the block; reopen and assert the partial write was rolled back. EXPECTED FAIL: ImportError on `_connect`.

    `tests/test_plugin_shutdown.py` (covers D-04, supports ASYNC-01):
      - test_shutdownIsCoroutine: assert `inspect.iscoroutinefunction(RetailerPlugin.shutdown)` is True. EXPECTED FAIL: AttributeError (RetailerPlugin has no `shutdown` yet).
      - test_defaultShutdownQuitsDriver: subclass RetailerPlugin with a MagicMock driver; await `instance.shutdown()`; assert `driver.quit` was called once via to_thread. EXPECTED FAIL: AttributeError.
      - test_shutdownNoDriverAttribute: subclass without setting self.driver; await `instance.shutdown()`; assert it returns None without raising. EXPECTED FAIL: AttributeError.
  </behavior>
  <action>
    1. Create `tests/test_orchestrator.py`. Use `from main import poll_plugin, purchase_writer` at the top (this will ImportError at collect today; that is the RED signal). Add the three test functions described in <behavior>. Use `appConfigStub` and `fakePluginFactory` fixtures.

    2. Create `tests/test_purchase_writer.py`. Use `from main import purchase_writer` at the top. Add the two tests. Use `monkeypatch.setattr("models.update_item_purchased", recorder)` to capture calls.

    3. Create `tests/test_registry_stagger.py`. Use `from plugin_registry import discover_async` at the top. Add the two tests. Write the stub plugin files into `tmp_path` using textwrap.dedent so each file contains a minimal RetailerPlugin subclass with a unique domain_pattern.

    4. Create `tests/test_models_wal.py`. Use `from models import initialize_db, _connect` at the top. Add the three tests. Use `tmpDbPath` fixture.

    5. Create `tests/test_plugin_shutdown.py`. Use `from plugin_base import RetailerPlugin`. Add the three tests. Use `pytest_asyncio` features via `asyncio_mode = "auto"` (just declare `async def test_*` with no decorator).

    6. Run `rtk pytest -q tests/test_orchestrator.py tests/test_purchase_writer.py tests/test_registry_stagger.py tests/test_models_wal.py tests/test_plugin_shutdown.py`. EXPECT all five files to either fail at collection (ImportError) or fail at execution. Zero of these tests should PASS today.

    7. Run `rtk pytest -x -q --ignore=tests/test_orchestrator.py --ignore=tests/test_purchase_writer.py --ignore=tests/test_registry_stagger.py --ignore=tests/test_models_wal.py --ignore=tests/test_plugin_shutdown.py`. EXPECT all pre-existing Phase 1/2/3 tests still pass.

    8. Document the RED state at the bottom of each new test file as a module docstring header:
       ```
       """Phase 4 RED skeleton for ASYNC-0X (see 04-01-PLAN.md).
       All tests in this file are expected to FAIL until Plan 04-0Y lands.
       """
       ```
       This makes downstream plans aware that flipping these to GREEN is part of their acceptance criteria.
  </action>
  <verify>
    <automated>rtk pytest tests/test_orchestrator.py tests/test_purchase_writer.py tests/test_registry_stagger.py tests/test_models_wal.py tests/test_plugin_shutdown.py 2>&1 | rtk grep -E "FAILED|ERROR|error"</automated>
    <automated>rtk pytest -x -q --ignore=tests/test_orchestrator.py --ignore=tests/test_purchase_writer.py --ignore=tests/test_registry_stagger.py --ignore=tests/test_models_wal.py --ignore=tests/test_plugin_shutdown.py</automated>
    <automated>rtk grep -l "Phase 4 RED skeleton" tests/</automated>
  </verify>
  <acceptance_criteria>
    - All five new test files exist with the test functions listed in <behavior>
    - Every test in the five new files fails (collection or execution) today
    - Pre-existing Phase 1/2/3 test suite remains green
    - Each new file has the RED-skeleton module docstring header
    - No new file imports from amazon_bot or bestbuy_bot (deleted Phase 2)
    - Test names use camelCase per CLAUDE.md
  </acceptance_criteria>
  <done>Five RED test files committed; Waves 1 and 2 have failing-test targets to drive against</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| tests/conftest.py fixture shadowing | New camelCase fixtures must not silently mask existing Phase 1 fixtures |
| WAL sidecar files in git | Transient transaction data must be gitignored before WAL ships in Plan 04-02 |
| RED skeleton at collection time | Import errors at collection do not crash other tests; pytest reports as ERROR not affect unrelated test runs |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-04-01-WAL-COMMIT | Information Disclosure | data/*.db-wal | mitigate | .gitignore patterns added in Task 1 before WAL mode lands in Plan 04-02 |
| T-04-01-FIXTURE-SHADOW | Tampering | tests/conftest.py | mitigate | Task 1 runs full pytest suite to verify zero regressions; camelCase names reduce collision risk with existing snake_case fixtures |
| T-04-01-PARTIAL-INSTALL | Denial of Service | requirements.txt | accept | pytest-asyncio install failure is loud and obvious (pytest --version omits the plugin line); developer reruns pip install |
</threat_model>

<verification>
- `rtk pip show pytest-asyncio` returns `Version: 1.3.0`
- `rtk grep -n "asyncio_mode" pyproject.toml` matches `asyncio_mode = "auto"`
- `rtk grep -n "db-wal\|db-shm" .gitignore` matches both patterns
- `rtk pytest -x -q --ignore=tests/test_orchestrator.py --ignore=tests/test_purchase_writer.py --ignore=tests/test_registry_stagger.py --ignore=tests/test_models_wal.py --ignore=tests/test_plugin_shutdown.py` green
- `rtk pytest tests/test_orchestrator.py tests/test_purchase_writer.py tests/test_registry_stagger.py tests/test_models_wal.py tests/test_plugin_shutdown.py` shows FAIL or ERROR for every test (none PASS)
</verification>

<success_criteria>
- Async test framework operational (pytest-asyncio installed, auto-mode configured)
- Shared async fixtures available to all Wave 1/2 tests
- Five RED skeleton test files exist covering ASYNC-01..05 + D-04
- Pre-existing suite unaffected
- Phase 4 Waves 1 and 2 can run their plan-local pytest commands and flip RED tests to GREEN as the canonical signal of GREEN-phase completion
</success_criteria>

<output>
After completion, create `.planning/phases/04-async-orchestrator/04-01-SUMMARY.md`
</output>
