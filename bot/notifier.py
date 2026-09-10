"""Уведомления в Telegram.

Подписывается на события ядра: если заказ создан в веб-приложении —
администратор получит сообщение в боте; если статус изменён в админке —
гость получит уведомление в Telegram. Тексты статусов общие (core.statuses).
"""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import config
from core import orders as orders_core
from core import statuses as st

log = logging.getLogger("sanuki.notifier")

STATUS_MESSAGES = {
    "new": "🆕 Заказ <b>создан</b> и передан кухне.",
    "accepted": "✅ Заказ <b>принят</b>! Начинаем готовить! 🔪",
    "cooking": "🔪 Заказ <b>готовится</b>! Ожидайте 10–15 минут ⏰",
    "ready": (
        "🍜 <b>Заказ готов!</b>\n\n"
        "🌸 Если вы в кафе — скоро принесут.\n"
        "🥡 Если с собой — можете забирать.\n"
        "🛵 Если доставка — передаём курьеру."
    ),
    "on_the_way": "🛵 Курьер уже в пути! Заказ скоро будет у вас.",
    "completed": "🎉 <b>Заказ выдан.</b> Спасибо, что выбрали SANUKI! 🌸",
    "cancelled": "❌ Заказ <b>отменён</b>. Приносим извинения.",
}


def status_message(status: str) -> str:
    return STATUS_MESSAGES.get(
        status, f"🔄 Статус заказа обновлён: <b>{st.status_title(status)}</b>"
    )


async def _safe_send(bot: Bot, chat_id: int, text: str, **kwargs) -> bool:
    try:
        await bot.send_message(chat_id, text, **kwargs)
        return True
    except TelegramForbiddenError:
        log.info("Пользователь %s запретил сообщения", chat_id)
    except TelegramRetryAfter as exc:
        log.warning("Flood limit: повтор через %s сек", exc.retry_after)
    except Exception:
        log.exception("Не удалось отправить сообщение %s", chat_id)
    return False


def _admin_keyboard(order: dict) -> InlineKeyboardMarkup:
    from bot.keyboards import admin_order_actions

    return admin_order_actions(order)


async def handle_event(event: str, payload: dict) -> None:
    from bot.app import get_bot

    bot = get_bot()
    if bot is None:
        return

    if event == "order_created":
        await _on_created(bot, payload)
    elif event == "order_status_changed":
        await _on_status(bot, payload)
    elif event == "payment_changed":
        await _on_payment(bot, payload)
    elif event == "staff_call":
        await _on_staff(bot, payload)


async def _on_created(bot: Bot, payload: dict) -> None:
    order = payload["order"]
    source = payload.get("source", "web")
    where = "🌐 веб-приложение" if source == "web" else "🤖 Telegram-бот"

    text = (
        f"🆕 <b>Новый заказ #{order['code']}</b> ({where})\n\n"
        f"👤 {order['guest_name']}"
        + (f" @{order['username']}" if order.get("username") else "")
        + "\n"
        f"📦 {order['order_type_title']}\n"
        + (f"🏠 Адрес: {order['address']}\n" if order.get("address") else "")
        + (f"💬 {order['comment']}\n" if order.get("comment") else "")
        + f"💳 Оплата: {order['payment_method']} ({order['payment_status']})\n\n"
        f"📝 Состав:\n{order['items_text']}\n\n"
        f"💰 <b>{order['total']} ₽</b>\n"
        f"{order['status_emoji']} Статус: <b>{order['status_title']}</b>"
    )

    for admin_id in config.ADMIN_IDS:
        await _safe_send(bot, admin_id, text, reply_markup=_admin_keyboard(order))

    # Гостю — подтверждение (одинаковое для бота и веба).
    if order.get("telegram_id"):
        await _safe_send(
            bot,
            order["telegram_id"],
            f"✅ <b>Заказ #{order['code']} оформлен!</b>\n\n"
            f"💰 Сумма: {order['total']} ₽\n"
            f"📦 {order['order_type_title']}\n"
            f"{order['status_emoji']} Статус: <b>{order['status_title']}</b>\n\n"
            "🍜 Мы начинаем готовить. Статус будет меняться здесь и в приложении — "
            "они всегда одинаковые.",
        )


async def _on_status(bot: Bot, payload: dict) -> None:
    order = payload["order"]
    status = payload["status"]
    actor = payload.get("actor", "system")

    if order.get("telegram_id"):
        await _safe_send(
            bot,
            order["telegram_id"],
            f"🌸 <b>Заказ #{order['code']}</b>\n\n{status_message(status)}",
        )

    if not str(actor).startswith("admin:"):
        for admin_id in config.ADMIN_IDS:
            await _safe_send(
                bot,
                admin_id,
                f"🔄 Заказ #{order['code']} — {order['status_label']}",
            )


async def _on_payment(bot: Bot, payload: dict) -> None:
    order = payload["order"]
    state = payload.get("payment_status")
    if state != "paid":
        return

    if order.get("telegram_id"):
        await _safe_send(
            bot,
            order["telegram_id"],
            f"💜 <b>Оплата заказа #{order['code']} прошла!</b>\n\n"
            f"Сумма: {order['total']} ₽. Спасибо! 🌸",
        )
    for admin_id in config.ADMIN_IDS:
        await _safe_send(
            bot,
            admin_id,
            f"💜 Заказ #{order['code']} оплачен ({order['total']} ₽)",
            reply_markup=_admin_keyboard(order),
        )


async def _on_staff(bot: Bot, payload: dict) -> None:
    kind_title = payload.get("kind_title", "🛎 Вызов сотрудника")
    text = (
        f"{kind_title}\n\n"
        f"👤 {payload.get('guest_name') or 'Гость'}\n"
        + (f"🪑 Стол: {payload['table_number']}\n" if payload.get("table_number") else "")
        + "🕓 Сотрудник, откликнитесь!"
    )
    for admin_id in config.ADMIN_IDS:
        await _safe_send(bot, admin_id, text)
