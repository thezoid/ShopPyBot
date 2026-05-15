"""Phase 5 RED skeleton for NOTIF-04 (see 05-01-PLAN.md).

All tests in this file FAIL today (ImportError at collection) until Plan
05-03 ships notifiers/shopbot_notifier_discord.py.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

# RED: notifiers.shopbot_notifier_discord does not exist yet (Plan 05-03 target).
from notifiers.shopbot_notifier_discord import DiscordNotifier  # type: ignore[import-not-found]
from notifier_base import NotificationEvent


def _makeResponse(status_code: int, retry_after: float | None = None):
    r = MagicMock()
    r.status_code = status_code
    r.headers = {"Retry-After": str(retry_after)} if retry_after is not None else {}
    r.json = lambda: ({"retry_after": retry_after} if retry_after is not None else {})
    r.raise_for_status = lambda: None if status_code < 400 else (_ for _ in ()).throw(
        Exception(f"HTTP {status_code}")
    )
    return r


def _makeEvent():
    return NotificationEvent(
        item_name="Widget",
        url="https://example.com/widget",
        platform="amazon",
        timestamp=datetime.now(timezone.utc),
        action="detected",
    )


def test_discordNotifierImportable():
    assert DiscordNotifier is not None


def test_urlReadAtInit(monkeypatch):
    from config_schema import DiscordNotifierConfig
    monkeypatch.setenv("SHOPBOT_DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1/x")
    notifier = DiscordNotifier(DiscordNotifierConfig(enabled=True))
    monkeypatch.delenv("SHOPBOT_DISCORD_WEBHOOK_URL")
    assert getattr(notifier, "webhook_url", None) == "https://discord.com/api/webhooks/1/x"


@pytest.mark.asyncio
async def test_embedShape(monkeypatch):
    from config_schema import DiscordNotifierConfig
    monkeypatch.setenv("SHOPBOT_DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1/x")
    posted: list = []

    def fakePost(url, json, timeout):
        posted.append((url, json))
        return _makeResponse(204)

    monkeypatch.setattr("notifiers.shopbot_notifier_discord.requests.post", fakePost)
    notifier = DiscordNotifier(DiscordNotifierConfig(enabled=True))
    await notifier.send(_makeEvent())
    embed = posted[0][1]["embeds"][0]
    for key in ("title", "description", "url", "color", "timestamp", "fields"):
        assert key in embed


@pytest.mark.asyncio
async def test_429RetryOnce(monkeypatch):
    from config_schema import DiscordNotifierConfig
    monkeypatch.setenv("SHOPBOT_DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1/x")
    calls: list = []
    responses = [_makeResponse(429, retry_after=0.01), _makeResponse(204)]

    def fakePost(url, json, timeout):
        calls.append(url)
        return responses.pop(0)

    monkeypatch.setattr("notifiers.shopbot_notifier_discord.requests.post", fakePost)
    monkeypatch.setattr("notifiers.shopbot_notifier_discord.time.sleep", lambda s: None)
    notifier = DiscordNotifier(DiscordNotifierConfig(enabled=True))
    await notifier.send(_makeEvent())
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_429GiveUpAfterOne(monkeypatch):
    from config_schema import DiscordNotifierConfig
    monkeypatch.setenv("SHOPBOT_DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1/x")
    calls: list = []

    def fakePost(url, json, timeout):
        calls.append(url)
        return _makeResponse(429, retry_after=0.01)

    monkeypatch.setattr("notifiers.shopbot_notifier_discord.requests.post", fakePost)
    monkeypatch.setattr("notifiers.shopbot_notifier_discord.time.sleep", lambda s: None)
    notifier = DiscordNotifier(DiscordNotifierConfig(enabled=True))
    await notifier.send(_makeEvent())
    assert len(calls) == 2
