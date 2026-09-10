"""
SANUKI — точка входа: поднимает веб-приложение (FastAPI, порт WEB_PORT)
и Telegram-бота (long polling) в одном процессе.

На BotHost достаточно трёх переменных окружения:
    BOT_TOKEN     — токен бота из BotFather
    ADMIN_ID      — ID администратора (можно несколько через запятую)
    YOOMONEY_API  — ключ API ЮMoney (пока можно оставить пустым — работает заглушка)

Опционально:
    WEB_BASE_URL  — публичный https-адрес веб-приложения (для кнопки в боте)
    WEB_PORT      — порт веб-приложения (по умолчанию 8000)
"""
import asyncio
import logging
import threading

import uvicorn

from config import BOT_TOKEN, WEB_PORT

log = logging.getLogger("sanuki")


def run_web() -> None:
    uvicorn.run(
        "webapp.server:app",
        host="0.0.0.0",
        port=WEB_PORT,
        log_level="warning",
    )


def main() -> None:
    threading.Thread(target=run_web, daemon=True, name="sanuki-web").start()

    if not BOT_TOKEN:
        log.warning("BOT_TOKEN не задан — запускаю только веб-приложение.")
        threading.Event().wait()  # спим вечно
        return

    from bot import main as bot_main
    asyncio.run(bot_main())


if __name__ == "__main__":
    main()
