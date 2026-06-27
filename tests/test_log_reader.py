"""test_log_reader.py: Wave 0 RED scaffold for tail_log_lines cursor function.

Three tests asserting the (new_lines, new_cursor) tuple contract for the cursor-based
tail function to be added to web/log_reader.py in Plan 02.

Every test FAILS on ImportError because tail_log_lines does not exist yet -- that is
the intended RED state. The file itself parses as valid Python (no syntax errors).

Midnight rollover: if after_line > total (new file has fewer lines than cursor),
tail_log_lines must reset by returning all lines of the new file and cursor=total.
"""
import pytest
from web.log_reader import tail_log_lines


# ---------------------------------------------------------------------------
# Test 1: returns only new lines from cursor position
# ---------------------------------------------------------------------------


def test_tail_returns_new_lines_from_cursor(monkeypatch):
    """tail_log_lines(2) on a 5-line file returns (lines[2:], 5): the 3 trailing lines."""
    fake_lines = ["line0", "line1", "line2", "line3", "line4"]
    monkeypatch.setattr("web.log_reader._read_today_lines", lambda: fake_lines)

    new_lines, new_cursor = tail_log_lines(2)

    assert new_lines == ["line2", "line3", "line4"], (
        f"Expected lines[2:] but got: {new_lines!r}"
    )
    assert new_cursor == 5, (
        f"Expected cursor=5 (total lines) but got: {new_cursor!r}"
    )


# ---------------------------------------------------------------------------
# Test 2: returns empty list and unchanged cursor when at end of file
# ---------------------------------------------------------------------------


def test_tail_advances_cursor_no_new_lines(monkeypatch):
    """tail_log_lines(5) on a 5-line file returns ([], 5): nothing new, cursor unchanged."""
    fake_lines = ["line0", "line1", "line2", "line3", "line4"]
    monkeypatch.setattr("web.log_reader._read_today_lines", lambda: fake_lines)

    new_lines, new_cursor = tail_log_lines(5)

    assert new_lines == [], (
        f"Expected [] (no new lines) but got: {new_lines!r}"
    )
    assert new_cursor == 5, (
        f"Expected cursor=5 but got: {new_cursor!r}"
    )


# ---------------------------------------------------------------------------
# Test 3: midnight rollover resets cursor and returns all lines of new file
# ---------------------------------------------------------------------------


def test_tail_rollover_resets_cursor(monkeypatch):
    """tail_log_lines(10) on a 2-line file triggers rollover: returns (all 2 lines, 2).

    After midnight the file rolls to a new day with fewer lines than the cursor.
    after_line (10) > total (2) signals rollover; the function must reset to the
    new file's total and return all lines from the fresh file.
    """
    fresh_lines = ["new_line0", "new_line1"]
    monkeypatch.setattr("web.log_reader._read_today_lines", lambda: fresh_lines)

    new_lines, new_cursor = tail_log_lines(10)

    assert new_lines == fresh_lines, (
        f"Expected all lines from new file {fresh_lines!r} but got: {new_lines!r}"
    )
    assert new_cursor == 2, (
        f"Expected cursor=2 (new total, not stale cursor 10) but got: {new_cursor!r}"
    )
