"""Contract + mocked-driver tests for BestBuyPlugin (PLG-02, PLG-03).

All tests monkeypatch external dependencies so no real Chrome process spawns
and selenium need not be installed. The plugin module is loaded via
`importlib.util.spec_from_file_location` because `plugins/` is intentionally
not a Python package (registry semantics).
"""
import ast
import importlib.util
import inspect
import pathlib
import sys
import types

import pytest

PLUGIN_FILE = (
    pathlib.Path(__file__).resolve().parents[1]
    / "plugins"
    / "shopbot_plugin_bestbuy.py"
)


def _install_selenium_stubs(monkeypatch):
    selenium = types.ModuleType("selenium")
    webdriver = types.ModuleType("selenium.webdriver")
    common = types.ModuleType("selenium.webdriver.common")
    by_mod = types.ModuleType("selenium.webdriver.common.by")
    support = types.ModuleType("selenium.webdriver.support")
    ui = types.ModuleType("selenium.webdriver.support.ui")
    ec = types.ModuleType("selenium.webdriver.support.expected_conditions")

    class _By:
        ID = "id"
        XPATH = "xpath"
        CLASS_NAME = "class name"

    class _WebDriverWait:
        def __init__(self, driver, timeout):
            self.driver = driver
            self.timeout = timeout

        def until(self, condition):
            raise RuntimeError("WebDriverWait stub - tests must not exercise selenium")

    def _presence(locator):
        return locator

    by_mod.By = _By
    ui.WebDriverWait = _WebDriverWait
    ec.presence_of_element_located = _presence

    for name, mod in [
        ("selenium", selenium),
        ("selenium.webdriver", webdriver),
        ("selenium.webdriver.common", common),
        ("selenium.webdriver.common.by", by_mod),
        ("selenium.webdriver.support", support),
        ("selenium.webdriver.support.ui", ui),
        ("selenium.webdriver.support.expected_conditions", ec),
    ]:
        monkeypatch.setitem(sys.modules, name, mod)


def _install_driver_stub(monkeypatch, sentinel):
    fake_driver = types.ModuleType("driver")
    fake_driver.build_driver = lambda *a, **kw: sentinel
    monkeypatch.setitem(sys.modules, "driver", fake_driver)


def _load_bestbuy_module(monkeypatch):
    sentinel = object()
    _install_selenium_stubs(monkeypatch)
    _install_driver_stub(monkeypatch, sentinel)
    sys.modules.pop("test_bestbuy_plugin_load", None)
    spec = importlib.util.spec_from_file_location(
        "test_bestbuy_plugin_load", PLUGIN_FILE
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module, sentinel


@pytest.fixture
def bestbuy_plugin_cls(monkeypatch):
    module, sentinel = _load_bestbuy_module(monkeypatch)
    return module.BestBuyPlugin, sentinel


class _DummyCreds:
    email = "test@example.com"
    password = "pw"


class _DummyPlatform:
    credentials = _DummyCreds()


def test_bestbuy_plugin_subclasses_retailer_plugin(bestbuy_plugin_cls):
    from plugin_base import RetailerPlugin
    cls, _ = bestbuy_plugin_cls
    assert issubclass(cls, RetailerPlugin)


def test_bestbuy_plugin_domain_pattern(bestbuy_plugin_cls):
    cls, _ = bestbuy_plugin_cls
    assert cls.domain_pattern == ["bestbuy.com"]


def test_bestbuy_plugin_login_at_startup_true(bestbuy_plugin_cls):
    cls, _ = bestbuy_plugin_cls
    assert cls.login_at_startup is True


def test_bestbuy_plugin_name_is_bestbuy(bestbuy_plugin_cls):
    cls, _ = bestbuy_plugin_cls
    assert cls.name == "bestbuy"


def test_bestbuy_plugin_owns_driver(bestbuy_plugin_cls):
    cls, sentinel = bestbuy_plugin_cls
    plugin = cls(_DummyPlatform(), driver_path="ignored")
    assert plugin.driver is sentinel


def test_bestbuy_plugin_check_availability_signature(bestbuy_plugin_cls):
    cls, _ = bestbuy_plugin_cls
    params = list(inspect.signature(cls.check_availability).parameters.keys())
    assert params == ["self", "url"]


def test_bestbuy_plugin_auto_buy_signature(bestbuy_plugin_cls):
    cls, _ = bestbuy_plugin_cls
    params = list(inspect.signature(cls.auto_buy).parameters.keys())
    assert params == ["self", "url", "config"]


def test_bestbuy_plugin_detect_captcha_not_overridden(bestbuy_plugin_cls):
    from plugin_base import RetailerPlugin
    cls, _ = bestbuy_plugin_cls
    assert cls.detect_captcha is RetailerPlugin.detect_captcha


def test_bestbuy_plugin_calls_update_item_purchased_on_success():
    """PLG-02 fix: update_item_purchased must be called inside the BestBuyPlugin
    class (auto_buy may delegate to a helper method, so accept any call site)."""
    tree = ast.parse(PLUGIN_FILE.read_text(encoding="utf-8"))
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "BestBuyPlugin":
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    func = sub.func
                    if isinstance(func, ast.Name) and func.id == "update_item_purchased":
                        found = True
                        break
                    if isinstance(func, ast.Attribute) and func.attr == "update_item_purchased":
                        found = True
                        break
    assert found, "update_item_purchased not called inside BestBuyPlugin (PLG-02 regression)"


def test_bestbuy_plugin_login_reads_credentials_from_platform_config():
    """AST walk: login() must access self.platform_config.credentials.email/.password."""
    tree = ast.parse(PLUGIN_FILE.read_text(encoding="utf-8"))
    login_fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "login":
            login_fn = node
            break
    assert login_fn is not None, "login method not found"
    saw_email = False
    saw_password = False
    for sub in ast.walk(login_fn):
        if isinstance(sub, ast.Attribute) and sub.attr in ("email", "password"):
            inner = sub.value
            if (
                isinstance(inner, ast.Attribute)
                and inner.attr == "credentials"
                and isinstance(inner.value, ast.Attribute)
                and inner.value.attr == "platform_config"
            ):
                if sub.attr == "email":
                    saw_email = True
                if sub.attr == "password":
                    saw_password = True
    assert saw_email, "login does not read self.platform_config.credentials.email"
    assert saw_password, "login does not read self.platform_config.credentials.password"


def test_bestbuy_plugin_no_config_singleton_import():
    source = PLUGIN_FILE.read_text(encoding="utf-8")
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("from config import") or stripped.startswith("import config"):
            pytest.fail(f"Forbidden config import: {line!r}")


def test_bestbuyPassesHeadlessAndUserAgentsToBuildDriver(monkeypatch):
    """ANTI-02 + ANTI-03: BestBuy threads headless + user_agents to build_driver."""
    sentinel = object()
    _install_selenium_stubs(monkeypatch)

    buildCalls = []
    fake_driver = types.ModuleType("driver")

    def _trackedBuild(*a, **kw):
        buildCalls.append((a, kw))
        return sentinel

    fake_driver.build_driver = _trackedBuild
    monkeypatch.setitem(sys.modules, "driver", fake_driver)

    sys.modules.pop("test_bestbuy_ua_load", None)
    spec = importlib.util.spec_from_file_location(
        "test_bestbuy_ua_load", PLUGIN_FILE,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    class _Platform:
        credentials = _DummyCreds()
        headless = True

    uas = ["BB-UA-1", "BB-UA-2"]
    module.BestBuyPlugin(_Platform(), driver_path="x", user_agents=uas)
    assert len(buildCalls) == 1
    _, kw = buildCalls[0]
    assert kw.get("headless") is True
    assert kw.get("user_agents") == uas


def test_bestbuy_plugin_no_positional_credential_args():
    """login and auto_buy must NOT have parameters named email/password/cvv."""
    tree = ast.parse(PLUGIN_FILE.read_text(encoding="utf-8"))
    forbidden = {"email", "password", "cvv"}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in ("login", "auto_buy"):
            params = {a.arg for a in node.args.args}
            bad = params & forbidden
            assert not bad, f"{node.name} has forbidden positional params: {bad}"
