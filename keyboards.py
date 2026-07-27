from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu_keyboard():
    buttons = [
        [InlineKeyboardButton(text="🍽 В кафе", callback_data="dine_in")],
        [InlineKeyboardButton(text="🥡 С собой", callback_data="takeaway")],
        [InlineKeyboardButton(text="🛵 Доставка", callback_data="delivery")],
        [InlineKeyboardButton(text="📋 История заказов", callback_data="history")],
        [InlineKeyboardButton(text="ℹ️ О SANUKI", callback_data="about")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def order_type_keyboard():
    buttons = [
        [InlineKeyboardButton(text="🍽 В кафе", callback_data="order_dine_in")],
        [InlineKeyboardButton(text="🥡 С собой", callback_data="order_takeaway")],
        [InlineKeyboardButton(text="🛵 Доставка", callback_data="order_delivery")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def base_keyboard(bases):
    buttons = []
    for base in bases:
        buttons.append([InlineKeyboardButton(text=base["name"], callback_data=f"base_{base['name']}")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_order_type")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def protein_keyboard(proteins, base_name):
    buttons = []
    for protein in proteins:
        buttons.append([InlineKeyboardButton(text=f"{protein['name']} — {protein['price']} ₽", callback_data=f"protein_{base_name}_{protein['name']}")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_bases")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def topping_keyboard(toppings):
    buttons = []
    for topping in toppings:
        buttons.append([InlineKeyboardButton(text=topping["name"], callback_data=f"topping_{topping['name']}")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_proteins")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def extras_keyboard(extras):
    buttons = []
    for extra in extras:
        buttons.append([InlineKeyboardButton(text=f"{extra['name']} — {extra['price']} ₽", callback_data=f"extra_{extra['name']}")])
    buttons.append([InlineKeyboardButton(text="✅ Готово, перейти к корзине", callback_data="go_to_cart")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_toppings")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def cart_keyboard():
    buttons = [
        [InlineKeyboardButton(text="➕ Добавить ещё", callback_data="add_more")],
        [InlineKeyboardButton(text="🗑 Очистить корзину", callback_data="clear_cart")],
        [InlineKeyboardButton(text="✅ Оформить заказ", callback_data="checkout")],
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def confirm_keyboard():
    buttons = [
        [InlineKeyboardButton(text="✅ Да, подтверждаю", callback_data="confirm_order")],
        [InlineKeyboardButton(text="🔙 Вернуться в корзину", callback_data="back_to_cart")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def admin_order_keyboard(order_id):
    buttons = [
        [InlineKeyboardButton(text="✅ Принять", callback_data=f"admin_accept_{order_id}"),
         InlineKeyboardButton(text="🔪 Готовим", callback_data=f"admin_cook_{order_id}")],
        [InlineKeyboardButton(text="✅ Готов", callback_data=f"admin_ready_{order_id}"),
         InlineKeyboardButton(text="❌ Отменить", callback_data=f"admin_cancel_{order_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)