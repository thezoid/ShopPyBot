"""Contract + mocked-driver tests for AmazonPlugin (PLG-01, PLG-03).

All tests monkeypatch external dependencies so no real Chrome process spawns
and pygame/selenium need not be installed in the test environment. The plugin
module is loaded via `importlib.util.spec_from_file_location` because
`plugins/` is intentionally not a Python package (registry semantics).
"""
import ast
import importlib.util
import inspect
import pathlib
import sys
import types

import pytest

PLUGIN_FILE = pathlib.Path(__file__).resolve().parents[1] / "plugins" / "shopbot_plugin_amazon.py"


def _install_selenium_stubs(monkeypatch):
    """Inject minimal selenium.* modules so the plugin's top-level imports succeed."""
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


def _install_pygame_stub(monkeypatch):
    """utils.py imports pygame at module load. Stub it so `from utils import ...` works."""
    pygame = types.ModuleType("pygame")
    mixer = types.ModuleType("pygame.mixer")

    def _noop(*a, **kw):
        return None

    mixer.init = _noop

    class _Music:
        def load(self, *a, **kw):
            return None

        def play(self, *a, **kw):
            return None

    mixer.music = _Music()
    pygame.mixer = mixer
    monkeypatch.setitem(sys.modules, "pygame", pygame)
    monkeypatch.setitem(sys.modules, "pygame.mixer", mixer)


def _install_driver_stub(monkeypatch, sentinel):
    """Replace the `driver` module with a stub whose build_driver returns sentinel."""
    fake_driver = types.ModuleType("driver")
    fake_driver.build_driver = lambda *a, **kw: sentinel
    monkeypatch.setitem(sys.modules, "driver", fake_driver)


def _load_amazon_module(monkeypatch):
    sentinel = object()
    _install_selenium_stubs(monkeypatch)
    _install_pygame_stub(monkeypatch)
    _install_driver_stub(monkeypatch, sentinel)
    # Drop any cached load so we re-exec under the current monkeypatches.
    sys.modules.pop("test_amazon_plugin_load", None)
    spec = importlib.util.spec_from_file_location(
        "test_amazon_plugin_load", PLUGIN_FILE
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module, sentinel


@pytest.fixture
def amazon_plugin_cls(monkeypatch):
    module, sentinel = _load_amazon_module(monkeypatch)
    return module.AmazonPlugin, sentinel


class _DummyCreds:
    email = "test@example.com"
    password = "pw"


class _DummyPlatform:
    credentials = _DummyCreds()


def test_amazon_plugin_subclasses_retailer_plugin(amazon_plugin_cls):
    from plugin_base import RetailerPlugin
    cls, _ = amazon_plugin_cls
    assert issubclass(cls, RetailerPlugin)


def test_amazon_plugin_domain_pattern(amazon_plugin_cls):
    cls, _ = amazon_plugin_cls
    assert cls.domain_pattern == ["amazon.com", "amzn.to"]


def test_amazon_plugin_login_at_startup_true(amazon_plugin_cls):
    cls, _ = amazon_plugin_cls
    assert cls.login_at_startup is True


def test_amazon_plugin_name_is_amazon(amazon_plugin_cls):
    cls, _ = amazon_plugin_cls
    assert cls.name == "amazon"


def test_amazon_plugin_owns_driver(amazon_plugin_cls):
    cls, sentinel = amazon_plugin_cls
    plugin = cls(_DummyPlatform(), driver_path="ignored")
    assert plugin.driver is sentinel


def test_amazon_plugin_construct_uses_platform_config(amazon_plugin_cls):
    cls, _ = amazon_plugin_cls
    platform = _DummyPlatform()
    plugin = cls(platform, driver_path="ignored")
    assert plugin.platform_config is platform


def test_amazon_plugin_check_availability_signature(amazon_plugin_cls):
    cls, _ = amazon_plugin_cls
    params = list(inspect.signature(cls.check_availability).parameters.keys())
    assert params == ["self", "url"]


def test_amazon_plugin_auto_buy_signature(amazon_plugin_cls):
    cls, _ = amazon_plugin_cls
    params = list(inspect.signature(cls.auto_buy).parameters.keys())
    assert params == ["self", "url", "config"]


def test_amazon_plugin_detect_captcha_overridden(amazon_plugin_cls):
    from plugin_base import RetailerPlugin
    cls, _ = amazon_plugin_cls
    assert cls.detect_captcha is not RetailerPlugin.detect_captcha


def test_amazon_plugin_calls_update_item_purchased_on_success():
    """AST grep: update_item_purchased must be called inside the AmazonPlugin
    class (auto_buy delegates to helper methods, so accept any method call site)."""
    tree = ast.parse(PLUGIN_FILE.read_text(encoding="utf-8"))
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "AmazonPlugin":
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    func = sub.func
                    if isinstance(func, ast.Name) and func.id == "update_item_purchased":
                        found = True
                        break
                    if isinstance(func, ast.Attribute) and func.attr == "update_item_purchased":
                        found = True
                        break
    assert found, "update_item_purchased not called inside AmazonPlugin"


def test_amazon_plugin_no_config_singleton_import():
    """Anti-pattern guard: plugins must not `from config import ...`."""
    source = PLUGIN_FILE.read_text(encoding="utf-8")
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("from config import") or stripped.startswith("import config"):
            pytest.fail(f"Forbidden config import found: {line!r}")
