import contextlib
import os
import sqlite3

DB_PATH = os.path.join('data', 'shop_py_bot.db')


@contextlib.contextmanager
def get_db_connection():
    """Open a WAL-enabled connection, yield it, commit/rollback, close.

    PRAGMA sequence (ASYNC-04, exact order required):
      journal_mode=WAL    -- readers never block writers under concurrent polling
      busy_timeout=5000   -- retry for up to 5s on write-lock contention
      synchronous=NORMAL  -- safe with WAL; better throughput than FULL
    """
    conn = sqlite3.connect(DB_PATH, timeout=5)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA synchronous=NORMAL")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_db(delete=False):
    if delete and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_db_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                link TEXT NOT NULL UNIQUE,
                auto_buy BOOLEAN NOT NULL,
                quantity INTEGER NOT NULL,
                purchased BOOLEAN NOT NULL DEFAULT 0
            )
        ''')
        # Idempotent column additions: read existing columns first, add only if absent.
        existing = {
            row[1]
            for row in conn.execute("PRAGMA table_info(items)").fetchall()
        }
        if "last_seen_available" not in existing:
            conn.execute(
                "ALTER TABLE items ADD COLUMN last_seen_available INTEGER NOT NULL DEFAULT 0"
            )
        if "last_notified" not in existing:
            conn.execute(
                "ALTER TABLE items ADD COLUMN last_notified TEXT"
            )


def get_items_sync():
    """Return all items as a list of (name, link, auto_buy, quantity, purchased)."""
    with get_db_connection() as conn:
        return conn.execute(
            "SELECT name, link, auto_buy, quantity, purchased FROM items"
        ).fetchall()


def update_item_purchased_sync(link):
    """Set purchased=1 for the item with the given link."""
    with get_db_connection() as conn:
        conn.execute("UPDATE items SET purchased=1 WHERE link=?", (link,))


def add_items_sync(items):
    """Insert items that are not already present (unique by link)."""
    with get_db_connection() as conn:
        for item in items:
            count = conn.execute(
                "SELECT COUNT(*) FROM items WHERE link=?", (item[1],)
            ).fetchone()[0]
            if count == 0:
                conn.execute(
                    "INSERT INTO items (name, link, auto_buy, quantity, purchased)"
                    " VALUES (?, ?, ?, ?, ?)",
                    item,
                )


def get_item_notification_state_sync(link: str) -> tuple[bool, str | None]:
    """Return (last_seen_available as bool, last_notified) for dedup checks (NOTIF-02)."""
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT last_seen_available, last_notified FROM items WHERE link=?",
            (link,),
        ).fetchone()
    if row is None:
        return False, None
    return bool(row[0]), row[1]


def set_item_available_sync(link: str, notified_at: str) -> None:
    """Set last_seen_available=1 and last_notified=notified_at for rising-edge dedup (NOTIF-02)."""
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE items SET last_seen_available=1, last_notified=? WHERE link=?",
            (notified_at, link),
        )


def clear_item_available_sync(link: str) -> None:
    """Set last_seen_available=0 (item went out of stock); preserve last_notified (NOTIF-02)."""
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE items SET last_seen_available=0 WHERE link=?",
            (link,),
        )


# Legacy names kept for backward compatibility (existing tests and imports).
# Single source of truth: body lives in the _sync functions above.

def get_items():
    return get_items_sync()


def update_item_purchased(link):
    return update_item_purchased_sync(link)


def add_items(items):
    return add_items_sync(items)
