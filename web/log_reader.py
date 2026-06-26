"""web/log_reader.py: read recent lines from today's log file."""

import datetime
import pathlib

_LOG_DIR = pathlib.Path(__file__).parent.parent / "logs"


def read_recent_logs(n: int = 50) -> list[str]:
    """Return the last n lines from today's log file.

    Uses the same strftime format as logger.py ('%Y%B%d') so the filename
    matches what the logger writes (e.g. '2026June04.log').
    Returns an empty list if the log file does not exist today.
    """
    fname = datetime.datetime.now().strftime("%Y%B%d") + ".log"
    log_path = _LOG_DIR / fname
    if not log_path.exists():
        return []
    text = log_path.read_text(encoding="utf-8", errors="replace")
    return text.splitlines()[-n:]


def read_logs_filtered(
    n: int = 50,
    level: str | None = None,
    search: str | None = None,
) -> list[str]:
    """Return the last n log lines, optionally filtered by level and/or search term.

    Filtering is applied to the n-line slice from read_recent_logs (not the full file).
    level: keep only lines starting with f"[{level.upper()}]".
    search: keep only lines containing search (case-insensitive substring match).
    Both filters are AND-combined when both are provided.
    No filters returns the same result as read_recent_logs(n).
    """
    lines = read_recent_logs(n)
    if level is not None:
        prefix = f"[{level.upper()}]"
        lines = [line for line in lines if line.startswith(prefix)]
    if search is not None:
        needle = search.lower()
        lines = [line for line in lines if needle in line.lower()]
    return lines
