"""Инициализация Telegram-бота и запуск его рядом с веб-сервером."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, MenuButtonWebApp, WebAppInfo

import config
from bot.handlers import router
from bot.notifier import handle_event
from core import notify

log = logging.getLogger("sanuki.bot")

_bot: Optional[Bot] = None
_dp: Optional[Dispatcher] = None
_polling_task: Optional[asyncio.Task] = None


def get_bot() -> Optional[Bot]:
    return _bot


def get_dispatcher() -> Optional[Dispatcher]:
    return _dp


def setup_bot() -> Optional[Bot]:
    """Создаёт бота и диспетчер. Возвращает None, если токен не задан."""
    global _bot, _dp

    if not config.BOT_TOKEN:
        log.warning("BOT_TOKEN не задан — бот отключён, веб-приложение работает.")
        return None
    if not config.BOT_ENABLED:
        log.info("Бот отключён через BOT_ENABLED=0")
        return None

    _bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    _dp = Dispatcher(storage=MemoryStorage())
    _dp.include_router(router)
    notify.subscribe(handle_event)
    return _bot


async def start_bot() -> None:
    """Запускает polling (или настраивает вебхук) в фоне."""
    global _polling_task

    if _bot is None and config.BOT_TOKEN and config.BOT_ENABLED:
        setup_bot()
    if _bot is None or _dp is None:
        return

    try:
        await _bot.delete_webhook(drop_pending_updates=True)

        await _bot.set_my_commands(
            [
                BotCommand(command="start", description="🌸 Запустить SANUKI"),
                BotCommand(command="menu", description="🍽 Главное меню"),
                BotCommand(command="orders", description="📋 Мои заказы"),
                BotCommand(command="app", description="🌐 Открыть приложение"),
                BotCommand(command="admin", description="👨‍🍳 Админ-панель"),
                BotCommand(command="stats", description="📊 Статистика"),
            ]
        )
        url = config.webapp_url()
        if url:
            await _bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(text="🌐 Меню", web_app=WebAppInfo(url=url))
            )
    except Exception:
        log.exception("Не удалось подключить бота (проверьте BOT_TOKEN и сеть). "
                      "Веб-приложение продолжает работу.")

    if config.WEBHOOK_URL:
        webhook_url = config.WEBHOOK_URL.rstrip("/") + config.WEBHOOK_PATH
        await _bot.set_webhook(webhook_url, drop_pending_updates=True)
        log.info("Бот работает на вебхуке: %s", webhook_url)
        return

    _polling_task = asyncio.create_task(_polling())
    try:
        me = await _bot.get_me()
        log.info("Бот @%s запущен (long polling)", me.username)
    except Exception:
        log.warning("Не удалось получить данные бота — polling всё равно запущен")


async def _polling() -> None:
    try:
        await _dp.start_polling(_bot, allowed_updates=_dp.resolve_used_update_types())
    except asyncio.CancelledError:
        pass
    except Exception:
        log.exception("Polling остановлен")


async def stop_bot() -> None:
    global _polling_task, _bot
    notify.unsubscribe(handle_event)

    if _polling_task:
        _polling_task.cancel()
        try:
            await _polling_task
        except (asyncio.CancelledError, Exception):
            pass
        _polling_task = None

    if _bot is not None:
        try:
            if _dp is not None:
                await _dp.stop_polling()
        except Exception:
            pass
        try:
            session = await _bot.get_session()
            if session and not session.closed:
                await session.close()
        except Exception:
            pass
        _bot = None
