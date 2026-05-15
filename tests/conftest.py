import os
from typing import Callable
from unittest.mock import AsyncMock, MagicMock

import pytest

from plugin_base import RetailerPlugin


@pytest.fixture
def fakeBrowser():
    """AsyncMock shaped to mimic a nodriver Browser/Tab for Wave 1 plugin tests.

    Exposes the methods Wave 1 plugins exercise: get, stop, select, select_all.
    Each test gets a fresh AsyncMock so call counts are isolated.
    """
    browser = AsyncMock()
    browser.get = AsyncMock()
    browser.stop = AsyncMock()
    browser.select = AsyncMock()
    browser.select_all = AsyncMock()
    return browser


@pytest.fixture
def clean_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("SHOPBOT_"):
            monkeypatch.delenv(key, raising=False)
    return monkeypatch


@pytest.fixture
def tmp_config_yml(tmp_path, monkeypatch):
    cfg = tmp_path / "config.yml"
    cfg.write_text(
        "selenium:\n  driver_path: ./chromedriver.exe\n"
        "debug:\n  logging_level: 3\n  test_mode: true\n"
        "open_browser: false\n"
        "platforms:\n  amazon:\n    enabled: true\n    credentials:\n      email: ''\n      password: ''\n"
        "available:\n  items: []\n"
    )
    monkeypatch.chdir(tmp_path)
    return cfg


@pytest.fixture
def tmp_plugins_dir(tmp_path):
    """Empty plugins/ dir for registry discovery tests."""
    d = tmp_path / "plugins"
    d.mkdir()
    return d


@pytest.fixture
def tmpDbPath(tmp_path, monkeypatch):
    """Redirect models.DB_PATH to a per-test sqlite file (Phase 4 async fixtures)."""
    dbPath = tmp_path / "shop_py_bot.db"
    monkeypatch.setattr("models.DB_PATH", str(dbPath))
    return dbPath


@pytest.fixture
def appConfigStub():
    """Minimal AppConfig-shaped namespace for orchestrator tests (Phase 4)."""
    class _Debug:
        logging_level = 0
        test_mode = True

    class _App:
        # Tight loop in tests; real default is 5.0.
        delay = 0.0

    class _Available:
        items: list = []

    class _Cfg:
        debug = _Debug()
        app = _App()
        open_browser = False
        available = _Available()

    return _Cfg()


@pytest.fixture
def fakePluginFactory() -> Callable[..., RetailerPlugin]:
    """Build minimal RetailerPlugin subclasses with controllable behavior (Phase 4)."""
    def _make(*, name: str = "fake",
              checkReturns: bool = False,
              checkRaises: Exception | None = None,
              autoBuyRaises: Exception | None = None) -> RetailerPlugin:
        class _FakePlugin(RetailerPlugin):
            domain_pattern = [f"{name}.example"]

            def __init__(self) -> None:
                super().__init__(platform_config=None)
                self.driver = MagicMock()
                self.checkCalls = 0
                self.autoBuyCalls = 0

            def check_availability(self, url: str) -> bool:
                self.checkCalls += 1
                if checkRaises is not None:
                    raise checkRaises
                return checkReturns

            def auto_buy(self, url: str, config) -> bool:
                self.autoBuyCalls += 1
                if autoBuyRaises is not None:
                    raise autoBuyRaises
                return True

        inst = _FakePlugin()
        inst.name = name
        return inst

    return _make


@pytest.fixture
def fakeNotifierFactory():
    """Build minimal Notifier subclasses with controllable send() behavior (Phase 5)."""
    from notifier_base import Notifier

    def _make(*, name: str = "fakeNotifier",
              enabled: bool = True,
              sendRaises: Exception | None = None,
              sendRecorder: list | None = None):
        class _FakeNotifier(Notifier):
            def __init__(self) -> None:
                self.name = name
                self.enabled = enabled
                self.sendCalls = 0

            async def send(self, event) -> None:
                self.sendCalls += 1
                if sendRecorder is not None:
                    sendRecorder.append((self.name, event))
                if sendRaises is not None:
                    raise sendRaises

        return _FakeNotifier()

    return _make
