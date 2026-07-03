"""web/log_reader.py: read recent lines from today's log file."""

import datetime


def _read_today_lines() -> list[str]:
    """Return ALL lines from today's log file (empty list if it does not exist).

    Resolves the log directory via core.paths.log_dir() — the SAME source logger.py
    writes to. (CR-01: the previous hardcoded <repo>/logs path is copied-then-deleted
    by core.paths path migration on first boot, so log reads silently returned nothing
    and every /api/logs response + SSE log frame was empty in production.) Resolving
    on each call also honours the SHOPBOT_DATA_DIR override used by tests. Uses the same
    strftime format as logger.py ('%Y%B%d') for the filename (e.g. '2026June04.log').
    """
    from core.paths import log_dir  # lazy: matches logger.py, avoids import cycle
    fname = datetime.datetime.now().strftime("%Y%B%d") + ".log"
    log_path = log_dir() / fname
    if not log_path.exists():
        return []
    return log_path.read_text(encoding="utf-8", errors="replace").splitlines()


def read_recent_logs(n: int = 50) -> list[str]:
    """Return the last n lines from today's log file (empty list if none)."""
    return _read_today_lines()[-n:]


def _plugin_tag_matches(line: str, plugin: str) -> bool:
    """Return True only if `plugin` is the SECOND bracket (`[LEVEL][plugin][ts] msg`).

    IN-03: `tag in line` matched `[plugin]` as a free-floating substring anywhere
    in the line -- including inside the free-text message body (e.g. an error
    message that happens to echo another plugin's bracketed name). Anchoring to
    the position immediately after the first `]` restricts the match to the
    actual tag logger.py injects, never the message text.
    """
    first_close = line.find("]")
    if first_close == -1:
        return False
    return line.startswith(f"[{plugin}]", first_close + 1)


def read_logs_filtered(
    n: int = 50,
    level: str | None = None,
    search: str | None = None,
    plugin: str | None = None,
) -> list[str]:
    """Return the last n log lines that match the optional filters.

    Filter-then-limit: filters are applied to the WHOLE day's log first, then the
    last n matching lines are returned. This guarantees up to n *matching* lines
    (a level/search query won't silently return fewer than n just because the
    matches sit earlier than the n-line tail).
    level: keep only lines starting with f"[{level.upper()}]".
    plugin: keep only lines whose SECOND bracket is exactly f"[{plugin}]" -- the
        guaranteed [plugin] tag injected by logger.py's ContextVar (FC-01, 34-01),
        anchored by position (IN-03) so a message body that happens to contain a
        literal "[plugin]"-shaped substring can never false-positive match.
    search: keep only lines containing search (case-insensitive substring match).
    All filters are AND-combined when provided together.
    No filters returns the same result as read_recent_logs(n).
    """
    lines = _read_today_lines()
    if level is not None:
        prefix = f"[{level.upper()}]"
        lines = [line for line in lines if line.startswith(prefix)]
    if plugin is not None:
        lines = [line for line in lines if _plugin_tag_matches(line, plugin)]
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
