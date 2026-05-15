"""SQLite layer (Phase 4: WAL + busy_timeout + context manager).

Connection rules:
- WAL mode is set ONCE in initialize_db() and persisted by an immediate write.
- busy_timeout is per-connection PRAGMA; applied inside _connect().
- Every public function uses `with _connect() as conn:`. No raw sqlite3.connect.
- Connections are NOT cached at module scope (SQLite connections cannot cross threads).
"""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

DB_PATH = os.path.join("data", "shop_py_bot.db")
BUSY_TIMEOUT_MS = 5000


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    """Single chokepoint for sqlite3 connections.

    Applies per-connection busy_timeout PRAGMA, commits on success, rolls back
    on exception, and always closes the connection.
    """
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS};")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _column_exists(conn, table: str, column: str) -> bool:
    """Return True iff `column` exists on `table` per PRAGMA table_info."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in rows)


def _migrate_add_last_notified_at(conn) -> None:
    """Idempotent migration: add last_notified_at column if absent (Phase 5 NOTIF-02).

    Plain ADD COLUMN is NOT idempotent in SQLite (duplicate column error on
    re-run). Precheck with PRAGMA table_info so legacy v1 databases upgrade
    without dropping data and fresh-install runs are no-ops.
    """
    if not _column_exists(conn, "items", "last_notified_at"):
        conn.execute(
            "ALTER TABLE items ADD COLUMN last_notified_at TIMESTAMP NULL"
        )


def initialize_db(delete: bool = False) -> None:
    if delete and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    parentDir = os.path.dirname(DB_PATH)
    if parentDir:
        os.makedirs(parentDir, exist_ok=True)
    with _connect() as conn:
        # WAL set FIRST, then a CREATE TABLE write so SQLite persists the
        # journal mode change in the file header.
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                link TEXT NOT NULL UNIQUE,
                auto_buy BOOLEAN NOT NULL,
                quantity INTEGER NOT NULL,
                purchased BOOLEAN NOT NULL DEFAULT 0,
                last_notified_at TIMESTAMP NULL
            )"""
        )
        _migrate_add_last_notified_at(conn)


def add_items(items) -> None:
    with _connect() as conn:
        for item in items:
            row = conn.execute(
                "SELECT COUNT(*) FROM items WHERE link = ?", (item[1],)
            ).fetchone()
            if row[0] == 0:
                conn.execute(
                    "INSERT INTO items (name, link, auto_buy, quantity, purchased) "
                    "VALUES (?, ?, ?, ?, ?)",
                    item,
                )


def update_item_purchased(link: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE items SET purchased = 1 WHERE link = ?", (link,))


def get_items():
    with _connect() as conn:
        return conn.execute(
            "SELECT name, link, auto_buy, quantity, purchased FROM items"
        ).fetchall()


def should_notify(link: str, restock_window_seconds: int) -> bool:
    """True if no prior notification recorded OR last notification older than window.

    Uses the Phase 4 _connect() context manager. Tz-naive timestamps from
    SQLite CURRENT_TIMESTAMP are backfilled to UTC before arithmetic.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT last_notified_at FROM items WHERE link = ?", (link,)
        ).fetchone()
        if row is None or row[0] is None:
            return True
        last = datetime.fromisoformat(row[0])
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - last).total_seconds()
        return elapsed > restock_window_seconds


def mark_notified(link: str) -> None:
    """Set last_notified_at = CURRENT_TIMESTAMP for `link` (parameterized)."""
    with _connect() as conn:
        conn.execute(
            "UPDATE items SET last_notified_at = CURRENT_TIMESTAMP WHERE link = ?",
            (link,),
        )
