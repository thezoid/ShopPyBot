"""RED skeleton for PLG-04 (Walmart plugin).

Wave 0 lands this file as RED: every test fails today because
`plugins/shopbot_plugin_walmart.py` does not exist yet. Wave 1 plan 06-02
fully rewrites this file with the GREEN test suite.

Convention: imports happen INSIDE test functions so collection succeeds
and each test fails with ImportError when called (not skipped).
"""
import pytest

from plugin_base import RetailerPlugin


def test_walmartPluginImportable():
    """RED: file does not exist yet."""
    from plugins.shopbot_plugin_walmart import WalmartPlugin
    assert WalmartPlugin is not None


def test_walmartSubclassesRetailerPlugin():
    from plugins.shopbot_plugin_walmart import WalmartPlugin
    assert issubclass(WalmartPlugin, RetailerPlugin)


def test_walmartDomainPattern():
    from plugins.shopbot_plugin_walmart import WalmartPlugin
    assert isinstance(WalmartPlugin.domain_pattern, list)
    assert len(WalmartPlugin.domain_pattern) > 0
    for pattern in WalmartPlugin.domain_pattern:
        assert isinstance(pattern, str)


async def test_walmartRiskyAutobuyGateOff(monkeypatch, fakeBrowser):
    monkeypatch.delenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", raising=False)
    from plugins.shopbot_plugin_walmart import WalmartPlugin
    plugin = WalmartPlugin(platform_config=None, user_agents=None)
    plugin._browser = fakeBrowser
    result = await plugin.auto_buy("https://www.walmart.com/ip/x", config=None)
    assert result is False


async def test_walmartRiskyAutobuyGateOn(monkeypatch, fakeBrowser):
    monkeypatch.setenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", "true")
    from plugins.shopbot_plugin_walmart import WalmartPlugin
    plugin = WalmartPlugin(platform_config=None, user_agents=None)
    assert plugin._riskyAutoBuyEnabled is True


async def test_walmartRiskNoteLoggedOnce(monkeypatch, fakeBrowser, capsys):
    monkeypatch.setenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", "true")
    from plugins.shopbot_plugin_walmart import WalmartPlugin
    plugin = WalmartPlugin(platform_config=None, user_agents=None)
    plugin._browser = fakeBrowser
    await plugin.auto_buy("https://www.walmart.com/ip/x", config=None)
    await plugin.auto_buy("https://www.walmart.com/ip/x", config=None)
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert combined.count("PerimeterX") == 1
