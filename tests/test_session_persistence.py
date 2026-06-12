"""Integration tests for Phase 23 session persistence (REL-04).

Covers:
- _dicts_to_cookie_params round-trip: type, SameSite enum, TimeSinceEpoch, expiry filter
- restore_session() returns True and uses raw CDP set_cookies path
- restore_session() returns False when disabled / no passphrase
- save_session() writes an encrypted file when enabled
- save_session() is a no-op when disabled or passphrase absent
"""

import time

import pytest
from unittest.mock import AsyncMock, MagicMock

from nodriver.cdp import network as cdp_network
from nodriver.cdp import storage as cdp_storage

from core.plugin_base import RetailerPlugin, _dicts_to_cookie_params
from core.session_store import SessionStore


# ---------------------------------------------------------------------------
# Minimal plugin subclass for tests
# ---------------------------------------------------------------------------

def _make_plugin(config, fake_tab):
    """Build a concrete RetailerPlugin subclass with platform_key='amazon' and fake tab."""

    class _TestPlugin(RetailerPlugin):
        domain_patterns = ["test.example.com"]
        platform_key = "amazon"

        async def check_availability(self, url: str) -> bool:
            return True

        async def auto_buy(self, url: str) -> bool:
            return False

        def get_active_tab(self):
            return fake_tab

    return _TestPlugin(config=config)


def _make_config(session_persistence: bool):
    """Return a minimal config mock with platforms.amazon.session_persistence set."""
    amazon_cfg = MagicMock()
    amazon_cfg.session_persistence = session_persistence
    platforms = MagicMock()
    platforms.amazon = amazon_cfg
    config = MagicMock()
    config.platforms = platforms
    return config


def _make_fake_tab():
    """Return a fake tab whose send() is an AsyncMock."""
    tab = MagicMock()
    tab.send = AsyncMock()
    return tab


# ---------------------------------------------------------------------------
# Task 1: _dicts_to_cookie_params round-trip
# ---------------------------------------------------------------------------

def test_cookie_param_roundtrip():
    """CookieParam round-trip: types, SameSite enum, TimeSinceEpoch, past-expiry filter."""
    future_ts = time.time() + 3600.0
    dicts = [
        {
            "name": "session-id",
            "value": "abc123",
            "domain": ".amazon.com",
            "path": "/",
            "expires": future_ts,
            "http_only": True,
            "secure": True,
            "same_site": "None",
        }
    ]
    params = _dicts_to_cookie_params(dicts)
    assert len(params) == 1
    p = params[0]
    assert isinstance(p, cdp_network.CookieParam)
    assert p.name == "session-id"
    assert p.value == "abc123"
    assert p.domain == ".amazon.com"
    assert p.path == "/"
    assert p.http_only is True
    assert p.secure is True
    # SameSite string 'None' -> CookieSameSite.NONE
    assert p.same_site == cdp_network.CookieSameSite.NONE
    # expires wrapped as TimeSinceEpoch
    assert isinstance(p.expires, cdp_network.TimeSinceEpoch)
    assert float(p.expires) == pytest.approx(future_ts)


def test_cookie_param_past_expiry_filtered():
    """Cookies with expires in the past are filtered out."""
    past_ts = time.time() - 60.0
    future_ts = time.time() + 3600.0
    dicts = [
        {"name": "expired", "value": "old", "expires": past_ts},
        {"name": "valid", "value": "new", "expires": future_ts},
    ]
    params = _dicts_to_cookie_params(dicts)
    assert len(params) == 1
    assert params[0].name == "valid"


def test_cookie_param_all_expired_returns_empty():
    """All expired cookies returns empty list."""
    past_ts = time.time() - 60.0
    dicts = [{"name": "dead", "value": "x", "expires": past_ts}]
    params = _dicts_to_cookie_params(dicts)
    assert params == []


def test_cookie_param_no_expires():
    """Cookies with expires=None pass through without TimeSinceEpoch wrapping."""
    dicts = [{"name": "session", "value": "s", "expires": None}]
    params = _dicts_to_cookie_params(dicts)
    assert len(params) == 1
    assert params[0].expires is None


def test_cookie_param_strict_same_site():
    """SameSite 'Strict' maps to CookieSameSite.STRICT."""
    dicts = [{"name": "x", "value": "y", "same_site": "Strict"}]
    params = _dicts_to_cookie_params(dicts)
    assert params[0].same_site == cdp_network.CookieSameSite.STRICT


def test_cookie_param_invalid_same_site_is_none():
    """Invalid same_site value maps to None (no crash)."""
    dicts = [{"name": "x", "value": "y", "same_site": "bogus"}]
    params = _dicts_to_cookie_params(dicts)
    assert params[0].same_site is None


# ---------------------------------------------------------------------------
# Task 1: restore_session() -- returns True and uses raw CDP path
# ---------------------------------------------------------------------------

async def test_restore_session_returns_true_when_session_exists(tmp_path, monkeypatch):
    """restore_session() returns True and calls tab.send(set_cookies(...)) when session exists."""
    monkeypatch.setenv("SHOPBOT_STORE_PASSPHRASE", "testpass")
    monkeypatch.setenv("SHOPBOT_DATA_DIR", str(tmp_path))

    # Pre-save a session file via SessionStore
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    future_ts = time.time() + 3600.0
    cookies = [{"name": "sid", "value": "abc", "domain": ".amazon.com",
                "path": "/", "expires": future_ts, "http_only": True,
                "secure": True, "same_site": "Lax"}]
    store = SessionStore(sessions_dir=sessions_dir, passphrase=b"testpass")
    store.save("amazon", cookies)

    fake_tab = _make_fake_tab()
    config = _make_config(session_persistence=True)
    plugin = _make_plugin(config, fake_tab)

    result = await plugin.restore_session()

    assert result is True
    # tab.send was called once (for set_cookies)
    assert fake_tab.send.await_count == 1
    # No CookieJar.set_all was called (raw CDP path only)


async def test_restore_session_false_when_disabled(tmp_path, monkeypatch):
    """restore_session() returns False and does not touch tab when disabled."""
    monkeypatch.setenv("SHOPBOT_STORE_PASSPHRASE", "testpass")
    monkeypatch.setenv("SHOPBOT_DATA_DIR", str(tmp_path))

    fake_tab = _make_fake_tab()
    config = _make_config(session_persistence=False)
    plugin = _make_plugin(config, fake_tab)

    result = await plugin.restore_session()

    assert result is False
    assert fake_tab.send.await_count == 0


async def test_restore_session_false_no_passphrase(tmp_path, monkeypatch):
    """restore_session() returns False without touching tab when passphrase absent."""
    monkeypatch.delenv("SHOPBOT_STORE_PASSPHRASE", raising=False)
    monkeypatch.setenv("SHOPBOT_DATA_DIR", str(tmp_path))

    fake_tab = _make_fake_tab()
    config = _make_config(session_persistence=True)
    plugin = _make_plugin(config, fake_tab)

    result = await plugin.restore_session()

    assert result is False
    assert fake_tab.send.await_count == 0


async def test_restore_session_false_no_file(tmp_path, monkeypatch):
    """restore_session() returns False when no session file exists."""
    monkeypatch.setenv("SHOPBOT_STORE_PASSPHRASE", "testpass")
    monkeypatch.setenv("SHOPBOT_DATA_DIR", str(tmp_path))

    fake_tab = _make_fake_tab()
    config = _make_config(session_persistence=True)
    plugin = _make_plugin(config, fake_tab)

    result = await plugin.restore_session()

    assert result is False
    assert fake_tab.send.await_count == 0


async def test_restore_session_skips_login(tmp_path, monkeypatch):
    """When restore_session() returns True, login is NOT called (relaunch-style check)."""
    monkeypatch.setenv("SHOPBOT_STORE_PASSPHRASE", "testpass")
    monkeypatch.setenv("SHOPBOT_DATA_DIR", str(tmp_path))

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    future_ts = time.time() + 3600.0
    cookies = [{"name": "tok", "value": "xyz", "expires": future_ts}]
    store = SessionStore(sessions_dir=sessions_dir, passphrase=b"testpass")
    store.save("amazon", cookies)

    fake_tab = _make_fake_tab()
    config = _make_config(session_persistence=True)

    call_order: list[str] = []

    class _OrderPlugin(RetailerPlugin):
        domain_patterns = ["order.example.com"]
        platform_key = "amazon"

        async def check_availability(self, url: str) -> bool:
            return True

        async def auto_buy(self, url: str) -> bool:
            return False

        def get_active_tab(self):
            return fake_tab

    plugin = _OrderPlugin(config=config)

    async def _record_login():
        call_order.append("login")

    plugin.login = AsyncMock(side_effect=_record_login)

    # Simulate the relaunch sequence but with real restore_session
    session_restored = await plugin.restore_session()
    if not session_restored:
        await plugin.login()

    assert session_restored is True
    assert "login" not in call_order


# ---------------------------------------------------------------------------
# Task 1: save_session() behavior
# ---------------------------------------------------------------------------

def _make_fake_cookie(name, value, domain=None, path="/", expires=None,
                      http_only=False, secure=False, same_site=None):
    """Return a MagicMock that mimics a network.Cookie with given field values."""
    c = MagicMock()
    c.name = name
    c.value = value
    c.domain = domain
    c.path = path
    c.expires = expires
    c.http_only = http_only
    c.secure = secure
    c.same_site = same_site
    return c


async def test_save_session_writes_encrypted_file(tmp_path, monkeypatch):
    """save_session() creates a session file when enabled and passphrase set."""
    monkeypatch.setenv("SHOPBOT_STORE_PASSPHRASE", "testpass")
    monkeypatch.setenv("SHOPBOT_DATA_DIR", str(tmp_path))

    fake_cookie = _make_fake_cookie("session-id", "abc123", domain=".amazon.com")
    fake_tab = _make_fake_tab()
    fake_tab.send = AsyncMock(return_value=[fake_cookie])

    config = _make_config(session_persistence=True)
    plugin = _make_plugin(config, fake_tab)

    await plugin.save_session()

    session_file = tmp_path / "sessions" / "amazon.bin"
    assert session_file.exists(), "Session file must be created after save_session()"
    # Verify it's encrypted (not valid JSON)
    raw = session_file.read_bytes()
    assert b"abc123" not in raw, "Session file must be encrypted (not plaintext)"


async def test_save_session_noop_when_disabled(tmp_path, monkeypatch):
    """save_session() writes no file when session_persistence=False."""
    monkeypatch.setenv("SHOPBOT_STORE_PASSPHRASE", "testpass")
    monkeypatch.setenv("SHOPBOT_DATA_DIR", str(tmp_path))

    fake_tab = _make_fake_tab()
    config = _make_config(session_persistence=False)
    plugin = _make_plugin(config, fake_tab)

    await plugin.save_session()

    session_file = tmp_path / "sessions" / "amazon.bin"
    assert not session_file.exists()
    assert fake_tab.send.await_count == 0


async def test_save_session_noop_no_passphrase(tmp_path, monkeypatch):
    """save_session() writes no file when passphrase is absent."""
    monkeypatch.delenv("SHOPBOT_STORE_PASSPHRASE", raising=False)
    monkeypatch.setenv("SHOPBOT_DATA_DIR", str(tmp_path))

    fake_tab = _make_fake_tab()
    config = _make_config(session_persistence=True)
    plugin = _make_plugin(config, fake_tab)

    await plugin.save_session()

    session_file = tmp_path / "sessions" / "amazon.bin"
    assert not session_file.exists()
