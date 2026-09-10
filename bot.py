"""
SANUKI BOT — Telegram-бот (aiogram 3).

Механика полностью совпадает с веб-приложением:
- общая база (core.py), единые статусы заказа;
- заказы из веба прилетают боту в личку админу с кнопками смены статуса;
- смена статуса ботом обновляет сайт в реальном времени (SSE),
  и наоборот;
- кнопка «Открыть на сайте» у заказов и в меню.
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    MenuButtonWebApp,
    Message,
    WebAppInfo,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

import core
from config import ADMIN_IDS, BOT_TOKEN, web_app_url
from core import (
    ACTIVE_STATUSES,
    ORDER_TYPES,
    STATUSES,
    add_user,
    all_orders,
    category_items,
    format_items_text,
    get_order,
    init_db,
    notify_user,
    set_bot_loop,
    set_client_notify,
    status_message,
    udon_bases,
    udon_proteins,
    udon_toppings,
    update_status,
    user_exists,
    user_orders,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("sanuki-bot")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()


# ============================================================
# FSM
# ============================================================
class Reg(StatesGroup):
    name = State()


class Order(StatesGroup):
    fresh = State()
    starters = State()
    drinks = State()
    base = State()
    protein = State()
    topping = State()
    extras = State()
    cart = State()


# ============================================================
# Клавиатуры
# ============================================================
def main_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🍽 Собрать заказ", callback_data="start_order")
    kb.button(text="🌐 Веб-версия (моя карта)", web_app=WebAppInfo(url=web_app_url()))
    kb.button(text="📋 Мои заказы", callback_data="history")
    kb.button(text="🎌 О SANUKI", callback_data="about")
    kb.button(text="📞 Позвать сотрудника", callback_data="call_staff")
    kb.adjust(1, 1, 2, 1)
    return kb.as_markup()


def order_type_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🍽 В зале", callback_data="otype_dine_in")
    kb.button(text="🥡 С собой", callback_data="otype_takeaway")
    kb.button(text="🛵 Доставка", callback_data="otype_delivery")
    kb.button(text="🌐 Заказ с сайта", web_app=WebAppInfo(url=web_app_url()))
    kb.button(text="🔙 Назад", callback_data="back_main")
    kb.adjust(2, 1, 1, 1)
    return kb.as_markup()


def back_kb(cb: str, title: str = "🔙 Назад"):
    kb = InlineKeyboardBuilder()
    kb.button(text=title, callback_data=cb)
    return kb.as_markup()


def list_kb(items: list[dict], prefix: str, back_cb: str, cart_btn: bool = False):
    kb = InlineKeyboardBuilder()
    for it in items:
        price = it.get("price")
        label = f"{it['name']}" + (f" — {price} ₽" if price else "")
        kb.button(text=label, callback_data=f"{prefix}_{it['name']}")
    if cart_btn:
        kb.button(text="🛒 Корзина", callback_data="cart")
    kb.button(text="🔙 Назад", callback_data=back_cb)
    kb.adjust(1)
    return kb.as_markup()


def confirm_order_kb(order_id: int):
    kb = InlineKeyboardBuilder()
    kb.button(text="💳 Оплатить картой (тест)", callback_data=f"pay_{order_id}")
    kb.button(text="🌐 Открыть на сайте", web_app=WebAppInfo(url=web_app_url()))
    kb.button(text="📜 Мои заказы", callback_data="history")
    kb.adjust(1)
    return kb.as_markup()


def admin_order_kb(order_id: int):
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Принять", callback_data=f"st:{order_id}:accepted")
    kb.button(text="🔪 Готовим", callback_data=f"st:{order_id}:cooking")
    kb.button(text="🍜 Готово", callback_data=f"st:{order_id}:ready")
    kb.button(text="🎉 Выдан", callback_data=f"st:{order_id}:issued")
    kb.button(text="❌ Отменить", callback_data=f"st:{order_id}:cancelled")
    kb.button(text="🌐 В веб", web_app=WebAppInfo(url=web_app_url()))
    kb.adjust(2, 2, 2)
    return kb.as_markup()


def admin_root_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Обновить список", callback_data="admin_refresh")
    kb.button(text="🌐 Открыть веб-админку", web_app=WebAppInfo(url=web_app_url() + "#/admin"))
    kb.adjust(1, 1)
    return kb.as_markup()


# ============================================================
# /start, регистрация, общие экраны
# ============================================================
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, command: CommandObject | None = None):
    await state.clear()
    user = user_exists(message.from_user.id)
    if user:
        await message.answer(
            f"🌸 <b>С возвращением, {user['name']}!</b>\n\n"
            "Добро пожаловать в <b>SANUKI UDON SHOP</b>.\n"
            "Футуристичный вкус Японии в сердце Петербурга.\n\n"
            "🍜 Что желаете?",
            reply_markup=main_menu_kb(),
        )
        return
    await message.answer(
        "🌸 <b>Добро пожаловать в SANUKI UDON SHOP</b>\n\n"
        "Футуристичный вкус Японии в сердце Петербурга.\n"
        "📍 Гороховая, 34\n\n"
        "✨ Прежде чем начать, представьтесь, пожалуйста:"
    )
    await state.set_state(Reg.name)


@router.message(Reg.name)
async def save_name(message: Message, state: FSMContext):
    add_user(message.from_user.id, message.text.strip(), message.from_user.username or "")
    await state.clear()
    await message.answer(
        f"🌺 <b>Приятно познакомиться, {message.text.strip()}!</b>\n\n"
        "Добро пожаловать в мир SANUKI —\n"
        "где традиции встречаются с футуризмом.\n\n"
        "🍜 Выберите действие:",
        reply_markup=main_menu_kb(),
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🌸 <b>Меню SANUKI</b>\n\nВыберите, что посмотреть:",
        reply_markup=menu_categories_kb(),
    )


def menu_categories_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🍜 Собрать удон", callback_data="start_order")
    kb.button(text="🥗 Fresh", callback_data="cat_fresh")
    kb.button(text="🍗 Starters", callback_data="cat_starters")
    kb.button(text="🥤 Напитки", callback_data="cat_drinks")
    kb.button(text="🛒 Корзина", callback_data="cart")
    kb.button(text="🌐 Заказать на сайте", web_app=WebAppInfo(url=web_app_url()))
    kb.button(text="🔙 В главное меню", callback_data="back_main")
    kb.adjust(1, 3, 1, 1, 1)
    return kb.as_markup()


@router.callback_query(F.data == "back_main")
async def back_main(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    user = user_exists(cb.from_user.id)
    await cb.message.edit_text(
        f"🌸 <b>{'С возвращением, ' + user['name'] + '!' if user else 'SANUKI UDON SHOP'}</b>\n\n"
        "Футуристичный вкус Японии в сердце Петербурга.\n\n"
        "🍜 Что желаете?",
        reply_markup=main_menu_kb(),
    )
    await cb.answer()


@router.callback_query(F.data == "about")
async def about(cb: CallbackQuery):
    from core import settings

    s = settings()
    await cb.message.edit_text(
        "🎌 <b>SANUKI UDON SHOP</b>\n\n"
        "Свежие ингредиенты · 15–20 минут · выбираешь сам.\n\n"
        f"📍 {s.get('address', 'Санкт-Петербург, Гороховая 34')}\n"
        f"🕒 {s.get('work_hours', '11:00 - 23:00')}\n"
        f"📞 {s.get('phone', '+7 (XXX) XXX-XX-XX')}\n\n"
        "saké kaori, tabe e no manazashi...",
        reply_markup=back_kb("back_main", "🏠 В главное меню"),
    )
    await cb.answer()


# ============================================================
# Категории Fresh / Starters / Напитки
# ============================================================
@router.callback_query(F.data == "cat_fresh")
async def cat_fresh(cb: CallbackQuery, state: FSMContext):
    await state.set_state(Order.fresh)
    items = category_items("FRESH")
    await cb.message.edit_text("🥗 <b>FRESH</b>\n\nСвежие и лёгкие закуски:",
                               reply_markup=list_kb(items, "add", "back_main", True))
    await cb.answer()


@router.callback_query(F.data == "cat_starters")
async def cat_starters(cb: CallbackQuery, state: FSMContext):
    await state.set_state(Order.starters)
    items = category_items("STARTERS")
    await cb.message.edit_text("🍗 <b>STARTERS</b>\n\nГорячие закуски к вашему удону:",
                               reply_markup=list_kb(items, "add", "back_main", True))
    await cb.answer()


@router.callback_query(F.data == "cat_drinks")
async def cat_drinks(cb: CallbackQuery, state: FSMContext):
    await state.set_state(Order.drinks)
    items = category_items("Напитки")
    await cb.message.edit_text("🥤 <b>Напитки</b>\n\nОсвежающие напитки к вашему заказу:",
                               reply_markup=list_kb(items, "add", "back_main", True))
    await cb.answer()


@router.callback_query(F.data.startswith("add_"))
async def add_simple(cb: CallbackQuery, state: FSMContext):
    name = cb.data[4:]
    pool = (category_items("FRESH") + category_items("STARTERS")
            + category_items("Напитки"))
    item = next((i for i in pool if i["name"] == name), None)
    if not item:
        await cb.answer("Не нашёл позицию 😔", show_alert=True)
        return
    data = await state.get_data()
    cart = data.get("cart", [])
    for line in cart:
        if line.get("kind") == "item" and line.get("name") == name:
            line["qty"] = line.get("qty", 1) + 1
            break
    else:
        cart.append({"kind": "item", "name": item["name"], "price": item["price"], "qty": 1})
    await state.update_data(cart=cart)
    await cb.answer(f"✅ {name} в корзине!")


# ============================================================
# Конструктор удона
# ============================================================
@router.callback_query(F.data == "start_order")
async def start_order(cb: CallbackQuery, state: FSMContext):
    await state.set_state(Order.base)
    await state.update_data(cart=[], extras=[])
    await cb.message.edit_text(
        "🌸 <b>Создание заказа</b>\n\nГде вы планируете насладиться удоном?",
        reply_markup=order_type_kb(),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("otype_"))
async def choose_otype(cb: CallbackQuery, state: FSMContext):
    otype = ORDER_TYPES[cb.data[6:]]
    await state.update_data(order_type=otype)
    await state.set_state(Order.base)
    bases = udon_bases()
    kb = InlineKeyboardBuilder()
    for b in bases:
        kb.button(text=f"{b['name']}", callback_data=f"base_{b['name']}")
    kb.button(text="🔙 Назад", callback_data="back_main")
    kb.adjust(1)
    await cb.message.edit_text(
        f"🌸 <b>Вы выбрали: {otype}</b>\n\n"
        "Теперь выберите <b>основу</b> для вашего удона:\n"
        "👇 Каждый вариант — это уникальный вкус.",
        reply_markup=kb.as_markup(),
    )
    await cb.answer(f"✅ {otype}")


@router.callback_query(F.data.startswith("base_"))
async def choose_base(cb: CallbackQuery, state: FSMContext):
    base_name = cb.data[5:]
    base = next((b for b in udon_bases() if b["name"] == base_name), None)
    await state.update_data(base=base_name)
    await state.set_state(Order.protein)
    kb = InlineKeyboardBuilder()
    for p in udon_proteins():
        kb.button(text=f"{p['name']} — {p['price']} ₽", callback_data=f"prot_{p['name']}")
    kb.button(text="🔙 Назад", callback_data="start_order")
    kb.adjust(1)
    await cb.message.edit_text(
        f"🌸 <b>Основа:</b> {base_name}\n"
        f"📖 {base['description'] if base else ''}\n\n"
        "Теперь выберите <b>главный ингредиент</b>:",
        reply_markup=kb.as_markup(),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("prot_"))
async def choose_protein(cb: CallbackQuery, state: FSMContext):
    name = cb.data[5:]
    protein = next((p for p in udon_proteins() if p["name"] == name), None)
    if not protein:
        await cb.answer("Не нашёл белок 😔", show_alert=True)
        return
    await state.update_data(protein=name, protein_price=protein["price"])
    await state.set_state(Order.topping)
    kb = InlineKeyboardBuilder()
    for t in udon_toppings():
        kb.button(text=f"🌿 {t['name']}", callback_data=f"top_{t['name']}")
    kb.button(text="⏭ Без топпинга", callback_data="top_skip")
    kb.button(text="🔙 Назад", callback_data="back_to_base")
    kb.adjust(1)
    await cb.message.edit_text(
        f"🌸 <b>Ваш выбор:</b> {name} (+{protein['price']} ₽)\n\n"
        "Теперь выберите <b>топпинг</b> — бесплатно:",
        reply_markup=kb.as_markup(),
    )
    await cb.answer()


@router.callback_query(F.data == "back_to_base")
async def back_to_base(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    otype = data.get("order_type", ORDER_TYPES["dine_in"])
    await state.set_state(Order.base)
    kb = InlineKeyboardBuilder()
    for b in udon_bases():
        kb.button(text=b["name"], callback_data=f"base_{b['name']}")
    kb.button(text="🔙 Назад", callback_data="start_order")
    kb.adjust(1)
    await cb.message.edit_text(f"🌸 <b>Формат: {otype}</b>\n\nВыберите <b>основу</b>:",
                               reply_markup=kb.as_markup())
    await cb.answer()


@router.callback_query(F.data.startswith("top_"))
async def choose_topping(cb: CallbackQuery, state: FSMContext):
    if cb.data == "top_skip":
        await state.update_data(topping=None)
    else:
        await state.update_data(topping=cb.data[4:])
    await state.set_state(Order.extras)
    kb = InlineKeyboardBuilder()
    for e in category_items("Дополнительные топпинги"):
        kb.button(text=f"➕ {e['name']} — {e['price']} ₽", callback_data=f"xtra_{e['name']}")
    kb.button(text="✅ Готово → Корзина", callback_data="cart")
    kb.button(text="🔙 Назад", callback_data="back_to_protein")
    kb.adjust(1)
    await cb.message.edit_text(
        "🌟 <b>Дополнительные топпинги</b>\n\nПо желанию — можно пропустить:",
        reply_markup=kb.as_markup(),
    )
    await cb.answer()


@router.callback_query(F.data == "back_to_protein")
async def back_to_protein(cb: CallbackQuery, state: FSMContext):
    await state.set_state(Order.protein)
    kb = InlineKeyboardBuilder()
    for p in udon_proteins():
        kb.button(text=f"{p['name']} — {p['price']} ₽", callback_data=f"prot_{p['name']}")
    kb.button(text="🔙 Назад", callback_data="back_to_base")
    kb.adjust(1)
    await cb.message.edit_text("Выберите <b>главный ингредиент</b>:",
                               reply_markup=kb.as_markup())
    await cb.answer()


@router.callback_query(F.data.startswith("xtra_"))
async def add_extra(cb: CallbackQuery, state: FSMContext):
    name = cb.data[5:]
    extras = category_items("Дополнительные топпинги")
    item = next((e for e in extras if e["name"] == name), None)
    if not item:
        await cb.answer("Не нашёл 😔", show_alert=True)
        return
    data = await state.get_data()
    extra_list = data.get("extras", [])
    extra_list.append({"name": item["name"], "price": item["price"]})
    await state.update_data(extras=extra_list)
    await cb.answer(f"✅ {name} добавлен!")


# ============================================================
# Корзина / оформление
# ============================================================
def build_lines(data: dict) -> tuple[list[dict], int]:
    """Собирает позиции заказа из FSM: удон + закуски + напитки + extras."""
    lines: list[dict] = []
    total = 0
    base = data.get("base")
    protein = data.get("protein")
    if base and protein:
        extras = [e["name"] for e in data.get("extras", [])]
        price = data.get("protein_price", 0) + sum(e["price"] for e in data.get("extras", []))
        lines.append({
            "kind": "udon",
            "title": f"Удон: {base} + {protein}",
            "base": base, "protein": protein,
            "topping": data.get("topping"),
            "extras": extras,
            "price": price, "qty": 1,
        })
        total += price
    for it in data.get("cart", []):
        qty = it.get("qty", 1)
        lines.append({"kind": "item", "title": it["name"], "price": it["price"], "qty": qty})
        total += it["price"] * qty
    return lines, total


@router.callback_query(F.data == "cart")
async def show_cart(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lines, total = build_lines(data)
    if not lines:
        await cb.answer("🛒 Корзина пуста!", show_alert=True)
        return
    await state.set_state(Order.cart)
    await state.update_data(lines=lines, total=total)
    text = "🛒 <b>Ваш заказ</b>\n\n" + format_items_text(lines) + f"\n\n💰 <b>Итого: {total} ₽</b>"
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Оформить заказ", callback_data="checkout")
    kb.button(text="➕ Добавить ещё", callback_data="menu_more")
    kb.button(text="🗑 Очистить", callback_data="cart_clear")
    kb.button(text="🏠 В меню", callback_data="back_main")
    kb.adjust(1)
    await cb.message.edit_text(text, reply_markup=kb.as_markup())
    await cb.answer()


@router.callback_query(F.data == "menu_more")
async def menu_more(cb: CallbackQuery, state: FSMContext):
    await cb.message.edit_text("🌸 <b>Что хотите добавить?</b>",
                               reply_markup=menu_categories_kb())
    await cb.answer()


@router.callback_query(F.data == "cart_clear")
async def cart_clear(cb: CallbackQuery, state: FSMContext):
    await state.update_data(cart=[], extras=[], base=None, protein=None, topping=None)
    await cb.answer("🗑 Корзина очищена")
    await cb.message.edit_text("🌸 <b>Корзина очищена</b>.\nНачните заказ заново:",
                               reply_markup=order_type_kb())


@router.callback_query(F.data == "checkout")
async def checkout(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lines, total = build_lines(data)
    if not lines:
        await cb.answer("🛒 Корзина пуста!", show_alert=True)
        return
    otype = data.get("order_type", ORDER_TYPES["dine_in"])
    user = user_exists(cb.from_user.id)
    order_id = core.save_order(
        telegram_id=cb.from_user.id,
        guest_name=user["name"] if user else (cb.from_user.full_name or "Гость"),
        order_type=otype,
        items=lines,
        total=total,
        source="bot",
        comment=None,
    )
    await state.clear()
    # уведомляем админов (и веб, через событие)
    await announce_admins(order_id)
    await cb.message.edit_text(
        f"✅ <b>Заказ #{order_id:04d} оформлен!</b>\n\n"
        f"{format_items_text(lines)}\n\n💰 <b>Итого: {total} ₽</b>\n\n"
        "🔔 Статус будет приходить сюда и на сайт.\n"
        "💳 Можно привязать оплату ЮMoney позже.",
        reply_markup=confirm_order_kb(order_id),
    )
    await cb.answer("Заказ оформлен!")


@router.callback_query(F.data.startswith("pay_"))
async def pay_stub(cb: CallbackQuery):
    """Заглушка ЮMoney: помечаем заказ оплаченным (без реальных денег)."""
    from payments import create_payment, confirm_payment_stub

    order_id = int(cb.data[4:])
    order = get_order(order_id)
    if not order:
        await cb.answer("Заказ не найден", show_alert=True)
        return
    payment = create_payment(order_id, order["total"])
    confirm_payment_stub(order_id, payment["payment_id"])
    await cb.answer("💳 Тестовая оплата прошла (заглушка ЮMoney)", show_alert=True)
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


# ============================================================
# Мои заказы (живые статусы)
# ============================================================
@router.callback_query(F.data == "history")
async def history_cb(cb: CallbackQuery):
    orders = user_orders(cb.from_user.id, limit=10)
    text, kb = _history_view(orders)
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()


@router.message(Command("orders"))
async def history_cmd(message: Message):
    orders = user_orders(message.from_user.id, limit=10)
    text, kb = _history_view(orders)
    await message.answer(text, reply_markup=kb, disable_web_page_preview=True)


def _history_view(orders):
    if not orders:
        text = ("📋 <b>История заказов</b>\n\nПока здесь пусто...\n"
                "🍜 Сделайте свой первый заказ в SANUKI!")
        kb = main_menu_kb()
    else:
        rows = []
        for o in orders:
            st = STATUSES.get(o["status"], STATUSES["new"])
            rows.append(f"{st['bot']} — <b>#{o['public_id']}</b> · {o['total']} ₽ · {o['order_type']}")
        text = ("📋 <b>Мои заказы</b>\n\n" + "\n".join(rows) +
                "\n\nСтатусы обновляются в реальном времени, как на сайте.")
        kb = InlineKeyboardBuilder()
        kb.button(text="🔄 Обновить", callback_data="history")
        kb.button(text="🌐 Открыть на сайте", web_app=WebAppInfo(url=web_app_url()))
        kb.button(text="🏠 В меню", callback_data="back_main")
        kb.adjust(1)
        kb = kb.as_markup()
    return text, kb


@router.message(Command("status"))
async def cmd_status(message: Message):
    """Быстрый просмотр активного заказа."""
    orders = user_orders(message.from_user.id, limit=5)
    active = [o for o in orders if o["status"] in ACTIVE_STATUSES]
    if not active:
        await message.answer("📭 Активных заказов нет.")
        return
    lines = []
    for o in active:
        st = STATUSES[o["status"]]
        lines.append(f"{st['bot']} <b>#{o['public_id']}</b> — {o['total']} ₽")
    await message.answer("🔔 <b>Активные заказы:</b>\n" + "\n".join(lines))


# ============================================================
# Персонал
# ============================================================
@router.callback_query(F.data == "call_staff")
async def call_staff(cb: CallbackQuery):
    await notify_admins(f"🆘 <b>Вызов сотрудника!</b>\n👤 {cb.from_user.full_name} "
                        f"(<a href='tg://user?id={cb.from_user.id}'>{cb.from_user.id}</a>)")
    await cb.message.answer("👩‍🍳 Сотрудник вызван! Сейчас подойдут 🏃")
    await cb.answer("Сотрудник вызван!")


# ============================================================
# Админ: панель и смена статусов
# ============================================================
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён")
        return
    orders = all_orders(list(ACTIVE_STATUSES) + ["new"], limit=10)
    if not orders:
        await message.answer("📭 <b>Активных заказов нет</b>.\n🌸 Все заказы выполнены. Отдыхайте!",
                             reply_markup=admin_root_kb())
        return
    await message.answer(f"🔐 <b>Панель администратора</b>\nАктивных заказов: {len(orders)}",
                         reply_markup=admin_root_kb())
    for o in orders:
        await message.answer(admin_order_text(o), reply_markup=admin_order_kb(o["id"]))


@router.callback_query(F.data == "admin_refresh")
async def admin_refresh(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("⛔ Нет доступа", show_alert=True)
        return
    orders = all_orders(list(ACTIVE_STATUSES) + ["new"], limit=10)
    await cb.message.edit_text(
        f"🔐 <b>Панель администратора</b>\nАктивных заказов: {len(orders)}",
        reply_markup=admin_root_kb(),
    )
    await cb.answer("Обновлено")


def admin_order_text(o) -> str:
    st = STATUSES.get(o["status"], STATUSES["new"])
    items = core.items_of(o)
    src = "🌐 сайт" if o["source"] == "web" else "🤖 бот"
    phone = f"\n📞 {o['phone']}" if o["phone"] else ""
    return (
        f"{st['bot']} <b>Заказ #{o['public_id']}</b> · {src}\n"
        f"👤 {o['guest_name']}{phone}\n"
        f"📦 {o['order_type']}\n\n"
        f"{format_items_text(items)}\n\n"
        f"💰 <b>{o['total']} ₽</b> · {'💳 ЮMoney' if o['pay_method'] == 'yoomoney' else '💵 при получении'}"
    )


@router.callback_query(F.data.startswith("st:"))
async def admin_set_status(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("⛔ Нет доступа", show_alert=True)
        return
    _, oid, status = cb.data.split(":")
    order_id = int(oid)
    if status not in STATUSES:
        await cb.answer("Неизвестный статус", show_alert=True)
        return
    update_status(order_id, status)
    order = get_order(order_id)
    st = STATUSES[status]
    await cb.answer(f"{st['bot']} #{order['public_id']}")

    # Уведомляем клиента (и в боте, и на сайте — сайт слушает SSE)
    await notify_user(order["telegram_id"], status_message(order_id, status))
    # Обновляем сообщение админа
    try:
        await cb.message.edit_text(admin_order_text(order), reply_markup=admin_order_kb(order_id))
    except Exception:
        pass


# ============================================================
# Рассылка админам
# ============================================================
async def notify_admins(text: str, reply_markup=None):
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, reply_markup=reply_markup)
        except Exception as e:
            log.warning("Не удалось написать админу %s: %s", admin_id, e)


async def announce_admins(order_id: int):
    order = get_order(order_id)
    src = "🌐 С САЙТА" if order["source"] == "web" else "🤖 из бота"
    text = (f"🆕 <b>Новый заказ #{order['public_id']}</b> · {src}\n\n"
            f"👤 {order['guest_name']}"
            + (f" · {order['phone']}" if order['phone'] else "")
            + f"\n📦 {order['order_type']}\n\n"
            + format_items_text(core.items_of(order))
            + f"\n\n💰 <b>{order['total']} ₽</b> · "
            + ("💳 ЮMoney" if order["pay_method"] == "yoomoney" else "💵 при получении"))
    await notify_admins(text, admin_order_kb(order_id))


# ============================================================
# Мост: уведомления из веба через ядро
# ============================================================
async def _client_notify(telegram_id: int, text: str):
    await bot.send_message(telegram_id, text)


set_client_notify(_client_notify)


# ============================================================
# Запуск
# ============================================================
async def on_startup():
    init_db()
    set_bot_loop(asyncio.get_running_loop())
    # настройка кнопки меню: веб-приложение
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="SANUKI", web_app=WebAppInfo(url=web_app_url())),
        )
    except Exception as e:
        log.warning("Не удалось установить menu button: %s", e)
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                "🌸 <b>SANUKI BOT запущен!</b>\n"
                "🔗 Связка с веб-приложением активна.\n\n"
                "Команды: /admin — панель, /orders — мои заказы.",
                reply_markup=admin_root_kb(),
            )
        except Exception:
            pass
    log.info("SANUKI BOT запущен")


async def main():
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await on_startup()
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
