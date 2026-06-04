"""CRED-06: No-plaintext-on-disk guard tests.

Asserts that no SECRET_KEYS value appears as plaintext in:
- config.yml (if present)
- logs/*.log files (if present)
- The SQLite DB file bytes (if present)
- The raw bytes of an EncryptedFileBackend-written store file

Tests skip (not fail) when the file being checked does not exist, so the
suite stays green in clean CI environments where config.yml, logs/, and
data/shop_py_bot.db are absent (RESEARCH 'No-Plaintext Guarantee').
"""

import os
from pathlib import Path

import pytest

from core.credentials import SECRET_KEYS, EncryptedFileBackend
import models


def _non_trivial_secret_values() -> list[tuple[str, str]]:
    """Return (key, value) pairs from os.environ for keys in SECRET_KEYS where len(val) > 4."""
    return [
        (k, v)
        for k in SECRET_KEYS
        for v in (os.environ.get(k, ""),)
        if v and len(v) > 4
    ]


def test_no_plaintext_secrets_in_config_yml():
    """No SECRET_KEYS value appears as plaintext in config.yml."""
    config_path = Path("config.yml")
    if not config_path.exists():
        pytest.skip("config.yml not present in this environment")

    content = config_path.read_text(errors="replace")
    for key, val in _non_trivial_secret_values():
        assert val not in content, (
            f"Secret value for {key} found as plaintext in config.yml"
        )


def test_no_plaintext_secrets_in_log_files():
    """No SECRET_KEYS value appears as plaintext in any logs/*.log file."""
    log_dir = Path("logs")
    if not log_dir.exists():
        return  # no logs yet -- vacuously pass

    for log_file in log_dir.glob("*.log"):
        content = log_file.read_text(errors="replace")
        for key, val in _non_trivial_secret_values():
            assert val not in content, (
                f"Secret value for {key} found as plaintext in {log_file}"
            )


def test_no_plaintext_secrets_in_sqlite():
    """No SECRET_KEYS value appears as plaintext in the SQLite DB file bytes."""
    db_path = Path(models.DB_PATH)
    if not db_path.exists():
        pytest.skip("SQLite DB not present in this environment")

    db_bytes = db_path.read_bytes()
    for key, val in _non_trivial_secret_values():
        assert val.encode() not in db_bytes, (
            f"Secret value for {key} found as plaintext in SQLite DB"
        )


def test_encrypted_file_is_not_plaintext(tmp_path):
    """EncryptedFileBackend.set produces a ciphertext-only file (no raw value in bytes)."""
    store_path = tmp_path / "creds.bin"
    store = EncryptedFileBackend(store_path, b"test-passphrase-08-03")

    secret_value = "plaintext_secret_value_99"
    store.set("AMZ_EMAIL", secret_value)

    raw = store_path.read_bytes()
    assert secret_value.encode() not in raw, (
        "EncryptedFileBackend wrote the plaintext secret value to disk"
    )
    # Confirm the file is non-empty (something was written)
    assert len(raw) > 0
