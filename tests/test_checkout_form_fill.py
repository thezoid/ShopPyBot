"""Tests for BestBuy + Amazon form-fill behavior (BUY-07 / Phase 20-04).

Covers:
- BestBuyPlugin._fill_field success (clear_input + send_keys called, returns True)
- BestBuyPlugin._fill_field missing selector (WARNING logged, returns False)
- BestBuy auto_buy returns False when _checkout_profile is None (no place_order_guarded)
- BestBuy auto_buy returns False when a required selector is absent (no place_order_guarded)
- Optional address_line2: no #street2 fill when value is None; no error when selector absent
- Amazon auto_buy continues to place_order_guarded when CVV field is absent (Pitfall 4)

Reviewer note: fake_element.clear_input and fake_element.send_keys are set as AsyncMocks
explicitly in each test that exercises _fill_field -- the conftest fake_element fixture does
NOT set clear_input, so we must set it here.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, call

from core.checkout_profile import CheckoutProfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bestbuy_plugin(config=None):
    """Build a no-browser BestBuyPlugin."""
    from plugins.shopbot_plugin_bestbuy import BestBuyPlugin

    plugin = BestBuyPlugin(config=config)
    plugin.driver = MagicMock()
    return plugin


def _make_amazon_plugin(config=None):
    """Build a no-browser AmazonPlugin."""
    from plugins.shopbot_plugin_amazon import AmazonPlugin

    plugin = AmazonPlugin(config=config)
    plugin.driver = MagicMock()
    return plugin


def _complete_profile(**overrides):
    """Return a CheckoutProfile with all required fields filled."""
    data = dict(
        first_name="Jane",
        last_name="Doe",
        address_line1="123 Main St",
        address_line2=None,
        city="Springfield",
        state="IL",
        zip_code="62701",
        country="US",
        phone="5551234567",
    )
    data.update(overrides)
    return CheckoutProfile(**data)


def _make_element():
    """Return a MagicMock element with clear_input and send_keys as AsyncMocks."""
    el = MagicMock()
    el.clear_input = AsyncMock()
    el.send_keys = AsyncMock()
    el.click = AsyncMock()
    el.apply = AsyncMock()
    return el


def _no_op_config():
    """Return a minimal config object that passes the monitor_only guard (False)."""
    debug = MagicMock()
    debug.monitor_only = False
    debug.test_mode = False
    cfg = MagicMock()
    cfg.debug = debug
    cfg.available.items = []
    cfg.checkout.step_timeout_secs = 30  # BUY-06: required for asyncio.timeout in auto_buy
    return cfg


# ---------------------------------------------------------------------------
# _fill_field unit tests
# ---------------------------------------------------------------------------


async def test_bestbuy_fill_field_success():
    """_fill_field returns True and calls clear_input then send_keys(value)."""
    plugin = _make_bestbuy_plugin()
    el = _make_element()
    tab = MagicMock()
    tab.select = AsyncMock(return_value=el)

    result = await plugin._fill_field(tab, "#first-name", "Jane")

    assert result is True
    el.clear_input.assert_awaited_once()
    el.send_keys.assert_awaited_once_with("Jane")


async def test_bestbuy_fill_field_missing_selector_warns_false(monkeypatch):
    """_fill_field with selector returning None returns False and logs a WARNING.

    writeLog writes to stdout, not Python logging; monkeypatch it to capture calls.
    """
    import plugins.shopbot_plugin_bestbuy as bb_mod

    log_calls = []
    monkeypatch.setattr(bb_mod, "writeLog", lambda msg, level="INFO": log_calls.append((msg, level)))

    plugin = _make_bestbuy_plugin()
    tab = MagicMock()
    tab.select = AsyncMock(return_value=None)

    result = await plugin._fill_field(tab, "#first-name", "Jane")

    assert result is False
    warning_calls = [(msg, lvl) for msg, lvl in log_calls if lvl == "WARNING"]
    assert any("#first-name" in msg for msg, _ in warning_calls), (
        f"Expected '#first-name' in WARNING log; got: {warning_calls}"
    )


# ---------------------------------------------------------------------------
# auto_buy -- profile-None guard
# ---------------------------------------------------------------------------


async def test_autobuy_returns_false_no_profile():
    """BestBuy auto_buy returns False immediately when _checkout_profile is None.

    place_order_guarded must NOT be awaited.
    """
    plugin = _make_bestbuy_plugin(config=_no_op_config())
    plugin._checkout_profile = None  # explicit None (already the default)
    plugin.login = AsyncMock()
    plugin.place_order_guarded = AsyncMock(return_value=True)

    # Build a tab that returns a truthy element for every selector up to login,
    # so the flow reaches the profile-None guard.
    el = _make_element()

    def _select_side_effect(selector, timeout=10):
        # add-to-cart, qty_dropdown, qty_option, checkout all return el
        return el

    tab = MagicMock()
    tab.select = AsyncMock(side_effect=_select_side_effect)
    plugin.driver.get = AsyncMock(return_value=tab)

    result = await plugin.auto_buy("https://www.bestbuy.com/product/123")

    assert result is False
    plugin.place_order_guarded.assert_not_awaited()


# ---------------------------------------------------------------------------
# auto_buy -- missing required selector aborts
# ---------------------------------------------------------------------------


async def test_missing_required_selector_aborts():
    """A None return for a required selector stops auto_buy (no place_order_guarded)."""
    plugin = _make_bestbuy_plugin(config=_no_op_config())
    plugin._checkout_profile = _complete_profile()
    plugin.login = AsyncMock()
    plugin.place_order_guarded = AsyncMock(return_value=True)

    el = _make_element()

    # Map selectors to return values. The #street selector returns None to trigger abort.
    selector_map = {
        ".add-to-cart-button": el,
        ".a-dropdown-prompt": el,
        "#quantity_1": el,
        ".checkout-buttons__checkout": el,
        "#first-name": el,
        "#last-name": el,
        "#street": None,   # MISSING required field
    }

    def _side_effect(selector, timeout=10):
        return selector_map.get(selector, el)

    tab = MagicMock()
    tab.select = AsyncMock(side_effect=_side_effect)
    plugin.driver.get = AsyncMock(return_value=tab)

    result = await plugin.auto_buy("https://www.bestbuy.com/product/123")

    assert result is False
    plugin.place_order_guarded.assert_not_awaited()


# ---------------------------------------------------------------------------
# auto_buy -- address_line2 optional skip
# ---------------------------------------------------------------------------


async def test_address_line2_none_no_street2_call():
    """When profile.address_line2 is None, #street2 is never selected."""
    plugin = _make_bestbuy_plugin(config=_no_op_config())
    plugin._checkout_profile = _complete_profile(address_line2=None)
    plugin.login = AsyncMock()
    plugin.place_order_guarded = AsyncMock(return_value=True)

    el = _make_element()
    selectors_queried = []

    def _side_effect(selector, timeout=10):
        selectors_queried.append(selector)
        return el

    tab = MagicMock()
    tab.select = AsyncMock(side_effect=_side_effect)
    plugin.driver.get = AsyncMock(return_value=tab)

    await plugin.auto_buy("https://www.bestbuy.com/product/123")

    assert "#street2" not in selectors_queried


async def test_address_line2_set_but_selector_none_no_error():
    """When profile.address_line2 is set but #street2 returns None, no exception raised."""
    plugin = _make_bestbuy_plugin(config=_no_op_config())
    plugin._checkout_profile = _complete_profile(address_line2="Apt 4B")
    plugin.login = AsyncMock()
    plugin.place_order_guarded = AsyncMock(return_value=True)

    el = _make_element()

    def _side_effect(selector, timeout=10):
        if selector == "#street2":
            return None
        return el

    tab = MagicMock()
    tab.select = AsyncMock(side_effect=_side_effect)
    plugin.driver.get = AsyncMock(return_value=tab)

    # Should not raise; flow continues to place_order_guarded
    result = await plugin.auto_buy("https://www.bestbuy.com/product/123")
    # place_order_guarded result returned (True from our mock)
    assert result is True


# ---------------------------------------------------------------------------
# Amazon -- CVV skip-if-absent
# ---------------------------------------------------------------------------


async def test_amazon_cvv_skip_when_field_absent():
    """Amazon auto_buy continues to place_order_guarded when CVV select returns None.

    An absent CVV field must NOT cause auto_buy to return False (Pitfall 4 / T-20-10).
    """
    plugin = _make_amazon_plugin(config=_no_op_config())
    plugin._cvv = "999"  # CVV is set
    plugin._checkout_profile = _complete_profile()
    plugin.login = AsyncMock()
    plugin.place_order_guarded = AsyncMock(return_value=True)

    el = _make_element()

    # Amazon auto_buy flow selectors in order:
    # driver.get(url) -> tab
    # tab.select(".a-button-dropdown")  -> el (qty dropdown)
    # tab.select("#quantity_0")          -> el (qty option; quantity=1, so qty-1=0)
    # tab.select("#buy-now-button")      -> el
    # tab.select("#submitOrderButtonId") -> el (place_order found)
    # tab.select("#addCreditCardCvvInput") -> None (absent -- should skip gracefully)

    selector_map = {
        ".a-button-dropdown": el,
        "#quantity_0": el,
        "#buy-now-button": el,
        "#submitOrderButtonId": el,
        "#addCreditCardCvvInput": None,  # CVV field ABSENT
    }

    def _side_effect(selector, timeout=10):
        return selector_map.get(selector, el)

    tab = MagicMock()
    tab.select = AsyncMock(side_effect=_side_effect)
    plugin.driver.get = AsyncMock(return_value=tab)

    result = await plugin.auto_buy("https://www.amazon.com/dp/B0001")

    # CVV field absent must NOT cause False; place_order_guarded must be awaited.
    plugin.place_order_guarded.assert_awaited_once()
    assert result is True
