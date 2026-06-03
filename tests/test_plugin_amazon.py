"""Tests for plugins/shopbot_plugin_amazon.py (PLG-01, PLG-03).

Loads the plugin via importlib.util.spec_from_file_location to mirror how the
registry discovers plugins -- no sys.path manipulation required.
"""

import importlib.util
import inspect
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Module loading (mirrors registry discovery pattern)
# ---------------------------------------------------------------------------

_PLUGIN_PATH = Path(__file__).parent.parent / "plugins" / "shopbot_plugin_amazon.py"


def _load_amazon_module():
    spec = importlib.util.spec_from_file_location("shopbot_plugin_amazon", _PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_amazon_module = _load_amazon_module()
AmazonPlugin = _amazon_module.AmazonPlugin

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

from core.plugin_base import RetailerPlugin  # noqa: E402


def _make_config(test_mode=True, items=None):
    """Return a minimal config-like object suitable for AmazonPlugin."""
    cfg = MagicMock()
    cfg.debug.test_mode = test_mode
    cfg.available.items = items or []
    return cfg


# ---------------------------------------------------------------------------
# ABC + structural tests (sync -- no async needed)
# ---------------------------------------------------------------------------


def test_amazon_satisfies_abc():
    """AmazonPlugin must be a concrete subclass of RetailerPlugin (PLG-01)."""
    assert issubclass(AmazonPlugin, RetailerPlugin)
    # Instantiating must succeed (all abstract methods implemented).
    plugin = AmazonPlugin(config=None)
    assert plugin is not None


def test_domain_patterns_includes_amazon():
    assert "amazon.com" in AmazonPlugin.domain_patterns


def test_no_global_driver():
    """PLG-03: no module-level 'driver'; instance.driver is None before setup()."""
    assert not hasattr(_amazon_module, "driver"), (
        "Module must not define a top-level 'driver' variable"
    )
    plugin = AmazonPlugin(config=None)
    assert plugin.driver is None

    # Also verify the source contains the required self.driver assignment pattern.
    source = _PLUGIN_PATH.read_text()
    assert "self.driver = await nodriver.start" in source, (
        "Plugin must build self.driver via nodriver.start() in setup()"
    )


# ---------------------------------------------------------------------------
# Async tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_availability_returns_true_when_button_found(fake_browser):
    """check_availability returns True when add-to-cart button is present."""
    plugin = AmazonPlugin(config=_make_config())
    plugin.driver = fake_browser

    # fake_browser.get returns fake_tab; fake_tab.select returns a fake element.
    # Patch detect_captcha to skip blocking input().
    with patch.object(plugin, "detect_captcha", new=AsyncMock(return_value=False)):
        result = await plugin.check_availability("https://www.amazon.com/dp/B00TEST")

    assert result is True


@pytest.mark.asyncio
async def test_check_availability_returns_false_when_no_button(fake_browser):
    """check_availability returns False when both buttons are absent."""
    plugin = AmazonPlugin(config=_make_config())
    plugin.driver = fake_browser

    # Make tab.select always return None (button not found).
    fake_browser.main_tab.select = AsyncMock(return_value=None)
    fake_browser.get.return_value.select = AsyncMock(return_value=None)

    with patch.object(plugin, "detect_captcha", new=AsyncMock(return_value=False)):
        result = await plugin.check_availability("https://www.amazon.com/dp/B00TEST")

    assert result is False


@pytest.mark.asyncio
async def test_check_availability_returns_bool_type(fake_browser):
    """check_availability always returns a bool, never None or another type."""
    plugin = AmazonPlugin(config=_make_config())
    plugin.driver = fake_browser

    with patch.object(plugin, "detect_captcha", new=AsyncMock(return_value=False)):
        result = await plugin.check_availability("https://www.amazon.com/dp/B00TEST")

    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_check_availability_never_raises(fake_browser):
    """check_availability catches exceptions and returns False instead of raising."""
    plugin = AmazonPlugin(config=_make_config())
    plugin.driver = fake_browser

    # Make browser.get raise an unexpected error.
    fake_browser.get = AsyncMock(side_effect=RuntimeError("network error"))

    result = await plugin.check_availability("https://www.amazon.com/dp/B00TEST")

    assert result is False


@pytest.mark.asyncio
async def test_detect_captcha_returns_true_when_element_found(fake_browser):
    """detect_captcha returns True when the CAPTCHA text element is found."""
    plugin = AmazonPlugin(config=_make_config())
    plugin.driver = fake_browser

    # fake_browser.main_tab.find returns a fake element by default.
    result = await plugin.detect_captcha()

    assert result is True


@pytest.mark.asyncio
async def test_detect_captcha_returns_false_when_element_absent(fake_browser):
    """detect_captcha returns False when tab.find returns None."""
    plugin = AmazonPlugin(config=_make_config())
    plugin.driver = fake_browser
    fake_browser.main_tab.find = AsyncMock(return_value=None)

    result = await plugin.detect_captcha()

    assert result is False
