import pytest
import yaml
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def tmp_config_yml(tmp_path):
    """Write a minimal valid config.yml to tmp_path and return its Path."""
    cfg = {
        "debug": {"logging_level": 3, "test_mode": True},
        "available": {"timeout": 10, "items": []},
        "platforms": {
            "amazon": {"delay_seconds": 30.0},
            "bestbuy": {"delay_seconds": 30.0},
        },
    }
    config_file = tmp_path / "config.yml"
    config_file.write_text(yaml.dump(cfg))
    return config_file


@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    """Redirect models.DB_PATH to a temp directory so tests don't need data/."""
    import models
    monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "shop_py_bot.db"))
    return tmp_path


async def test_asyncio_smoke():
    """Confirm asyncio_mode=auto runs async def tests (RESEARCH Pitfall 5 gate)."""
    pass


@pytest.fixture
def fake_browser():
    """Return a mock nodriver Browser whose .get() returns a fake Tab.

    Fake Tab exposes select, select_all, find as AsyncMocks and main_tab.
    Fake Element exposes click and send_keys as AsyncMocks.
    Browser.stop is a plain MagicMock (sync per nodriver Browser.stop() semantics).
    """
    fake_element = MagicMock()
    fake_element.click = AsyncMock()
    fake_element.send_keys = AsyncMock()

    fake_tab = MagicMock()
    fake_tab.select = AsyncMock(return_value=fake_element)
    fake_tab.select_all = AsyncMock(return_value=[fake_element])
    fake_tab.find = AsyncMock(return_value=fake_element)
    fake_tab.main_tab = fake_tab

    browser = MagicMock()
    browser.get = AsyncMock(return_value=fake_tab)
    browser.stop = MagicMock()
    browser.main_tab = fake_tab

    return browser


@pytest.fixture
def tmp_plugins_dir(tmp_path):
    """Return a plugins dir containing one valid shopbot_plugin_fake.py file.

    Wave 2 registry tests import this fixture to drive discovery and routing
    without touching real plugin files.
    """
    plugin_code = (
        "from core.plugin_base import RetailerPlugin\n"
        "\n"
        "\n"
        "class FakePlugin(RetailerPlugin):\n"
        "    domain_patterns = [\"fake.com\"]\n"
        "\n"
        "    async def check_availability(self, url):\n"
        "        return True\n"
        "\n"
        "    async def auto_buy(self, url):\n"
        "        return False\n"
    )
    (tmp_path / "shopbot_plugin_fake.py").write_text(plugin_code)
    return tmp_path
