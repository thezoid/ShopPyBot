"""Tests for pygame headless guard in utils.py (SRV-01).

Covers:
  - _initialize_audio returns False when pygame.mixer.init raises pygame.error
  - _initialize_audio returns True when pygame.mixer.init succeeds
  - play_sound is a silent no-op (no exception, no mixer call) when _AUDIO_AVAILABLE is False
  - SoundNotifier.send does not raise when _AUDIO_AVAILABLE is False
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

import pygame
import utils
from notifications.sound_notifier import SoundNotifier
from notifications.base import NotificationEvent


def _make_event(action: str = "detected") -> NotificationEvent:
    return NotificationEvent(
        item_name="Test Item",
        item_url="https://example.com/item",
        platform="TestPlatform",
        timestamp=datetime.utcnow(),
        action=action,
    )


def test_initialize_audio_returns_false_on_pygame_error():
    """_initialize_audio returns False when mixer.init raises pygame.error."""
    with patch.object(pygame.mixer, "init", side_effect=pygame.error("no audio device")):
        result = utils._initialize_audio()
    assert result is False


def test_initialize_audio_returns_true_on_success():
    """_initialize_audio returns True when mixer.init succeeds."""
    with patch.object(pygame.mixer, "init", return_value=None):
        result = utils._initialize_audio()
    assert result is True


def test_play_sound_noop_when_audio_unavailable(monkeypatch):
    """play_sound returns None without touching pygame.mixer when _AUDIO_AVAILABLE is False."""
    monkeypatch.setattr(utils, "_AUDIO_AVAILABLE", False)
    mock_load = MagicMock()
    with patch.object(pygame.mixer.music, "load", mock_load):
        result = utils.play_sound("notification")
    assert result is None
    mock_load.assert_not_called()


def test_play_sound_noop_does_not_raise(monkeypatch):
    """play_sound does not raise when _AUDIO_AVAILABLE is False."""
    monkeypatch.setattr(utils, "_AUDIO_AVAILABLE", False)
    # Should complete without any exception
    utils.play_sound("notification")
    utils.play_sound("buy")
    utils.play_sound("available")


@pytest.mark.asyncio
async def test_sound_notifier_no_audio(monkeypatch):
    """SoundNotifier.send does not raise when audio is unavailable."""
    monkeypatch.setattr(utils, "_AUDIO_AVAILABLE", False)
    notifier = SoundNotifier()
    for action in ("detected", "purchased", "health_degraded"):
        event = _make_event(action)
        await notifier.send(event)  # must not raise
