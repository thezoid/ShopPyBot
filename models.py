import contextlib
import os
import sqlite3

from core.paths import data_dir as _paths_data_dir

DB_PATH = str(_paths_data_dir() / "shop_py_bot.db")


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
        # Phase 16: price monitoring columns (idempotent -- PRICE-01, PRICE-05).
        if "target_price" not in existing:
            conn.execute("ALTER TABLE items ADD COLUMN target_price INTEGER")
        if "price_drop_pct" not in existing:
            conn.execute("ALTER TABLE items ADD COLUMN price_drop_pct REAL")
        if "price_alert_armed" not in existing:
            conn.execute(
                "ALTER TABLE items ADD COLUMN price_alert_armed INTEGER NOT NULL DEFAULT 0"
            )
        if "price_last_notified" not in existing:
            conn.execute("ALTER TABLE items ADD COLUMN price_last_notified TEXT")
        # Phase 19: confirmation columns (BUY-03, BUY-04).
        if "order_id" not in existing:
            conn.execute("ALTER TABLE items ADD COLUMN order_id TEXT")
        if "confirmed_at" not in existing:
            conn.execute("ALTER TABLE items ADD COLUMN confirmed_at TEXT")
        if "checkout_attempts" not in existing:
            conn.execute(
                "ALTER TABLE items ADD COLUMN checkout_attempts INTEGER NOT NULL DEFAULT 0"
            )
        # Phase 16: append-only price history table (PRICE-02).
        conn.execute('''
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY,
                item_link TEXT NOT NULL,
                price_cents INTEGER NOT NULL,
                currency TEXT NOT NULL DEFAULT 'USD',
                scraped_at TEXT NOT NULL
            )
        ''')


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


def update_item_confirmed_sync(link: str, order_id: str, confirmed_at: str) -> None:
    """Set purchased=1, order_id, and confirmed_at together (BUY-03/BUY-04).

    The order_id column is the idempotency anchor for Phase 21 retry (BUY-05).
    Does not touch checkout_attempts (increment is Phase 21 scope).
    """
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE items SET purchased=1, order_id=?, confirmed_at=? WHERE link=?",
            (order_id, confirmed_at, link),
        )


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


def remove_item_sync(link):
    """Delete the item with the given link (parameterized DELETE)."""
    with get_db_connection() as conn:
        conn.execute("DELETE FROM items WHERE link=?", (link,))


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


# ---------------------------------------------------------------------------
# Phase 16: price history + price-alert dedup + price config (PRICE-01/02/05)
# ---------------------------------------------------------------------------


def append_price_history_sync(
    link: str, price_cents: int, scraped_at: str, currency: str = "USD"
) -> None:
    """Insert one price observation into the append-only price_history table."""
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO price_history (item_link, price_cents, currency, scraped_at)"
            " VALUES (?, ?, ?, ?)",
            (link, price_cents, currency, scraped_at),
        )


def get_price_history_sync(link: str, limit: int = 10) -> list[tuple]:
    """Return last N (price_cents, currency, scraped_at) rows, newest first."""
    with get_db_connection() as conn:
        return conn.execute(
            "SELECT price_cents, currency, scraped_at FROM price_history"
            " WHERE item_link=? ORDER BY scraped_at DESC LIMIT ?",
            (link, limit),
        ).fetchall()


def get_last_price_sync(link: str) -> int | None:
    """Return the most recent price_cents for the item, or None if no history."""
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT price_cents FROM price_history"
            " WHERE item_link=? ORDER BY scraped_at DESC LIMIT 1",
            (link,),
        ).fetchone()
    return row[0] if row else None


def get_price_alert_state_sync(link: str) -> tuple[bool, str | None]:
    """Return (price_alert_armed as bool, price_last_notified) for price dedup.

    Returns (False, None) when the item row is missing.
    """
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT price_alert_armed, price_last_notified FROM items WHERE link=?",
            (link,),
        ).fetchone()
    if row is None:
        return False, None
    return bool(row[0]), row[1]


def set_price_alert_armed_sync(link: str, notified_at: str) -> None:
    """Set price_alert_armed=1 and price_last_notified for price-drop dedup.

    MUST NOT touch last_seen_available or last_notified (Pitfall 1).
    """
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE items SET price_alert_armed=1, price_last_notified=? WHERE link=?",
            (notified_at, link),
        )


def clear_price_alert_armed_sync(link: str) -> None:
    """Reset price_alert_armed=0 (price recovered above threshold)."""
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE items SET price_alert_armed=0 WHERE link=?",
            (link,),
        )


def update_item_price_config_sync(
    link: str, target_price: int | None, price_drop_pct: float | None
) -> None:
    """Write per-item price monitoring config to the items table (PRICE-01/05).

    Called after add_items_sync to seed config from ItemConfig fields.
    Idempotent: NULL overwrites NULL when config has no price targets.
    """
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE items SET target_price=?, price_drop_pct=? WHERE link=?",
            (target_price, price_drop_pct, link),
        )


def get_item_price_config_sync(link: str) -> tuple[int | None, float | None] | None:
    """Return (target_price, price_drop_pct) for the item, or None if row missing."""
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT target_price, price_drop_pct FROM items WHERE link=?",
            (link,),
        ).fetchone()
    if row is None:
        return None
    return row[0], row[1]


# Legacy names kept for backward compatibility (existing tests and imports).
# Single source of truth: body lives in the _sync functions above.

def get_items():
    return get_items_sync()


def update_item_purchased(link):
    return update_item_purchased_sync(link)


def add_items(items):
    return add_items_sync(items)
