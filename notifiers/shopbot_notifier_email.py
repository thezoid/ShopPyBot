"""Email/SMTP notifier (NOTIF-05).

Sends a MIME multipart message via stdlib smtplib. Defaults to port 587 +
STARTTLS (RFC 6409 modern submission). Port 465 selects implicit SMTPS via
SMTP_SSL. Password from SHOPBOT_SMTP_PASSWORD env var, never config.yml
(SEC-01). The password is read once at __init__ (CONTEXT pitfall #4) and
held on the instance; runtime env changes do not affect a live notifier.
"""
import asyncio
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from logger import writeLog
from notifier_base import Notifier, NotificationEvent

_SMTP_TIMEOUT_SECONDS = 15


class EmailNotifier(Notifier):
    name = "email"

    def __init__(self, *, sub_config=None, app_config=None) -> None:
        self._password = os.environ.get("SHOPBOT_SMTP_PASSWORD", "")
        wantedEnabled = bool(sub_config and getattr(sub_config, "enabled", False))
        if not wantedEnabled:
            self.enabled = False
            return
        missing = _validate(sub_config, self._password)
        if missing:
            writeLog(
                f"Email notifier: missing required setting(s): {missing}; disabling.",
                "WARNING",
            )
            self.enabled = False
            return
        self._host = sub_config.smtp_host
        self._port = sub_config.smtp_port
        self._user = sub_config.smtp_user
        self._from = sub_config.from_addr
        self._to = sub_config.to_addr
        self.enabled = True

    async def send(self, event: NotificationEvent) -> None:
        message = _build_message(event, self._from, self._to)
        await asyncio.to_thread(self._send_smtp, message)

    def _send_smtp(self, message) -> None:
        if self._port == 465:
            with smtplib.SMTP_SSL(
                self._host, self._port, timeout=_SMTP_TIMEOUT_SECONDS
            ) as s:
                s.login(self._user, self._password)
                s.send_message(message)
        else:
            with smtplib.SMTP(
                self._host, self._port, timeout=_SMTP_TIMEOUT_SECONDS
            ) as s:
                s.ehlo()
                s.starttls()
                s.ehlo()
                s.login(self._user, self._password)
                s.send_message(message)


def _validate(sub_config, password: str) -> str:
    missing = []
    if not sub_config.smtp_host:
        missing.append("smtp_host")
    if not sub_config.smtp_user:
        missing.append("smtp_user")
    if not sub_config.from_addr:
        missing.append("from_addr")
    if not sub_config.to_addr:
        missing.append("to_addr")
    if not password:
        missing.append("SHOPBOT_SMTP_PASSWORD env var")
    return ", ".join(missing)


def _build_message(event: NotificationEvent, from_addr: str, to_addr: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[ShopPyBot] {event.platform}: {event.item_name}"
    msg["From"] = from_addr
    msg["To"] = to_addr
    body = (
        f"Item: {event.item_name}\n"
        f"Platform: {event.platform}\n"
        f"Action: {event.action}\n"
        f"URL: {event.url}\n"
        f"Time: {event.timestamp.isoformat()}\n"
    )
    msg.attach(MIMEText(body, "plain"))
    return msg
