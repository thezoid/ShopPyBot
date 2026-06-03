"""Tests for plugins/shopbot_plugin_bestbuy.py (PLG-02, PLG-03).

Loads the plugin via importlib.util.spec_from_file_location to mirror how the
registry discovers plugins -- no sys.path manipulation required.

Key test: test_autobuy_calls_update_purchased asserts the PLG-02 fix is present --
update_item_purchased must be called once with the item url after a successful buy.
"""

import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Module loading (mirrors registry discovery pattern)
# ---------------------------------------------------------------------------

_PLUGIN_PATH = Path(__file__).parent.parent / "plugins" / "shopbot_plugin_bestbuy.py"


def _load_bestbuy_module():
    spec = importlib.util.spec_from_file_location("shopbot_plugin_bestbuy", _PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_bestbuy_module = _load_bestbuy_module()
BestBuyPlugin = _bestbuy_module.BestBuyPlugin

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

from core.plugin_base import RetailerPlugin  # noqa: E402


def _make_config(items=None):
    cfg = MagicMock()
    cfg.available.items = items or []
    return cfg


# ---------------------------------------------------------------------------
# ABC + structural tests (sync)
# ---------------------------------------------------------------------------


def test_bestbuy_satisfies_abc():
    """BestBuyPlugin must be a concrete subclass of RetailerPlugin (PLG-02)."""
    assert issubclass(BestBuyPlugin, RetailerPlugin)
    plugin = BestBuyPlugin(config=None)
    assert plugin is not None


def test_domain_patterns_includes_bestbuy():
    assert "bestbuy.com" in BestBuyPlugin.domain_patterns


def test_no_global_driver():
    """PLG-03: no module-level 'driver'; instance.driver is None before setup()."""
    assert not hasattr(_bestbuy_module, "driver"), (
        "Module must not define a top-level 'driver' variable"
    )
    plugin = BestBuyPlugin(config=None)
    assert plugin.driver is None

    source = _PLUGIN_PATH.read_text()
    assert "self.driver = await nodriver.start" in source, (
        "Plugin must build self.driver via nodriver.start() in setup()"
    )


def test_cvv_attribute_defaults_to_none():
    """_cvv must default to None; main.py sets it after setup (Plan 05 contract)."""
    plugin = BestBuyPlugin(config=None)
    assert plugin._cvv is None


# ---------------------------------------------------------------------------
# Async tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_availability_returns_true_when_button_found(fake_browser):
    """check_availability returns True when add-to-cart button is present."""
    plugin = BestBuyPlugin(config=_make_config())
    plugin.driver = fake_browser

    result = await plugin.check_availability("https://www.bestbuy.com/site/test/1234.p")

    assert result is True


@pytest.mark.asyncio
async def test_check_availability_returns_false_when_no_button(fake_browser):
    """check_availability returns False when add-to-cart button is absent."""
    plugin = BestBuyPlugin(config=_make_config())
    plugin.driver = fake_browser

    fake_browser.get.return_value.select = AsyncMock(return_value=None)

    result = await plugin.check_availability("https://www.bestbuy.com/site/test/1234.p")

    assert result is False


@pytest.mark.asyncio
async def test_check_availability_returns_bool_type(fake_browser):
    """check_availability always returns a bool."""
    plugin = BestBuyPlugin(config=_make_config())
    plugin.driver = fake_browser

    result = await plugin.check_availability("https://www.bestbuy.com/site/test/1234.p")

    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_check_availability_never_raises(fake_browser):
    """check_availability catches exceptions and returns False instead of raising."""
    plugin = BestBuyPlugin(config=_make_config())
    plugin.driver = fake_browser

    fake_browser.get = AsyncMock(side_effect=RuntimeError("network error"))

    result = await plugin.check_availability("https://www.bestbuy.com/site/test/1234.p")

    assert result is False


@pytest.mark.asyncio
async def test_autobuy_returns_true_without_direct_db_write(fake_browser):
    """ASYNC-05: auto_buy must return True on success WITHOUT calling update_item_purchased.

    The orchestrator's write queue owns the sole write path (ASYNC-05). The plugin
    signals success by returning True; the orchestrator enqueues the DB write.

    Drives the full auto_buy flow with a fake tab. Verifies:
      - auto_buy returns True on a successful flow
      - update_item_purchased is NOT called (import removed; orchestrator owns writes)
    """
    item_url = "https://www.bestbuy.com/site/test/1234.p"

    plugin = BestBuyPlugin(config=_make_config())
    plugin.driver = fake_browser
    plugin._cvv = "123"  # set as main.py would after setup()

    # update_item_purchased must not be importable from the plugin module (ASYNC-05).
    assert not hasattr(_bestbuy_module, "update_item_purchased"), (
        "BestBuyPlugin module must not import update_item_purchased (ASYNC-05)"
    )

    with patch.object(plugin, "login", new=AsyncMock(return_value=None)), \
         patch.dict("os.environ", {"BB_EMAIL": "test@test.com", "BB_PASSWORD": "pw"}):

        result = await plugin.auto_buy(item_url)

    assert result is True, "auto_buy must return True after successful purchase"


# ---------------------------------------------------------------------------
# SC3: setup() reads config.platforms.bestbuy.headless (Task 3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_setup_passes_headless_true_from_config(mock_nodriver_start):
    """setup() passes headless=True when config.platforms.bestbuy.headless is True (SC3)."""
    cfg = MagicMock()
    cfg.platforms.bestbuy.headless = True
    plugin = BestBuyPlugin(config=cfg)
    await plugin.setup()
    assert mock_nodriver_start.last_kwargs.get("headless") is True


@pytest.mark.asyncio
async def test_setup_passes_headless_false_from_config(mock_nodriver_start):
    """setup() passes headless=False when config.platforms.bestbuy.headless is False (SC3)."""
    cfg = MagicMock()
    cfg.platforms.bestbuy.headless = False
    plugin = BestBuyPlugin(config=cfg)
    await plugin.setup()
    assert mock_nodriver_start.last_kwargs.get("headless") is False


@pytest.mark.asyncio
async def test_setup_with_config_none_defaults_headless_true(mock_nodriver_start):
    """setup() defaults headless=True when self.config is None (guard test, SC3)."""
    plugin = BestBuyPlugin(config=None)
    await plugin.setup()
    assert mock_nodriver_start.last_kwargs.get("headless") is True


@pytest.mark.asyncio
async def test_sc3_mixed_mode_amazon_visible_bestbuy_headless(mock_nodriver_start):
    """SC3 mixed-mode: Amazon setup() passes headless=False while BestBuy passes headless=True.

    Proves that two plugins can run with different headless states in the same process.
    Amazon's config sets headless=False (visible); BestBuy's config sets headless=True.
    Both setup() calls are captured by the same mock_nodriver_start fixture.
    """
    import importlib.util
    from pathlib import Path

    # Load the Amazon plugin in this test's context
    amazon_path = Path(__file__).parent.parent / "plugins" / "shopbot_plugin_amazon.py"
    spec = importlib.util.spec_from_file_location("shopbot_plugin_amazon_sc3", amazon_path)
    amazon_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(amazon_mod)
    AmazonPluginSC3 = amazon_mod.AmazonPlugin

    # Amazon: headless=False (visible)
    amz_cfg = MagicMock()
    amz_cfg.platforms.amazon.headless = False
    amz_plugin = AmazonPluginSC3(config=amz_cfg)
    await amz_plugin.setup()
    amz_headless = mock_nodriver_start.calls[-1].get("headless")
    assert amz_headless is False, (
        f"Amazon setup() must pass headless=False when config.platforms.amazon.headless=False, got {amz_headless}"
    )

    # BestBuy: headless=True (headless)
    bb_cfg = MagicMock()
    bb_cfg.platforms.bestbuy.headless = True
    bb_plugin = BestBuyPlugin(config=bb_cfg)
    await bb_plugin.setup()
    bb_headless = mock_nodriver_start.calls[-1].get("headless")
    assert bb_headless is True, (
        f"BestBuy setup() must pass headless=True when config.platforms.bestbuy.headless=True, got {bb_headless}"
    )

    # Verify both calls were recorded -- different headless values in same run (SC3)
    assert len(mock_nodriver_start.calls) >= 2, "Both plugins must have called nodriver.start"
