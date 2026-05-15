"""GREEN tests for TargetPlugin (PLG-05).

Covers: ABC contract, env-at-init risky autobuy gate, Akamai headless WARNING,
EXPERIMENTAL docstring, domain_pattern, no Selenium imports, no plugin-level
notifier imports, open() builds uc.start with UA + headless, shutdown override
uses the O-3 inspect.isawaitable fallback, check_availability uses nodriver
Tab API.
"""
import ast
import inspect
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from plugin_base import RetailerPlugin


EXPECTED_ATC_SELECTOR = 'button[data-test="orderPickupButton"]'

_SOURCE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "plugins",
    "shopbot_plugin_target.py",
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

    monkeypatch.setattr("plugins.shopbot_plugin_target.writeLog", _fakeWriteLog)
    return records


def _sourceAst():
    with open(_SOURCE_PATH, "r", encoding="utf-8") as f:
        return ast.parse(f.read())


# ---- ABC + module shape ----------------------------------------------------

def test_targetPluginImportable():
    from plugins.shopbot_plugin_target import TargetPlugin
    assert TargetPlugin is not None


def test_targetSubclassesRetailerPlugin():
    from plugins.shopbot_plugin_target import TargetPlugin
    assert issubclass(TargetPlugin, RetailerPlugin)
    assert TargetPlugin.domain_pattern == ["target.com"]
    assert TargetPlugin.login_at_startup is False
    assert TargetPlugin.name == "target"


def test_targetDomainPattern():
    from plugins.shopbot_plugin_target import TargetPlugin
    assert isinstance(TargetPlugin.domain_pattern, list)
    assert len(TargetPlugin.domain_pattern) > 0
    for pattern in TargetPlugin.domain_pattern:
        assert isinstance(pattern, str)


def test_targetAbcContract():
    from plugins.shopbot_plugin_target import TargetPlugin
    assert inspect.iscoroutinefunction(TargetPlugin.open)
    assert inspect.iscoroutinefunction(TargetPlugin.check_availability)
    assert inspect.iscoroutinefunction(TargetPlugin.auto_buy)
    assert inspect.iscoroutinefunction(TargetPlugin.shutdown)


def test_targetExperimentalDocstring():
    from plugins import shopbot_plugin_target as mod
    assert mod.__doc__ is not None
    assert "EXPERIMENTAL" in mod.__doc__


# ---- Risky autobuy gate ----------------------------------------------------

async def test_targetRiskyAutobuyGateOff(monkeypatch, fakeBrowser, captureLogs):
    monkeypatch.delenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", raising=False)
    from plugins.shopbot_plugin_target import TargetPlugin
    plugin = TargetPlugin(_platformConfig(), user_agents=None)
    plugin.driver = fakeBrowser
    result = await plugin.auto_buy("https://www.target.com/p/x", config=None)
    assert result is False
    assert plugin._riskyAutoBuyEnabled is False
    warnings = [m for t, m in captureLogs if t == "WARNING"]
    assert any("SHOPBOT_ENABLE_RISKY_AUTOBUY" in m for m in warnings)
    fakeBrowser.get.assert_not_called()


async def test_targetRiskyAutobuyGateOn(monkeypatch, fakeBrowser):
    monkeypatch.setenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", "true")
    from plugins.shopbot_plugin_target import TargetPlugin
    plugin = TargetPlugin(_platformConfig(), user_agents=None)
    assert plugin._riskyAutoBuyEnabled is True


async def test_targetEnvReadOnce(monkeypatch):
    monkeypatch.setenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", "true")
    from plugins.shopbot_plugin_target import TargetPlugin
    plugin = TargetPlugin(_platformConfig(), user_agents=None)
    assert plugin._riskyAutoBuyEnabled is True
    monkeypatch.delenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", raising=False)
    # Env was read once at __init__; deleting the var after must not change state.
    assert plugin._riskyAutoBuyEnabled is True


def test_targetEnvReadOnlyInInit():
    """AST grep: os.environ.get appears ONLY inside __init__."""
    tree = _sourceAst()
    targetCls = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "TargetPlugin"
    )
    for funcNode in targetCls.body:
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


# ---- Akamai headless WARNING -----------------------------------------------

def test_targetHeadlessAkamaiWarning(captureLogs):
    from plugins.shopbot_plugin_target import TargetPlugin
    plugin = TargetPlugin(_platformConfig(headless=True), user_agents=None)
    warnings = [m for t, m in captureLogs if t == "WARNING"]
    assert any("Akamai" in m for m in warnings), (
        f"Expected an Akamai-mentioning WARNING; got {warnings!r}"
    )
    # Plugin still constructs successfully.
    assert plugin._headless is True


def test_targetHeadlessFalseNoAkamaiWarning(captureLogs):
    from plugins.shopbot_plugin_target import TargetPlugin
    plugin = TargetPlugin(_platformConfig(headless=False), user_agents=None)
    akamaiWarns = [
        m for t, m in captureLogs if t == "WARNING" and "Akamai" in m
    ]
    assert akamaiWarns == []
    assert plugin._headless is False


# ---- Import hygiene --------------------------------------------------------

def test_targetNoSeleniumImport():
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


def test_targetNoNotifierImport():
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

async def test_targetOpenCallsUcStart(monkeypatch, fakeBrowser):
    monkeypatch.delenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", raising=False)
    from plugins import shopbot_plugin_target as mod
    fakeStart = AsyncMock(return_value=fakeBrowser)
    monkeypatch.setattr(mod.uc, "start", fakeStart)
    plugin = mod.TargetPlugin(_platformConfig(headless=False), user_agents=None)

    await plugin.open()

    assert plugin.driver is fakeBrowser
    fakeStart.assert_awaited_once()
    kwargs = fakeStart.await_args.kwargs
    assert kwargs["headless"] is False
    browserArgs = kwargs["browser_args"]
    assert any(arg.startswith("--user-agent=") for arg in browserArgs)
    assert "--disable-blink-features=AutomationControlled" in browserArgs


async def test_targetHeadlessPassthrough(monkeypatch, fakeBrowser):
    from plugins import shopbot_plugin_target as mod
    fakeStart = AsyncMock(return_value=fakeBrowser)
    monkeypatch.setattr(mod.uc, "start", fakeStart)
    plugin = mod.TargetPlugin(_platformConfig(headless=True), user_agents=None)
    await plugin.open()
    assert fakeStart.await_args.kwargs["headless"] is True


async def test_targetUaRotation(monkeypatch, fakeBrowser):
    """Two instances with monkeypatched random.choice return distinct UAs."""
    from plugins import shopbot_plugin_target as mod
    fakeStart = AsyncMock(return_value=fakeBrowser)
    monkeypatch.setattr(mod.uc, "start", fakeStart)

    uas = ["UA-A", "UA-B"]
    seq = iter(uas)
    monkeypatch.setattr(mod.random, "choice", lambda lst: next(seq))

    plugin1 = mod.TargetPlugin(_platformConfig(), user_agents=uas)
    plugin2 = mod.TargetPlugin(_platformConfig(), user_agents=uas)
    await plugin1.open()
    await plugin2.open()

    args1 = fakeStart.await_args_list[0].kwargs["browser_args"]
    args2 = fakeStart.await_args_list[1].kwargs["browser_args"]
    ua1 = next(a for a in args1 if a.startswith("--user-agent="))
    ua2 = next(a for a in args2 if a.startswith("--user-agent="))
    assert ua1 != ua2


# ---- check_availability ----------------------------------------------------

async def test_targetCheckAvailabilityTrue(fakeBrowser):
    from plugins.shopbot_plugin_target import TargetPlugin
    plugin = TargetPlugin(_platformConfig(), user_agents=None)
    fakeTab = MagicMock()
    fakeTab.select = AsyncMock(return_value=MagicMock())
    fakeBrowser.get = AsyncMock(return_value=fakeTab)
    plugin.driver = fakeBrowser

    result = await plugin.check_availability("https://www.target.com/p/x")
    assert result is True
    fakeBrowser.get.assert_awaited_once()
    fakeTab.select.assert_awaited_once_with(EXPECTED_ATC_SELECTOR)


async def test_targetCheckAvailabilityFalse(fakeBrowser):
    from plugins.shopbot_plugin_target import TargetPlugin
    plugin = TargetPlugin(_platformConfig(), user_agents=None)
    fakeTab = MagicMock()
    fakeTab.select = AsyncMock(return_value=None)
    fakeBrowser.get = AsyncMock(return_value=fakeTab)
    plugin.driver = fakeBrowser

    result = await plugin.check_availability("https://www.target.com/p/oos")
    assert result is False


async def test_targetCheckAvailabilityRaises(fakeBrowser, captureLogs):
    from plugins.shopbot_plugin_target import TargetPlugin
    plugin = TargetPlugin(_platformConfig(), user_agents=None)
    fakeBrowser.get = AsyncMock(side_effect=RuntimeError("net boom"))
    plugin.driver = fakeBrowser

    result = await plugin.check_availability("https://www.target.com/p/x")
    assert result is False
    errors = [m for t, m in captureLogs if t == "ERROR"]
    assert any("check_availability error" in m for m in errors)


# ---- shutdown --------------------------------------------------------------

async def test_targetShutdownNoDriver(captureLogs):
    from plugins.shopbot_plugin_target import TargetPlugin
    plugin = TargetPlugin(_platformConfig(), user_agents=None)
    plugin.driver = None
    await plugin.shutdown()  # must not raise
    assert all("driver.stop raised" not in m for _, m in captureLogs)


async def test_targetShutdownAwaitsDriverStop(fakeBrowser):
    from plugins.shopbot_plugin_target import TargetPlugin
    plugin = TargetPlugin(_platformConfig(), user_agents=None)
    plugin.driver = fakeBrowser
    await plugin.shutdown()
    fakeBrowser.stop.assert_awaited_once()


async def test_targetShutdownHandlesSyncStop(captureLogs):
    """O-3 fallback: nodriver 0.50.3's browser.stop() is sync (returns None)."""
    from plugins.shopbot_plugin_target import TargetPlugin
    plugin = TargetPlugin(_platformConfig(), user_agents=None)
    syncDriver = MagicMock()
    syncDriver.stop = MagicMock(return_value=None)
    plugin.driver = syncDriver
    await plugin.shutdown()  # must not raise TypeError about None await
    syncDriver.stop.assert_called_once()
    warnings = [m for t, m in captureLogs if t == "WARNING"]
    assert not any("driver.stop raised" in m for m in warnings)


async def test_targetShutdownDriverStopRaises(fakeBrowser, captureLogs):
    from plugins.shopbot_plugin_target import TargetPlugin
    plugin = TargetPlugin(_platformConfig(), user_agents=None)
    fakeBrowser.stop = AsyncMock(side_effect=RuntimeError("boom"))
    plugin.driver = fakeBrowser
    await plugin.shutdown()  # must swallow
    warnings = [m for t, m in captureLogs if t == "WARNING"]
    assert any("driver.stop raised" in m for m in warnings)
