import logging
import os
from datetime import datetime
from pathlib import Path
from colorama import Fore, Style
import yaml


def _load_logging_level() -> int:
    from core.paths import config_path as _config_path  # lazy: avoids circular import
    try:
        with open(_config_path(), 'r') as file:
            settings = yaml.safe_load(file)
        return int(settings.get('debug', {}).get('logging_level', 5))
    except (FileNotFoundError, KeyError, TypeError, ValueError):
        return 5

_LOGGING_LEVEL: int = _load_logging_level()

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
        print(f"{color}[{type.upper()}][{datetime.now().strftime('%Y%B%d@%H:%M:%S')}] {message}{Style.RESET_ALL}")
        if writeTofile:
            from core.paths import log_dir as _paths_log_dir  # lazy: avoids circular import with core/paths.py
            _log_dir = _paths_log_dir()
            _log_dir.mkdir(parents=True, exist_ok=True)
            log_file_path = _log_dir / f"{datetime.now().strftime('%Y%B%d')}.log"
            with open(log_file_path, "a", encoding="utf-8") as logFile:
                logFile.write(f"[{type.upper()}][{datetime.now().strftime('%Y%B%d@%H:%M:%S')}] {message}\n")