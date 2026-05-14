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
                purchased BOOLEAN NOT NULL DEFAULT 0
            )"""
        )


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
