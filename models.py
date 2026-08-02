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
        # Phase 30: place-order write-ahead marker (BF-02 double-buy guard).
        if "place_order_attempted_at" not in existing:
            conn.execute(
                "ALTER TABLE items ADD COLUMN place_order_attempted_at TEXT"
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


def get_confirmed_orders_sync():
    """Return (name, order_id, confirmed_at, checkout_attempts) for purchased items.

    Returns rows WHERE purchased=1. order_id and confirmed_at may be None for
    legacy rows created before BUY-04 added those columns.
    """
    with get_db_connection() as conn:
        return conn.execute(
            "SELECT name, order_id, confirmed_at, checkout_attempts"
            " FROM items WHERE purchased=1"
        ).fetchall()


def get_order_analytics_rows_sync():
    """Return rows needed for outcome analytics (FC-02). Read-only.

    Selects every item that was attempted (place-order marker set) OR has an
    order_id, plus the two durable buy-flow timestamps. link is included ONLY
    for platform resolution by the caller (core/service.py:get_analytics) --
    it must never be forwarded into the analytics response.
    """
    with get_db_connection() as conn:
        return conn.execute(
            "SELECT name, link, order_id, confirmed_at, checkout_attempts,"
            " place_order_attempted_at, purchased"
            " FROM items"
            " WHERE place_order_attempted_at IS NOT NULL OR order_id IS NOT NULL"
        ).fetchall()


def update_item_purchased_sync(link):
    """Set purchased=1 for the item with the given link."""
    with get_db_connection() as conn:
        conn.execute("UPDATE items SET purchased=1 WHERE link=?", (link,))


def increment_checkout_attempts_sync(link: str) -> None:
    """Increment checkout_attempts by exactly 1 for the given link (BUY-05/REL-08).

    Uses a relative SQL increment so each call adds 1 without knowing the current value.
    Never resets the counter; monotonic per-attempt accounting for double-buy detection.
    """
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE items SET checkout_attempts = checkout_attempts + 1 WHERE link=?",
            (link,),
        )


def get_item_order_state_sync(link: str) -> tuple[bool, str | None]:
    """Return (purchased as bool, order_id) for the cart-retry idempotency check (BUY-05).

    Returns (False, None) when the item row is missing (safe no-op for retry guard).
    """
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT purchased, order_id FROM items WHERE link=?",
            (link,),
        ).fetchone()
    if row is None:
        return False, None
    return bool(row[0]), row[1]


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


def get_place_order_marker_sync(link: str) -> str | None:
    """Return place_order_attempted_at for the link, or None if unset/missing (BF-02).

    A non-None marker means a place-order click was dispatched for this link but
    no confirmed order_id has been captured -- the retry guard's "possibly placed"
    signal (D-02/D-03). Returns None for a missing row (safe no-op for the guard).
    """
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT place_order_attempted_at FROM items WHERE link=?",
            (link,),
        ).fetchone()
    return row[0] if row else None


def mark_place_order_attempted_sync(link: str, attempted_at: str) -> None:
    """Set the place-order write-ahead marker immediately before the click (D-01/BF-02).

    Must be called via run_in_executor and awaited so the write durably commits
    before the click fires -- this is the crash-durability guarantee the marker
    exists for. Does not touch order_id/confirmed_at/checkout_attempts.
    """
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE items SET place_order_attempted_at=? WHERE link=?",
            (attempted_at, link),
        )


def clear_place_order_marker_sync(link: str) -> None:
    """Reset place_order_attempted_at to NULL after manual operator review (LOW-03).

    Recovery accessor: the only way to un-latch an item whose place-order marker
    was set by a genuine (non-suppressed) click with no confirmed order_id. No
    caller is wired up yet -- this is the reset primitive an operator-facing tool
    or manual invocation uses after confirming (out-of-band) whether the order
    went through. Mirrors clear_item_available_sync / clear_price_alert_armed_sync.
    """
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE items SET place_order_attempted_at=NULL WHERE link=?",
            (link,),
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
