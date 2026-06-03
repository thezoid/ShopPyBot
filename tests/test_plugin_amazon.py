"""Tests for plugins/shopbot_plugin_amazon.py (PLG-01, PLG-03, ASYNC-03).

Loads the plugin via importlib.util.spec_from_file_location to mirror how the
registry discovers plugins -- no sys.path manipulation required.
"""

import asyncio
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


# ---------------------------------------------------------------------------
# ASYNC-03: asyncio.Event intervention pattern tests (TDD RED)
# ---------------------------------------------------------------------------


def test_amazon_plugin_has_four_event_attrs():
    """AmazonPlugin.__init__ must create 4 asyncio.Event attributes (ASYNC-03)."""
    plugin = AmazonPlugin(config=None)
    for attr in ("captcha_event", "passkey_event", "otp_event", "test_pause_event"):
        assert hasattr(plugin, attr), f"AmazonPlugin missing attribute: {attr}"
        assert isinstance(getattr(plugin, attr), asyncio.Event), (
            f"{attr} must be asyncio.Event, got {type(getattr(plugin, attr))}"
        )


def test_amazon_plugin_has_wait_user_action_helper():
    """AmazonPlugin must define _wait_user_action coroutine method (ASYNC-03)."""
    plugin = AmazonPlugin(config=None)
    assert hasattr(plugin, "_wait_user_action"), (
        "AmazonPlugin missing _wait_user_action helper"
    )
    assert asyncio.iscoroutinefunction(plugin._wait_user_action), (
        "_wait_user_action must be an async def coroutine"
    )


def test_no_input_call_in_amazon_source():
    """No input() call (non-comment) must exist in the Amazon plugin source (ASYNC-03)."""
    source_lines = _PLUGIN_PATH.read_text().splitlines()
    violations = [
        (i + 1, line)
        for i, line in enumerate(source_lines)
        if "input(" in line and not line.lstrip().startswith("#")
    ]
    assert not violations, (
        "Found input() calls in non-comment lines:\n"
        + "\n".join(f"  line {ln}: {txt}" for ln, txt in violations)
    )


@pytest.mark.asyncio
async def test_captcha_event_resumes_check_availability(fake_browser, event_shim):
    """check_availability resumes after captcha_event is set (ASYNC-03 Event wakeup).

    Sequence:
      1. detect_captcha returns True -> _wait_user_action is called on captcha_event
      2. Before the await can block, the event_shim fires captcha_event via
         loop.call_soon_threadsafe (the real stdin-listener bridge)
      3. check_availability completes and returns a bool without hanging
    """
    plugin = AmazonPlugin(config=_make_config())
    plugin.driver = fake_browser

    loop = asyncio.get_running_loop()

    # Schedule the event signal to fire on the next iteration of the event loop.
    # This ensures _wait_user_action hits its await before the event is set,
    # proving the coroutine wakes from the Event -- not from a pre-set flag.
    loop.call_soon(event_shim, plugin.captcha_event, loop)

    with patch.object(plugin, "detect_captcha", new=AsyncMock(return_value=True)):
        result = await plugin.check_availability("https://www.amazon.com/dp/B00TEST")

    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_wait_user_action_clears_event_after_resume():
    """_wait_user_action must clear the event in finally so next cycle re-waits (Pitfall 7)."""
    plugin = AmazonPlugin(config=None)
    event = plugin.captcha_event
    event.set()  # pre-set so wait_for returns immediately

    with patch("plugins.shopbot_plugin_amazon.play_notification_sound"), \
         patch("plugins.shopbot_plugin_amazon.writeLog"):
        await plugin._wait_user_action(event, "test message")

    assert not event.is_set(), "Event must be cleared after _wait_user_action returns"


@pytest.mark.asyncio
async def test_wait_user_action_timeout_does_not_raise():
    """_wait_user_action must log and continue (not raise) on 300s timeout."""
    plugin = AmazonPlugin(config=None)
    event = asyncio.Event()  # never set -> will time out

    with patch("plugins.shopbot_plugin_amazon.play_notification_sound"), \
         patch("plugins.shopbot_plugin_amazon.writeLog"), \
         patch("plugins.shopbot_plugin_amazon.asyncio") as mock_asyncio:
        # Mock asyncio.wait_for to raise TimeoutError immediately
        mock_asyncio.wait_for = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_asyncio.TimeoutError = asyncio.TimeoutError
        mock_asyncio.Event = asyncio.Event

        # Should not raise -- timeout is caught internally
        try:
            await plugin._wait_user_action(event, "test")
        except asyncio.TimeoutError:
            pytest.fail("_wait_user_action must not propagate TimeoutError")
