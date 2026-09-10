"""SANUKI UDON SHOP — единая точка входа.

Запускает веб-приложение (FastAPI + SPA) и Telegram-бота в одном процессе,
поверх одной базы данных. Поэтому статусы заказов всегда одинаковы
в боте, в веб-приложении и в админ-панели.

    python main.py

Переменные окружения: BOT_TOKEN, ADMIN_ID, YOOMONEY_API (см. .env.example).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

import config
import db
from api.server import create_app
from bot import app as bot_app

logging.basicConfig(
    level=logging.DEBUG if config.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
log = logging.getLogger("sanuki")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("SANUKI запускается…")
    await db.init_db()
    bot_app.setup_bot()
    await bot_app.start_bot()
    if config.webapp_url():
        log.info("Веб-приложение: %s", config.webapp_url())
    log.info("Администраторы: %s", config.ADMIN_IDS or "не заданы")
    log.info("ЮMoney: %s (заглушка=%s)", config.YOOMONEY_MODE, not config.YOOMONEY_API)
    try:
        yield
    finally:
        await bot_app.stop_bot()
        await db.close()
        log.info("SANUKI остановлен")


app = create_app()
app.router.lifespan_context = lifespan


if __name__ == "__main__":
    if not config.BOT_TOKEN:
        log.warning("BOT_TOKEN не задан — бот не запустится (веб продолжит работу)")
    if not config.ADMIN_IDS:
        log.warning("ADMIN_ID не задан — админ-панель будет недоступна")

    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG,
        reload_excludes=["data/*", "*.db", "*.db-wal", "*.db-shm", "webapp/*"],
        log_level="debug" if config.DEBUG else "info",
    )
