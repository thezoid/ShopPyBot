"""Tests for Phase 16 Plan 01: price_history table, items price columns, _sync functions.

TDD RED phase: tests fail until Task 2 adds migration + models functions.
"""

from __future__ import annotations

import sqlite3

import pytest

import models


# ---------------------------------------------------------------------------
# Migration / schema tests
# ---------------------------------------------------------------------------


def test_price_history_table_created(tmp_data_dir):
    """initialize_db(delete=True) creates the price_history table with required columns."""
    models.initialize_db(delete=True)

    conn = sqlite3.connect(models.DB_PATH)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(price_history)").fetchall()}
    conn.close()

    assert "id" in cols
    assert "item_link" in cols
    assert "price_cents" in cols
    assert "currency" in cols
    assert "scraped_at" in cols


def test_items_price_columns_added(tmp_data_dir):
    """initialize_db(delete=True) adds four new price columns to the items table."""
    models.initialize_db(delete=True)

    conn = sqlite3.connect(models.DB_PATH)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(items)").fetchall()}
    conn.close()

    assert "target_price" in cols
    assert "price_drop_pct" in cols
    assert "price_alert_armed" in cols
    assert "price_last_notified" in cols


def test_migration_idempotent(tmp_data_dir):
    """initialize_db() called twice does not raise or duplicate any column."""
    models.initialize_db(delete=True)  # fresh DB
    models.initialize_db()             # second call must not raise

    conn = sqlite3.connect(models.DB_PATH)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(items)").fetchall()]
    conn.close()

    assert cols.count("price_alert_armed") == 1
    assert cols.count("target_price") == 1
    assert cols.count("price_drop_pct") == 1
    assert cols.count("price_last_notified") == 1


# ---------------------------------------------------------------------------
# append / read price_history
# ---------------------------------------------------------------------------


def test_append_and_get_price_history(tmp_data_dir):
    """append_price_history_sync inserts a row; get_price_history_sync returns it newest-first."""
    from models import (
        append_price_history_sync,
        get_price_history_sync,
        initialize_db,
    )

    initialize_db(delete=True)
    link = "https://example.com/item"
    append_price_history_sync(link, 4999, "2026-06-09T12:00:00+00:00")
    rows = get_price_history_sync(link)

    assert len(rows) == 1
    price_cents, currency, scraped_at = rows[0]
    assert price_cents == 4999
    assert currency == "USD"
    assert scraped_at == "2026-06-09T12:00:00+00:00"


def test_get_price_history_limit_and_order(tmp_data_dir):
    """T-03: get_price_history_sync respects LIMIT and returns rows newest-first (DESC).

    Inserts 3 rows with increasing scraped_at; asserts limit=2 returns exactly 2
    rows AND rows[0] is the newest entry.
    """
    from models import (
        append_price_history_sync,
        get_price_history_sync,
        initialize_db,
    )

    initialize_db(delete=True)
    link = "https://example.com/limit-test"

    # Insert oldest -> newest
    append_price_history_sync(link, 5000, "2026-06-09T10:00:00+00:00")  # oldest
    append_price_history_sync(link, 4800, "2026-06-09T11:00:00+00:00")  # middle
    append_price_history_sync(link, 4500, "2026-06-09T12:00:00+00:00")  # newest

    # limit=2 must return exactly 2 rows
    rows = get_price_history_sync(link, limit=2)
    assert len(rows) == 2, f"Expected 2 rows with limit=2, got {len(rows)}"

    # First row must be the newest (DESC order)
    assert rows[0][0] == 4500, f"Expected newest price 4500 first, got {rows[0][0]}"
    assert rows[0][2] == "2026-06-09T12:00:00+00:00"

    # Second row is the middle entry
    assert rows[1][0] == 4800, f"Expected middle price 4800 second, got {rows[1][0]}"

    # Confirm oldest row is excluded by the limit
    all_prices = {r[0] for r in get_price_history_sync(link, limit=10)}
    assert 5000 in all_prices, "Oldest row must be present when limit=10"


def test_get_last_price(tmp_data_dir):
    """get_last_price_sync returns the most recent price_cents or None when no history."""
    from models import (
        append_price_history_sync,
        get_last_price_sync,
        initialize_db,
    )

    initialize_db(delete=True)
    link = "https://example.com/item"

    # No history yet.
    assert get_last_price_sync(link) is None

    append_price_history_sync(link, 5000, "2026-06-09T11:00:00+00:00")
    append_price_history_sync(link, 4500, "2026-06-09T12:00:00+00:00")

    # Most recent is 4500.
    assert get_last_price_sync(link) == 4500


# ---------------------------------------------------------------------------
# Price-alert dedup state
# ---------------------------------------------------------------------------


def test_price_alert_state_roundtrip(tmp_data_dir):
    """get_price_alert_state_sync defaults (False, None); set/clear roundtrip correctly."""
    from models import (
        add_items_sync,
        clear_price_alert_armed_sync,
        get_price_alert_state_sync,
        initialize_db,
        set_price_alert_armed_sync,
    )

    initialize_db(delete=True)
    link = "https://example.com/widget"
    add_items_sync([("Widget", link, False, 1, 0)])

    # Default state.
    armed, ts = get_price_alert_state_sync(link)
    assert armed is False
    assert ts is None

    # Arm it.
    set_price_alert_armed_sync(link, "2026-06-09T12:00:00+00:00")
    armed, ts = get_price_alert_state_sync(link)
    assert armed is True
    assert ts == "2026-06-09T12:00:00+00:00"

    # Disarm.
    clear_price_alert_armed_sync(link)
    armed, ts = get_price_alert_state_sync(link)
    assert armed is False


def test_price_dedup_independent_from_stock_dedup(tmp_data_dir):
    """Price dedup columns do not touch stock dedup columns and vice versa."""
    from models import (
        add_items_sync,
        clear_item_available_sync,
        get_item_notification_state_sync,
        get_price_alert_state_sync,
        initialize_db,
        set_item_available_sync,
        set_price_alert_armed_sync,
    )

    initialize_db(delete=True)
    link = "https://example.com/widget"
    add_items_sync([("Widget", link, False, 1, 0)])

    # Arm price alert -- stock dedup columns must stay untouched.
    set_price_alert_armed_sync(link, "2026-06-09T12:00:00+00:00")
    stock_available, stock_notified = get_item_notification_state_sync(link)
    assert stock_available is False
    assert stock_notified is None

    # Arm stock alert -- price dedup columns must stay untouched.
    set_item_available_sync(link, "2026-06-09T13:00:00+00:00")
    price_armed, price_ts = get_price_alert_state_sync(link)
    assert price_armed is True
    assert price_ts == "2026-06-09T12:00:00+00:00"

    # Clear stock alert -- price columns must still be armed.
    clear_item_available_sync(link)
    price_armed, price_ts = get_price_alert_state_sync(link)
    assert price_armed is True


# ---------------------------------------------------------------------------
# Price config (target_price / price_drop_pct)
# ---------------------------------------------------------------------------


def test_update_item_price_config(tmp_data_dir):
    """update_item_price_config_sync writes target_price + price_drop_pct; get reads them back."""
    from models import (
        add_items_sync,
        get_item_price_config_sync,
        initialize_db,
        update_item_price_config_sync,
    )

    initialize_db(delete=True)
    link = "https://example.com/widget"
    add_items_sync([("Widget", link, False, 1, 0)])

    # Both NULL initially.
    row = get_item_price_config_sync(link)
    assert row is not None
    target, drop_pct = row
    assert target is None
    assert drop_pct is None

    # Write config.
    update_item_price_config_sync(link, 4999, 10.0)
    row = get_item_price_config_sync(link)
    assert row is not None
    target, drop_pct = row
    assert target == 4999
    assert drop_pct == 10.0
