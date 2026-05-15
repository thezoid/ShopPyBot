"""RED skeleton for PLG-06 (GameStop plugin).

Wave 0 lands this file as RED: every test fails today because
`plugins/shopbot_plugin_gamestop.py` does not exist yet. Wave 1 plan 06-04
fully rewrites this file with the GREEN test suite.
"""
import pytest

from plugin_base import RetailerPlugin


def test_gamestopPluginImportable():
    from plugins.shopbot_plugin_gamestop import GameStopPlugin
    assert GameStopPlugin is not None


def test_gamestopSubclassesRetailerPlugin():
    from plugins.shopbot_plugin_gamestop import GameStopPlugin
    assert issubclass(GameStopPlugin, RetailerPlugin)


def test_gamestopDomainPattern():
    from plugins.shopbot_plugin_gamestop import GameStopPlugin
    assert isinstance(GameStopPlugin.domain_pattern, list)
    assert len(GameStopPlugin.domain_pattern) > 0
    for pattern in GameStopPlugin.domain_pattern:
        assert isinstance(pattern, str)


async def test_gamestopRiskyAutobuyGateOff(monkeypatch, fakeBrowser):
    monkeypatch.delenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", raising=False)
    from plugins.shopbot_plugin_gamestop import GameStopPlugin
    plugin = GameStopPlugin(platform_config=None, user_agents=None)
    plugin._browser = fakeBrowser
    result = await plugin.auto_buy("https://www.gamestop.com/p/x", config=None)
    assert result is False


async def test_gamestopRiskyAutobuyGateOn(monkeypatch, fakeBrowser):
    monkeypatch.setenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", "true")
    from plugins.shopbot_plugin_gamestop import GameStopPlugin
    plugin = GameStopPlugin(platform_config=None, user_agents=None)
    assert plugin._riskyAutoBuyEnabled is True


async def test_gamestopCaptchaPauseNonBlocking(monkeypatch, fakeBrowser):
    monkeypatch.setenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", "true")
    monkeypatch.setattr("builtins.input", lambda *a, **kw: "")
    from plugins.shopbot_plugin_gamestop import GameStopPlugin
    plugin = GameStopPlugin(platform_config=None, user_agents=None)
    plugin._browser = fakeBrowser
    # CAPTCHA detected: auto_buy must pause for manual solve via
    # asyncio.to_thread(input) without blocking the event loop.
    monkeypatch.setattr(plugin, "detect_captcha", lambda: True)
    await plugin.auto_buy("https://www.gamestop.com/p/x", config=None)
