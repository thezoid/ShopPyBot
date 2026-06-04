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
