"""Админ-панель веб-приложения (работает с той же БД, что и бот)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

import db
from api.deps import admin_user, current_user
from core import orders as orders_core
from core import statuses as st

router = APIRouter(prefix="/api/admin")


@router.get("/orders")
async def admin_orders(
    status: Optional[str] = Query(None),
    active: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    user: dict = Depends(current_user),
):
    await admin_user(user)
    orders = await orders_core.list_orders(
        status=status, active_only=active, limit=limit
    )
    return {"orders": orders}


class StatusIn(BaseModel):
    status: str
    comment: Optional[str] = ""


@router.post("/orders/{order_id}/status")
async def admin_set_status(order_id: int, payload: StatusIn,
                           user: dict = Depends(current_user)):
    await admin_user(user)
    if payload.status not in st.STATUSES:
        raise HTTPException(status_code=400, detail="Неизвестный статус")
    try:
        order = await orders_core.set_status(
            order_id,
            payload.status,
            actor=f"admin:{user['telegram_id']}",
            comment=payload.comment or "",
            strict=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"order": order}


@router.get("/stats")
async def admin_stats(user: dict = Depends(current_user)):
    await admin_user(user)
    return await orders_core.stats()


@router.get("/stop-list")
async def admin_stop_list(user: dict = Depends(current_user)):
    await admin_user(user)
    return {"items": await db.get_stop_list()}


class StopItem(BaseModel):
    name: str
    reason: Optional[str] = ""


@router.post("/stop-list")
async def admin_stop_add(payload: StopItem, user: dict = Depends(current_user)):
    await admin_user(user)
    await db.add_stop_item(payload.name.strip(), payload.reason or "")
    return {"items": await db.get_stop_list()}


@router.delete("/stop-list/{name}")
async def admin_stop_remove(name: str, user: dict = Depends(current_user)):
    await admin_user(user)
    await db.remove_stop_item(name)
    return {"items": await db.get_stop_list()}


@router.get("/statuses")
async def admin_statuses(user: dict = Depends(current_user)):
    await admin_user(user)
    return {"statuses": st.status_payload(), "actions": st.ADMIN_ACTIONS}
