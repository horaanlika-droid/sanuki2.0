"""Конфигурация SANUKI.

На хостинге достаточно заполнить три переменные:

    BOT_TOKEN      — токен Telegram-бота
    ADMIN_ID       — Telegram ID администратора (можно несколько через запятую)
    YOOMONEY_API   — токен ЮMoney (сейчас используется заглушкой)

Все остальные переменные необязательны, у них есть разумные значения
по умолчанию. См. `.env.example`.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "webapp"

load_dotenv(BASE_DIR / ".env")


def _env(name: str, default=None):
    value = os.getenv(name)
    if value is None or str(value).strip() == "":
        return default
    return value.strip()


def _flag(name: str, default: bool = False) -> bool:
    value = _env(name)
    if value is None:
        return default
    return value.lower() in ("1", "true", "yes", "on", "да")


def _int(name: str, default: int) -> int:
    try:
        return int(str(_env(name, default)).strip())
    except (TypeError, ValueError):
        return default


def _admin_ids() -> list[int]:
    """Поддерживаем и ADMIN_ID (один), и ADMIN_IDS (список)."""
    raw = _env("ADMIN_ID") or _env("ADMIN_IDS") or _env("ADMINS") or ""
    ids: list[int] = []
    for chunk in raw.replace(";", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            ids.append(int(chunk))
        except ValueError:
            continue
    return ids


# ---------- обязательное ----------
BOT_TOKEN: str = _env("BOT_TOKEN", "") or ""
ADMIN_IDS: list[int] = _admin_ids()
YOOMONEY_API: str = _env("YOOMONEY_API", "") or ""

# ---------- ЮMoney ----------
# stub  — оплата имитируется локально (реальных списаний нет)
# live  — реальные запросы к api.yoomoney.ru
YOOMONEY_MODE: str = (_env("YOOMONEY_MODE", "stub") or "stub").lower()
YOOMONEY_WALLET: str = _env("YOOMONEY_WALLET", "4100111111111111")
YOOMONEY_RETURN_URL: str = _env("YOOMONEY_RETURN_URL", "") or ""
YOOMONEY_SECRET: str = _env("YOOMONEY_SECRET", "") or ""

# ---------- сервер ----------
HOST: str = _env("HOST", "0.0.0.0")
PORT: int = _int("PORT", 8000)
DEBUG: bool = _flag("DEBUG", False)
DB_PATH: str = _env("DB_PATH", str(DATA_DIR / "sanuki.db"))

# Публичный адрес приложения. Если задан — бот показывает кнопку
# «Открыть приложение» (Telegram Web App) и ссылку в меню.
WEBAPP_URL: str = _env("WEBAPP_URL") or _env("PUBLIC_URL") or _env("APP_URL") or ""
# Если публичный адрес не задан, считаем, что он совпадает с адресом сервера.
if not WEBAPP_URL and not DEBUG:
    WEBAPP_URL = ""

# ---------- бот ----------
BOT_ENABLED: bool = _flag("BOT_ENABLED", True)
# Если задан WEBHOOK_URL — бот работает на вебхуке, иначе long polling.
WEBHOOK_URL: str = _env("WEBHOOK_URL", "") or ""
WEBHOOK_PATH: str = _env("WEBHOOK_PATH", "/telegram/webhook") or "/telegram/webhook"

# ---------- прочее ----------
# Разрешить вход без Telegram (для локальной разработки/демо).
# В продакшене держите DEBUG=0.
DEV_LOGIN: bool = _flag("DEV_LOGIN", DEBUG)


def webapp_url() -> str:
    """Актуальный адрес веб-приложения (без завершающего слэша)."""
    return (WEBAPP_URL or "").rstrip("/")


def is_admin(telegram_id) -> bool:
    try:
        return int(telegram_id) in ADMIN_IDS
    except (TypeError, ValueError):
        return False
