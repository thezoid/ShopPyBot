"""notifications package -- fan-out notification dispatcher (Phase 5).

Exports:
  Notifier                -- ABC for all channel implementations
  NotificationEvent       -- event dataclass passed to all notifiers
  NotificationDispatcher  -- fan-out dispatcher with per-channel isolation
"""

from notifications.base import Notifier, NotificationEvent
from notifications.dispatcher import NotificationDispatcher

__all__ = ["Notifier", "NotificationEvent", "NotificationDispatcher"]
