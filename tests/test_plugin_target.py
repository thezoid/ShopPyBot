"""Tests for plugins/shopbot_plugin_target.py (PLG-05, ANTI-02, ANTI-03, SC4).

Loads the plugin via importlib.util.spec_from_file_location to mirror how the
registry discovers plugins -- no sys.path manipulation required.

Tests cover:
  - TargetPlugin satisfies RetailerPlugin ABC
  - domain_patterns includes "target.com"
  - platform_key == "target"
  - setup() passes headless=True/False to nodriver.start (ANTI-03)
  - setup() passes --user-agent=<ua> in browser_args when user_agents non-empty (ANTI-02)
  - Plugin module docstring contains "Akamai" and "headless" (SC4)
  - No update_item_purchased in plugin source (ASYNC-05)
"""

import importlib.util
import inspect
from pathlib import Path
from unittest.mock import ANY, AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Module loading (mirrors registry discovery pattern)
# ---------------------------------------------------------------------------

_PLUGIN_PATH = Path(__file__).parent.parent / "plugins" / "shopbot_plugin_target.py"


def _load_target_module():
    spec = importlib.util.spec_from_file_location("shopbot_plugin_target", _PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_target_module = _load_target_module()
TargetPlugin = _target_module.TargetPlugin

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

from core.plugin_base import RetailerPlugin  # noqa: E402


def _make_config(headless=True, user_agents=None):
    """Return a minimal config-like object suitable for TargetPlugin."""
    cfg = MagicMock()
    cfg.platforms.target.headless = headless
    cfg.platforms.target.user_agents = user_agents if user_agents is not None else []
    cfg.available.items = []
    return cfg


# ---------------------------------------------------------------------------
# ABC + structural tests (sync)
# ---------------------------------------------------------------------------


def test_target_satisfies_abc():
    """TargetPlugin must be a concrete subclass of RetailerPlugin (PLG-05)."""
    assert issubclass(TargetPlugin, RetailerPlugin)
    plugin = TargetPlugin(config=None)
    assert plugin is not None


def test_domain_patterns_includes_target():
    """domain_patterns must contain target.com."""
    assert "target.com" in TargetPlugin.domain_patterns


def test_platform_key_is_target():
    """platform_key must be 'target' to match config.platforms.target (ANTI-01 jitter)."""
    assert TargetPlugin.platform_key == "target"


def test_no_global_driver():
    """PLG-03: no module-level 'driver'; instance.driver is None before setup()."""
    assert not hasattr(_target_module, "driver"), (
        "Module must not define a top-level 'driver' variable"
    )
    plugin = TargetPlugin(config=None)
    assert plugin.driver is None

    source = _PLUGIN_PATH.read_text()
    assert "self.driver = await nodriver.start" in source, (
        "Plugin must build self.driver via nodriver.start() in setup()"
    )


def test_risk_docstring_contains_akamai():
    """Module docstring must contain 'Akamai' (SC4)."""
    doc = inspect.getdoc(_target_module)
    assert doc is not None, "Plugin module must have a docstring"
    assert "Akamai" in doc, (
        f"Module docstring must contain 'Akamai' (SC4). Got:\n{doc}"
    )


def test_risk_docstring_contains_headless():
    """Module docstring must contain 'headless' (SC4 -- Target blocks headless via Akamai)."""
    doc = inspect.getdoc(_target_module)
    assert doc is not None, "Plugin module must have a docstring"
    assert "headless" in doc, (
        f"Module docstring must contain 'headless' (SC4). Got:\n{doc}"
    )


def test_no_update_item_purchased_in_source():
    """ASYNC-05: plugin must NOT import or call update_item_purchased (ASYNC-05)."""
    # Check the module does not import update_item_purchased at the module level.
    assert not hasattr(_target_module, "update_item_purchased"), (
        "TargetPlugin module must not import update_item_purchased (ASYNC-05)"
    )
    # Also verify no non-comment source lines call it.
    source_lines = _PLUGIN_PATH.read_text().splitlines()
    violations = [
        (i + 1, line)
        for i, line in enumerate(source_lines)
        if "update_item_purchased" in line
        and not line.lstrip().startswith("#")
        and "ASYNC-05" not in line
        and "write queue" not in line
    ]
    assert not violations, (
        "TargetPlugin must not call update_item_purchased -- found non-comment usage:\n"
        + "\n".join(f"  line {ln}: {txt}" for ln, txt in violations)
    )


def test_todo_selector_markers_present():
    """check_availability must carry TODO markers for unverified selectors."""
    source = _PLUGIN_PATH.read_text()
    assert "# TODO: verify selectors against live" in source


def test_auto_buy_experimental_warning_in_source():
    """auto_buy must log an 'experimental' WARNING (Target checkout is experimental)."""
    source = _PLUGIN_PATH.read_text()
    assert "experimental" in source, (
        "TargetPlugin auto_buy must log an experimental WARNING (Akamai blocks checkout)"
    )


# ---------------------------------------------------------------------------
# Async tests (ANTI-02: UA rotation, ANTI-03: headless)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_setup_passes_headless_true(mock_nodriver_start):
    """setup() passes headless=True when config.platforms.target.headless is True (ANTI-03)."""
    plugin = TargetPlugin(config=_make_config(headless=True))
    await plugin.setup()
    assert mock_nodriver_start.last_kwargs.get("headless") is True


@pytest.mark.asyncio
async def test_setup_passes_headless_false(mock_nodriver_start):
    """setup() passes headless=False when config.platforms.target.headless is False (ANTI-03)."""
    plugin = TargetPlugin(config=_make_config(headless=False))
    await plugin.setup()
    assert mock_nodriver_start.last_kwargs.get("headless") is False


@pytest.mark.asyncio
async def test_setup_ua_rotation_with_platform_agents(mock_nodriver_start):
    """setup() passes --user-agent= in browser_args when platform user_agents non-empty (ANTI-02)."""
    uas = ["Mozilla/5.0 TestAgent/2.0"]
    plugin = TargetPlugin(config=_make_config(user_agents=uas))
    await plugin.setup()
    browser_args = mock_nodriver_start.last_kwargs.get("browser_args")
    assert browser_args is not None, "browser_args must be set when user_agents is non-empty"
    assert any("--user-agent=" in arg for arg in browser_args), (
        f"browser_args must contain '--user-agent=...', got: {browser_args}"
    )


@pytest.mark.asyncio
async def test_setup_with_config_none_defaults_headless_true(mock_nodriver_start):
    """setup() defaults headless=True when self.config is None (guard test)."""
    plugin = TargetPlugin(config=None)
    await plugin.setup()
    assert mock_nodriver_start.last_kwargs.get("headless") is True


@pytest.mark.asyncio
async def test_check_availability_returns_bool(fake_browser):
    """check_availability always returns a bool, never raises."""
    plugin = TargetPlugin(config=_make_config())
    plugin.driver = fake_browser
    result = await plugin.check_availability("https://www.target.com/p/test/-/A-12345")
    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_check_availability_never_raises(fake_browser):
    """check_availability catches exceptions and returns False instead of raising."""
    plugin = TargetPlugin(config=_make_config())
    plugin.driver = fake_browser
    fake_browser.get = AsyncMock(side_effect=RuntimeError("network error"))
    result = await plugin.check_availability("https://www.target.com/p/test/-/A-12345")
    assert result is False


# ---------------------------------------------------------------------------
# Login + auto_buy tests (BF-03: login() -> bool via _verify_login_generic; D-11/D-12/D-13)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_returns_false_missing_credentials(monkeypatch, fake_browser):
    """login() returns False when TARGET_EMAIL/TARGET_PASSWORD are unset (D-14)."""
    plugin = TargetPlugin(config=_make_config())
    plugin.driver = fake_browser
    fake_store = MagicMock()
    fake_store.get.return_value = None
    monkeypatch.setattr(_target_module, "get_store", lambda: fake_store)
    result = await plugin.login()
    assert result is False


@pytest.mark.asyncio
async def test_login_returns_false_on_exception(monkeypatch, fake_browser):
    """login() returns False (never raises) on any exception during sign-in (D-13)."""
    plugin = TargetPlugin(config=_make_config())
    plugin.driver = fake_browser
    fake_store = MagicMock()
    fake_store.get.side_effect = lambda key: "creds" if "EMAIL" in key or "PASSWORD" in key else None
    monkeypatch.setattr(_target_module, "get_store", lambda: fake_store)
    fake_browser.get = AsyncMock(side_effect=RuntimeError("network error"))
    result = await plugin.login()
    assert result is False


@pytest.mark.asyncio
async def test_login_returns_true_when_verified(monkeypatch, fake_browser):
    """login() returns True only after _verify_login_generic confirms (D-12)."""
    plugin = TargetPlugin(config=_make_config())
    plugin.driver = fake_browser
    fake_store = MagicMock()
    fake_store.get.side_effect = lambda key: "creds" if "EMAIL" in key or "PASSWORD" in key else None
    monkeypatch.setattr(_target_module, "get_store", lambda: fake_store)
    plugin._verify_login_generic = AsyncMock(return_value=True)
    result = await plugin.login()
    assert result is True
    plugin._verify_login_generic.assert_awaited_once_with(
        ANY, "/account/signin", '[data-test="accountNav-signIn"] input[type="email"]'
    )


@pytest.mark.asyncio
async def test_login_returns_false_when_verification_fails(monkeypatch, fake_browser):
    """login() returns False when _verify_login_generic cannot confirm success (D-13)."""
    plugin = TargetPlugin(config=_make_config())
    plugin.driver = fake_browser
    fake_store = MagicMock()
    fake_store.get.side_effect = lambda key: "creds" if "EMAIL" in key or "PASSWORD" in key else None
    monkeypatch.setattr(_target_module, "get_store", lambda: fake_store)
    plugin._verify_login_generic = AsyncMock(return_value=False)
    result = await plugin.login()
    assert result is False


@pytest.mark.asyncio
async def test_auto_buy_sets_checkout_stage_login_before_login_call(fake_browser):
    """auto_buy sets _checkout_stage='login' immediately before calling login()."""
    plugin = TargetPlugin(config=_make_config())
    plugin.driver = fake_browser
    plugin.place_order_guarded = AsyncMock(return_value=True)
    stage_at_login_call = {}

    async def _fake_login():
        stage_at_login_call["stage"] = plugin._checkout_stage
        return True

    plugin.login = _fake_login
    result = await plugin.auto_buy("https://www.target.com/p/test/-/A-12345")
    assert stage_at_login_call.get("stage") == "login"
    assert result is True


@pytest.mark.asyncio
async def test_auto_buy_aborts_on_failed_login(fake_browser):
    """auto_buy returns False and never reaches place-order when login() returns False (D-15)."""
    plugin = TargetPlugin(config=_make_config())
    plugin.driver = fake_browser
    plugin.login = AsyncMock(return_value=False)
    plugin.place_order_guarded = AsyncMock(return_value=True)
    result = await plugin.auto_buy("https://www.target.com/p/test/-/A-12345")
    assert result is False
    plugin.place_order_guarded.assert_not_awaited()
