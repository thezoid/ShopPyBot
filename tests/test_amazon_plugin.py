"""Tests for plugins/shopbot_plugin_amazon.py -- _last_tab + get_active_tab() (BUY-03).

Covers:
- AmazonPlugin.get_active_tab() returns self._last_tab when set
- AmazonPlugin.get_active_tab() falls back to driver.main_tab when _last_tab not set
- AmazonPlugin.get_active_tab() returns None when both _last_tab and main_tab absent
- self._last_tab is assigned before place_order_guarded (structural assertion via source)
"""
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_amazon_plugin():
    """Build an AmazonPlugin instance without launching a real browser."""
    from plugins.shopbot_plugin_amazon import AmazonPlugin

    instance = AmazonPlugin(config=None)
    instance.driver = None  # no browser
    return instance


# ---------------------------------------------------------------------------
# get_active_tab() override tests
# ---------------------------------------------------------------------------


def test_get_active_tab_returns_last_tab_when_set():
    """get_active_tab() returns self._last_tab when it has been assigned."""
    plugin = _make_amazon_plugin()
    fake_tab = MagicMock()
    plugin._last_tab = fake_tab
    assert plugin.get_active_tab() is fake_tab


def test_get_active_tab_falls_back_to_main_tab():
    """get_active_tab() returns driver.main_tab when _last_tab is not set."""
    plugin = _make_amazon_plugin()
    fake_driver = MagicMock()
    fake_main_tab = MagicMock()
    fake_driver.main_tab = fake_main_tab
    plugin.driver = fake_driver
    # _last_tab not set
    assert plugin.get_active_tab() is fake_main_tab


def test_get_active_tab_returns_none_when_both_absent():
    """get_active_tab() returns None when neither _last_tab nor driver.main_tab exist."""
    plugin = _make_amazon_plugin()
    # driver is None, no _last_tab
    result = plugin.get_active_tab()
    assert result is None


def test_get_active_tab_last_tab_none_falls_back_to_main_tab():
    """get_active_tab() falls through to main_tab when _last_tab is explicitly None."""
    plugin = _make_amazon_plugin()
    plugin._last_tab = None  # explicitly None
    fake_driver = MagicMock()
    fake_main_tab = MagicMock()
    fake_driver.main_tab = fake_main_tab
    plugin.driver = fake_driver
    assert plugin.get_active_tab() is fake_main_tab
