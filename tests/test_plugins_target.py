"""RED skeleton for PLG-05 (Target plugin).

Wave 0 lands this file as RED: every test fails today because
`plugins/shopbot_plugin_target.py` does not exist yet. Wave 1 plan 06-03
fully rewrites this file with the GREEN test suite.
"""
import pytest

from plugin_base import RetailerPlugin


def test_targetPluginImportable():
    from plugins.shopbot_plugin_target import TargetPlugin
    assert TargetPlugin is not None


def test_targetSubclassesRetailerPlugin():
    from plugins.shopbot_plugin_target import TargetPlugin
    assert issubclass(TargetPlugin, RetailerPlugin)


def test_targetDomainPattern():
    from plugins.shopbot_plugin_target import TargetPlugin
    assert isinstance(TargetPlugin.domain_pattern, list)
    assert len(TargetPlugin.domain_pattern) > 0
    for pattern in TargetPlugin.domain_pattern:
        assert isinstance(pattern, str)


async def test_targetRiskyAutobuyGateOff(monkeypatch, fakeBrowser):
    monkeypatch.delenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", raising=False)
    from plugins.shopbot_plugin_target import TargetPlugin
    plugin = TargetPlugin(platform_config=None, user_agents=None)
    plugin._browser = fakeBrowser
    result = await plugin.auto_buy("https://www.target.com/p/x", config=None)
    assert result is False


async def test_targetRiskyAutobuyGateOn(monkeypatch, fakeBrowser):
    monkeypatch.setenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", "true")
    from plugins.shopbot_plugin_target import TargetPlugin
    plugin = TargetPlugin(platform_config=None, user_agents=None)
    assert plugin._riskyAutoBuyEnabled is True
