"""REST API для веб-приложения (меню, заказы, оплата, вызов сотрудника)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

import config
import db
from api.deps import admin_user, current_user, optional_user
from core import auth as auth_core
from core import menu as menu_core
from core import orders as orders_core
from core import payments as payments_core
from core import statuses as st

router = APIRouter(prefix="/api")


# --------------------------------------------------------------------------
# Публичные данные
# --------------------------------------------------------------------------
@router.get("/health")
async def health():
    return {"ok": True, "service": "sanuki", "bot": bool(config.BOT_TOKEN), "debug": config.DEBUG}


@router.get("/menu")
async def api_menu():
    stop = [row["name"] for row in await db.get_stop_list()]
    return menu_core.get_catalog(stop)


@router.get("/statuses")
async def api_statuses():
    return {
        "statuses": st.status_payload(),
        "order": st.STATUS_ORDER,
        "active": st.ACTIVE_STATUSES,
        "final": st.FINAL_STATUSES,
    }


@router.get("/settings")
async def api_settings():
    return menu_core.load_settings()


@router.get("/payment-methods")
async def api_payment_methods():
    return {"methods": payments_core.payment_methods(), "stub": payments_core.is_stub()}


# --------------------------------------------------------------------------
# Авторизация
# --------------------------------------------------------------------------
class TelegramLogin(BaseModel):
    init_data: str


class DevLogin(BaseModel):
    telegram_id: int
    name: Optional[str] = ""


@router.post("/auth/telegram")
async def login_telegram(payload: TelegramLogin):
    session = await auth_core.login(payload.init_data)
    if not session:
        raise HTTPException(status_code=401, detail="Не удалось подтвердить данные Telegram")
    return session


@router.post("/auth/dev")
async def login_dev(payload: DevLogin):
    session = await auth_core.dev_login(payload.telegram_id, payload.name)
    if not session:
        raise HTTPException(status_code=403, detail="Dev-вход отключён")
    return session


@router.get("/me")
async def me(user: dict = Depends(current_user)):
    return user


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None


@router.post("/me")
async def update_profile(payload: ProfileUpdate, user: dict = Depends(current_user)):
    updated = await db.upsert_user(
        user["telegram_id"],
        name=payload.name or "",
        phone=payload.phone or "",
        username=user.get("username") or "",
    )
    return {
        "telegram_id": updated.get("telegram_id"),
        "name": updated.get("name") or "",
        "phone": updated.get("phone") or "",
        "username": updated.get("username") or "",
        "is_admin": user.get("is_admin", False),
    }


# --------------------------------------------------------------------------
# Заказы
# --------------------------------------------------------------------------
class OrderIn(BaseModel):
    items: list[dict] = Field(default_factory=list)
    order_type: str = "dine_in"
    guest_name: Optional[str] = ""
    phone: Optional[str] = ""
    address: Optional[str] = ""
    comment: Optional[str] = ""
    table_number: Optional[str] = ""
    payment_method: Optional[str] = "cash"


@router.post("/orders")
async def create_order(payload: OrderIn, request: Request,
                       user: dict = Depends(current_user)):
    try:
        order = await orders_core.create_order(
            telegram_id=user["telegram_id"],
            guest_name=payload.guest_name or user.get("name") or "",
            items=payload.items,
            order_type=payload.order_type,
            phone=payload.phone,
            address=payload.address,
            comment=payload.comment,
            table_number=payload.table_number,
            payment_method=payload.payment_method or "cash",
            source="web",
            username=user.get("username") or "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    payment = await payments_core.create_payment(order, order["payment_method"])
    order = await orders_core.get_order(order["id"])
    return {"order": order, "payment": payment}


@router.get("/orders")
async def my_orders(user: dict = Depends(current_user)):
    orders = await orders_core.list_orders(telegram_id=user["telegram_id"], limit=50)
    return {"orders": orders}


@router.get("/orders/{key}")
async def order_detail(key: str, user: dict = Depends(current_user)):
    order = await _find_order(key)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    if not user.get("is_admin") and order.get("telegram_id") != user["telegram_id"]:
        raise HTTPException(status_code=403, detail="Это чужой заказ")
    history = await orders_core.get_history(order["id"])
    return {"order": order, "history": history, "timeline": st.timeline_for(order["order_type"])}


@router.post("/orders/{key}/cancel")
async def cancel_order(key: str, user: dict = Depends(current_user)):
    order = await _find_order(key)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    if not user.get("is_admin") and order.get("telegram_id") != user["telegram_id"]:
        raise HTTPException(status_code=403, detail="Это чужой заказ")
    if not order.get("can_cancel"):
        raise HTTPException(status_code=409, detail="Заказ уже нельзя отменить")
    updated = await orders_core.set_status(
        order["id"], "cancelled", actor=f"web:{user['telegram_id']}", comment="Отменён гостем"
    )
    return {"order": updated}


@router.post("/orders/{key}/pay")
async def pay_order(key: str, user: dict = Depends(current_user)):
    order = await _find_order(key)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    if not user.get("is_admin") and order.get("telegram_id") != user["telegram_id"]:
        raise HTTPException(status_code=403, detail="Это чужой заказ")
    payment = await payments_core.create_payment(order, order["payment_method"] or "yoomoney")
    order = await orders_core.get_order(order["id"])
    return {"order": order, "payment": payment}


@router.get("/orders/{key}/history")
async def order_history(key: str, user: dict = Depends(current_user)):
    order = await _find_order(key)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    if not user.get("is_admin") and order.get("telegram_id") != user["telegram_id"]:
        raise HTTPException(status_code=403, detail="Это чужой заказ")
    return {"history": await orders_core.get_history(order["id"])}


async def _find_order(key: str) -> Optional[dict]:
    if str(key).isdigit():
        return await orders_core.get_order(int(key))
    return await orders_core.get_order_by_code(key)


# --------------------------------------------------------------------------
# Оплата
# --------------------------------------------------------------------------
@router.post("/payments/stub/{code}")
async def stub_payment(code: str, user: dict = Depends(current_user)):
    """Подтверждение оплаты в режиме заглушки."""
    order = await orders_core.get_order_by_code(code)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    if not user.get("is_admin") and order.get("telegram_id") != user["telegram_id"]:
        raise HTTPException(status_code=403, detail="Это чужой заказ")
    updated = await payments_core.confirm_stub_payment(code)
    return {"order": updated}


@router.post("/payments/yoomoney/webhook")
async def yoomoney_webhook(request: Request):
    """Сюда ЮMoney будет присылать уведомления об оплате."""
    content_type = request.headers.get("content-type", "")
    if "json" in content_type:
        data = await request.json()
    else:
        form = await request.form()
        data = {k: v for k, v in form.items()}
    try:
        order = await payments_core.handle_notification(data)
    except PermissionError:
        raise HTTPException(status_code=403, detail="bad signature")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "order_id": order["id"]}


# --------------------------------------------------------------------------
# Вызов сотрудника
# --------------------------------------------------------------------------
class StaffCall(BaseModel):
    kind: str = "help"
    table_number: Optional[str] = ""
    guest_name: Optional[str] = ""


@router.post("/staff-call")
async def staff_call(payload: StaffCall, user: dict = Depends(current_user)):
    result = await orders_core.call_staff(
        telegram_id=user["telegram_id"],
        guest_name=payload.guest_name or user.get("name") or "",
        table_number=payload.table_number or "",
        kind=payload.kind or "help",
    )
    return {"ok": True, "call": result}
