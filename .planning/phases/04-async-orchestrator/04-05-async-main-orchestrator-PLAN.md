---
phase: 04-async-orchestrator
plan: 05
type: execute
wave: 2
depends_on: ["01", "02", "03", "04"]
files_modified:
  - main.py
  - config_schema.py
  - tests/test_orchestrator.py
  - tests/test_purchase_writer.py
  - tests/test_main_smoke.py
autonomous: true
requirements:
  - ASYNC-01
  - ASYNC-03
  - ASYNC-05
tags:
  - python
  - asyncio
  - taskgroup
  - orchestrator
  - main
  - integration

must_haves:
  truths:
    - "main.py defines `async def main()` (not sync); `if __name__ == '__main__': asyncio.run(main())` is the only top-level entrypoint (D-02 supersedes literal asyncio.Event wording in ASYNC-03)"
    - "main() installs a shared ThreadPoolExecutor sized max(4, len(registry)*2) via loop.set_default_executor BEFORE the TaskGroup opens (Pitfall: executor must exist before first to_thread call inside TaskGroup)"
    - "main() awaits `registry = await discover_async(Path('plugins'), app_config=app_config, cvvs=cvvs)` from Plan 04-04"
    - "main() iterates registry and runs `await asyncio.to_thread(plugin.login, app_config)` SEQUENTIALLY for every plugin with login_at_startup=True (preserves Phase 2 D-03; serializes stdin contention per Pitfall 11)"
    - "main() opens `async with asyncio.TaskGroup() as tg:` and creates one task per plugin via `poll_plugin(...)` plus one task for `purchase_writer(...)`"
    - "poll_plugin wraps the per-iteration body in try/except Exception that logs ERROR and continues; CancelledError is re-raised (Pitfall 1: TaskGroup cancels siblings on unhandled Exception)"
    - "poll_plugin uses `await asyncio.to_thread(plugin.check_availability, link)` and `await asyncio.to_thread(plugin.auto_buy, link, app_config)` (D-01: plugin methods stay sync; orchestrator bridges via to_thread)"
    - "purchase_writer is a critical task: its body is NOT wrapped in defensive try/except; Pitfall 10 — its crash MUST tear down the TaskGroup so the bot stops. Only the `update_item_purchased` call itself has try/except/finally so that `queue.task_done()` always runs even on write failure"
    - "After successful auto_buy, poll_plugin enqueues the URL via `await purchase_queue.put((link,))` instead of calling update_item_purchased directly (D-03)"
    - "purchase_queue is `asyncio.Queue(maxsize=100)` (D-03 bound)"
    - "main() finally-block awaits `asyncio.gather(*(asyncio.shield(p.shutdown()) for p in registry), return_exceptions=True)` (D-04 + Pitfall 4: shield prevents Ctrl-C during shutdown from leaving orphaned chromedriver.exe)"
    - "main() finally-block also calls `executor.shutdown(wait=True, cancel_futures=False)` so the ThreadPoolExecutor drains cleanly"
    - "main() catches KeyboardInterrupt at the asyncio.run boundary and exits cleanly with no traceback (Pitfall 6: Windows signal handling)"
    - "Windows compatibility: main.py sets `asyncio.WindowsSelectorEventLoopPolicy()` on Windows (Pitfall 6: ProactorEventLoop has fragile Ctrl-C; SelectorEventLoop is fine because the project does not use subprocess pipes)"
    - "main.py contains ZERO bare `input(...)` calls (D-02: all input via asyncio.to_thread); poll_plugin and any CAPTCHA pause go through to_thread"
    - "main.py contains ZERO `time.sleep(...)` calls in async paths (Pitfall 9: only await asyncio.sleep allowed)"
    - "main.py polling cadence read from `app_config.app.delay` (new field defaulting to 5.0)"
    - "config_schema.AppConfig gains a new nested `app: AppConfig.AppSettings` section with `delay: float = 5.0` (default preserves current implicit behavior; users can override via env or YAML)"
    - "All RED tests from Plan 04-01 in tests/test_orchestrator.py and tests/test_purchase_writer.py now PASS"
    - "tests/test_main_smoke.py (from Phase 2) gains new tests asserting async refactor: main is async, executor set before TaskGroup, no bare input in async paths, no time.sleep in main.py"
    - "Full pytest suite remains green across Phase 1/2/3/4"
  artifacts:
    - path: "main.py"
      provides: "Async orchestrator with TaskGroup, ThreadPoolExecutor, purchase_writer, asyncio.shield shutdown, Windows signal handling"
      contains: "async def main"
      min_lines: 150
    - path: "config_schema.py"
      provides: "AppConfig extended with app.delay field"
      contains: "delay: float"
    - path: "tests/test_orchestrator.py"
      provides: "GREEN tests for ASYNC-01 (concurrent polling, crash isolation, executor ordering) and ASYNC-03 (no bare input in async paths)"
      min_lines: 80
    - path: "tests/test_purchase_writer.py"
      provides: "GREEN tests for ASYNC-05 (queue drain, task_done on failure)"
      min_lines: 50
    - path: "tests/test_main_smoke.py"
      provides: "Phase 2 smoke tests + Phase 4 async assertions"
      contains: "AsyncFunctionDef"
  key_links:
    - from: "main.main"
      to: "discover_async"
      via: "await plugin_registry.discover_async(...) at startup"
      pattern: "await\\s+discover_async"
    - from: "main.main"
      to: "asyncio.TaskGroup"
      via: "async with asyncio.TaskGroup() as tg"
      pattern: "TaskGroup"
    - from: "main.poll_plugin"
      to: "asyncio.to_thread"
      via: "wraps plugin.check_availability and plugin.auto_buy"
      pattern: "to_thread\\(.*plugin\\."
    - from: "main.poll_plugin"
      to: "purchase_queue.put"
      via: "after successful auto_buy"
      pattern: "queue\\.put"
    - from: "main.purchase_writer"
      to: "asyncio.to_thread(update_item_purchased"
      via: "drain queue and write through models.py"
      pattern: "to_thread.*update_item_purchased"
    - from: "main.main finally"
      to: "asyncio.shield(p.shutdown())"
      via: "asyncio.gather under shield for each plugin"
      pattern: "asyncio\\.shield.*shutdown"
---

<objective>
Rewrite `main.py` from a sync `while True` loop into an `async def main()` that drives all plugins concurrently inside `asyncio.TaskGroup`. Bridge blocking Selenium calls via `asyncio.to_thread`. Serialize SQLite writes through a single `purchase_writer` task draining an `asyncio.Queue`. Replace every blocking `input(...)` in the async path with `asyncio.to_thread(input, prompt)`. Guarantee Ctrl-C cleanup via `asyncio.shield(p.shutdown())` for every plugin. Flip every remaining RED test from Plan 04-01 to GREEN.

Purpose: This is the Wave 2 integration plan. It depends on the GREEN outputs of Plans 04-02 (WAL models), 04-03 (async shutdown ABC), and 04-04 (discover_async stagger). With all three of those landed, this plan stitches them together at the entrypoint. After this plan ships, the bot polls Amazon and BestBuy concurrently, writes purchases serially through one queue, shuts down cleanly on Ctrl-C, and exposes a config-driven polling cadence.

Output: rewritten async main.py, AppConfig.app.delay field, GREEN tests in tests/test_orchestrator.py and tests/test_purchase_writer.py, extended tests/test_main_smoke.py.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/04-async-orchestrator/04-CONTEXT.md
@.planning/phases/04-async-orchestrator/04-RESEARCH.md
@.planning/phases/04-async-orchestrator/04-01-async-test-infra-PLAN.md
@.planning/phases/04-async-orchestrator/04-02-sqlite-wal-context-managers-PLAN.md
@.planning/phases/04-async-orchestrator/04-03-plugin-abc-async-shutdown-PLAN.md
@.planning/phases/04-async-orchestrator/04-04-registry-discover-async-stagger-PLAN.md
@.planning/phases/02-plugin-migration/02-04-SUMMARY.md
@main.py
@config_schema.py
@plugin_base.py
@plugin_registry.py
@models.py
@logger.py
@credentials.py
@utils.py
@tests/test_orchestrator.py
@tests/test_purchase_writer.py
@tests/test_main_smoke.py
@tests/conftest.py
</context>

<interfaces>
Target `main.py` shape (full file, replacing the current sync version from Phase 2):

```python
"""ShopPyBot entrypoint (Phase 4: async orchestrator).

Concurrency model:
- async def main() drives an asyncio.TaskGroup with one task per plugin plus
  one purchase_writer task.
- Blocking Selenium calls bridged via asyncio.to_thread.
- Shared ThreadPoolExecutor sized max(4, N*2) installed via
  loop.set_default_executor BEFORE TaskGroup opens (Pitfall 4-2).
- Plugin task crashes are isolated (try/except Exception inside poll_plugin).
- purchase_writer crash is FATAL (Pitfall 4-10): it tears down the TaskGroup.
- Shutdown: asyncio.shield(p.shutdown()) for each plugin in finally block.
- Windows: SelectorEventLoopPolicy installed (Pitfall 4-6).
"""
import asyncio
import os
import signal
import sys
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

if sys.version_info < (3, 11):
    sys.exit(f"ShopPyBot requires Python 3.11+. Detected: {sys.version}")

import requests
from webdriver_manager.chrome import ChromeDriverManager

from config_schema import AppConfig
from credentials import collect_cvvs
from logger import configure as configure_logger, writeLog
from models import add_items, get_items, initialize_db, update_item_purchased
from plugin_registry import discover_async, route_url, verify_coverage
from utils import play_available_sound, play_buy_sound


def get_chromedriver_path(driver_path: str) -> str:
    writeLog("Entering get_chromedriver_path", "DEBUG")
    if not os.path.exists(driver_path):
        writeLog(
            f"Chromedriver not found at {driver_path}. Downloading.",
            "WARNING",
        )
        driver_path = ChromeDriverManager().install()
        if not os.path.exists(driver_path):
            writeLog("Failed to download Chromedriver. Exiting.", "ERROR")
            sys.exit(1)
    writeLog(f"Chromedriver path: {driver_path}", "DEBUG")
    return driver_path


def make_tiny(url: str) -> str:
    response = requests.get(f"http://tinyurl.com/api-create.php?url={url}")
    return response.text


async def purchase_writer(queue: asyncio.Queue) -> None:
    """Single consumer for serialized SQLite writes (D-03).

    Critical infrastructure: a crash here is FATAL and propagates to TaskGroup
    (Pitfall 4-10). Only the inner update call is try/except/finally to
    guarantee queue.task_done() runs even on write failure (Pitfall 4-5).
    """
    while True:
        url, *_ = await queue.get()
        try:
            await asyncio.to_thread(update_item_purchased, url)
        except Exception as e:
            writeLog(f"purchase_writer: write failed for {url}: {e}", "ERROR")
        finally:
            queue.task_done()


async def poll_plugin(
    plugin,
    app_config,
    queue: asyncio.Queue,
    stop_event: asyncio.Event,
) -> None:
    """Run one plugin's polling loop. Crash-isolated per Pitfall 4-1."""
    openBrowser = app_config.open_browser
    delay = app_config.app.delay
    while not stop_event.is_set():
        try:
            await _poll_once(plugin, app_config, queue, openBrowser)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            writeLog(f"{plugin.name}: unexpected error: {e}", "ERROR")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=delay)
        except asyncio.TimeoutError:
            pass


async def _poll_once(plugin, app_config, queue, openBrowser) -> None:
    """One iteration: fetch items, check, auto-buy if available."""
    items = await asyncio.to_thread(get_items)
    for name, link, autoBuy, _qty, purchased in items:
        if purchased:
            continue
        matched = route_url(link, [plugin])
        if matched is None:
            continue  # not this plugin's URL
        try:
            available = await asyncio.to_thread(plugin.check_availability, link)
        except Exception as e:
            writeLog(
                f"{plugin.name}: check_availability raised on {link}: {e}",
                "ERROR",
            )
            continue
        if not available:
            continue
        play_available_sound()
        writeLog(f"{name} is available: {make_tiny(link)}", "SUCCESS")
        if autoBuy:
            await _attempt_purchase(plugin, link, name, app_config, queue)
        elif openBrowser:
            webbrowser.open(link)


async def _attempt_purchase(plugin, link, name, app_config, queue) -> None:
    try:
        await asyncio.to_thread(plugin.auto_buy, link, app_config)
        play_buy_sound()
        await queue.put((link,))
    except Exception as e:
        writeLog(
            f"{plugin.name}: auto_buy raised on {link}: {e}",
            "ERROR",
        )


def _seed_items(app_config) -> None:
    initialize_db()
    add_items([
        (it.name, it.link, it.auto_buy, it.quantity, False)
        for it in app_config.available.items
    ])


def _install_signal_handler(stop_event: asyncio.Event) -> None:
    """Pitfall 4-6: explicit SIGINT handler so Ctrl-C sets stop_event cleanly."""
    def _handler(_signum, _frame):
        writeLog("SIGINT received; signaling stop", "INFO")
        try:
            asyncio.get_running_loop().call_soon_threadsafe(stop_event.set)
        except RuntimeError:
            stop_event.set()
    signal.signal(signal.SIGINT, _handler)


async def main() -> None:
    try:
        app_config = AppConfig()
    except Exception as e:
        sys.stderr.write(str(e) + "\n")
        sys.exit(1)

    configure_logger(app_config.debug.logging_level)
    writeLog("Starting ShopPyBot (async)", "INFO")

    cvvs = await asyncio.to_thread(collect_cvvs, app_config)
    app_config.selenium.driver_path = await asyncio.to_thread(
        get_chromedriver_path, app_config.selenium.driver_path,
    )

    registry = await discover_async(
        Path("plugins"), app_config=app_config, cvvs=cvvs,
    )
    verify_coverage(registry, app_config.available.items)

    loop = asyncio.get_running_loop()
    maxWorkers = max(4, len(registry) * 2)
    executor = ThreadPoolExecutor(
        max_workers=maxWorkers, thread_name_prefix="shopbot",
    )
    loop.set_default_executor(executor)

    # Sequential startup login (preserves Phase 2 D-03; serializes stdin per Pitfall 4-11)
    for plugin in registry:
        if plugin.login_at_startup:
            await asyncio.to_thread(plugin.login, app_config)

    _seed_items(app_config)

    purchase_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    stop_event = asyncio.Event()
    _install_signal_handler(stop_event)

    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(purchase_writer(purchase_queue))
            for plugin in registry:
                tg.create_task(
                    poll_plugin(plugin, app_config, purchase_queue, stop_event)
                )
    except* KeyboardInterrupt:
        pass
    except* asyncio.CancelledError:
        pass
    finally:
        writeLog("Shutting down plugins", "INFO")
        await asyncio.gather(
            *(asyncio.shield(p.shutdown()) for p in registry),
            return_exceptions=True,
        )
        executor.shutdown(wait=True, cancel_futures=False)
        writeLog("ShopPyBot stopped cleanly", "INFO")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
```

Target `config_schema.py` addition (insert near other nested config classes):

```python
class AppSettings(BaseModel):
    """Phase 4: orchestrator-level settings."""
    delay: float = Field(default=5.0, ge=0.1, le=3600.0)


class AppConfig(BaseSettings):
    # ... existing fields ...
    app: AppSettings = AppSettings()
    # ... existing fields ...
```

(Planner note: `app:` was previously the legacy/deprecated section in Phase 1 D-06 — the `reject_deprecated_keys` validator rejects keys like `app.amz_email`. The validator must be updated to allow `app.delay` while still rejecting the four deprecated credential keys. Update the validator to check ONLY for the deprecated keys, not for the entire `app` section being present.)

Target `tests/test_orchestrator.py` GREEN suite:

```python
"""Phase 4 GREEN: tests for ASYNC-01 and ASYNC-03."""
import asyncio
import ast
import inspect
from unittest.mock import MagicMock

import pytest

import main as mainModule
from main import poll_plugin, purchase_writer, _attempt_purchase


# --- ASYNC-01 ----------------------------------------------------------------

async def test_mainIsAsyncCoroutine():
    assert inspect.iscoroutinefunction(mainModule.main)


async def test_pollPluginIsAsyncCoroutine():
    assert inspect.iscoroutinefunction(poll_plugin)


async def test_purchaseWriterIsAsyncCoroutine():
    assert inspect.iscoroutinefunction(purchase_writer)


async def test_pluginCrashIsolated(fakePluginFactory, appConfigStub, tmpDbPath, monkeypatch):
    """ASYNC-01: one plugin's check_availability raising must NOT cancel siblings."""
    from models import initialize_db, add_items
    initialize_db(delete=True)
    add_items([
        ("good", "https://fake.example/good", False, 1, False),
        ("bad",  "https://bad.example/bad",   False, 1, False),
    ])
    good = fakePluginFactory(name="fake", checkReturns=False)
    good.domain_pattern = ["fake.example"]
    bad = fakePluginFactory(name="bad", checkRaises=RuntimeError("boom"))
    bad.domain_pattern = ["bad.example"]
    queue: asyncio.Queue = asyncio.Queue()
    stop = asyncio.Event()

    async def runBriefly():
        async with asyncio.TaskGroup() as tg:
            tg.create_task(poll_plugin(good, appConfigStub, queue, stop))
            tg.create_task(poll_plugin(bad, appConfigStub, queue, stop))
            await asyncio.sleep(0.05)
            stop.set()

    await runBriefly()
    # Both plugins kept being polled despite bad raising
    assert good.checkCalls > 0
    assert bad.checkCalls > 0


def test_executorConfiguredBeforeTaskGroup():
    """Pitfall 4-2: set_default_executor must come before TaskGroup."""
    src = open("main.py").read()
    tree = ast.parse(src)
    setExecLine = None
    taskGroupLine = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Attribute) and f.attr == "set_default_executor":
                setExecLine = node.lineno
        if isinstance(node, ast.AsyncWith):
            for item in node.items:
                ctx = item.context_expr
                if (isinstance(ctx, ast.Call)
                        and isinstance(ctx.func, ast.Attribute)
                        and ctx.func.attr == "TaskGroup"):
                    taskGroupLine = node.lineno
                    break
    assert setExecLine is not None, "main.py never calls set_default_executor"
    assert taskGroupLine is not None, "main.py never opens asyncio.TaskGroup"
    assert setExecLine < taskGroupLine, (
        f"set_default_executor (line {setExecLine}) must come BEFORE "
        f"asyncio.TaskGroup (line {taskGroupLine})"
    )


# --- ASYNC-03 ----------------------------------------------------------------

def test_noBareInputInAsyncPath():
    """ASYNC-03 (per D-02): no bare input() call inside any async def in main.py.
    Allowed: asyncio.to_thread(input, prompt).
    """
    tree = ast.parse(open("main.py").read())
    asyncFuncs = [n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef)]
    for fn in asyncFuncs:
        for node in ast.walk(fn):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id != "input", (
                    f"Bare input() in async fn {fn.name} at line {node.lineno}; "
                    "use asyncio.to_thread(input, prompt) per D-02"
                )


def test_noTimeSleepInMain():
    """Pitfall 4-9: time.sleep blocks the event loop."""
    src = open("main.py").read()
    assert "time.sleep" not in src, "time.sleep blocks the event loop; use await asyncio.sleep"


def test_pluginShutdownCalledUnderShield():
    """Pitfall 4-4 + D-04: every plugin.shutdown() in main.py is wrapped in asyncio.shield."""
    src = open("main.py").read()
    # Cheap source check: shutdown call appears inside asyncio.shield(...) text
    assert "asyncio.shield(p.shutdown())" in src or "asyncio.shield(plugin.shutdown())" in src, (
        "plugin.shutdown() must be wrapped in asyncio.shield per Pitfall 4-4"
    )
```

Target `tests/test_purchase_writer.py` GREEN suite:

```python
"""Phase 4 GREEN: tests for ASYNC-05 (purchase_writer)."""
import asyncio
from unittest.mock import patch

import pytest

from main import purchase_writer


async def test_writerDrainsQueue(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr("main.update_item_purchased", lambda url: calls.append(url))
    queue: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(purchase_writer(queue))
    await queue.put(("https://a.example",))
    await queue.put(("https://b.example",))
    await queue.join()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert calls == ["https://a.example", "https://b.example"]


async def test_taskDoneCalledOnWriteFailure(monkeypatch):
    """Pitfall 4-5: queue.task_done MUST run even when update_item_purchased raises."""
    def _boom(url):
        raise RuntimeError("write failure")
    monkeypatch.setattr("main.update_item_purchased", _boom)
    queue: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(purchase_writer(queue))
    await queue.put(("https://will-fail.example",))
    # If task_done isn't called, queue.join() hangs forever; use a tight timeout.
    await asyncio.wait_for(queue.join(), timeout=2.0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_writerCrashIsFatal(monkeypatch):
    """Pitfall 4-10: purchase_writer crash must propagate out of TaskGroup."""
    def _boom(_):
        raise RuntimeError("infrastructure failure")
    # Patch asyncio.to_thread to immediately raise inside the writer body
    async def _badToThread(fn, *args, **kw):
        raise RuntimeError("infrastructure failure")
    queue: asyncio.Queue = asyncio.Queue()
    # The writer body catches exceptions from update_item_purchased ONLY
    # inside its inner try; an exception from queue.get() or task_done would propagate.
    # We assert that the writer's body DOES NOT have a defensive outer try/except
    # by parsing main.py.
    import ast
    src = open("main.py").read()
    tree = ast.parse(src)
    writerFn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "purchase_writer"
    )
    # The writer's while True body has at most ONE Try node (the inner one around the to_thread call).
    tryNodes = [n for n in ast.walk(writerFn) if isinstance(n, ast.Try)]
    assert len(tryNodes) == 1, (
        f"purchase_writer must have exactly 1 try/except (around update_item_purchased); "
        f"found {len(tryNodes)}. Defensive outer try/except violates Pitfall 4-10."
    )
```

Target `tests/test_main_smoke.py` additions (append to Phase 2 file; do NOT modify existing tests):

```python
# === Phase 4 additions: async refactor smoke ===

def test_mainIsAsyncFunctionDef():
    """Phase 4: main() must be `async def`, not `def`."""
    import ast
    tree = ast.parse(open("main.py").read())
    mainFn = next(
        (n for n in ast.walk(tree)
         if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "main"),
        None,
    )
    assert isinstance(mainFn, ast.AsyncFunctionDef), "main must be an async function"


def test_mainImportsDiscoverAsync():
    import ast
    tree = ast.parse(open("main.py").read())
    foundDiscoverAsync = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "plugin_registry":
            for alias in node.names:
                if alias.name == "discover_async":
                    foundDiscoverAsync = True
    assert foundDiscoverAsync, "main.py must import discover_async from plugin_registry"


def test_mainImportsTaskGroupViaAsyncio():
    import ast
    src = open("main.py").read()
    assert "asyncio.TaskGroup" in src or "TaskGroup" in src
```
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Extend AppConfig with app.delay; update deprecated-key validator</name>
  <files>config_schema.py, tests/test_main_smoke.py</files>
  <read_first>
    - config_schema.py (current AppConfig with reject_deprecated_keys validator)
    - .planning/phases/01-foundations-security/01-03-pydantic-config-schema-SUMMARY.md (D-06 deprecated-key rejection logic)
    - .planning/phases/04-async-orchestrator/04-RESEARCH.md (config schema addition note)
    - sample.config.yml (existing sample, may need an `app:` example added — Plan 04-05 leaves the YAML alone; users can override via env or YAML; default 5.0 is fine for current behavior)
  </read_first>
  <behavior>
    - `AppConfig.app` field exists, typed as `AppSettings`, defaulted to `AppSettings()`.
    - `AppSettings.delay: float = 5.0` with bounds `ge=0.1, le=3600.0`.
    - The existing `reject_deprecated_keys` validator continues to reject `app.amz_email`, `app.amz_pwd`, `app.bb_email`, `app.bb_password`, `app.bb_cvv` exactly as before — but now ALLOWS `app.delay` to pass through unflagged.
    - All Phase 1/2/3 config tests still pass (no regressions in deprecated-key rejection).
    - Importing `AppConfig` and reading `AppConfig().app.delay` returns 5.0 with default config.yml.
  </behavior>
  <action>
    1. Open `config_schema.py`. Locate the nested config classes (SeleniumConfig, DebugConfig, etc.) and add `AppSettings` near them:
       ```python
       class AppSettings(BaseModel):
           delay: float = Field(default=5.0, ge=0.1, le=3600.0)
       ```

    2. Add `app: AppSettings = AppSettings()` to the `AppConfig(BaseSettings)` class field list (next to `debug` and `available`).

    3. Update the `reject_deprecated_keys` validator: it currently checks `if not isinstance(data, dict): return data` then pulls `app = data.get("app", {})` and checks for the five deprecated keys. The fix: the validator already only flags keys in the `deprecated` dict, so adding `app.delay` to config.yml will NOT match any deprecated key — the existing logic already allows it. Verify by reading the validator body and confirming no test asserts "app section must be empty". If such an assertion exists, update it to ignore `delay`.

    4. Run `rtk pytest -x -q tests/test_config.py tests/test_pydantic_config.py 2>/dev/null || rtk pytest -x -q -k config`. All existing config tests must pass. The validator change is additive (no new deprecated keys, just a new legitimate key).

    5. Sanity smoke: `python -c "from config_schema import AppConfig; cfg = AppConfig(); print(cfg.app.delay)"` should print `5.0` (assumes sample.config.yml or env provides minimum required fields; if it fails on missing fields, that's unrelated to this change — verify by checking the error message).

    6. Append the three Phase 4 smoke tests from <interfaces> (`test_mainIsAsyncFunctionDef`, `test_mainImportsDiscoverAsync`, `test_mainImportsTaskGroupViaAsyncio`) to the END of `tests/test_main_smoke.py`. Do NOT modify existing Phase 2 tests in this file. These three tests will FAIL until Task 2 lands (main.py is still sync).
  </action>
  <verify>
    <automated>python -c "from config_schema import AppConfig, AppSettings; assert AppSettings().delay == 5.0; print('OK')"</automated>
    <automated>rtk grep -n "AppSettings\|app: AppSettings\|delay: float" config_schema.py</automated>
    <automated>rtk pytest -x -q -k "config or pydantic"</automated>
    <automated>rtk grep -n "test_mainIsAsyncFunctionDef\|test_mainImportsDiscoverAsync" tests/test_main_smoke.py</automated>
  </verify>
  <acceptance_criteria>
    - config_schema.py defines AppSettings class with delay field (default 5.0, ge=0.1, le=3600.0)
    - AppConfig.app = AppSettings() field added
    - reject_deprecated_keys validator still rejects the five deprecated credential keys
    - Phase 1/2/3 config tests still pass
    - tests/test_main_smoke.py has 3 new APPENDED tests asserting async refactor (these FAIL today; will GREEN after Task 2)
    - Existing Phase 2 tests in tests/test_main_smoke.py untouched
  </acceptance_criteria>
  <done>Config schema ready; smoke tests appended in pre-RED state for the upcoming main.py rewrite</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Rewrite main.py as async orchestrator (TaskGroup + purchase_writer + shield shutdown)</name>
  <files>main.py</files>
  <read_first>
    - main.py (current Phase 2 sync version)
    - .planning/phases/04-async-orchestrator/04-CONTEXT.md (D-01..D-04; Specifics section sketch of target main; ALL Pitfalls)
    - .planning/phases/04-async-orchestrator/04-RESEARCH.md (Pattern 1 poll_plugin, Pattern 2 executor, Pattern 4 system diagram, Pitfalls 1-11)
    - plugin_registry.py (post-Plan-04-04: discover_async signature)
    - plugin_base.py (post-Plan-04-03: async shutdown contract)
    - models.py (post-Plan-04-02: WAL + context manager; update_item_purchased signature unchanged)
    - config_schema.py (post-Task-1: app.delay field)
    - logger.py, credentials.py, utils.py (unchanged; consumed via to_thread)
  </read_first>
  <behavior>
    All `must_haves.truths` listed in frontmatter, in full. Specifically:
    - main is `async def main()` and only called via `asyncio.run(main())` at module bottom
    - On Windows (`sys.platform == "win32"`), install `WindowsSelectorEventLoopPolicy` before asyncio.run (Pitfall 4-6)
    - ThreadPoolExecutor sized `max(4, len(registry) * 2)`, thread_name_prefix="shopbot"
    - `loop.set_default_executor(executor)` runs BEFORE `async with asyncio.TaskGroup(...)` (Pitfall 4-2; verified by test_executorConfiguredBeforeTaskGroup)
    - Plugin discovery via `await discover_async(...)` from Plan 04-04
    - Sequential `for plugin in registry: if plugin.login_at_startup: await asyncio.to_thread(plugin.login, app_config)` (Phase 2 D-03 preserved; serializes stdin per Pitfall 4-11)
    - `purchase_queue = asyncio.Queue(maxsize=100)` (D-03)
    - `stop_event = asyncio.Event()` set by SIGINT handler
    - TaskGroup creates ONE task per plugin (via `poll_plugin`) plus ONE `purchase_writer` task
    - `poll_plugin` body wraps each iteration in try/except Exception (re-raises CancelledError), logs ERROR and continues (Pitfall 4-1)
    - `purchase_writer` body has EXACTLY ONE try/except — around `update_item_purchased` ONLY — with `task_done()` in finally (Pitfall 4-5 + Pitfall 4-10)
    - Successful auto_buy enqueues via `await purchase_queue.put((link,))`; main.py NEVER calls `update_item_purchased` directly (only purchase_writer does)
    - Finally block: `await asyncio.gather(*(asyncio.shield(p.shutdown()) for p in registry), return_exceptions=True)` (D-04 + Pitfall 4-4)
    - Finally block: `executor.shutdown(wait=True, cancel_futures=False)`
    - `except* KeyboardInterrupt:` and `except* asyncio.CancelledError:` (Python 3.11+ exception-group syntax) inside main, plus outer `except KeyboardInterrupt:` at the `asyncio.run` boundary
    - All blocking calls go through `asyncio.to_thread`: `collect_cvvs`, `get_chromedriver_path`, `plugin.login`, `plugin.check_availability`, `plugin.auto_buy`, `update_item_purchased`, `get_items`
    - ZERO bare `input(` calls inside any `async def` body (D-02 / ASYNC-03; verified by test_noBareInputInAsyncPath)
    - ZERO `time.sleep` anywhere in main.py (Pitfall 4-9)
    - File stays under 300 lines; each function under 30 lines (CLAUDE.md). To fit under 30 lines per function, `main()` delegates to small helpers: `_seed_items`, `_install_signal_handler`, `_poll_once`, `_attempt_purchase`, etc.
  </behavior>
  <action>
    1. Replace the entire contents of `main.py` with the target shape shown in <interfaces>. Keep `get_chromedriver_path` and `make_tiny` as sync helpers (they are called via `asyncio.to_thread` from `main()`).

    2. Imports: add `import asyncio`, `import signal`, `from concurrent.futures import ThreadPoolExecutor`. Update `from plugin_registry import ...` to import `discover_async` (instead of `discover`), keep `route_url`, keep `verify_coverage`. Add `update_item_purchased` to the `from models import ...` line (purchase_writer needs it).

    3. Keep the Python-version guard at the top: `if sys.version_info < (3, 11): sys.exit(...)`. TaskGroup and `except*` syntax require 3.11+.

    4. Implement `purchase_writer` exactly per <interfaces>: ONE inner try/except/finally around `update_item_purchased` only. Do NOT add an outer defensive try/except — Pitfall 4-10 says writer crash must propagate so TaskGroup tears down (a write-system failure means we should stop, not keep buying without recording it).

    5. Implement `poll_plugin` per <interfaces>. The inner per-iteration try/except catches `Exception` (NOT BaseException), re-raises `CancelledError`, and continues on any other exception. The polling cadence uses `await asyncio.wait_for(stop_event.wait(), timeout=delay)` — this gives us a fast Ctrl-C response: when stop_event is set, the wait returns immediately, the loop checks `while not stop_event.is_set()` and exits.

    6. Implement `_poll_once` as a small helper called from `poll_plugin`. It fetches items via `await asyncio.to_thread(get_items)` so the SQLite read does not block the loop. For each item it calls `route_url(link, [plugin])` — note: pass a list of ONLY this plugin, so we get back this plugin if its domain matches, else None (skip). This avoids cross-plugin races where plugin A polls plugin B's URLs.

    7. Implement `_attempt_purchase` as a small helper. On success: enqueue. On exception: log ERROR. Never call `update_item_purchased` here — only `purchase_writer` does.

    8. Implement `_install_signal_handler(stop_event)`: install `signal.signal(signal.SIGINT, handler)` where handler calls `loop.call_soon_threadsafe(stop_event.set)`. Wrap the `get_running_loop()` call in try/except RuntimeError so the handler still works if called from outside the loop context (defensive).

    9. Use `except* KeyboardInterrupt:` (PEP 654 exception groups, Python 3.11+) inside `main()` because TaskGroup wraps everything in ExceptionGroup. This is the canonical way to catch a single-exception subtype from inside an `async with TaskGroup()`. Same for `except* CancelledError:`.

    10. At the bottom: `if __name__ == "__main__":` block sets `WindowsSelectorEventLoopPolicy` on Windows BEFORE `asyncio.run(main())`. Wrap `asyncio.run(main())` in an OUTER `try/except KeyboardInterrupt: pass` so a Ctrl-C during teardown does not print a traceback.

    11. CRITICAL: do NOT call `update_item_purchased` directly from `_attempt_purchase`. Only `purchase_writer` writes. This is the D-03 serialization contract.

    12. CRITICAL: do NOT wrap `purchase_writer`'s outer body in try/except. Only the inner `update_item_purchased` call is in try/except/finally. Test `test_writerCrashIsFatal` enforces this via AST inspection.

    13. CRITICAL: every `plugin.shutdown()` call is wrapped in `asyncio.shield(...)`. The shield prevents a Ctrl-C-during-shutdown from cancelling the in-flight `driver.quit` (Pitfall 4-4). `asyncio.gather(..., return_exceptions=True)` ensures one plugin's shutdown failure does not block others.

    14. CRITICAL: `executor.shutdown(wait=True, cancel_futures=False)` must run AFTER all plugin shutdowns complete. Order matters: drivers quit (releases ports), then executor drains. Cancelling pending futures would leave half-quit chromedrivers.

    15. Run `python -c "import ast; ast.parse(open('main.py').read())"` — exit 0.

    16. Run `rtk pytest -x -q tests/test_main_smoke.py`. The three new Phase 4 tests appended in Task 1 should now PASS. The Phase 2 tests still PASS.

    17. Do NOT run `python main.py` (would launch Chrome). Phase verification is the test suite plus a manual smoke at phase close.
  </action>
  <verify>
    <automated>python -c "import ast; t = ast.parse(open('main.py').read()); fns = [n.name for n in ast.walk(t) if isinstance(n, ast.AsyncFunctionDef)]; assert 'main' in fns and 'poll_plugin' in fns and 'purchase_writer' in fns; print('OK')"</automated>
    <automated>rtk grep -n "asyncio.TaskGroup\|asyncio.shield\|discover_async\|asyncio.run\|set_default_executor\|WindowsSelectorEventLoopPolicy\|purchase_queue\|signal.signal" main.py</automated>
    <automated>rtk grep -n "time.sleep" main.py</automated>
    <automated>rtk pytest -x -q tests/test_main_smoke.py</automated>
    <automated>rtk pytest -x -q --ignore=tests/test_orchestrator.py --ignore=tests/test_purchase_writer.py</automated>
  </verify>
  <acceptance_criteria>
    - main.py defines async main, poll_plugin, purchase_writer, plus small helpers
    - All imports present (asyncio, signal, ThreadPoolExecutor, discover_async, update_item_purchased)
    - TaskGroup opens AFTER set_default_executor; verified by AST line-number ordering
    - SIGINT handler installs stop_event.set
    - asyncio.shield wraps every plugin.shutdown()
    - executor.shutdown(wait=True, cancel_futures=False) runs after plugin shutdowns
    - WindowsSelectorEventLoopPolicy installed on win32
    - No bare input(), no time.sleep in main.py
    - File parses as valid Python, under 300 lines, all functions under 30 lines
    - Phase 2 smoke tests still pass; new Phase 4 smoke tests (from Task 1) now pass
    - Phase 1/2/3 + Phase 4 Plans 02/03/04 tests still pass (excluding test_orchestrator.py and test_purchase_writer.py which Task 3 handles)
  </acceptance_criteria>
  <done>main.py rewritten as async orchestrator with all Pitfalls 1-11 mitigated</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Flip tests/test_orchestrator.py and tests/test_purchase_writer.py to GREEN</name>
  <files>tests/test_orchestrator.py, tests/test_purchase_writer.py</files>
  <read_first>
    - tests/test_orchestrator.py (RED skeleton from Plan 04-01)
    - tests/test_purchase_writer.py (RED skeleton from Plan 04-01)
    - main.py (GREEN after Task 2)
    - tests/conftest.py (fakePluginFactory, appConfigStub, tmpDbPath fixtures from Plan 04-01)
    - models.py (post-Plan-04-02 GREEN)
  </read_first>
  <behavior>
    - tests/test_orchestrator.py contains all 7 tests defined in <interfaces>: mainIsAsyncCoroutine, pollPluginIsAsyncCoroutine, purchaseWriterIsAsyncCoroutine, pluginCrashIsolated, executorConfiguredBeforeTaskGroup, noBareInputInAsyncPath, noTimeSleepInMain, pluginShutdownCalledUnderShield. (Note: this is actually 8 tests; the suite is comprehensive.)
    - tests/test_purchase_writer.py contains all 3 tests from <interfaces>: writerDrainsQueue, taskDoneCalledOnWriteFailure, writerCrashIsFatal.
    - All tests PASS.
    - The pluginCrashIsolated test uses fakePluginFactory + tmpDbPath to seed a real SQLite DB with two items (one routing to "good" plugin's domain, one to "bad" plugin's domain), so route_url correctly finds the matching plugin and exercises the crash path.
  </behavior>
  <action>
    1. Replace contents of `tests/test_orchestrator.py` (RED skeleton from Plan 04-01) with the GREEN suite shown in <interfaces>. Update module docstring from "RED skeleton" to "Phase 4 GREEN".

    2. Replace contents of `tests/test_purchase_writer.py` (RED skeleton from Plan 04-01) with the GREEN suite shown in <interfaces>. Update module docstring similarly.

    3. The `pluginCrashIsolated` test requires actual DB rows so `get_items()` returns matchable URLs. Use `tmpDbPath` fixture, then `initialize_db(delete=True)` and `add_items([...])` to seed two rows.

    4. The `executorConfiguredBeforeTaskGroup` test reads main.py and uses AST to find both call sites. If either is missing, the assertion message identifies which one. Line numbers are required to be strictly increasing.

    5. The `noBareInputInAsyncPath` test walks every `AsyncFunctionDef` in main.py and asserts no `Call` node with `func.id == "input"`. This catches the most common ASYNC-03 regression: a developer adds `input("Press Enter")` inside an async function instead of `await asyncio.to_thread(input, "Press Enter")`.

    6. The `writerCrashIsFatal` test uses AST inspection of `purchase_writer` to count `Try` nodes — must be exactly 1 (the inner one around update_item_purchased). This locks in Pitfall 4-10.

    7. Run `rtk pytest -x -q tests/test_orchestrator.py tests/test_purchase_writer.py`. Expect ALL PASS.

    8. Run full suite `rtk pytest -x -q`. Must stay green.

    9. Optional manual smoke (NOT a per-task gate, documented for phase-close verification):
       - `python main.py` with config.yml configured for one item per plugin
       - observe log lines from both plugins interleaving (concurrent polling)
       - observe `discover_async` log gap of ~1.5s between plugin instantiations
       - Ctrl-C: bot logs "SIGINT received", "Shutting down plugins", "ShopPyBot stopped cleanly"
       - `tasklist | findstr chromedriver` after exit: zero rows (no orphans)
       This is captured in phase VERIFICATION.md, not here.
  </action>
  <verify>
    <automated>rtk pytest -x -q tests/test_orchestrator.py tests/test_purchase_writer.py</automated>
    <automated>rtk pytest -x -q</automated>
    <automated>rtk grep -n "writerCrashIsFatal\|pluginCrashIsolated\|executorConfiguredBeforeTaskGroup\|noBareInputInAsyncPath" tests/test_orchestrator.py tests/test_purchase_writer.py</automated>
  </verify>
  <acceptance_criteria>
    - tests/test_orchestrator.py: 8 PASSING tests covering ASYNC-01 (concurrency, crash isolation, executor ordering) and ASYNC-03 (no bare input, no time.sleep, shield shutdown)
    - tests/test_purchase_writer.py: 3 PASSING tests covering ASYNC-05 (queue drain, task_done on failure, writer crash is fatal)
    - Full pytest suite green across Phases 1-4
    - All RED tests from Plan 04-01 (across all five new test files) are now GREEN
  </acceptance_criteria>
  <done>ASYNC-01, ASYNC-03, ASYNC-05 fully GREEN; Phase 4 implementation complete</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| event loop vs Selenium worker threads | All blocking Selenium calls must cross the loop->thread boundary via to_thread; missing one stalls everything |
| TaskGroup cancellation propagation | Unhandled Exception in any child task cancels siblings — defeats ASYNC-01 isolation goal unless plugin tasks wrap their bodies |
| purchase_writer infrastructure crash vs plugin task crash | Different blast radius: plugin crash is isolated, writer crash is fatal (Pitfall 4-10) |
| stdin contention between concurrent plugins | Two simultaneous input() prompts race on terminal stdin — startup login already sequential, runtime CAPTCHA prompts accepted as v1 limitation |
| signal handler vs asyncio loop | SIGINT delivered to main thread; must use call_soon_threadsafe to set asyncio.Event from a signal handler |
| executor lifecycle vs driver lifecycle | Drivers must quit BEFORE executor shuts down or quit() futures get cancelled and leave orphaned chromedriver.exe |
| Windows ProactorEventLoop signal handling | Default Windows event loop has fragile Ctrl-C; SelectorEventLoop is fine because we do not use subprocess pipes |
| WAL sidecar files | data/*.db-wal must remain gitignored (Plan 04-01 handled this) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-04-05-LOOP-STALL | Denial of Service | event loop blocked by Selenium | mitigate | Every plugin method call wrapped in asyncio.to_thread inside poll_plugin/_attempt_purchase; ThreadPoolExecutor sized max(4, N*2) so OTP-blocked threads don't starve siblings |
| T-04-05-SIBLING-CANCEL | Denial of Service | one plugin crash cancels all (Pitfall 4-1) | mitigate | poll_plugin wraps per-iteration body in try/except Exception, re-raises CancelledError. Verified by test_pluginCrashIsolated |
| T-04-05-WRITER-SILENT-DEATH | Repudiation | purchase_writer dies silently (Pitfall 4-10) | mitigate | No outer try/except around writer body; AST test_writerCrashIsFatal enforces this. Writer crash propagates to TaskGroup, which propagates to main, which logs and exits |
| T-04-05-QUEUE-HANG | Denial of Service | queue.task_done missed (Pitfall 4-5) | mitigate | task_done in finally clause; test_taskDoneCalledOnWriteFailure asserts queue.join() returns within 2s even when write raises |
| T-04-05-ORPHAN-CHROMEDRIVER | Denial of Service (self) | chromedriver.exe leak on Ctrl-C (Pitfall 4-4) | mitigate | asyncio.shield(p.shutdown()) for every plugin; executor.shutdown(wait=True, cancel_futures=False) runs AFTER plugin shutdowns. Verified by test_pluginShutdownCalledUnderShield + manual phase-close smoke (tasklist findstr chromedriver) |
| T-04-05-WIN-SIGINT | Availability | Ctrl-C ignored on Windows (Pitfall 4-6) | mitigate | WindowsSelectorEventLoopPolicy installed before asyncio.run; explicit signal.signal(SIGINT) handler sets asyncio.Event via call_soon_threadsafe |
| T-04-05-BARE-INPUT | Denial of Service | bare input() in async path stalls loop (D-02 / ASYNC-03) | mitigate | test_noBareInputInAsyncPath AST-checks every async def; CI blocks regression |
| T-04-05-TIME-SLEEP | Denial of Service | time.sleep blocks loop (Pitfall 4-9) | mitigate | test_noTimeSleepInMain greps main.py source; CI blocks regression |
| T-04-05-DOUBLE-BUY | Tampering | concurrent update_item_purchased writes | mitigate | Single writer task (D-03) serializes; WAL+busy_timeout (Plan 04-02) handles unexpected concurrent reads |
| T-04-05-STDIN-RACE | Tampering | two plugins prompt input() simultaneously (Pitfall 4-11) | accept | Startup login serialized (Phase 2 D-03); runtime CAPTCHA prompts accepted as v1 limitation; document in CONTRIBUTING in a future doc plan |
| T-04-05-EXECUTOR-RACE | Tampering | first to_thread call uses default fixed-size pool before set_default_executor lands (Pitfall 4-2) | mitigate | set_default_executor runs synchronously before async with TaskGroup; test_executorConfiguredBeforeTaskGroup AST-verifies line ordering |
</threat_model>

<verification>
- `python -c "import ast; t = ast.parse(open('main.py').read()); print('OK')"` exits 0
- `rtk grep -n "asyncio.TaskGroup\|asyncio.shield\|discover_async\|asyncio.run\|set_default_executor\|WindowsSelectorEventLoopPolicy" main.py` matches all
- `rtk grep -n "time.sleep" main.py` returns no matches
- `rtk pytest -x -q tests/test_orchestrator.py tests/test_purchase_writer.py` shows all PASS
- `rtk pytest -x -q` full suite green across Phases 1-4
- All RED tests from Plan 04-01 across all five new test files are now GREEN

Manual phase-close smoke (documented; runs after VERIFICATION pass, not as a per-task gate):
- `python main.py` with config.yml configured for one item per plugin starts polling
- Log timestamps show overlapping check_availability calls from Amazon and BestBuy
- Driver startup spacing visible: ~1.5s gap between plugin instantiation logs
- Ctrl-C: logs "SIGINT received", "Shutting down plugins", "ShopPyBot stopped cleanly"
- `tasklist | findstr chromedriver` after exit: zero rows (no orphans)
</verification>

<success_criteria>
- ASYNC-01 GREEN: TaskGroup runs N plugins concurrently, crashes isolated, executor configured before TaskGroup
- ASYNC-03 GREEN: zero bare input() in async paths; all input bridged via asyncio.to_thread per D-02
- ASYNC-05 GREEN: purchase_writer single-consumer queue serializes update_item_purchased; task_done always runs; writer crash is fatal
- D-04 wiring live: every plugin.shutdown() wrapped in asyncio.shield; executor drains after shutdowns
- Pitfalls 1-11 all mitigated and test-covered or accepted with documented rationale
- main.py under 300 lines; all functions under 30 lines (CLAUDE.md compliance)
- Phase 4 complete; ready for VERIFICATION + phase close
</success_criteria>

<output>
After completion, create `.planning/phases/04-async-orchestrator/04-05-SUMMARY.md`
</output>
