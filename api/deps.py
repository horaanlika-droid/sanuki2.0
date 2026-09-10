"""Зависимости FastAPI: разбор сессии, проверка прав администратора."""

from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException, Query, Request

import config
import db


async def _token_from(request: Request, authorization: Optional[str],
                      token: Optional[str]) -> str:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    if token:
        return token.strip()
    return request.headers.get("X-Session-Token", "").strip()


async def current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
) -> dict:
    raw = await _token_from(request, authorization, token)
    session = await db.get_session(raw)
    if not session:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    user = await db.get_user(session["telegram_id"]) or {}
    return {
        "telegram_id": int(session["telegram_id"]),
        "name": session.get("name") or user.get("name") or "",
        "username": session.get("username") or user.get("username") or "",
        "phone": user.get("phone") or "",
        "is_admin": config.is_admin(session["telegram_id"]),
    }


async def optional_user(
    request: Request,
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
) -> Optional[dict]:
    try:
        return await current_user(request, authorization, token)
    except HTTPException:
        return None


async def admin_user(user: dict = None) -> dict:
    """Админ — тот, чей Telegram ID указан в ADMIN_ID."""
    if not user:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Доступ только для администратора")
    return user
