import sqlite3

DB_NAME = "sanuki.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            name TEXT,
            username TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            guest_name TEXT,
            order_type TEXT,
            items TEXT,
            total INTEGER DEFAULT 0,
            status TEXT DEFAULT 'новый',
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def user_exists(telegram_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
    user = cur.fetchone()
    conn.close()
    return user

def add_user(telegram_id: int, name: str, username: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO users (telegram_id, name, username) VALUES (?, ?, ?)",
        (telegram_id, name, username)
    )
    conn.commit()
    conn.close()

def save_order(telegram_id: int, guest_name: str, order_type: str, items: list, total: int):
    import json
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO orders (telegram_id, guest_name, order_type, items, total) VALUES (?, ?, ?, ?, ?)",
        (telegram_id, guest_name, order_type, json.dumps(items, ensure_ascii=False), total)
    )
    order_id = cur.lastrowid
    conn.commit()
    conn.close()
    return order_id