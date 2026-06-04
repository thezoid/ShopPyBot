"""notifications package -- fan-out notification dispatcher (Phase 5).

Exports:
  Notifier                -- ABC for all channel implementations
  NotificationEvent       -- event dataclass passed to all notifiers
  NotificationDispatcher  -- fan-out dispatcher with per-channel isolation
  build_dispatcher        -- factory: build dispatcher from AppConfig
"""

from core.credentials import get_store
from notifications.base import Notifier, NotificationEvent
from notifications.dispatcher import NotificationDispatcher

__all__ = ["Notifier", "NotificationEvent", "NotificationDispatcher", "build_dispatcher"]


def build_dispatcher(cfg) -> NotificationDispatcher:
    """Build a NotificationDispatcher from the notifications section of AppConfig.

    Notifiers included based on enable flags:
      - SoundNotifier always included when cfg.notifications.sound is True.
      - DiscordNotifier included when discord.enabled AND DISCORD_WEBHOOK_URL env var is set.
      - EmailNotifier included when email.enabled.
      - SmsNotifier included when sms.enabled (creds validated by SmsConfig at startup).

    Args:
        cfg: AppConfig instance (or any object with a .notifications attribute).

    Returns:
        NotificationDispatcher holding the enabled notifiers.
    """
    from notifications.sound_notifier import SoundNotifier
    from notifications.discord_notifier import DiscordNotifier
    from notifications.email_notifier import EmailNotifier
    from notifications.sms_notifier import SmsNotifier

    notifiers: list[Notifier] = []
    notif = cfg.notifications

    if notif.sound:
        notifiers.append(SoundNotifier())

    discord_url = get_store().get("DISCORD_WEBHOOK_URL")
    if notif.discord.enabled and discord_url:
        notifiers.append(DiscordNotifier(discord_url))

    if notif.email.enabled:
        notifiers.append(EmailNotifier(notif.email))

    if notif.sms.enabled:
        notifiers.append(SmsNotifier(notif.sms))

    return NotificationDispatcher(notifiers)
