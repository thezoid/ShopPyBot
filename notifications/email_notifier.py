"""EmailNotifier: sends SMTP alerts via STARTTLS or SMTP_SSL (NOTIF-05).

Security contract (T-05-07):
  - SMTP_PASSWORD is read from env at send time; never stored as an attribute,
    never logged, never included in exception messages emitted by this module.
  - SMTP exceptions propagate to the dispatcher boundary so it can isolate
    per-channel (do NOT catch/swallow them here).
  - No bare except; specific SMTP exception types are documented in RESEARCH
    Pattern 5.

Transport:
  - Blocking smtplib calls run via loop.run_in_executor so they never stall
    the async event loop (Pitfall 4 from RESEARCH).
  - STARTTLS path: smtplib.SMTP + starttls() + login() + send_message().
  - SSL path: smtplib.SMTP_SSL + login() + send_message() (no starttls call).
"""

import asyncio
import smtplib
from email.message import EmailMessage

from core.config_schema import EmailConfig
from core.credentials import get_store
from notifications.base import Notifier, NotificationEvent, cents_to_display


def _build_email_body(event: NotificationEvent) -> str:
    """Construct the plain-text email body from a NotificationEvent."""
    lines = [
        f"Item: {event.item_name}",
        f"URL: {event.item_url}",
        f"Platform: {event.platform}",
        f"Action: {event.action}",
    ]
    if event.action == "price_drop":
        lines.append(f"Current Price: {cents_to_display(event.price_cents)}")
        lines.append(f"Target Price: {cents_to_display(event.target_price_cents)}")
        if event.pct_from_target is not None:
            lines.append(f"Below Target: {event.pct_from_target}%")
    return "\n".join(lines) + "\n"


def _send_email_blocking(
    host: str,
    port: int,
    username: str,
    sender: str,
    recipients: list[str],
    password: str,
    subject: str,
    body: str,
    use_ssl: bool,
) -> None:
    """Send email synchronously. Caller must run this via run_in_executor."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.set_content(body)

    if use_ssl:
        with smtplib.SMTP_SSL(host, port, timeout=10) as smtp:
            smtp.login(username, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.starttls()
            smtp.login(username, password)
            smtp.send_message(msg)
    # Exceptions intentionally propagate:
    # smtplib.SMTPAuthenticationError, smtplib.SMTPConnectError,
    # smtplib.SMTPRecipientsRefused, smtplib.SMTPException, OSError


class EmailNotifier(Notifier):
    """Sends an email alert for each NotificationEvent via SMTP."""

    def __init__(self, config: EmailConfig) -> None:
        self._config = config
        self._username = config.smtp_username or config.sender

    async def send(self, event: NotificationEvent) -> None:
        """Build subject/body and run blocking SMTP send in executor."""
        cfg = self._config
        password = get_store().get("SMTP_PASSWORD") or ""
        subject = f"{event.item_name} {event.action}"
        body = _build_email_body(event)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            _send_email_blocking,
            cfg.smtp_host,
            cfg.smtp_port,
            self._username,
            cfg.sender,
            cfg.recipients,
            password,
            subject,
            body,
            cfg.smtp_ssl,
        )
