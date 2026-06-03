"""SoundNotifier: wraps pygame sound helpers from utils.py (NOTIF-03).

Dispatches by event.action:
  "detected"  -> play_available_sound()
  "purchased" -> play_buy_sound()
  <other>     -> play_notification_sound()

Sound calls are synchronous and stay on the calling thread. Per RESEARCH
Open Question 3, pygame.mixer is not confirmed thread-safe; the dispatcher
must not route SoundNotifier through run_in_executor.
"""

from notifications.base import Notifier, NotificationEvent
from utils import play_available_sound, play_buy_sound, play_notification_sound


class SoundNotifier(Notifier):
    """Plays an audio cue appropriate to the notification event action."""

    async def send(self, event: NotificationEvent) -> None:
        """Dispatch by action and call the matching utils play_* function."""
        if event.action == "detected":
            play_available_sound()
        elif event.action == "purchased":
            play_buy_sound()
        else:
            play_notification_sound()
