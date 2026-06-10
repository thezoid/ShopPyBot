"""Tests for core/registry.py.

Covers CORE-03 (importlib discovery, warn+ignore, import-failure isolation)
and CORE-04 (hostname routing) plus the D-09 lazy setup/teardown lifecycle.
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from core.plugin_base import RetailerPlugin
from core.registry import PluginRegistry


# ---------------------------------------------------------------------------
# CORE-03: Discovery
# ---------------------------------------------------------------------------


def test_discovers_valid_plugin(tmp_plugins_dir):
    """A single shopbot_plugin_*.py file produces exactly one plugin instance."""
    registry = PluginRegistry(config=None, plugins_dir=tmp_plugins_dir)
    assert len(registry._all_plugins) == 1


def test_non_matching_py_warns(tmp_path):
    """A helper.py (no shopbot_plugin_ prefix) triggers a WARNING and is not loaded."""
    (tmp_path / "helper.py").write_text("# not a plugin\n")

    warnings_emitted: list[str] = []

    def fake_write_log(message: str, level: str, *args, **kwargs):
        if level == "WARNING":
            warnings_emitted.append(message)

    with patch("core.registry.writeLog", side_effect=fake_write_log):
        registry = PluginRegistry(config=None, plugins_dir=tmp_path)

    assert any("does not match shopbot_plugin_*.py" in msg for msg in warnings_emitted)
    assert len(registry._all_plugins) == 0


def test_import_failure_skips(tmp_path):
    """A shopbot_plugin_*.py that raises at import is logged and does not crash registry."""
    broken = tmp_path / "shopbot_plugin_broken.py"
    broken.write_text('raise RuntimeError("boom")\n')

    warnings_emitted: list[str] = []

    def fake_write_log(message: str, level: str, *args, **kwargs):
        if level == "WARNING":
            warnings_emitted.append(message)

    # Construction must not raise even though the plugin errors on import.
    with patch("core.registry.writeLog", side_effect=fake_write_log):
        registry = PluginRegistry(config=None, plugins_dir=tmp_path)

    assert len(registry._all_plugins) == 0
    assert any("Failed to import" in msg for msg in warnings_emitted)


# ---------------------------------------------------------------------------
# CORE-04: Routing
# ---------------------------------------------------------------------------


def test_route_by_domain(tmp_plugins_dir):
    """route() returns the matching plugin for a known host; None for unknown."""
    registry = PluginRegistry(config=None, plugins_dir=tmp_plugins_dir)
    # Simulate that setup_for_items has already activated all discovered plugins.
    registry._active_plugins = registry._all_plugins[:]

    matched = registry.route("https://www.fake.com/product/123")
    assert matched is not None
    assert "fake.com" in matched.domain_patterns

    no_match = registry.route("https://www.other.com/x")
    assert no_match is None


# ---------------------------------------------------------------------------
# D-09: Lazy setup/teardown lifecycle
# ---------------------------------------------------------------------------


async def test_setup_only_matched(tmp_plugins_dir, tmp_path):
    """setup_for_items awaits setup() only for plugins with a matching item link."""
    # Add a second plugin for a different domain to confirm it is NOT set up.
    other_code = (
        "from core.plugin_base import RetailerPlugin\n"
        "\n"
        "\n"
        "class OtherPlugin(RetailerPlugin):\n"
        "    domain_patterns = ['other.com']\n"
        "\n"
        "    async def check_availability(self, url):\n"
        "        return False\n"
        "\n"
        "    async def auto_buy(self, url):\n"
        "        return False\n"
    )
    (tmp_plugins_dir / "shopbot_plugin_other.py").write_text(other_code)

    registry = PluginRegistry(config=None, plugins_dir=tmp_plugins_dir)
    assert len(registry._all_plugins) == 2

    # Replace setup on each plugin instance with an AsyncMock.
    for plugin in registry._all_plugins:
        plugin.setup = AsyncMock()

    # Items list: only the fake.com link; other.com has no items.
    items = [("Fake Item", "https://www.fake.com/product/1", True, 1, False)]

    await registry.setup_for_items(items)

    # Only the fake.com plugin should have been set up.
    assert len(registry._active_plugins) == 1

    fake_plugin = next(
        p for p in registry._all_plugins if "fake.com" in p.domain_patterns
    )
    other_plugin = next(
        p for p in registry._all_plugins if "other.com" in p.domain_patterns
    )

    fake_plugin.setup.assert_awaited_once()
    other_plugin.setup.assert_not_awaited()


async def test_teardown_all(tmp_plugins_dir):
    """teardown_all awaits teardown() on every plugin in _active_plugins."""
    registry = PluginRegistry(config=None, plugins_dir=tmp_plugins_dir)

    # Create a mock plugin and place it directly in _active_plugins.
    mock_plugin = MagicMock(spec=RetailerPlugin)
    mock_plugin.teardown = AsyncMock()
    registry._active_plugins = [mock_plugin]

    await registry.teardown_all()

    mock_plugin.teardown.assert_awaited_once()


# ---------------------------------------------------------------------------
# PX-04: plugins_for_items deduplicates by id() and skips non-matching links
# ---------------------------------------------------------------------------


def test_plugins_for_items_dedups_and_skips_unmatched(tmp_plugins_dir):
    """PX-04: plugins_for_items deduplicates plugin instances and ignores no-match links.

    Covers registry.py:120 (_route_all returns None for a non-matching host) and
    registry.py:129-136 (id()-based deduplication keeps only the first occurrence).

    Two items link to the same fake.com plugin -- the result must contain exactly
    one entry for that plugin (not two). A third item links to nomatch.test, which
    has no registered plugin and must contribute nothing.
    """
    registry = PluginRegistry(config=None, plugins_dir=tmp_plugins_dir)

    items = [
        ("Item A", "https://www.fake.com/product/1", True, 1, False),
        ("Item B", "https://www.fake.com/product/2", True, 1, False),
        ("Item C", "https://nomatch.test/product/x", True, 1, False),
    ]

    result = registry.plugins_for_items(items)

    # Only one plugin instance (fake.com) must appear; nomatch.test contributes nothing
    assert len(result) == 1, (
        f"Expected 1 plugin (deduped), got {len(result)}"
    )
    assert "fake.com" in result[0].domain_patterns, (
        f"Expected the fake.com plugin; got domain_patterns={result[0].domain_patterns}"
    )


# ---------------------------------------------------------------------------
# PX-05: setup_for_items isolates per-plugin setup() failure (WARNING + skip)
# ---------------------------------------------------------------------------


async def test_setup_for_items_skips_plugin_on_setup_error(
    fake_plugin, tmp_path
):
    """PX-05: a setup() exception logs WARNING and skips that plugin without abort.

    Covers registry.py:158-159 -- when plugin A's setup() raises RuntimeError,
    a WARNING is emitted, A is NOT in _active_plugins, and plugin B (healthy)
    still sets up and lands in _active_plugins.
    """
    # Build two plugins for distinct domains
    plugin_a = fake_plugin(domains=["alpha.test"])
    plugin_a.setup = AsyncMock(side_effect=RuntimeError("boom"))
    plugin_b = fake_plugin(domains=["beta.test"])
    plugin_b.setup = AsyncMock()

    registry = PluginRegistry(config=None, plugins_dir=tmp_path)
    registry._all_plugins = [plugin_a, plugin_b]

    items = [
        ("Alpha Item", "https://alpha.test/1", True, 1, False),
        ("Beta Item", "https://beta.test/1", True, 1, False),
    ]

    warnings_captured: list[str] = []

    def _fake_log(message: str, level: str, *args, **kwargs):
        if level == "WARNING":
            warnings_captured.append(message)

    with patch("core.registry.writeLog", side_effect=_fake_log):
        await registry.setup_for_items(items)

    # plugin_a failed setup -- must NOT be active
    assert plugin_a not in registry._active_plugins, (
        "plugin_a (setup raised) must not be in _active_plugins"
    )
    # plugin_b succeeded -- must be active
    assert plugin_b in registry._active_plugins, (
        "plugin_b (setup succeeded) must be in _active_plugins"
    )
    # A WARNING must mention "Plugin setup failed"
    assert any("Plugin setup failed" in msg for msg in warnings_captured), (
        f"Expected WARNING containing 'Plugin setup failed'; got {warnings_captured}"
    )


# ---------------------------------------------------------------------------
# PX-06: teardown_all logs WARNING and continues past a teardown error
# ---------------------------------------------------------------------------


async def test_teardown_all_logs_and_continues_on_error(tmp_path):
    """PX-06: teardown_all logs WARNING for a failing teardown and still runs the rest.

    Covers registry.py:169-170 -- if plugin A's teardown() raises, a WARNING is
    logged and iteration continues so plugin B's teardown() is still awaited.
    The method must NOT propagate the exception.
    """
    registry = PluginRegistry(config=None, plugins_dir=tmp_path)

    plugin_a = MagicMock(spec=RetailerPlugin)
    plugin_a.teardown = AsyncMock(side_effect=RuntimeError("teardown exploded"))
    plugin_b = MagicMock(spec=RetailerPlugin)
    plugin_b.teardown = AsyncMock()
    registry._active_plugins = [plugin_a, plugin_b]

    warnings_captured: list[str] = []

    def _fake_log(message: str, level: str, *args, **kwargs):
        if level == "WARNING":
            warnings_captured.append(message)

    with patch("core.registry.writeLog", side_effect=_fake_log):
        # Must not raise even though plugin_a.teardown raises
        await registry.teardown_all()

    # plugin_b's teardown must still have been called despite plugin_a's failure
    plugin_b.teardown.assert_awaited_once()

    # A WARNING must mention "Plugin teardown error"
    assert any("Plugin teardown error" in msg for msg in warnings_captured), (
        f"Expected WARNING containing 'Plugin teardown error'; got {warnings_captured}"
    )
