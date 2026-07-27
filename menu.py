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
    cart_keyboard, confirm_keyboard, admin_order_keyboard,
    call_staff_keyboard, fresh_keyboard, starters_keyboard, drinks_keyboard
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
    choosing_fresh = State()
    choosing_starters = State()
    choosing_drinks = State()

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
            f"🌸 <b>С возвращением, {user['name']}!</b>\n\n"
            "Добро пожаловать в <b>SANUKI UDON SHOP</b>\n"
            "Футуристичный вкус Японии в сердце Петербурга.\n\n"
            "🍜 Что желаете?",
            reply_markup=main_menu_keyboard()
        )
        return
    
    await message.answer(
        "🌸 <b>Добро пожаловать в SANUKI UDON SHOP</b>\n\n"
        "Футуристичный вкус Японии в сердце Петербурга.\n"
        "📍 Гороховая, 34\n\n"
        "✨ Прежде чем начать, представьтесь, пожалуйста:"
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
        f"🌺 <b>Приятно познакомиться, {message.text}!</b>\n\n"
        "Добро пожаловать в мир SANUKI —\n"
        "где традиции встречаются с футуризмом.\n\n"
        "🍜 Выберите действие:",
        reply_markup=main_menu_keyboard()
    )

# ========== КОМАНДА /MENU ==========
@router.message(Command("menu"))
async def show_menu_command(message: Message):
    user = user_exists(message.from_user.id)
    if user:
        await message.answer(
            f"🌸 <b>Главное меню, {user['name']}</b>",
            reply_markup=main_menu_keyboard()
        )
    else:
        await message.answer("Сначала пройдите регистрацию через /start")

# ========== ГЛАВНОЕ МЕНЮ ==========
@router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("🌺 Главное меню")
    user = user_exists(callback.from_user.id)
    await callback.message.edit_text(
        f"🌸 <b>Главное меню, {user['name']}</b>",
        reply_markup=main_menu_keyboard()
    )

# ========== О SANUKI ==========
@router.callback_query(F.data == "about")
async def about(callback: CallbackQuery):
    await callback.answer("🎌 О SANUKI")
    await callback.message.answer(
        "🌸 <b>SANUKI UDON SHOP</b>\n\n"
        "📍 <b>Адрес:</b> Санкт-Петербург, Гороховая 34\n"
        "⏰ <b>Режим работы:</b> Ежедневно 11:00 – 23:00\n\n"
        "🍜 <b>О нас:</b>\n"
        "Мы создаём настоящий удон по японским рецептам,\n"
        "добавляя футуристичный акцент в каждое блюдо.\n\n"
        "✨ <b>Наша философия:</b>\n"
        "Традиции, переосмысленные через призму современности.\n\n"
        "🇯🇵 <b>Добро пожаловать в будущее вкуса!</b>"
    )

# ========== ВЫЗОВ СОТРУДНИКА ==========
@router.callback_query(F.data == "call_staff")
async def call_staff(callback: CallbackQuery):
    await callback.answer("📞 Вызов сотрудника")
    await callback.message.answer(
        "🛎 <b>Чем можем помочь?</b>\n\n"
        "Выберите причину вызова:",
        reply_markup=call_staff_keyboard()
    )

@router.callback_query(F.data == "staff_help")
async def staff_help(callback: CallbackQuery):
    await callback.answer("🆘 Помощь")
    await callback.message.answer(
        "🆘 <b>Сотрудник уже в пути!</b>\n\n"
        "Пожалуйста, подождите минуту.\n"
        "Мы обязательно поможем вам с заказом."
    )

@router.callback_query(F.data == "staff_bill")
async def staff_bill(callback: CallbackQuery):
    await callback.answer("🧾 Счёт")
    await callback.message.answer(
        "🧾 <b>Счёт будет предоставлен</b>\n\n"
        "Сотрудник подойдёт к вам в ближайшее время.\n"
        "Оплата доступна наличными и картой."
    )

# ========== ИСТОРИЯ ЗАКАЗОВ ==========
@router.callback_query(F.data == "history")
async def history(callback: CallbackQuery):
    await callback.answer("📋 История заказов")
    await callback.message.answer(
        "📋 <b>История заказов</b>\n\n"
        "Пока здесь пусто...\n"
        "🍜 Сделайте свой первый заказ в SANUKI!"
    )

# ========== ПОКАЗ КАТЕГОРИЙ МЕНЮ ==========
@router.callback_query(F.data == "show_menu")
async def show_menu_categories(callback: CallbackQuery):
    await callback.answer("📋 Меню")
    await callback.message.answer(
        "🌸 <b>Наше меню</b>\n\n"
        "Выберите категорию:",
        reply_markup=menu_categories_keyboard()
    )

# ========== FRESH ==========
@router.callback_query(F.data == "category_fresh")
async def show_fresh(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OrderStates.choosing_fresh)
    menu = await load_menu()
    fresh_items = [item for item in menu["categories"] if item["name"] == "FRESH"][0]["items"]
    
    await callback.answer("🥗 FRESH")
    await callback.message.edit_text(
        "🥗 <b>FRESH</b>\n\n"
        "Свежие и лёгкие закуски:",
        reply_markup=fresh_keyboard(fresh_items)
    )

@router.callback_query(F.data.startswith("fresh_"))
async def add_fresh_to_cart(callback: CallbackQuery, state: FSMContext):
    item_name = callback.data.split("_", 1)[1]
    menu = await load_menu()
    fresh_items = [item for item in menu["categories"] if item["name"] == "FRESH"][0]["items"]
    item = next(i for i in fresh_items if i["name"] == item_name)
    
    data = await state.get_data()
    cart = data.get("cart", [])
    cart.append({"name": item["name"], "price": item["price"], "type": "fresh"})
    await state.update_data(cart=cart)
    
    await callback.answer(f"✅ {item_name} добавлен!")
    
    # Показываем обновлённый список FRESH
    await callback.message.edit_text(
        f"✅ <b>{item_name}</b> добавлен в корзину!\n\n"
        "Можно выбрать ещё или перейти в корзину:",
        reply_markup=fresh_keyboard_with_cart(fresh_items)
    )

# ========== STARTERS ==========
@router.callback_query(F.data == "category_starters")
async def show_starters(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OrderStates.choosing_starters)
    menu = await load_menu()
    starters_items = [item for item in menu["categories"] if item["name"] == "STARTERS"][0]["items"]
    
    await callback.answer("🍗 STARTERS")
    await callback.message.edit_text(
        "🍗 <b>STARTERS</b>\n\n"
        "Горячие закуски к вашему удону:",
        reply_markup=starters_keyboard(starters_items)
    )

@router.callback_query(F.data.startswith("starters_"))
async def add_starters_to_cart(callback: CallbackQuery, state: FSMContext):
    item_name = callback.data.split("_", 1)[1]
    menu = await load_menu()
    starters_items = [item for item in menu["categories"] if item["name"] == "STARTERS"][0]["items"]
    item = next(i for i in starters_items if i["name"] == item_name)
    
    data = await state.get_data()
    cart = data.get("cart", [])
    cart.append({"name": item["name"], "price": item["price"], "type": "starters"})
    await state.update_data(cart=cart)
    
    await callback.answer(f"✅ {item_name} добавлен!")
    
    await callback.message.edit_text(
        f"✅ <b>{item_name}</b> добавлен в корзину!\n\n"
        "Можно выбрать ещё или перейти в корзину:",
        reply_markup=starters_keyboard(starters_items)
    )

# ========== НАПИТКИ ==========
@router.callback_query(F.data == "category_drinks")
async def show_drinks(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OrderStates.choosing_drinks)
    menu = await load_menu()
    drinks_items = [item for item in menu["categories"] if item["name"] == "Напитки"][0]["items"]
    
    await callback.answer("🥤 Напитки")
    await callback.message.edit_text(
        "🥤 <b>Напитки</b>\n\n"
        "Освежающие напитки к вашему заказу:",
        reply_markup=drinks_keyboard(drinks_items)
    )

@router.callback_query(F.data.startswith("drink_"))
async def add_drink_to_cart(callback: CallbackQuery, state: FSMContext):
    item_name = callback.data.split("_", 1)[1]
    menu = await load_menu()
    drinks_items = [item for item in menu["categories"] if item["name"] == "Напитки"][0]["items"]
    item = next(i for i in drinks_items if i["name"] == item_name)
    
    data = await state.get_data()
    cart = data.get("cart", [])
    cart.append({"name": item["name"], "price": item["price"], "type": "drink"})
    await state.update_data(cart=cart)
    
    await callback.answer(f"✅ {item_name} добавлен!")
    
    await callback.message.edit_text(
        f"✅ <b>{item_name}</b> добавлен в корзину!\n\n"
        "Можно выбрать ещё или перейти в корзину:",
        reply_markup=drinks_keyboard(drinks_items)
    )

# ========== НАЧАЛО ЗАКАЗА UDON ==========
@router.callback_query(F.data == "start_order")
async def start_order_menu(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OrderStates.choosing_order_type)
    await callback.answer("🍽 Создаём заказ")
    await callback.message.edit_text(
        "🌸 <b>Создание заказа</b>\n\n"
        "Где вы планируете насладиться удоном?",
        reply_markup=order_type_keyboard()
    )

@router.callback_query(F.data.in_({"dine_in", "takeaway", "delivery"}))
async def choose_order_type(callback: CallbackQuery, state: FSMContext):
    order_type_map = {
        "dine_in": "В кафе 🍽",
        "takeaway": "С собой 🥡",
        "delivery": "Доставка 🛵"
    }
    order_type = order_type_map[callback.data]
    await state.update_data(order_type=order_type, cart=[])
    await state.set_state(OrderStates.choosing_base)
    
    await callback.answer(f"✅ {order_type}")
    menu = await load_menu()
    bases = [item for item in menu["categories"] if item["name"] == "UDON"][0]["bases"]
    
    await callback.message.edit_text(
        f"🌸 <b>Вы выбрали: {order_type}</b>\n\n"
        "Теперь выберите <b>основу</b> для вашего удона:\n"
        "👇 Каждый вариант — это уникальный вкус.",
        reply_markup=base_keyboard(bases)
    )

# ========== ВЫБОР ОСНОВЫ ==========
@router.callback_query(F.data.startswith("base_"))
async def choose_base(callback: CallbackQuery, state: FSMContext):
    base_name = callback.data.split("_", 1)[1]
    await state.update_data(base=base_name)
    
    menu = await load_menu()
    proteins = [item for item in menu["categories"] if item["name"] == "UDON"][0]["proteins"]
    
    bases = [item for item in menu["categories"] if item["name"] == "UDON"][0]["bases"]
    base_description = next(b["description"] for b in bases if b["name"] == base_name)
    
    await callback.answer(f"✅ {base_name}")
    await callback.message.edit_text(
        f"🌸 <b>Основа:</b> {base_name}\n"
        f"📖 {base_description}\n\n"
        "Теперь выберите <b>главный ингредиент</b>:\n"
        "👇 Каждый добавляет уникальный характер блюду.",
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
    
    await callback.answer(f"✅ {protein_name}")
    await callback.message.edit_text(
        f"🌸 <b>Ваш выбор:</b>\n"
        f"Основа: {base_name}\n"
        f"Главный ингредиент: {protein_name} (+{protein_price} ₽)\n\n"
        "Теперь выберите <b>топпинг</b>:\n"
        "🌿 Это <b>бесплатно</b> и входит в стоимость!",
        reply_markup=topping_keyboard(toppings)
    )

# ========== ПРОПУСК ТОППИНГА ==========
@router.callback_query(F.data == "skip_topping")
async def skip_topping(callback: CallbackQuery, state: FSMContext):
    await state.update_data(topping="Без топпинга")
    menu = await load_menu()
    extras = [item for item in menu["categories"] if item["name"] == "Дополнительные топпинги"][0]["items"]
    
    await callback.answer("⏭ Топпинг пропущен")
    await callback.message.edit_text(
        "🌿 <b>Топпинг пропущен</b>\n\n"
        "Хотите добавить дополнительные ингредиенты?\n"
        "👇 Это по вашему желанию.",
        reply_markup=extras_keyboard(extras)
    )

# ========== ВЫБОР ТОППИНГА ==========
@router.callback_query(F.data.startswith("topping_"))
async def choose_topping(callback: CallbackQuery, state: FSMContext):
    topping_name = callback.data.split("_", 1)[1]
    await state.update_data(topping=topping_name)
    
    menu = await load_menu()
    extras = [item for item in menu["categories"] if item["name"] == "Дополнительные топпинги"][0]["items"]
    
    await callback.answer(f"✅ {topping_name}")
    await callback.message.edit_text(
        f"🌸 <b>Топпинг:</b> {topping_name} ✅\n\n"
        "Хотите добавить дополнительные ингредиенты?\n"
        "👇 Это по вашему желанию.",
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
    
    extras_text = "\n".join([f"  🌟 {e['name']} — {e['price']} ₽" for e in cart if e['type'] == 'extra'])
    menu = await load_menu()
    extras_list = [item for item in menu["categories"] if item["name"] == "Дополнительные топпинги"][0]["items"]
    
    await callback.message.edit_text(
        f"🌸 <b>Дополнительные топпинги:</b>\n"
        f"{extras_text if extras_text else 'Пока ничего не добавлено'}\n\n"
        "Можно добавить ещё или перейти к корзине:",
        reply_markup=extras_keyboard(extras_list)
    )

# ========== КОРЗИНА ==========
@router.callback_query(F.data == "go_to_cart")
async def show_cart(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", [])
    base = data.get("base")
    protein = data.get("protein")
    protein_price = data.get("protein_price", 0)
    topping = data.get("topping", "Без топпинга")
    
    total = protein_price
    items_text = ""
    
    # Добавляем UDON, если он есть
    if base and protein:
        items_text += f"🍜 {base} + {protein}\n  🌿 Топпинг: {topping}\n"
    else:
        # Если только закуски/напитки
        pass
    
    # Добавляем все остальные позиции
    for item in cart:
        if item['type'] == 'extra':
            items_text += f"  🌟 {item['name']} — {item['price']} ₽\n"
            total += item['price']
        elif item['type'] in ['fresh', 'starters', 'drink']:
            items_text += f"  {item['name']} — {item['price']} ₽\n"
            total += item['price']
    
    # Если корзина пуста
    if not items_text and total == 0:
        await callback.answer("🛒 Корзина пуста!")
        await callback.message.edit_text(
            "🛒 <b>Корзина пуста</b>\n\n"
            "Добавьте что-нибудь из меню!",
            reply_markup=cart_keyboard()
        )
        return
    
    order_items = []
    if base and protein:
        order_items.append({"base": base, "protein": protein, "topping": topping})
    order_items.extend(cart)
    
    await state.update_data(order_items=order_items, total=total)
    await state.set_state(OrderStates.viewing_cart)
    
    await callback.message.edit_text(
        f"🛒 <b>Ваш заказ</b>\n\n"
        f"{items_text}\n"
        f"💰 <b>Итого:</b> {total} ₽",
        reply_markup=cart_keyboard()
    )

@router.callback_query(F.data == "add_more")
async def add_more(callback: CallbackQuery, state: FSMContext):
    await callback.answer("➕ Добавляем ещё")
    await callback.message.edit_text(
        "🌸 <b>Что хотите добавить?</b>\n\n"
        "Выберите категорию:",
        reply_markup=menu_categories_keyboard()
    )

@router.callback_query(F.data == "clear_cart")
async def clear_cart(callback: CallbackQuery, state: FSMContext):
    await state.update_data(cart=[])
    await state.set_state(OrderStates.choosing_order_type)
    await callback.answer("🗑 Корзина очищена")
    await callback.message.edit_text(
        "🌸 <b>Корзина очищена</b>\n\n"
        "Начните заказ заново:",
        reply_markup=order_type_keyboard()
    )

@router.callback_query(F.data == "checkout")
async def checkout(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    total = data.get("total", 0)
    
    if total == 0:
        await callback.answer("🛒 Корзина пуста!")
        return
    
    await state.set_state(OrderStates.confirming)
    await callback.message.edit_text(
        f"📋 <b>Подтверждение заказа</b>\n\n"
        f"💰 Сумма: {total} ₽\n\n"
        "🌸 Всё верно?",
        reply_markup=confirm_keyboard()
    )

@router.callback_query(F.data == "back_to_cart")
async def back_to_cart(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OrderStates.viewing_cart)
    await show_cart(callback, state)

# ========== ПОДТВЕРЖДЕНИЕ ЗАКАЗА ==========
@router.callback_query(F.data == "confirm_order")
async def confirm_order(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    order_type = data.get("order_type", "Не указан")
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
    
    # Формируем красивый текст заказа
    items_text = "\n".join([
        f"  • {item.get('name', item.get('base', ''))}" 
        for item in order_items
    ])
    
    admin_text = (
        f"🆕 <b>Новый заказ #{order_id}</b>\n\n"
        f"👤 {user['name']}\n"
        f"📦 {order_type}\n"
        f"📝 Состав:\n{items_text}\n"
        f"💰 {total} ₽"
    )
    
    for admin_id in ADMIN_IDS:
        await callback.bot.send_message(
            admin_id,
            admin_text,
            reply_markup=admin_order_keyboard(order_id)
        )
    
    await callback.message.edit_text(
        f"✅ <b>Заказ #{order_id} оформлен!</b>\n\n"
        f"🌸 Статус: <b>Передан кухне</b>\n"
        f"💰 Сумма: {total} ₽\n\n"
        "🍜 Мы начинаем готовить ваш заказ.\n"
        "Ожидайте уведомлений о статусе!\n\n"
        "✨ Спасибо, что выбрали SANUKI!",
        reply_markup=main_menu_keyboard()
    )
    await state.finish()

# ========== АДМИН-ПАНЕЛЬ ==========
@router.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ <b>Доступ запрещён</b>")
        return
    
    from db import get_connection
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE status IN ('новый', 'принят', 'готовится') ORDER BY created_at DESC")
    orders = cur.fetchall()
    conn.close()
    
    if not orders:
        await message.answer(
            "📭 <b>Активных заказов нет</b>\n\n"
            "🌸 Все заказы выполнены. Отдыхайте!"
        )
        return
    
    for order in orders:
        status_emoji = {
            "новый": "🆕",
            "принят": "✅",
            "готовится": "🔪",
            "готов": "🍜",
            "отменён": "❌"
        }.get(order["status"], "📦")
        
        text = (
            f"{status_emoji} <b>Заказ #{order['id']}</b>\n"
            f"👤 {order['guest_name']}\n"
            f"📦 {order['order_type']}\n"
            f"📊 Статус: <b>{order['status']}</b>\n"
            f"💰 {order['total']} ₽"
        )
        await message.answer(text, reply_markup=admin_order_keyboard(order['id']))

# ========== ОБРАБОТЧИКИ АДМИНА ==========
@router.callback_query(F.data.startswith("admin_accept_"))
async def admin_accept(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    await update_order_status(order_id, "принят", "✅ Заказ принят", callback)
    await callback.answer("✅ Заказ принят")

@router.callback_query(F.data.startswith("admin_cook_"))
async def admin_cook(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    await update_order_status(order_id, "готовится", "🔪 Начинаем готовить", callback)
    await callback.answer("🔪 Заказ готовится")

@router.callback_query(F.data.startswith("admin_ready_"))
async def admin_ready(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    await update_order_status(order_id, "готов", "🍜 Заказ готов!", callback)
    await callback.answer("🍜 Заказ готов!")

@router.callback_query(F.data.startswith("admin_cancel_"))
async def admin_cancel(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    await update_order_status(order_id, "отменён", "❌ Заказ отменён", callback)
    await callback.answer("❌ Заказ отменён")

async def update_order_status(order_id: int, status: str, admin_message: str, callback: CallbackQuery):
    from db import get_connection
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
    conn.commit()
    conn.close()
    
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE id=?", (order_id,))
    order = cur.fetchone()
    conn.close()
    
    status_messages = {
        "принят": "✅ Заказ <b>принят</b>! Начинаем готовить! 🔪",
        "готовится": "🔪 Заказ <b>готовится</b>! Ожидайте 10-15 минут ⏰",
        "готов": "🍜 <b>Заказ готов!</b>\n\n"
                 "🌸 Если вы в кафе — скоро принесут.\n"
                 "🥡 Если с собой — можете забирать.\n"
                 "🛵 Если доставка — передаём курьеру.",
        "отменён": "❌ Заказ <b>отменён</b>. Приносим извинения."
    }
    
    status_text = status_messages.get(status, f"🔄 Статус заказа обновлён: <b>{status}</b>")
    
    await callback.bot.send_message(
        order["telegram_id"],
        f"🌸 <b>Заказ #{order_id}</b>\n\n{status_text}"
    )
    
    await callback.message.edit_text(
        f"✅ Заказ #{order_id} — {status}",
        reply_markup=None
    )

# ========== ВСПОМОГАТЕЛЬНЫЕ КЛАВИАТУРЫ ==========
def menu_categories_keyboard():
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = [
        [InlineKeyboardButton(text="🍜 Собрать удон", callback_data="start_order")],
        [InlineKeyboardButton(text="🥗 FRESH", callback_data="category_fresh")],
        [InlineKeyboardButton(text="🍗 STARTERS", callback_data="category_starters")],
        [InlineKeyboardButton(text="🥤 Напитки", callback_data="category_drinks")],
        [InlineKeyboardButton(text="🛒 Корзина", callback_data="go_to_cart")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def fresh_keyboard(items):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = []
    for item in items:
        buttons.append([InlineKeyboardButton(
            text=f"{item['name']} — {item['price']} ₽",
            callback_data=f"fresh_{item['name']}"
        )])
    buttons.append([InlineKeyboardButton(text="🛒 Перейти в корзину", callback_data="go_to_cart")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="show_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def starters_keyboard(items):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = []
    for item in items:
        buttons.append([InlineKeyboardButton(
            text=f"{item['name']} — {item['price']} ₽",
            callback_data=f"starters_{item['name']}"
        )])
    buttons.append([InlineKeyboardButton(text="🛒 Перейти в корзину", callback_data="go_to_cart")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="show_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def drinks_keyboard(items):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = []
    for item in items:
        buttons.append([InlineKeyboardButton(
            text=f"{item['name']} — {item['price']} ₽",
            callback_data=f"drink_{item['name']}"
        )])
    buttons.append([InlineKeyboardButton(text="🛒 Перейти в корзину", callback_data="go_to_cart")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="show_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def fresh_keyboard_with_cart(items):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = []
    for item in items:
        buttons.append([InlineKeyboardButton(
            text=f"{item['name']} — {item['price']} ₽",
            callback_data=f"fresh_{item['name']}"
        )])
    buttons.append([InlineKeyboardButton(text="🛒 Перейти в корзину", callback_data="go_to_cart")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="show_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)