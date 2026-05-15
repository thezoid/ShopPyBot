"""GREEN tests for NOTIF-03 SoundNotifier (Plan 05-02).

Verifies: importability, class-level threading.Lock, asyncio.to_thread in send(),
action-to-sound dispatch (detected -> available, purchased -> buy), exception
swallowing with WARNING log, and lock-held-during-play under concurrent gather.
"""
import ast
import asyncio
import threading
from datetime import datetime, timezone
from pathlib import Path

import pytest

from notifiers.shopbot_notifier_sound import SoundNotifier
from notifier_base import NotificationEvent
from config_schema import SoundNotifierConfig


def _event(action: str = "detected") -> NotificationEvent:
    return NotificationEvent(
        item_name="x",
        url="https://e/x",
        platform="amazon",
        timestamp=datetime.now(timezone.utc),
        action=action,
    )


def _make(enabled: bool = True) -> SoundNotifier:
    return SoundNotifier(sub_config=SoundNotifierConfig(enabled=enabled), app_config=None)


def test_soundNotifierImportable():
    assert SoundNotifier is not None
    assert SoundNotifier.name == "sound"


def test_classLockExists():
    assert isinstance(SoundNotifier._lock, type(threading.Lock()))


def test_lockIsClassLevelSharedAcrossInstances():
    a = _make()
    b = _make()
    assert a._lock is b._lock
    assert a._lock is SoundNotifier._lock


def test_enabledFromSubConfig():
    assert _make(enabled=True).enabled is True
    assert _make(enabled=False).enabled is False


def test_enabledFalseWhenSubConfigNone():
    n = SoundNotifier(sub_config=None, app_config=None)
    assert n.enabled is False


def test_sendUsesAsyncToThread():
    src = Path("notifiers/shopbot_notifier_sound.py").read_text()
    tree = ast.parse(src)
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "send":
            for child in ast.walk(node):
                if isinstance(child, ast.Attribute) and child.attr == "to_thread":
                    found = True
                    break
    assert found, "expected asyncio.to_thread inside SoundNotifier.send body"


def test_sourceImportsBothSoundHelpers():
    src = Path("notifiers/shopbot_notifier_sound.py").read_text()
    assert "play_available_sound" in src
    assert "play_buy_sound" in src
    assert "play_notification_sound" not in src


@pytest.mark.asyncio
async def test_sendDetectedPlaysAvailable(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        "notifiers.shopbot_notifier_sound.play_available_sound",
        lambda: calls.append("available"),
    )
    monkeypatch.setattr(
        "notifiers.shopbot_notifier_sound.play_buy_sound",
        lambda: calls.append("buy"),
    )

    await _make().send(_event(action="detected"))

    assert calls == ["available"]


@pytest.mark.asyncio
async def test_sendPurchasedPlaysBuy(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        "notifiers.shopbot_notifier_sound.play_available_sound",
        lambda: calls.append("available"),
    )
    monkeypatch.setattr(
        "notifiers.shopbot_notifier_sound.play_buy_sound",
        lambda: calls.append("buy"),
    )

    await _make().send(_event(action="purchased"))

    assert calls == ["buy"]


@pytest.mark.asyncio
async def test_sendSwallowsPlaybackException(monkeypatch):
    def boom() -> None:
        raise RuntimeError("missing sound file")

    monkeypatch.setattr(
        "notifiers.shopbot_notifier_sound.play_available_sound", boom
    )

    logged: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "notifiers.shopbot_notifier_sound.writeLog",
        lambda msg, level: logged.append((msg, level)),
    )

    await _make().send(_event(action="detected"))

    assert any("playback failed" in msg for msg, _ in logged)


@pytest.mark.asyncio
async def test_concurrentSendsSerializeViaLock(monkeypatch):
    """Each play call observes cls._lock as held; concurrent sends do not interleave."""
    observedHeld: list[bool] = []

    def recorder() -> None:
        observedHeld.append(SoundNotifier._lock.locked())

    monkeypatch.setattr(
        "notifiers.shopbot_notifier_sound.play_available_sound", recorder
    )

    notifier = _make()
    await asyncio.gather(*(notifier.send(_event()) for _ in range(4)))

    assert len(observedHeld) == 4
    assert all(observedHeld), "lock should be held during each play call"
    assert SoundNotifier._lock.locked() is False
