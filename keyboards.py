from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu_keyboard():
    """Главное меню в стиле SANUKI"""
    buttons = [
        [InlineKeyboardButton(text="🍽 Сделать заказ", callback_data="start_order")],
        [InlineKeyboardButton(text="📋 Мои заказы", callback_data="history")],
        [InlineKeyboardButton(text="🎌 О SANUKI", callback_data="about")],
        [InlineKeyboardButton(text="📞 Позвать сотрудника", callback_data="call_staff")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def order_type_keyboard():
    """Выбор типа заказа"""
    buttons = [
        [InlineKeyboardButton(text="🍽 В кафе", callback_data="dine_in")],
        [InlineKeyboardButton(text="🥡 С собой", callback_data="takeaway")],
        [InlineKeyboardButton(text="🛵 Доставка", callback_data="delivery")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def base_keyboard(bases):
    """Выбор основы удона"""
    buttons = []
    for base in bases:
        # Добавляем эмодзи для разных основ
        emoji_map = {
            "Говяжий бульон": "🥩",
            "Цую бульон": "🍜",
            "Соус карри": "🍛",
            "Сырный соус": "🧀"
        }
        emoji = emoji_map.get(base["name"], "🍽")
        buttons.append([InlineKeyboardButton(
            text=f"{emoji} {base['name']}",
            callback_data=f"base_{base['name']}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_order_type")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def protein_keyboard(proteins, base_name):
    """Выбор белка"""
    buttons = []
    for protein in proteins:
        emoji_map = {
            "криспи курица": "🍗",
            "креветки темпура": "🦐",
            "томлёная говядина": "🥩",
            "хрустящий бекон": "🥓",
            "томлёная курица": "🍗"
        }
        emoji = emoji_map.get(protein["name"], "🍖")
        buttons.append([InlineKeyboardButton(
            text=f"{emoji} {protein['name']} — {protein['price']} ₽",
            callback_data=f"protein_{base_name}_{protein['name']}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_bases")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def topping_keyboard(toppings):
    """Выбор топпинга (бесплатный)"""
    buttons = []
    for topping in toppings:
        emoji_map = {
            "Овощи темпура": "🥬",
            "Вешенки темпура": "🍄",
            "Тофу темпура": "🧈"
        }
        emoji = emoji_map.get(topping["name"], "🌿")
        buttons.append([InlineKeyboardButton(
            text=f"{emoji} {topping['name']} ✅",
            callback_data=f"topping_{topping['name']}"
        )])
    buttons.append([InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_topping")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_proteins")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def extras_keyboard(extras):
    """Дополнительные топпинги"""
    buttons = []
    for extra in extras:
        emoji_map = {
            "Яйцо маринованное": "🥚",
            "Яйцо термальное": "🥚",
            "Крабовая палка": "🦀"
        }
        emoji = emoji_map.get(extra["name"], "➕")
        buttons.append([InlineKeyboardButton(
            text=f"{emoji} {extra['name']} — {extra['price']} ₽",
            callback_data=f"extra_{extra['name']}"
        )])
    buttons.append([InlineKeyboardButton(text="✅ Готово → Корзина", callback_data="go_to_cart")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_toppings")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def cart_keyboard():
    """Корзина"""
    buttons = [
        [InlineKeyboardButton(text="➕ Добавить ещё", callback_data="add_more")],
        [InlineKeyboardButton(text="🗑 Очистить", callback_data="clear_cart")],
        [InlineKeyboardButton(text="✅ Оформить заказ", callback_data="checkout")],
        [InlineKeyboardButton(text="🏠 В меню", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def confirm_keyboard():
    """Подтверждение заказа"""
    buttons = [
        [InlineKeyboardButton(text="✅ Да, всё верно", callback_data="confirm_order")],
        [InlineKeyboardButton(text="🔙 Вернуться", callback_data="back_to_cart")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def admin_order_keyboard(order_id):
    """Админ-панель для заказа"""
    buttons = [
        [InlineKeyboardButton(text="✅ Принять", callback_data=f"admin_accept_{order_id}"),
         InlineKeyboardButton(text="🔪 Готовим", callback_data=f"admin_cook_{order_id}")],
        [InlineKeyboardButton(text="✅ Готово", callback_data=f"admin_ready_{order_id}"),
         InlineKeyboardButton(text="❌ Отменить", callback_data=f"admin_cancel_{order_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def call_staff_keyboard():
    """Вызов сотрудника"""
    buttons = [
        [InlineKeyboardButton(text="🆘 Нужна помощь", callback_data="staff_help")],
        [InlineKeyboardButton(text="🧾 Счёт", callback_data="staff_bill")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)