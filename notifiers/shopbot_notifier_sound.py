"""Sound notifier (NOTIF-03).

Wraps existing utils.play_available_sound / play_buy_sound in asyncio.to_thread
and serializes pygame.mixer.music access via a class-level threading.Lock
(RESEARCH Q5: pygame.mixer.music is single-channel; concurrent .load+.play from
worker threads can interleave and truncate).
"""
import asyncio
import threading

from logger import writeLog
from notifier_base import Notifier, NotificationEvent
from utils import play_available_sound, play_buy_sound


class SoundNotifier(Notifier):
    name = "sound"
    _lock = threading.Lock()

    def __init__(self, *, sub_config, app_config) -> None:
        self.enabled = bool(sub_config and sub_config.enabled)

    async def send(self, event: NotificationEvent) -> None:
        fn = play_buy_sound if event.action == "purchased" else play_available_sound
        await asyncio.to_thread(self._play_locked, fn)

    @classmethod
    def _play_locked(cls, fn) -> None:
        with cls._lock:
            try:
                fn()
            except Exception as e:
                writeLog(f"sound notifier: playback failed: {e}", "WARNING")
