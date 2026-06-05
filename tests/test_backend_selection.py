"""Backend auto-selection tests (XPLAT-02 / SC3).

Proves _build_store("auto", cfg) selects the correct credential backend based
on _has_real_keyring() result and the SHOPBOT_STORE_PASSPHRASE env var. All
three tests are env-independent: no real keyring, D-Bus, or Secret Service is
touched because _has_real_keyring is fully mocked.
"""

from unittest.mock import patch


def test_auto_selects_keyring_when_available(reset_credential_store, tmp_config_yml):
    """When _has_real_keyring() returns True, auto-detect picks KeyringBackend."""
    with patch("core.credentials._has_real_keyring", return_value=True):
        from core.credentials import _build_store
        from core.config_schema import AppConfig

        cfg = AppConfig(yaml_file=tmp_config_yml)
        store = _build_store("auto", cfg)
    assert store.__class__.__name__ == "KeyringBackend"


def test_auto_selects_file_when_no_keyring(
    reset_credential_store, tmp_config_yml, monkeypatch
):
    """When _has_real_keyring() is False and SHOPBOT_STORE_PASSPHRASE is set,
    auto-detect picks EncryptedFileBackend."""
    monkeypatch.setenv("SHOPBOT_STORE_PASSPHRASE", "test-passphrase")
    with patch("core.credentials._has_real_keyring", return_value=False):
        from core.credentials import _build_store
        from core.config_schema import AppConfig

        cfg = AppConfig(yaml_file=tmp_config_yml)
        store = _build_store("auto", cfg)
    assert store.__class__.__name__ == "EncryptedFileBackend"


def test_auto_falls_back_to_env(
    reset_credential_store, tmp_config_yml, monkeypatch
):
    """When _has_real_keyring() is False and no passphrase is set, auto-detect
    falls back to EnvVarBackend."""
    monkeypatch.delenv("SHOPBOT_STORE_PASSPHRASE", raising=False)
    with patch("core.credentials._has_real_keyring", return_value=False):
        from core.credentials import _build_store
        from core.config_schema import AppConfig

        cfg = AppConfig(yaml_file=tmp_config_yml)
        store = _build_store("auto", cfg)
    assert store.__class__.__name__ == "EnvVarBackend"
