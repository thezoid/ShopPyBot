"""OS-appropriate path resolution for data, config, and log directories.

Uses platformdirs to resolve per-user, per-OS standard locations.
SHOPBOT_DATA_DIR env var overrides data_dir() and log_dir() on every call
so tests can monkeypatch without affecting the cached _DIRS singleton.
"""

from __future__ import annotations

import os
from pathlib import Path

from platformdirs import PlatformDirs

_APP_NAME = "shoppybot"
# appauthor=False suppresses the redundant vendor subdir on Windows,
# giving %LOCALAPPDATA%\shoppybot instead of %LOCALAPPDATA%\shoppybot\shoppybot.
_DIRS = PlatformDirs(_APP_NAME, appauthor=False)

# Monkeypatched in tests to redirect the legacy repo root away from the real checkout.
_REPO_ROOT_OVERRIDE: "Path | None" = None


def _env_override() -> Path | None:
    val = os.environ.get("SHOPBOT_DATA_DIR", "").strip()
    return Path(val) if val else None


def _repo_root() -> Path:
    """Return the repo root, using the test override when set."""
    if _REPO_ROOT_OVERRIDE is not None:
        return _REPO_ROOT_OVERRIDE
    return Path(__file__).parent.parent


def data_dir() -> Path:
    """Return the data directory, honouring SHOPBOT_DATA_DIR if set."""
    return _env_override() or Path(_DIRS.user_data_dir)


def config_path() -> Path:
    """Return the path to config.yml under the data directory."""
    return data_dir() / "config.yml"


def log_dir() -> Path:
    """Return the log directory, honouring SHOPBOT_DATA_DIR if set."""
    override = _env_override()
    if override:
        return override / "logs"
    return Path(_DIRS.user_log_dir)


def _migrate_logs(repo_root: Path) -> None:
    """Copy legacy logs/ dir to log_dir() and remove the src. No-op if already done."""
    import shutil
    from logger import writeLog  # lazy: avoids circular import (logger imports paths)

    legacy_logs = repo_root / "logs"
    new_logs = log_dir()
    if legacy_logs.is_dir() and not new_logs.exists():
        shutil.copytree(str(legacy_logs), str(new_logs))
        shutil.rmtree(str(legacy_logs))
        writeLog(f"Migrated logs {legacy_logs} -> {new_logs}", "INFO")


def migrate_legacy_paths() -> None:
    """Move project-relative legacy data to OS-standard locations (idempotent).

    Runs copy2-before-unlink so src is intact if the copy fails.
    Guard `src.exists() and not dst.exists()` makes every run a no-op once done.
    Logs only src->dst path strings; never reads or logs creds.bin content.
    """
    import shutil
    from logger import writeLog  # lazy: avoids circular import

    root = _repo_root()
    migrations = [
        (root / "data" / "shop_py_bot.db", data_dir() / "shop_py_bot.db"),
        (root / "data" / "creds.bin",       data_dir() / "creds.bin"),
        (root / "config.yml",               config_path()),
    ]
    for src, dst in migrations:
        if src.exists() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            src.unlink()
            writeLog(f"Migrated {src} -> {dst}", "INFO")

    _migrate_logs(root)
