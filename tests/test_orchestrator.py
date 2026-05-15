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
