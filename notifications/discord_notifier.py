"""DiscordNotifier: posts a standardized embed to a Discord webhook (NOTIF-04).

Security contract (T-05-04):
  - Webhook URL is read from env DISCORD_WEBHOOK_URL; never logged, never stored
    as a visible attribute.
  - On HTTPError the failure path logs only exc.__class__.__name__ + HTTP status;
    never str(exc), repr(exc), or the webhook URL (Pitfall 1 from RESEARCH).

Transport:
  - Blocking requests.post runs via loop.run_in_executor so it never stalls the
    async event loop.
  - 204 No Content is treated as success (raise_for_status passes through).
  - 429 raises RuntimeError with the Retry-After value so callers can log and
    continue; no retry loop in this scope (T-05-05 accept).
"""

import asyncio

import requests

from core.credentials import get_store
from logger import writeLog
from notifications.base import Notifier, NotificationEvent
from datetime import timezone


def _build_discord_payload(event: NotificationEvent) -> dict:
    """Construct the Discord embed payload from a NotificationEvent."""
    color = 0x57F287 if event.action == "detected" else 0xFEE75C
    timestamp = event.timestamp.astimezone(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z"
    )
    return {
        "embeds": [
            {
                "title": f"{event.item_name} — {event.action.capitalize()}",
                "url": event.item_url,
                "color": color,
                "timestamp": timestamp,
                "fields": [
                    {"name": "Platform", "value": event.platform, "inline": True},
                    {"name": "Action", "value": event.action, "inline": True},
                ],
            }
        ]
    }


def _send_discord_blocking(webhook_url: str, payload: dict) -> None:
    """POST payload to webhook_url synchronously. Raises on non-2xx or 429."""
    resp = requests.post(webhook_url, json=payload, timeout=10)
    if resp.status_code == 429:
        retry_after = resp.headers.get("Retry-After", "unknown")
        raise RuntimeError(
            f"Discord rate-limited; retry after {retry_after}s"
        )
    resp.raise_for_status()
    # 204 No Content passes through -- success


class DiscordNotifier(Notifier):
    """Posts a Discord embed for each NotificationEvent."""

    def __init__(self) -> None:
        # Read once at construction; never stored as a logged attribute name.
        url = get_store().get("DISCORD_WEBHOOK_URL")
        if not url:
            raise ValueError("DISCORD_WEBHOOK_URL not configured")
        self._webhook_url = url

    async def send(self, event: NotificationEvent) -> None:
        """Build and POST the embed; run blocking I/O in executor."""
        payload = _build_discord_payload(event)
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(
                None, _send_discord_blocking, self._webhook_url, payload
            )
        except requests.HTTPError as exc:
            # Secret-safe: log only class name + status, never str(exc) or URL.
            status = exc.response.status_code if exc.response is not None else "?"
            writeLog(
                f"[DiscordNotifier] HTTP {status} -- delivery failed",
                "ERROR",
            )
            raise
