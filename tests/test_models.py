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
