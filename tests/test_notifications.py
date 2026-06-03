"""Notification system test scaffold (Phase 5).

Wave 0 (this plan -- 05-01):
  - test_sms_misconfigured_raises: passes now (config schema)
  - test_sms_disabled_by_default: passes now (config schema)
  - test_dedup_*: passes now (models dedup columns/state fns)
  - test_notifier_abc_*: passes now (Notifier ABC + NotificationEvent)
  - All 14 named tests present; tests for Plans 02-04 marked xfail.

Wave 1+ (Plans 02-04): xfail tests become real as channel notifiers are implemented.
"""

import os
from datetime import datetime, timezone

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
# NOTIF-01: Dispatcher fan-out (xfail — Plan 05-04)
# ============================================================


@pytest.mark.xfail(reason="implemented in plan 05-04", strict=False)
def test_failing_notifier_does_not_block():
    """A failing channel notifier must not prevent other channels from firing."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(reason="implemented in plan 05-04", strict=False)
def test_all_notifiers_called():
    """All enabled notifiers must be called for a single NotificationEvent."""
    pytest.fail("not yet implemented")


# ============================================================
# NOTIF-03: Sound notifier (xfail — Plan 05-02)
# ============================================================


@pytest.mark.xfail(reason="implemented in plan 05-02", strict=False)
def test_sound_notifier_detected():
    """SoundNotifier.send with action='detected' must call play_available_sound."""
    pytest.fail("not yet implemented")


# ============================================================
# NOTIF-04: Discord notifier (xfail — Plan 05-02)
# ============================================================


@pytest.mark.xfail(reason="implemented in plan 05-02", strict=False)
def test_discord_payload_shape():
    """Discord embed payload must contain all required fields (title, url, color, etc.)."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(reason="implemented in plan 05-02", strict=False)
def test_discord_timestamp_format():
    """Discord embed timestamp must be UTC ISO-8601 with Z suffix."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(reason="implemented in plan 05-02", strict=False)
def test_discord_rate_limit():
    """Discord 429 response must raise RuntimeError with Retry-After info."""
    pytest.fail("not yet implemented")


# ============================================================
# NOTIF-05: Email notifier (xfail — Plan 05-03)
# ============================================================


@pytest.mark.xfail(reason="implemented in plan 05-03", strict=False)
def test_email_starttls():
    """EmailNotifier must send via STARTTLS with correct headers."""
    pytest.fail("not yet implemented")


@pytest.mark.xfail(reason="implemented in plan 05-03", strict=False)
def test_email_auth_error_isolated():
    """SMTPAuthenticationError in EmailNotifier must be caught at the channel boundary."""
    pytest.fail("not yet implemented")


# ============================================================
# NOTIF-06: SMS notifier payload (xfail — Plan 05-03)
# ============================================================


@pytest.mark.xfail(reason="implemented in plan 05-03", strict=False)
def test_sms_payload():
    """SmsNotifier must POST to the correct Twilio URL with Basic Auth + form params."""
    pytest.fail("not yet implemented")
