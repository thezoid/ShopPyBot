"""Phase 5 GREEN tests for notification_writer (Plan 05-06).

Covers:
- notification_writer is an async coroutine (Task 1 contract)
- NOTIF-01: one failed notifier does not block siblings (gather isolation)
- NOTIF-02 carve-out: purchased events bypass should_notify dedup gate
- Pitfall #8: queue.task_done() fires in finally even when inner body raises
- CONTEXT pitfall #1: mark_notified failure logs ERROR but does not crash writer
"""
import asyncio
import inspect
from datetime import datetime, timezone

import pytest

from main import notification_writer
from notifier_base import NotificationEvent


def _makeEvent(action="detected", url="https://example.com/item"):
    return NotificationEvent(
        item_name="Widget",
        url=url,
        platform="amazon",
        timestamp=datetime.now(timezone.utc),
        action=action,
    )


async def _drainAndStop(task, queue, timeout=2.0):
    await asyncio.wait_for(queue.join(), timeout=timeout)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


def test_notificationWriterIsAsyncCoroutine():
    assert inspect.iscoroutinefunction(notification_writer)


@pytest.mark.asyncio
async def test_oneFailedNotifierDoesNotBlockOthers(fakeNotifierFactory, monkeypatch):
    monkeypatch.setattr("main.should_notify", lambda url, w: True)
    monkeypatch.setattr("main.mark_notified", lambda url: None)
    failed = fakeNotifierFactory(name="bad", sendRaises=RuntimeError("boom"))
    ok = fakeNotifierFactory(name="good")
    queue: asyncio.Queue = asyncio.Queue(maxsize=10)
    await queue.put(_makeEvent())
    task = asyncio.create_task(notification_writer(queue, [failed, ok], 600))
    await _drainAndStop(task, queue)
    assert ok.sendCalls == 1
    assert failed.sendCalls == 1


@pytest.mark.asyncio
async def test_purchasedActionBypassesDedup(fakeNotifierFactory, monkeypatch):
    markCalls: list = []
    monkeypatch.setattr("main.should_notify", lambda url, w: False)
    monkeypatch.setattr("main.mark_notified", lambda url: markCalls.append(url))
    notifier = fakeNotifierFactory(name="ok")
    queue: asyncio.Queue = asyncio.Queue(maxsize=10)
    await queue.put(_makeEvent(action="purchased"))
    task = asyncio.create_task(notification_writer(queue, [notifier], 600))
    await _drainAndStop(task, queue)
    assert notifier.sendCalls == 1
    assert markCalls == [], "purchased events must NOT call mark_notified"


@pytest.mark.asyncio
async def test_taskDoneCalledInFinally(fakeNotifierFactory, monkeypatch):
    def boom(url, w):
        raise RuntimeError("dedup blew up")

    monkeypatch.setattr("main.should_notify", boom)
    monkeypatch.setattr("main.mark_notified", lambda url: None)
    notifier = fakeNotifierFactory(name="ok")
    queue: asyncio.Queue = asyncio.Queue(maxsize=10)
    await queue.put(_makeEvent())
    task = asyncio.create_task(notification_writer(queue, [notifier], 600))
    # If task_done fired in finally, queue.join() resolves; otherwise it hangs.
    # The writer itself crashes (FATAL by design), but task_done in finally
    # unblocks queue.join() before that crash propagates.
    try:
        await asyncio.wait_for(queue.join(), timeout=1.0)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_markNotifiedFailureLoggedNotCrashed(fakeNotifierFactory, monkeypatch):
    logCalls: list = []
    monkeypatch.setattr("main.should_notify", lambda url, w: True)

    def boom(url):
        raise RuntimeError("db locked")

    monkeypatch.setattr("main.mark_notified", boom)

    def fakeLog(msg, level="INFO"):
        logCalls.append((level, msg))

    monkeypatch.setattr("main.writeLog", fakeLog)
    notifier = fakeNotifierFactory(name="ok")
    queue: asyncio.Queue = asyncio.Queue(maxsize=10)
    await queue.put(_makeEvent())
    await queue.put(_makeEvent(url="https://example.com/item2"))
    task = asyncio.create_task(notification_writer(queue, [notifier], 600))
    await _drainAndStop(task, queue)
    # Writer survived both events despite mark_notified raising on each.
    assert notifier.sendCalls == 2
    assert any("mark_notified failed" in m for _, m in logCalls)
