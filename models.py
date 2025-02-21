import sqlite3
import os

DB_PATH = os.path.join('data', 'shop_py_bot.db')

def initialize_db(delete=False):
    if delete and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            link TEXT NOT NULL UNIQUE,
            auto_buy BOOLEAN NOT NULL,
            quantity INTEGER NOT NULL,
            purchased BOOLEAN NOT NULL DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def add_items(items):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for item in items:
        cursor.execute('''
            SELECT COUNT(*) FROM items WHERE link = ?
        ''', (item[1],))
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO items (name, link, auto_buy, quantity, purchased)
                VALUES (?, ?, ?, ?, ?)
            ''', item)
    conn.commit()
    conn.close()

def update_item_purchased(link):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE items
        SET purchased = 1
        WHERE link = ?
    ''', (link,))
    conn.commit()
    conn.close()

def get_items():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT name, link, auto_buy, quantity, purchased
        FROM items
    ''')
    items = cursor.fetchall()
    conn.close()
    return items