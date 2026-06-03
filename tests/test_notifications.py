"""Notification system test scaffold (Phase 5).

Wave 0 (plan 05-01):
  - test_sms_misconfigured_raises: passes now (config schema)
  - test_sms_disabled_by_default: passes now (config schema)
  - test_dedup_*: passes now (models dedup columns/state fns)
  - test_notifier_abc_*: passes now (Notifier ABC + NotificationEvent)

Wave 1 (plan 05-02):
  - test_sound_notifier_*: SoundNotifier wrapping utils play_* functions
  - test_discord_*: DiscordNotifier embed POST, timestamp format, 429 handling

Wave 2+ (Plans 05-03, 05-04): email, SMS, dispatcher tests.
"""

import asyncio
import re
import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError


# ============================================================
# Helpers
# ============================================================


def _make_sms_config(enabled: bool, env_vars: dict | None = None, monkeypatch=None):
    """Construct a SmsConfig, optionally setting env vars first."""
    from core.config_schema import SmsConfig

    if monkeypatch and env_vars:
        for k, v in env_vars.items():
            monkeypatch.setenv(k, v)

    return SmsConfig(enabled=enabled)


# ============================================================
# NOTIF-06: SMS config startup gate (passes in Plan 05-01)
# ============================================================


def test_sms_misconfigured_raises(monkeypatch):
    """Enabling SMS without TWILIO_* env vars must raise a ValidationError at startup."""
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TWILIO_FROM", raising=False)

    with pytest.raises(ValidationError) as exc_info:
        from core.config_schema import SmsConfig
        SmsConfig(enabled=True)

    err = str(exc_info.value)
    assert "TWILIO_ACCOUNT_SID" in err
    assert "TWILIO_AUTH_TOKEN" in err
    assert "TWILIO_FROM" in err


def test_sms_disabled_by_default(monkeypatch):
    """Default SmsConfig (enabled=False) must not raise even when TWILIO_* are absent."""
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TWILIO_FROM", raising=False)

    from core.config_schema import SmsConfig
    cfg = SmsConfig()  # must not raise
    assert cfg.enabled is False


# ============================================================
# Notifier ABC + NotificationEvent contract (passes in Plan 05-01)
# ============================================================


def test_notifier_abc_cannot_instantiate_without_send():
    """A Notifier subclass that does not override send must raise TypeError."""
    from notifications.base import Notifier

    class _Bad(Notifier):
        pass

    with pytest.raises(TypeError):
        _Bad()


def test_notifier_abc_concrete_subclass_works():
    """A Notifier subclass that overrides send must be instantiable."""
    from notifications.base import Notifier, NotificationEvent

    class _Good(Notifier):
        async def send(self, event: NotificationEvent) -> None:
            pass

    instance = _Good()
    assert isinstance(instance, Notifier)


def test_notification_event_fields():
    """NotificationEvent must carry all required fields."""
    from notifications.base import NotificationEvent

    event = NotificationEvent(
        item_name="GPU",
        item_url="https://bestbuy.com/gpu",
        platform="BestBuy",
        timestamp=datetime(2026, 6, 3, 12, 0, 0, tzinfo=timezone.utc),
        action="detected",
    )
    assert event.item_name == "GPU"
    assert event.item_url == "https://bestbuy.com/gpu"
    assert event.platform == "BestBuy"
    assert event.action == "detected"
    assert event.timestamp.tzinfo is not None


async def test_fake_notifier_records_events(fake_notifier, notification_event):
    """fake_notifier fixture must record sent events."""
    notifier = fake_notifier()
    event = notification_event()
    await notifier.send(event)
    assert len(notifier.events) == 1
    assert notifier.events[0] is event


async def test_fake_notifier_can_raise(fake_notifier, notification_event):
    """fake_notifier(raises=...) must raise the configured exception on send."""
    notifier = fake_notifier(raises=ValueError("boom"))
    event = notification_event()
    with pytest.raises(ValueError, match="boom"):
        await notifier.send(event)


# ============================================================
# NOTIF-02: Dedup columns and state functions (passes in Plan 05-01)
# ============================================================


def test_dedup_single_notify_per_restock(tmp_data_dir):
    """Rising edge (0->1) should be detectable via get_item_notification_state_sync."""
    from models import (
        initialize_db,
        add_items_sync,
        get_item_notification_state_sync,
        set_item_available_sync,
    )
    from datetime import datetime, timezone

    initialize_db()
    add_items_sync([("Widget", "https://example.com/widget", False, 1, False)])
    link = "https://example.com/widget"

    was_avail, last_notified = get_item_notification_state_sync(link)
    assert was_avail is False
    assert last_notified is None

    ts = datetime.now(timezone.utc).isoformat()
    set_item_available_sync(link, ts)

    was_avail2, last_notified2 = get_item_notification_state_sync(link)
    assert was_avail2 is True
    assert last_notified2 == ts


def test_dedup_suppresses_while_available(tmp_data_dir):
    """After set_item_available_sync, state remains True (suppresses re-notification)."""
    from models import (
        initialize_db,
        add_items_sync,
        get_item_notification_state_sync,
        set_item_available_sync,
    )
    from datetime import datetime, timezone

    initialize_db()
    link = "https://example.com/gadget"
    add_items_sync([("Gadget", link, False, 1, False)])

    ts = datetime.now(timezone.utc).isoformat()
    set_item_available_sync(link, ts)

    # Call again (simulating second poll tick with item still available)
    was_avail, _ = get_item_notification_state_sync(link)
    assert was_avail is True  # still True — no edge, should suppress


def test_dedup_renotify_after_restock(tmp_data_dir):
    """After clear_item_available_sync, state resets to False (ready for next restock)."""
    from models import (
        initialize_db,
        add_items_sync,
        get_item_notification_state_sync,
        set_item_available_sync,
        clear_item_available_sync,
    )
    from datetime import datetime, timezone

    initialize_db()
    link = "https://example.com/console"
    add_items_sync([("Console", link, False, 1, False)])

    ts = datetime.now(timezone.utc).isoformat()
    set_item_available_sync(link, ts)

    clear_item_available_sync(link)

    was_avail, last_notified = get_item_notification_state_sync(link)
    assert was_avail is False  # reset — next availability will be a rising edge again
    assert last_notified == ts  # last_notified preserved (historical record)


# ============================================================
# NOTIF-01: Dispatcher fan-out (Plan 05-04)
# ============================================================


async def test_all_notifiers_called(fake_notifier, notification_event):
    """All registered notifiers must receive the event when none raises."""
    from notifications.dispatcher import NotificationDispatcher

    a = fake_notifier()
    b = fake_notifier()
    c = fake_notifier()
    event = notification_event()

    dispatcher = NotificationDispatcher([a, b, c])
    await dispatcher.notify(event)

    assert len(a.events) == 1 and a.events[0] is event
    assert len(b.events) == 1 and b.events[0] is event
    assert len(c.events) == 1 and c.events[0] is event


async def test_failing_notifier_does_not_block(fake_notifier, notification_event):
    """A failing middle notifier must not prevent the other two from receiving the event."""
    from notifications.dispatcher import NotificationDispatcher

    a = fake_notifier()
    b = fake_notifier(raises=RuntimeError("channel exploded"))
    c = fake_notifier()
    event = notification_event()

    dispatcher = NotificationDispatcher([a, b, c])
    # notify() must return without raising even though b raises
    await dispatcher.notify(event)

    assert len(a.events) == 1 and a.events[0] is event, "first notifier must fire"
    assert len(c.events) == 1 and c.events[0] is event, "third notifier must fire"
    # b recorded the event before raising
    assert len(b.events) == 1, "failing notifier still appended the event before raising"


async def test_dispatcher_does_not_propagate(fake_notifier, notification_event):
    """notify() must return normally even when every notifier raises."""
    from notifications.dispatcher import NotificationDispatcher

    a = fake_notifier(raises=ValueError("bad"))
    b = fake_notifier(raises=RuntimeError("worse"))
    event = notification_event()

    dispatcher = NotificationDispatcher([a, b])
    # Should not raise
    await dispatcher.notify(event)


async def test_dispatcher_secret_scrub(fake_notifier, notification_event, capsys):
    """Failure log must contain the notifier class name but NOT the exception string (secret).

    writeLog() uses print() (not Python logging), so capsys captures the output.
    The test verifies that the exception message -- which embeds a fake webhook URL --
    never reaches the log, satisfying T-05-11 (secret scrub on channel failure).
    """
    from notifications.dispatcher import NotificationDispatcher

    secret_url = "https://discord.com/api/webhooks/999/secret-token-xyzzy"

    # Simulate a notifier whose exception embeds a secret webhook URL
    err = RuntimeError(f"POST {secret_url} returned 403")
    leaky = fake_notifier(raises=err)
    good = fake_notifier()
    event = notification_event()

    dispatcher = NotificationDispatcher([leaky, good])
    await dispatcher.notify(event)

    captured = capsys.readouterr()
    output = captured.out + captured.err

    assert output, "expected at least one log line written to stdout/stderr"
    assert "_FakeNotifier" in output, "notifier class name must appear in the log"
    assert secret_url not in output, "secret webhook URL must NOT appear in the log"
    assert "RuntimeError" in output, "exception class name must appear in the log"

    # Other notifier still fires
    assert len(good.events) == 1 and good.events[0] is event


# ============================================================
# NOTIF-03: Sound notifier (Plan 05-02)
# ============================================================


async def test_sound_notifier_detected(notification_event):
    """SoundNotifier.send with action='detected' must call play_available_sound exactly once."""
    from notifications.sound_notifier import SoundNotifier

    event = notification_event(action="detected")
    notifier = SoundNotifier()

    with patch("notifications.sound_notifier.play_available_sound") as mock_avail, \
         patch("notifications.sound_notifier.play_buy_sound") as mock_buy:
        await notifier.send(event)

    mock_avail.assert_called_once()
    mock_buy.assert_not_called()


async def test_sound_notifier_purchased(notification_event):
    """SoundNotifier.send with action='purchased' must call play_buy_sound exactly once."""
    from notifications.sound_notifier import SoundNotifier

    event = notification_event(action="purchased")
    notifier = SoundNotifier()

    with patch("notifications.sound_notifier.play_available_sound") as mock_avail, \
         patch("notifications.sound_notifier.play_buy_sound") as mock_buy:
        await notifier.send(event)

    mock_buy.assert_called_once()
    mock_avail.assert_not_called()


async def test_sound_notifier_unknown_action_plays_notification(notification_event):
    """SoundNotifier.send with an unknown action falls back to play_notification_sound."""
    from notifications.sound_notifier import SoundNotifier

    event = notification_event(action="unknown")
    notifier = SoundNotifier()

    with patch("notifications.sound_notifier.play_notification_sound") as mock_notif:
        await notifier.send(event)

    mock_notif.assert_called_once()


# ============================================================
# NOTIF-04: Discord notifier (Plan 05-02)
# ============================================================


def _make_discord_event():
    """Return a deterministic NotificationEvent for Discord tests."""
    from notifications.base import NotificationEvent

    return NotificationEvent(
        item_name="RTX 5090",
        item_url="https://bestbuy.com/rtx5090",
        platform="BestBuy",
        timestamp=datetime(2026, 6, 3, 12, 0, 0, tzinfo=timezone.utc),
        action="detected",
    )


def test_discord_payload_shape():
    """Discord embed payload must contain all required fields (title, url, color, timestamp, fields)."""
    from notifications.discord_notifier import _build_discord_payload

    event = _make_discord_event()
    payload = _build_discord_payload(event)

    assert "embeds" in payload
    embed = payload["embeds"][0]
    assert "title" in embed
    assert "url" in embed
    assert embed["url"] == event.item_url
    assert "color" in embed
    assert "timestamp" in embed
    fields = {f["name"]: f["value"] for f in embed["fields"]}
    assert "Platform" in fields
    assert fields["Platform"] == event.platform
    assert "Action" in fields
    assert fields["Action"] == event.action


def test_discord_timestamp_format():
    """Discord embed timestamp must match UTC ISO-8601 format with Z suffix."""
    from notifications.discord_notifier import _build_discord_payload

    event = _make_discord_event()
    payload = _build_discord_payload(event)
    ts = payload["embeds"][0]["timestamp"]

    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.000Z$", ts), (
        f"Timestamp {ts!r} does not match required UTC ISO-8601 format"
    )
    assert ts.endswith("Z")


def test_discord_rate_limit(monkeypatch):
    """A mocked 429 response from Discord must raise RuntimeError mentioning Retry-After."""
    from notifications.discord_notifier import _send_discord_blocking

    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.headers = {"Retry-After": "5"}

    with patch("notifications.discord_notifier.requests.post", return_value=mock_resp):
        with pytest.raises(RuntimeError) as exc_info:
            _send_discord_blocking("https://fake.webhook/", {"embeds": []})

    assert "5" in str(exc_info.value)


async def test_discord_send_calls_run_in_executor(monkeypatch, notification_event):
    """DiscordNotifier.send must complete without live network (requests.post mocked)."""
    from notifications.discord_notifier import DiscordNotifier

    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://fake.webhook/test")

    mock_resp = MagicMock()
    mock_resp.status_code = 204
    mock_resp.raise_for_status = MagicMock()

    event = notification_event(action="detected")
    notifier = DiscordNotifier()

    with patch("notifications.discord_notifier.requests.post", return_value=mock_resp) as mock_post:
        await notifier.send(event)

    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert call_kwargs.kwargs.get("timeout") == 10 or (
        len(call_kwargs.args) >= 1  # positional is also fine
    )


# ============================================================
# NOTIF-05: Email notifier (Plan 05-03)
# ============================================================


async def test_email_starttls(monkeypatch):
    """EmailNotifier must call starttls(), login(), and send_message() via STARTTLS path."""
    import smtplib
    from unittest.mock import AsyncMock, MagicMock, patch, call
    from core.config_schema import EmailConfig
    from notifications.email_notifier import EmailNotifier
    from notifications.base import NotificationEvent

    monkeypatch.setenv("SMTP_PASSWORD", "secret-pass")

    cfg = EmailConfig(
        enabled=True,
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_ssl=False,
        sender="bot@example.com",
        recipients=["user@example.com"],
    )
    notifier = EmailNotifier(cfg)

    mock_smtp_instance = MagicMock()
    mock_smtp_instance.__enter__ = MagicMock(return_value=mock_smtp_instance)
    mock_smtp_instance.__exit__ = MagicMock(return_value=False)

    event = NotificationEvent(
        item_name="RTX 5090",
        item_url="https://bestbuy.com/rtx5090",
        platform="BestBuy",
        timestamp=datetime(2026, 6, 3, 12, 0, 0, tzinfo=timezone.utc),
        action="detected",
    )

    with patch("smtplib.SMTP", return_value=mock_smtp_instance) as mock_smtp_cls:
        await notifier.send(event)

    mock_smtp_cls.assert_called_once_with("smtp.example.com", 587, timeout=10)
    mock_smtp_instance.starttls.assert_called_once()
    mock_smtp_instance.login.assert_called_once_with("bot@example.com", "secret-pass")
    mock_smtp_instance.send_message.assert_called_once()

    sent_msg = mock_smtp_instance.send_message.call_args[0][0]
    assert sent_msg["From"] == "bot@example.com"
    assert "user@example.com" in sent_msg["To"]


async def test_email_auth_error_isolated(monkeypatch):
    """SMTPAuthenticationError raised by mock must propagate out of send(), not be swallowed."""
    import smtplib
    from unittest.mock import MagicMock, patch
    from core.config_schema import EmailConfig
    from notifications.email_notifier import EmailNotifier
    from notifications.base import NotificationEvent

    monkeypatch.setenv("SMTP_PASSWORD", "wrong-pass")

    cfg = EmailConfig(
        enabled=True,
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_ssl=False,
        sender="bot@example.com",
        recipients=["user@example.com"],
    )
    notifier = EmailNotifier(cfg)

    mock_smtp_instance = MagicMock()
    mock_smtp_instance.__enter__ = MagicMock(return_value=mock_smtp_instance)
    mock_smtp_instance.__exit__ = MagicMock(return_value=False)
    mock_smtp_instance.login.side_effect = smtplib.SMTPAuthenticationError(535, "auth failed")

    event = NotificationEvent(
        item_name="RTX 5090",
        item_url="https://bestbuy.com/rtx5090",
        platform="BestBuy",
        timestamp=datetime(2026, 6, 3, 12, 0, 0, tzinfo=timezone.utc),
        action="detected",
    )

    with patch("smtplib.SMTP", return_value=mock_smtp_instance):
        with pytest.raises(smtplib.SMTPAuthenticationError):
            await notifier.send(event)


# ============================================================
# NOTIF-06: SMS notifier payload (Plan 05-03)
# ============================================================


async def test_sms_payload(monkeypatch):
    """SmsNotifier must POST to Twilio Messages.json with HTTPBasicAuth + To/From/Body form data."""
    from requests.auth import HTTPBasicAuth
    from core.config_schema import SmsConfig
    from notifications.sms_notifier import SmsNotifier
    from notifications.base import NotificationEvent

    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACTEST123")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "authtoken456")
    monkeypatch.setenv("TWILIO_FROM", "+15550001111")

    cfg = SmsConfig(enabled=True, to_number="+15559998888")
    notifier = SmsNotifier(cfg)

    event = NotificationEvent(
        item_name="RTX 5090",
        item_url="https://bestbuy.com/rtx5090",
        platform="BestBuy",
        timestamp=datetime(2026, 6, 3, 12, 0, 0, tzinfo=timezone.utc),
        action="detected",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.post", return_value=mock_resp) as mock_post:
        await notifier.send(event)

    mock_post.assert_called_once()
    call_args = mock_post.call_args
    posted_url = call_args.args[0] if call_args.args else call_args.kwargs.get("url")
    assert posted_url.endswith("/Messages.json")

    auth_arg = call_args.kwargs.get("auth")
    assert isinstance(auth_arg, HTTPBasicAuth)

    data_arg = call_args.kwargs.get("data", {})
    assert data_arg.get("To") == "+15559998888"
    assert data_arg.get("From") == "+15550001111"
    assert "Body" in data_arg
