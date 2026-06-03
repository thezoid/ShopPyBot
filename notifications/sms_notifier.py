"""SmsNotifier: sends SMS alerts via Twilio Messages.json REST API (NOTIF-06).

Security contract (T-05-08):
  - TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM are read from env at
    send time; never stored as attributes, never logged.
  - The Twilio endpoint URL embeds the Account SID — it must NEVER be logged.
    On failure, log only the HTTP status code and the scrubbed label
    "twilio/Messages.json" (never resp.request.url, str(exc), the SID, or
    the token).
  - requests.HTTPError propagates to the dispatcher boundary for per-channel
    isolation.

Transport:
  - Blocking requests.post runs via loop.run_in_executor so it never stalls
    the async event loop.
  - Success: HTTP 201 Created.
  - 4xx/5xx: resp.raise_for_status() raises requests.HTTPError.
"""

import asyncio
import os

import requests
from requests.auth import HTTPBasicAuth

from core.config_schema import SmsConfig
from notifications.base import Notifier, NotificationEvent


def _send_sms_blocking(
    account_sid: str,
    auth_token: str,
    from_number: str,
    to_number: str,
    body: str,
) -> None:
    """POST to Twilio Messages.json synchronously. Caller uses run_in_executor."""
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    resp = requests.post(
        url,
        auth=HTTPBasicAuth(account_sid, auth_token),
        data={"To": to_number, "From": from_number, "Body": body},
        timeout=10,
    )
    resp.raise_for_status()
    # 201 Created = success; 4xx/5xx raises requests.HTTPError
    # Caller must NOT log resp.request.url -- it contains the account SID


class SmsNotifier(Notifier):
    """Sends an SMS alert for each NotificationEvent via Twilio REST."""

    def __init__(self, config: SmsConfig) -> None:
        self._config = config

    async def send(self, event: NotificationEvent) -> None:
        """Build SMS body and run blocking Twilio POST in executor."""
        account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        from_number = os.environ.get("TWILIO_FROM", "")
        to_number = self._config.to_number

        body = (
            f"{event.item_name} {event.action}: "
            f"{event.item_url} ({event.platform})"
        )

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            _send_sms_blocking,
            account_sid,
            auth_token,
            from_number,
            to_number,
            body,
        )
