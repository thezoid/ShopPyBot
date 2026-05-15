"""GREEN tests for SquareEnixPlugin (PLG-07).

Covers: ABC contract, env-at-init risky-autobuy gate, dual-domain routing
(square-enix.com + square-enix-games.com via plugin_registry.route_url),
no Selenium / notifier imports, open() builds uc.start with UA + headless,
shutdown override uses inspect.isawaitable() to handle nodriver 0.50.3's
sync Browser.stop() (O-3 fallback), check_availability uses nodriver Tab API.
"""
import ast
import inspect
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from plugin_base import RetailerPlugin
from plugin_registry import route_url


EXPECTED_ATC_SELECTOR = 'button.product-detail-add-to-cart'

_SOURCE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "plugins",
    "shopbot_plugin_squareenix.py",
)


def _platformConfig(*, headless: bool = False, min_delay: float = 3.0, max_delay: float = 8.0):
    cfg = MagicMock()
    cfg.headless = headless
    cfg.min_delay = min_delay
    cfg.max_delay = max_delay
    return cfg


@pytest.fixture
def captureLogs(monkeypatch):
    records: list[tuple[str, str]] = []

    def _fakeWriteLog(message, type, writeTofile=True):
        records.append((type.upper(), message))

    monkeypatch.setattr("plugins.shopbot_plugin_squareenix.writeLog", _fakeWriteLog)
    return records


def _sourceAst():
    with open(_SOURCE_PATH, "r", encoding="utf-8") as f:
        return ast.parse(f.read())


# ---- ABC + module shape ----------------------------------------------------

def test_squareenixPluginImportable():
    from plugins.shopbot_plugin_squareenix import SquareEnixPlugin
    assert SquareEnixPlugin is not None


def test_squareenixSubclassesRetailerPlugin():
    from plugins.shopbot_plugin_squareenix import SquareEnixPlugin
    assert issubclass(SquareEnixPlugin, RetailerPlugin)
    assert "square-enix.com" in SquareEnixPlugin.domain_pattern
    assert "square-enix-games.com" in SquareEnixPlugin.domain_pattern
    assert SquareEnixPlugin.login_at_startup is False
    assert SquareEnixPlugin.name == "squareenix"


def test_squareenixDomainPattern():
    from plugins.shopbot_plugin_squareenix import SquareEnixPlugin
    assert isinstance(SquareEnixPlugin.domain_pattern, list)
    assert len(SquareEnixPlugin.domain_pattern) >= 2
    for pattern in SquareEnixPlugin.domain_pattern:
        assert isinstance(pattern, str)


def test_squareenixAbcContract():
    from plugins.shopbot_plugin_squareenix import SquareEnixPlugin
    assert inspect.iscoroutinefunction(SquareEnixPlugin.open)
    assert inspect.iscoroutinefunction(SquareEnixPlugin.check_availability)
    assert inspect.iscoroutinefunction(SquareEnixPlugin.auto_buy)
    assert inspect.iscoroutinefunction(SquareEnixPlugin.shutdown)


# ---- Risky autobuy gate ----------------------------------------------------

async def test_squareenixRiskyAutobuyGateOff(monkeypatch, fakeBrowser, captureLogs):
    monkeypatch.delenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", raising=False)
    from plugins.shopbot_plugin_squareenix import SquareEnixPlugin
    plugin = SquareEnixPlugin(_platformConfig(), user_agents=None)
    plugin.driver = fakeBrowser
    result = await plugin.auto_buy("https://store.na.square-enix-games.com/x", config=None)
    assert result is False
    assert plugin._riskyAutoBuyEnabled is False
    warnings = [m for t, m in captureLogs if t == "WARNING"]
    assert any("SHOPBOT_ENABLE_RISKY_AUTOBUY" in m for m in warnings)
    fakeBrowser.get.assert_not_called()


async def test_squareenixRiskyAutobuyGateOn(monkeypatch, fakeBrowser):
    monkeypatch.setenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", "true")
    from plugins.shopbot_plugin_squareenix import SquareEnixPlugin
    plugin = SquareEnixPlugin(_platformConfig(), user_agents=None)
    assert plugin._riskyAutoBuyEnabled is True


async def test_squareenixEnvReadOnce(monkeypatch):
    monkeypatch.setenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", "true")
    from plugins.shopbot_plugin_squareenix import SquareEnixPlugin
    plugin = SquareEnixPlugin(_platformConfig(), user_agents=None)
    assert plugin._riskyAutoBuyEnabled is True
    monkeypatch.delenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", raising=False)
    assert plugin._riskyAutoBuyEnabled is True


def test_squareenixEnvReadOnlyInInit():
    """AST grep: os.environ.get appears ONLY inside __init__."""
    tree = _sourceAst()
    cls = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "SquareEnixPlugin"
    )
    for funcNode in cls.body:
        if not isinstance(funcNode, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        envGetCalls = [
            n for n in ast.walk(funcNode)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "get"
            and isinstance(n.func.value, ast.Attribute)
            and n.func.value.attr == "environ"
        ]
        if funcNode.name == "__init__":
            assert len(envGetCalls) >= 1, "Expected os.environ.get inside __init__"
        else:
            assert envGetCalls == [], (
                f"os.environ.get must not appear in {funcNode.name}"
            )


# ---- Import hygiene --------------------------------------------------------

def test_squareenixNoSeleniumImport():
    tree = _sourceAst()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("selenium"), (
                    f"selenium import found: {alias.name}"
                )
        if isinstance(node, ast.ImportFrom):
            assert node.module is None or not node.module.startswith("selenium"), (
                f"selenium import found: {node.module}"
            )


def test_squareenixNoNotifierImport():
    tree = _sourceAst()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert mod != "notifier_base", "plugin must not import notifier_base"
            if mod == "utils":
                for alias in node.names:
                    assert not alias.name.startswith("play_"), (
                        f"plugin must not import {alias.name} from utils"
                    )


# ---- Dual-domain routing ---------------------------------------------------

@pytest.mark.parametrize("url", [
    "https://www.square-enix.com/item/123",
    "https://square-enix.com/item/123",
    "https://store.na.square-enix-games.com/item/123",
    "https://store.eu.square-enix-games.com/item/123",
    "https://square-enix-games.com/item/123",
])
def test_squareenixDualDomainRouting(monkeypatch, url):
    monkeypatch.delenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", raising=False)
    from plugins.shopbot_plugin_squareenix import SquareEnixPlugin
    plugin = SquareEnixPlugin(_platformConfig(), user_agents=None)
    matched = route_url(url, [plugin])
    assert matched is plugin


def test_squareenixOffDomainRoutingNone(monkeypatch):
    monkeypatch.delenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", raising=False)
    from plugins.shopbot_plugin_squareenix import SquareEnixPlugin
    plugin = SquareEnixPlugin(_platformConfig(), user_agents=None)
    assert route_url("https://example.com/item", [plugin]) is None
    assert route_url("https://www.walmart.com/ip/x", [plugin]) is None


# ---- open() / uc.start ------------------------------------------------------

async def test_squareenixOpenCallsUcStart(monkeypatch, fakeBrowser):
    monkeypatch.delenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", raising=False)
    from plugins import shopbot_plugin_squareenix as mod
    fakeStart = AsyncMock(return_value=fakeBrowser)
    monkeypatch.setattr(mod.uc, "start", fakeStart)
    plugin = mod.SquareEnixPlugin(_platformConfig(headless=False), user_agents=None)

    await plugin.open()

    assert plugin.driver is fakeBrowser
    fakeStart.assert_awaited_once()
    kwargs = fakeStart.await_args.kwargs
    assert kwargs["headless"] is False
    browserArgs = kwargs["browser_args"]
    assert any(arg.startswith("--user-agent=") for arg in browserArgs)
    assert "--disable-blink-features=AutomationControlled" in browserArgs


async def test_squareenixHeadlessPassthrough(monkeypatch, fakeBrowser):
    from plugins import shopbot_plugin_squareenix as mod
    fakeStart = AsyncMock(return_value=fakeBrowser)
    monkeypatch.setattr(mod.uc, "start", fakeStart)
    plugin = mod.SquareEnixPlugin(_platformConfig(headless=True), user_agents=None)
    await plugin.open()
    assert fakeStart.await_args.kwargs["headless"] is True


async def test_squareenixUaRotation(monkeypatch, fakeBrowser):
    from plugins import shopbot_plugin_squareenix as mod
    fakeStart = AsyncMock(return_value=fakeBrowser)
    monkeypatch.setattr(mod.uc, "start", fakeStart)

    uas = ["UA-A", "UA-B"]
    seq = iter(uas)
    monkeypatch.setattr(mod.random, "choice", lambda lst: next(seq))

    plugin1 = mod.SquareEnixPlugin(_platformConfig(), user_agents=uas)
    plugin2 = mod.SquareEnixPlugin(_platformConfig(), user_agents=uas)
    await plugin1.open()
    await plugin2.open()

    args1 = fakeStart.await_args_list[0].kwargs["browser_args"]
    args2 = fakeStart.await_args_list[1].kwargs["browser_args"]
    ua1 = next(a for a in args1 if a.startswith("--user-agent="))
    ua2 = next(a for a in args2 if a.startswith("--user-agent="))
    assert ua1 != ua2


# ---- check_availability ----------------------------------------------------

async def test_squareenixCheckAvailabilityTrue(monkeypatch, fakeBrowser):
    from plugins.shopbot_plugin_squareenix import SquareEnixPlugin
    plugin = SquareEnixPlugin(_platformConfig(), user_agents=None)
    fakeTab = MagicMock()
    fakeTab.select = AsyncMock(return_value=MagicMock())
    fakeBrowser.get = AsyncMock(return_value=fakeTab)
    plugin.driver = fakeBrowser

    result = await plugin.check_availability("https://store.na.square-enix-games.com/x")
    assert result is True
    fakeBrowser.get.assert_awaited_once()
    fakeTab.select.assert_awaited_once_with(EXPECTED_ATC_SELECTOR)


async def test_squareenixCheckAvailabilityFalse(monkeypatch, fakeBrowser):
    from plugins.shopbot_plugin_squareenix import SquareEnixPlugin
    plugin = SquareEnixPlugin(_platformConfig(), user_agents=None)
    fakeTab = MagicMock()
    fakeTab.select = AsyncMock(return_value=None)
    fakeBrowser.get = AsyncMock(return_value=fakeTab)
    plugin.driver = fakeBrowser

    result = await plugin.check_availability("https://www.square-enix.com/oos")
    assert result is False


async def test_squareenixCheckAvailabilitySwallowsErrors(monkeypatch, fakeBrowser, captureLogs):
    from plugins.shopbot_plugin_squareenix import SquareEnixPlugin
    plugin = SquareEnixPlugin(_platformConfig(), user_agents=None)
    fakeBrowser.get = AsyncMock(side_effect=RuntimeError("boom"))
    plugin.driver = fakeBrowser

    result = await plugin.check_availability("https://www.square-enix.com/x")
    assert result is False
    errors = [m for t, m in captureLogs if t == "ERROR"]
    assert any("boom" in m for m in errors)


# ---- shutdown --------------------------------------------------------------

async def test_squareenixShutdownNoDriver(captureLogs):
    from plugins.shopbot_plugin_squareenix import SquareEnixPlugin
    plugin = SquareEnixPlugin(_platformConfig(), user_agents=None)
    plugin.driver = None
    await plugin.shutdown()  # must not raise
    assert all("driver.stop raised" not in m for _, m in captureLogs)


async def test_squareenixShutdownAwaitsAsyncStop(fakeBrowser):
    from plugins.shopbot_plugin_squareenix import SquareEnixPlugin
    plugin = SquareEnixPlugin(_platformConfig(), user_agents=None)
    plugin.driver = fakeBrowser
    await plugin.shutdown()
    fakeBrowser.stop.assert_awaited_once()


async def test_squareenixShutdownHandlesSyncStop(captureLogs):
    """O-3 fallback: nodriver 0.50.3's browser.stop() is sync (returns None)."""
    from plugins.shopbot_plugin_squareenix import SquareEnixPlugin
    plugin = SquareEnixPlugin(_platformConfig(), user_agents=None)
    syncDriver = MagicMock()
    syncDriver.stop = MagicMock(return_value=None)
    plugin.driver = syncDriver
    await plugin.shutdown()  # must not raise TypeError about None await
    syncDriver.stop.assert_called_once()
    warnings = [m for t, m in captureLogs if t == "WARNING"]
    assert not any("driver.stop raised" in m for m in warnings)


async def test_squareenixShutdownDriverStopRaises(fakeBrowser, captureLogs):
    from plugins.shopbot_plugin_squareenix import SquareEnixPlugin
    plugin = SquareEnixPlugin(_platformConfig(), user_agents=None)
    fakeBrowser.stop = AsyncMock(side_effect=RuntimeError("boom"))
    plugin.driver = fakeBrowser
    await plugin.shutdown()  # must swallow
    warnings = [m for t, m in captureLogs if t == "WARNING"]
    assert any("driver.stop raised" in m for m in warnings)
