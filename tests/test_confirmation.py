"""Unit tests for core/confirmation.py -- detect_order_confirmation (BUY-03).

All tests use FakeTab/FakeElement to avoid any browser dependency.
asyncio_mode=auto (configured in pyproject.toml) -- no decorator needed.
"""
from core.confirmation import detect_order_confirmation


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class FakeElement:
    """Minimal nodriver Element stub with a .text str attribute."""

    def __init__(self, text: str) -> None:
        self.text = text


class FakeTab:
    """Minimal nodriver Tab stub: sync target.url + async sleep/select.

    selector_map: dict mapping CSS selector strings to FakeElement or None.
    sleep() is a no-op so tests skip the 3s settle delay.
    """

    def __init__(self, url: str, selector_map: dict | None = None) -> None:
        self.target = type("_T", (), {"url": url})()
        self._selector_map: dict = selector_map or {}

    async def sleep(self, t: float) -> None:
        pass  # skip settle delay in tests

    async def select(self, selector: str, timeout: int = 10):
        return self._selector_map.get(selector)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_url_match_url_param():
    """Amazon url with orderID query param returns the param value directly."""
    tab = FakeTab(
        url="https://www.amazon.com/gp/buy/thankyou?orderID=302-001",
        selector_map={},
    )
    result = await detect_order_confirmation(tab, "AmazonPlugin")
    assert result == "302-001"


async def test_url_match_dom_hit():
    """Amazon url without query param falls back to DOM selector text."""
    tab = FakeTab(
        url="https://www.amazon.com/gp/buy/thankyou",
        selector_map={"#confirmedOrderId": FakeElement("123-456")},
    )
    result = await detect_order_confirmation(tab, "AmazonPlugin")
    assert result == "123-456"


async def test_bestbuy_dom_hit():
    """BestBuy confirmation url with DOM order-number selector returns text."""
    tab = FakeTab(
        url="https://www.bestbuy.com/checkout/r/thank-you",
        selector_map={".thank-you-order-number": FakeElement("BBY01-806")},
    )
    result = await detect_order_confirmation(tab, "BestBuyPlugin")
    assert result == "BBY01-806"


async def test_url_match_dom_miss_returns_sentinel():
    """URL matches but no param or DOM hit -- sentinel CONFIRMED-<ts> returned."""
    tab = FakeTab(
        url="https://www.amazon.com/gp/buy/thankyou",
        selector_map={},
    )
    result = await detect_order_confirmation(tab, "AmazonPlugin")
    assert result is not None
    assert result.startswith("CONFIRMED-")


async def test_url_no_match():
    """Non-confirmation URL returns None."""
    tab = FakeTab(
        url="https://www.amazon.com/product/B001",
        selector_map={},
    )
    result = await detect_order_confirmation(tab, "AmazonPlugin")
    assert result is None


async def test_unknown_platform():
    """Unknown platform name returns None (legacy fallback)."""
    tab = FakeTab(
        url="https://www.walmart.com/checkout/thank-you",
        selector_map={},
    )
    result = await detect_order_confirmation(tab, "WalmartPlugin")
    assert result is None
