import logging
import os
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from colorama import Fore, Style
import yaml


def _load_logging_level() -> int:
    # Try the migrated AppData path first; fall back to the legacy repo-root path on
    # first boot before migrate_legacy_paths() has run (WR-03: migration runs after
    # imports, so the migrated file may not exist yet on the very first boot).
    from core.paths import config_path as _config_path  # lazy: avoids circular import
    candidates = [_config_path(), Path(__file__).parent / "config.yml"]
    for path in candidates:
        try:
            with open(path, 'r') as f:
                settings = yaml.safe_load(f)
            return int(settings.get('debug', {}).get('logging_level', 5))
        except (FileNotFoundError, KeyError, TypeError, ValueError):
            continue
    return 5

_LOGGING_LEVEL: int = _load_logging_level()

# FC-01: per-task active-plugin tag, injected into every writeLog line as the
# second bracket (after the level). Defaults to the "core" sentinel when no
# plugin task has set it (startup, web tier, service init). Set once per
# plugin task in core/orchestrator.py:supervise(); asyncio.create_task/TaskGroup
# copy the context at task creation, so each plugin task's .set() is isolated.
_current_plugin: ContextVar[str] = ContextVar("current_plugin", default="core")


def set_log_plugin(platform_key: str):
    """Set the active plugin tag for all writeLog calls in the current context/task.

    Falsy input (None, "") coerces to the "core" sentinel. Returns the Token
    from ContextVar.set() (callers may reset via it, but per-task context
    isolation makes an explicit reset optional).
    """
    return _current_plugin.set(platform_key or "core")


def setup_logger():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    return logging.getLogger(__name__)

def writeLog(message: str, type: str, writeTofile: bool = True) -> None:
    loggingLevel = _LOGGING_LEVEL
    log_levels = {
        "ALWAYS": (Fore.CYAN, 0),
        "ERROR": (Fore.RED, 1),
        "WARNING": (Fore.YELLOW, 2),
        "SUCCESS": (Fore.GREEN, 2),
        "INFO": (Fore.WHITE, 3),
        "DEBUG": (Fore.BLUE, 4),
        "TRACE": (Fore.MAGENTA, 5)
    }
    color, level = log_levels.get(type.upper(), (Fore.LIGHTBLACK_EX, 0))
    if loggingLevel >= level:
        plugin = _current_plugin.get()
        ts = datetime.now().strftime('%Y%B%d@%H:%M:%S')
        head = f"[{type.upper()}][{plugin}][{ts}]"
        print(f"{color}{head} {message}{Style.RESET_ALL}")
        if writeTofile:
            from core.paths import log_dir as _paths_log_dir  # lazy: avoids circular import with core/paths.py
            _log_dir = _paths_log_dir()
            _log_dir.mkdir(parents=True, exist_ok=True)
            log_file_path = _log_dir / f"{datetime.now().strftime('%Y%B%d')}.log"
            with open(log_file_path, "a", encoding="utf-8") as logFile:
                logFile.write(f"{head} {message}\n")