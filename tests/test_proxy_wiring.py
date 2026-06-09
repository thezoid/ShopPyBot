"""Tests for Plan 03 proxy+stealth wiring into service, orchestrator, registry, and plugins.

Task 1: ProxyPool construction (service log + orchestrator) + registry.assign_proxy
Task 2: Wire amazon + bestbuy setup() (stealth + proxy + WebRTC + auth) and ban-detect
Task 3: Wire the 5 Phase-6 plugins (walmart, target, gamestop, squareenix, newegg)
"""

import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from core.config_schema import AppConfig, ProxyConfig
from core.registry import PluginRegistry
from core.service import BotService
from core.stealth import ProxyPool, _ProxyEntry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pool(urls=None):
    """Return a ProxyPool with the given URLs (defaults to 3 distinct proxies)."""
    if urls is None:
        urls = [
            "http://user1:pass1@h1.example.com:3128",
            "http://user2:pass2@h2.example.com:3128",
            "http://user3:pass3@h3.example.com:3128",
        ]
    return ProxyPool.from_urls(urls)


def _make_proxy_cfg(enabled=True, urls=None):
    """Return a ProxyConfig with given settings."""
    return ProxyConfig(
        enabled=enabled,
        urls=urls or ["http://u:secret@h1:1", "http://h2:2"],
    )


def _make_app_cfg(proxy_enabled=True, urls=None):
    """Return an AppConfig with proxy settings applied via construct."""
    cfg = MagicMock(spec=AppConfig)
    cfg.proxy = _make_proxy_cfg(proxy_enabled, urls)
    return cfg


def _load_plugin(name):
    """Load a plugin module by short name (e.g. 'amazon')."""
    path = Path(__file__).parent.parent / "plugins" / f"shopbot_plugin_{name}.py"
    spec = importlib.util.spec_from_file_location(f"shopbot_plugin_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_entry(host_port="proxy.example.com:3128", username="user", password="pass"):
    """Return a _ProxyEntry for testing."""
    return _ProxyEntry(
        url=f"http://{username}:{password}@{host_port}",
        host_port=host_port,
        username=username,
        password=password,
    )


def _make_tab_mock():
    """Return a mock tab with AsyncMock send."""
    tab = MagicMock()
    tab.send = AsyncMock()
    return tab


def _make_browser_mock(main_tab=None):
    """Return a mock browser with a main_tab."""
    browser = MagicMock()
    browser.main_tab = main_tab or _make_tab_mock()
    return browser


# ---------------------------------------------------------------------------
# Task 1: service startup log
# ---------------------------------------------------------------------------


def test_proxy_startup_log_no_credentials(tmp_path, caplog):
    """BotService with proxy.enabled emits 'Proxy rotation: enabled, pool_size=N'; no creds."""
    import yaml
    cfg_data = {
        "debug": {"logging_level": 0, "test_mode": True},
        "available": {"timeout": 10, "items": []},
        "proxy": {
            "enabled": True,
            "urls": ["http://u:secret@h1:1", "http://h2:2"],
        },
    }
    yml = tmp_path / "config.yml"
    yml.write_text(yaml.dump(cfg_data))
    cfg = AppConfig(yaml_file=yml)

    logged: list[str] = []

    def fake_write_log(message, level, *args, **kwargs):
        logged.append(message)

    with patch("core.service.writeLog", side_effect=fake_write_log):
        with patch("core.service.init_store"):
            BotService(cfg=cfg)

    assert any("Proxy rotation: enabled, pool_size=2" == m for m in logged), (
        f"Expected exact log line not found. Logged: {logged}"
    )
    for msg in logged:
        assert "secret" not in msg, f"Credential 'secret' leaked into log: {msg}"
        assert "u:" not in msg, f"Credential 'u:' leaked into log: {msg}"
        assert "@h1" not in msg, f"Host credential '@h1' leaked into log: {msg}"


def test_proxy_disabled_no_log(tmp_path):
    """BotService with proxy.enabled=False emits no 'Proxy rotation' line."""
    import yaml
    cfg_data = {
        "debug": {"logging_level": 0, "test_mode": True},
        "available": {"timeout": 10, "items": []},
        "proxy": {"enabled": False, "urls": []},
    }
    yml = tmp_path / "config.yml"
    yml.write_text(yaml.dump(cfg_data))
    cfg = AppConfig(yaml_file=yml)

    logged: list[str] = []

    def fake_write_log(message, level, *args, **kwargs):
        logged.append(message)

    with patch("core.service.writeLog", side_effect=fake_write_log):
        with patch("core.service.init_store"):
            BotService(cfg=cfg)

    assert not any("Proxy rotation" in m for m in logged), (
        f"Unexpected 'Proxy rotation' log line found: {logged}"
    )


# ---------------------------------------------------------------------------
# Task 1: registry.assign_proxy
# ---------------------------------------------------------------------------


def test_registry_assign_proxy_distinct_per_plugin(tmp_path):
    """assign_proxy with a 3-entry pool gives distinct host_ports to pluginA and pluginB."""
    pool = _make_pool([
        "http://u1:p1@host1:3128",
        "http://u2:p2@host2:3128",
        "http://u3:p3@host3:3128",
    ])
    registry = PluginRegistry(config=None, plugins_dir=tmp_path, proxy_pool=pool)

    plugin_a = MagicMock()
    plugin_b = MagicMock()

    registry.assign_proxy(plugin_a)
    registry.assign_proxy(plugin_b)

    # Both get a _proxy and _proxy_required=True
    assert plugin_a._proxy_required is True
    assert plugin_b._proxy_required is True
    assert plugin_a._proxy is not None
    assert plugin_b._proxy is not None
    # Per-instance scoping: distinct host_ports (Pitfall 6)
    assert plugin_a._proxy.host_port != plugin_b._proxy.host_port, (
        "Expected distinct proxies per plugin instance"
    )
    # Both share the same pool
    assert plugin_a._pool is pool
    assert plugin_b._pool is pool


def test_assign_proxy_noop_when_pool_none(tmp_path):
    """assign_proxy with proxy_pool=None leaves _proxy None and _proxy_required False."""
    registry = PluginRegistry(config=None, plugins_dir=tmp_path, proxy_pool=None)
    plugin = MagicMock()

    registry.assign_proxy(plugin)

    assert plugin._proxy is None
    assert plugin._proxy_required is False


def test_assign_proxy_exhausted_sets_required_but_none(tmp_path):
    """Pool with all entries retired: assign_proxy sets _proxy_required True but _proxy None."""
    pool = _make_pool(["http://u:p@h1:1"])
    # Retire the only entry
    entry = pool.advance()
    assert entry is not None
    # Force retirement by maxing out failures
    for _ in range(pool._max_failures):
        pool.record_failure(entry)

    registry = PluginRegistry(config=None, plugins_dir=tmp_path, proxy_pool=pool)
    plugin = MagicMock()
    registry.assign_proxy(plugin)

    assert plugin._proxy_required is True
    assert plugin._proxy is None


# ---------------------------------------------------------------------------
# Task 2: Amazon stealth + proxy + auth + fail-loud + ban-detect
# ---------------------------------------------------------------------------


_amazon_module = _load_plugin("amazon")
AmazonPlugin = _amazon_module.AmazonPlugin
_bestbuy_module = _load_plugin("bestbuy")
BestBuyPlugin = _bestbuy_module.BestBuyPlugin


async def test_amazon_setup_applies_stealth():
    """apply_stealth is awaited on main_tab after nodriver.start, before any tab.get."""
    plugin = AmazonPlugin(config=None)
    tab = _make_tab_mock()
    browser = _make_browser_mock(tab)

    call_order = []

    async def mock_start(**kwargs):
        call_order.append("start")
        return browser

    async def mock_stealth(t):
        call_order.append("stealth")

    async def mock_get(url):
        call_order.append(f"get:{url}")
        return tab

    browser.get = mock_get

    with patch("nodriver.start", side_effect=mock_start):
        with patch("core.stealth.apply_stealth", side_effect=mock_stealth):
            # Monkeypatch the apply_stealth import inside the plugin module
            with patch.object(_amazon_module, "apply_stealth", side_effect=mock_stealth):
                await plugin.setup()

    start_idx = call_order.index("start")
    stealth_idx = call_order.index("stealth")
    assert stealth_idx > start_idx, "apply_stealth must be called after nodriver.start"
    # No "get:" entries before stealth
    get_before = [e for e in call_order[:stealth_idx] if e.startswith("get:")]
    assert not get_before, f"tab.get called before apply_stealth: {call_order}"


async def test_amazon_setup_proxy_enabled_args_and_webrtc():
    """With _proxy assigned, browser_args contains --proxy-server and WebRTC flag."""
    plugin = AmazonPlugin(config=None)
    entry = _make_entry("myproxy.com:3128", "alice", "s3cr3t")
    plugin._proxy = entry
    plugin._proxy_required = True

    tab = _make_tab_mock()
    browser = _make_browser_mock(tab)

    captured_args = {}

    async def mock_start(**kwargs):
        captured_args.update(kwargs)
        return browser

    async def mock_stealth(t):
        pass

    async def mock_auth(t, username, password):
        captured_args["auth_username"] = username
        captured_args["auth_password"] = password

    with patch("nodriver.start", side_effect=mock_start):
        with patch.object(_amazon_module, "apply_stealth", side_effect=mock_stealth):
            with patch.object(_amazon_module, "setup_proxy_auth", side_effect=mock_auth):
                await plugin.setup()

    args = captured_args.get("browser_args", [])
    assert any("--proxy-server=myproxy.com:3128" in a for a in args), (
        f"--proxy-server not found in browser_args: {args}"
    )
    assert any("disable_non_proxied_udp" in a for a in args), (
        f"WebRTC flag not found in browser_args: {args}"
    )
    assert captured_args.get("auth_username") == "alice"
    assert captured_args.get("auth_password") == "s3cr3t"


async def test_amazon_setup_proxy_disabled_no_proxy_args():
    """With _proxy=None and _proxy_required=False, no --proxy-server in args; stealth still runs."""
    plugin = AmazonPlugin(config=None)
    plugin._proxy = None
    plugin._proxy_required = False

    tab = _make_tab_mock()
    browser = _make_browser_mock(tab)

    stealth_called = []
    captured_args = {}

    async def mock_start(**kwargs):
        captured_args.update(kwargs)
        return browser

    async def mock_stealth(t):
        stealth_called.append(True)

    with patch("nodriver.start", side_effect=mock_start):
        with patch.object(_amazon_module, "apply_stealth", side_effect=mock_stealth):
            await plugin.setup()

    args = captured_args.get("browser_args") or []
    assert not any("--proxy-server" in a for a in args), (
        f"--proxy-server unexpectedly in browser_args: {args}"
    )
    assert stealth_called, "apply_stealth must still be called when proxy disabled"


async def test_amazon_setup_fails_loud_when_exhausted():
    """_proxy_required=True + _proxy=None -> setup logs ERROR and raises; nodriver.start NOT called."""
    plugin = AmazonPlugin(config=None)
    plugin._proxy = None
    plugin._proxy_required = True

    start_called = []
    logged_errors = []

    async def mock_start(**kwargs):
        start_called.append(True)
        return MagicMock()

    def fake_write_log(message, level, *args, **kwargs):
        if level == "ERROR":
            logged_errors.append(message)

    with patch("nodriver.start", side_effect=mock_start):
        with patch.object(_amazon_module, "writeLog", side_effect=fake_write_log):
            with pytest.raises((RuntimeError, Exception)):
                await plugin.setup()

    assert not start_called, "nodriver.start must NOT be called when pool exhausted"
    assert logged_errors, "ERROR must be logged when pool exhausted"


async def test_amazon_ban_signal_records_failure():
    """check_availability with a ban body calls pool.record_failure(proxy) once; no mid-session teardown."""
    plugin = AmazonPlugin(config=None)

    tab = _make_tab_mock()
    browser = _make_browser_mock(tab)
    plugin.driver = browser

    entry = _make_entry()
    pool = MagicMock()
    pool.record_failure = MagicMock()
    plugin._proxy = entry
    plugin._pool = pool

    # Simulate a ban response body via evaluate returning ban phrase
    async def mock_get(url):
        return tab

    browser.get = mock_get

    # Make select return None (no add-to-cart found) so check returns False
    async def mock_select(selector, timeout=10):
        return None

    tab.select = mock_select
    tab.evaluate = AsyncMock(return_value="access denied - bot detected")

    with patch.object(_amazon_module, "_is_ban_response", return_value=True):
        result = await plugin.check_availability("https://www.amazon.com/dp/TEST")

    pool.record_failure.assert_called_once_with(entry)
    # No teardown called (restart-only rotation)
    assert not hasattr(plugin, "_setup_count") or getattr(plugin, "_setup_count", 0) == 0


# ---------------------------------------------------------------------------
# Task 2: BestBuy mirrors
# ---------------------------------------------------------------------------


async def test_bestbuy_setup_applies_stealth():
    """apply_stealth is awaited on main_tab after nodriver.start, before any tab.get."""
    plugin = BestBuyPlugin(config=None)
    tab = _make_tab_mock()
    browser = _make_browser_mock(tab)

    call_order = []

    async def mock_start(**kwargs):
        call_order.append("start")
        return browser

    async def mock_stealth(t):
        call_order.append("stealth")

    with patch("nodriver.start", side_effect=mock_start):
        with patch.object(_bestbuy_module, "apply_stealth", side_effect=mock_stealth):
            await plugin.setup()

    start_idx = call_order.index("start")
    stealth_idx = call_order.index("stealth")
    assert stealth_idx > start_idx


async def test_bestbuy_setup_proxy_enabled_args_and_webrtc():
    """BestBuy: proxy entry -> browser_args has --proxy-server and WebRTC flag."""
    plugin = BestBuyPlugin(config=None)
    entry = _make_entry("bbproxy.com:8080", "bob", "passwd")
    plugin._proxy = entry
    plugin._proxy_required = True

    tab = _make_tab_mock()
    browser = _make_browser_mock(tab)
    captured_args = {}

    async def mock_start(**kwargs):
        captured_args.update(kwargs)
        return browser

    async def mock_auth(t, username, password):
        captured_args["auth_username"] = username

    with patch("nodriver.start", side_effect=mock_start):
        with patch.object(_bestbuy_module, "apply_stealth", AsyncMock()):
            with patch.object(_bestbuy_module, "setup_proxy_auth", side_effect=mock_auth):
                await plugin.setup()

    args = captured_args.get("browser_args", [])
    assert any("--proxy-server=bbproxy.com:8080" in a for a in args)
    assert any("disable_non_proxied_udp" in a for a in args)
    assert captured_args.get("auth_username") == "bob"


async def test_bestbuy_setup_proxy_disabled_no_proxy_args():
    """BestBuy: no proxy -> no --proxy-server; stealth still runs."""
    plugin = BestBuyPlugin(config=None)
    plugin._proxy = None
    plugin._proxy_required = False

    tab = _make_tab_mock()
    browser = _make_browser_mock(tab)
    stealth_called = []
    captured_args = {}

    async def mock_start(**kwargs):
        captured_args.update(kwargs)
        return browser

    with patch("nodriver.start", side_effect=mock_start):
        with patch.object(_bestbuy_module, "apply_stealth", AsyncMock(side_effect=lambda t: stealth_called.append(True))):
            await plugin.setup()

    args = captured_args.get("browser_args") or []
    assert not any("--proxy-server" in a for a in args)
    assert stealth_called


async def test_bestbuy_setup_fails_loud_when_exhausted():
    """BestBuy: _proxy_required=True + _proxy=None -> ERROR + raise + nodriver.start NOT called."""
    plugin = BestBuyPlugin(config=None)
    plugin._proxy = None
    plugin._proxy_required = True

    start_called = []

    async def mock_start(**kwargs):
        start_called.append(True)
        return MagicMock()

    with patch("nodriver.start", side_effect=mock_start):
        with patch.object(_bestbuy_module, "writeLog", MagicMock()):
            with pytest.raises((RuntimeError, Exception)):
                await plugin.setup()

    assert not start_called


# ---------------------------------------------------------------------------
# Task 3: Phase-6 plugins (walmart, target, gamestop, squareenix, newegg)
# ---------------------------------------------------------------------------


_walmart_module = _load_plugin("walmart")
WalmartPlugin = _walmart_module.WalmartPlugin
_target_module = _load_plugin("target")
TargetPlugin = _target_module.TargetPlugin
_gamestop_module = _load_plugin("gamestop")
GameStopPlugin = _gamestop_module.GameStopPlugin
_squareenix_module = _load_plugin("squareenix")
SquareEnixPlugin = _squareenix_module.SquareEnixPlugin
_newegg_module = _load_plugin("newegg")
NeweggPlugin = _newegg_module.NeweggPlugin


def _phase6_cases():
    """Return list of (plugin_class, module, platform_key) tuples for Phase-6 plugins."""
    return [
        (WalmartPlugin, _walmart_module, "walmart"),
        (TargetPlugin, _target_module, "target"),
        (GameStopPlugin, _gamestop_module, "gamestop"),
        (SquareEnixPlugin, _squareenix_module, "squareenix"),
        (NeweggPlugin, _newegg_module, "newegg"),
    ]


def _make_phase6_config(platform_key, headless=True, user_agents=None):
    cfg = MagicMock()
    platform_cfg = MagicMock()
    platform_cfg.headless = headless
    platform_cfg.user_agents = user_agents if user_agents is not None else ["Mozilla/5.0 (test)"]
    setattr(cfg.platforms, platform_key, platform_cfg)
    return cfg


@pytest.mark.parametrize("plugin_cls,mod,pkey", _phase6_cases())
async def test_phase6_setup_applies_stealth(plugin_cls, mod, pkey):
    """Each Phase-6 plugin awaits apply_stealth after nodriver.start, before navigation."""
    plugin = plugin_cls(config=_make_phase6_config(pkey))
    tab = _make_tab_mock()
    browser = _make_browser_mock(tab)

    call_order = []

    async def mock_start(**kwargs):
        call_order.append("start")
        return browser

    async def mock_stealth(t):
        call_order.append("stealth")

    with patch("nodriver.start", side_effect=mock_start):
        with patch.object(mod, "apply_stealth", side_effect=mock_stealth):
            await plugin.setup()

    assert "start" in call_order
    assert "stealth" in call_order
    start_idx = call_order.index("start")
    stealth_idx = call_order.index("stealth")
    assert stealth_idx > start_idx, f"{plugin_cls.__name__}: stealth must come after start"


@pytest.mark.parametrize("plugin_cls,mod,pkey", _phase6_cases())
async def test_phase6_setup_merges_proxy_with_ua(plugin_cls, mod, pkey):
    """Phase-6 plugin with proxy: browser_args has --user-agent AND --proxy-server AND WebRTC."""
    plugin = plugin_cls(config=_make_phase6_config(pkey, user_agents=["Mozilla/5.0 TestUA"]))
    entry = _make_entry("proxyfarm.com:9090", "user", "pw")
    plugin._proxy = entry
    plugin._proxy_required = True

    tab = _make_tab_mock()
    browser = _make_browser_mock(tab)
    captured_args = {}

    async def mock_start(**kwargs):
        captured_args.update(kwargs)
        return browser

    with patch("nodriver.start", side_effect=mock_start):
        with patch.object(mod, "apply_stealth", AsyncMock()):
            with patch.object(mod, "setup_proxy_auth", AsyncMock()):
                await plugin.setup()

    args = captured_args.get("browser_args", [])
    assert any("--user-agent" in a for a in args), f"{plugin_cls.__name__}: --user-agent missing"
    assert any("--proxy-server=proxyfarm.com:9090" in a for a in args), (
        f"{plugin_cls.__name__}: --proxy-server missing"
    )
    assert any("disable_non_proxied_udp" in a for a in args), (
        f"{plugin_cls.__name__}: WebRTC flag missing"
    )


@pytest.mark.parametrize("plugin_cls,mod,pkey", _phase6_cases())
async def test_phase6_setup_proxy_disabled_keeps_ua_only(plugin_cls, mod, pkey):
    """Phase-6 plugin without proxy: --user-agent present, no --proxy-server; stealth runs."""
    plugin = plugin_cls(config=_make_phase6_config(pkey, user_agents=["Mozilla/5.0 TestUA"]))
    plugin._proxy = None
    plugin._proxy_required = False

    tab = _make_tab_mock()
    browser = _make_browser_mock(tab)
    stealth_called = []
    captured_args = {}

    async def mock_start(**kwargs):
        captured_args.update(kwargs)
        return browser

    with patch("nodriver.start", side_effect=mock_start):
        with patch.object(mod, "apply_stealth", AsyncMock(side_effect=lambda t: stealth_called.append(True))):
            await plugin.setup()

    args = captured_args.get("browser_args", [])
    assert any("--user-agent" in a for a in args), f"{plugin_cls.__name__}: --user-agent missing"
    assert not any("--proxy-server" in a for a in args), (
        f"{plugin_cls.__name__}: --proxy-server should not appear when proxy disabled"
    )
    assert stealth_called


@pytest.mark.parametrize("plugin_cls,mod,pkey", _phase6_cases())
async def test_phase6_fails_loud_when_exhausted(plugin_cls, mod, pkey):
    """Phase-6: _proxy_required=True + _proxy=None -> ERROR + raise + nodriver.start NOT called."""
    plugin = plugin_cls(config=_make_phase6_config(pkey))
    plugin._proxy = None
    plugin._proxy_required = True

    start_called = []

    async def mock_start(**kwargs):
        start_called.append(True)
        return MagicMock()

    with patch("nodriver.start", side_effect=mock_start):
        with patch.object(mod, "writeLog", MagicMock()):
            with pytest.raises((RuntimeError, Exception)):
                await plugin.setup()

    assert not start_called, f"{plugin_cls.__name__}: nodriver.start must NOT be called when pool exhausted"
