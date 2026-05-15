"""GREEN tests for GamestopPlugin (PLG-06).

Covers: ABC contract, env-at-init risky autobuy gate, hCaptcha detection
across both selectors, asyncio.to_thread(input) pause keeps the event loop
responsive, AST-grep import hygiene + bare-input prohibition, open() builds
uc.start with UA + headless, shutdown override uses the inspect.isawaitable
fallback (O-3, nodriver 0.50.3 sync stop).
"""
import ast
import asyncio
import inspect
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from plugin_base import RetailerPlugin


EXPECTED_ATC_SELECTOR = 'button.add-to-cart:not(:disabled)'
EXPECTED_HCAPTCHA_IFRAME = 'iframe[src*="hcaptcha.com"]'
EXPECTED_HCAPTCHA_WIDGET = 'div[data-hcaptcha-widget-id]'

_SOURCE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "plugins",
    "shopbot_plugin_gamestop.py",
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

    monkeypatch.setattr("plugins.shopbot_plugin_gamestop.writeLog", _fakeWriteLog)
    return records


def _sourceAst():
    with open(_SOURCE_PATH, "r", encoding="utf-8") as f:
        return ast.parse(f.read())


# ---- ABC + module shape ----------------------------------------------------

def test_gamestopPluginImportable():
    from plugins.shopbot_plugin_gamestop import GamestopPlugin
    assert GamestopPlugin is not None


def test_gamestopSubclassesRetailerPlugin():
    from plugins.shopbot_plugin_gamestop import GamestopPlugin
    assert issubclass(GamestopPlugin, RetailerPlugin)
    assert GamestopPlugin.domain_pattern == ["gamestop.com"]
    assert GamestopPlugin.login_at_startup is False
    assert GamestopPlugin.name == "gamestop"


def test_gamestopDomainPattern():
    from plugins.shopbot_plugin_gamestop import GamestopPlugin
    assert isinstance(GamestopPlugin.domain_pattern, list)
    assert len(GamestopPlugin.domain_pattern) > 0
    for pattern in GamestopPlugin.domain_pattern:
        assert isinstance(pattern, str)


def test_gamestopAbcContract():
    from plugins.shopbot_plugin_gamestop import GamestopPlugin
    assert inspect.iscoroutinefunction(GamestopPlugin.open)
    assert inspect.iscoroutinefunction(GamestopPlugin.check_availability)
    assert inspect.iscoroutinefunction(GamestopPlugin.auto_buy)
    assert inspect.iscoroutinefunction(GamestopPlugin.detect_captcha)
    assert inspect.iscoroutinefunction(GamestopPlugin.shutdown)


# ---- Risky autobuy gate ----------------------------------------------------

async def test_gamestopRiskyAutobuyGateOff(monkeypatch, fakeBrowser, captureLogs):
    monkeypatch.delenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", raising=False)
    from plugins.shopbot_plugin_gamestop import GamestopPlugin
    plugin = GamestopPlugin(_platformConfig(), user_agents=None)
    plugin.driver = fakeBrowser
    result = await plugin.auto_buy("https://www.gamestop.com/p/x", config=None)
    assert result is False
    assert plugin._riskyAutoBuyEnabled is False
    warnings = [m for t, m in captureLogs if t == "WARNING"]
    assert any("SHOPBOT_ENABLE_RISKY_AUTOBUY" in m for m in warnings)
    fakeBrowser.get.assert_not_called()


async def test_gamestopRiskyAutobuyGateOn(monkeypatch, fakeBrowser):
    monkeypatch.setenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", "true")
    from plugins.shopbot_plugin_gamestop import GamestopPlugin
    plugin = GamestopPlugin(_platformConfig(), user_agents=None)
    assert plugin._riskyAutoBuyEnabled is True


async def test_gamestopEnvReadOnce(monkeypatch):
    monkeypatch.setenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", "true")
    from plugins.shopbot_plugin_gamestop import GamestopPlugin
    plugin = GamestopPlugin(_platformConfig(), user_agents=None)
    assert plugin._riskyAutoBuyEnabled is True
    monkeypatch.delenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", raising=False)
    # Env read once at __init__; later mutation must not flip the flag.
    assert plugin._riskyAutoBuyEnabled is True


def test_gamestopEnvReadOnlyInInit():
    """AST grep: os.environ.get appears ONLY inside __init__."""
    tree = _sourceAst()
    cls = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "GamestopPlugin"
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
            assert len(envGetCalls) >= 1
        else:
            assert envGetCalls == [], (
                f"os.environ.get must not appear in {funcNode.name}"
            )


# ---- Import hygiene --------------------------------------------------------

def test_gamestopNoSeleniumImport():
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


def test_gamestopNoNotifierImport():
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


def test_gamestopInputWrappedInToThread():
    """AST grep: every `input(...)` Call must be the first arg of `asyncio.to_thread(...)`.

    No bare top-level `input(...)`. This proves the event loop is never
    blocked by stdin: only the worker thread sleeps on input.
    """
    tree = _sourceAst()
    # Build a set of Call nodes that are asyncio.to_thread(input, ...) wrappers.
    allowed_input_nodes: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            isToThread = (
                isinstance(func, ast.Attribute)
                and func.attr == "to_thread"
                and isinstance(func.value, ast.Name)
                and func.value.id == "asyncio"
            )
            if isToThread and node.args:
                firstArg = node.args[0]
                if isinstance(firstArg, ast.Name) and firstArg.id == "input":
                    allowed_input_nodes.add(id(firstArg))

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id == "input":
                pytest.fail("bare input() call detected; must be wrapped in asyncio.to_thread")


# ---- detect_captcha --------------------------------------------------------

async def test_gamestopDetectCaptchaNullTab():
    from plugins.shopbot_plugin_gamestop import GamestopPlugin
    plugin = GamestopPlugin(_platformConfig(), user_agents=None)
    plugin._tab = None
    assert await plugin.detect_captcha() is False


def _tabWithSelectMap(selectorMap: dict):
    tab = MagicMock()

    async def _select(selector):
        return selectorMap.get(selector)

    tab.select = AsyncMock(side_effect=_select)
    return tab


async def test_gamestopDetectCaptchaIframe():
    from plugins.shopbot_plugin_gamestop import GamestopPlugin
    plugin = GamestopPlugin(_platformConfig(), user_agents=None)
    iframeSentinel = MagicMock(name="iframeElement")
    plugin._tab = _tabWithSelectMap({EXPECTED_HCAPTCHA_IFRAME: iframeSentinel})
    assert await plugin.detect_captcha() is True


async def test_gamestopDetectCaptchaWidget():
    from plugins.shopbot_plugin_gamestop import GamestopPlugin
    plugin = GamestopPlugin(_platformConfig(), user_agents=None)
    widgetSentinel = MagicMock(name="widgetElement")
    plugin._tab = _tabWithSelectMap({
        EXPECTED_HCAPTCHA_IFRAME: None,
        EXPECTED_HCAPTCHA_WIDGET: widgetSentinel,
    })
    assert await plugin.detect_captcha() is True


async def test_gamestopDetectCaptchaAbsent():
    from plugins.shopbot_plugin_gamestop import GamestopPlugin
    plugin = GamestopPlugin(_platformConfig(), user_agents=None)
    plugin._tab = _tabWithSelectMap({
        EXPECTED_HCAPTCHA_IFRAME: None,
        EXPECTED_HCAPTCHA_WIDGET: None,
    })
    assert await plugin.detect_captcha() is False


# ---- CAPTCHA pause via asyncio.to_thread(input) ----------------------------

async def test_gamestopCaptchaPauseNonBlocking(monkeypatch, captureLogs):
    """Two concurrent auto_buy invocations both finish quickly even when a
    CAPTCHA is detected. The to_thread(input) bridge blocks only the worker
    thread, so the event loop continues to serve the second task.
    """
    monkeypatch.setenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", "true")
    monkeypatch.setattr("builtins.input", lambda *a, **kw: "")
    from plugins.shopbot_plugin_gamestop import GamestopPlugin

    def _buildPlugin():
        plugin = GamestopPlugin(_platformConfig(), user_agents=None)
        atcSentinel = MagicMock()
        atcSentinel.click = AsyncMock()
        checkoutSentinel = MagicMock()
        checkoutSentinel.click = AsyncMock()
        placeOrderSentinel = MagicMock()
        placeOrderSentinel.click = AsyncMock()

        # The PDP tab returns ATC; the cart tab returns the captcha iframe +
        # checkout button; the post-checkout tab returns place-order.
        pdpTab = _tabWithSelectMap({EXPECTED_ATC_SELECTOR: atcSentinel})
        cartTab = _tabWithSelectMap({
            EXPECTED_HCAPTCHA_IFRAME: MagicMock(name="captchaIframe"),
            'button.checkout-continue': checkoutSentinel,
            'button.place-order': placeOrderSentinel,
        })
        browser = AsyncMock()
        # First get() -> pdpTab, subsequent gets -> cartTab.
        browser.get = AsyncMock(side_effect=[pdpTab, cartTab])
        plugin.driver = browser
        return plugin

    plugin1 = _buildPlugin()
    plugin2 = _buildPlugin()

    # config with test_mode True short-circuits before final click; we only
    # care that both tasks complete in bounded time.
    cfg = MagicMock()
    cfg.debug.test_mode = True

    try:
        results = await asyncio.wait_for(
            asyncio.gather(
                plugin1.auto_buy("https://www.gamestop.com/p/x", config=cfg),
                plugin2.auto_buy("https://www.gamestop.com/p/y", config=cfg),
            ),
            timeout=5.0,
        )
    except asyncio.TimeoutError:
        pytest.fail("auto_buy blocked the event loop; to_thread bridge failed")

    # Both returned False because test_mode short-circuits the final click.
    assert results == [False, False]
    # CAPTCHA pause was logged for both plugins.
    captchaWarnings = [m for t, m in captureLogs if t == "WARNING" and "CAPTCHA" in m]
    assert len(captchaWarnings) >= 2


# ---- check_availability ----------------------------------------------------

async def test_gamestopCheckAvailabilityTrue(fakeBrowser):
    from plugins.shopbot_plugin_gamestop import GamestopPlugin
    plugin = GamestopPlugin(_platformConfig(), user_agents=None)
    fakeTab = MagicMock()
    fakeTab.select = AsyncMock(return_value=MagicMock())
    fakeBrowser.get = AsyncMock(return_value=fakeTab)
    plugin.driver = fakeBrowser

    assert await plugin.check_availability("https://www.gamestop.com/p/x") is True
    fakeTab.select.assert_awaited_once_with(EXPECTED_ATC_SELECTOR)


async def test_gamestopCheckAvailabilityFalse(fakeBrowser):
    from plugins.shopbot_plugin_gamestop import GamestopPlugin
    plugin = GamestopPlugin(_platformConfig(), user_agents=None)
    fakeTab = MagicMock()
    fakeTab.select = AsyncMock(return_value=None)
    fakeBrowser.get = AsyncMock(return_value=fakeTab)
    plugin.driver = fakeBrowser

    assert await plugin.check_availability("https://www.gamestop.com/p/oos") is False


# ---- open() / uc.start ------------------------------------------------------

async def test_gamestopOpenCallsUcStart(monkeypatch, fakeBrowser):
    monkeypatch.delenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", raising=False)
    from plugins import shopbot_plugin_gamestop as mod
    fakeStart = AsyncMock(return_value=fakeBrowser)
    monkeypatch.setattr(mod.uc, "start", fakeStart)
    plugin = mod.GamestopPlugin(_platformConfig(headless=False), user_agents=None)

    await plugin.open()

    assert plugin.driver is fakeBrowser
    fakeStart.assert_awaited_once()
    kwargs = fakeStart.await_args.kwargs
    assert kwargs["headless"] is False
    browserArgs = kwargs["browser_args"]
    assert any(arg.startswith("--user-agent=") for arg in browserArgs)
    assert "--disable-blink-features=AutomationControlled" in browserArgs


async def test_gamestopUaRotation(monkeypatch, fakeBrowser):
    from plugins import shopbot_plugin_gamestop as mod
    fakeStart = AsyncMock(return_value=fakeBrowser)
    monkeypatch.setattr(mod.uc, "start", fakeStart)

    uas = ["UA-A", "UA-B"]
    seq = iter(uas)
    monkeypatch.setattr(mod.random, "choice", lambda lst: next(seq))

    plugin1 = mod.GamestopPlugin(_platformConfig(), user_agents=uas)
    plugin2 = mod.GamestopPlugin(_platformConfig(), user_agents=uas)
    await plugin1.open()
    await plugin2.open()

    args1 = fakeStart.await_args_list[0].kwargs["browser_args"]
    args2 = fakeStart.await_args_list[1].kwargs["browser_args"]
    ua1 = next(a for a in args1 if a.startswith("--user-agent="))
    ua2 = next(a for a in args2 if a.startswith("--user-agent="))
    assert ua1 != ua2


# ---- shutdown --------------------------------------------------------------

async def test_gamestopShutdownNoDriver(captureLogs):
    from plugins.shopbot_plugin_gamestop import GamestopPlugin
    plugin = GamestopPlugin(_platformConfig(), user_agents=None)
    plugin.driver = None
    await plugin.shutdown()  # must not raise
    assert all("driver.stop raised" not in m for _, m in captureLogs)


async def test_gamestopShutdownHandlesSyncStop(captureLogs):
    """O-3 fallback: nodriver 0.50.3's browser.stop() is sync (returns None)."""
    from plugins.shopbot_plugin_gamestop import GamestopPlugin
    plugin = GamestopPlugin(_platformConfig(), user_agents=None)
    syncDriver = MagicMock()
    syncDriver.stop = MagicMock(return_value=None)
    plugin.driver = syncDriver
    await plugin.shutdown()  # must not raise TypeError about None await
    syncDriver.stop.assert_called_once()
    warnings = [m for t, m in captureLogs if t == "WARNING"]
    assert not any("driver.stop raised" in m for m in warnings)


async def test_gamestopShutdownDriverStopRaises(fakeBrowser, captureLogs):
    from plugins.shopbot_plugin_gamestop import GamestopPlugin
    plugin = GamestopPlugin(_platformConfig(), user_agents=None)
    fakeBrowser.stop = MagicMock(side_effect=RuntimeError("boom"))
    plugin.driver = fakeBrowser
    await plugin.shutdown()  # must swallow
    warnings = [m for t, m in captureLogs if t == "WARNING"]
    assert any("driver.stop raised" in m for m in warnings)
