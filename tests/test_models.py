import os
import sqlite3
import pytest
from models import initialize_db, add_items, get_items, update_item_purchased


@pytest.fixture
def setup_db(tmp_data_dir):
    import models
    initialize_db(delete=True)
    items = [
        ("Item 1", "https://example.com/item1", True, 1, False),
        ("Item 2", "https://example.com/item2", False, 2, False),
    ]
    add_items(items)
    yield
    if os.path.exists(models.DB_PATH):
        os.remove(models.DB_PATH)


def test_add_items(setup_db):
    items = get_items()
    assert len(items) == 2
    assert items[0][1] == "https://example.com/item1"
    assert items[1][1] == "https://example.com/item2"


def test_update_item_purchased(setup_db):
    update_item_purchased("https://example.com/item1")
    items = get_items()
    assert items[0][4] == 1  # purchased should be True
    assert items[1][4] == 0  # purchased should be False


# ---------------------------------------------------------------------------
# Phase 19: confirmation columns + update_item_confirmed_sync (BUY-04)
# ---------------------------------------------------------------------------


def test_confirmation_columns_added(tmp_data_dir):
    """initialize_db(delete=True) adds order_id, confirmed_at, checkout_attempts columns."""
    import models
    models.initialize_db(delete=True)

    conn = sqlite3.connect(models.DB_PATH)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(items)").fetchall()}
    conn.close()

    assert "order_id" in cols
    assert "confirmed_at" in cols
    assert "checkout_attempts" in cols


def test_migration_on_legacy_schema(tmp_data_dir):
    """initialize_db() on a DB with only v3.0 columns adds all 3 confirmation columns."""
    import models
    conn = sqlite3.connect(models.DB_PATH)
    conn.execute(
        "CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT NOT NULL, "
        "link TEXT NOT NULL UNIQUE, auto_buy BOOLEAN NOT NULL, "
        "quantity INTEGER NOT NULL, purchased BOOLEAN NOT NULL DEFAULT 0)"
    )
    conn.commit()
    conn.close()

    models.initialize_db()

    conn = sqlite3.connect(models.DB_PATH)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(items)").fetchall()}
    conn.close()

    assert "order_id" in cols
    assert "confirmed_at" in cols
    assert "checkout_attempts" in cols


def test_migration_idempotent_confirmation(tmp_data_dir):
    """Two initialize_db() calls do not duplicate confirmation columns."""
    import models
    models.initialize_db(delete=True)
    models.initialize_db()

    conn = sqlite3.connect(models.DB_PATH)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(items)").fetchall()]
    conn.close()

    assert cols.count("order_id") == 1
    assert cols.count("confirmed_at") == 1
    assert cols.count("checkout_attempts") == 1


def test_update_item_confirmed(tmp_data_dir):
    """update_item_confirmed_sync sets purchased=1, order_id, confirmed_at together."""
    import models
    models.initialize_db(delete=True)
    models.add_items_sync([("Widget", "https://ex.com/item", True, 1, False)])
    models.update_item_confirmed_sync(
        "https://ex.com/item", "123-456", "2026-06-11T00:00:00+00:00"
    )

    conn = sqlite3.connect(models.DB_PATH)
    row = conn.execute(
        "SELECT purchased, order_id, confirmed_at FROM items WHERE link=?",
        ("https://ex.com/item",),
    ).fetchone()
    conn.close()

    assert row[0] == 1
    assert row[1] == "123-456"
    assert row[2] == "2026-06-11T00:00:00+00:00"


# ---------------------------------------------------------------------------
# Phase 21: increment_checkout_attempts_sync + get_item_order_state_sync (BUY-05)
# ---------------------------------------------------------------------------


def test_increment_checkout_attempts_by_one(tmp_data_dir):
    """increment_checkout_attempts_sync increments by exactly 1 per call, never resets."""
    import models
    models.initialize_db(delete=True)
    models.add_items_sync([("Widget", "https://ex.com/buy1", True, 1, False)])

    # First increment: 0 -> 1
    models.increment_checkout_attempts_sync("https://ex.com/buy1")
    conn = sqlite3.connect(models.DB_PATH)
    row = conn.execute(
        "SELECT checkout_attempts FROM items WHERE link=?",
        ("https://ex.com/buy1",),
    ).fetchone()
    conn.close()
    assert row[0] == 1

    # Second increment: 1 -> 2
    models.increment_checkout_attempts_sync("https://ex.com/buy1")
    conn = sqlite3.connect(models.DB_PATH)
    row = conn.execute(
        "SELECT checkout_attempts FROM items WHERE link=?",
        ("https://ex.com/buy1",),
    ).fetchone()
    conn.close()
    assert row[0] == 2


def test_get_item_order_state_fresh(tmp_data_dir):
    """get_item_order_state_sync returns (False, None) for a freshly added item."""
    import models
    models.initialize_db(delete=True)
    models.add_items_sync([("Widget", "https://ex.com/buy2", True, 1, False)])

    purchased, order_id = models.get_item_order_state_sync("https://ex.com/buy2")

    assert purchased is False
    assert order_id is None


def test_get_item_order_state_after_confirm(tmp_data_dir):
    """get_item_order_state_sync returns (True, order_id) after update_item_confirmed_sync."""
    import models
    models.initialize_db(delete=True)
    models.add_items_sync([("Widget", "https://ex.com/buy3", True, 1, False)])
    models.update_item_confirmed_sync(
        "https://ex.com/buy3", "ORDER123", "2026-06-11T00:00:00+00:00"
    )

    purchased, order_id = models.get_item_order_state_sync("https://ex.com/buy3")

    assert purchased is True
    assert order_id == "ORDER123"


def test_get_item_order_state_missing_row(tmp_data_dir):
    """get_item_order_state_sync returns (False, None) for a missing link without raising."""
    import models
    models.initialize_db(delete=True)

    purchased, order_id = models.get_item_order_state_sync("https://no-such-item")

    assert purchased is False
    assert order_id is None


# ---------------------------------------------------------------------------
# Phase 26: get_confirmed_orders_sync (OBS-08)
# ---------------------------------------------------------------------------


def test_get_confirmed_orders_sync_empty(tmp_data_dir):
    """get_confirmed_orders_sync returns [] when no items have purchased=1."""
    import models
    from models import get_confirmed_orders_sync
    models.initialize_db(delete=True)

    result = get_confirmed_orders_sync()

    assert result == []


def test_get_confirmed_orders_sync_returns_confirmed(tmp_data_dir):
    """get_confirmed_orders_sync returns one tuple with 4 fields after confirmation."""
    import models
    from models import get_confirmed_orders_sync
    models.initialize_db(delete=True)
    models.add_items_sync([("Widget B", "https://ex.com/wb", True, 1, False)])
    models.update_item_confirmed_sync(
        "https://ex.com/wb", "ORD-7", "2026-01-01T00:00:00+00:00"
    )

    result = get_confirmed_orders_sync()

    assert len(result) == 1
    row = result[0]
    assert len(row) == 4
    assert row[1] == "ORD-7"
    assert row[2] == "2026-01-01T00:00:00+00:00"


def test_get_confirmed_orders_sync_excludes_unpurchased(tmp_data_dir):
    """get_confirmed_orders_sync does not include items where purchased=0."""
    import models
    from models import get_confirmed_orders_sync
    models.initialize_db(delete=True)
    models.add_items_sync([("Widget C", "https://ex.com/wc", True, 1, False)])

    result = get_confirmed_orders_sync()

    assert result == []
