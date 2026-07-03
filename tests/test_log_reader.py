"""test_log_reader.py: Wave 0 RED scaffold for tail_log_lines cursor function.

Three tests asserting the (new_lines, new_cursor) tuple contract for the cursor-based
tail function to be added to web/log_reader.py in Plan 02.

Every test FAILS on ImportError because tail_log_lines does not exist yet -- that is
the intended RED state. The file itself parses as valid Python (no syntax errors).

Midnight rollover: if after_line > total (new file has fewer lines than cursor),
tail_log_lines must reset by returning all lines of the new file and cursor=total.
"""
import pytest
from web.log_reader import tail_log_lines, read_logs_filtered


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


# ---------------------------------------------------------------------------
# Plugin filter tests (Phase 34 Plan 02 / FC-01: read_logs_filtered plugin param)
# ---------------------------------------------------------------------------


def test_read_logs_filtered_plugin_only(monkeypatch):
    """plugin filter keeps only lines containing the guaranteed [plugin] tag."""
    fake_lines = [
        "[INFO][amazon][ts] checking stock",
        "[INFO][bestbuy][ts] checking stock",
        "[ERROR][amazon][ts] captcha detected",
    ]
    monkeypatch.setattr("web.log_reader._read_today_lines", lambda: fake_lines)

    result = read_logs_filtered(50, None, None, "amazon")

    assert result == [
        "[INFO][amazon][ts] checking stock",
        "[ERROR][amazon][ts] captcha detected",
    ], f"Expected only [amazon]-tagged lines but got: {result!r}"


def test_read_logs_filtered_plugin_composes_with_level_and_search(monkeypatch):
    """plugin AND-composes with level+search: all three filters must match."""
    fake_lines = [
        "[ERROR][amazon][ts] captcha detected",
        "[ERROR][amazon][ts] timeout waiting",
        "[ERROR][bestbuy][ts] captcha detected",
        "[INFO][amazon][ts] captcha mentioned in passing",
    ]
    monkeypatch.setattr("web.log_reader._read_today_lines", lambda: fake_lines)

    result = read_logs_filtered(50, "ERROR", "captcha", "amazon")

    assert result == ["[ERROR][amazon][ts] captcha detected"], (
        f"Expected only the single line matching ERROR+captcha+amazon but got: {result!r}"
    )


def test_read_logs_filtered_plugin_does_not_match_substring_in_message(monkeypatch):
    """IN-03: the plugin filter is anchored to the SECOND-bracket tag position,
    not a free-floating substring match -- a message body that happens to
    contain a literal "[amazon]"-shaped string must not false-positive match."""
    fake_lines = [
        "[WARNING][bestbuy][ts] unexpected token seen: [amazon] fallback triggered",
        "[INFO][amazon][ts] checking stock",
    ]
    monkeypatch.setattr("web.log_reader._read_today_lines", lambda: fake_lines)

    result = read_logs_filtered(50, None, None, "amazon")

    assert result == ["[INFO][amazon][ts] checking stock"], (
        f"Expected only the genuinely [amazon]-tagged line, got: {result!r}"
    )


def test_read_logs_filtered_plugin_none_passthrough(monkeypatch):
    """plugin=None applies no plugin filtering -- existing callers unchanged."""
    fake_lines = [
        "[INFO][amazon][ts] checking stock",
        "[INFO][bestbuy][ts] checking stock",
    ]
    monkeypatch.setattr("web.log_reader._read_today_lines", lambda: fake_lines)

    result = read_logs_filtered(50, None, None, None)

    assert result == fake_lines, (
        f"Expected byte-identical passthrough with plugin=None but got: {result!r}"
    )
