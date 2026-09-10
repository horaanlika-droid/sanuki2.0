"""Обработчики Telegram-бота.

Логика заказов повторяет веб-приложение: те же шаги конструктора,
те же статусы (core.statuses), та же база заказов.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

import config
import db
from core import menu as menu_core
from core import orders as orders_core
from core import statuses as st

log = logging.getLogger("sanuki.bot")

router = Router()

WELCOME = (
    "🌸 <b>SANUKI UDON SHOP</b>\n\n"
    "Футуристичный вкус Японии в сердце Петербурга.\n"
    "🍜 Свежие ингредиенты · 15–20 минут · собираем удон сами\n\n"
)


class Registration(StatesGroup):
    waiting_name = State()


class OrderFlow(StatesGroup):
    order_type = State()
    base = State()
    protein = State()
    topping = State()
    extras = State()
    cart = State()
    payment = State()
    delivery_address = State()
    confirm = State()


# --------------------------------------------------------------------------
#Helpers
# --------------------------------------------------------------------------
async def _catalog():
    stop = [row["name"] for row in await db.get_stop_list()]
    return menu_core.get_catalog(stop)


def _udon_of(catalog: dict) -> dict:
    return catalog.get("udon", {"bases": [], "proteins": [], "toppings": []})


def _extras_of(catalog: dict) -> list[dict]:
    for cat in catalog.get("categories", []):
        if cat["name"] == "Дополнительные топпинги":
            return cat.get("items", [])
    return []


async def _state_items(state: FSMContext) -> list[dict]:
    data = await state.get_data()
    return list(data.get("items", []))


async def _add_item(state: FSMContext, item: dict) -> None:
    items = await _state_items(state)
    items.append(item)
    await state.update_data(items=items)


def _cart_text(items: list[dict], total: int) -> str:
    if not items:
        return "🛒 <b>Корзина пуста</b>\n\nДобавьте что-нибудь из меню!"
    lines = [menu_core.describe_item(item) for item in items]
    return (
        "🛒 <b>Ваш заказ</b>\n\n"
        + "\n".join(lines)
        + f"\n\n💰 <b>Итого:</b> {total} ₽"
    )


def _webapp_button() -> InlineKeyboardMarkup | None:
    url = config.webapp_url()
    if not url:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Открыть SANUKI", web_app=WebAppInfo(url=url))]
        ]
    )


async def _require_user(message: Message | CallbackQuery) -> dict | None:
    telegram_id = message.from_user.id
    user = await db.get_user(telegram_id)
    if not user:
        text = "Сначала запустите бота командой /start"
        if isinstance(message, CallbackQuery):
            await message.answer(text, show_alert=True)
        else:
            await message.answer(text)
        return None
    return user


# --------------------------------------------------------------------------
# Регистрация и главное меню
# --------------------------------------------------------------------------
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = await db.get_user(message.from_user.id)
    if user:
        text = (
            WELCOME
            + f"🌸 <b>С возвращением, {user['name']}!</b>\n\n"
            + "🍜 Что желаете?"
        )
        kb = _webapp_button()
        if kb:
            await message.answer(
                "Держите приложение SANUKI — меню, заказы и статусы в один тап:",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[
                        [
                            KeyboardButton(
                                text="🌐 Открыть SANUKI",
                                web_app=WebAppInfo(url=config.webapp_url()),
                            )
                        ]
                    ],
                    resize_keyboard=True,
                    is_persistent=True,
                ),
            )
        await message.answer(text, reply_markup=main_menu_kb())
        return

    await db.upsert_user(
        message.from_user.id,
        username=message.from_user.username or "",
    )
    await message.answer(
        WELCOME
        + "📍 Гороховая, 34\n\n"
        + "✨ Прежде чем начать, представьтесь, пожалуйса:"
    )
    await state.set_state(Registration.waiting_name)


@router.message(Registration.waiting_name)
async def registration_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()[:64]
    if not name:
        await message.answer("Введите, пожалуйста, ваше имя:")
        return

    await db.upsert_user(
        message.from_user.id,
        name=name,
        username=message.from_user.username or "",
    )
    await state.clear()
    await message.answer(
        f"🌺 <b>Приятно познакомиться, {name}!</b>\n\n"
        "Добро пожаловать в мир SANUKI —\n"
        "где традиции встречаются с футуризмом.\n\n"
        "🍜 Выберите действие:",
        reply_markup=main_menu_kb(),
    )


def main_menu_kb() -> InlineKeyboardMarkup:
    from bot.keyboards import main_menu

    return main_menu()


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала пройдите регистрацию через /start")
        return
    await message.answer(f"🌸 <b>Главное меню, {user['name']}</b>", reply_markup=main_menu_kb())


@router.message(Command("app"))
async def cmd_app(message: Message) -> None:
    url = config.webapp_url()
    if not url:
        await message.answer(
            "Веб-приложение не настроено: задайте переменную WEBAPP_URL "
            "(например, https://ваш-домен), чтобы получить кнопку приложения."
        )
        return
    await message.answer(
        "🌐 <b>SANUKI в один тап</b>\n\nМеню, конструктор удона, оплата и статусы заказов:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Открыть приложение", web_app=WebAppInfo(url=url))]
            ]
        ),
    )


@router.callback_query(F.data == "webapp")
async def cb_webapp(callback: CallbackQuery) -> None:
    url = config.webapp_url()
    if not url:
        await callback.answer("WEBAPP_URL не задан", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(
        "🌐 Открыть приложение SANUKI:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Открыть", web_app=WebAppInfo(url=url))]
            ]
        ),
    )


@router.callback_query(F.data == "main")
async def cb_main(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    user = await db.get_user(callback.from_user.id)
    name = user["name"] if user else "гость"
    await callback.answer("🌺 Главное меню")
    await callback.message.edit_text(
        f"🌸 <b>Главное меню, {name}</b>", reply_markup=main_menu_kb()
    )


@router.callback_query(F.data == "about")
async def cb_about(callback: CallbackQuery) -> None:
    settings = menu_core.load_settings()
    await callback.answer("🎌 О SANUKI")
    await callback.message.edit_text(
        "🌸 <b>SANUKI UDON SHOP</b>\n\n"
        f"📍 <b>Адрес:</b> {settings['address']}\n"
        f"⏰ <b>Режим работы:</b> {settings['work_hours']}\n"
        f"☎️ <b>Телефон:</b> {settings['phone']}\n\n"
        "🍜 <b>О нас:</b>\n"
        "Мы создаём настоящий удон по японским рецептам,\n"
        "добавляя футуристичный акцент в каждое блюдо.\n\n"
        "🇯🇵 <b>Добро пожаловать в будущее вкуса!</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="main")]]
        ),
    )


# --------------------------------------------------------------------------
# Конструктор заказа
# --------------------------------------------------------------------------
@router.callback_query(F.data == "order:start")
async def cb_order_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(items=[])
    await state.set_state(OrderFlow.order_type)
    await callback.answer("🍽 Создаём заказ")
    await callback.message.edit_text(
        "🌸 <b>Создание заказа</b>\n\nГде вы планируете насладиться удоном?",
        reply_markup=order_types_kb(),
    )


def order_types_kb() -> InlineKeyboardMarkup:
    from bot.keyboards import order_types

    return order_types()


@router.callback_query(OrderFlow.order_type, F.data.startswith("order:type:"))
async def cb_order_type(callback: CallbackQuery, state: FSMContext) -> None:
    code = callback.data.split(":", 2)[2]
    if code not in menu_core.ORDER_TYPES:
        await callback.answer("Неизвестный формат")
        return
    await state.update_data(order_type=code, base=None, protein=None, topping=None, extras=[])
    await state.set_state(OrderFlow.base)

    catalog = await _catalog()
    await callback.answer(menu_core.ORDER_TYPES[code])
    await callback.message.edit_text(
        f"🌸 <b>Вы выбрали: {menu_core.ORDER_TYPES[code]}</b>\n\n"
        "Теперь выберите <b>основу</b> для вашего удона:\n"
        "👇 Каждый вариант — это уникальный вкус.",
        reply_markup=bases_kb(_udon_of(catalog)["bases"]),
    )


def bases_kb(items) -> InlineKeyboardMarkup:
    from bot.keyboards import bases

    return bases(items)


@router.callback_query(F.data == "step:base")
async def cb_step_base(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(OrderFlow.base)
    catalog = await _catalog()
    await callback.message.edit_text(
        "🌸 <b>Шаг 1 из 4 — основа</b>\n\nВыберите основу для вашего удона:",
        reply_markup=bases_kb(_udon_of(catalog)["bases"]),
    )


@router.callback_query(OrderFlow.base, F.data.startswith("base:"))
async def cb_base(callback: CallbackQuery, state: FSMContext) -> None:
    base_name = callback.data.split(":", 1)[1]
    await state.update_data(base=base_name)
    await state.set_state(OrderFlow.protein)

    catalog = await _catalog()
    description = ""
    for base in _udon_of(catalog)["bases"]:
        if base["name"] == base_name:
            description = base.get("description", "")
            break

    await callback.answer(f"✅ {base_name}")
    await callback.message.edit_text(
        f"🌸 <b>Шаг 2 из 4 — белок</b>\n\n"
        f"<b>Основа:</b> {base_name}\n"
        + (f"📖 {description}\n\n" if description else "\n")
        + "Теперь выберите <b>главный ингредиент</b>:",
        reply_markup=proteins_kb(_udon_of(catalog)["proteins"]),
    )


def proteins_kb(items) -> InlineKeyboardMarkup:
    from bot.keyboards import proteins

    return proteins(items)


@router.callback_query(F.data == "step:protein")
async def cb_step_protein(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(OrderFlow.protein)
    catalog = await _catalog()
    await callback.message.edit_text(
        "🌸 <b>Шаг 2 из 4 — белок</b>\n\nВыберите главный ингредиент:",
        reply_markup=proteins_kb(_udon_of(catalog)["proteins"]),
    )


@router.callback_query(OrderFlow.protein, F.data.startswith("protein:"))
async def cb_protein(callback: CallbackQuery, state: FSMContext) -> None:
    protein_name = callback.data.split(":", 1)[1]
    info = menu_core.find_protein(protein_name)
    if not info:
        await callback.answer("Позиция недоступна")
        return
    await state.update_data(protein=info["name"], protein_price=info["price"])
    await state.set_state(OrderFlow.topping)

    catalog = await _catalog()
    await callback.answer(f"✅ {info['name']}")
    await callback.message.edit_text(
        f"🌸 <b>Шаг 3 из 4 — топпинг</b>\n\n"
        f"Основа: {(await state.get_data()).get('base')}\n"
        f"Белок: {info['name']} ({info['price']} ₽)\n\n"
        "Выберите <b>топпинг</b> — это <b>бесплатно</b>:",
        reply_markup=toppings_kb(_udon_of(catalog)["toppings"]),
    )


def toppings_kb(items) -> InlineKeyboardMarkup:
    from bot.keyboards import toppings

    return toppings(items)


@router.callback_query(F.data == "step:topping")
async def cb_step_topping(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(OrderFlow.topping)
    catalog = await _catalog()
    await callback.message.edit_text(
        "🌸 <b>Шаг 3 из 4 — топпинг</b>\n\nВыберите бесплатный топпинг:",
        reply_markup=toppings_kb(_udon_of(catalog)["toppings"]),
    )


async def _show_extras(callback: CallbackQuery, state: FSMContext, note: str = "") -> None:
    await state.set_state(OrderFlow.extras)
    catalog = await _catalog()
    data = await state.get_data()
    chosen = data.get("extras", [])
    chosen_text = (
        "\n".join(f"  ➕ {e['name']} — {e['price']} ₽" for e in chosen)
        if chosen
        else "пока ничего не добавлено"
    )
    await callback.message.edit_text(
        "🌸 <b>Шаг 4 из 4 — дополнительные топпинги</b>\n\n"
        f"Выбрано:\n{chosen_text}\n\n"
        + (f"{note}\n\n" if note else "")
        + "Можно добавить ещё или перейти в корзину:",
        reply_markup=extras_kb(_extras_of(catalog)),
    )


def extras_kb(items) -> InlineKeyboardMarkup:
    from bot.keyboards import extras

    return extras(items)


@router.callback_query(OrderFlow.topping, F.data.startswith("topping:"))
async def cb_topping(callback: CallbackQuery, state: FSMContext) -> None:
    value = callback.data.split(":", 1)[1]
    if value == "skip":
        await state.update_data(topping="Без топпинга")
        await callback.answer("⏭ Топпинг пропущен")
        await _show_extras(callback, state)
        return
    await state.update_data(topping=value)
    await callback.answer(f"✅ {value}")
    await _show_extras(callback, state)


@router.callback_query(OrderFlow.extras, F.data.startswith("extra:"))
async def cb_extra(callback: CallbackQuery, state: FSMContext) -> None:
    name = callback.data.split(":", 1)[1]
    data = await state.get_data()
    chosen = list(data.get("extras", []))
    prices = menu_core.extras_prices()
    price = prices.get((name or "").strip().lower(), 0)
    chosen.append({"name": name, "price": price})
    await state.update_data(extras=chosen)
    await callback.answer(f"✅ {name} добавлен")
    await _show_extras(callback, state)


# --------------------------------------------------------------------------
# Каталог закусок/напитков
# --------------------------------------------------------------------------
@router.callback_query(F.data == "catalog")
async def cb_catalog(callback: CallbackQuery, state: FSMContext) -> None:
    catalog = await _catalog()
    await callback.answer("📋 Категории")
    await callback.message.edit_text(
        "🌸 <b>Что хотите добавить?</b>\n\nВыберите категорию:",
        reply_markup=categories_kb(catalog["categories"]),
    )


def categories_kb(items) -> InlineKeyboardMarkup:
    from bot.keyboards import categories

    return categories(items)


@router.callback_query(F.data.startswith("cat:"))
async def cb_category(callback: CallbackQuery, state: FSMContext) -> None:
    name = callback.data.split(":", 1)[1]
    catalog = await _catalog()
    category = next((c for c in catalog["categories"] if c["name"] == name), None)
    if not category:
        await callback.answer("Категория не найдена")
        return
    await callback.answer(f"{category['emoji']} {name}")
    await callback.message.edit_text(
        f"{category['emoji']} <b>{name}</b>", reply_markup=category_items_kb(category)
    )


def category_items_kb(category) -> InlineKeyboardMarkup:
    from bot.keyboards import category_items

    return category_items(category)


@router.callback_query(F.data.startswith("item:"))
async def cb_add_item(callback: CallbackQuery, state: FSMContext) -> None:
    _, category_name, item_name = callback.data.split(":", 2)
    item = menu_core.build_simple_item(item_name)
    if not item:
        await callback.answer("Позиция недоступна")
        return
    await _add_item(state, item)
    await callback.answer(f"✅ {item_name} добавлен")

    catalog = await _catalog()
    category = next((c for c in catalog["categories"] if c["name"] == category_name), None)
    if category:
        await callback.message.edit_text(
            f"✅ <b>{item_name}</b> добавлен в корзину!\n\n"
            "Можно выбрать ещё или перейти в корзину:",
            reply_markup=category_items_kb(category),
        )


# --------------------------------------------------------------------------
# Корзина
# --------------------------------------------------------------------------
@router.callback_query(F.data == "cart")
async def cb_cart(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()

    # Если удон собран, но ещё не положен в корзину — кладём.
    if data.get("base") and data.get("protein") and not data.get("udon_added"):
        udon = menu_core.build_udon(
            base=data["base"],
            protein=data["protein"],
            topping=data.get("topping") or "Без топпинга",
            extras=[e["name"] for e in data.get("extras", [])],
        )
        await _add_item(state, udon)
        await state.update_data(udon_added=True)

    items = await _state_items(state)
    total = menu_core.items_total(items)
    await state.update_data(total=total)
    await state.set_state(OrderFlow.cart)

    await callback.answer("🛒 Корзина")
    await callback.message.edit_text(_cart_text(items, total), reply_markup=cart_kb())


def cart_kb() -> InlineKeyboardMarkup:
    from bot.keyboards import cart

    return cart()


@router.callback_query(F.data == "cart:clear")
async def cb_cart_clear(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(items=[], base=None, protein=None, topping=None, extras=[],
                            udon_added=False, total=0)
    await state.set_state(OrderFlow.order_type)
    await callback.answer("🗑 Корзина очищена")
    await callback.message.edit_text(
        "🌸 <b>Корзина очищена</b>\n\nНачните заказ заново:", reply_markup=order_types_kb()
    )


@router.callback_query(F.data == "checkout")
async def cb_checkout(callback: CallbackQuery, state: FSMContext) -> None:
    items = await _state_items(state)
    total = menu_core.items_total(items)
    if total <= 0:
        await callback.answer("🛒 Корзина пуста!", show_alert=True)
        return
    await state.set_state(OrderFlow.payment)
    await callback.answer("💳 Оплата")
    await callback.message.edit_text(
        f"📋 <b>Оформление заказа</b>\n\n💰 Сумма: <b>{total} ₽</b>\n\n"
        "Выберите способ оплаты:",
        reply_markup=payment_methods_kb(),
    )


def payment_methods_kb() -> InlineKeyboardMarkup:
    from bot.keyboards import payment_methods

    return payment_methods()


@router.callback_query(OrderFlow.payment, F.data.startswith("pay:"))
async def cb_payment(callback: CallbackQuery, state: FSMContext) -> None:
    method = callback.data.split(":", 1)[1]
    await state.update_data(payment_method=method)
    data = await state.get_data()

    if data.get("order_type") == "delivery":
        await state.set_state(OrderFlow.delivery_address)
        await callback.answer("🛵 Укажите адрес")
        await callback.message.edit_text(
            "🛵 <b>Доставка</b>\n\nНапишите адрес доставки одним сообщением:"
        )
        return

    await _show_confirmation(callback, state)


@router.message(OrderFlow.delivery_address)
async def delivery_address(message: Message, state: FSMContext) -> None:
    await state.update_data(address=(message.text or "").strip()[:200])
    await _show_confirmation(message, state)


async def _show_confirmation(target: Message | CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    items = await _state_items(state)
    total = menu_core.items_total(items)
    order_type = menu_core.ORDER_TYPES.get(data.get("order_type", "dine_in"), "")

    text = (
        "📋 <b>Подтверждение заказа</b>\n\n"
        + _cart_text(items, total)
        + f"\n\n📦 {order_type}\n"
        + (f"🏠 Адрес: {data.get('address')}\n" if data.get("address") else "")
        + "💳 Оплата: "
        + {"cash": "наличными", "card": "картой при получении", "yoomoney": "ЮMoney"}.get(
            data.get("payment_method", "cash"), "наличными"
        )
        + "\n\n🌸 Всё верно?"
    )
    await state.set_state(OrderFlow.confirm)

    from bot.keyboards import confirm as confirm_kb

    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=confirm_kb())
    else:
        await target.answer(text, reply_markup=confirm_kb())


@router.callback_query(OrderFlow.confirm, F.data == "confirm")
async def cb_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    items = await _state_items(state)
    if not items:
        await callback.answer("🛒 Корзина пуста!", show_alert=True)
        return

    user = await db.get_user(callback.from_user.id)
    try:
        order = await orders_core.create_order(
            telegram_id=callback.from_user.id,
            guest_name=(user or {}).get("name") or callback.from_user.full_name,
            items=items,
            order_type=data.get("order_type", "dine_in"),
            address=data.get("address", ""),
            payment_method=data.get("payment_method", "cash"),
            source="bot",
            username=(user or {}).get("username") or "",
        )
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return

    await state.clear()

    # Заказ онлайн — показываем кнопку оплаты (заглушка ЮMoney).
    from core import payments as payments_core

    kb_rows = []
    if order["payment_method"] == "yoomoney":
        payment = await payments_core.create_payment(order, "yoomoney")
        if payment.get("payment_url"):
            kb_rows.append(
                [
                    InlineKeyboardButton(
                        text=f"💜 Оплатить {order['total']} ₽",
                        web_app=WebAppInfo(url=_absolute(payment["payment_url"])),
                    )
                ]
                if _absolute(payment["payment_url"]).startswith("http")
                else [
                    InlineKeyboardButton(
                        text=f"💜 Оплатить {order['total']} ₽", callback_data="noop"
                    )
                ]
            )
    kb_rows.append([InlineKeyboardButton(text="📋 Мои заказы", callback_data="orders")])
    kb_rows.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="main")])

    await callback.answer("✅ Заказ оформлен!")
    await callback.message.edit_text(
        _order_created_text(order), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows)
    )


def _absolute(url: str) -> str:
    if url.startswith("http"):
        return url
    return (config.webapp_url() + "/" + url.lstrip("/")) if config.webapp_url() else url


def _order_created_text(order: dict) -> str:
    return (
        f"✅ <b>Заказ #{order['code']} оформлен!</b>\n\n"
        f"💰 Сумма: {order['total']} ₽\n"
        f"📦 {order['order_type_title']}\n"
        f"{st.status_emoji(order['status'])} Статус: <b>{st.status_title(order['status'])}</b>\n\n"
        "🍜 Мы начинаем готовить. Статус будет меняться здесь и в приложении — "
        "они всегда одинаковые."
    )


# --------------------------------------------------------------------------
# Мои заказы
# --------------------------------------------------------------------------
@router.message(Command("orders"))
async def cmd_orders(message: Message) -> None:
    orders = await orders_core.list_orders(telegram_id=message.from_user.id, limit=10)
    if not orders:
        await message.answer(
            "📋 <b>История заказов</b>\n\nПока здесь пусто...\n"
            "🍜 Сделайте свой первый заказ в SANUKI!"
        )
        return
    await message.answer(_orders_text(orders), reply_markup=user_orders_kb(orders))


@router.callback_query(F.data == "orders")
async def cb_orders(callback: CallbackQuery) -> None:
    orders = await orders_core.list_orders(telegram_id=callback.from_user.id, limit=10)
    if not orders:
        await callback.answer("Пока заказов нет")
        await callback.message.edit_text(
            "📋 <b>История заказов</b>\n\nПока здесь пусто...\n"
            "🍜 Сделайте свой первый заказ в SANUKI!",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🍽 Сделать заказ", callback_data="order:start")]]
            ),
        )
        return
    await callback.answer("📋 Ваши заказы")
    await callback.message.edit_text(_orders_text(orders), reply_markup=user_orders_kb(orders))


def _orders_text(orders: list[dict]) -> str:
    lines = []
    for order in orders:
        lines.append(
            f"{order['status_emoji']} <b>№{order['code']}</b> · {order['created_at'][11:16]}\n"
            f"   {order['status_title']} · {order['total']} ₽ · {order['order_type_title']}"
        )
    return "📋 <b>Ваши заказы</b>\n\n" + "\n".join(lines)


def user_orders_kb(orders) -> InlineKeyboardMarkup:
    from bot.keyboards import user_orders

    return user_orders(orders)


@router.callback_query(F.data.startswith("order:"))
async def cb_order_detail(callback: CallbackQuery) -> None:
    order_id = int(callback.data.split(":", 1)[1])
    order = await orders_core.get_order(order_id)
    if not order or order.get("telegram_id") != callback.from_user.id:
        await callback.answer("Заказ не найден")
        return
    history = await orders_core.get_history(order_id)
    await callback.answer()
    await callback.message.edit_text(
        _order_detail_text(order, history), reply_markup=order_card_kb(order)
    )


def _order_detail_text(order: dict, history: list[dict]) -> str:
    lines = [
        f"🍜 <b>Заказ №{order['code']}</b>",
        "",
        order["items_text"],
        "",
        f"💰 <b>Итого:</b> {order['total']} ₽",
        f"📦 {order['order_type_title']}",
        f"{order['status_emoji']} <b>Статус: {order['status_title']}</b>",
        f"💳 Оплата: {order['payment_status']}",
        "",
        "🕓 <b>История статусов:</b>",
    ]
    for entry in history:
        lines.append(
            f"   {entry['status_emoji']} {entry['status_title']} · {entry['created_at'][11:16]}"
        )
    return "\n".join(lines)


def order_card_kb(order) -> InlineKeyboardMarkup:
    from bot.keyboards import order_card

    return order_card(order)


# --------------------------------------------------------------------------
# Вызов сотрудника
# --------------------------------------------------------------------------
@router.callback_query(F.data == "staff")
async def cb_staff(callback: CallbackQuery) -> None:
    await callback.answer("📞 Вызов сотрудника")
    await callback.message.edit_text(
        "🛎 <b>Чем можем помочь?</b>\n\nВыберите причину вызова:", reply_markup=staff_kb()
    )


def staff_kb() -> InlineKeyboardMarkup:
    from bot.keyboards import staff

    return staff()


@router.callback_query(F.data.in_({"staff:help", "staff:bill"}))
async def cb_staff_call(callback: CallbackQuery) -> None:
    kind = callback.data.split(":", 1)[1]
    user = await db.get_user(callback.from_user.id)
    await orders_core.call_staff(
        telegram_id=callback.from_user.id,
        guest_name=(user or {}).get("name") or callback.from_user.full_name,
        table_number="",
        kind=kind,
    )
    await callback.answer("🛎 Вызов отправлен")
    if kind == "help":
        text = "🆘 <b>Сотрудник уже в пути!</b>\n\nПодождите минуту, мы поможем с заказом."
    else:
        text = "🧾 <b>Счёт будет предоставлен</b>\n\nСотрудник подойдёт к вам в ближайшее время."
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🏠 Главное меню", callback_data="main")]]
        ),
    )


# --------------------------------------------------------------------------
# Админ-панель в боте (те же статусы, что и в вебе)
# --------------------------------------------------------------------------
@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if not config.is_admin(message.from_user.id):
        await message.answer("⛔ <b>Доступ запрещён</b>")
        return

    orders = await orders_core.list_orders(active_only=True, limit=20)
    if not orders:
        await message.answer(
            "📭 <b>Активных заказов нет</b>\n\n🌸 Все заказы выполнены. Отдыхайте!"
        )
        return

    stats = await orders_core.stats()
    await message.answer(
        f"👨‍🍳 <b>Админ-панель SANUKI</b>\n\n"
        f"Активных заказов: <b>{len(orders)}</b>\n"
        f"Выручка: <b>{stats['revenue']} ₽</b>\n\n"
        "Статусы синхронны с веб-приложением:"
    )
    for order in orders:
        await message.answer(_admin_order_text(order), reply_markup=admin_actions_kb(order))


def _admin_order_text(order: dict) -> str:
    return (
        f"{order['status_emoji']} <b>Заказ #{order['code']}</b> "
        f"(ID {order['id']}, {order['source']})\n"
        f"👤 {order['guest_name']} "
        + (f"@{order['username']}" if order.get("username") else "")
        + "\n"
        f"📦 {order['order_type_title']}\n"
        f"📊 Статус: <b>{order['status_title']}</b>\n"
        + (f"💳 Оплата: {order['payment_status']}\n" if order["payment_method"] == "yoomoney" else "")
        + f"📝 {order['items_text']}\n"
        f"💰 {order['total']} ₽"
    )


def admin_actions_kb(order) -> InlineKeyboardMarkup:
    from bot.keyboards import admin_order_actions

    return admin_order_actions(order)


@router.callback_query(F.data.startswith("admin:"))
async def cb_admin_status(callback: CallbackQuery) -> None:
    if not config.is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return

    _, status, order_id = callback.data.split(":", 2)
    try:
        order = await orders_core.set_status(
            int(order_id),
            status,
            actor=f"admin:{callback.from_user.id}",
            strict=True,
        )
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return

    await callback.answer(st.status_label(status))
    if order["status"] in st.FINAL_STATUSES:
        await callback.message.edit_text(
            f"{order['status_emoji']} Заказ #{order['code']} — <b>{order['status_title']}</b>\n\n"
            "Статус обновлён в боте и в веб-приложении."
        )
    else:
        await callback.message.edit_text(
            _admin_order_text(order), reply_markup=admin_actions_kb(order)
        )


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if not config.is_admin(message.from_user.id):
        await message.answer("⛔ <b>Доступ запрещён</b>")
        return
    stats = await orders_core.stats()
    lines = [
        f"{s['emoji']} {s['title']}: <b>{s['count']}</b>" for s in stats["by_status"]
    ]
    await message.answer(
        "📊 <b>Статистика SANUKI</b>\n\n"
        f"Всего заказов: <b>{stats['total_orders']}</b>\n"
        f"Выручка: <b>{stats['revenue']} ₽</b>\n"
        f"Средний чек: <b>{stats['avg_total']} ₽</b>\n\n"
        + "\n".join(lines)
    )


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.message()
async def fallback(message: Message, state: FSMContext) -> None:
    """Любое сообщение вне сценария — подсказка, что делать."""
    current = await state.get_state()
    if current in (Registration.waiting_name, OrderFlow.delivery_address):
        return
    await message.answer(
        "🌸 Я не понял сообщение. Откройте меню командой /menu "
        "или соберите удон через /start."
    )
