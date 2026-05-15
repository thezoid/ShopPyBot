"""Phase 5 GREEN tests for NOTIF-06 (Plan 05-05).

Two-lock opt-in (CONTEXT D-04): BOTH notifications.sms.enabled=True in config
AND env SHOPBOT_ENABLE_SMS=='true' are required. Twilio credentials come
from env vars only (SEC-01). In test_mode, SMS is forcibly disabled.
"""
import ast
import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest

from notifiers.shopbot_notifier_sms import SmsNotifier
from notifier_base import NotificationEvent


_SMS_MODULE_PATH = Path(__file__).resolve().parent.parent / "notifiers" / "shopbot_notifier_sms.py"


class _AppCfgStub:
    class _Debug:
        test_mode = False
    debug = _Debug()


def _makeAppCfg(test_mode: bool = False):
    cfg = _AppCfgStub()
    cfg.debug = _AppCfgStub._Debug()
    cfg.debug.test_mode = test_mode
    return cfg


def _setTwilioEnv(monkeypatch, enable: bool = True):
    monkeypatch.setenv("SHOPBOT_TWILIO_ACCOUNT_SID", "ACtest")
    monkeypatch.setenv("SHOPBOT_TWILIO_AUTH_TOKEN", "tok")
    monkeypatch.setenv("SHOPBOT_TWILIO_FROM", "+15550001111")
    if enable:
        monkeypatch.setenv("SHOPBOT_ENABLE_SMS", "true")
    else:
        monkeypatch.delenv("SHOPBOT_ENABLE_SMS", raising=False)


def _clearTwilioEnv(monkeypatch):
    for k in (
        "SHOPBOT_TWILIO_ACCOUNT_SID",
        "SHOPBOT_TWILIO_AUTH_TOKEN",
        "SHOPBOT_TWILIO_FROM",
        "SHOPBOT_ENABLE_SMS",
    ):
        monkeypatch.delenv(k, raising=False)


def _smsCfg(enabled=True, to="+15551234567"):
    from config_schema import SmsNotifierConfig
    return SmsNotifierConfig(enabled=enabled, to=to)


def _makeEvent():
    return NotificationEvent(
        item_name="Widget",
        url="https://example.test/widget",
        platform="Amazon",
        timestamp=datetime(2026, 5, 15, tzinfo=timezone.utc),
        action="detected",
    )


class _FakeMessages:
    def __init__(self):
        self.calls: list[dict] = []
        self.raise_exc: Exception | None = None

    def create(self, **kw):
        self.calls.append(kw)
        if self.raise_exc is not None:
            raise self.raise_exc


class _FakeTwilioClient:
    instances: list["_FakeTwilioClient"] = []

    def __init__(self, sid, token):
        self.sid = sid
        self.token = token
        self.messages = _FakeMessages()
        _FakeTwilioClient.instances.append(self)


@pytest.fixture(autouse=True)
def _reset_fake_clients():
    _FakeTwilioClient.instances.clear()
    yield


@pytest.fixture
def patchedClient(monkeypatch):
    monkeypatch.setattr(
        "notifiers.shopbot_notifier_sms.Client", _FakeTwilioClient
    )
    return _FakeTwilioClient


def test_smsNotifierImportable():
    assert SmsNotifier is not None


def test_disabledIfBothOff(monkeypatch, caplog):
    _clearTwilioEnv(monkeypatch)
    notifier = SmsNotifier(_smsCfg(enabled=False), app_config=_makeAppCfg())
    assert notifier.enabled is False


def test_disabledIfConfigOff(monkeypatch):
    _setTwilioEnv(monkeypatch, enable=True)
    notifier = SmsNotifier(_smsCfg(enabled=False), app_config=_makeAppCfg())
    assert notifier.enabled is False


def test_disabledIfEnvOff(monkeypatch, capsys):
    _setTwilioEnv(monkeypatch, enable=False)
    notifier = SmsNotifier(_smsCfg(enabled=True), app_config=_makeAppCfg())
    assert notifier.enabled is False
    out = capsys.readouterr().out
    assert "SHOPBOT_ENABLE_SMS" in out
    assert "WARNING" in out


def test_disabledIfEnvOffMessageDistinguishes(monkeypatch, capsys):
    _setTwilioEnv(monkeypatch, enable=True)
    notifier = SmsNotifier(_smsCfg(enabled=False), app_config=_makeAppCfg())
    assert notifier.enabled is False
    out = capsys.readouterr().out
    assert "notifications.sms.enabled is false" in out


def test_enabledWhenBothLocksPass(monkeypatch, patchedClient):
    _setTwilioEnv(monkeypatch, enable=True)
    notifier = SmsNotifier(_smsCfg(enabled=True), app_config=_makeAppCfg())
    assert notifier.enabled is True
    assert isinstance(notifier._client, _FakeTwilioClient)
    assert notifier._client.sid == "ACtest"
    assert notifier._client.token == "tok"


def test_testModeDisablesSms(monkeypatch, patchedClient, capsys):
    _setTwilioEnv(monkeypatch, enable=True)
    notifier = SmsNotifier(_smsCfg(enabled=True), app_config=_makeAppCfg(test_mode=True))
    assert notifier.enabled is False
    out = capsys.readouterr().out
    assert "test_mode" in out


def test_missingTwilioCredsDisables(monkeypatch, patchedClient, capsys):
    _setTwilioEnv(monkeypatch, enable=True)
    monkeypatch.delenv("SHOPBOT_TWILIO_ACCOUNT_SID", raising=False)
    notifier = SmsNotifier(_smsCfg(enabled=True), app_config=_makeAppCfg())
    assert notifier.enabled is False
    out = capsys.readouterr().out
    assert "SHOPBOT_TWILIO_ACCOUNT_SID" in out


def test_sendUsesFromUnderscoreKwarg(monkeypatch, patchedClient):
    _setTwilioEnv(monkeypatch, enable=True)
    notifier = SmsNotifier(_smsCfg(enabled=True, to="+15551234567"), app_config=_makeAppCfg())
    asyncio.run(notifier.send(_makeEvent()))
    assert len(notifier._client.messages.calls) == 1
    call = notifier._client.messages.calls[0]
    assert call["from_"] == "+15550001111"
    assert call["to"] == "+15551234567"
    assert "body" in call


def test_twilioFromUnderscore():
    """AST check: messages.create uses from_= and never from= or from_addr=."""
    tree = ast.parse(_SMS_MODULE_PATH.read_text())
    found = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # Find Call attribute chain ending in .create
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "create":
            kwargs = [kw.arg for kw in node.keywords if kw.arg]
            assert "from_" in kwargs, "messages.create must use from_= kwarg"
            assert "from" not in kwargs
            assert "from_addr" not in kwargs
            found = True
    assert found, "no messages.create() call found"


def test_credsReadOnce(monkeypatch, patchedClient):
    _setTwilioEnv(monkeypatch, enable=True)
    first = SmsNotifier(_smsCfg(enabled=True), app_config=_makeAppCfg())
    assert first._account_sid == "ACtest"
    # Now clear all envs and build a second instance
    _clearTwilioEnv(monkeypatch)
    second = SmsNotifier(_smsCfg(enabled=True), app_config=_makeAppCfg())
    # First instance unchanged (snapshot at __init__)
    assert first._account_sid == "ACtest"
    assert first._auth_token == "tok"
    assert first._from == "+15550001111"
    # Second instance is disabled (no env)
    assert second.enabled is False


def test_envReadOnlyInInit():
    """AST grep: os.environ access only in __init__, never in send/_send_sms."""
    tree = ast.parse(_SMS_MODULE_PATH.read_text())
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) and not isinstance(node, ast.AsyncFunctionDef):
            continue
        if node.name in ("__init__",):
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Attribute) and sub.attr == "environ":
                pytest.fail(f"os.environ accessed in {node.name}")


def test_credsNotLogged():
    """AST grep: writeLog calls never reference self._account_sid/_auth_token/_from."""
    tree = ast.parse(_SMS_MODULE_PATH.read_text())
    forbidden = {"_account_sid", "_auth_token", "_from"}
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
        for arg in ast.walk(node):
            if isinstance(arg, ast.Attribute) and arg.attr in forbidden:
                pytest.fail(f"writeLog references self.{arg.attr}")


def test_twilioRestExceptionSanitized(monkeypatch, patchedClient):
    from twilio.base.exceptions import TwilioRestException
    _setTwilioEnv(monkeypatch, enable=True)
    notifier = SmsNotifier(_smsCfg(enabled=True), app_config=_makeAppCfg())
    notifier._client.messages.raise_exc = TwilioRestException(
        status=401, uri="x", msg="secret in here", code=20003
    )
    with pytest.raises(RuntimeError) as exc_info:
        asyncio.run(notifier.send(_makeEvent()))
    message = str(exc_info.value)
    assert "20003" in message
    assert "401" in message
    assert "secret in here" not in message
    assert "tok" not in message


def test_credsAbsentFromSchema():
    from config_schema import SmsNotifierConfig
    fields = SmsNotifierConfig.model_fields
    assert "account_sid" not in fields
    assert "auth_token" not in fields
    assert "from_number" not in fields
