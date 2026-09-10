"""
Мост бот <-> веб: уведомление админов о заказах с сайта.

Использует собственный экземпляр Bot (свой event loop веб-сервера),
чтобы не пересекаться с long polling бота.
"""
import logging

from aiogram.types import WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import ADMIN_IDS, BOT_TOKEN, web_app_url
from core import format_items_text, get_order, items_of

log = logging.getLogger("sanuki-bridge")

_web_bot = None


def _get_web_bot():
    global _web_bot
    if _web_bot is None:
        if not BOT_TOKEN:
            raise RuntimeError("BOT_TOKEN не задан")
        from aiogram import Bot
        _web_bot = Bot(token=BOT_TOKEN)
    return _web_bot


def admin_order_kb(order_id: int):
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Принять", callback_data=f"st:{order_id}:accepted")
    kb.button(text="🔪 Готовим", callback_data=f"st:{order_id}:cooking")
    kb.button(text="🍜 Готово", callback_data=f"st:{order_id}:ready")
    kb.button(text="🎉 Выдан", callback_data=f"st:{order_id}:issued")
    kb.button(text="❌ Отменить", callback_data=f"st:{order_id}:cancelled")
    kb.button(text="🌐 В веб-админку", web_app=WebAppInfo(url=web_app_url() + "#/admin"))
    kb.adjust(2, 2, 2)
    return kb.as_markup()


async def announce_admins_web(order_id: int, bot=None):
    """Отправка админам уведомления о заказе, созданном на сайте."""
    try:
        bot = bot or _get_web_bot()
        order = get_order(order_id)
        phone = f" · {order['phone']}" if order["phone"] else ""
        text = (
            f"🆕 <b>Новый заказ #{order['public_id']}</b> · 🌐 С САЙТА\n\n"
            f"👤 {order['guest_name']}{phone}\n"
            f"📦 {order['order_type']}\n\n"
            f"{format_items_text(items_of(order))}\n\n"
            f"💰 <b>{order['total']} ₽</b> · "
            + ("💳 ЮMoney" if order["pay_method"] == "yoomoney" else "💵 при получении")
        )
        if order["comment"]:
            text += f"\n📝 {order['comment']}"
        kb = admin_order_kb(order_id)
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, text, reply_markup=kb)
            except Exception as e:
                log.warning("Админ %s недоступен: %s", admin_id, e)
    except Exception as e:
        log.warning("Не удалось уведомить админов о заказе #%s: %s", order_id, e)
