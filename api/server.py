"""FastAPI-приложение: REST API + раздача веб-приложения."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import config
from api.admin import router as admin_router
from api.routes import router as api_router

log = logging.getLogger("sanuki.api")

WEBAPP_DIR = Path(__file__).resolve().parent.parent / "webapp"
STATIC_DIR = WEBAPP_DIR / "static"
INDEX_FILE = WEBAPP_DIR / "index.html"

DESCRIPTION = """
API SANUKI UDON SHOP. Один и тот же слой данных обслуживает
Telegram-бота и веб-приложение: заказы, статусы и история общие.
"""


def create_app() -> FastAPI:
    app = FastAPI(
        title="SANUKI API",
        description=DESCRIPTION,
        version="2.0.0",
        docs_url="/api/docs",
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    app.include_router(admin_router)

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # ---------- SPA ----------
    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(INDEX_FILE)

    @app.get("/healthz", include_in_schema=False)
    async def healthz():
        return {"ok": True}

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        candidate = WEBAPP_DIR / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(INDEX_FILE)

    # ---------- вебхук Telegram (если задан WEBHOOK_URL) ----------
    def _bot():
        from bot.app import get_bot, get_dispatcher

        return get_bot(), get_dispatcher()

    if config.WEBHOOK_URL:
        from aiogram.types import Update

        @app.post(config.WEBHOOK_PATH)
        async def telegram_webhook(request: Request):
            bot, dp = _bot()
            if bot is None or dp is None:
                return {"ok": False, "reason": "bot disabled"}
            data = await request.json()
            await dp.feed_update(bot, Update.model_validate(data))
            return {"ok": True}

    return app
