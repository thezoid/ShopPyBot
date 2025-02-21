import os
import sqlite3
import pytest
from models import initialize_db, add_items, get_items, update_item_purchased, DB_PATH

@pytest.fixture(scope='module')
def setup_db():
    # Setup: Initialize the database and add some items
    initialize_db(delete=True)
    items = [
        ("Item 1", "https://example.com/item1", True, 1, False),
        ("Item 2", "https://example.com/item2", False, 2, False)
    ]
    add_items(items)
    yield
    # Teardown: Remove the database file
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

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