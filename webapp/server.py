"""
SANUKI WEB — FastAPI сервер веб-приложения.

Всё в одном файле (routes + запуск), чтобы на BotHost не было лишней
структуры. Статика — из webapp/static. Шаблоны не используются:
SPA (fetch + JSON API), стиль — как на брендовом постере SANUKI.
"""
import asyncio
import json
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

import core
import payments
from config import ADMIN_IDS
from core import (
    ACTIVE_STATUSES,
    ORDER_TYPES,
    STATUSES,
    add_user,
    all_orders,
    category_items,
    format_items_text,
    get_order,
    get_order_by_public,
    notify_user,
    order_history,
    set_event_loop,
    stats,
    subscribe,
    unsubscribe,
    update_status,
    udon_bases,
    udon_proteins,
    udon_toppings,
    user_orders,
)

log = logging.getLogger("sanuki-web")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="SANUKI UDON SHOP", docs_url=None, redoc_url=None)

app.mount("/assets", StaticFiles(directory="webapp/assets"), name="assets")


# ============================================================
# Стартовые хуки: event loop для шины событий
# ============================================================
@app.on_event("startup")
async def _startup():
    set_event_loop(asyncio.get_running_loop())
    core.init_db()
    log.info("SANUKI WEB запущен. Статусы синхронизированы с ботом.")


# ============================================================
# Страница
# ============================================================
@app.get("/", response_class=HTMLResponse)
async def index():
    with open("webapp/index.html", encoding="utf-8") as f:
        return HTMLResponse(f.read())


# ============================================================
# API: меню и настройки
# ============================================================
@app.get("/api/menu")
async def api_menu():
    return {
        "categories": [
            {"id": "fresh",    "title": "Fresh",    "items": category_items("FRESH")},
            {"id": "starters", "title": "Starters", "items": category_items("STARTERS")},
            {"id": "drinks",   "title": "Напитки",  "items": category_items("Напитки")},
        ],
        "udon": {
            "bases": udon_bases(),
            "proteins": udon_proteins(),
            "toppings": udon_toppings(),
        },
        "extras": category_items("Дополнительные топпинги"),
        "statuses": [{"id": k, "title": v["web"], "color": v["color"]} for k, v in STATUSES.items()],
    }


@app.get("/api/settings")
async def api_settings():
    s = core.settings()
    return {
        "address": s.get("address", "Санкт-Петербург, Гороховая 34"),
        "work_hours": s.get("work_hours", "11:00 - 23:00"),
        "phone": s.get("phone", "+7 (XXX) XXX-XX-XX"),
        "yoomoney_stub": payments.IS_STUB,
    }


# ============================================================
# API: заказы
# ============================================================
def _order_json(o, with_items: bool = True) -> dict:
    data = {
        "id": o["id"],
        "public_id": o["public_id"],
        "name": o["guest_name"],
        "phone": o["phone"],
        "type": o["order_type"],
        "status": o["status"],
        "status_title": STATUSES.get(o["status"], STATUSES["new"])["web"],
        "status_color": STATUSES.get(o["status"], STATUSES["new"])["color"],
        "total": o["total"],
        "pay_method": o["pay_method"],
        "payment_stub": bool(o["payment_id"] and str(o["payment_id"]).startswith("stub-")),
        "source": o["source"],
        "created_at": o["created_at"],
        "history": [
            {"status": STATUSES.get(h["status"], {"web": h["status"]})["web"],
             "color": STATUSES.get(h["status"], {"color": "#333"})["color"],
             "at": h["created_at"]}
            for h in order_history(o["id"])
        ],
    }
    if with_items:
        data["items"] = core.items_of(o)
        data["items_text"] = format_items_text(core.items_of(o))
    return data


@app.post("/api/orders")
async def api_create_order(request: Request):
    """Создание заказа с сайта. Механика та же, что в боте."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "bad json")

    name = (payload.get("name") or "").strip()[:60]
    phone = (payload.get("phone") or "").strip()[:24]
    order_type = payload.get("order_type") or "С собой 🥡"
    if order_type not in ORDER_TYPES.values():
        order_type = ORDER_TYPES.get(order_type, "С собой 🥡")
    items = payload.get("items") or []
    comment = (payload.get("comment") or "").strip()[:300] or None
    pay_method = payload.get("pay_method") or "cash"

    if not name:
        raise HTTPException(422, "Укажите имя")
    if not items:
        raise HTTPException(422, "Корзина пуста")

    total = 0
    norm_items = []
    for it in items:
        qty = max(1, int(it.get("qty", 1)))
        price = int(it.get("price", 0))
        line = {"kind": it.get("kind", "item"), "title": it.get("title") or it.get("name") or "",
                "price": price, "qty": qty}
        if it.get("kind") == "udon":
            line.update({"base": it.get("base"), "protein": it.get("protein"),
                         "topping": it.get("topping"), "extras": it.get("extras") or []})
        norm_items.append(line)
        total += price * qty

    telegram_id = payload.get("telegram_id")  # из Telegram Mini App, если есть
    order_id = core.save_order(
        telegram_id=telegram_id,
        guest_name=name,
        order_type=order_type,
        items=norm_items,
        total=total,
        source="web",
        phone=phone or None,
        comment=comment,
        pay_method=pay_method if pay_method in ("cash", "yoomoney") else "cash",
    )

    if telegram_id:
        add_user(int(telegram_id), name, "", phone or None)

    # Админам в Telegram — уведомление с кнопками смены статуса
    from webbridge import announce_admins_web
    await announce_admins_web(order_id)

    order = get_order(order_id)
    return _order_json(order)


@app.post("/api/orders/{order_id}/pay")
async def api_pay_stub(order_id: int):
    """Оплата — ЗАГЛУШКА ЮMoney. Позже здесь будет реальная касса."""
    order = get_order(order_id)
    if not order:
        raise HTTPException(404, "Заказ не найден")
    payment = payments.create_payment(order_id, order["total"])
    result = payments.confirm_payment_stub(order_id, payment["payment_id"])
    return JSONResponse(result)


@app.get("/api/orders/{order_id}")
async def api_order(order_id: int):
    o = get_order(order_id)
    if not o:
        raise HTTPException(404, "Заказ не найден")
    return _order_json(o)


@app.get("/api/orders/by-public/{public_id}")
async def api_order_by_public(public_id: str):
    o = get_order_by_public(public_id)
    if not o:
        raise HTTPException(404, "Заказ не найден")
    return _order_json(o)


@app.get("/api/my-orders")
async def api_my_orders(telegram_id: int):
    rows = user_orders(int(telegram_id), limit=20)
    return [_order_json(o, with_items=False) for o in rows]


# ============================================================
# API: админ
# ============================================================
def _check_admin(request: Request):
    admin = request.query_params.get("admin") or request.headers.get("X-Admin-Id")
    try:
        if int(admin or 0) not in ADMIN_IDS:
            raise HTTPException(403, "Доступ только для администратора")
        return int(admin)
    except ValueError:
        raise HTTPException(403, "Доступ только для администратора")


@app.get("/api/admin/orders")
async def api_admin_orders(request: Request, scope: str = "active"):
    _check_admin(request)
    if scope == "all":
        rows = all_orders(None, limit=60)
    else:
        rows = all_orders(list(ACTIVE_STATUSES) + ["new"], limit=30)
    return [_order_json(o) for o in rows]


@app.get("/api/admin/stats")
async def api_admin_stats(request: Request):
    _check_admin(request)
    return stats()


@app.post("/api/admin/orders/{order_id}/status")
async def api_admin_set_status(order_id: int, request: Request):
    _check_admin(request)
    body = await request.json()
    status = body.get("status")
    if status not in STATUSES:
        raise HTTPException(422, "Неверный статус")
    if not get_order(order_id):
        raise HTTPException(404, "Заказ не найден")
    update_status(order_id, status)
    order = get_order(order_id)
    from core import status_message
    await notify_user(order["telegram_id"], status_message(order_id, status))
    return {"ok": True, "status": status}


# ============================================================
# SSE: живые события (статусы, новые заказы)
# ============================================================
@app.get("/api/events")
async def api_events(request: Request, admin: str | None = None):
    if admin:  # админский стрим — проверяем
        _check_admin(request)
    queue = await subscribe()

    async def stream():
        try:
            yield "retry: 3000\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            unsubscribe(queue)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })
