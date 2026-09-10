"""Общая база данных SQLite.

Одна база на бота и веб-приложение — поэтому заказы и их статусы
всегда одинаковы в Telegram и в браузере.
"""

import asyncio
import json
import os
import random
import string
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Iterable, Optional

import aiosqlite

from config import DB_PATH

_lock = asyncio.Lock()
_conn: Optional[aiosqlite.Connection] = None


def _ensure_dir() -> None:
    path = Path(DB_PATH)
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)


async def get_connection() -> aiosqlite.Connection:
    global _conn
    if _conn is None:
        _ensure_dir()
        _conn = await aiosqlite.connect(DB_PATH)
        _conn.row_factory = aiosqlite.Row
        await _conn.execute("PRAGMA journal_mode=WAL")
        await _conn.execute("PRAGMA foreign_keys=ON")
    return _conn


async def close() -> None:
    global _conn
    if _conn is not None:
        await _conn.close()
        _conn = None


@asynccontextmanager
async def transaction():
    conn = await get_connection()
    async with _lock:
        try:
            yield conn
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise


def rows_to_dicts(rows: Iterable[aiosqlite.Row]) -> list[dict]:
    return [dict(r) for r in rows]


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def loads(value: Any, default: Any = None) -> Any:
    if value is None or value == "":
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


CODE_ALPHABET = string.ascii_uppercase + string.digits


def generate_code(length: int = 5) -> str:
    return "".join(random.choice(CODE_ALPHABET) for _ in range(length))


# --------------------------------------------------------------------------
# Схема
# --------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id   INTEGER UNIQUE,
    name          TEXT,
    username      TEXT,
    phone         TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    token         TEXT PRIMARY KEY,
    telegram_id   INTEGER,
    name          TEXT,
    username      TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at    TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    code            TEXT UNIQUE,
    telegram_id     INTEGER,
    guest_name      TEXT,
    phone           TEXT,
    username        TEXT,
    source          TEXT DEFAULT 'web',      -- web | bot
    order_type      TEXT DEFAULT 'dine_in',  -- dine_in | takeaway | delivery
    table_number    TEXT,
    address         TEXT,
    comment         TEXT,
    items           TEXT,                    -- JSON
    total           INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'new',
    payment_method  TEXT DEFAULT 'cash',     -- cash | card | yoomoney
    payment_status  TEXT DEFAULT 'unpaid',   -- unpaid | pending | paid | failed
    payment_id      TEXT,
    payment_url     TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS order_status_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id     INTEGER NOT NULL,
    status       TEXT NOT NULL,
    actor        TEXT DEFAULT 'system',
    comment      TEXT,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stop_list (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT UNIQUE,
    reason    TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staff_calls (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id  INTEGER,
    guest_name   TEXT,
    table_number TEXT,
    kind         TEXT,
    status       TEXT DEFAULT 'new',
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_orders_telegram ON orders(telegram_id);
CREATE INDEX IF NOT EXISTS idx_orders_status   ON orders(status);
CREATE INDEX IF NOT EXISTS idx_history_order   ON order_status_history(order_id);
"""


async def init_db() -> None:
    conn = await get_connection()
    async with _lock:
        await conn.executescript(SCHEMA)
        await conn.commit()
    await _migrate(conn)


async def _migrate(conn: aiosqlite.Connection) -> None:
    """Мягкая миграция старых баз (из предыдущей версии бота)."""
    async with _lock:
        cur = await conn.execute("PRAGMA table_info(orders)")
        cols = {row["name"] for row in await cur.fetchall()}
        if cols and "code" not in cols:
            await conn.execute("ALTER TABLE orders ADD COLUMN code TEXT")
        if cols and "source" not in cols:
            await conn.execute("ALTER TABLE orders ADD COLUMN source TEXT DEFAULT 'bot'")
        if cols and "payment_method" not in cols:
            await conn.execute("ALTER TABLE orders ADD COLUMN payment_method TEXT DEFAULT 'cash'")
        if cols and "payment_status" not in cols:
            await conn.execute("ALTER TABLE orders ADD COLUMN payment_status TEXT DEFAULT 'unpaid'")
        if cols and "table_number" not in cols:
            await conn.execute("ALTER TABLE orders ADD COLUMN table_number TEXT")
        if cols and "address" not in cols:
            await conn.execute("ALTER TABLE orders ADD COLUMN address TEXT")
        await conn.commit()

        cur = await conn.execute("SELECT id, code FROM orders WHERE code IS NULL OR code=''")
        rows = await cur.fetchall()
        for row in rows:
            await conn.execute("UPDATE orders SET code=? WHERE id=?", (generate_code(), row["id"]))
        await conn.commit()


# --------------------------------------------------------------------------
# Пользователи
# --------------------------------------------------------------------------
async def get_user(telegram_id: int) -> Optional[dict]:
    conn = await get_connection()
    async with _lock:
        cur = await conn.execute("SELECT * FROM users WHERE telegram_id=?", (int(telegram_id),))
        row = await cur.fetchone()
    return dict(row) if row else None


async def upsert_user(telegram_id: int, name: str = "", username: str = "", phone: str = "") -> dict:
    conn = await get_connection()
    async with _lock:
        await conn.execute(
            """
            INSERT INTO users (telegram_id, name, username, phone)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                name     = COALESCE(NULLIF(excluded.name, ''), users.name),
                username = COALESCE(NULLIF(excluded.username, ''), users.username),
                phone    = COALESCE(NULLIF(excluded.phone, ''), users.phone)
            """,
            (int(telegram_id), name or "", username or "", phone or ""),
        )
        await conn.commit()
        cur = await conn.execute("SELECT * FROM users WHERE telegram_id=?", (int(telegram_id),))
        row = await cur.fetchone()
    return dict(row) if row else {}


# --------------------------------------------------------------------------
# Сессии веб-приложения
# --------------------------------------------------------------------------
async def create_session(telegram_id: int, name: str, username: str, token: str,
                         expires_at: str) -> None:
    conn = await get_connection()
    async with _lock:
        await conn.execute(
            "INSERT OR REPLACE INTO sessions (token, telegram_id, name, username, expires_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (token, int(telegram_id), name, username, expires_at),
        )
        await conn.commit()


async def get_session(token: str) -> Optional[dict]:
    if not token:
        return None
    conn = await get_connection()
    async with _lock:
        cur = await conn.execute(
            "SELECT * FROM sessions WHERE token=? AND (expires_at IS NULL OR expires_at > datetime('now'))",
            (token,),
        )
        row = await cur.fetchone()
    return dict(row) if row else None


async def drop_session(token: str) -> None:
    conn = await get_connection()
    async with _lock:
        await conn.execute("DELETE FROM sessions WHERE token=?", (token,))
        await conn.commit()


# --------------------------------------------------------------------------
# Стоп-лист
# --------------------------------------------------------------------------
async def get_stop_list() -> list[dict]:
    conn = await get_connection()
    async with _lock:
        cur = await conn.execute("SELECT * FROM stop_list ORDER BY created_at DESC")
        rows = await cur.fetchall()
    return rows_to_dicts(rows)


async def add_stop_item(name: str, reason: str = "") -> None:
    conn = await get_connection()
    async with _lock:
        await conn.execute(
            "INSERT OR REPLACE INTO stop_list (name, reason) VALUES (?, ?)", (name, reason)
        )
        await conn.commit()


async def remove_stop_item(name: str) -> None:
    conn = await get_connection()
    async with _lock:
        await conn.execute("DELETE FROM stop_list WHERE name=?", (name,))
        await conn.commit()


# --------------------------------------------------------------------------
# Вызовы сотрудника
# --------------------------------------------------------------------------
async def add_staff_call(telegram_id, guest_name: str, table_number: str, kind: str) -> int:
    conn = await get_connection()
    async with _lock:
        cur = await conn.execute(
            "INSERT INTO staff_calls (telegram_id, guest_name, table_number, kind)"
            " VALUES (?, ?, ?, ?)",
            (telegram_id, guest_name, table_number or "", kind or "help"),
        )
        await conn.commit()
        return cur.lastrowid


async def reset_demo_data() -> None:
    """Полностью очистить базу (используется только в демо-режиме)."""
    conn = await get_connection()
    async with _lock:
        await conn.executescript(
            "DELETE FROM orders; DELETE FROM order_status_history;"
            " DELETE FROM staff_calls; DELETE FROM sessions;"
        )
        await conn.commit()
