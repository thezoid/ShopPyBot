"""Tests for plugins/shopbot_plugin_bestbuy.py (PLG-02, PLG-03).

Loads the plugin via importlib.util.spec_from_file_location to mirror how the
registry discovers plugins -- no sys.path manipulation required.

Key test: test_autobuy_calls_update_purchased asserts the PLG-02 fix is present --
update_item_purchased must be called once with the item url after a successful buy.
"""

import asyncio
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


def _make_config(items=None, test_mode=True, monitor_only=False):
    cfg = MagicMock()
    cfg.available.items = items or []
    cfg.debug.test_mode = test_mode
    cfg.debug.monitor_only = monitor_only
    cfg.checkout.step_timeout_secs = 30  # BUY-06: required for asyncio.timeout in auto_buy
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

    # Patch detect_captcha to skip the CAPTCHA branch (no CAPTCHA on normal pages).
    with patch.object(plugin, "detect_captcha", new=AsyncMock(return_value=False)):
        result = await plugin.check_availability("https://www.bestbuy.com/site/test/1234.p")

    assert result is True


@pytest.mark.asyncio
async def test_check_availability_returns_false_when_no_button(fake_browser):
    """check_availability returns False when add-to-cart button is absent."""
    plugin = BestBuyPlugin(config=_make_config())
    plugin.driver = fake_browser

    fake_browser.get.return_value.select = AsyncMock(return_value=None)

    with patch.object(plugin, "detect_captcha", new=AsyncMock(return_value=False)):
        result = await plugin.check_availability("https://www.bestbuy.com/site/test/1234.p")

    assert result is False


@pytest.mark.asyncio
async def test_check_availability_returns_bool_type(fake_browser):
    """check_availability always returns a bool."""
    plugin = BestBuyPlugin(config=_make_config())
    plugin.driver = fake_browser

    with patch.object(plugin, "detect_captcha", new=AsyncMock(return_value=False)):
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

    # Use test_mode=False, monitor_only=False so place_order_guarded allows the click
    # (simulating a live-mode run that should return True on success).
    plugin = BestBuyPlugin(config=_make_config(test_mode=False, monitor_only=False))
    plugin.driver = fake_browser
    plugin._cvv = "123"  # set as main.py would after setup()

    # BUY-07: provide a complete checkout profile so the form-fill guard passes.
    # Without this, auto_buy returns False before place_order_guarded (expected behavior).
    from core.checkout_profile import CheckoutProfile
    plugin._checkout_profile = CheckoutProfile(
        first_name="Jane", last_name="Doe",
        address_line1="123 Main St", city="Springfield",
        state="IL", zip_code="62701", country="US", phone="5551234567",
    )

    # update_item_purchased must not be importable from the plugin module (ASYNC-05).
    assert not hasattr(_bestbuy_module, "update_item_purchased"), (
        "BestBuyPlugin module must not import update_item_purchased (ASYNC-05)"
    )

    with patch.object(plugin, "login", new=AsyncMock(return_value=None)), \
         patch.dict("os.environ", {"BB_EMAIL": "test@test.com", "BB_PASSWORD": "pw"}):

        result = await plugin.auto_buy(item_url)

    assert result is True, "auto_buy must return True after successful purchase"


# ---------------------------------------------------------------------------
# CR-02 regression: ban page triggers record_failure on proxy pool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_availability_ban_page_triggers_record_failure(fake_browser):
    """CR-02 regression: a ban-phrase body causes check_availability to return False
    and call pool.record_failure(proxy) so the proxy rotates away.

    Pre-fix, BestBuy had no ban scan and silently returned False without
    rotating the proxy; a banned proxy would be used indefinitely.
    """
    from unittest.mock import MagicMock

    plugin = BestBuyPlugin(config=_make_config())
    plugin.driver = fake_browser

    # Attach a mock proxy and pool so record_failure can be asserted.
    mock_proxy = MagicMock()
    mock_pool = MagicMock()
    plugin._proxy = mock_proxy
    plugin._pool = mock_pool

    # Fake tab returns a ban-phrase body; ban scan fires before CAPTCHA detection.
    fake_browser.get.return_value.evaluate = AsyncMock(return_value="Access Denied")

    with patch.object(plugin, "detect_captcha", new=AsyncMock(return_value=False)):
        result = await plugin.check_availability("https://www.bestbuy.com/site/test/9999.p")

    assert result is False, "Ban page must return False"
    mock_pool.record_failure.assert_called_once_with(mock_proxy)


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


# ---------------------------------------------------------------------------
# BUY-06: per-step asyncio.timeout + _checkout_stage tracking (Plan 21-03)
# ---------------------------------------------------------------------------


def test_bestbuy_auto_buy_has_eight_timeout_blocks():
    """BestBuy auto_buy must contain exactly 8 asyncio.timeout(step_timeout_secs) blocks (BUY-06)."""
    import ast

    source = _PLUGIN_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(_PLUGIN_PATH))

    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncWith):
            for item in node.items:
                ctx = item.context_expr
                if isinstance(ctx, ast.Call):
                    func = ctx.func
                    func_name = ""
                    if isinstance(func, ast.Name):
                        func_name = func.id
                    elif isinstance(func, ast.Attribute):
                        func_name = func.attr
                    if func_name == "timeout" and ctx.args:
                        arg_src = ast.unparse(ctx.args[0])
                        if "step_timeout_secs" in arg_src:
                            count += 1

    assert count == 8, (
        f"BestBuy auto_buy must have exactly 8 asyncio.timeout(step_timeout_secs) blocks, found {count}"
    )


@pytest.mark.asyncio
async def test_bestbuy_auto_buy_returns_false_on_step_timeout(fake_browser):
    """BUY-06: when a DOM stage exceeds step_timeout_secs, auto_buy returns False.

    Simulates a hung navigate stage by making driver.get raise asyncio.TimeoutError.
    """
    cfg = MagicMock()
    cfg.debug.test_mode = False
    cfg.debug.monitor_only = False
    cfg.checkout.step_timeout_secs = 30
    cfg.available.items = []

    plugin = BestBuyPlugin(config=cfg)
    plugin.driver = fake_browser

    fake_browser.get = AsyncMock(side_effect=asyncio.TimeoutError())

    with patch.object(plugin, "login", new=AsyncMock(return_value=None)):
        result = await plugin.auto_buy("https://www.bestbuy.com/site/test/1234.p")

    assert result is False, "auto_buy must return False when a step timeout fires"


@pytest.mark.asyncio
async def test_bestbuy_auto_buy_logs_stage_name_on_timeout(fake_browser):
    """BUY-06: the error log on step timeout must include the stage name and exc class name.

    Verifies _checkout_stage is readable on timeout and exc.__class__.__name__ is used
    (not str(exc) -- T-21-07).
    """
    import asyncio as _asyncio

    cfg = MagicMock()
    cfg.debug.test_mode = False
    cfg.debug.monitor_only = False
    cfg.checkout.step_timeout_secs = 30
    cfg.available.items = []

    plugin = BestBuyPlugin(config=cfg)
    plugin.driver = fake_browser

    fake_browser.get = AsyncMock(side_effect=_asyncio.TimeoutError())

    log_calls: list[tuple] = []

    def _capture_log(msg, level):
        log_calls.append((msg, level))

    with patch.object(plugin, "login", new=AsyncMock(return_value=None)), \
         patch.object(_bestbuy_module, "writeLog", _capture_log):
        await plugin.auto_buy("https://www.bestbuy.com/site/test/1234.p")

    error_logs = [msg for msg, lvl in log_calls if lvl == "ERROR"]
    assert any("navigate" in m for m in error_logs), (
        f"Error log must contain stage name 'navigate'; got: {error_logs}"
    )
    assert any("TimeoutError" in m for m in error_logs), (
        f"Error log must contain exc.__class__.__name__ 'TimeoutError'; got: {error_logs}"
    )


def test_bestbuy_checkout_stage_default_is_empty_string():
    """_checkout_stage must default to '' on BestBuyPlugin (inherits from RetailerPlugin base)."""
    plugin = BestBuyPlugin(config=None)
    assert plugin._checkout_stage == "", (
        f"_checkout_stage must default to '' on BestBuyPlugin, got {plugin._checkout_stage!r}"
    )
