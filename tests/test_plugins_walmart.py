"""GREEN tests for WalmartPlugin (PLG-04).

Covers: ABC contract, env-at-init risky autobuy gate, one-time PerimeterX
INFO note, domain_pattern, no Selenium imports, no plugin-level notifier
imports, open() builds uc.start with UA + headless, shutdown override uses
await self.driver.stop(), check_availability uses nodriver Tab API.

Includes one xfail-marked O-1 smoke test: real uc.start() inside asyncio.run
loop. If it raises, the documented fallback is asyncio.to_thread of a sync
helper. See SUMMARY.md for the captured outcome.
"""
import ast
import asyncio
import inspect
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from plugin_base import RetailerPlugin


EXPECTED_ATC_SELECTOR = 'button[data-automation-id="atc-button"]'

_SOURCE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "plugins",
    "shopbot_plugin_walmart.py",
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

    monkeypatch.setattr("plugins.shopbot_plugin_walmart.writeLog", _fakeWriteLog)
    return records


def _sourceAst():
    with open(_SOURCE_PATH, "r", encoding="utf-8") as f:
        return ast.parse(f.read())


# ---- ABC + module shape ----------------------------------------------------

def test_walmartPluginImportable():
    from plugins.shopbot_plugin_walmart import WalmartPlugin
    assert WalmartPlugin is not None


def test_walmartSubclassesRetailerPlugin():
    from plugins.shopbot_plugin_walmart import WalmartPlugin
    assert issubclass(WalmartPlugin, RetailerPlugin)
    assert WalmartPlugin.domain_pattern == ["walmart.com"]
    assert WalmartPlugin.login_at_startup is False
    assert WalmartPlugin.name == "walmart"


def test_walmartDomainPattern():
    from plugins.shopbot_plugin_walmart import WalmartPlugin
    assert isinstance(WalmartPlugin.domain_pattern, list)
    assert len(WalmartPlugin.domain_pattern) > 0
    for pattern in WalmartPlugin.domain_pattern:
        assert isinstance(pattern, str)


def test_walmartAbcContract():
    from plugins.shopbot_plugin_walmart import WalmartPlugin
    assert inspect.iscoroutinefunction(WalmartPlugin.open)
    assert inspect.iscoroutinefunction(WalmartPlugin.check_availability)
    assert inspect.iscoroutinefunction(WalmartPlugin.auto_buy)
    assert inspect.iscoroutinefunction(WalmartPlugin.shutdown)


# ---- Risky autobuy gate ----------------------------------------------------

async def test_walmartRiskyAutobuyGateOff(monkeypatch, fakeBrowser, captureLogs):
    monkeypatch.delenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", raising=False)
    from plugins.shopbot_plugin_walmart import WalmartPlugin
    plugin = WalmartPlugin(_platformConfig(), user_agents=None)
    plugin.driver = fakeBrowser
    result = await plugin.auto_buy("https://www.walmart.com/ip/x", config=None)
    assert result is False
    assert plugin._riskyAutoBuyEnabled is False
    warnings = [m for t, m in captureLogs if t == "WARNING"]
    assert any("SHOPBOT_ENABLE_RISKY_AUTOBUY" in m for m in warnings)
    fakeBrowser.get.assert_not_called()


async def test_walmartRiskyAutobuyGateOn(monkeypatch, fakeBrowser):
    monkeypatch.setenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", "true")
    from plugins.shopbot_plugin_walmart import WalmartPlugin
    plugin = WalmartPlugin(_platformConfig(), user_agents=None)
    assert plugin._riskyAutoBuyEnabled is True


async def test_walmartRiskNoteLoggedOnce(monkeypatch, fakeBrowser, captureLogs):
    monkeypatch.setenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", "true")
    from plugins.shopbot_plugin_walmart import WalmartPlugin
    plugin = WalmartPlugin(_platformConfig(), user_agents=None)
    # Make the purchase flow short-circuit cleanly (atc=None) so the test
    # focuses on the one-time INFO note rather than the full purchase chain.
    fakeBrowser.select = AsyncMock(return_value=None)
    plugin.driver = fakeBrowser

    assert plugin._walmartRiskNoted is False
    await plugin.auto_buy("https://www.walmart.com/ip/x", config=None)
    assert plugin._walmartRiskNoted is True
    await plugin.auto_buy("https://www.walmart.com/ip/x", config=None)

    infoNotes = [m for t, m in captureLogs if t == "INFO" and "PerimeterX" in m]
    assert len(infoNotes) == 1


async def test_walmartEnvReadOnce(monkeypatch):
    monkeypatch.setenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", "true")
    from plugins.shopbot_plugin_walmart import WalmartPlugin
    plugin = WalmartPlugin(_platformConfig(), user_agents=None)
    assert plugin._riskyAutoBuyEnabled is True
    monkeypatch.delenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", raising=False)
    # Env was read once at __init__; deleting the var after must not change state.
    assert plugin._riskyAutoBuyEnabled is True


def test_walmartEnvReadOnlyInInit():
    """AST grep: os.environ.get appears ONLY inside __init__."""
    tree = _sourceAst()
    walmartCls = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "WalmartPlugin"
    )
    for funcNode in walmartCls.body:
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

def test_walmartNoSeleniumImport():
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


def test_walmartNoNotifierImport():
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


# ---- open() / uc.start ------------------------------------------------------

async def test_walmartOpenCallsUcStart(monkeypatch, fakeBrowser):
    monkeypatch.delenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", raising=False)
    from plugins import shopbot_plugin_walmart as mod
    fakeStart = AsyncMock(return_value=fakeBrowser)
    monkeypatch.setattr(mod.uc, "start", fakeStart)
    plugin = mod.WalmartPlugin(_platformConfig(headless=False), user_agents=None)

    await plugin.open()

    assert plugin.driver is fakeBrowser
    fakeStart.assert_awaited_once()
    kwargs = fakeStart.await_args.kwargs
    assert kwargs["headless"] is False
    browserArgs = kwargs["browser_args"]
    assert any(arg.startswith("--user-agent=") for arg in browserArgs)
    assert "--disable-blink-features=AutomationControlled" in browserArgs


async def test_walmartHeadlessPassthrough(monkeypatch, fakeBrowser):
    from plugins import shopbot_plugin_walmart as mod
    fakeStart = AsyncMock(return_value=fakeBrowser)
    monkeypatch.setattr(mod.uc, "start", fakeStart)
    plugin = mod.WalmartPlugin(_platformConfig(headless=True), user_agents=None)
    await plugin.open()
    assert fakeStart.await_args.kwargs["headless"] is True


async def test_walmartUaRotation(monkeypatch, fakeBrowser):
    """Two instances with monkeypatched random.choice return distinct UAs."""
    from plugins import shopbot_plugin_walmart as mod
    fakeStart = AsyncMock(return_value=fakeBrowser)
    monkeypatch.setattr(mod.uc, "start", fakeStart)

    uas = ["UA-A", "UA-B"]
    seq = iter(uas)
    monkeypatch.setattr(mod.random, "choice", lambda lst: next(seq))

    plugin1 = mod.WalmartPlugin(_platformConfig(), user_agents=uas)
    plugin2 = mod.WalmartPlugin(_platformConfig(), user_agents=uas)
    await plugin1.open()
    await plugin2.open()

    args1 = fakeStart.await_args_list[0].kwargs["browser_args"]
    args2 = fakeStart.await_args_list[1].kwargs["browser_args"]
    ua1 = next(a for a in args1 if a.startswith("--user-agent="))
    ua2 = next(a for a in args2 if a.startswith("--user-agent="))
    assert ua1 != ua2


# ---- check_availability ----------------------------------------------------

async def test_walmartCheckAvailabilityTrue(monkeypatch, fakeBrowser):
    from plugins.shopbot_plugin_walmart import WalmartPlugin
    plugin = WalmartPlugin(_platformConfig(), user_agents=None)
    fakeTab = MagicMock()
    fakeTab.select = AsyncMock(return_value=MagicMock())
    fakeBrowser.get = AsyncMock(return_value=fakeTab)
    plugin.driver = fakeBrowser

    result = await plugin.check_availability("https://www.walmart.com/ip/x")
    assert result is True
    fakeBrowser.get.assert_awaited_once()
    fakeTab.select.assert_awaited_once_with(EXPECTED_ATC_SELECTOR)


async def test_walmartCheckAvailabilityFalse(monkeypatch, fakeBrowser):
    from plugins.shopbot_plugin_walmart import WalmartPlugin
    plugin = WalmartPlugin(_platformConfig(), user_agents=None)
    fakeTab = MagicMock()
    fakeTab.select = AsyncMock(return_value=None)
    fakeBrowser.get = AsyncMock(return_value=fakeTab)
    plugin.driver = fakeBrowser

    result = await plugin.check_availability("https://www.walmart.com/ip/oos")
    assert result is False


# ---- shutdown --------------------------------------------------------------

async def test_walmartShutdownNoDriver(captureLogs):
    from plugins.shopbot_plugin_walmart import WalmartPlugin
    plugin = WalmartPlugin(_platformConfig(), user_agents=None)
    plugin.driver = None
    await plugin.shutdown()  # must not raise
    assert all("driver.stop raised" not in m for _, m in captureLogs)


async def test_walmartShutdownAwaitsDriverStop(fakeBrowser):
    from plugins.shopbot_plugin_walmart import WalmartPlugin
    plugin = WalmartPlugin(_platformConfig(), user_agents=None)
    plugin.driver = fakeBrowser
    await plugin.shutdown()
    fakeBrowser.stop.assert_awaited_once()


async def test_walmartShutdownHandlesSyncStop(captureLogs):
    """O-3 fallback: nodriver 0.50.3's browser.stop() is sync (returns None).

    shutdown() must call stop() and conditionally await only if the return
    value is awaitable. A MagicMock (sync) here mimics the real nodriver shape.
    """
    from plugins.shopbot_plugin_walmart import WalmartPlugin
    plugin = WalmartPlugin(_platformConfig(), user_agents=None)
    syncDriver = MagicMock()
    syncDriver.stop = MagicMock(return_value=None)
    plugin.driver = syncDriver
    await plugin.shutdown()  # must not raise TypeError about None await
    syncDriver.stop.assert_called_once()
    warnings = [m for t, m in captureLogs if t == "WARNING"]
    assert not any("driver.stop raised" in m for m in warnings)


async def test_walmartShutdownDriverStopRaises(fakeBrowser, captureLogs):
    from plugins.shopbot_plugin_walmart import WalmartPlugin
    plugin = WalmartPlugin(_platformConfig(), user_agents=None)
    fakeBrowser.stop = AsyncMock(side_effect=RuntimeError("boom"))
    plugin.driver = fakeBrowser
    await plugin.shutdown()  # must swallow
    warnings = [m for t, m in captureLogs if t == "WARNING"]
    assert any("driver.stop raised" in m for m in warnings)


# ---- O-1 smoke test (RESEARCH Open Question O-1) ---------------------------

@pytest.mark.skipif(
    os.environ.get("SHOPBOT_O1_SMOKE") != "true",
    reason="O-1 nodriver-in-asyncio.run smoke test requires real Chrome; "
           "set SHOPBOT_O1_SMOKE=true to opt in.",
)
def test_walmartO1NodriverInsideAsyncioRun():
    """Smoke: does `await uc.start(...)` work inside an active asyncio.run loop?

    RESEARCH A2/O-1: nodriver docs warn `asyncio.run` "never worked"; we expect
    it to work for us because ShopPyBot's main() already runs inside one. If
    this test raises RuntimeError, the documented fallback is to wrap uc.start
    via `asyncio.to_thread` of a sync helper. The outcome is recorded in
    06-02-SUMMARY.md regardless of pass/fail.
    """
    import nodriver as uc

    async def _smoke():
        browser = await uc.start(headless=True)
        try:
            tab = await browser.get("https://example.com")
            assert tab is not None
        finally:
            await browser.stop()

    asyncio.run(_smoke())
