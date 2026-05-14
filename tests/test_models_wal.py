"""Phase 4 RED skeleton for ASYNC-04 (see 04-01-PLAN.md).

All tests in this file are expected to FAIL until Plan 04-02 lands.
ASYNC-04: SQLite WAL journal mode, busy_timeout >= 5000ms, _connect context
manager that rolls back on exception.
"""
import sqlite3

import pytest

from models import initialize_db, _connect  # noqa: F401 — ImportError is the RED signal


def test_journalModeIsWal(tmpDbPath):
    """initialize_db must leave the database in WAL journal mode."""
    initialize_db(delete=True)

    conn = sqlite3.connect(str(tmpDbPath))
    try:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    finally:
        conn.close()

    assert mode.lower() == "wal", f"expected journal_mode=wal, got {mode!r}"


def test_busyTimeoutApplied(tmpDbPath):
    """Connections opened via _connect must have busy_timeout >= 5000ms."""
    initialize_db(delete=True)

    with _connect() as conn:
        timeoutMs = conn.execute("PRAGMA busy_timeout").fetchone()[0]

    assert timeoutMs >= 5000, f"expected busy_timeout >= 5000ms, got {timeoutMs}"


def test_contextManagerRollback(tmpDbPath):
    """Exception inside _connect block must roll back the transaction."""
    initialize_db(delete=True)

    with pytest.raises(RuntimeError):
        with _connect() as conn:
            conn.execute(
                "INSERT INTO items (name, link, auto_buy, quantity, purchased) "
                "VALUES (?, ?, ?, ?, ?)",
                ("rollback-me", "https://example.com/rollback", 0, 1, 0),
            )
            raise RuntimeError("force rollback")

    conn = sqlite3.connect(str(tmpDbPath))
    try:
        rows = conn.execute(
            "SELECT COUNT(*) FROM items WHERE link = ?",
            ("https://example.com/rollback",),
        ).fetchone()
    finally:
        conn.close()

    assert rows[0] == 0, "row inserted before exception must be rolled back"
