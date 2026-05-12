"""Color + file logger (INFRA-02 refactor).

Per-call yaml.safe_load is removed: configure(level) sets a module-level int
once at startup, and writeLog reads it directly. Signature, type strings, and
timestamped color print format are preserved verbatim from the legacy logger
because downstream callers depend on them.
"""
import functools
import os
from datetime import datetime

from colorama import Fore, Style

LOG_LEVELS = {
    "ALWAYS": (Fore.CYAN, 0),
    "ERROR": (Fore.RED, 1),
    "WARNING": (Fore.YELLOW, 2),
    "SUCCESS": (Fore.GREEN, 2),
    "INFO": (Fore.WHITE, 3),
    "DEBUG": (Fore.BLUE, 4),
    "TRACE": (Fore.MAGENTA, 5),
}

_logging_level: int | None = None  # set once via configure()


def configure(level: int) -> None:
    """Called once from main.py after AppConfig loads."""
    global _logging_level
    _logging_level = level


def writeLog(message: str, type: str, writeTofile: bool = True) -> None:
    levelThreshold = 5 if _logging_level is None else _logging_level
    color, level = LOG_LEVELS.get(type.upper(), (Fore.LIGHTBLACK_EX, 0))
    if levelThreshold >= level:
        ts = datetime.now().strftime('%Y%B%d@%H:%M:%S')
        print(f"{color}[{type.upper()}][{ts}] {message}{Style.RESET_ALL}")
        if writeTofile:
            _writeToFile(type, ts, message)


@functools.cache
def _logDir() -> str:
    here = os.path.dirname(os.path.realpath(__file__))
    d = os.path.join(here, "logs")
    os.makedirs(d, exist_ok=True)
    return d


def _writeToFile(type: str, ts: str, message: str) -> None:
    path = os.path.join(_logDir(), f"{datetime.now().strftime('%Y%B%d')}.log")
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"[{type.upper()}][{ts}] {message}\n")
