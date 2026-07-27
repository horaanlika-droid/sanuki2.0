import json
import aiofiles
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from db import user_exists, add_user, save_order
from keyboards import (
    main_menu_keyboard, order_type_keyboard, base_keyboard,
    protein_keyboard, topping_keyboard, extras_keyboard,
    cart_keyboard, confirm_keyboard, admin_order_keyboard
)
from config import ADMIN_IDS

router = Router()

class Registration(StatesGroup):
    waiting_name = State()

class OrderStates(StatesGroup):
    choosing_order_type = State()
    choosing_base = State()
    choosing_protein = State()
    choosing_topping = State()
    choosing_extras = State()
    viewing_cart = State()
    confirming = State()

# ========== ЗАГРУЗКА МЕНЮ ==========
async def load_menu():
    async with aiofiles.open("menu.json", "r", encoding="utf-8") as f:
        data = json.loads(await f.read())
    return data

# ========== РЕГИСТРАЦИЯ ==========
@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    user = user_exists(message.from_user.id)
    if user:
        await message.answer(
            f"С возвращением, <b>{user['name']}</b>! 👋\n\n"
            "Добро пожаловать в <b>SANUKI UDON SHOP</b>",
            reply_markup=main_menu_keyboard()
        )
        return
    await message.answer(
        "Добро пожаловать в <b>SANUKI UDON SHOP</b> 🍜\n\n"
        "Прежде чем начать, как к вам обращаться?"
    )
    await state.set_state(Registration.waiting_name)

@router.message(Registration.waiting_name)
async def save_name(message: Message, state: FSMContext):
    add_user(
        telegram_id=message.from_user.id,
        name=message.text,
        username=message.from_user.username or ""
    )
    await state.clear()
    await message.answer(
        f"Спасибо, <b>{message.text}</b>! ✅\n\n"
        "Теперь можно сделать заказ:",
        reply_markup=main_menu_keyboard()
    )

# ========== КОМАНДА /menu ==========
@router.message(Command("menu"))
async def show_menu_command(message: Message):
    user = user_exists(message.from_user.id)
    if user:
        await message.answer("Главное меню:", reply_markup=main_menu_keyboard())
    else:
        await message.answer("Сначала пройдите регистрацию через /start")

# ========== ГЛАВНОЕ МЕНЮ ==========
@router.callback_query(F.data == "about")
async def about(callback: CallbackQuery):
    await callback.answer("О нас")
    await callback.message.answer(
        "🍜 <b>SANUKI UDON SHOP</b>\n\n"
        "📍 Санкт-Петербург, Гороховая 34\n"
        "⏰ Ежедневно 11:00 – 23:00\n\n"
        "Мы готовим настоящий удон по японским рецептам.\n"
        "Футуристичная азиатская атмосфера ждёт вас!"
    )

@router.callback_query(F.data == "history")
async def history(callback: CallbackQuery):
    await callback.answer("История заказов")
    await callback.message.answer("📋 Пока заказов нет. Сделайте первый!")

# ========== НАЧАЛО ЗАКАЗА ==========
@router.callback_query(F.data.in_({"dine_in", "takeaway", "delivery"}))
async def start_order(callback: CallbackQuery, state: FSMContext):
    order_type_map = {
        "dine_in": "В кафе",
        "takeaway": "С собой",
        "delivery": "Доставка"
    }
    order_type = order_type_map[callback.data]
    await state.update_data(order_type=order_type, cart=[])
    await state.set_state(OrderStates.choosing_order_type)
    
    await callback.answer(f"Вы выбрали «{order_type}»")
    await callback.message.edit_text(
        f"Вы выбрали: <b>{order_type}</b>\n\n"
        "Теперь выберите основу для удона:",
        reply_markup=await base_keyboard_from_menu()
    )

async def base_keyboard_from_menu():
    menu = await load_menu()
    bases = [item for item in menu["categories"] if item["name"] == "UDON"][0]["bases"]
    return base_keyboard(bases)

# ========== ВЫБОР ОСНОВЫ ==========
@router.callback_query(F.data.startswith("base_"))
async def choose_base(callback: CallbackQuery, state: FSMContext):
    base_name = callback.data.split("_", 1)[1]
    await state.update_data(base=base_name)
    
    menu = await load_menu()
    proteins = [item for item in menu["categories"] if item["name"] == "UDON"][0]["proteins"]
    
    await callback.answer(f"Выбрана основа: {base_name}")
    await callback.message.edit_text(
        f"<b>Основа:</b> {base_name}\n\n"
        "Теперь выберите главный ингредиент:",
        reply_markup=protein_keyboard(proteins, base_name)
    )

# ========== ВЫБОР БЕЛКА ==========
@router.callback_query(F.data.startswith("protein_"))
async def choose_protein(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    base_name = parts[1]
    protein_name = parts[2]
    
    menu = await load_menu()
    proteins = [item for item in menu["categories"] if item["name"] == "UDON"][0]["proteins"]
    protein_price = next(p["price"] for p in proteins if p["name"] == protein_name)
    
    await state.update_data(protein=protein_name, protein_price=protein_price)
    
    toppings = [item for item in menu["categories"] if item["name"] == "UDON"][0]["toppings"]
    
    await callback.answer(f"Выбран белок: {protein_name}")
    await callback.message.edit_text(
        f"<b>Основа:</b> {base_name}\n"
        f"<b>Белок:</b> {protein_name} (+{protein_price} ₽)\n\n"
        "Теперь выберите топпинг (входит в стоимость):",
        reply_markup=topping_keyboard(toppings)
    )

# ========== ВЫБОР ТОППИНГА ==========
@router.callback_query(F.data.startswith("topping_"))
async def choose_topping(callback: CallbackQuery, state: FSMContext):
    topping_name = callback.data.split("_", 1)[1]
    await state.update_data(topping=topping_name)
    
    menu = await load_menu()
    extras = [item for item in menu["categories"] if item["name"] == "Дополнительные топпинги"][0]["items"]
    
    await callback.answer(f"Выбран топпинг: {topping_name}")
    await callback.message.edit_text(
        "Отлично! Теперь можно добавить дополнительные топпинги "
        "(или нажмите «Готово» для перехода к корзине):",
        reply_markup=extras_keyboard(extras)
    )

# ========== ДОПОЛНИТЕЛЬНЫЕ ТОППИНГИ ==========
@router.callback_query(F.data.startswith("extra_"))
async def add_extra(callback: CallbackQuery, state: FSMContext):
    extra_name = callback.data.split("_", 1)[1]
    
    data = await state.get_data()
    cart = data.get("cart", [])
    
    menu = await load_menu()
    extras = [item for item in menu["categories"] if item["name"] == "Дополнительные топпинги"][0]["items"]
    extra_price = next(e["price"] for e in extras if e["name"] == extra_name)
    
    cart.append({"name": extra_name, "price": extra_price, "type": "extra"})
    await state.update_data(cart=cart)
    
    await callback.answer(f"✅ {extra_name} добавлен!")
    # Обновляем сообщение с текущим списком
    extras_text = "\n".join([f"• {e['name']} — {e['price']} ₽" for e in cart if e['type'] == 'extra'])
    await callback.message.edit_text(
        f"Добавлены дополнительные топпинги:\n{extras_text}\n\n"
        "Можно добавить ещё или перейти к корзине:",
        reply_markup=await extras_keyboard_from_menu()
    )

async def extras_keyboard_from_menu():
    menu = await load_menu()
    extras = [item for item in menu["categories"] if item["name"] == "Дополнительные топпинги"][0]["items"]
    return extras_keyboard(extras)

# ========== КОРЗИНА ==========
@router.callback_query(F.data == "go_to_cart")
async def show_cart(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", [])
    base = data.get("base")
    protein = data.get("protein")
    protein_price = data.get("protein_price", 0)
    topping = data.get("topping")
    
    # Собираем заказ
    total = protein_price
    items_text = f"• {base} + {protein}\n  Топпинг: {topping}\n"
    
    for item in cart:
        if item['type'] == 'extra':
            items_text += f"  + {item['name']} — {item['price']} ₽\n"
            total += item['price']
    
    # Сохраняем полный заказ в state
    order_items = [
        {"base": base, "protein": protein, "topping": topping},
        *cart
    ]
    await state.update_data(order_items=order_items, total=total)
    await state.set_state(OrderStates.viewing_cart)
    
    await callback.message.edit_text(
        f"🛒 <b>Ваш заказ</b>\n\n"
        f"{items_text}\n"
        f"<b>Итого:</b> {total} ₽",
        reply_markup=cart_keyboard()
    )

@router.callback_query(F.data == "add_more")
async def add_more(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OrderStates.choosing_base)
    await callback.answer("Добавляем ещё")
    await callback.message.edit_text(
        "Выберите основу для нового блюда:",
        reply_markup=await base_keyboard_from_menu()
    )

@router.callback_query(F.data == "clear_cart")
async def clear_cart(callback: CallbackQuery, state: FSMContext):
    await state.update_data(cart=[])
    await state.set_state(OrderStates.choosing_order_type)
    await callback.answer("Корзина очищена")
    await callback.message.edit_text(
        "Корзина очищена. Начните заказ заново.",
        reply_markup=order_type_keyboard()
    )

@router.callback_query(F.data == "checkout")
async def checkout(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    total = data.get("total", 0)
    order_items = data.get("order_items", [])
    
    await state.set_state(OrderStates.confirming)
    await callback.message.edit_text(
        f"📋 <b>Подтверждение заказа</b>\n\n"
        f"Сумма: {total} ₽\n\n"
        "Всё верно?",
        reply_markup=confirm_keyboard()
    )

@router.callback_query(F.data == "back_to_cart")
async def back_to_cart(callback: CallbackQuery, state: FSMContext):
    await show_cart(callback, state)

@router.callback_query(F.data == "confirm_order")
async def confirm_order(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    order_type = data.get("order_type")
    order_items = data.get("order_items", [])
    total = data.get("total", 0)
    
    user = user_exists(callback.from_user.id)
    order_id = save_order(
        telegram_id=callback.from_user.id,
        guest_name=user["name"],
        order_type=order_type,
        items=order_items,
        total=total
    )
    
    # Отправляем админу
    items_text = "\n".join([f"• {item.get('name', item.get('base', ''))}" for item in order_items])
    admin_text = (
        f"🆕 <b>Новый заказ #{order_id}</b>\n\n"
        f"👤 {user['name']}\n"
        f"📦 {order_type}\n"
        f"📝 {items_text}\n"
        f"💰 {total} ₽"
    )
    
    for admin_id in ADMIN_IDS:
        await callback.bot.send_message(
            admin_id,
            admin_text,
            reply_markup=admin_order_keyboard(order_id)
        )
    
    # Отправляем клиенту
    await callback.message.edit_text(
        f"✅ <b>Заказ #{order_id} оформлен!</b>\n\n"
        f"Статус: <b>Передан кухне</b>\n"
        f"Сумма: {total} ₽\n\n"
        "Мы начнём готовить ваш заказ. Ожидайте уведомлений!",
        reply_markup=main_menu_keyboard()
    )
    await state.clear()

# ========== АДМИН-ПАНЕЛЬ ==========
@router.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Доступ запрещён")
        return
    
    from db import get_connection
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE status IN ('новый', 'принят', 'готовится') ORDER BY created_at DESC")
    orders = cur.fetchall()
    conn.close()
    
    if not orders:
        await message.answer("📭 Активных заказов нет")
        return
    
    for order in orders:
        text = (
            f"🆔 <b>Заказ #{order['id']}</b>\n"
            f"👤 {order['guest_name']}\n"
            f"📦 {order['order_type']}\n"
            f"📊 Статус: {order['status']}\n"
            f"💰 {order['total']} ₽"
        )
        await message.answer(text, reply_markup=admin_order_keyboard(order['id']))

@router.callback_query(F.data.startswith("admin_accept_"))
async def admin_accept(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    await update_order_status(order_id, "принят", callback)
    await callback.answer("Заказ принят")

@router.callback_query(F.data.startswith("admin_cook_"))
async def admin_cook(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    await update_order_status(order_id, "готовится", callback)
    await callback.answer("Заказ готовится")

@router.callback_query(F.data.startswith("admin_ready_"))
async def admin_ready(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    await update_order_status(order_id, "готов", callback)
    await callback.answer("Заказ готов!")

@router.callback_query(F.data.startswith("admin_cancel_"))
async def admin_cancel(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    await update_order_status(order_id, "отменён", callback)
    await callback.answer("Заказ отменён")

async def update_order_status(order_id: int, status: str, callback: CallbackQuery):
    from db import get_connection
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
    conn.commit()
    conn.close()
    
    # Получаем заказ
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE id=?", (order_id,))
    order = cur.fetchone()
    conn.close()
    
    # Отправляем клиенту
    await callback.bot.send_message(
        order["telegram_id"],
        f"🔄 <b>Статус заказа #{order_id} обновлён!</b>\n\n"
        f"Новый статус: <b>{status}</b>"
    )
    
    # Обновляем сообщение админа
    await callback.message.edit_text(
        f"✅ Заказ #{order_id} — {status}",
        reply_markup=None
    )

# ========== НАВИГАЦИЯ НАЗАД ==========
@router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Главное меню")
    await callback.message.edit_text(
        "Главное меню:",
        reply_markup=main_menu_keyboard()
    )

@router.callback_query(F.data == "back_to_order_type")
async def back_to_order_type(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OrderStates.choosing_order_type)
    await callback.answer("Назад")
    await callback.message.edit_text(
        "Выберите тип заказа:",
        reply_markup=order_type_keyboard()
    )

@router.callback_query(F.data == "back_to_bases")
async def back_to_bases(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OrderStates.choosing_base)
    await callback.answer("Назад")
    await callback.message.edit_text(
        "Выберите основу для удона:",
        reply_markup=await base_keyboard_from_menu()
    )

@router.callback_query(F.data == "back_to_proteins")
async def back_to_proteins(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    base_name = data.get("base")
    menu = await load_menu()
    proteins = [item for item in menu["categories"] if item["name"] == "UDON"][0]["proteins"]
    
    await state.set_state(OrderStates.choosing_protein)
    await callback.answer("Назад")
    await callback.message.edit_text(
        f"<b>Основа:</b> {base_name}\n\n"
        "Выберите главный ингредиент:",
        reply_markup=protein_keyboard(proteins, base_name)
    )

@router.callback_query(F.data == "back_to_toppings")
async def back_to_toppings(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OrderStates.choosing_topping)
    await callback.answer("Назад")
    menu = await load_menu()
    toppings = [item for item in menu["categories"] if item["name"] == "UDON"][0]["toppings"]
    await callback.message.edit_text(
        "Выберите топпинг (входит в стоимость):",
        reply_markup=topping_keyboard(toppings)
    )

@router.callback_query(F.data == "back_to_cart_from_confirm")
async def back_to_cart_from_confirm(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OrderStates.viewing_cart)
    await show_cart(callback, state)