"""Tests for Plan 16-02: NotificationEvent price fields, get_price() ABC hook,
Amazon _parse_price_to_cents parser, and notifier price_drop branches.

RED phase: all tests fail until Tasks 2-4 land.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Task 1-a: NotificationEvent optional price fields default to None
# ---------------------------------------------------------------------------


def test_event_optional_price_fields_default_none(notification_event):
    """New price fields default to None; existing positional construction unchanged."""
    from notifications.base import NotificationEvent

    # Existing positional construction must still work.
    event = notification_event()
    assert event.price_cents is None
    assert event.target_price_cents is None
    assert event.pct_from_target is None

    # Explicit keyword construction with all five required fields still works.
    event2 = NotificationEvent(
        item_name="Widget",
        item_url="https://example.com/w",
        platform="Amazon",
        timestamp=datetime.now(timezone.utc),
        action="detected",
    )
    assert event2.price_cents is None
    assert event2.target_price_cents is None
    assert event2.pct_from_target is None

    # Populate price fields when provided.
    event3 = NotificationEvent(
        item_name="Widget",
        item_url="https://example.com/w",
        platform="Amazon",
        timestamp=datetime.now(timezone.utc),
        action="price_drop",
        price_cents=4999,
        target_price_cents=5999,
        pct_from_target=16.7,
    )
    assert event3.price_cents == 4999
    assert event3.target_price_cents == 5999
    assert event3.pct_from_target == 16.7


# ---------------------------------------------------------------------------
# Task 1-b: _parse_price_to_cents text→cents parser fixtures
# ---------------------------------------------------------------------------


def test_parse_price_to_cents_fixtures():
    """Parser converts canonical price strings to integer cents; rejects garbage."""
    from plugins.shopbot_plugin_amazon import _parse_price_to_cents

    # Valid inputs.
    assert _parse_price_to_cents("$49.99") == 4999
    assert _parse_price_to_cents("1,299.00") == 129900
    assert _parse_price_to_cents("$1.00") == 100

    # Invalid / empty / unavailable inputs must return None, not raise.
    assert _parse_price_to_cents("") is None
    assert _parse_price_to_cents(None) is None
    assert _parse_price_to_cents("Currently unavailable") is None
    assert _parse_price_to_cents("Price: see cart") is None

    # T-04: zero and negative-looking strings must return None (guard: value <= 0)
    assert _parse_price_to_cents("$0.00") is None, "$0.00 must return None"
    assert _parse_price_to_cents("-$5.00") is None, "negative price string must return None"


# ---------------------------------------------------------------------------
# Task 1-c: Default get_price() on ABC returns None
# ---------------------------------------------------------------------------


async def test_get_price_default_none():
    """A plugin that does not override get_price() must return None."""
    from core.plugin_base import RetailerPlugin

    class _MinimalPlugin(RetailerPlugin):
        domain_patterns = ["minimal.example.com"]

        async def check_availability(self, url: str) -> bool:
            return True

        async def auto_buy(self, url: str) -> bool:
            return False

    plugin = _MinimalPlugin(config=None)
    result = await plugin.get_price("https://minimal.example.com/item")
    assert result is None


# ---------------------------------------------------------------------------
# Task 1-d: Amazon get_price() parses real DOM price text
# ---------------------------------------------------------------------------


async def test_amazon_get_price_parses_dom():
    """AmazonPlugin.get_price() returns integer cents when selector returns price text;
    returns None when the element is missing or text is malformed."""
    from plugins.shopbot_plugin_amazon import AmazonPlugin

    # --- success case: selector returns a price element with "$59.99" ---
    fake_element_ok = MagicMock()
    fake_element_ok.text = "$59.99"

    fake_tab_ok = MagicMock()
    # First selector hit returns the price element; no need for fallback selectors.
    fake_tab_ok.select = AsyncMock(return_value=fake_element_ok)
    fake_tab_ok.evaluate = AsyncMock(return_value="$59.99")

    fake_browser_ok = MagicMock()
    fake_browser_ok.get = AsyncMock(return_value=fake_tab_ok)
    fake_browser_ok.main_tab = fake_tab_ok

    plugin_ok = AmazonPlugin.__new__(AmazonPlugin)
    plugin_ok.driver = fake_browser_ok
    plugin_ok.config = None

    result = await plugin_ok.get_price("https://www.amazon.com/dp/B001")
    assert result == 5999

    # --- missing element case: select returns None for all selectors ---
    fake_tab_none = MagicMock()
    fake_tab_none.select = AsyncMock(return_value=None)

    fake_browser_none = MagicMock()
    fake_browser_none.get = AsyncMock(return_value=fake_tab_none)

    plugin_none = AmazonPlugin.__new__(AmazonPlugin)
    plugin_none.driver = fake_browser_none
    plugin_none.config = None

    result_none = await plugin_none.get_price("https://www.amazon.com/dp/B002")
    assert result_none is None

    # --- malformed price text: select returns an element with garbage text ---
    fake_element_bad = MagicMock()
    fake_element_bad.text = "Currently unavailable"

    fake_tab_bad = MagicMock()
    fake_tab_bad.select = AsyncMock(return_value=fake_element_bad)

    fake_browser_bad = MagicMock()
    fake_browser_bad.get = AsyncMock(return_value=fake_tab_bad)

    plugin_bad = AmazonPlugin.__new__(AmazonPlugin)
    plugin_bad.driver = fake_browser_bad
    plugin_bad.config = None

    result_bad = await plugin_bad.get_price("https://www.amazon.com/dp/B003")
    assert result_bad is None


# ---------------------------------------------------------------------------
# Task 1-e: Discord price_drop payload
# ---------------------------------------------------------------------------


def test_discord_price_drop_payload():
    """_build_discord_payload for price_drop includes current price, target, and pct."""
    from notifications.discord_notifier import _build_discord_payload
    from notifications.base import NotificationEvent

    event = NotificationEvent(
        item_name="Fancy Widget",
        item_url="https://amazon.com/dp/B001",
        platform="Amazon",
        timestamp=datetime.now(timezone.utc),
        action="price_drop",
        price_cents=4500,
        target_price_cents=5000,
        pct_from_target=10.0,
    )

    payload = _build_discord_payload(event)
    payload_str = str(payload)

    assert "$45.00" in payload_str
    assert "$50.00" in payload_str
    assert "10.0" in payload_str or "10%" in payload_str


# ---------------------------------------------------------------------------
# Task 1-f: Email and SMS price_drop formatting
# ---------------------------------------------------------------------------


async def test_email_sms_price_drop_format():
    """Email and SMS notifiers include current price $X.XX in price_drop output."""
    from notifications.base import NotificationEvent

    price_event = NotificationEvent(
        item_name="Gadget",
        item_url="https://amazon.com/dp/B004",
        platform="Amazon",
        timestamp=datetime.now(timezone.utc),
        action="price_drop",
        price_cents=7999,
        target_price_cents=8999,
        pct_from_target=11.1,
    )

    # --- Email: _build_email_body or send logic must mention price ---
    from notifications.email_notifier import _build_email_body

    body = _build_email_body(price_event)
    assert "$79.99" in body

    # --- SMS: _build_sms_body or format logic must mention price ---
    from notifications.sms_notifier import _build_sms_body

    sms_body = _build_sms_body(price_event)
    assert "$79.99" in sms_body
