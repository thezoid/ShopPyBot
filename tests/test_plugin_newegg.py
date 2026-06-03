"""Tests for plugins/shopbot_plugin_newegg.py (PLG-08, ANTI-02, ANTI-03).

Loads the plugin via importlib.util.spec_from_file_location to mirror how the
registry discovers plugins -- no sys.path manipulation required.

Tests cover:
  - NeweggPlugin satisfies RetailerPlugin ABC
  - domain_patterns includes "newegg.com" and "newegg.ca"
  - platform_key == "newegg" (matches config attribute)
  - setup() passes headless=True/False to nodriver.start (ANTI-03)
  - setup() passes --user-agent=<ua> in browser_args when user_agents non-empty (ANTI-02)
  - setup() passes --user-agent= even when user_agents is empty (falls back to DEFAULT_USER_AGENTS)
  - Plugin module docstring declares MEDIUM risk (PLG-08)
  - No update_item_purchased in plugin source (ASYNC-05)
  - TODO selector markers are present
"""

import importlib.util
import inspect
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Module loading (mirrors registry discovery pattern)
# ---------------------------------------------------------------------------

_PLUGIN_PATH = Path(__file__).parent.parent / "plugins" / "shopbot_plugin_newegg.py"


def _load_newegg_module():
    spec = importlib.util.spec_from_file_location("shopbot_plugin_newegg", _PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_newegg_module = _load_newegg_module()
NeweggPlugin = _newegg_module.NeweggPlugin

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

from core.plugin_base import RetailerPlugin  # noqa: E402


def _make_config(headless=True, user_agents=None):
    """Return a minimal config-like object suitable for NeweggPlugin."""
    cfg = MagicMock()
    cfg.platforms.newegg.headless = headless
    cfg.platforms.newegg.user_agents = user_agents if user_agents is not None else []
    cfg.available.items = []
    return cfg


# ---------------------------------------------------------------------------
# ABC + structural tests (sync)
# ---------------------------------------------------------------------------


def test_newegg_satisfies_abc():
    """NeweggPlugin must be a concrete subclass of RetailerPlugin (PLG-08)."""
    assert issubclass(NeweggPlugin, RetailerPlugin)
    plugin = NeweggPlugin(config=None)
    assert plugin is not None


def test_domain_patterns_includes_newegg_com():
    """domain_patterns must contain 'newegg.com'."""
    assert "newegg.com" in NeweggPlugin.domain_patterns


def test_domain_patterns_includes_newegg_ca():
    """domain_patterns must contain 'newegg.ca' for Canadian store coverage."""
    assert "newegg.ca" in NeweggPlugin.domain_patterns


def test_platform_key_is_newegg():
    """platform_key must be 'newegg' to match config.platforms.newegg (ANTI-01 jitter)."""
    assert NeweggPlugin.platform_key == "newegg"


def test_no_global_driver():
    """PLG-03: no module-level 'driver'; instance.driver is None before setup()."""
    assert not hasattr(_newegg_module, "driver"), (
        "Module must not define a top-level 'driver' variable"
    )
    plugin = NeweggPlugin(config=None)
    assert plugin.driver is None

    source = _PLUGIN_PATH.read_text()
    assert "self.driver = await nodriver.start" in source, (
        "Plugin must build self.driver via nodriver.start() in setup()"
    )


def test_risk_docstring_declares_medium():
    """Module docstring must declare MEDIUM risk level (PLG-08)."""
    doc = inspect.getdoc(_newegg_module)
    assert doc is not None, "Plugin module must have a docstring"
    assert "MEDIUM" in doc, (
        f"Module docstring must contain 'MEDIUM' risk level. Got:\n{doc}"
    )


def test_no_update_item_purchased_in_source():
    """ASYNC-05: plugin must NOT import or call update_item_purchased."""
    assert not hasattr(_newegg_module, "update_item_purchased"), (
        "NeweggPlugin module must not import update_item_purchased (ASYNC-05)"
    )
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
        "NeweggPlugin must not call update_item_purchased -- found non-comment usage:\n"
        + "\n".join(f"  line {ln}: {txt}" for ln, txt in violations)
    )


def test_todo_selector_markers_present():
    """check_availability must carry TODO markers for unverified selectors."""
    source = _PLUGIN_PATH.read_text()
    assert "# TODO: verify selectors against live" in source


# ---------------------------------------------------------------------------
# Async tests (ANTI-02: UA rotation, ANTI-03: headless)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_setup_passes_headless_true(mock_nodriver_start):
    """setup() passes headless=True when config.platforms.newegg.headless is True (ANTI-03)."""
    plugin = NeweggPlugin(config=_make_config(headless=True))
    await plugin.setup()
    assert mock_nodriver_start.last_kwargs.get("headless") is True


@pytest.mark.asyncio
async def test_setup_passes_headless_false(mock_nodriver_start):
    """setup() passes headless=False when config.platforms.newegg.headless is False (ANTI-03)."""
    plugin = NeweggPlugin(config=_make_config(headless=False))
    await plugin.setup()
    assert mock_nodriver_start.last_kwargs.get("headless") is False


@pytest.mark.asyncio
async def test_setup_ua_rotation_with_platform_agents(mock_nodriver_start):
    """setup() passes --user-agent= in browser_args when platform user_agents non-empty (ANTI-02)."""
    uas = ["Mozilla/5.0 TestAgent/1.0"]
    plugin = NeweggPlugin(config=_make_config(user_agents=uas))
    await plugin.setup()
    browser_args = mock_nodriver_start.last_kwargs.get("browser_args")
    assert browser_args is not None, "browser_args must be set when user_agents is non-empty"
    assert any("--user-agent=" in arg for arg in browser_args), (
        f"browser_args must contain '--user-agent=...', got: {browser_args}"
    )


@pytest.mark.asyncio
async def test_setup_ua_rotation_falls_back_to_default(mock_nodriver_start):
    """setup() still passes --user-agent= from DEFAULT_USER_AGENTS when platform list is empty."""
    plugin = NeweggPlugin(config=_make_config(user_agents=[]))
    await plugin.setup()
    browser_args = mock_nodriver_start.last_kwargs.get("browser_args")
    assert browser_args is not None, "browser_args must be set even when user_agents is empty (fallback to DEFAULT_USER_AGENTS)"
    assert any("--user-agent=" in arg for arg in browser_args), (
        f"browser_args must contain '--user-agent=...' from default pool, got: {browser_args}"
    )


@pytest.mark.asyncio
async def test_setup_with_config_none_defaults_headless_true(mock_nodriver_start):
    """setup() defaults headless=True when self.config is None (guard test)."""
    plugin = NeweggPlugin(config=None)
    await plugin.setup()
    assert mock_nodriver_start.last_kwargs.get("headless") is True


@pytest.mark.asyncio
async def test_check_availability_returns_bool(fake_browser):
    """check_availability always returns a bool, never raises."""
    plugin = NeweggPlugin(config=_make_config())
    plugin.driver = fake_browser
    result = await plugin.check_availability("https://www.newegg.com/p/1234")
    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_check_availability_never_raises(fake_browser):
    """check_availability catches exceptions and returns False instead of raising."""
    plugin = NeweggPlugin(config=_make_config())
    plugin.driver = fake_browser
    fake_browser.get = AsyncMock(side_effect=RuntimeError("network error"))
    result = await plugin.check_availability("https://www.newegg.com/p/1234")
    assert result is False
