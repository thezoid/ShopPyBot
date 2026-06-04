import asyncio

import pytest
import yaml
from unittest.mock import AsyncMock, MagicMock

# ---------------------------------------------------------------------------
# keyring import guard: keyring is installed in plan 08-02; guard here so
# conftest.py loads cleanly in plan 08-01 before keyring is available.
# ---------------------------------------------------------------------------
try:
    import keyring as _keyring_module
    import keyring.core as _keyring_core

    class _DictKeyring(_keyring_module.backend.KeyringBackend):
        """In-memory keyring for testing. No filesystem or OS interaction."""

        priority = 1

        def __init__(self):
            self._data: dict = {}

        def get_password(self, service, username):
            return self._data.get((service, username))

        def set_password(self, service, username, password):
            self._data[(service, username)] = password

        def delete_password(self, service, username):
            self._data.pop((service, username), None)

    _KEYRING_AVAILABLE = True
except ImportError:
    _KEYRING_AVAILABLE = False


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


@pytest.fixture
def fake_plugin():
    """Factory fixture: returns a builder fn that creates a no-browser RetailerPlugin.

    Usage:
        plugin = fake_plugin(domains=["ex.com"], available=True, bought=False)

    The returned instance subclasses RetailerPlugin with AsyncMock setup/teardown
    and async check_availability/auto_buy that return the configured values. No real
    browser is launched. Downstream tests may attach asyncio.Event attributes
    (captcha_event, passkey_event, otp_event, test_pause_event) as needed.
    """
    from core.plugin_base import RetailerPlugin

    def _build(domains=None, available=True, bought=False, config=None):
        class _FakePlugin(RetailerPlugin):
            domain_patterns = domains or ["fake.example.com"]

            async def check_availability(self, url: str) -> bool:
                return available

            async def auto_buy(self, url: str) -> bool:
                return bought

        instance = _FakePlugin(config=config)
        instance.setup = AsyncMock()
        instance.teardown = AsyncMock()
        return instance

    return _build


@pytest.fixture
def fake_notifier():
    """Factory fixture: returns a builder that creates a configurable Notifier subclass.

    Usage:
        notifier = fake_notifier()           # records calls, never raises
        notifier = fake_notifier(raises=ValueError("boom"))  # raises on send

    The returned instance is a concrete Notifier subclass whose send() appends
    each event to notifier.events and optionally raises a pre-configured exception.
    """
    from notifications.base import Notifier, NotificationEvent

    def _build(raises: Exception | None = None):
        class _FakeNotifier(Notifier):
            def __init__(self):
                self.events: list[NotificationEvent] = []
                self._raises = raises

            async def send(self, event: NotificationEvent) -> None:
                self.events.append(event)
                if self._raises is not None:
                    raise self._raises

        return _FakeNotifier()

    return _build


@pytest.fixture
def notification_event():
    """Factory fixture: builds a NotificationEvent with sensible defaults.

    Usage:
        event = notification_event()
        event = notification_event(action="purchased", platform="BestBuy")
    """
    from notifications.base import NotificationEvent
    from datetime import datetime, timezone

    def _build(
        item_name: str = "Test Widget",
        item_url: str = "https://example.com/widget",
        platform: str = "Amazon",
        timestamp: datetime | None = None,
        action: str = "detected",
    ) -> NotificationEvent:
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        return NotificationEvent(
            item_name=item_name,
            item_url=item_url,
            platform=platform,
            timestamp=timestamp,
            action=action,
        )

    return _build


@pytest.fixture
def mock_nodriver_start():
    """Patch nodriver.start so it never launches Chrome.

    Yields a recorder object with:
        .last_kwargs  -- the kwargs from the most recent nodriver.start() call
        .calls        -- list of all kwargs dicts from every call made

    Usage in a plugin test:
        async def test_setup_headless(mock_nodriver_start, fake_browser):
            mock_nodriver_start.browser = fake_browser
            await plugin.setup()
            assert mock_nodriver_start.last_kwargs.get("headless") is True
    """
    from unittest.mock import AsyncMock, patch, MagicMock

    class _Recorder:
        def __init__(self):
            self.calls: list[dict] = []
            self.last_kwargs: dict = {}
            self.browser = MagicMock()

    recorder = _Recorder()

    async def _fake_start(*args, **kwargs):
        recorder.calls.append(kwargs)
        recorder.last_kwargs = kwargs
        return recorder.browser

    with patch("nodriver.start", new=_fake_start):
        yield recorder


@pytest.fixture
def event_shim():
    """Fixture returning a helper that simulates the stdin listener thread.

    The real _stdin_listener_thread uses loop.call_soon_threadsafe(event.set)
    as the only thread-safe bridge (RESEARCH Pitfall 1). This shim replicates
    that exact call so downstream tests can drive asyncio.Events from sync code
    and prove a waiting coroutine resumes correctly.

    Usage:
        shim = event_shim  # the fixture value IS the helper function
        event = asyncio.Event()
        loop = asyncio.get_event_loop()
        shim(event, loop)    # fires event from thread-safe bridge
        await event.wait()   # would have unblocked
    """

    def _fire(event: asyncio.Event, loop: asyncio.AbstractEventLoop) -> None:
        """Signal event via the thread-safe bridge used by _stdin_listener_thread."""
        loop.call_soon_threadsafe(event.set)

    return _fire


# ---------------------------------------------------------------------------
# Phase 8: credential store test fixtures (RESEARCH Pitfall 1 + Pattern 8)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=False)
def reset_credential_store():
    """Restore the module-level _store singleton between tests.

    Prevents singleton bleed when one test calls init_store() and the next
    test expects the lazy-fallback EnvVarBackend (RESEARCH Pitfall 1).
    """
    from core import credentials

    original = credentials._store
    yield
    credentials._store = original


@pytest.fixture(autouse=False)
def isolated_keyring():
    """Swap the OS keyring with an in-memory _DictKeyring for the test duration.

    Skips if keyring is not yet installed (plan 08-01 pre-condition); will run
    normally once keyring is installed in plan 08-02.
    """
    if not _KEYRING_AVAILABLE:
        pytest.skip("keyring not installed (available after plan 08-02)")

    kb = _DictKeyring()
    _keyring_module.set_keyring(kb)
    yield kb
    _keyring_core._keyring_backend = None
