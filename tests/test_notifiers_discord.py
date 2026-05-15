"""GREEN tests for NOTIF-04 (Plan 05-03).

Covers:
- DiscordNotifier import + Notifier subclass
- SHOPBOT_DISCORD_WEBHOOK_URL read once at __init__ (env change after init ignored)
- Embed payload shape (title/description/url/color/timestamp/fields)
- 429 retry-once-then-success
- 429 retry-once-then-give-up (no raise; WARNING logged)
- Disabled when env missing (with WARNING)
- Disabled when sub_config.enabled=False (quiet)
- Webhook URL NEVER referenced in writeLog call sites (AST grep)
- Purchased action uses purchased color
"""
import ast
from datetime import datetime, timezone
from pathlib import Path

import pytest

from config_schema import DiscordNotifierConfig
from notifier_base import NotificationEvent, Notifier
from notifiers.shopbot_notifier_discord import DiscordNotifier


_WEBHOOK = "https://discord.com/api/webhooks/1/test"


class FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(self, status_code: int, headers: dict | None = None,
                 json_body: dict | None = None) -> None:
        self.status_code = status_code
        self.headers = headers or {}
        self._json_body = json_body or {}

    def json(self) -> dict:
        return self._json_body

    def raise_for_status(self) -> None:
        if 400 <= self.status_code < 600:
            import requests
            raise requests.HTTPError(f"HTTP {self.status_code}")


def _makePostRecorder(responses: list[FakeResponse]):
    """Build a fake requests.post that returns queued responses in order."""
    calls: list[dict] = []

    def fakePost(url, json, timeout):
        calls.append({"url": url, "json": json, "timeout": timeout})
        return responses.pop(0)

    return fakePost, calls


def _makeEvent(action: str = "detected") -> NotificationEvent:
    return NotificationEvent(
        item_name="Widget",
        url="https://example.com/widget",
        platform="amazon",
        timestamp=datetime.now(timezone.utc),
        action=action,
    )


def _enabledConfig() -> DiscordNotifierConfig:
    return DiscordNotifierConfig(enabled=True)


def _disabledConfig() -> DiscordNotifierConfig:
    return DiscordNotifierConfig(enabled=False)


def test_discordNotifierImportable():
    assert DiscordNotifier is not None
    assert issubclass(DiscordNotifier, Notifier)


def test_urlReadAtInit(monkeypatch):
    monkeypatch.setenv("SHOPBOT_DISCORD_WEBHOOK_URL", _WEBHOOK)
    notifier = DiscordNotifier(sub_config=_enabledConfig(), app_config=None)
    # Mutate env after __init__; webhook_url must be unchanged.
    monkeypatch.setenv("SHOPBOT_DISCORD_WEBHOOK_URL", "https://changed.example/x")
    assert notifier.webhook_url == _WEBHOOK
    assert notifier.enabled is True


async def test_embedShape(monkeypatch):
    monkeypatch.setenv("SHOPBOT_DISCORD_WEBHOOK_URL", _WEBHOOK)
    fakePost, calls = _makePostRecorder([FakeResponse(204)])
    monkeypatch.setattr(
        "notifiers.shopbot_notifier_discord.requests.post", fakePost
    )
    notifier = DiscordNotifier(sub_config=_enabledConfig(), app_config=None)
    await notifier.send(_makeEvent("detected"))

    assert len(calls) == 1
    embed = calls[0]["json"]["embeds"][0]
    for key in ("title", "description", "url", "color", "timestamp", "fields"):
        assert key in embed
    assert embed["color"] == 0x2ECC71
    assert embed["url"] == "https://example.com/widget"
    # Timestamp is an ISO 8601 string parseable back to a tz-aware UTC datetime.
    parsed = datetime.fromisoformat(embed["timestamp"])
    assert parsed.tzinfo is not None


async def test_purchasedColor(monkeypatch):
    monkeypatch.setenv("SHOPBOT_DISCORD_WEBHOOK_URL", _WEBHOOK)
    fakePost, calls = _makePostRecorder([FakeResponse(204)])
    monkeypatch.setattr(
        "notifiers.shopbot_notifier_discord.requests.post", fakePost
    )
    notifier = DiscordNotifier(sub_config=_enabledConfig(), app_config=None)
    await notifier.send(_makeEvent("purchased"))

    embed = calls[0]["json"]["embeds"][0]
    assert embed["color"] == 0x3498DB


async def test_429RetryOnce(monkeypatch):
    monkeypatch.setenv("SHOPBOT_DISCORD_WEBHOOK_URL", _WEBHOOK)
    sleeps: list[float] = []
    monkeypatch.setattr(
        "notifiers.shopbot_notifier_discord.time.sleep",
        lambda s: sleeps.append(s),
    )
    fakePost, calls = _makePostRecorder([
        FakeResponse(429, headers={"Retry-After": "0.01"}),
        FakeResponse(204),
    ])
    monkeypatch.setattr(
        "notifiers.shopbot_notifier_discord.requests.post", fakePost
    )
    notifier = DiscordNotifier(sub_config=_enabledConfig(), app_config=None)
    await notifier.send(_makeEvent())

    assert len(calls) == 2
    assert sleeps == [0.01]


async def test_429RetryAfterCapAt30(monkeypatch):
    monkeypatch.setenv("SHOPBOT_DISCORD_WEBHOOK_URL", _WEBHOOK)
    sleeps: list[float] = []
    monkeypatch.setattr(
        "notifiers.shopbot_notifier_discord.time.sleep",
        lambda s: sleeps.append(s),
    )
    fakePost, calls = _makePostRecorder([
        FakeResponse(429, headers={"Retry-After": "9999"}),
        FakeResponse(204),
    ])
    monkeypatch.setattr(
        "notifiers.shopbot_notifier_discord.requests.post", fakePost
    )
    notifier = DiscordNotifier(sub_config=_enabledConfig(), app_config=None)
    await notifier.send(_makeEvent())

    assert sleeps == [30.0]
    assert len(calls) == 2


async def test_429GiveUpAfterOne(monkeypatch):
    monkeypatch.setenv("SHOPBOT_DISCORD_WEBHOOK_URL", _WEBHOOK)
    monkeypatch.setattr(
        "notifiers.shopbot_notifier_discord.time.sleep", lambda s: None
    )
    logged: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "notifiers.shopbot_notifier_discord.writeLog",
        lambda msg, type: logged.append((msg, type)),
    )
    fakePost, calls = _makePostRecorder([
        FakeResponse(429, headers={"Retry-After": "0.01"}),
        FakeResponse(429, headers={"Retry-After": "0.01"}),
    ])
    monkeypatch.setattr(
        "notifiers.shopbot_notifier_discord.requests.post", fakePost
    )
    notifier = DiscordNotifier(sub_config=_enabledConfig(), app_config=None)
    # MUST NOT raise on second 429.
    await notifier.send(_makeEvent())

    assert len(calls) == 2
    assert any("giving up" in msg for msg, _ in logged)
    assert any(level == "WARNING" for _, level in logged)


async def test_500PropagatesAsException(monkeypatch):
    import requests as _requests

    monkeypatch.setenv("SHOPBOT_DISCORD_WEBHOOK_URL", _WEBHOOK)
    fakePost, _calls = _makePostRecorder([FakeResponse(500)])
    monkeypatch.setattr(
        "notifiers.shopbot_notifier_discord.requests.post", fakePost
    )
    notifier = DiscordNotifier(sub_config=_enabledConfig(), app_config=None)
    with pytest.raises(_requests.HTTPError):
        await notifier.send(_makeEvent())


def test_disabledIfEnvMissing(monkeypatch):
    monkeypatch.delenv("SHOPBOT_DISCORD_WEBHOOK_URL", raising=False)
    logged: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "notifiers.shopbot_notifier_discord.writeLog",
        lambda msg, type: logged.append((msg, type)),
    )
    notifier = DiscordNotifier(sub_config=_enabledConfig(), app_config=None)
    assert notifier.enabled is False
    assert any(
        level == "WARNING" and "SHOPBOT_DISCORD_WEBHOOK_URL" in msg
        for msg, level in logged
    )


def test_disabledIfConfigOff(monkeypatch):
    monkeypatch.setenv("SHOPBOT_DISCORD_WEBHOOK_URL", _WEBHOOK)
    logged: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "notifiers.shopbot_notifier_discord.writeLog",
        lambda msg, type: logged.append((msg, type)),
    )
    notifier = DiscordNotifier(sub_config=_disabledConfig(), app_config=None)
    assert notifier.enabled is False
    # Quiet opt-out: no warnings fire when user explicitly turned it off.
    assert logged == []


def test_webhookUrlNotLogged():
    """AST grep: no writeLog call references self.webhook_url or contains
    a discord.com/api/webhooks literal."""
    source = Path(
        "notifiers/shopbot_notifier_discord.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)

    def _refersToWebhookUrl(node: ast.AST) -> bool:
        for sub in ast.walk(node):
            if isinstance(sub, ast.Attribute) and sub.attr == "webhook_url":
                return True
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                if "discord.com/api/webhooks" in sub.value:
                    return True
        return False

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_writeLog = (
            (isinstance(func, ast.Name) and func.id == "writeLog")
            or (isinstance(func, ast.Attribute) and func.attr == "writeLog")
        )
        if not is_writeLog:
            continue
        for arg in node.args:
            assert not _refersToWebhookUrl(arg), (
                "writeLog argument references webhook_url; "
                "secret leak per T-05-03-WEBHOOK-LEAK"
            )


def test_envReadExactlyOnce():
    """rtk grep -c 'os.environ' must be 1 (single read site)."""
    source = Path(
        "notifiers/shopbot_notifier_discord.py"
    ).read_text(encoding="utf-8")
    occurrences = source.count("os.environ")
    assert occurrences == 1, (
        f"Expected exactly one os.environ reference, found {occurrences}"
    )
