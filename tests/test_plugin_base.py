from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from core.plugin_base import RetailerPlugin, PLUGIN_API_VERSION


# ---------------------------------------------------------------------------
# Module-level concrete stub for v2 ABC (async methods, no driver parameter)
# ---------------------------------------------------------------------------


class MinimalPlugin(RetailerPlugin):
    """Minimal concrete subclass satisfying the v2 abstract contract."""

    domain_patterns = ["example.com"]

    async def check_availability(self, url: str) -> bool:
        return True

    async def auto_buy(self, url: str) -> bool:
        return False


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------


def test_version_constant():
    assert PLUGIN_API_VERSION == 2


# ---------------------------------------------------------------------------
# ABC enforcement (sync — TypeError on instantiation; no async needed)
# ---------------------------------------------------------------------------


def test_incomplete_plugin_raises():
    """A subclass that implements nothing cannot be instantiated."""
    class Incomplete(RetailerPlugin):
        pass

    with pytest.raises(TypeError):
        Incomplete(config=None)


def test_abstract_methods_enforced():
    """A subclass missing auto_buy cannot be instantiated."""
    class MissingBuy(RetailerPlugin):
        domain_patterns = ["x.com"]

        async def check_availability(self, url):
            return True

    with pytest.raises(TypeError):
        MissingBuy(config=None)


def test_minimal_plugin_instantiates():
    """A complete subclass with both abstract methods CAN be instantiated."""
    p = MinimalPlugin(config=None)
    assert isinstance(p, RetailerPlugin)


# ---------------------------------------------------------------------------
# Async no-op defaults
# ---------------------------------------------------------------------------


async def test_login_noop():
    p = MinimalPlugin(config=None)
    result = await p.login()
    assert result is None


async def test_detect_captcha_noop():
    p = MinimalPlugin(config=None)
    result = await p.detect_captcha()
    assert result is False


# ---------------------------------------------------------------------------
# __init__ contract (D-06: driver is None after construction; built in setup())
# ---------------------------------------------------------------------------


def test_init_sets_driver_none():
    p = MinimalPlugin(config=None)
    assert p.driver is None


# ---------------------------------------------------------------------------
# REG-02: registry metadata class attributes (difficulty, requires_proxy, requires_captcha)
# ---------------------------------------------------------------------------


def test_defaults():
    """MinimalPlugin inherits difficulty='medium', requires_proxy=False, requires_captcha=False."""
    p = MinimalPlugin(config=None)
    assert p.difficulty == "medium"
    assert p.requires_proxy is False
    assert p.requires_captcha is False


def test_override():
    """A subclass explicitly setting difficulty='hard' and requires_proxy=True reports those values."""
    class HardPlugin(RetailerPlugin):
        domain_patterns = ["hard.com"]
        difficulty = "hard"
        requires_proxy = True

        async def check_availability(self, url: str) -> bool:
            return True

        async def auto_buy(self, url: str) -> bool:
            return False

    p = HardPlugin(config=None)
    assert p.difficulty == "hard"
    assert p.requires_proxy is True
    assert p.requires_captcha is False  # still inherits default


def test_invalid_difficulty_raises():
    """Defining a subclass with an invalid difficulty value raises ValueError at class-definition time."""
    with pytest.raises(ValueError, match="Easy"):
        class BadPlugin(RetailerPlugin):
            domain_patterns = ["bad.com"]
            difficulty = "Easy"  # wrong case -- must fail at class-definition time

            async def check_availability(self, url: str) -> bool:
                return True

            async def auto_buy(self, url: str) -> bool:
                return False


def test_existing_plugins_load():
    """All existing shopbot_plugin_*.py files load unchanged with valid defaults (REG-02)."""
    from core.registry import _discover_plugins

    plugins_dir = Path(__file__).parent.parent / "plugins"
    plugin_classes = _discover_plugins(plugins_dir)
    assert len(plugin_classes) >= 7, (
        f"Expected >= 7 plugin classes, found {len(plugin_classes)}"
    )
    _valid = {"easy", "medium", "hard"}
    for cls in plugin_classes:
        instance = cls(config=None)
        assert instance.difficulty in _valid, (
            f"{cls.__name__}.difficulty={instance.difficulty!r} is not a valid value"
        )
        assert isinstance(instance.requires_proxy, bool), (
            f"{cls.__name__}.requires_proxy is not a bool"
        )
        assert isinstance(instance.requires_captcha, bool), (
            f"{cls.__name__}.requires_captcha is not a bool"
        )


# ---------------------------------------------------------------------------
# AB-03: requires_captcha=True + difficulty='easy' override permutation
# ---------------------------------------------------------------------------


def test_requires_captcha_and_easy_difficulty_overrides():
    """A subclass may override requires_captcha=True and difficulty='easy'; both values
    stick and __init_subclass__ accepts the valid difficulty without raising."""

    class EasyCaptchaPlugin(RetailerPlugin):
        domain_patterns = ["ex.com"]
        difficulty = "easy"
        requires_captcha = True

        async def check_availability(self, url: str) -> bool:
            return True

        async def auto_buy(self, url: str) -> bool:
            return False

    # Override permutation assertions (plugin_base.py:22-24 + __init_subclass__ validation)
    assert EasyCaptchaPlugin.requires_captcha is True
    assert EasyCaptchaPlugin.difficulty == "easy"
    # requires_proxy is not overridden; must still inherit the False default
    assert EasyCaptchaPlugin.requires_proxy is False


# ---------------------------------------------------------------------------
# AB-04: _handle_ban ban→proxy-cooldown bridge (plugin_base.py:43-55, branch 53→55)
# ---------------------------------------------------------------------------


def test_handle_ban_records_failure_on_proxy_when_banned():
    """_handle_ban covers the three sub-cases on branch 53->55:
    (1) ban phrase + proxy/pool present -> pool.record_failure(proxy) called once, returns True
    (2) benign text -> returns False, record_failure not called (early return at line 49-50)
    (3) no _proxy/_pool attributes -> returns True, no exception (if-guard short-circuits)
    """
    # --- Sub-case 1: ban path WITH proxy ---
    plugin = MinimalPlugin(config=None)
    proxy_sentinel = object()
    mock_pool = MagicMock()
    plugin._proxy = proxy_sentinel
    plugin._pool = mock_pool

    result = plugin._handle_ban("Access Denied - bot detected")

    assert result is True
    mock_pool.record_failure.assert_called_once_with(proxy_sentinel)

    # --- Sub-case 2: benign path (same plugin instance; record_failure call count must not grow) ---
    call_count_before = mock_pool.record_failure.call_count
    benign_result = plugin._handle_ban("normal page content")
    assert benign_result is False
    assert mock_pool.record_failure.call_count == call_count_before  # no new call

    # --- Sub-case 3: no _proxy/_pool configured (fresh instance, no attributes set) ---
    fresh_plugin = MinimalPlugin(config=None)
    # Verify the attributes are truly absent (not just falsy)
    assert not hasattr(fresh_plugin, "_proxy")
    assert not hasattr(fresh_plugin, "_pool")

    no_proxy_result = fresh_plugin._handle_ban("access denied")
    assert no_proxy_result is True  # ban detected; safe no-op on missing proxy (branch 53->55)


# ---------------------------------------------------------------------------
# BUY-02: place_order_guarded -- suppression and allow-through gates
# ---------------------------------------------------------------------------


async def test_place_order_guarded_suppressed_test_mode():
    """place_order_guarded returns False + does not call click_fn when test_mode=True."""
    cfg = MagicMock()
    cfg.debug.test_mode = True
    cfg.debug.monitor_only = False
    plugin = MinimalPlugin(config=cfg)
    click_fn = AsyncMock()

    result = await plugin.place_order_guarded(click_fn)

    assert result is False
    click_fn.assert_not_called()


async def test_place_order_guarded_suppressed_monitor_only():
    """place_order_guarded returns False + does not call click_fn when monitor_only=True."""
    cfg = MagicMock()
    cfg.debug.test_mode = False
    cfg.debug.monitor_only = True
    plugin = MinimalPlugin(config=cfg)
    click_fn = AsyncMock()

    result = await plugin.place_order_guarded(click_fn)

    assert result is False
    click_fn.assert_not_called()


async def test_place_order_guarded_allows_click():
    """place_order_guarded awaits click_fn and returns True when both flags are False."""
    cfg = MagicMock()
    cfg.debug.test_mode = False
    cfg.debug.monitor_only = False
    plugin = MinimalPlugin(config=cfg)
    click_fn = AsyncMock()

    result = await plugin.place_order_guarded(click_fn)

    assert result is True
    click_fn.assert_awaited_once()


async def test_place_order_guarded_suppressed_when_config_none():
    """CR-01: place_order_guarded suppresses when config is None (fail-safe default)."""
    plugin = MinimalPlugin(config=None)
    click_fn = AsyncMock()

    result = await plugin.place_order_guarded(click_fn)

    assert result is False
    click_fn.assert_not_called()


async def test_place_order_guarded_suppressed_when_debug_absent():
    """CR-01: place_order_guarded suppresses when debug attribute is missing from config.

    A legacy config object or partial mock that lacks a debug attribute should
    fail-safe to suppression rather than accidentally allowing an order.
    """
    cfg = object()  # plain object -- no debug attribute
    plugin = MinimalPlugin(config=cfg)
    click_fn = AsyncMock()

    result = await plugin.place_order_guarded(click_fn)

    assert result is False
    click_fn.assert_not_called()


# ---------------------------------------------------------------------------
# BUY-03: get_active_tab() -- additive concrete hook on RetailerPlugin ABC
# ---------------------------------------------------------------------------


def test_get_active_tab_default_returns_main_tab():
    """get_active_tab() returns driver.main_tab when driver has that attribute."""
    p = MinimalPlugin(config=None)
    fake_tab = object()
    fake_driver = MagicMock()
    fake_driver.main_tab = fake_tab
    p.driver = fake_driver

    result = p.get_active_tab()

    assert result is fake_tab


def test_get_active_tab_none_driver():
    """get_active_tab() returns None when self.driver is None (no AttributeError)."""
    p = MinimalPlugin(config=None)
    assert p.driver is None

    result = p.get_active_tab()

    assert result is None


def test_plugin_api_version_stays_2_after_get_active_tab():
    """PLUGIN_API_VERSION must remain 2 after adding get_active_tab (additive BUY-03)."""
    assert PLUGIN_API_VERSION == 2


# ---------------------------------------------------------------------------
# BUY-06: _checkout_stage default on RetailerPlugin ABC
# ---------------------------------------------------------------------------


def test_checkout_stage_default_empty_string():
    """RetailerPlugin.__init__ must set _checkout_stage to '' (BUY-06 -- always readable on timeout)."""
    p = MinimalPlugin(config=None)
    assert hasattr(p, "_checkout_stage"), "RetailerPlugin must expose _checkout_stage after construction"
    assert p._checkout_stage == "", f"_checkout_stage must default to '' got {p._checkout_stage!r}"


def test_checkout_stage_default_no_attribute_error_on_read():
    """Reading _checkout_stage before auto_buy must never raise AttributeError (Pitfall 5)."""
    p = MinimalPlugin(config=None)
    try:
        _ = p._checkout_stage
    except AttributeError as exc:
        pytest.fail(f"AttributeError reading _checkout_stage on fresh instance: {exc}")


def test_checkout_stage_is_str_type():
    """_checkout_stage must be a str (not None or any other type) on a fresh instance."""
    p = MinimalPlugin(config=None)
    assert isinstance(p._checkout_stage, str), (
        f"_checkout_stage must be str, got {type(p._checkout_stage)}"
    )


def test_api_version_unchanged_after_checkout_stage():
    """PLUGIN_API_VERSION must remain 2 after adding _checkout_stage (BUY-06 additive default)."""
    assert PLUGIN_API_VERSION == 2
