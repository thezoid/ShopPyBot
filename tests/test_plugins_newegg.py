"""RED skeleton for PLG-08 (NewEgg plugin).

Wave 0 lands this file as RED: every test fails today because
`plugins/shopbot_plugin_newegg.py` does not exist yet. Wave 1 plan 06-06
fully rewrites this file with the GREEN test suite.
"""
import pytest

from plugin_base import RetailerPlugin


def test_neweggPluginImportable():
    from plugins.shopbot_plugin_newegg import NewEggPlugin
    assert NewEggPlugin is not None


def test_neweggSubclassesRetailerPlugin():
    from plugins.shopbot_plugin_newegg import NewEggPlugin
    assert issubclass(NewEggPlugin, RetailerPlugin)


def test_neweggDomainPattern():
    from plugins.shopbot_plugin_newegg import NewEggPlugin
    assert isinstance(NewEggPlugin.domain_pattern, list)
    assert len(NewEggPlugin.domain_pattern) > 0
    for pattern in NewEggPlugin.domain_pattern:
        assert isinstance(pattern, str)


async def test_neweggRiskyAutobuyGateOff(monkeypatch, fakeBrowser):
    monkeypatch.delenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", raising=False)
    from plugins.shopbot_plugin_newegg import NewEggPlugin
    plugin = NewEggPlugin(platform_config=None, user_agents=None)
    plugin._browser = fakeBrowser
    result = await plugin.auto_buy("https://www.newegg.com/p/x", config=None)
    assert result is False


async def test_neweggRiskyAutobuyGateOn(monkeypatch, fakeBrowser):
    monkeypatch.setenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", "true")
    from plugins.shopbot_plugin_newegg import NewEggPlugin
    plugin = NewEggPlugin(platform_config=None, user_agents=None)
    assert plugin._riskyAutoBuyEnabled is True
