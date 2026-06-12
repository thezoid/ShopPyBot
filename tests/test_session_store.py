"""Unit tests for core/session_store.py (Phase 23 -- REL-04).

Coverage:
    - Round-trip save/restore with a real passphrase
    - On-disk file is NOT valid JSON (encrypted-only guarantee)
    - restore() returns None on missing file
    - restore() returns None on corrupt/truncated data (no raise)
    - restore() returns None on wrong passphrase / InvalidToken (no raise)
    - save() is no-op when passphrase is None; restore() returns None
"""

import json
import pytest


_COOKIES = [
    {
        "name": "session-id",
        "value": "abc123",
        "domain": ".amazon.com",
        "path": "/",
        "expires": None,
        "http_only": True,
        "secure": True,
        "same_site": "None",
    }
]


def test_save_restore_roundtrip(tmp_path):
    """save() then restore() returns the identical cookie list."""
    from core.session_store import SessionStore

    store = SessionStore(tmp_path / "sessions", b"test-passphrase")
    store.save("amazon", _COOKIES)
    result = store.restore("amazon")
    assert result == _COOKIES


def test_no_plaintext_file(tmp_path):
    """The on-disk .bin file is NOT valid JSON and contains no plaintext sentinel."""
    from core.session_store import SessionStore

    sentinel = "SENTINEL_AUTH_abc123"
    cookies = [{"name": "tok", "value": sentinel, "domain": ".amazon.com"}]
    store = SessionStore(tmp_path / "sessions", b"test-passphrase")
    store.save("amazon", cookies)

    raw = (tmp_path / "sessions" / "amazon.bin").read_bytes()
    assert sentinel.encode() not in raw, "Plaintext cookie value found in encrypted file"
    with pytest.raises(Exception):
        json.loads(raw)


def test_restore_missing_file(tmp_path):
    """restore() returns None when no session file exists."""
    from core.session_store import SessionStore

    store = SessionStore(tmp_path / "sessions", b"test-passphrase")
    assert store.restore("amazon") is None


def test_restore_corrupt_data(tmp_path):
    """restore() returns None on corrupt/truncated data -- never raises."""
    from core.session_store import SessionStore

    store = SessionStore(tmp_path / "sessions", b"test-passphrase")
    store.save("amazon", _COOKIES)
    # Overwrite with garbage (keeps the directory present)
    (tmp_path / "sessions" / "amazon.bin").write_bytes(b"\x00" * 8 + b"garbage")
    result = store.restore("amazon")
    assert result is None


def test_restore_wrong_passphrase(tmp_path):
    """restore() returns None on wrong passphrase (InvalidToken) -- never raises."""
    from core.session_store import SessionStore

    store = SessionStore(tmp_path / "sessions", b"correct")
    store.save("amazon", _COOKIES)
    bad = SessionStore(tmp_path / "sessions", b"wrong")
    assert bad.restore("amazon") is None


def test_save_noop_no_passphrase(tmp_path):
    """When passphrase=None: save() writes no file, restore() returns None."""
    from core.session_store import SessionStore

    store = SessionStore(tmp_path / "sessions", None)
    store.save("amazon", _COOKIES)
    assert not (tmp_path / "sessions" / "amazon.bin").exists()
    assert store.restore("amazon") is None
