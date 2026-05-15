"""Discord webhook notifier (NOTIF-04).

Posts a Discord embed to a webhook URL read from SHOPBOT_DISCORD_WEBHOOK_URL
env var. On a 429 response, honors the Retry-After header once (capped at 30
seconds), then gives up + logs. NEVER blocks the writer for more than one retry.

Webhook URL is read ONCE at __init__ (CONTEXT pitfall #4). Reading env vars
inside send() is FORBIDDEN by the must_haves contract.
"""
import asyncio
import os
import time
from datetime import timezone

import requests

from logger import writeLog
from notifier_base import Notifier, NotificationEvent

_DETECTED_COLOR = 0x2ECC71
_PURCHASED_COLOR = 0x3498DB
_MAX_RETRY_WAIT_SECONDS = 30.0
_HTTP_TIMEOUT_SECONDS = 10


class DiscordNotifier(Notifier):
    name = "discord"

    def __init__(self, *, sub_config=None, app_config=None) -> None:
        wantedEnabled = bool(sub_config and getattr(sub_config, "enabled", False))
        self.webhook_url = os.environ.get("SHOPBOT_DISCORD_WEBHOOK_URL", "")
        if not wantedEnabled:
            self.enabled = False
            return
        if not self.webhook_url:
            writeLog(
                "Discord notifier: config.discord.enabled=true but "
                "SHOPBOT_DISCORD_WEBHOOK_URL env var is missing; disabling.",
                "WARNING",
            )
            self.enabled = False
            return
        self.enabled = True

    async def send(self, event: NotificationEvent) -> None:
        payload = _build_payload(event)
        await asyncio.to_thread(self._post_with_one_retry, payload)

    def _post_with_one_retry(self, payload: dict) -> None:
        r = requests.post(
            self.webhook_url, json=payload, timeout=_HTTP_TIMEOUT_SECONDS
        )
        if r.status_code == 429:
            wait = _retry_after_seconds(r)
            time.sleep(min(wait, _MAX_RETRY_WAIT_SECONDS))
            r = requests.post(
                self.webhook_url, json=payload, timeout=_HTTP_TIMEOUT_SECONDS
            )
            if r.status_code == 429:
                event_url = payload["embeds"][0].get("url")
                writeLog(
                    f"Discord notifier: 429 after one retry; giving up "
                    f"(event url={event_url})",
                    "WARNING",
                )
                return
        r.raise_for_status()


def _build_payload(event: NotificationEvent) -> dict:
    color = _PURCHASED_COLOR if event.action == "purchased" else _DETECTED_COLOR
    return {
        "embeds": [{
            "title": f"{event.platform}: {event.item_name}",
            "description": f"Action: **{event.action}**",
            "url": event.url,
            "color": color,
            "timestamp": event.timestamp.astimezone(timezone.utc).isoformat(),
            "fields": [
                {"name": "Platform", "value": event.platform, "inline": True},
                {"name": "Action", "value": event.action, "inline": True},
            ],
        }]
    }


def _retry_after_seconds(response) -> float:
    header = response.headers.get("Retry-After")
    if header is not None:
        try:
            return float(header)
        except (TypeError, ValueError):
            pass
    try:
        body = response.json()
    except Exception:
        return 1.0
    try:
        return float(body.get("retry_after", 1.0))
    except (TypeError, ValueError):
        return 1.0
