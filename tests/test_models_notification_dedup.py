"""Phase 5 RED skeleton for NOTIF-02 dedup helpers (see 05-01-PLAN.md).

Tests in this file PASS today because Plan 05-01 ships should_notify,
mark_notified, and the idempotent migration. They serve as the regression
net for NOTIF-02, not a RED target.
"""
from models import (
    _connect,
    _migrate_add_last_notified_at,
    add_items,
    initialize_db,
    mark_notified,
    should_notify,
)


def _seedRow(link: str) -> None:
    """Insert one item with the given link."""
    add_items([("Widget", link, False, 1, 0)])


def test_shouldNotifyTrueForUnknownLink(tmpDbPath):
    initialize_db(delete=True)
    assert should_notify("https://example.com/missing", 600) is True


def test_shouldNotifyTrueForNullColumn(tmpDbPath):
    initialize_db(delete=True)
    link = "https://example.com/null"
    _seedRow(link)
    assert should_notify(link, 600) is True


def test_shouldNotifyFalseInsideWindow(tmpDbPath):
    initialize_db(delete=True)
    link = "https://example.com/inside"
    _seedRow(link)
    mark_notified(link)
    assert should_notify(link, 600) is False


def test_shouldNotifyTrueAfterWindow(tmpDbPath):
    initialize_db(delete=True)
    link = "https://example.com/elapsed"
    _seedRow(link)
    # Simulate a stale notification 700 seconds in the past.
    with _connect() as conn:
        conn.execute(
            "UPDATE items SET last_notified_at = "
            "datetime(CURRENT_TIMESTAMP, '-700 seconds') WHERE link = ?",
            (link,),
        )
    assert should_notify(link, 600) is True


def test_markNotifiedSetsTimestamp(tmpDbPath):
    initialize_db(delete=True)
    link = "https://example.com/marked"
    _seedRow(link)
    mark_notified(link)
    with _connect() as conn:
        row = conn.execute(
            "SELECT last_notified_at FROM items WHERE link = ?", (link,)
        ).fetchone()
    assert row is not None and row[0] is not None


def test_migrationIdempotent(tmpDbPath):
    initialize_db(delete=True)
    # Second call must not raise even though column already exists.
    initialize_db(delete=False)
    with _connect() as conn:
        _migrate_add_last_notified_at(conn)  # third invocation; still no-op


def test_columnPresentAfterInit(tmpDbPath):
    initialize_db(delete=True)
    with _connect() as conn:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(items)").fetchall()]
    assert "last_notified_at" in cols
