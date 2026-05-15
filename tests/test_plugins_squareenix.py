"""RED skeleton for PLG-07 (Square Enix plugin).

Wave 0 lands this file as RED: every test fails today because
`plugins/shopbot_plugin_squareenix.py` does not exist yet. Wave 1 plan 06-05
fully rewrites this file with the GREEN test suite.
"""
import pytest

from plugin_base import RetailerPlugin


def test_squareenixPluginImportable():
    from plugins.shopbot_plugin_squareenix import SquareEnixPlugin
    assert SquareEnixPlugin is not None


def test_squareenixSubclassesRetailerPlugin():
    from plugins.shopbot_plugin_squareenix import SquareEnixPlugin
    assert issubclass(SquareEnixPlugin, RetailerPlugin)


def test_squareenixDomainPattern():
    from plugins.shopbot_plugin_squareenix import SquareEnixPlugin
    assert isinstance(SquareEnixPlugin.domain_pattern, list)
    assert len(SquareEnixPlugin.domain_pattern) > 0
    for pattern in SquareEnixPlugin.domain_pattern:
        assert isinstance(pattern, str)


async def test_squareenixRiskyAutobuyGateOff(monkeypatch, fakeBrowser):
    monkeypatch.delenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", raising=False)
    from plugins.shopbot_plugin_squareenix import SquareEnixPlugin
    plugin = SquareEnixPlugin(platform_config=None, user_agents=None)
    plugin._browser = fakeBrowser
    result = await plugin.auto_buy("https://store.na.square-enix-games.com/x", config=None)
    assert result is False


async def test_squareenixRiskyAutobuyGateOn(monkeypatch, fakeBrowser):
    monkeypatch.setenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", "true")
    from plugins.shopbot_plugin_squareenix import SquareEnixPlugin
    plugin = SquareEnixPlugin(platform_config=None, user_agents=None)
    assert plugin._riskyAutoBuyEnabled is True
