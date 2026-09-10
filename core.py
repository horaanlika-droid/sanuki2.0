"""
Общее ядро SANUKI: база данных, статусы заказов, шина событий.

Используется ОДНОВРЕМЕННО ботом и веб-приложением, поэтому:
- один файл БД (sanuki.db),
- одинаковый набор статусов у обоих клиентов,
- события (шторка SSE /events) позволяют боту и вебу реагировать
  на изменение статуса мгновенно.
"""
import asyncio
import json
import os
import sqlite3
import threading
from datetime import datetime

DB_NAME = os.getenv("SANUKI_DB", "sanuki.db")

# ============================================================
# ЕДИНЫЕ СТАТУСЫ (видны одинаково в боте и на сайте)
# ============================================================
STATUSES = {
    "new":      {"ru": "Новый",     "bot": "🆕 Новый",            "web": "Новый",     "color": "#f2681f"},
    "accepted": {"ru": "Принят",    "bot": "✅ Принят",           "web": "Принят",    "color": "#3f9142"},
    "cooking":  {"ru": "Готовится", "bot": "🔪 Готовится",        "web": "Готовится", "color": "#f2681f"},
    "ready":    {"ru": "Готов",     "bot": "🍜 Готов",            "web": "Готов",     "color": "#2a7cb8"},
    "issued":   {"ru": "Выдан",     "bot": "🎉 Выдан",            "web": "Выдан",     "color": "#3f9142"},
    "cancelled":{"ru": "Отменён",   "bot": "❌ Отменён",          "web": "Отменён",   "color": "#d9534f"},
}
STATUS_ORDER = ["new", "accepted", "cooking", "ready", "issued"]
ACTIVE_STATUSES = ("new", "accepted", "cooking", "ready")

# Типы заказа
ORDER_TYPES = {
    "dine_in":  "В зале 🍽",
    "takeaway": "С собой 🥡",
    "delivery": "Доставка 🛵",
}

# ============================================================
# Шина событий (бот <-> веб)
# ============================================================
_EVENT_LOOP: asyncio.AbstractEventLoop | None = None
_listeners: list[asyncio.Queue] = []


def set_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    """FastAPI вызывает это на старте: события из потока бота
    (или синхронного кода) пробрасываются в цикл веба."""
    global _EVENT_LOOP
    _EVENT_LOOP = loop


def publish(event: dict) -> None:
    """Безопасно опубликовать событие из любого места."""
    data = dict(event)
    data.setdefault("ts", datetime.now().isoformat(timespec="seconds"))
    if _EVENT_LOOP and not _EVENT_LOOP.is_closed():
        try:
            asyncio.run_coroutine_threadsafe(_emit(data), _EVENT_LOOP)
        except RuntimeError:
            pass


async def _emit(data: dict) -> None:
    for q in list(_listeners):
        try:
            q.put_nowait(data)
        except Exception:
            pass


async def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=64)
    _listeners.append(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    if q in _listeners:
        _listeners.remove(q)


# ============================================================
# База данных
# ============================================================
_local = threading.local()


def get_connection() -> sqlite3.Connection:
    """Отдельное соединение на поток (бот и веб живут в разных потоках)."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(DB_NAME, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        _local.conn = conn
    return conn


def init_db() -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            name TEXT,
            username TEXT,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("PRAGMA table_info(users)")
    cols = {r[1] for r in cur.fetchall()}
    if "phone" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN phone TEXT")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            public_id TEXT,
            telegram_id INTEGER,
            guest_name TEXT,
            phone TEXT,
            order_type TEXT,
            items TEXT,
            total INTEGER DEFAULT 0,
            status TEXT DEFAULT 'new',
            comment TEXT,
            source TEXT DEFAULT 'bot',
            pay_method TEXT DEFAULT 'cash',
            payment_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("PRAGMA table_info(orders)")
    ocols = {r[1] for r in cur.fetchall()}
    migrations = {
        "public_id":  "ALTER TABLE orders ADD COLUMN public_id TEXT",
        "phone":      "ALTER TABLE orders ADD COLUMN phone TEXT",
        "source":     "ALTER TABLE orders ADD COLUMN source TEXT DEFAULT 'bot'",
        "pay_method": "ALTER TABLE orders ADD COLUMN pay_method TEXT DEFAULT 'cash'",
        "payment_id": "ALTER TABLE orders ADD COLUMN payment_id TEXT",
        "updated_at": "ALTER TABLE orders ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    }
    for col, ddl in migrations.items():
        if col not in ocols:
            cur.execute(ddl)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS order_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_orders_tg   ON orders(telegram_id)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(created_at)
    """)
    conn.commit()


def _public_id(order_id: int) -> str:
    return f"{order_id:04d}"


# ------------------------- пользователи -------------------------
def user_exists(telegram_id: int):
    cur = get_connection().cursor()
    cur.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
    return cur.fetchone()


def add_user(telegram_id: int, name: str, username: str = "", phone: str | None = None):
    conn = get_connection()
    conn.execute(
        """INSERT INTO users (telegram_id, name, username, phone)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(telegram_id) DO UPDATE SET
             name=excluded.name, username=CASE WHEN excluded.username!='' THEN excluded.username ELSE users.username END,
             phone=COALESCE(excluded.phone, users.phone)""",
        (telegram_id, name, username or "", phone),
    )
    conn.commit()


def update_phone(telegram_id: int, phone: str) -> None:
    conn = get_connection()
    conn.execute("UPDATE users SET phone=? WHERE telegram_id=?", (phone, telegram_id))
    conn.commit()


# ------------------------- заказы -------------------------
def save_order(telegram_id: int | None, guest_name: str, order_type: str,
               items: list, total: int, source: str = "bot",
               phone: str | None = None, comment: str | None = None,
               pay_method: str = "cash") -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO orders (telegram_id, guest_name, phone, order_type, items,
                               total, status, comment, source, pay_method)
           VALUES (?, ?, ?, ?, ?, ?, 'new', ?, ?, ?)""",
        (telegram_id, guest_name, phone, order_type,
         json.dumps(items, ensure_ascii=False), total, comment, source, pay_method),
    )
    order_id = cur.lastrowid
    cur.execute("UPDATE orders SET public_id=? WHERE id=?", (_public_id(order_id), order_id))
    cur.execute("INSERT INTO order_history (order_id, status) VALUES (?, 'new')", (order_id,))
    conn.commit()
    publish({
        "type": "order_new",
        "order_id": order_id,
        "public_id": _public_id(order_id),
        "total": total,
        "source": source,
    })
    return order_id


def get_order(order_id: int):
    cur = get_connection().cursor()
    cur.execute("SELECT * FROM orders WHERE id=?", (order_id,))
    return cur.fetchone()


def get_order_by_public(public_id: str):
    cur = get_connection().cursor()
    cur.execute("SELECT * FROM orders WHERE public_id=?", (str(public_id),))
    return cur.fetchone()


def user_orders(telegram_id: int, limit: int = 20):
    cur = get_connection().cursor()
    cur.execute(
        "SELECT * FROM orders WHERE telegram_id=? ORDER BY id DESC LIMIT ?",
        (telegram_id, limit),
    )
    return cur.fetchall()


def update_status(order_id: int, status: str) -> None:
    """Единственная точка смены статуса: пишем БД + историю + событие."""
    if status not in STATUSES:
        raise ValueError(f"Неизвестный статус: {status}")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE orders SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (status, order_id),
    )
    cur.execute("INSERT INTO order_history (order_id, status) VALUES (?, ?)", (order_id, status))
    conn.commit()
    order = get_order(order_id)
    publish({
        "type": "order_status",
        "order_id": order_id,
        "public_id": order["public_id"],
        "status": status,
        "telegram_id": order["telegram_id"],
    })


def order_history(order_id: int):
    cur = get_connection().cursor()
    cur.execute(
        "SELECT status, created_at FROM order_history WHERE order_id=? ORDER BY id",
        (order_id,),
    )
    return cur.fetchall()


def all_orders(statuses: list[str] | None = None, limit: int = 50):
    q = "SELECT * FROM orders"
    args: list = []
    if statuses:
        q += " WHERE status IN (%s)" % ",".join("?" * len(statuses))
        args.extend(statuses)
    q += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    cur = get_connection().cursor()
    cur.execute(q, args)
    return cur.fetchall()


# ------------------------- админ-статистика -------------------------
def stats():
    cur = get_connection().cursor()
    out = {"today": 0, "today_sum": 0, "active": 0, "users": 0}
    cur.execute("SELECT COUNT(*) c, COALESCE(SUM(total),0) s FROM orders WHERE DATE(created_at)=DATE('now','localtime')")
    row = cur.fetchone()
    out["today"], out["today_sum"] = row["c"], row["s"]
    cur.execute("SELECT COUNT(*) c FROM orders WHERE status IN ('new','accepted','cooking','ready')")
    out["active"] = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) c FROM users")
    out["users"] = cur.fetchone()["c"]
    return out


def items_of(order_row) -> list:
    try:
        return json.loads(order_row["items"] or "[]")
    except Exception:
        return []


def format_items_text(items: list) -> str:
    """Человекочитаемый состав заказа — одинаков для бота и веба."""
    lines = []
    for it in items:
        title = it.get("title") or it.get("name") or ""
        if it.get("kind") == "udon":
            parts = [f"🍜 Удон: {it.get('base','')} + {it.get('protein','')}"]
            top = it.get("topping")
            if top:
                parts.append(f"   🌿 топпинг: {top}")
            extras = it.get("extras") or []
            if extras:
                parts.append("   ➕ " + ", ".join(extras))
            price = it.get("price", 0)
            lines.append("\n".join(parts) + (f" — {price} ₽" if price else ""))
        else:
            qty = it.get("qty", 1)
            lines.append(f"• {title} × {qty} — {it.get('price',0) * qty} ₽")
    return "\n".join(lines) or "—"


# ------------------------- уведомления клиенту -------------------------
_client_notify = None  # колбэк: async fn(telegram_id, text)
_bot_loop: asyncio.AbstractEventLoop | None = None


def set_client_notify(fn) -> None:
    global _client_notify
    _client_notify = fn


def set_bot_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Цикл бота: из веба уведомления уходят в него без cross-loop ошибок."""
    global _bot_loop
    _bot_loop = loop


async def notify_user(telegram_id: int | None, text: str) -> None:
    """Доставка сообщения пользователю через бота (если он известен).

    Безопасно вызывается как из цикла бота, так и из цикла веба."""
    if not telegram_id or not _client_notify:
        return
    coro = _client_notify(int(telegram_id), text)
    try:
        current = asyncio.get_running_loop()
    except RuntimeError:
        current = None
    try:
        if _bot_loop is not None and current is not _bot_loop:
            await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(coro, _bot_loop))
        else:
            await coro
    except Exception:
        pass


def status_message(order_id: int, status: str) -> str:
    """Единый текст уведомления о смене статуса — для бота и веба."""
    order = get_order(order_id)
    pid = order["public_id"] if order else f"{order_id:04d}"
    if status == "accepted":
        return f"🌸 <b>Заказ #{pid}</b>\n\n✅ Заказ <b>принят</b>! Начинаем готовить! 🔪"
    if status == "cooking":
        return f"🌸 <b>Заказ #{pid}</b>\n\n🔪 Заказ <b>готовится</b>! Ожидайте 10–15 минут ⏰"
    if status == "ready":
        return ("🌸 <b>Заказ #" + pid + "</b>\n\n🍜 <b>Заказ готов!</b>\n\n"
                "🍽 Если вы в зале — скоро принесут.\n"
                "🥡 Если с собой — можно забирать.\n"
                "🛵 Если доставка — уже в пути!")
    if status == "issued":
        return f"🌸 <b>Заказ #{pid}</b>\n\n🎉 Заказ <b>выдан</b>. Приходите ещё — мы вас ждём! 🙏"
    if status == "cancelled":
        return (f"🌸 <b>Заказ #{pid}</b>\n\n❌ Заказ <b>отменён</b>.\n"
                "Приносим извинения. Если это ошибка — позвольте сотруднику помочь.")
    return f"🌸 Заказ #{pid}: {STATUSES[status]['ru']}"


# ============================================================
# Меню (общий источник menu.json)
# ============================================================
_MENU_CACHE: dict | None = None


def load_menu() -> dict:
    global _MENU_CACHE
    if _MENU_CACHE is None:
        with open("menu.json", encoding="utf-8") as f:
            _MENU_CACHE = json.load(f)
    return _MENU_CACHE


def category(name: str) -> dict:
    for cat in load_menu()["categories"]:
        if cat["name"] == name:
            return cat
    return {}


def udon_bases() -> list:    return category("UDON").get("bases", [])
def udon_proteins() -> list: return category("UDON").get("proteins", [])
def udon_toppings() -> list: return category("UDON").get("toppings", [])


def category_items(name: str) -> list:
    return category(name).get("items", [])


def settings() -> dict:
    try:
        with open("setting.json", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}
