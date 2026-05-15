"""Phase 5 RED skeleton for NOTIF-06 (see 05-01-PLAN.md).

All tests in this file FAIL today (ImportError at collection) until Plan
05-05 ships notifiers/shopbot_notifier_sms.py.
"""
import ast
from datetime import datetime, timezone
from pathlib import Path

import pytest

# RED: notifiers.shopbot_notifier_sms does not exist yet (Plan 05-05 target).
from notifiers.shopbot_notifier_sms import SmsNotifier  # type: ignore[import-not-found]
from notifier_base import NotificationEvent


class _AppCfgStub:
    class _Debug:
        test_mode = False
    debug = _Debug()


def _setTwilioEnv(monkeypatch, enable: bool = True):
    monkeypatch.setenv("SHOPBOT_TWILIO_ACCOUNT_SID", "ACtest")
    monkeypatch.setenv("SHOPBOT_TWILIO_AUTH_TOKEN", "tok")
    monkeypatch.setenv("SHOPBOT_TWILIO_FROM", "+15550001111")
    if enable:
        monkeypatch.setenv("SHOPBOT_ENABLE_SMS", "true")
    else:
        monkeypatch.delenv("SHOPBOT_ENABLE_SMS", raising=False)


def _smsCfg(enabled=True, to="+15551234567"):
    from config_schema import SmsNotifierConfig
    return SmsNotifierConfig(enabled=enabled, to=to)


def test_smsNotifierImportable():
    assert SmsNotifier is not None


def test_disabledIfConfigOff(monkeypatch):
    _setTwilioEnv(monkeypatch, enable=True)
    notifier = SmsNotifier(_smsCfg(enabled=False), app_config=_AppCfgStub())
    assert notifier.enabled is False


def test_disabledIfEnvOff(monkeypatch):
    _setTwilioEnv(monkeypatch, enable=False)
    notifier = SmsNotifier(_smsCfg(enabled=True), app_config=_AppCfgStub())
    assert notifier.enabled is False


def test_enabledWhenBothLocksPass(monkeypatch):
    _setTwilioEnv(monkeypatch, enable=True)
    notifier = SmsNotifier(_smsCfg(enabled=True), app_config=_AppCfgStub())
    assert notifier.enabled is True


def test_testModeDisablesSms(monkeypatch):
    _setTwilioEnv(monkeypatch, enable=True)
    cfg = _AppCfgStub()
    cfg.debug.test_mode = True
    notifier = SmsNotifier(_smsCfg(enabled=True), app_config=cfg)
    assert notifier.enabled is False


def test_twilioFromUnderscore():
    src = Path("notifiers/shopbot_notifier_sms.py").read_text()
    tree = ast.parse(src)
    keywords: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg:
                    keywords.append(kw.arg)
    assert "from_" in keywords, "Twilio call must use from_= (trailing underscore)"
    assert "from" not in keywords  # `from` is a reserved word; defensive check
