"""Tests for migrate_legacy_paths() in core/paths.py.

TDD RED phase: all tests fail because migrate_legacy_paths and
_REPO_ROOT_OVERRIDE do not yet exist in core/paths.
"""

from __future__ import annotations

from pathlib import Path
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_legacy_db(repo_root: Path) -> Path:
    legacy = repo_root / "data" / "shop_py_bot.db"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_bytes(b"fake-db-content")
    return legacy


def _make_legacy_creds(repo_root: Path, content: bytes = b"encrypted-creds-bytes") -> Path:
    legacy = repo_root / "data" / "creds.bin"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_bytes(content)
    return legacy


def _make_legacy_config(repo_root: Path) -> Path:
    legacy = repo_root / "config.yml"
    legacy.write_bytes(b"debug:\n  logging_level: 5\n")
    return legacy


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_migration_moves_db(tmp_path, monkeypatch):
    """Legacy data/shop_py_bot.db is copied to data_dir() and src is removed."""
    new_dir = tmp_path / "new"
    monkeypatch.setenv("SHOPBOT_DATA_DIR", str(new_dir))

    repo_root = tmp_path / "repo"
    legacy = _make_legacy_db(repo_root)

    import core.paths
    monkeypatch.setattr(core.paths, "_REPO_ROOT_OVERRIDE", repo_root)

    core.paths.migrate_legacy_paths()

    assert (new_dir / "shop_py_bot.db").exists(), "DB not present at new location"
    assert not legacy.exists(), "Legacy DB src was not unlinked"


def test_migration_moves_creds_verbatim(tmp_path, monkeypatch):
    """creds.bin is copied byte-for-byte and the legacy src is removed."""
    secret_bytes = b"\x00\x01encrypted-fernet-blob\xff\xfe"
    new_dir = tmp_path / "new"
    monkeypatch.setenv("SHOPBOT_DATA_DIR", str(new_dir))

    repo_root = tmp_path / "repo"
    legacy = _make_legacy_creds(repo_root, secret_bytes)

    import core.paths
    monkeypatch.setattr(core.paths, "_REPO_ROOT_OVERRIDE", repo_root)

    core.paths.migrate_legacy_paths()

    dst = new_dir / "creds.bin"
    assert dst.exists(), "creds.bin not present at new location"
    assert dst.read_bytes() == secret_bytes, "creds.bin content differs (must be verbatim)"
    assert not legacy.exists(), "Legacy creds.bin src was not unlinked"


def test_migration_idempotent(tmp_path, monkeypatch):
    """Calling migrate_legacy_paths() twice is a no-op on the second call."""
    new_dir = tmp_path / "new"
    monkeypatch.setenv("SHOPBOT_DATA_DIR", str(new_dir))

    repo_root = tmp_path / "repo"
    _make_legacy_db(repo_root)

    import core.paths
    monkeypatch.setattr(core.paths, "_REPO_ROOT_OVERRIDE", repo_root)

    core.paths.migrate_legacy_paths()
    core.paths.migrate_legacy_paths()  # second call must not raise

    assert (new_dir / "shop_py_bot.db").exists()


def test_migration_skips_when_dst_exists(tmp_path, monkeypatch):
    """If the destination already exists, src is NOT overwritten and NOT unlinked."""
    new_dir = tmp_path / "new"
    new_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SHOPBOT_DATA_DIR", str(new_dir))

    # Pre-create the destination with distinct content
    dst = new_dir / "shop_py_bot.db"
    dst.write_bytes(b"existing-db")

    repo_root = tmp_path / "repo"
    legacy = _make_legacy_db(repo_root)
    original_legacy_bytes = legacy.read_bytes()

    import core.paths
    monkeypatch.setattr(core.paths, "_REPO_ROOT_OVERRIDE", repo_root)

    core.paths.migrate_legacy_paths()

    # dst should be unchanged
    assert dst.read_bytes() == b"existing-db", "dst was overwritten"
    # src should still exist (not unlinked)
    assert legacy.exists(), "Legacy src was incorrectly unlinked"
    assert legacy.read_bytes() == original_legacy_bytes


def test_migration_logs_paths_not_secrets(tmp_path, monkeypatch):
    """Logged messages contain dst path strings, never the creds.bin byte content."""
    secret_bytes = b"super-secret-fernet-token-never-log-me"
    new_dir = tmp_path / "new"
    monkeypatch.setenv("SHOPBOT_DATA_DIR", str(new_dir))

    repo_root = tmp_path / "repo"
    _make_legacy_db(repo_root)
    _make_legacy_creds(repo_root, secret_bytes)
    _make_legacy_config(repo_root)

    logged_messages: list[str] = []

    def _capture_log(message: str, log_type: str, writeTofile: bool = True) -> None:
        logged_messages.append(message)

    import core.paths
    monkeypatch.setattr(core.paths, "_REPO_ROOT_OVERRIDE", repo_root)
    # Patch writeLog as it will be imported inside migrate_legacy_paths
    import logger
    monkeypatch.setattr(logger, "writeLog", _capture_log)

    core.paths.migrate_legacy_paths()

    assert logged_messages, "No log messages emitted during migration"
    for msg in logged_messages:
        assert secret_bytes.decode("latin-1") not in msg, (
            f"Secret bytes appeared in log message: {msg!r}"
        )
        # Confirm path string is present in at least one message
    path_mentioned = any(str(new_dir) in msg for msg in logged_messages)
    assert path_mentioned, "No log message referenced the destination path"
