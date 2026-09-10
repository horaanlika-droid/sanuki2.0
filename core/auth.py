"""Авторизация веб-приложения через Telegram Web App.

Клиент присылает `window.Telegram.WebApp.initData`, сервер проверяет
подпись (HMAC-SHA256 по секрету из токена бота) и выдаёт сессию.
Так пользователь в браузере — тот же, что и в боте: общие заказы,
общие статусы.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Optional

import config
import db

log = logging.getLogger("sanuki.auth")

SESSION_TTL_HOURS = 24 * 30


def _secret_key() -> bytes:
    return hmac.new(b"WebAppData", config.BOT_TOKEN.encode("utf-8"), hashlib.sha256).digest()


def parse_init_data(init_data: str) -> dict:
    params = dict(urllib.parse.parse_qsl(init_data or "", keep_blank_values=True))
    return params


def verify_init_data(init_data: str, max_age_seconds: int = 24 * 3600) -> Optional[dict]:
    """Проверяет подпись Telegram и возвращает данные пользователя."""
    if not init_data or not config.BOT_TOKEN:
        return None

    params = parse_init_data(init_data)
    received_hash = params.pop("hash", "")
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    calculated = hmac.new(
        _secret_key(), data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(calculated, received_hash.lower()):
        return None

    try:
        auth_date = int(params.get("auth_date", 0))
    except ValueError:
        auth_date = 0
    if auth_date and time.time() - auth_date > max_age_seconds:
        log.warning("Устаревший initData")
        return None

    user_raw = params.get("user")
    user = {}
    if user_raw:
        try:
            user = json.loads(user_raw)
        except ValueError:
            user = {}

    return {
        "telegram_id": int(user.get("id")) if user.get("id") else None,
        "name": " ".join(
            p for p in [user.get("first_name", ""), user.get("last_name", "")] if p
        ).strip(),
        "username": user.get("username", ""),
        "auth_date": auth_date,
        "start_param": params.get("start_param", ""),
        "raw": params,
    }


async def login(init_data: str) -> Optional[dict]:
    data = verify_init_data(init_data)
    if not data or not data.get("telegram_id"):
        return None
    return await issue_session(
        telegram_id=data["telegram_id"],
        name=data.get("name", ""),
        username=data.get("username", ""),
    )


async def issue_session(telegram_id: int, name: str, username: str) -> dict:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)
    await db.create_session(
        telegram_id=int(telegram_id),
        name=name or "",
        username=username or "",
        token=token,
        expires_at=expires.strftime("%Y-%m-%d %H:%M:%S"),
    )
    return {
        "token": token,
        "telegram_id": int(telegram_id),
        "name": name or "",
        "username": username or "",
        "is_admin": config.is_admin(telegram_id),
    }


async def dev_login(telegram_id: int, name: str = "") -> Optional[dict]:
    """Вход без Telegram — только для локальной разработки (DEV_LOGIN=1)."""
    if not config.DEV_LOGIN:
        return None
    user = await db.get_user(telegram_id) or {}
    return await issue_session(
        telegram_id=int(telegram_id),
        name=name or user.get("name") or "Гость",
        username=user.get("username") or "",
    )
