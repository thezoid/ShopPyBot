"""NotificationDispatcher: fan-out with per-channel isolation (NOTIF-01).

Dispatches a NotificationEvent to every registered Notifier. Each notifier
runs inside its own try/except so a single channel failure never blocks or
propagates to other channels. Error log contains only the notifier class name
and exception class name -- never str(exc), repr(exc), or any secret such as
a webhook URL, SMTP password, or Twilio token (T-05-11).
"""

from notifications.base import Notifier, NotificationEvent


class NotificationDispatcher:
    """Fan-out dispatcher: calls every registered notifier for each event.

    Args:
        notifiers: List of Notifier instances to invoke in order.

    Usage::
        dispatcher = NotificationDispatcher([sound, discord, email])
        await dispatcher.notify(event)
    """

    def __init__(self, notifiers: list[Notifier]) -> None:
        self._notifiers = notifiers

    async def notify(self, event: NotificationEvent) -> None:
        """Deliver event to all registered notifiers with per-channel isolation.

        A channel failure is logged at ERROR with the notifier class name and
        exception class name only. The failure does NOT propagate and does NOT
        prevent subsequent notifiers from being called (NOTIF-01 / T-05-12).
        KeyboardInterrupt and SystemExit pass through because we catch
        Exception, not BaseException (T-05-13).
        """
        from logger import writeLog

        for notifier in self._notifiers:
            try:
                await notifier.send(event)
            except Exception as exc:
                writeLog(
                    f"[{notifier.__class__.__name__}] notification failed:"
                    f" {exc.__class__.__name__}",
                    "ERROR",
                )
