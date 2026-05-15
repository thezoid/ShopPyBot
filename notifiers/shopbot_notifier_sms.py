"""SMS/Twilio notifier (NOTIF-06).

Two-lock opt-in (CONTEXT D-04): BOTH notifications.sms.enabled=True in config
AND env SHOPBOT_ENABLE_SMS=='true' are required. Either alone keeps SMS
disabled. Twilio credentials come from env vars only (SEC-01). In test_mode,
SMS is forcibly disabled to prevent accidental charges during test runs.

All env vars and the Twilio Client are constructed ONCE at __init__. Reading
env vars or rebuilding the client inside send() is FORBIDDEN.
"""
import asyncio
import os

from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from logger import writeLog
from notifier_base import Notifier, NotificationEvent


class SmsNotifier(Notifier):
    name = "sms"

    def __init__(self, sub_config=None, app_config=None) -> None:
        envEnable = os.environ.get("SHOPBOT_ENABLE_SMS", "").strip().lower() == "true"
        self._account_sid = os.environ.get("SHOPBOT_TWILIO_ACCOUNT_SID", "")
        self._auth_token = os.environ.get("SHOPBOT_TWILIO_AUTH_TOKEN", "")
        self._from = os.environ.get("SHOPBOT_TWILIO_FROM", "")

        configOn = bool(sub_config and getattr(sub_config, "enabled", False))

        if not configOn and not envEnable:
            writeLog(
                "SMS notifier disabled: both notifications.sms.enabled and "
                "SHOPBOT_ENABLE_SMS are off.",
                "INFO",
            )
            self.enabled = False
            return
        if not configOn:
            writeLog(
                "SMS notifier disabled: SHOPBOT_ENABLE_SMS=true but "
                "notifications.sms.enabled is false in config.",
                "WARNING",
            )
            self.enabled = False
            return
        if not envEnable:
            writeLog(
                "SMS notifier disabled: notifications.sms.enabled=true but "
                "SHOPBOT_ENABLE_SMS env var is not set to 'true'.",
                "WARNING",
            )
            self.enabled = False
            return

        if getattr(getattr(app_config, "debug", None), "test_mode", False):
            writeLog("test_mode: SMS notifier disabled.", "INFO")
            self.enabled = False
            return

        missing = _missing_twilio_creds(
            self._account_sid,
            self._auth_token,
            self._from,
            getattr(sub_config, "to", None),
        )
        if missing:
            writeLog(
                f"SMS notifier disabled: missing Twilio setting(s): {missing}.",
                "WARNING",
            )
            self.enabled = False
            return

        self._to = sub_config.to
        self._client = Client(self._account_sid, self._auth_token)
        self.enabled = True

    async def send(self, event: NotificationEvent) -> None:
        await asyncio.to_thread(self._send_sms, event)

    def _send_sms(self, event: NotificationEvent) -> None:
        body = f"[ShopPyBot] {event.item_name} {event.action}: {event.url}"
        try:
            self._client.messages.create(
                to=self._to,
                from_=self._from,
                body=body,
            )
        except TwilioRestException as e:
            raise RuntimeError(
                f"Twilio send failed (code={e.code}, status={e.status})"
            ) from None


def _missing_twilio_creds(account_sid: str, auth_token: str, from_num: str, to_num) -> str:
    missing = []
    if not account_sid:
        missing.append("SHOPBOT_TWILIO_ACCOUNT_SID env var")
    if not auth_token:
        missing.append("SHOPBOT_TWILIO_AUTH_TOKEN env var")
    if not from_num:
        missing.append("SHOPBOT_TWILIO_FROM env var")
    if not to_num:
        missing.append("notifications.sms.to config value")
    return ", ".join(missing)
