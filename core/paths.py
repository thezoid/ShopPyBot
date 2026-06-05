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


def _env_override() -> Path | None:
    val = os.environ.get("SHOPBOT_DATA_DIR", "").strip()
    return Path(val) if val else None


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
