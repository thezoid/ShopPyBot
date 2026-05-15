"""Phase 5 RED skeleton for NOTIF-03 (see 05-01-PLAN.md).

All tests in this file FAIL today (ImportError at collection) until Plan
05-02 ships notifiers/shopbot_notifier_sound.py.
"""
import ast
import threading
from datetime import datetime, timezone
from pathlib import Path

import pytest

# RED: notifiers.shopbot_notifier_sound does not exist yet (Plan 05-02 target).
from notifiers.shopbot_notifier_sound import SoundNotifier  # type: ignore[import-not-found]
from notifier_base import NotificationEvent


def test_soundNotifierImportable():
    assert SoundNotifier is not None


def test_classLockExists():
    assert isinstance(SoundNotifier._lock, type(threading.Lock()))


def test_sendUsesAsyncToThread():
    src = Path("notifiers/shopbot_notifier_sound.py").read_text()
    tree = ast.parse(src)
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "to_thread":
            found = True
            break
    assert found, "expected asyncio.to_thread in shopbot_notifier_sound.py"


@pytest.mark.asyncio
async def test_sendDispatchesByAction(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        "notifiers.shopbot_notifier_sound.play_available_sound",
        lambda: calls.append("available"),
    )
    monkeypatch.setattr(
        "notifiers.shopbot_notifier_sound.play_buy_sound",
        lambda: calls.append("buy"),
    )
    from config_schema import SoundNotifierConfig

    notifier = SoundNotifier(SoundNotifierConfig(enabled=True))
    event = NotificationEvent(
        item_name="x", url="https://e/x", platform="amazon",
        timestamp=datetime.now(timezone.utc), action="detected",
    )
    await notifier.send(event)
    assert calls == ["available"]
