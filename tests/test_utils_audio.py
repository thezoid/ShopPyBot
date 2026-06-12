"""Tests for pygame headless guard in utils.py (SRV-01).

Covers:
  - utils imports successfully even when pygame is not installed (CR-01)
  - _AUDIO_AVAILABLE is False when pygame import is absent (CR-01)
  - play_sound is a silent no-op (no exception, no mixer call) when pygame absent (CR-01)
  - _initialize_audio returns False when pygame.mixer.init raises pygame.error
  - _initialize_audio returns True when pygame.mixer.init succeeds
  - play_sound is a silent no-op (no exception, no mixer call) when _AUDIO_AVAILABLE is False
  - play_sound catches pygame.error from load/play and does not propagate (WR-03)
  - SoundNotifier.send does not raise when _AUDIO_AVAILABLE is False
"""

import importlib
import sys
import types
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

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


# ---------------------------------------------------------------------------
# CR-01: import-failure simulation -- non-vacuous test
# ---------------------------------------------------------------------------

def test_utils_imports_without_pygame(monkeypatch):
    """utils module must import cleanly when pygame is not installed (SRV-01 / CR-01).

    Simulates a missing pygame by temporarily removing it from sys.modules and
    blocking re-import, then reloading utils. The reloaded module must have
    _AUDIO_AVAILABLE=False and play_sound must be a no-op.
    """
    # Save original state
    original_pygame = sys.modules.get("pygame")
    original_utils = sys.modules.get("utils")

    # Block pygame import
    sys.modules["pygame"] = None  # type: ignore[assignment]
    # Remove utils so it reloads fresh
    sys.modules.pop("utils", None)

    try:
        fresh_utils = importlib.import_module("utils")
        assert fresh_utils._AUDIO_AVAILABLE is False, (
            "_AUDIO_AVAILABLE must be False when pygame is not installed"
        )
        assert fresh_utils._PYGAME_AVAILABLE is False, (
            "_PYGAME_AVAILABLE must be False when pygame is not installed"
        )
        # play_sound must be a no-op (no exception, returns None)
        result = fresh_utils.play_sound("notification")
        assert result is None
    finally:
        # Restore original sys.modules state
        if original_pygame is None:
            sys.modules.pop("pygame", None)
        else:
            sys.modules["pygame"] = original_pygame
        sys.modules.pop("utils", None)
        if original_utils is not None:
            sys.modules["utils"] = original_utils


# ---------------------------------------------------------------------------
# Existing mixer-init tests (use utils._pygame since refactor renamed the ref)
# ---------------------------------------------------------------------------

def test_initialize_audio_returns_false_on_pygame_error():
    """_initialize_audio returns False when mixer.init raises pygame.error."""
    _pygame = utils._pygame
    if _pygame is None:
        pytest.skip("pygame not installed on this host")
    with patch.object(_pygame.mixer, "init", side_effect=_pygame.error("no audio device")):
        result = utils._initialize_audio()
    assert result is False


def test_initialize_audio_returns_true_on_success():
    """_initialize_audio returns True when mixer.init succeeds."""
    _pygame = utils._pygame
    if _pygame is None:
        pytest.skip("pygame not installed on this host")
    with patch.object(_pygame.mixer, "init", return_value=None):
        result = utils._initialize_audio()
    assert result is True


def test_play_sound_noop_when_audio_unavailable(monkeypatch):
    """play_sound returns None without touching pygame.mixer when _AUDIO_AVAILABLE is False."""
    _pygame = utils._pygame
    monkeypatch.setattr(utils, "_AUDIO_AVAILABLE", False)
    mock_load = MagicMock()
    if _pygame is not None:
        with patch.object(_pygame.mixer.music, "load", mock_load):
            result = utils.play_sound("notification")
    else:
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


def test_play_sound_catches_pygame_error_from_load(monkeypatch):
    """play_sound swallows pygame.error raised by mixer.music.load (WR-03)."""
    _pygame = utils._pygame
    if _pygame is None:
        pytest.skip("pygame not installed on this host")
    monkeypatch.setattr(utils, "_AUDIO_AVAILABLE", True)
    monkeypatch.setattr(utils, "_pygame", _pygame)
    with patch.object(_pygame.mixer.music, "load", side_effect=_pygame.error("bad codec")):
        # Must not raise
        utils.play_sound("notification")


def test_play_sound_catches_pygame_error_from_play(monkeypatch):
    """play_sound swallows pygame.error raised by mixer.music.play (WR-03)."""
    _pygame = utils._pygame
    if _pygame is None:
        pytest.skip("pygame not installed on this host")
    monkeypatch.setattr(utils, "_AUDIO_AVAILABLE", True)
    monkeypatch.setattr(utils, "_pygame", _pygame)
    with patch.object(_pygame.mixer.music, "load", return_value=None):
        with patch.object(_pygame.mixer.music, "play", side_effect=_pygame.error("device torn down")):
            # Must not raise
            utils.play_sound("notification")


@pytest.mark.asyncio
async def test_sound_notifier_no_audio(monkeypatch):
    """SoundNotifier.send does not raise when audio is unavailable."""
    monkeypatch.setattr(utils, "_AUDIO_AVAILABLE", False)
    notifier = SoundNotifier()
    for action in ("detected", "purchased", "health_degraded"):
        event = _make_event(action)
        await notifier.send(event)  # must not raise
