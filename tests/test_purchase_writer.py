"""Phase 4 GREEN: tests for ASYNC-05 (purchase_writer)."""
import ast
import asyncio
from pathlib import Path

import pytest

from main import purchase_writer


MAIN_PY_PATH = Path(__file__).resolve().parent.parent / "main.py"


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


def test_writerCrashIsFatal():
    """Pitfall 4-10: purchase_writer crash must propagate out of TaskGroup.

    The writer body must have EXACTLY ONE try/except (the inner one around
    update_item_purchased). A defensive outer try/except would swallow
    infrastructure failures and violate Pitfall 4-10.
    """
    src = MAIN_PY_PATH.read_text(encoding="utf-8")
    tree = ast.parse(src)
    writerFn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "purchase_writer"
    )
    tryNodes = [n for n in ast.walk(writerFn) if isinstance(n, ast.Try)]
    assert len(tryNodes) == 1, (
        f"purchase_writer must have exactly 1 try/except (around update_item_purchased); "
        f"found {len(tryNodes)}. Defensive outer try/except violates Pitfall 4-10."
    )
