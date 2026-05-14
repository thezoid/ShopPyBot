"""Phase 4 RED skeleton for ASYNC-05 (see 04-01-PLAN.md).

All tests in this file are expected to FAIL until Plan 04-04 lands.
ASYNC-05: dedicated purchase_writer task drains an asyncio.Queue and calls
update_item_purchased; task_done() runs even when the write raises.
"""
import asyncio

import pytest

from main import purchase_writer  # noqa: F401 — ImportError is the RED signal


async def test_writerDrainsQueue(monkeypatch):
    """Two URLs put on the queue must both reach update_item_purchased in order."""
    recordedCalls: list[str] = []

    def recorder(link: str) -> None:
        recordedCalls.append(link)

    monkeypatch.setattr("models.update_item_purchased", recorder)

    queue: asyncio.Queue = asyncio.Queue()
    await queue.put(("https://example.com/a",))
    await queue.put(("https://example.com/b",))

    writerTask = asyncio.create_task(purchase_writer(queue))
    try:
        await asyncio.wait_for(queue.join(), timeout=1.0)
    finally:
        writerTask.cancel()
        try:
            await writerTask
        except asyncio.CancelledError:
            pass

    assert recordedCalls == ["https://example.com/a", "https://example.com/b"]


async def test_taskDoneOnFailure(monkeypatch):
    """queue.join() must return even when update_item_purchased raises (task_done in finally)."""
    def raiser(link: str) -> None:
        raise RuntimeError("simulated write failure")

    monkeypatch.setattr("models.update_item_purchased", raiser)

    queue: asyncio.Queue = asyncio.Queue()
    await queue.put(("https://example.com/fail",))

    writerTask = asyncio.create_task(purchase_writer(queue))
    try:
        await asyncio.wait_for(queue.join(), timeout=1.0)
    finally:
        writerTask.cancel()
        try:
            await writerTask
        except asyncio.CancelledError:
            pass
