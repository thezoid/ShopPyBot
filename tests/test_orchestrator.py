"""Phase 4 GREEN: tests for ASYNC-01 and ASYNC-03."""
import ast
import asyncio
import inspect
from pathlib import Path

import pytest

import main as mainModule
from main import poll_plugin, purchase_writer, _attempt_purchase  # noqa: F401


MAIN_PY_PATH = Path(__file__).resolve().parent.parent / "main.py"


def _read_main():
    return MAIN_PY_PATH.read_text(encoding="utf-8")


# --- ASYNC-01 ----------------------------------------------------------------

async def test_mainIsAsyncCoroutine():
    assert inspect.iscoroutinefunction(mainModule.main)


async def test_pollPluginIsAsyncCoroutine():
    assert inspect.iscoroutinefunction(poll_plugin)


async def test_purchaseWriterIsAsyncCoroutine():
    assert inspect.iscoroutinefunction(purchase_writer)


async def test_pluginCrashIsolated(
    fakePluginFactory, appConfigStub, tmpDbPath
):
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
    notifQueue: asyncio.Queue = asyncio.Queue()
    stop = asyncio.Event()

    async def runBriefly():
        async with asyncio.TaskGroup() as tg:
            tg.create_task(poll_plugin(good, appConfigStub, queue, notifQueue, stop))
            tg.create_task(poll_plugin(bad, appConfigStub, queue, notifQueue, stop))
            await asyncio.sleep(0.05)
            stop.set()

    await runBriefly()
    assert good.checkCalls > 0
    assert bad.checkCalls > 0


def test_executorConfiguredBeforeTaskGroup():
    """Pitfall 4-2: set_default_executor must come before TaskGroup."""
    tree = ast.parse(_read_main())
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
    tree = ast.parse(_read_main())
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
    src = _read_main()
    assert "time.sleep" not in src, \
        "time.sleep blocks the event loop; use await asyncio.sleep"


def test_pluginShutdownCalledUnderShield():
    """Pitfall 4-4 + D-04: every plugin.shutdown() in main.py is wrapped in asyncio.shield."""
    src = _read_main()
    assert (
        "asyncio.shield(p.shutdown())" in src
        or "asyncio.shield(plugin.shutdown())" in src
    ), "plugin.shutdown() must be wrapped in asyncio.shield per Pitfall 4-4"


# --- Phase 5 (05-06) notification fan-out assertions ------------------------

def test_noInlineSoundCalls():
    """Phase 5: SoundNotifier owns sound playback; inline calls must be removed."""
    tree = ast.parse(_read_main())
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert "play_available_sound" not in names
    assert "play_buy_sound" not in names


def test_notificationWriterInTaskGroup():
    """notification_writer must be created as a task inside the TaskGroup."""
    tree = ast.parse(_read_main())
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "create_task":
            if node.args and isinstance(node.args[0], ast.Call):
                called = node.args[0].func
                if isinstance(called, ast.Name) and called.id == "notification_writer":
                    found = True
                    break
    assert found, "notification_writer not added to TaskGroup"


def test_notificationEventTimestampsTzAware():
    """Every NotificationEvent(...) call must use datetime.now(timezone.utc)."""
    tree = ast.parse(_read_main())
    sites = 0
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "NotificationEvent"
        ):
            sites += 1
            ts = next((kw for kw in node.keywords if kw.arg == "timestamp"), None)
            assert ts is not None, "NotificationEvent missing timestamp kwarg"
            v = ts.value
            assert isinstance(v, ast.Call), "timestamp must be a Call (datetime.now(...))"
            func_name = ""
            if isinstance(v.func, ast.Attribute):
                func_name = v.func.attr
            assert func_name == "now", "timestamp must be datetime.now(...)"
            args_and_kwargs = list(v.args) + [kw.value for kw in v.keywords]
            has_utc = any(
                isinstance(a, ast.Attribute) and a.attr == "utc"
                for a in args_and_kwargs
            )
            assert has_utc, "NotificationEvent timestamp not tz-aware UTC"
    assert sites >= 2, "expected at least two NotificationEvent put-sites in main.py"


def test_mainImportsDiscoverNotifiers():
    tree = ast.parse(_read_main())
    ok = any(
        isinstance(n, ast.ImportFrom)
        and n.module == "notifier_registry"
        and any(a.name == "discover_notifiers" for a in n.names)
        for n in ast.walk(tree)
    )
    assert ok, "main.py must import discover_notifiers from notifier_registry"


def test_shutdownGathersNotifiers():
    """Finally-block shutdown gather must cover notifiers under asyncio.shield."""
    src = _read_main()
    assert "for n in notifiers" in src, \
        "shutdown gather must iterate notifiers"
    assert "asyncio.shield" in src, \
        "notifier shutdowns must be wrapped in asyncio.shield"


# --- Phase 6 (06-07) plugin.next_delay() + iscoroutinefunction branches ----

from unittest.mock import MagicMock

from main import _poll_once


def _makeSyncPlugin(name="sync", available=False):
    from plugin_base import RetailerPlugin

    class _Sync(RetailerPlugin):
        domain_pattern = [f"{name}.example"]

        def __init__(self):
            super().__init__(platform_config=None)
            self.driver = MagicMock()
            self.nextDelayCalls = 0
            self.checkCalls = 0
            self.autoBuyCalls = 0

        def next_delay(self) -> float:
            self.nextDelayCalls += 1
            return 0.0

        def check_availability(self, url):
            self.checkCalls += 1
            return available

        def auto_buy(self, url, config):
            self.autoBuyCalls += 1
            return True

    inst = _Sync()
    inst.name = name
    return inst


def _makeAsyncPlugin(name="async", available=False):
    from plugin_base import RetailerPlugin

    class _Async(RetailerPlugin):
        domain_pattern = [f"{name}.example"]

        def __init__(self):
            super().__init__(platform_config=None)
            self.driver = MagicMock()
            self.nextDelayCalls = 0
            self.checkCalls = 0
            self.autoBuyCalls = 0

        def next_delay(self) -> float:
            self.nextDelayCalls += 1
            return 0.0

        async def check_availability(self, url):
            self.checkCalls += 1
            return available

        async def auto_buy(self, url, config):
            self.autoBuyCalls += 1
            return True

    inst = _Async()
    inst.name = name
    return inst


async def test_pollPluginUsesNextDelay(appConfigStub, tmpDbPath):
    """ANTI-01: poll_plugin must call plugin.next_delay() per iteration."""
    from models import initialize_db
    initialize_db(delete=True)
    plugin = _makeSyncPlugin(name="nd")
    q: asyncio.Queue = asyncio.Queue()
    nq: asyncio.Queue = asyncio.Queue()
    stop = asyncio.Event()

    async def runBriefly():
        async with asyncio.TaskGroup() as tg:
            tg.create_task(poll_plugin(plugin, appConfigStub, q, nq, stop))
            await asyncio.sleep(0.05)
            stop.set()

    await runBriefly()
    assert plugin.nextDelayCalls >= 1


async def test_pollOnceAwaitsAsyncCheck(appConfigStub, tmpDbPath, monkeypatch):
    """Async check_availability must be awaited directly, NOT via to_thread."""
    from models import initialize_db, add_items
    initialize_db(delete=True)
    add_items([("a", "https://async.example/x", False, 1, False)])
    plugin = _makeAsyncPlugin(name="async")
    toThreadCalls = []
    realToThread = asyncio.to_thread

    async def recorder(func, *args, **kwargs):
        toThreadCalls.append(getattr(func, "__name__", repr(func)))
        return await realToThread(func, *args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", recorder)
    q: asyncio.Queue = asyncio.Queue()
    nq: asyncio.Queue = asyncio.Queue()
    await _poll_once(plugin, appConfigStub, q, nq, False)
    assert plugin.checkCalls == 1
    assert "check_availability" not in toThreadCalls


async def test_pollOnceToThreadSyncCheck(appConfigStub, tmpDbPath, monkeypatch):
    """Sync check_availability must be wrapped via asyncio.to_thread."""
    from models import initialize_db, add_items
    initialize_db(delete=True)
    add_items([("a", "https://sync.example/x", False, 1, False)])
    plugin = _makeSyncPlugin(name="sync")
    toThreadCalls = []
    realToThread = asyncio.to_thread

    async def recorder(func, *args, **kwargs):
        toThreadCalls.append(getattr(func, "__name__", repr(func)))
        return await realToThread(func, *args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", recorder)
    q: asyncio.Queue = asyncio.Queue()
    nq: asyncio.Queue = asyncio.Queue()
    await _poll_once(plugin, appConfigStub, q, nq, False)
    assert plugin.checkCalls == 1
    assert "check_availability" in toThreadCalls


async def test_attemptPurchaseAwaitsAsyncAutoBuy(appConfigStub, monkeypatch):
    plugin = _makeAsyncPlugin(name="async")
    toThreadCalls = []
    realToThread = asyncio.to_thread

    async def recorder(func, *args, **kwargs):
        toThreadCalls.append(getattr(func, "__name__", repr(func)))
        return await realToThread(func, *args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", recorder)
    q: asyncio.Queue = asyncio.Queue()
    nq: asyncio.Queue = asyncio.Queue()
    await _attempt_purchase(plugin, "https://async.example/x", "n", appConfigStub, q, nq)
    assert plugin.autoBuyCalls == 1
    assert "auto_buy" not in toThreadCalls


async def test_attemptPurchaseToThreadSyncAutoBuy(appConfigStub, monkeypatch):
    plugin = _makeSyncPlugin(name="sync")
    toThreadCalls = []
    realToThread = asyncio.to_thread

    async def recorder(func, *args, **kwargs):
        toThreadCalls.append(getattr(func, "__name__", repr(func)))
        return await realToThread(func, *args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", recorder)
    q: asyncio.Queue = asyncio.Queue()
    nq: asyncio.Queue = asyncio.Queue()
    await _attempt_purchase(plugin, "https://sync.example/x", "n", appConfigStub, q, nq)
    assert plugin.autoBuyCalls == 1
    assert "auto_buy" in toThreadCalls


def test_mainImportsInspect():
    src = _read_main()
    assert "import inspect" in src, "main.py must `import inspect`"


def test_mainUsesIscoroutinefunctionForCheck():
    src = _read_main()
    assert "iscoroutinefunction(plugin.check_availability" in src


def test_mainUsesIscoroutinefunctionForAutoBuy():
    src = _read_main()
    assert "iscoroutinefunction(plugin.auto_buy" in src


def test_pollPluginNoLongerReadsAppDelay():
    src = _read_main()
    # poll_plugin must use plugin.next_delay() instead of app_config.app.delay
    assert "plugin.next_delay()" in src
    # the literal `app_config.app.delay` line must be gone from poll_plugin
    assert "app_config.app.delay" not in src
