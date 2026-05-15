"""GREEN tests for EmailNotifier (NOTIF-05, Plan 05-04).

Monkeypatches smtplib.SMTP / smtplib.SMTP_SSL with recording context-manager
fakes; verifies STARTTLS-587 sequence, SMTP_SSL-465 path, MIME headers,
env-at-init password capture, and that the password never reaches writeLog.
"""
import ast
import inspect
from datetime import datetime, timezone

import pytest

from notifiers.shopbot_notifier_email import EmailNotifier
from notifier_base import Notifier, NotificationEvent
from config_schema import EmailNotifierConfig


def _makeEvent():
    return NotificationEvent(
        item_name="Widget",
        url="https://example.com/widget",
        platform="amazon",
        timestamp=datetime.now(timezone.utc),
        action="detected",
    )


class _FakeSmtp:
    """Recording context-manager double for smtplib.SMTP."""
    instances: list = []

    def __init__(self, host, port, timeout=15):
        self.host = host
        self.port = port
        self.timeout = timeout
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
        self.calls.append(("login", u, p))

    def send_message(self, msg):
        # Capture headers as dict for assertion without leaking refs.
        self.calls.append(("send_message", {k: v for k, v in msg.items()}, msg))


class _FakeSmtpSsl(_FakeSmtp):
    """Recording context-manager double for smtplib.SMTP_SSL (no starttls)."""
    instances: list = []

    def __init__(self, host, port, timeout=15):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.calls: list = []
        _FakeSmtpSsl.instances.append(self)

    # Intentionally no starttls method to mirror real SMTP_SSL surface.
    def starttls(self):  # pragma: no cover - presence would be a bug
        raise AssertionError("SMTP_SSL should not call starttls()")


def _resetFakes():
    _FakeSmtp.instances = []
    _FakeSmtpSsl.instances = []


def _emailConfig(port=587, **overrides):
    fields = dict(
        enabled=True,
        from_addr="from@example.com",
        to_addr="to@example.com",
        smtp_host="smtp.example.com",
        smtp_port=port,
        smtp_user="user@example.com",
    )
    fields.update(overrides)
    return EmailNotifierConfig(**fields)


def test_emailNotifierImportable():
    assert EmailNotifier is not None
    assert issubclass(EmailNotifier, Notifier)


def test_sendIsCoroutine():
    assert inspect.iscoroutinefunction(EmailNotifier.send)


@pytest.mark.asyncio
async def test_starttlsOn587(monkeypatch):
    _resetFakes()
    monkeypatch.setenv("SHOPBOT_SMTP_PASSWORD", "pw")
    monkeypatch.setattr(
        "notifiers.shopbot_notifier_email.smtplib.SMTP", _FakeSmtp
    )
    notifier = EmailNotifier(sub_config=_emailConfig(port=587))
    assert notifier.enabled is True
    await notifier.send(_makeEvent())
    calls = _FakeSmtp.instances[-1].calls
    actions = [c if isinstance(c, str) else c[0] for c in calls]
    # Order: ehlo -> starttls -> ehlo -> login -> send_message.
    assert actions == ["ehlo", "starttls", "ehlo", "login", "send_message"]


@pytest.mark.asyncio
async def test_smtpsslOn465(monkeypatch):
    _resetFakes()
    monkeypatch.setenv("SHOPBOT_SMTP_PASSWORD", "pw")
    monkeypatch.setattr(
        "notifiers.shopbot_notifier_email.smtplib.SMTP_SSL", _FakeSmtpSsl
    )
    notifier = EmailNotifier(sub_config=_emailConfig(port=465))
    assert notifier.enabled is True
    await notifier.send(_makeEvent())
    calls = _FakeSmtpSsl.instances[-1].calls
    actions = [c if isinstance(c, str) else c[0] for c in calls]
    assert "starttls" not in actions
    assert actions == ["login", "send_message"]


def test_passwordFromEnvAtInit(monkeypatch):
    monkeypatch.setenv("SHOPBOT_SMTP_PASSWORD", "secret")
    notifier = EmailNotifier(sub_config=_emailConfig())
    assert notifier.enabled is True
    assert notifier._password == "secret"
    # Changing env after init does not change instance password.
    monkeypatch.setenv("SHOPBOT_SMTP_PASSWORD", "different")
    assert notifier._password == "secret"


def test_passwordEnvMissingDisables(monkeypatch, caplog):
    monkeypatch.delenv("SHOPBOT_SMTP_PASSWORD", raising=False)
    notifier = EmailNotifier(sub_config=_emailConfig())
    assert notifier.enabled is False


@pytest.mark.asyncio
async def test_messageHeaders(monkeypatch):
    _resetFakes()
    monkeypatch.setenv("SHOPBOT_SMTP_PASSWORD", "pw")
    monkeypatch.setattr(
        "notifiers.shopbot_notifier_email.smtplib.SMTP", _FakeSmtp
    )
    notifier = EmailNotifier(sub_config=_emailConfig())
    event = _makeEvent()
    await notifier.send(event)
    send_call = next(
        c for c in _FakeSmtp.instances[-1].calls
        if not isinstance(c, str) and c[0] == "send_message"
    )
    headers = send_call[1]
    msg = send_call[2]
    assert headers["Subject"].startswith("[ShopPyBot]")
    assert event.platform in headers["Subject"]
    assert event.item_name in headers["Subject"]
    assert headers["From"] == "from@example.com"
    assert headers["To"] == "to@example.com"
    # Body content checks.
    body = msg.get_payload(0).get_payload()
    assert event.item_name in body
    assert event.url in body
    assert event.action in body
    assert event.timestamp.isoformat() in body


def test_passwordNotLogged():
    """AST grep: no writeLog Call argument references self._password."""
    src = inspect.getsource(
        __import__("notifiers.shopbot_notifier_email", fromlist=["x"])
    )
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_writelog = (
            (isinstance(func, ast.Name) and func.id == "writeLog")
            or (isinstance(func, ast.Attribute) and func.attr == "writeLog")
        )
        if not is_writelog:
            continue
        for arg in node.args:
            for sub in ast.walk(arg):
                if isinstance(sub, ast.Attribute) and sub.attr == "_password":
                    raise AssertionError(
                        f"writeLog Call argument references self._password "
                        f"at line {node.lineno}"
                    )


def test_disabledIfConfigOff(monkeypatch, caplog):
    monkeypatch.setenv("SHOPBOT_SMTP_PASSWORD", "pw")
    cfg = _emailConfig()
    cfg = EmailNotifierConfig(
        enabled=False,
        from_addr=cfg.from_addr,
        to_addr=cfg.to_addr,
        smtp_host=cfg.smtp_host,
        smtp_port=cfg.smtp_port,
        smtp_user=cfg.smtp_user,
    )
    notifier = EmailNotifier(sub_config=cfg)
    assert notifier.enabled is False


def test_disabledIfHostMissing(monkeypatch):
    monkeypatch.setenv("SHOPBOT_SMTP_PASSWORD", "pw")
    cfg = _emailConfig(smtp_host=None)
    notifier = EmailNotifier(sub_config=cfg)
    assert notifier.enabled is False


def test_smtpPasswordAbsentFromSchema():
    assert "smtp_password" not in EmailNotifierConfig.model_fields


def test_envReadExactlyOnceInSource():
    """Regression: env var must be read once at __init__, never in send()."""
    import notifiers.shopbot_notifier_email as mod
    src = inspect.getsource(mod)
    assert src.count("os.environ") == 1
