---
phase: 04-async-orchestrator
plan: 03
type: execute
wave: 1
depends_on: ["01"]
files_modified:
  - plugin_base.py
  - tests/test_plugin_shutdown.py
  - tests/test_plugin_base.py
autonomous: true
requirements:
  - ASYNC-01
tags:
  - python
  - abc
  - plugin-contract
  - asyncio
  - shutdown

must_haves:
  truths:
    - "RetailerPlugin defines `async def shutdown(self) -> None` as a non-abstract method (D-04)"
    - "Default shutdown body awaits asyncio.to_thread(self.driver.quit) when self.driver is present"
    - "Default shutdown no-ops cleanly when self.driver is None or unset (test stubs, check-only plugins without drivers)"
    - "Default shutdown catches and logs exceptions from driver.quit without re-raising (so one plugin's quit failure cannot block the orchestrator from shutting down the others)"
    - "PLUGIN_API_VERSION remains 1 (additive non-breaking change per D-04)"
    - "Existing Amazon and BestBuy plugins inherit the default shutdown unchanged — their plugin source files are NOT modified by this plan"
    - "tests/test_plugin_shutdown.py RED skeletons from Plan 04-01 are now GREEN"
    - "Existing tests/test_plugin_base.py contract tests still pass and gain one new test asserting shutdown is a coroutine function"
    - "inspect.iscoroutinefunction(RetailerPlugin.shutdown) returns True"
  artifacts:
    - path: "plugin_base.py"
      provides: "RetailerPlugin ABC with async shutdown default; PLUGIN_API_VERSION=1 preserved"
      contains: "async def shutdown"
      min_lines: 50
    - path: "tests/test_plugin_shutdown.py"
      provides: "GREEN tests for D-04: shutdown is coroutine, default quits driver via to_thread, no-driver no-ops, exception logged not raised"
      min_lines: 50
    - path: "tests/test_plugin_base.py"
      provides: "Existing ABC contract tests extended with one shutdown-coroutine assertion"
      contains: "iscoroutinefunction"
  key_links:
    - from: "RetailerPlugin.shutdown"
      to: "asyncio.to_thread(driver.quit)"
      via: "default implementation when self.driver is truthy"
      pattern: "asyncio.to_thread.*quit"
    - from: "plugin_base"
      to: "logger.writeLog"
      via: "exception logging inside shutdown default"
      pattern: "writeLog.*shutdown"
---

<objective>
Amend the RetailerPlugin ABC with a non-abstract `async def shutdown(self) -> None` defaulting to `await asyncio.to_thread(self.driver.quit)`. Subclasses with no driver inherit a no-op-safe default; subclasses with extra cleanup override and call `super().shutdown()`. This unblocks Plan 04-05's TaskGroup `finally` block where the orchestrator awaits `asyncio.shield(p.shutdown())` for each plugin.

Purpose: D-04 is the only plugin-contract change in Phase 4. It must land before Plan 04-05 (orchestrator rewrite) because the orchestrator's `finally` block calls `plugin.shutdown()` on each registered plugin. Done in Wave 1 in parallel with models.py (Plan 04-02) and registry stagger (Plan 04-04) because the three files do not overlap.

Output: amended plugin_base.py, GREEN tests in tests/test_plugin_shutdown.py, one new assertion in tests/test_plugin_base.py.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/04-async-orchestrator/04-CONTEXT.md
@.planning/phases/04-async-orchestrator/04-RESEARCH.md
@.planning/phases/04-async-orchestrator/04-01-async-test-infra-PLAN.md
@.planning/phases/01-foundations-security/01-02-plugin-abc-contract-SUMMARY.md
@.planning/phases/02-plugin-migration/02-01-SUMMARY.md
@plugin_base.py
@tests/test_plugin_shutdown.py
@tests/test_plugin_base.py
@logger.py
</context>

<interfaces>
Target `plugin_base.py` (full file, replacing current 49-line version):

```python
"""Retail plugin contract for ShopPyBot.

All retailer integrations subclass RetailerPlugin and implement the two
abstract methods (check_availability, auto_buy). login(), detect_captcha(),
and shutdown() have working defaults so check-only plugins do not need boilerplate.

Per D-01 (Phase 1 CONTEXT): ABC methods do NOT take a `driver` argument.
Subclasses construct `self.driver` in `__init__`.

Per Phase 4 D-04: `shutdown()` is an async coroutine; default implementation
awaits asyncio.to_thread(self.driver.quit) so the orchestrator can run all
plugin teardowns under asyncio.shield in a TaskGroup finally block.
"""
import asyncio
from abc import ABC, abstractmethod

from logger import writeLog

PLUGIN_API_VERSION: int = 1


class RetailerPlugin(ABC):
    """Abstract base for retail platform plugins.

    Subclasses MUST set `domain_pattern` to a non-empty list of hostnames
    (e.g. ["amazon.com", "amzn.to"]) and implement `check_availability` and
    `auto_buy`. Per Phase 2 D-03, set `login_at_startup = True` to opt in to
    a one-shot `.login()` call at startup before the polling loop begins.
    Per Phase 4 D-04, override `shutdown()` for extra teardown; call
    super().shutdown() at the end to inherit driver.quit cleanup.
    """

    domain_pattern: list[str] = []
    login_at_startup: bool = False
    name: str = ""

    def __init__(self, platform_config) -> None:
        self.platform_config = platform_config

    @abstractmethod
    def check_availability(self, url: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def auto_buy(self, url: str, config) -> bool:
        raise NotImplementedError

    def login(self, config) -> None:
        return None

    def detect_captcha(self) -> bool:
        return False

    async def shutdown(self) -> None:
        """Default cleanup: quit the Selenium driver in a worker thread.

        Override to add extra cleanup; call `await super().shutdown()` at the
        end. Plugins with no driver (test stubs, check-only) inherit the
        no-op-safe default. Exceptions from `driver.quit` are logged at
        WARNING and swallowed so one plugin's quit failure cannot block the
        orchestrator from shutting down the others.
        """
        driver = getattr(self, "driver", None)
        if driver is None:
            return
        try:
            await asyncio.to_thread(driver.quit)
        except Exception as e:
            writeLog(
                f"{type(self).__name__}.shutdown: driver.quit raised: {e}",
                "WARNING",
            )
```

Target `tests/test_plugin_shutdown.py` (replace RED skeleton from Plan 04-01):

```python
"""Phase 4 GREEN: tests for D-04 (async shutdown ABC default)."""
import asyncio
import inspect
from unittest.mock import MagicMock

import pytest

from plugin_base import RetailerPlugin


class _NoDriverPlugin(RetailerPlugin):
    domain_pattern = ["x.example"]
    def check_availability(self, url): return False
    def auto_buy(self, url, config): return False


class _WithDriverPlugin(RetailerPlugin):
    domain_pattern = ["y.example"]
    def __init__(self):
        super().__init__(platform_config=None)
        self.driver = MagicMock()
    def check_availability(self, url): return False
    def auto_buy(self, url, config): return False


def test_shutdownIsCoroutineFunction():
    assert inspect.iscoroutinefunction(RetailerPlugin.shutdown)


async def test_defaultShutdownQuitsDriver():
    plugin = _WithDriverPlugin()
    await plugin.shutdown()
    plugin.driver.quit.assert_called_once_with()


async def test_shutdownNoDriverAttribute():
    plugin = _NoDriverPlugin(platform_config=None)
    # No self.driver assigned; must not raise
    await plugin.shutdown()


async def test_shutdownSwallowsDriverQuitException(caplog):
    plugin = _WithDriverPlugin()
    plugin.driver.quit.side_effect = RuntimeError("driver hang")
    # Must NOT propagate; orchestrator depends on this contract for asyncio.gather(..., return_exceptions=True)
    await plugin.shutdown()
    plugin.driver.quit.assert_called_once_with()


async def test_subclassCanOverrideAndCallSuper():
    class _CustomCleanup(_WithDriverPlugin):
        def __init__(self):
            super().__init__()
            self.extraCleanupRan = False
        async def shutdown(self):
            self.extraCleanupRan = True
            await super().shutdown()
    plugin = _CustomCleanup()
    await plugin.shutdown()
    assert plugin.extraCleanupRan is True
    plugin.driver.quit.assert_called_once_with()
```

Existing `tests/test_plugin_base.py` extension: append ONE test (do not modify existing tests):

```python
def test_shutdownIsAsyncCoroutineFunction():
    """Phase 4 D-04: shutdown must be an async coroutine, not a sync method."""
    import inspect
    from plugin_base import RetailerPlugin
    assert inspect.iscoroutinefunction(RetailerPlugin.shutdown)
```
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add async shutdown default to RetailerPlugin ABC</name>
  <files>plugin_base.py</files>
  <read_first>
    - plugin_base.py (current 49-line ABC; ABC unchanged except shutdown addition)
    - .planning/phases/04-async-orchestrator/04-CONTEXT.md (D-04 lock)
    - .planning/phases/04-async-orchestrator/04-RESEARCH.md (Pattern 3)
    - .planning/phases/01-foundations-security/01-02-plugin-abc-contract-SUMMARY.md (ABC history; what changed in Phase 1)
    - .planning/phases/02-plugin-migration/02-01-SUMMARY.md (Phase 2 amendments to ABC: domain_pattern list, login_at_startup)
    - logger.py (writeLog signature)
  </read_first>
  <behavior>
    - PLUGIN_API_VERSION stays at 1 (D-04: additive non-breaking).
    - `shutdown` is `async def`, NOT decorated `@abstractmethod`.
    - Default body checks `getattr(self, "driver", None)` so plugins that never set self.driver do not AttributeError.
    - Default body wraps `driver.quit` in `await asyncio.to_thread(...)` (NEVER `driver.quit()` directly — Pitfall 1 in CONTEXT).
    - Exceptions from `driver.quit` are caught, logged at WARNING, and swallowed.
    - No changes to existing abstract methods (check_availability, auto_buy) or default methods (login, detect_captcha).
    - File remains under 300 lines.
  </behavior>
  <action>
    1. Replace the contents of `plugin_base.py` with the target shape shown in <interfaces>. Add the `import asyncio` and `from logger import writeLog` imports at the top.

    2. Confirm `PLUGIN_API_VERSION: int = 1` line is preserved exactly (D-04 explicitly says version stays at 1 because the change is additive).

    3. The `shutdown` method goes AFTER `detect_captcha` in the class body so the abstract methods come first, then default sync methods, then the new async default. This preserves a readable contract order.

    4. The `getattr(self, "driver", None)` guard handles three cases:
       - plugin has a driver: call quit via to_thread
       - plugin's __init__ never assigned self.driver: return None
       - plugin assigned self.driver = None for an explicit no-op: return None
       All three are acceptable per D-04.

    5. Verify Amazon and BestBuy plugins are NOT modified: they inherit the default. Run `rtk grep -n "def shutdown\|async def shutdown" plugins/` — expect no matches. If any match exists, the plugin author added their own shutdown in a previous phase; flag in summary, don't change.

    6. Run `rtk pytest -x -q tests/test_plugin_base.py`. All existing tests must pass. The new shutdown test will pass once Task 2 lands; for this task, just ensure no regressions.

    7. Static syntax check: `python -c "import ast; ast.parse(open('plugin_base.py').read())"` exits 0.

    8. Import smoke: `python -c "from plugin_base import RetailerPlugin, PLUGIN_API_VERSION; import inspect; assert PLUGIN_API_VERSION == 1; assert inspect.iscoroutinefunction(RetailerPlugin.shutdown)"` exits 0.
  </action>
  <verify>
    <automated>python -c "from plugin_base import RetailerPlugin, PLUGIN_API_VERSION; import inspect; assert PLUGIN_API_VERSION == 1; assert inspect.iscoroutinefunction(RetailerPlugin.shutdown); print('OK')"</automated>
    <automated>rtk grep -n "async def shutdown\|asyncio.to_thread\|PLUGIN_API_VERSION" plugin_base.py</automated>
    <automated>rtk grep -n "def shutdown\|async def shutdown" plugins/</automated>
    <automated>rtk pytest -x -q tests/test_plugin_base.py</automated>
  </verify>
  <acceptance_criteria>
    - plugin_base.py exports `RetailerPlugin.shutdown` as an async coroutine function
    - PLUGIN_API_VERSION still equals 1
    - Default body awaits asyncio.to_thread(driver.quit) when driver is truthy; returns silently when None
    - Exceptions from driver.quit are logged at WARNING and not re-raised
    - Amazon and BestBuy plugin files unchanged (no shutdown override added)
    - Existing Phase 1/2 plugin_base tests still pass
    - File parses as valid Python and under 300 lines
  </acceptance_criteria>
  <done>D-04 ABC amendment landed; PLUGIN_API_VERSION=1 preserved; existing plugins inherit default</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Flip tests/test_plugin_shutdown.py to GREEN; extend tests/test_plugin_base.py</name>
  <files>tests/test_plugin_shutdown.py, tests/test_plugin_base.py</files>
  <read_first>
    - tests/test_plugin_shutdown.py (RED skeleton from Plan 04-01)
    - tests/test_plugin_base.py (existing Phase 1/2 ABC tests)
    - plugin_base.py (GREEN after Task 1)
    - tests/conftest.py (asyncio_mode=auto means async def test_* runs without decorators)
  </read_first>
  <behavior>
    - tests/test_plugin_shutdown.py contains the five tests defined in <interfaces>: shutdownIsCoroutineFunction, defaultShutdownQuitsDriver, shutdownNoDriverAttribute, shutdownSwallowsDriverQuitException, subclassCanOverrideAndCallSuper.
    - tests/test_plugin_base.py gains ONE new test (test_shutdownIsAsyncCoroutineFunction) appended at the end. All existing tests in the file are unchanged.
    - All tests PASS.
    - asyncio_mode=auto (from Plan 04-01) makes `async def test_*` collect and run as asyncio tests without `@pytest.mark.asyncio`.
  </behavior>
  <action>
    1. Replace contents of `tests/test_plugin_shutdown.py` (RED skeleton from Plan 04-01) with the GREEN suite shown in <interfaces>. Update the module docstring from "RED skeleton" to "Phase 4 GREEN".

    2. The two test subclasses (_NoDriverPlugin, _WithDriverPlugin) live at module scope so they are reusable across tests in the file. Both implement the two abstract methods minimally.

    3. The `test_shutdownSwallowsDriverQuitException` test uses `caplog` fixture from pytest to optionally assert on the WARNING log line, but the primary assertion is that `await plugin.shutdown()` returns normally (does not raise).

    4. Open `tests/test_plugin_base.py` and APPEND the single test shown in <interfaces> at the end of the file. Do NOT modify or reorder existing tests.

    5. Run `rtk pytest -x -q tests/test_plugin_shutdown.py tests/test_plugin_base.py`. Expect all tests PASS.

    6. Run full suite `rtk pytest -x -q`. Must remain green.
  </action>
  <verify>
    <automated>rtk pytest -x -q tests/test_plugin_shutdown.py tests/test_plugin_base.py</automated>
    <automated>rtk pytest -x -q</automated>
    <automated>rtk grep -n "iscoroutinefunction" tests/test_plugin_base.py tests/test_plugin_shutdown.py</automated>
  </verify>
  <acceptance_criteria>
    - tests/test_plugin_shutdown.py has 5 PASSING tests
    - tests/test_plugin_base.py gained 1 new PASSING test (test_shutdownIsAsyncCoroutineFunction)
    - No existing tests in test_plugin_base.py were modified
    - Full pytest suite green
    - asyncio_mode=auto picks up async def test_* without decorator (verifies Plan 04-01 wiring)
  </acceptance_criteria>
  <done>D-04 fully covered by tests; ABC contract change verified across both test files</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| async vs sync shutdown contract | If any plugin overrides shutdown as `def` instead of `async def`, the orchestrator's `await plugin.shutdown()` raises TypeError ("object NoneType can't be used in 'await' expression"); test contract catches this |
| driver.quit exception propagation | One plugin's hung driver must not block the orchestrator from shutting down the others; default impl swallows exceptions and logs |
| plugin API version drift | PLUGIN_API_VERSION must stay at 1 because the change is additive (existing plugins compile); contributor docs in PLUGIN_DEV.md need a separate note in a future doc-only plan, not here |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-04-03-SYNC-OVERRIDE | Tampering | future plugin overrides shutdown with `def` instead of `async def` | mitigate | test_shutdownIsAsyncCoroutineFunction asserts at module level; per-plugin tests can re-use the same check. orchestrator try/except in asyncio.gather(..., return_exceptions=True) limits blast radius |
| T-04-03-QUIT-HANG | Denial of Service | driver.quit hangs blocking shutdown | mitigate | asyncio.to_thread runs quit in a worker thread; orchestrator's asyncio.shield + outer timeout (Plan 04-05) bounds total shutdown duration |
| T-04-03-EXC-PROPAGATION | Denial of Service | quit raises, blocks sibling shutdown | mitigate | Default impl catches Exception, logs WARNING, swallows. asyncio.gather(..., return_exceptions=True) at the orchestrator collects results |
| T-04-03-MISSING-DRIVER | Tampering | test stub plugins without self.driver | accept | getattr(self, "driver", None) guard returns silently. Test test_shutdownNoDriverAttribute proves the behavior |
| T-04-03-API-VERSION-BUMP | Repudiation | future contributor bumps PLUGIN_API_VERSION unnecessarily | mitigate | This plan asserts version stays 1; test_shutdownIsAsyncCoroutineFunction also imports PLUGIN_API_VERSION indirectly. Doc-level reinforcement deferred to a Phase 5+ docs update |
</threat_model>

<verification>
- `python -c "from plugin_base import RetailerPlugin; import inspect; assert inspect.iscoroutinefunction(RetailerPlugin.shutdown)"` exits 0
- `rtk grep -n "PLUGIN_API_VERSION" plugin_base.py` shows `PLUGIN_API_VERSION: int = 1` exactly once
- `rtk grep -n "def shutdown\|async def shutdown" plugins/` returns no matches (Amazon and BestBuy plugins unchanged)
- `rtk pytest -x -q tests/test_plugin_shutdown.py tests/test_plugin_base.py` shows all tests PASS
- `rtk pytest -x -q` full suite green
</verification>

<success_criteria>
- D-04 implemented exactly: async def shutdown default with to_thread(driver.quit), no-driver no-op, exception logged not raised
- PLUGIN_API_VERSION = 1 unchanged (additive change confirmed by no version bump)
- Existing Amazon and BestBuy plugin files untouched (inherit default)
- 5 new tests in tests/test_plugin_shutdown.py PASS; 1 new test in tests/test_plugin_base.py PASS
- ABC ready for Plan 04-05 to call `await asyncio.shield(p.shutdown())` in the orchestrator finally block
- ASYNC-01 cleanup guarantee gains its plugin-side contract
</success_criteria>

<output>
After completion, create `.planning/phases/04-async-orchestrator/04-03-SUMMARY.md`
</output>
