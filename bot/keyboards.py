"""Клавиатуры бота (aiogram 3). Тексты статусов берём из core.statuses."""

from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

import config
from core import statuses as st
from core.menu import ORDER_TYPES


def _btn(text: str, callback: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback)


def main_menu() -> InlineKeyboardMarkup:
    rows = [
        [_btn("🍽 Сделать заказ", "order:start")],
        [_btn("📋 Мои заказы", "orders")],
        [_btn("🎌 О SANUKI", "about"), _btn("📞 Позвать сотрудника", "staff")],
    ]
    if config.webapp_url():
        rows.insert(0, [_btn("🌐 Открыть приложение", "webapp")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def webapp_reply_keyboard() -> ReplyKeyboardMarkup | None:
    """Постоянная кнопка веб-приложения под полем ввода."""
    url = config.webapp_url()
    if not url:
        return None
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🌐 Открыть SANUKI", web_app=WebAppInfo(url=url))]],
        resize_keyboard=True,
        is_persistent=True,
    )


def order_types() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("🍽 В кафе", "order:type:dine_in")],
            [_btn("🥡 С собой", "order:type:takeaway")],
            [_btn("🛵 Доставка", "order:type:delivery")],
            [_btn("🔙 Назад", "main")],
        ]
    )


def bases(bases_list: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [_btn(f"{b['emoji']} {b['name']}", f"base:{b['name']}")]
        for b in bases_list
        if b.get("available", True)
    ]
    rows.append([_btn("🔙 Назад", "order:start")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def proteins(proteins_list: list[dict], with_back: bool = True) -> InlineKeyboardMarkup:
    rows = [
        [_btn(f"{p['emoji']} {p['name']} — {p['price']} ₽", f"protein:{p['name']}")]
        for p in proteins_list
        if p.get("available", True)
    ]
    if with_back:
        rows.append([_btn("🔙 Назад", "step:base")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def toppings(toppings_list: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [_btn(f"{t['emoji']} {t['name']} ✅", f"topping:{t['name']}")]
        for t in toppings_list
        if t.get("available", True)
    ]
    rows.append([_btn("⏭ Пропустить", "topping:skip")])
    rows.append([_btn("🔙 Назад", "step:protein")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def extras(extras_list: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [_btn(f"{e['emoji']} {e['name']} — {e['price']} ₽", f"extra:{e['name']}")]
        for e in extras_list
        if e.get("available", True)
    ]
    rows.append([_btn("🛒 Готово → Корзина", "cart")])
    rows.append([_btn("🔙 Назад", "step:topping")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def categories(categories_list: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [_btn(f"{c['emoji']} {c['name']}", f"cat:{c['name']}")]
        for c in categories_list
        if c.get("kind") == "items" and c.get("items")
    ]
    rows.append([_btn("🍜 Собрать удон", "order:start")])
    rows.append([_btn("🛒 Корзина", "cart")])
    rows.append([_btn("🔙 Главное меню", "main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def category_items(category: dict) -> InlineKeyboardMarkup:
    rows = []
    for item in category.get("items", []):
        if not item.get("available", True):
            continue
        rows.append(
            [_btn(f"{item['name']} — {item['price']} ₽", f"item:{category['name']}:{item['name']}")]
        )
    rows.append([_btn("🛒 В корзину", "cart")])
    rows.append([_btn("🔙 К категориям", "catalog")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cart() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("➕ Добавить ещё", "catalog")],
            [_btn("🗑 Очистить", "cart:clear")],
            [_btn("✅ Оформить заказ", "checkout")],
            [_btn("🏠 Главное меню", "main")],
        ]
    )


def payment_methods() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("💵 Наличными", "pay:cash")],
            [_btn("💳 Картой при получении", "pay:card")],
            [_btn("💜 ЮMoney (онлайн)", "pay:yoomoney")],
            [_btn("🔙 К корзине", "cart")],
        ]
    )


def confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("✅ Всё верно", "confirm")],
            [_btn("🔙 К корзине", "cart")],
        ]
    )


def admin_order_actions(order: dict) -> InlineKeyboardMarkup:
    """Кнопки статусов — ровно те же, что и в веб-админке."""
    rows = []
    for code in order.get("next_statuses", []):
        label = st.ADMIN_ACTIONS.get(code, st.status_label(code))
        rows.append([_btn(label, f"admin:{code}:{order['id']}")])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else InlineKeyboardMarkup(
        inline_keyboard=[[_btn("🏠 В меню", "main")]]
    )


def staff() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("🆘 Нужна помощь", "staff:help")],
            [_btn("🧾 Счёт", "staff:bill")],
            [_btn("🔙 Назад", "main")],
        ]
    )


def user_orders(orders: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [
            _btn(
                f"{o['status_emoji']} #{o['code']} · {o['total']} ₽",
                f"order:{o['id']}",
            )
        ]
        for o in orders[:10]
    ]
    rows.append([_btn("🍽 Сделать заказ", "order:start")])
    rows.append([_btn("🏠 Главное меню", "main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def order_card(order: dict) -> InlineKeyboardMarkup:
    rows = []
    if config.webapp_url():
        rows.append([_btn("🌐 Открыть в приложении", "webapp")])
    rows.append([_btn("🔙 К заказам", "orders"), _btn("🏠 Главное меню", "main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
