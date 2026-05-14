---
phase: 04-async-orchestrator
plan: 04
type: execute
wave: 1
depends_on: ["01"]
files_modified:
  - plugin_registry.py
  - tests/test_registry_stagger.py
  - tests/test_plugin_registry.py
autonomous: true
requirements:
  - ASYNC-02
tags:
  - python
  - asyncio
  - plugin-registry
  - stagger
  - discovery

must_haves:
  truths:
    - "plugin_registry exports `async def discover_async(plugins_dir, *, app_config, cvvs, stagger_seconds=1.5)`"
    - "discover_async sleeps `stagger_seconds` BEFORE each plugin instantiation except the first (Pitfall 7: sleep must straddle driver construction, not happen after)"
    - "First plugin: no sleep before instantiation"
    - "Between plugin N and N+1 (N >= 1): exactly one `await asyncio.sleep(stagger_seconds)`"
    - "discover_async runs each `_instantiate(...)` call inside `await asyncio.to_thread(...)` (because plugin __init__ calls build_driver which is blocking Selenium)"
    - "Per-plugin import/instantiation failures are still logged as WARNING and skipped (D-04 Phase A lenient behavior preserved from existing sync discover)"
    - "Existing sync `discover()` function REMAINS in plugin_registry.py unchanged (for backwards-compat with any tests still using it; Plan 04-05 main.py will switch to discover_async)"
    - "All RED tests in tests/test_registry_stagger.py written in Plan 04-01 now PASS"
    - "Existing tests/test_plugin_registry.py continues to pass (no regressions in sync discover, route_url, verify_coverage)"
  artifacts:
    - path: "plugin_registry.py"
      provides: "Sync discover + async discover_async with 1.5s stagger; shared helpers"
      contains: "async def discover_async"
      min_lines: 150
    - path: "tests/test_registry_stagger.py"
      provides: "GREEN tests for ASYNC-02: stagger between plugins, no sleep before first, stagger_seconds override"
      min_lines: 50
    - path: "tests/test_plugin_registry.py"
      provides: "Existing Phase 2 registry tests preserved"
      contains: "discover"
  key_links:
    - from: "plugin_registry.discover_async"
      to: "asyncio.sleep(stagger_seconds)"
      via: "between instantiations, not before first or after last"
      pattern: "asyncio.sleep"
    - from: "plugin_registry.discover_async"
      to: "asyncio.to_thread(_instantiate, ...)"
      via: "every plugin instantiation runs on a worker thread (Selenium driver init blocks)"
      pattern: "asyncio.to_thread.*_instantiate\\|_load_and_instantiate"
---

<objective>
Add `async def discover_async(...)` to plugin_registry.py that runs sequential plugin instantiation with a 1.5s `await asyncio.sleep` between each, satisfying ASYNC-02 and respecting CONTEXT Pitfall 7 (sleep must happen BEFORE the next driver construction, not after). The sync `discover()` stays as-is for backwards compatibility; Plan 04-05 will switch main.py to discover_async.

Purpose: ChromeDriver allocates an ephemeral TCP port at `webdriver.Chrome(...)` startup. On Windows this bind window has been observed to race when two plugins are instantiated within microseconds. ASYNC-02 mandates a 1.5s stagger between WebDriver instances. Doing this inside `plugin_registry.discover_async` keeps the orchestrator (Plan 04-05) clean: it just awaits the registry once and gets back a fully-staggered list of ready plugins. Done in Wave 1 in parallel with Plans 04-02 and 04-03 because the three files (models.py, plugin_base.py, plugin_registry.py) do not overlap.

Output: extended plugin_registry.py with discover_async + shared helpers, GREEN tests in tests/test_registry_stagger.py, preserved tests/test_plugin_registry.py.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/04-async-orchestrator/04-CONTEXT.md
@.planning/phases/04-async-orchestrator/04-RESEARCH.md
@.planning/phases/04-async-orchestrator/04-01-async-test-infra-PLAN.md
@.planning/phases/02-plugin-migration/02-01-SUMMARY.md
@plugin_registry.py
@tests/test_registry_stagger.py
@tests/test_plugin_registry.py
</context>

<interfaces>
Target `plugin_registry.py` additions (extend; do not modify existing public functions):

```python
# Add at top alongside existing imports:
import asyncio

DEFAULT_STAGGER_SECONDS: float = 1.5


def _iter_plugin_paths(plugins_dir: Path):
    """Internal: yield sorted plugin file paths, skipping non-conforming files."""
    for path in sorted(Path(plugins_dir).glob("*.py")):
        if path.name.startswith("_") or path.name == "__init__.py":
            continue
        if not path.stem.startswith(PLUGIN_PREFIX):
            writeLog(
                f"Skipped {path.name} (not auto-loaded; copy to "
                f"{PLUGIN_PREFIX}<name>.py to enable)",
                "INFO",
            )
            continue
        yield path


def _load_and_instantiate(path: Path, app_config, cvvs):
    """Internal: load module, find plugin class, instantiate. Returns instance or None."""
    try:
        cls = _load_plugin_class(path)
    except Exception as e:
        writeLog(f"Failed to load {path.name}: {e}", "WARNING")
        return None
    name = getattr(cls, "name", "") or path.stem.removeprefix(PLUGIN_PREFIX)
    try:
        inst = _instantiate(cls, name, app_config, cvvs)
    except Exception as e:
        writeLog(
            f"Failed to instantiate {cls.__name__} from {path.name}: {e}",
            "WARNING",
        )
        return None
    inst.name = name
    return inst


async def discover_async(
    plugins_dir: Path,
    *,
    app_config,
    cvvs: dict[str, str],
    stagger_seconds: float = DEFAULT_STAGGER_SECONDS,
) -> list[RetailerPlugin]:
    """Async plugin discovery with a `stagger_seconds` sleep between plugins.

    The sleep happens BEFORE each plugin's `_instantiate` (Pitfall 7) so the
    chromedriver TCP bind window cannot race with the next plugin. The first
    plugin instantiates immediately with no leading sleep.

    Per-plugin failures are logged as WARNING and skipped (D-04 Phase A).
    """
    instances: list[RetailerPlugin] = []
    paths = list(_iter_plugin_paths(plugins_dir))
    for index, path in enumerate(paths):
        if index > 0:
            await asyncio.sleep(stagger_seconds)
        inst = await asyncio.to_thread(
            _load_and_instantiate, path, app_config, cvvs
        )
        if inst is not None:
            instances.append(inst)
    return instances
```

The existing sync `discover()` function should be refactored INTERNALLY to use `_iter_plugin_paths` and `_load_and_instantiate` so both code paths share helpers; the public signature and behavior of sync `discover()` remain identical (existing tests must still pass).

Refactored sync `discover()`:

```python
def discover(plugins_dir: Path, *, app_config, cvvs: dict[str, str]) -> list[RetailerPlugin]:
    """Sync plugin discovery (preserved for backwards compat; Plan 04-05 uses discover_async)."""
    instances: list[RetailerPlugin] = []
    for path in _iter_plugin_paths(plugins_dir):
        inst = _load_and_instantiate(path, app_config, cvvs)
        if inst is not None:
            instances.append(inst)
    return instances
```

Target `tests/test_registry_stagger.py` GREEN suite (replace RED skeleton from Plan 04-01):

```python
"""Phase 4 GREEN: tests for ASYNC-02 (1.5s stagger in discover_async)."""
import asyncio
import textwrap
from pathlib import Path

import pytest

from plugin_registry import discover_async, DEFAULT_STAGGER_SECONDS


PLUGIN_TEMPLATE = textwrap.dedent("""\
    from plugin_base import RetailerPlugin

    class {className}(RetailerPlugin):
        domain_pattern = ["{domain}"]
        def __init__(self, platform_config=None, cvv=None, driver_path=None):
            super().__init__(platform_config=platform_config)
        def check_availability(self, url): return False
        def auto_buy(self, url, config): return False
""")


def _writePlugin(directory: Path, slug: str, className: str, domain: str) -> None:
    (directory / f"shopbot_plugin_{slug}.py").write_text(
        PLUGIN_TEMPLATE.format(className=className, domain=domain)
    )


@pytest.fixture
def fakeAsyncSleep(monkeypatch):
    sleeps: list[float] = []
    async def _fake(delay):
        sleeps.append(delay)
    monkeypatch.setattr("plugin_registry.asyncio.sleep", _fake)
    return sleeps


async def test_staggerBetweenTwoPlugins(tmp_path, fakeAsyncSleep):
    _writePlugin(tmp_path, "alpha", "Alpha", "alpha.example")
    _writePlugin(tmp_path, "beta", "Beta", "beta.example")
    plugins = await discover_async(tmp_path, app_config=None, cvvs={})
    assert len(plugins) == 2
    assert fakeAsyncSleep == [DEFAULT_STAGGER_SECONDS]


async def test_firstPluginNoSleep(tmp_path, fakeAsyncSleep):
    _writePlugin(tmp_path, "alpha", "Alpha", "alpha.example")
    plugins = await discover_async(tmp_path, app_config=None, cvvs={})
    assert len(plugins) == 1
    assert fakeAsyncSleep == []


async def test_staggerOverride(tmp_path, fakeAsyncSleep):
    _writePlugin(tmp_path, "a", "A", "a.example")
    _writePlugin(tmp_path, "b", "B", "b.example")
    _writePlugin(tmp_path, "c", "C", "c.example")
    await discover_async(tmp_path, app_config=None, cvvs={}, stagger_seconds=0.25)
    assert fakeAsyncSleep == [0.25, 0.25]


async def test_failedInstantiationStillStaggersNext(tmp_path, fakeAsyncSleep):
    """A plugin that fails to load does NOT skip the stagger before the NEXT plugin
    (the failed import still consumed Selenium-startup-equivalent time conceptually;
    even though the bind window only opens on successful build_driver, we keep
    the contract simple: sleep happens between every path-iteration boundary)."""
    _writePlugin(tmp_path, "ok", "Ok", "ok.example")
    # Deliberately broken plugin: import-time error
    (tmp_path / "shopbot_plugin_broken.py").write_text("raise RuntimeError('broken')\n")
    _writePlugin(tmp_path, "good", "Good", "good.example")
    plugins = await discover_async(tmp_path, app_config=None, cvvs={})
    assert len(plugins) == 2  # broken skipped, two good ones returned
    # Two stagger sleeps recorded (one before "broken", one before "good")
    assert fakeAsyncSleep == [DEFAULT_STAGGER_SECONDS, DEFAULT_STAGGER_SECONDS]
```
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add discover_async + shared helpers to plugin_registry.py</name>
  <files>plugin_registry.py</files>
  <read_first>
    - plugin_registry.py (current 159-line file; preserve sync discover, route_url, verify_coverage)
    - .planning/phases/04-async-orchestrator/04-CONTEXT.md (D-04 Phase A lenient discovery; Pitfall 7 on stagger site)
    - .planning/phases/04-async-orchestrator/04-RESEARCH.md (Pattern 5; Q7)
    - .planning/phases/02-plugin-migration/02-01-SUMMARY.md (sync discover semantics; D-04 Phase A)
  </read_first>
  <behavior>
    - plugin_registry.py exports `discover_async`, `DEFAULT_STAGGER_SECONDS`, and the existing public functions (`discover`, `route_url`, `verify_coverage`).
    - Two new private helpers (`_iter_plugin_paths`, `_load_and_instantiate`) are shared between sync `discover` and async `discover_async`.
    - Sync `discover` is refactored INTERNALLY to use the new helpers; its public signature and behavior are bit-identical.
    - `discover_async` runs each `_load_and_instantiate` call via `await asyncio.to_thread(...)` so blocking Selenium driver construction in plugin __init__ does not stall the event loop.
    - Sleep occurs BEFORE each plugin past the first; first plugin: no sleep.
    - Per-plugin failures still log WARNING and skip the plugin (no crash, no aborted discovery).
    - File remains under 300 lines.
    - All functions still under 30 lines.
  </behavior>
  <action>
    1. Open `plugin_registry.py`. Add `import asyncio` at the top alongside existing imports.

    2. Add `DEFAULT_STAGGER_SECONDS: float = 1.5` at module scope below `PLUGIN_PREFIX`.

    3. Extract `_iter_plugin_paths` and `_load_and_instantiate` helpers from the existing sync `discover` (see <interfaces>). The helpers preserve every behavior of the inline loop body in the original `discover`: skip private files, log INFO and skip for non-conforming names, log WARNING and skip on load failure, log WARNING and skip on instantiate failure.

    4. Refactor sync `discover` to call the two helpers. The function body becomes a small loop that appends successful instances. Public signature unchanged.

    5. Add `async def discover_async(...)` per <interfaces>. Note: the `await asyncio.sleep(stagger_seconds)` runs BEFORE the next `_load_and_instantiate` call (Pitfall 7). First plugin: index == 0, skip sleep.

    6. Wrap `_load_and_instantiate` in `await asyncio.to_thread(...)` inside `discover_async` because plugin `__init__` runs `build_driver(...)` which is blocking Selenium I/O.

    7. Sanity-check existing sync `discover` callers: run `rtk grep -n "from plugin_registry import\|plugin_registry.discover" main.py tests/`. All current usages either import or call sync `discover` — make sure refactor preserves behavior. Existing tests in tests/test_plugin_registry.py exercise sync `discover` and must remain green.

    8. Run `rtk pytest -x -q tests/test_plugin_registry.py`. Expected: PASS (this Task does not touch the test file).

    9. Run `python -c "import asyncio; from plugin_registry import discover_async, DEFAULT_STAGGER_SECONDS; assert DEFAULT_STAGGER_SECONDS == 1.5; print('OK')"`.

    10. Run full suite `rtk pytest -x -q --ignore=tests/test_registry_stagger.py`. Stagger tests are still RED until Task 2 lands; everything else must stay green.
  </action>
  <verify>
    <automated>rtk grep -n "discover_async\|DEFAULT_STAGGER_SECONDS\|_iter_plugin_paths\|_load_and_instantiate\|asyncio.sleep\|asyncio.to_thread" plugin_registry.py</automated>
    <automated>python -c "from plugin_registry import discover, discover_async, DEFAULT_STAGGER_SECONDS, route_url, verify_coverage; import inspect; assert inspect.iscoroutinefunction(discover_async); print('OK')"</automated>
    <automated>rtk pytest -x -q tests/test_plugin_registry.py</automated>
    <automated>rtk pytest -x -q --ignore=tests/test_registry_stagger.py</automated>
  </verify>
  <acceptance_criteria>
    - plugin_registry.py exports `discover_async` as an async coroutine function
    - `DEFAULT_STAGGER_SECONDS = 1.5` defined at module scope
    - Two new private helpers `_iter_plugin_paths` and `_load_and_instantiate` exist
    - Sync `discover` refactored to use the helpers; public behavior unchanged
    - tests/test_plugin_registry.py still passes (sync discover regression check)
    - File under 300 lines; all functions under 30 lines
    - main.py imports unchanged this plan (Plan 04-05 switches to discover_async)
  </acceptance_criteria>
  <done>discover_async ready with proper stagger placement; sync discover preserved for compat</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Flip tests/test_registry_stagger.py to GREEN</name>
  <files>tests/test_registry_stagger.py</files>
  <read_first>
    - tests/test_registry_stagger.py (RED skeleton from Plan 04-01)
    - plugin_registry.py (GREEN after Task 1)
    - tests/conftest.py (no special fixtures needed for these tests; tmp_path is pytest built-in)
    - .planning/phases/04-async-orchestrator/04-RESEARCH.md (Sample test patterns)
  </read_first>
  <behavior>
    - tests/test_registry_stagger.py contains the four tests defined in <interfaces>: staggerBetweenTwoPlugins, firstPluginNoSleep, staggerOverride, failedInstantiationStillStaggersNext.
    - All tests PASS.
    - `fakeAsyncSleep` fixture monkeypatches `plugin_registry.asyncio.sleep` (not `asyncio.sleep` at module global scope) so we intercept the exact symbol discover_async calls.
    - Each test writes minimal stub plugin files (single class with empty domain_pattern entry) to tmp_path; the registry loads, instantiates, and returns them with NO real chromedriver involvement.
  </behavior>
  <action>
    1. Replace contents of `tests/test_registry_stagger.py` (RED skeleton from Plan 04-01) with the GREEN suite shown in <interfaces>. Update module docstring from "RED skeleton" to "Phase 4 GREEN".

    2. The `PLUGIN_TEMPLATE` constant uses `textwrap.dedent` to keep test source readable. The template's plugin class accepts the `platform_config`, `cvv`, and `driver_path` kwargs that `_instantiate` passes (see plugin_registry.py:_instantiate function for the signature) so instantiation does not fail.

    3. `fakeAsyncSleep` monkeypatches `plugin_registry.asyncio.sleep` — NOT `asyncio.sleep` globally — so other parts of the test framework (pytest-asyncio internals, etc.) are not affected.

    4. `test_failedInstantiationStillStaggersNext` deliberately writes a `shopbot_plugin_broken.py` containing `raise RuntimeError('broken')` at module scope. The registry's `_load_and_instantiate` catches this, logs WARNING, and returns None — but the path iteration continues, and the stagger sleep BEFORE the next path-iteration still happens. This documents the intentional contract: sleep is per path-iteration, not per successful load. If a future change re-orders to "sleep only when prior plugin succeeded", this test will catch it and require explicit re-approval.

    5. Run `rtk pytest -x -q tests/test_registry_stagger.py`. Expect 4 PASS.

    6. Run full suite `rtk pytest -x -q`. Must remain green.
  </action>
  <verify>
    <automated>rtk pytest -x -q tests/test_registry_stagger.py</automated>
    <automated>rtk pytest -x -q</automated>
    <automated>rtk grep -n "fakeAsyncSleep\|staggerBetweenTwoPlugins\|firstPluginNoSleep" tests/test_registry_stagger.py</automated>
  </verify>
  <acceptance_criteria>
    - tests/test_registry_stagger.py has 4 PASSING tests
    - fakeAsyncSleep fixture intercepts sleep calls correctly
    - Failed-instantiation case documented + tested
    - Full pytest suite green
    - ASYNC-02 GREEN
  </acceptance_criteria>
  <done>ASYNC-02 fully covered; discover_async ready for Plan 04-05 to consume</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| chromedriver TCP bind race window | Two webdriver.Chrome() calls within microseconds can collide on the ephemeral port assignment; the 1.5s stagger sits before driver construction in discover_async |
| sync `discover` regression | Existing tests pass sync `discover` to the old code path; refactoring must preserve all behavior |
| event-loop-blocking driver construction | Plugin __init__ runs build_driver which blocks the event loop if called directly; to_thread wrapper offloads to a worker thread |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-04-04-PORT-RACE | Denial of Service | webdriver.Chrome TCP bind | mitigate | asyncio.sleep(1.5) between each plugin's _load_and_instantiate; verified by test_staggerBetweenTwoPlugins |
| T-04-04-LOOP-STALL | Denial of Service | event loop blocks during driver init | mitigate | _load_and_instantiate wrapped in asyncio.to_thread inside discover_async |
| T-04-04-SYNC-REGRESSION | Tampering | shared helpers altering sync discover behavior | mitigate | tests/test_plugin_registry.py preserved and green; static refactor pattern (extract-method) keeps semantics |
| T-04-04-STAGGER-AFTER | Tampering | future change moves sleep after driver construction | mitigate | test_staggerBetweenTwoPlugins asserts the first plugin has zero leading sleeps; test_failedInstantiationStillStaggersNext locks in the contract that sleeps happen per path-iteration boundary |
| T-04-04-SLEEP-OMISSION | Denial of Service | future change removes the asyncio.sleep call | mitigate | All three GREEN tests assert exact sleep durations; any removal breaks all three |
</threat_model>

<verification>
- `python -c "from plugin_registry import discover_async; import inspect; assert inspect.iscoroutinefunction(discover_async); print('OK')"` exits 0
- `rtk grep -n "DEFAULT_STAGGER_SECONDS\s*=\s*1\.5" plugin_registry.py` matches
- `rtk grep -n "asyncio.sleep\|asyncio.to_thread" plugin_registry.py` matches inside discover_async
- `rtk pytest -x -q tests/test_registry_stagger.py tests/test_plugin_registry.py` all pass
- `rtk pytest -x -q` full suite green
</verification>

<success_criteria>
- ASYNC-02 fully satisfied: 1.5s stagger between plugin instantiations
- Sleep placement is BEFORE driver construction (Pitfall 7 honored)
- Sync `discover` regression-free; shared helpers extracted cleanly
- 4 GREEN tests cover stagger between plugins, no leading sleep, override parameter, failed-instantiation case
- discover_async signature matches the orchestrator's needs for Plan 04-05
</success_criteria>

<output>
After completion, create `.planning/phases/04-async-orchestrator/04-04-SUMMARY.md`
</output>
