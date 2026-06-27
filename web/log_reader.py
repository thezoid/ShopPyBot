"""web/log_reader.py: read recent lines from today's log file."""

import datetime
import pathlib

_LOG_DIR = pathlib.Path(__file__).parent.parent / "logs"


def _read_today_lines() -> list[str]:
    """Return ALL lines from today's log file (empty list if it does not exist).

    Uses the same strftime format as logger.py ('%Y%B%d') so the filename matches
    what the logger writes (e.g. '2026June04.log').
    """
    fname = datetime.datetime.now().strftime("%Y%B%d") + ".log"
    log_path = _LOG_DIR / fname
    if not log_path.exists():
        return []
    return log_path.read_text(encoding="utf-8", errors="replace").splitlines()


def read_recent_logs(n: int = 50) -> list[str]:
    """Return the last n lines from today's log file (empty list if none)."""
    return _read_today_lines()[-n:]


def read_logs_filtered(
    n: int = 50,
    level: str | None = None,
    search: str | None = None,
) -> list[str]:
    """Return the last n log lines that match the optional filters.

    Filter-then-limit: filters are applied to the WHOLE day's log first, then the
    last n matching lines are returned. This guarantees up to n *matching* lines
    (a level/search query won't silently return fewer than n just because the
    matches sit earlier than the n-line tail).
    level: keep only lines starting with f"[{level.upper()}]".
    search: keep only lines containing search (case-insensitive substring match).
    Both filters are AND-combined when both are provided.
    No filters returns the same result as read_recent_logs(n).
    """
    lines = _read_today_lines()
    if level is not None:
        prefix = f"[{level.upper()}]"
        lines = [line for line in lines if line.startswith(prefix)]
    if search is not None:
        needle = search.lower()
        lines = [line for line in lines if needle in line.lower()]
    return lines[-n:]


def tail_log_lines(after_line: int) -> tuple[list[str], int]:
    """Return (new_lines, new_cursor) from today's log, starting after after_line.

    after_line: 0-based count of lines already consumed. Returns lines[after_line:].
    Midnight rollover: if after_line > total, the file has rolled to a new day;
    reset cursor to the new total and return all lines from the fresh file.
    """
    lines = _read_today_lines()
    total = len(lines)
    if after_line > total:
        return lines, total
    return lines[after_line:], total
