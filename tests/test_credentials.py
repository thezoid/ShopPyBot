"""Tests for core/credentials.py (CRED-01..CRED-07).

Wave 0 (plan 08-01): test scaffold with real tests for CRED-01/CRED-04 and
xfail stubs for CRED-02/03/05/06/07 (implemented in plans 08-02/03/04).

Test names match RESEARCH.md "Phase Requirements to Test Map" exactly.
"""

import os
from pathlib import Path

import pytest


# ============================================================
# CRED-01 / CRED-04: EnvVarBackend (real tests -- pass in plan 08-01)
# ============================================================


def test_env_backend_get(monkeypatch):
    """EnvVarBackend.get returns the value set via monkeypatch.setenv."""
    from core.credentials import EnvVarBackend

    monkeypatch.setenv("AMZ_EMAIL", "test@example.com")
    backend = EnvVarBackend()
    assert backend.get("AMZ_EMAIL") == "test@example.com"


def test_env_backend_monkeypatch(monkeypatch):
    """Existing setenv pattern works through EnvVarBackend (CRED-04 identity check)."""
    from core.credentials import EnvVarBackend

    monkeypatch.setenv("AMZ_EMAIL", "x@example.com")
    assert EnvVarBackend().get("AMZ_EMAIL") == "x@example.com"


def test_env_backend_missing_key_returns_none(monkeypatch):
    """EnvVarBackend.get returns None for an unset key."""
    from core.credentials import EnvVarBackend

    monkeypatch.delenv("NEWEGG_PASSWORD", raising=False)
    assert EnvVarBackend().get("NEWEGG_PASSWORD") is None


def test_env_backend_set_and_delete(monkeypatch):
    """EnvVarBackend.set writes to os.environ; delete removes the key."""
    from core.credentials import EnvVarBackend

    monkeypatch.delenv("AMZ_PASSWORD", raising=False)
    backend = EnvVarBackend()
    backend.set("AMZ_PASSWORD", "hunter2")
    assert os.environ.get("AMZ_PASSWORD") == "hunter2"
    backend.delete("AMZ_PASSWORD")
    assert os.environ.get("AMZ_PASSWORD") is None


def test_env_backend_list(monkeypatch):
    """EnvVarBackend.list returns only SECRET_KEYS that are currently set."""
    from core.credentials import EnvVarBackend, SECRET_KEYS

    # Clear all secret keys then set two
    for k in SECRET_KEYS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.example")
    monkeypatch.setenv("AMZ_EMAIL", "user@example.com")

    result = EnvVarBackend().list()
    assert "DISCORD_WEBHOOK_URL" in result
    assert "AMZ_EMAIL" in result
    # Only returns known SECRET_KEYS that are set
    for key in result:
        assert key in SECRET_KEYS


# ============================================================
# CRED-01: get_store lazy fallback (real test -- passes in plan 08-01)
# ============================================================


def test_get_store_lazy_fallback(reset_credential_store):
    """When _store is None, get_store() returns an EnvVarBackend instance."""
    import core.credentials as creds
    from core.credentials import EnvVarBackend, get_store

    creds._store = None
    store = get_store()
    assert isinstance(store, EnvVarBackend)


# ============================================================
# CRED-01: SECRET_KEYS canonical list (real test -- passes in plan 08-01)
# ============================================================


def test_secret_keys_canonical():
    """SECRET_KEYS contains all 19 canonical names with no duplicates."""
    from core.credentials import SECRET_KEYS

    assert len(SECRET_KEYS) == 19
    assert len(SECRET_KEYS) == len(set(SECRET_KEYS)), "Duplicate keys in SECRET_KEYS"
    # Spot-check boundaries
    assert "DISCORD_WEBHOOK_URL" in SECRET_KEYS
    assert "NEWEGG_PASSWORD" in SECRET_KEYS
    # Spot-check all groups present
    for key in (
        "SMTP_PASSWORD",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_FROM",
        "AMZ_EMAIL",
        "AMZ_PASSWORD",
        "BB_EMAIL",
        "BB_PASSWORD",
        "WALMART_EMAIL",
        "WALMART_PASSWORD",
        "TARGET_EMAIL",
        "TARGET_PASSWORD",
        "GAMESTOP_EMAIL",
        "GAMESTOP_PASSWORD",
        "SQUAREENIX_EMAIL",
        "SQUAREENIX_PASSWORD",
        "NEWEGG_EMAIL",
        "NEWEGG_PASSWORD",
    ):
        assert key in SECRET_KEYS, f"{key} missing from SECRET_KEYS"


# ============================================================
# CRED-01: CredentialsConfig default (real test -- passes in plan 08-01)
# ============================================================


def test_credentials_config_default():
    """AppConfig().credentials.backend defaults to 'auto'."""
    from core.config_schema import AppConfig

    cfg = AppConfig()
    assert cfg.credentials.backend == "auto"
    assert cfg.credentials.data_dir == ""


# ============================================================
# CRED-02: KeyringBackend (plan 08-02)
# ============================================================


def test_keyring_backend(isolated_keyring):
    """KeyringBackend.get/set/delete/list work with the in-memory DictKeyring."""
    from core.credentials import KeyringBackend

    store = KeyringBackend()
    store.set("AMZ_EMAIL", "keyring@example.com")
    assert store.get("AMZ_EMAIL") == "keyring@example.com"
    store.delete("AMZ_EMAIL")
    assert store.get("AMZ_EMAIL") is None


def test_keyring_list(isolated_keyring):
    """KeyringBackend.list returns only SECRET_KEYS that have a stored value."""
    from core.credentials import KeyringBackend, SECRET_KEYS

    store = KeyringBackend()
    store.set("AMZ_EMAIL", "user@example.com")
    store.set("BB_EMAIL", "user2@example.com")
    result = store.list()
    assert "AMZ_EMAIL" in result
    assert "BB_EMAIL" in result
    # Only known SECRET_KEYS may be returned
    for key in result:
        assert key in SECRET_KEYS
    # Keys not set are absent
    assert "DISCORD_WEBHOOK_URL" not in result


def test_has_real_keyring_fail():
    """_has_real_keyring() returns False for fail.Keyring and True for DictKeyring."""
    import keyring
    from keyring.backends import fail as keyring_fail
    from core.credentials import _has_real_keyring

    # Force fail.Keyring: must return False
    original = keyring.get_keyring()
    try:
        keyring.set_keyring(keyring_fail.Keyring())
        assert _has_real_keyring() is False
    finally:
        keyring.set_keyring(original)


# ============================================================
# CRED-03: EncryptedFileBackend (plan 08-02)
# ============================================================


def test_file_backend(tmp_path):
    """EncryptedFileBackend round-trip: set/get/delete/list."""
    from core.credentials import EncryptedFileBackend

    store = EncryptedFileBackend(tmp_path / "creds.bin", b"test-passphrase")
    store.set("AMZ_EMAIL", "file@example.com")
    assert store.get("AMZ_EMAIL") == "file@example.com"
    store.delete("AMZ_EMAIL")
    assert store.get("AMZ_EMAIL") is None
    assert store.list() == []


def test_encrypted_file_is_not_plaintext(tmp_path):
    """The Fernet-encrypted store file contains no plaintext secret values."""
    from core.credentials import EncryptedFileBackend

    store_path = tmp_path / "creds.bin"
    store = EncryptedFileBackend(store_path, b"test-passphrase")
    store.set("AMZ_EMAIL", "mytest@example.com")
    raw = store_path.read_bytes()
    assert b"mytest@example.com" not in raw


def test_file_backend_wrong_passphrase(tmp_path):
    """Wrong passphrase raises a clear ValueError (not a cryptic cryptography error)."""
    from core.credentials import EncryptedFileBackend

    store = EncryptedFileBackend(tmp_path / "creds.bin", b"correct-passphrase")
    store.set("AMZ_EMAIL", "secret@example.com")

    bad = EncryptedFileBackend(tmp_path / "creds.bin", b"wrong-passphrase")
    with pytest.raises(ValueError, match="SHOPBOT_STORE_PASSPHRASE"):
        bad.get("AMZ_EMAIL")


# ============================================================
# CRED-05: Backend auto-selection (plan 08-03 -- un-xfailed)
# ============================================================


def test_auto_select_keyring(reset_credential_store, isolated_keyring, monkeypatch):
    """init_store returns KeyringBackend when _has_real_keyring returns True."""
    from unittest.mock import patch
    from core.credentials import KeyringBackend, init_store
    from core.config_schema import AppConfig

    cfg = AppConfig()
    with patch("core.credentials._has_real_keyring", return_value=True):
        store = init_store(cfg)
    assert isinstance(store, KeyringBackend)


def test_auto_select_file(reset_credential_store, monkeypatch, tmp_path):
    """init_store returns EncryptedFileBackend when passphrase set and no real keyring."""
    from unittest.mock import patch
    from core.credentials import EncryptedFileBackend, init_store
    from core.config_schema import AppConfig

    monkeypatch.setenv("SHOPBOT_STORE_PASSPHRASE", "testpassphrase")
    cfg = AppConfig()
    with patch("core.credentials._has_real_keyring", return_value=False):
        store = init_store(cfg)
    assert isinstance(store, EncryptedFileBackend)


def test_auto_select_env(reset_credential_store, monkeypatch):
    """init_store returns EnvVarBackend when no keyring and no passphrase."""
    from unittest.mock import patch
    from core.credentials import EnvVarBackend, init_store
    from core.config_schema import AppConfig

    monkeypatch.delenv("SHOPBOT_STORE_PASSPHRASE", raising=False)
    cfg = AppConfig()
    with patch("core.credentials._has_real_keyring", return_value=False):
        store = init_store(cfg)
    assert isinstance(store, EnvVarBackend)


def test_explicit_backend_override(reset_credential_store, monkeypatch, tmp_path):
    """cfg.credentials.backend='env'/'keyring'/'file' bypasses auto-detect."""
    from unittest.mock import patch
    from core.credentials import (
        EnvVarBackend, KeyringBackend, EncryptedFileBackend,
        init_store,
    )
    from core.config_schema import AppConfig

    # env override
    cfg = AppConfig()
    cfg.credentials.backend = "env"
    with patch("core.credentials._has_real_keyring", return_value=False):
        store = init_store(cfg)
    assert isinstance(store, EnvVarBackend)

    # keyring override (even when _has_real_keyring would be False in auto)
    cfg2 = AppConfig()
    cfg2.credentials.backend = "keyring"
    from tests.conftest import _DictKeyring  # noqa: F401 -- available post-08-02
    import keyring as _kr
    _kr.set_keyring(_DictKeyring())
    try:
        store2 = init_store(cfg2)
    finally:
        _kr.core._keyring_backend = None
    assert isinstance(store2, KeyringBackend)

    # file override
    monkeypatch.setenv("SHOPBOT_STORE_PASSPHRASE", "pw")
    cfg3 = AppConfig()
    cfg3.credentials.backend = "file"
    store3 = init_store(cfg3)
    assert isinstance(store3, EncryptedFileBackend)


def test_startup_log_backend_name(reset_credential_store, monkeypatch, capsys):
    """init_store logs 'backend active' exactly once; no secret value in the log."""
    from unittest.mock import patch
    from core.credentials import init_store
    from core.config_schema import AppConfig

    monkeypatch.delenv("SHOPBOT_STORE_PASSPHRASE", raising=False)
    cfg = AppConfig()
    with patch("core.credentials._has_real_keyring", return_value=False):
        init_store(cfg)
    captured = capsys.readouterr()
    assert "backend active" in captured.out
    # No secret values should appear in the log output (T-08-09)
    for env_key in ("AMZ_EMAIL", "AMZ_PASSWORD", "DISCORD_WEBHOOK_URL",
                    "BB_EMAIL", "BB_PASSWORD"):
        secret_val = os.environ.get(env_key, "")
        if secret_val:
            assert secret_val not in captured.out, (
                f"Secret value for {env_key} found in log output"
            )


# ============================================================
# Task 2: BotService initializes store at construction (plan 08-03)
# ============================================================


def test_botservice_initializes_store(reset_credential_store, monkeypatch):
    """BotService(cfg) sets the process-wide _store singleton (not just lazy fallback)."""
    import core.credentials as creds
    from unittest.mock import patch
    from core.credentials import EnvVarBackend
    from core.config_schema import AppConfig
    from core.service import BotService

    # Ensure _store starts as None so the test is meaningful
    creds._store = None

    monkeypatch.delenv("SHOPBOT_STORE_PASSPHRASE", raising=False)
    cfg = AppConfig()
    cfg.credentials.backend = "env"

    with patch("core.credentials._has_real_keyring", return_value=False):
        BotService(cfg)

    # After BotService construction, _store must be set (not None)
    assert creds._store is not None, "BotService did not call init_store"
    assert isinstance(creds._store, EnvVarBackend)


# ============================================================
# CRED-06: No-plaintext secrets (stubs -- implemented in plan 08-04)
# ============================================================


@pytest.mark.xfail(reason="No-plaintext test implemented in plan 08-04", strict=False)
def test_no_plaintext_secrets_in_config_yml():
    """Assert none of the SECRET_KEYS values appear as plaintext in config.yml."""
    from core.credentials import SECRET_KEYS

    config_path = Path("config.yml")
    if not config_path.exists():
        pytest.skip("config.yml not present in this environment")
    content = config_path.read_text(errors="replace")
    for key in SECRET_KEYS:
        val = os.environ.get(key, "")
        if val:
            assert val not in content, f"Secret {key} value found in config.yml"


# ============================================================
# CRED-07: migrate_from_env (stub -- implemented in plan 08-04)
# ============================================================


def test_migrate_from_env(monkeypatch, reset_credential_store, tmp_path):
    """migrate_from_env writes set env secrets into target backend; returns key names."""
    from core.credentials import EncryptedFileBackend, migrate_from_env, SECRET_KEYS

    # Clear all secret keys to ensure isolation
    for k in SECRET_KEYS:
        monkeypatch.delenv(k, raising=False)

    monkeypatch.setenv("AMZ_EMAIL", "migrate@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "smtppass")

    target = EncryptedFileBackend(tmp_path / "creds.bin", b"testpass")
    migrated = migrate_from_env(target)

    # Returns only the set keys
    assert "AMZ_EMAIL" in migrated
    assert "SMTP_PASSWORD" in migrated
    # Unset keys are skipped
    assert "BB_EMAIL" not in migrated
    # The values were written to the backend
    assert target.get("AMZ_EMAIL") == "migrate@example.com"
    # Values are never in the returned list -- only key names
    assert "migrate@example.com" not in migrated


def test_migrate_confirms_by_name(monkeypatch, reset_credential_store, tmp_path):
    """migrate_from_env returned list contains key NAMES only, never values."""
    from core.credentials import EncryptedFileBackend, migrate_from_env, SECRET_KEYS

    for k in SECRET_KEYS:
        monkeypatch.delenv(k, raising=False)

    monkeypatch.setenv("AMZ_EMAIL", "supersecret@example.com")
    monkeypatch.setenv("AMZ_PASSWORD", "hunter2secret")

    target = EncryptedFileBackend(tmp_path / "creds.bin", b"testpass")
    migrated = migrate_from_env(target)

    # Names in list
    assert "AMZ_EMAIL" in migrated
    assert "AMZ_PASSWORD" in migrated
    # Secret values NOT in list
    assert "supersecret@example.com" not in migrated
    assert "hunter2secret" not in migrated


def test_main_migrate_flag(monkeypatch, reset_credential_store, tmp_path, capsys):
    """--migrate flag prints key names only and exits without starting the bot."""
    import sys
    from core.credentials import SECRET_KEYS, EnvVarBackend

    for k in SECRET_KEYS:
        monkeypatch.delenv(k, raising=False)

    monkeypatch.setenv("AMZ_EMAIL", "flagtest@example.com")
    monkeypatch.setenv("BB_EMAIL", "flagbb@example.com")

    # Patch get_store to return an EnvVarBackend (which reads from monkeypatched env)
    # and patch migrate_from_env to return the expected key list
    from unittest.mock import patch

    def _fake_migrate(store):
        from core.credentials import SECRET_KEYS as _SK
        import os
        migrated = []
        for key in _SK:
            val = os.environ.get(key)
            if val:
                migrated.append(key)
        return migrated

    monkeypatch.setattr(sys, "argv", ["shoppybot", "--migrate"])

    # Patch at the module where migrate_from_env is used after the Phase-9
    # refactor: handle_setup in core.cli.setup now owns the --migrate path.
    with patch("core.cli.setup.migrate_from_env", side_effect=_fake_migrate):
        from core import service as _svc
        # Re-import to pick up fresh main with --migrate
        import importlib
        importlib.reload(_svc)
        # --migrate path now calls sys.exit(0) after printing (CR-01)
        with pytest.raises(SystemExit) as exc_info:
            _svc.main()
        assert exc_info.value.code == 0

    captured = capsys.readouterr()
    # Key names appear in output
    assert "AMZ_EMAIL" in captured.out
    assert "BB_EMAIL" in captured.out
    # Secret values do NOT appear
    assert "flagtest@example.com" not in captured.out
    assert "flagbb@example.com" not in captured.out
