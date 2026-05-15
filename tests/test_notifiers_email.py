"""Phase 5 RED skeleton for NOTIF-05 (see 05-01-PLAN.md).

All tests in this file FAIL today (ImportError at collection) until Plan
05-04 ships notifiers/shopbot_notifier_email.py.
"""
from datetime import datetime, timezone

import pytest

# RED: notifiers.shopbot_notifier_email does not exist yet (Plan 05-04 target).
from notifiers.shopbot_notifier_email import EmailNotifier  # type: ignore[import-not-found]
from notifier_base import NotificationEvent


def _makeEvent():
    return NotificationEvent(
        item_name="Widget",
        url="https://example.com/widget",
        platform="amazon",
        timestamp=datetime.now(timezone.utc),
        action="detected",
    )


class _FakeSmtp:
    """Recording context-manager double for smtplib.SMTP / SMTP_SSL."""
    instances: list = []

    def __init__(self, host, port, timeout=15):
        self.host = host
        self.port = port
        self.calls: list = []
        _FakeSmtp.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def ehlo(self):
        self.calls.append("ehlo")

    def starttls(self):
        self.calls.append("starttls")

    def login(self, u, p):
        self.calls.append(("login", u))

    def send_message(self, msg):
        self.calls.append(("send_message", dict(msg)))


def _resetFake():
    _FakeSmtp.instances = []


def _emailConfig(port=587):
    from config_schema import EmailNotifierConfig
    return EmailNotifierConfig(
        enabled=True,
        from_addr="from@example.com",
        to_addr="to@example.com",
        smtp_host="smtp.example.com",
        smtp_port=port,
        smtp_user="user@example.com",
    )


def test_emailNotifierImportable():
    assert EmailNotifier is not None


@pytest.mark.asyncio
async def test_starttlsOn587(monkeypatch):
    _resetFake()
    monkeypatch.setenv("SHOPBOT_SMTP_PASSWORD", "pw")
    monkeypatch.setattr("notifiers.shopbot_notifier_email.smtplib.SMTP", _FakeSmtp)
    notifier = EmailNotifier(_emailConfig(port=587))
    await notifier.send(_makeEvent())
    calls = _FakeSmtp.instances[-1].calls
    actions = [c if isinstance(c, str) else c[0] for c in calls]
    assert "starttls" in actions
    assert any(a == "login" for a in actions)
    assert any(a == "send_message" for a in actions)


@pytest.mark.asyncio
async def test_smtpsslOn465(monkeypatch):
    _resetFake()
    monkeypatch.setenv("SHOPBOT_SMTP_PASSWORD", "pw")
    monkeypatch.setattr("notifiers.shopbot_notifier_email.smtplib.SMTP_SSL", _FakeSmtp)
    notifier = EmailNotifier(_emailConfig(port=465))
    await notifier.send(_makeEvent())
    calls = _FakeSmtp.instances[-1].calls
    actions = [c if isinstance(c, str) else c[0] for c in calls]
    assert "starttls" not in actions
    assert any(a == "login" for a in actions)


def test_passwordFromEnv(monkeypatch):
    monkeypatch.setenv("SHOPBOT_SMTP_PASSWORD", "secret")
    notifier = EmailNotifier(_emailConfig())
    assert notifier.enabled is True
    monkeypatch.delenv("SHOPBOT_SMTP_PASSWORD", raising=False)
    notifier2 = EmailNotifier(_emailConfig())
    assert notifier2.enabled is False


@pytest.mark.asyncio
async def test_messageHeaders(monkeypatch):
    _resetFake()
    monkeypatch.setenv("SHOPBOT_SMTP_PASSWORD", "pw")
    monkeypatch.setattr("notifiers.shopbot_notifier_email.smtplib.SMTP", _FakeSmtp)
    notifier = EmailNotifier(_emailConfig())
    event = _makeEvent()
    await notifier.send(event)
    send_call = next(c for c in _FakeSmtp.instances[-1].calls
                     if not isinstance(c, str) and c[0] == "send_message")
    headers = send_call[1]
    assert "Subject" in headers
    assert event.platform in headers["Subject"]
    assert event.item_name in headers["Subject"]
    assert headers.get("From") == "from@example.com"
    assert headers.get("To") == "to@example.com"
