"""Phase 5 RED skeleton for notification_writer (see 05-01-PLAN.md).

All tests in this file FAIL today (ImportError at collection) until Plan
05-06 ships main.notification_writer. Covers NOTIF-01 fan-out isolation,
dedup gating, purchased-bypass, and task_done-in-finally.
"""
import asyncio
import inspect
from datetime import datetime, timezone

import pytest

# RED: main.notification_writer does not exist yet (Plan 05-06 target).
from main import notification_writer  # type: ignore[attr-defined]
from notifier_base import NotificationEvent


def _makeEvent(action="detected", url="https://example.com/item"):
    return NotificationEvent(
        item_name="Widget",
        url=url,
        platform="amazon",
        timestamp=datetime.now(timezone.utc),
        action=action,
    )


def test_notificationWriterIsAsyncCoroutine():
    assert inspect.iscoroutinefunction(notification_writer)


@pytest.mark.asyncio
async def test_oneFailedNotifierDoesNotBlockOthers(fakeNotifierFactory, monkeypatch):
    monkeypatch.setattr("models.should_notify", lambda url, w: True)
    monkeypatch.setattr("models.mark_notified", lambda url: None)
    failed = fakeNotifierFactory(name="bad", sendRaises=RuntimeError("boom"))
    ok = fakeNotifierFactory(name="good")
    queue: asyncio.Queue = asyncio.Queue()
    await queue.put(_makeEvent())
    task = asyncio.create_task(notification_writer(queue, [failed, ok], 600))
    await queue.join()
    task.cancel()
    assert ok.sendCalls == 1


@pytest.mark.asyncio
async def test_purchasedActionBypassesDedup(fakeNotifierFactory, monkeypatch):
    monkeypatch.setattr("models.should_notify", lambda url, w: False)
    monkeypatch.setattr("models.mark_notified", lambda url: None)
    notifier = fakeNotifierFactory(name="ok")
    queue: asyncio.Queue = asyncio.Queue()
    await queue.put(_makeEvent(action="purchased"))
    task = asyncio.create_task(notification_writer(queue, [notifier], 600))
    await queue.join()
    task.cancel()
    assert notifier.sendCalls == 1


@pytest.mark.asyncio
async def test_taskDoneCalledInFinally(fakeNotifierFactory, monkeypatch):
    def boom(url, w):
        raise RuntimeError("dedup blew up")

    monkeypatch.setattr("models.should_notify", boom)
    notifier = fakeNotifierFactory(name="ok")
    queue: asyncio.Queue = asyncio.Queue()
    await queue.put(_makeEvent())
    task = asyncio.create_task(notification_writer(queue, [notifier], 600))
    await asyncio.wait_for(queue.join(), timeout=1.0)
    task.cancel()
