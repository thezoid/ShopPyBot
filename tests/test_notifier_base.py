"""Phase 5 RED skeleton for ABC contract (see 05-01-PLAN.md).

Tests that fail at collection (ImportError) are the canonical RED signal for
the matching plan; the matching plan flips them GREEN. Tests in this file
PASS today because Plan 05-01 ships the Notifier ABC + NotificationEvent;
they serve as a regression net, not a RED target.
"""
import inspect
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from notifier_base import NOTIFIER_API_VERSION, NotificationEvent, Notifier


def test_notifierApiVersionIsOne():
    assert NOTIFIER_API_VERSION == 1


def test_sendIsAbstractCoroutine():
    assert inspect.iscoroutinefunction(Notifier.send)
    assert Notifier.send.__isabstractmethod__ is True


def test_shutdownIsAsyncDefault():
    assert inspect.iscoroutinefunction(Notifier.shutdown)


@pytest.mark.asyncio
async def test_shutdownDefaultReturnsNone():
    class _Concrete(Notifier):
        async def send(self, event):
            return None

    inst = _Concrete()
    assert await inst.shutdown() is None


def test_notificationEventIsFrozen():
    event = NotificationEvent(
        item_name="Widget",
        url="https://example.com/widget",
        platform="amazon",
        timestamp=datetime.now(timezone.utc),
        action="detected",
    )
    with pytest.raises(FrozenInstanceError):
        event.item_name = "Other"  # type: ignore[misc]


def test_notifierCannotInstantiateWithoutSend():
    with pytest.raises(TypeError):
        Notifier()  # type: ignore[abstract]
