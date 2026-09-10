"""Доменная логика заказов.

Этим слоем пользуются и Telegram-бот, и веб-приложение: заказ создаётся
одинаково, статусы меняются по одним и тем же правилам, а уведомления
уходят подписчикам (боту) через core.notify.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import db
from core import menu as menu_core
from core import notify
from core import statuses as st

log = logging.getLogger("sanuki.orders")


# --------------------------------------------------------------------------
# Создание
# --------------------------------------------------------------------------
async def create_order(
    telegram_id: int | None,
    guest_name: str,
    items: list[dict],
    order_type: str = "dine_in",
    phone: str = "",
    address: str = "",
    comment: str = "",
    table_number: str = "",
    payment_method: str = "cash",
    source: str = "web",
    username: str = "",
) -> dict:
    if not items:
        raise ValueError("Пустой заказ")

    clean_items = [_normalize_item(item) for item in items]
    clean_items = [item for item in clean_items if item]
    if not clean_items:
        raise ValueError("В заказе нет корректных позиций")

    total = menu_core.items_total(clean_items)
    conn = await db.get_connection()

    code = db.generate_code()
    async with db.transaction() as conn:
        cur = await conn.execute(
            """
            INSERT INTO orders (code, telegram_id, guest_name, phone, username, source,
                                order_type, table_number, address, comment, items, total,
                                status, payment_method, payment_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, 'unpaid')
            """,
            (
                code,
                int(telegram_id) if telegram_id else None,
                (guest_name or "").strip() or "Гость SANUKI",
                phone or "",
                username or "",
                source,
                order_type,
                table_number or "",
                address or "",
                comment or "",
                db.dumps(clean_items),
                total,
                payment_method or "cash",
            ),
        )
        order_id = cur.lastrowid
        await conn.execute(
            "INSERT INTO order_status_history (order_id, status, actor, comment)"
            " VALUES (?, 'new', ?, ?)",
            (order_id, source, "Заказ создан"),
        )

    order = await get_order(order_id)
    if telegram_id:
        await db.upsert_user(telegram_id, name=guest_name, username=username, phone=phone)

    await notify.emit(
        "order_created",
        {"order": order, "source": source, "telegram_id": telegram_id},
    )
    return order


def _normalize_item(raw: dict) -> Optional[dict]:
    """Собираем позицию заново по меню, чтобы клиент не мог подменить цену."""
    if not isinstance(raw, dict):
        return None

    kind = raw.get("kind", "item")
    qty = max(1, min(50, int(raw.get("qty", 1) or 1)))

    if kind == "udon":
        base = (raw.get("base") or "").strip()
        protein = (raw.get("protein") or "").strip()
        if not base or not protein:
            return None
        extras = [str(e.get("name", e)).strip() for e in (raw.get("extras") or []) if e]
        item = menu_core.build_udon(
            base=base,
            protein=protein,
            topping=(raw.get("topping") or "").strip(),
            extras=[e for e in extras if e],
        )
        item["qty"] = qty
        return item

    name = (raw.get("name") or raw.get("title") or "").strip()
    item = menu_core.build_simple_item(name, qty=qty)
    return item


# --------------------------------------------------------------------------
# Чтение
# --------------------------------------------------------------------------
async def get_order(order_id: int) -> Optional[dict]:
    conn = await db.get_connection()
    cur = await conn.execute("SELECT * FROM orders WHERE id=?", (int(order_id),))
    row = await cur.fetchone()
    return await _decorate(dict(row)) if row else None


async def get_order_by_code(code: str) -> Optional[dict]:
    conn = await db.get_connection()
    cur = await conn.execute(
        "SELECT * FROM orders WHERE UPPER(code)=UPPER(?) ORDER BY id DESC LIMIT 1", (code,)
    )
    row = await cur.fetchone()
    return await _decorate(dict(row)) if row else None


async def get_history(order_id: int) -> list[dict]:
    conn = await db.get_connection()
    cur = await conn.execute(
        "SELECT * FROM order_status_history WHERE order_id=? ORDER BY id ASC", (int(order_id),)
    )
    rows = await cur.fetchall()
    history = [dict(r) for r in rows]
    for entry in history:
        entry["status_title"] = st.status_title(entry["status"])
        entry["status_emoji"] = st.status_emoji(entry["status"])
    return history


async def list_orders(
    telegram_id: int | None = None,
    status: str | None = None,
    active_only: bool = False,
    limit: int = 50,
) -> list[dict]:
    conn = await db.get_connection()
    sql = "SELECT * FROM orders WHERE 1=1"
    params: list[Any] = []
    if telegram_id:
        sql += " AND telegram_id=?"
        params.append(int(telegram_id))
    if status:
        sql += " AND status=?"
        params.append(status)
    if active_only:
        placeholders = ",".join("?" * len(st.ACTIVE_STATUSES))
        sql += f" AND status IN ({placeholders})"
        params.extend(st.ACTIVE_STATUSES)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(int(limit))

    cur = await conn.execute(sql, params)
    rows = await cur.fetchall()
    return [await _decorate(dict(r)) for r in rows]


async def _decorate(order: dict) -> dict:
    order = dict(order)
    order["items"] = db.loads(order.get("items"), [])
    order["status_title"] = st.status_title(order["status"])
    order["status_emoji"] = st.status_emoji(order["status"])
    order["status_description"] = st.status_description(order["status"])
    order["status_label"] = st.status_label(order["status"])
    order["order_type_title"] = menu_core.ORDER_TYPES.get(
        order.get("order_type"), order.get("order_type") or ""
    )
    order["can_cancel"] = order["status"] in ("new", "accepted")
    order["next_statuses"] = st.next_statuses(order["status"], order.get("order_type") or "")
    order["items_text"] = menu_core.describe_items(order["items"])
    order["final"] = order["status"] in st.FINAL_STATUSES
    return order


# --------------------------------------------------------------------------
# Статусы
# --------------------------------------------------------------------------
async def set_status(
    order_id: int,
    status: str,
    actor: str = "system",
    comment: str = "",
    strict: bool = False,
) -> dict:
    if status not in st.STATUSES:
        raise ValueError(f"Неизвестный статус: {status}")

    order = await get_order(order_id)
    if not order:
        raise ValueError(f"Заказ #{order_id} не найден")

    if strict and not st.can_transit(order["status"], status):
        raise ValueError(
            f"Нельзя перевести заказ из «{st.status_title(order['status'])}» "
            f"в «{st.status_title(status)}»"
        )

    previous = order["status"]
    conn = await db.get_connection()
    async with db.transaction() as conn:
        await conn.execute(
            "UPDATE orders SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (status, int(order_id)),
        )
        await conn.execute(
            "INSERT INTO order_status_history (order_id, status, actor, comment)"
            " VALUES (?, ?, ?, ?)",
            (int(order_id), status, actor, comment or ""),
        )

    order = await get_order(order_id)
    await notify.emit(
        "order_status_changed",
        {
            "order": order,
            "previous_status": previous,
            "status": status,
            "actor": actor,
            "comment": comment,
        },
    )
    return order


# --------------------------------------------------------------------------
# Оплата
# --------------------------------------------------------------------------
async def set_payment(
    order_id: int,
    payment_status: str,
    payment_id: str = "",
    payment_url: str = "",
) -> dict:
    conn = await db.get_connection()
    async with db.transaction() as conn:
        await conn.execute(
            "UPDATE orders SET payment_status=?, payment_id=?, payment_url=?,"
            " updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (payment_status, payment_id, payment_url, int(order_id)),
        )
    order = await get_order(order_id)
    await notify.emit(
        "payment_changed",
        {"order": order, "payment_status": payment_status, "payment_id": payment_id},
    )
    return order


# --------------------------------------------------------------------------
# Вызов сотрудника
# --------------------------------------------------------------------------
async def call_staff(telegram_id, guest_name: str, table_number: str, kind: str) -> dict:
    call_id = await db.add_staff_call(telegram_id, guest_name, table_number, kind)
    payload = {
        "id": call_id,
        "telegram_id": telegram_id,
        "guest_name": guest_name,
        "table_number": table_number,
        "kind": kind,
        "kind_title": {"help": "🆘 Нужна помощь", "bill": "🧾 Счёт"}.get(kind, kind),
    }
    await notify.emit("staff_call", payload)
    return payload


# --------------------------------------------------------------------------
# Статистика для админки
# --------------------------------------------------------------------------
async def stats() -> dict:
    conn = await db.get_connection()

    cur = await conn.execute("SELECT COUNT(*) AS c FROM orders")
    total_orders = (await cur.fetchone())["c"]

    cur = await conn.execute(
        "SELECT COUNT(*) AS c, COALESCE(SUM(total),0) AS s FROM orders"
        " WHERE status NOT IN ('cancelled')"
    )
    row = await cur.fetchone()
    paid_orders = row["c"]
    revenue = row["s"]

    by_status: dict[str, int] = {code: 0 for code in st.STATUSES}
    cur = await conn.execute("SELECT status, COUNT(*) AS c FROM orders GROUP BY status")
    for row in await cur.fetchall():
        by_status[row["status"]] = row["c"]

    cur = await conn.execute("SELECT COUNT(*) AS c FROM orders WHERE status='cancelled'")
    cancelled = (await cur.fetchone())["c"]

    cur = await conn.execute(
        "SELECT COALESCE(AVG(total),0) AS avg FROM orders WHERE status NOT IN ('cancelled')"
    )
    avg_total = round((await cur.fetchone())["avg"] or 0)

    popular: dict[str, int] = {}
    cur = await conn.execute("SELECT items FROM orders")
    for row in await cur.fetchall():
        for item in db.loads(row["items"], []):
            name = item.get("base", "") or item.get("name", "")
            if item.get("kind") == "udon":
                name = f"Удон: {item.get('protein', '')}"
            if not name:
                continue
            popular[name] = popular.get(name, 0) + int(item.get("qty", 1) or 1)

    top_items = sorted(popular.items(), key=lambda kv: kv[1], reverse=True)[:8]

    return {
        "total_orders": total_orders,
        "paid_orders": paid_orders,
        "revenue": revenue,
        "cancelled": cancelled,
        "avg_total": avg_total,
        "by_status": [
            {
                "code": code,
                "title": st.status_title(code),
                "emoji": st.status_emoji(code),
                "count": by_status.get(code, 0),
            }
            for code in st.STATUSES
        ],
        "top_items": [{"name": name, "count": count} for name, count in top_items],
    }
