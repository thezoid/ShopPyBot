import os

try:
    import pygame as _pygame
    _PYGAME_AVAILABLE = True
except (ModuleNotFoundError, ImportError):
    _pygame = None  # type: ignore[assignment]
    _PYGAME_AVAILABLE = False

from logger import writeLog

# Define the path to the sounds directory
SOUNDS_DIR = os.path.join(os.path.dirname(__file__), 'sounds')


def _initialize_audio() -> bool:
    """Attempt pygame mixer init. Return True on success, False on failure."""
    if not _PYGAME_AVAILABLE:
        writeLog("pygame not installed -- sound notifications disabled", "INFO")
        return False
    try:
        _pygame.mixer.init()
        return True
    except _pygame.error as exc:
        writeLog(
            f"Audio device unavailable ({exc.__class__.__name__}) -- sound notifications disabled",
            "INFO",
        )
        return False


_AUDIO_AVAILABLE: bool = _initialize_audio()


def play_sound(file_name):
    if not _AUDIO_AVAILABLE:
        return
    writeLog(f"Attempting to play sound: {file_name}", "DEBUG")
    mp3_path = os.path.join(SOUNDS_DIR, f"{file_name}.mp3")
    wav_path = os.path.join(SOUNDS_DIR, f"{file_name}.wav")
    try:
        if os.path.exists(mp3_path):
            _pygame.mixer.music.load(mp3_path)
        elif os.path.exists(wav_path):
            _pygame.mixer.music.load(wav_path)
        else:
            writeLog(f"Sound file {file_name}.mp3 or {file_name}.wav not found", "ERROR")
            return
        _pygame.mixer.music.play()
    except _pygame.error as exc:
        writeLog(f"Audio playback error ({exc.__class__.__name__}) -- skipping sound", "WARNING")

def play_notification_sound():
    writeLog("Playing notification sound", "DEBUG")
    play_sound("notification")

def play_buy_sound():
    writeLog("Playing buy sound", "DEBUG")
    play_sound("buy")

def play_available_sound():
    writeLog("Playing available sound", "DEBUG")
    play_sound("available")
