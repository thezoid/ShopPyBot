"""notifications package — fan-out notification dispatcher (Phase 5).

Exports available at Wave 0 (Plan 05-01):
  Notifier           -- ABC for all channel implementations
  NotificationEvent  -- event dataclass passed to all notifiers

NotificationDispatcher is added in Plan 05-04. Import it conditionally
until that plan lands:

    from notifications import NotificationDispatcher  # available after 05-04
"""

from notifications.base import Notifier, NotificationEvent

__all__ = ["Notifier", "NotificationEvent"]

# NotificationDispatcher forward-declaration: imported lazily so this package
# remains importable in Plans 02-03 before the dispatcher exists.
try:
    from notifications.dispatcher import NotificationDispatcher  # noqa: F401
    __all__.append("NotificationDispatcher")
except ImportError:
    pass
