"""
WAL PRAGMA, context-manager close, and concurrent-write stress proxy tests.
ASYNC-04 / ASYNC-05 — Plan 04-02
"""
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from models import (
    add_items_sync,
    get_db_connection,
    get_items_sync,
    initialize_db,
    update_item_purchased_sync,
)


@pytest.fixture
def db(tmp_data_dir):
    """Fresh DB in a temp dir. Returns tmp_path for reference."""
    initialize_db(delete=True)
    return tmp_data_dir


def test_wal_pragma_applied(db):
    """After opening via get_db_connection, journal_mode is 'wal'."""
    with get_db_connection() as conn:
        row = conn.execute("PRAGMA journal_mode").fetchone()
    assert row[0] == "wal", f"Expected 'wal', got {row[0]!r}"


def test_busy_timeout_applied(db):
    """busy_timeout pragma returns 5000 on a fresh connection."""
    with get_db_connection() as conn:
        row = conn.execute("PRAGMA busy_timeout").fetchone()
    assert row[0] == 5000, f"Expected 5000, got {row[0]!r}"


def test_synchronous_normal_applied(db):
    """synchronous pragma returns 1 (NORMAL) on a fresh connection."""
    with get_db_connection() as conn:
        # SQLite returns integer: 0=OFF, 1=NORMAL, 2=FULL, 3=EXTRA
        row = conn.execute("PRAGMA synchronous").fetchone()
    assert row[0] == 1, f"Expected 1 (NORMAL), got {row[0]!r}"


def test_connection_closed_on_exit(db):
    """The connection is closed after the with-block exits cleanly."""
    with get_db_connection() as conn:
        pass
    # Any operation on a closed sqlite3 connection raises ProgrammingError.
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_connection_closed_on_exception(db):
    """The connection is closed even when the body raises."""
    conn_ref = None
    try:
        with get_db_connection() as conn:
            conn_ref = conn
            raise ValueError("simulated error")
    except ValueError:
        pass
    assert conn_ref is not None
    with pytest.raises(sqlite3.ProgrammingError):
        conn_ref.execute("SELECT 1")


def test_concurrent_writes_no_lock(db):
    """Many concurrent update_item_purchased_sync calls produce zero OperationalError.

    This is the short stress proxy for the 60-min soak (SC-4). Full soak is
    human-verify. Each worker updates a distinct link so they serialise at the WAL
    writer lock rather than colliding on the same row.
    """
    n_items = 20
    items = [
        (f"Item {i}", f"https://example.com/item{i}", False, 1, False)
        for i in range(n_items)
    ]
    add_items_sync(items)

    errors = []
    links = [f"https://example.com/item{i}" for i in range(n_items)]

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(update_item_purchased_sync, link): link for link in links}
        for future in as_completed(futures):
            try:
                future.result()
            except sqlite3.OperationalError as exc:
                errors.append(str(exc))

    assert errors == [], f"'database is locked' errors: {errors}"

    # Verify all rows were actually updated.
    purchased = [row[4] for row in get_items_sync()]
    assert all(p == 1 for p in purchased), f"Some items not marked purchased: {purchased}"
