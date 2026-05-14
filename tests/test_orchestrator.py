"""Phase 4 RED skeleton for ASYNC-01 and ASYNC-03 (see 04-01-PLAN.md).

All tests in this file are expected to FAIL until Plan 04-04 lands.
ASYNC-01: asyncio.TaskGroup orchestrator with per-plugin task isolation.
ASYNC-03: blocking input() bridged via asyncio.to_thread.
"""
import ast
import asyncio
from pathlib import Path

import pytest

from main import poll_plugin, purchase_writer  # noqa: F401 — ImportError is the RED signal


MAIN_PY_PATH = Path(__file__).resolve().parent.parent / "main.py"


async def test_pluginCrashIsolated(appConfigStub, fakePluginFactory):
    """One plugin raising must not cancel sibling plugin tasks."""
    goodPlugin = fakePluginFactory(name="good", checkReturns=False)
    badPlugin = fakePluginFactory(
        name="bad",
        checkRaises=RuntimeError("simulated crash"),
    )
    queue: asyncio.Queue = asyncio.Queue()

    async with asyncio.TaskGroup() as tg:
        tg.create_task(poll_plugin(goodPlugin, appConfigStub, queue))
        tg.create_task(poll_plugin(badPlugin, appConfigStub, queue))
        await asyncio.sleep(0.05)
        for task in asyncio.all_tasks() - {asyncio.current_task()}:
            task.cancel()

    assert goodPlugin.checkCalls >= 1, "good plugin must keep being polled after bad plugin raises"


def test_inputBridgedViaToThread():
    """No bare input() call may appear inside any async def body in main.py."""
    source = MAIN_PY_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    mainFunc = next(
        (node for node in ast.walk(tree)
         if isinstance(node, ast.AsyncFunctionDef) and node.name == "main"),
        None,
    )
    assert mainFunc is not None, "main() must be async (`async def main()`) for ASYNC-03"

    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef):
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                assert child.func.id != "input", (
                    f"bare input() found in async def {node.name}; "
                    "use `await asyncio.to_thread(input, ...)` instead"
                )


def test_executorConfiguredBeforeTaskGroup():
    """ThreadPoolExecutor must be set on the loop before TaskGroup spawns plugin tasks."""
    source = MAIN_PY_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    executorLine = None
    taskGroupLine = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "set_default_executor":
                executorLine = node.lineno
        if isinstance(node, ast.AsyncWith):
            for item in node.items:
                expr = item.context_expr
                if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute):
                    if expr.func.attr == "TaskGroup":
                        taskGroupLine = node.lineno

    assert executorLine is not None, "main.py must call loop.set_default_executor(...)"
    assert taskGroupLine is not None, "main.py must use `async with asyncio.TaskGroup()`"
    assert executorLine < taskGroupLine, (
        "set_default_executor must run BEFORE TaskGroup starts; "
        f"got executor at line {executorLine} and TaskGroup at line {taskGroupLine}"
    )
