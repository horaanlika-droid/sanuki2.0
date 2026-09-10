"""Обратная совместимость: старые модули импортируют db.get_connection / init_db.

Вся реальная логика переехала в core.py (общее ядро бота и веба)."""

from core import (  # noqa: F401
    DB_NAME,
    add_user,
    all_orders,
    get_connection,
    get_order,
    get_order_by_public,
    init_db,
    order_history,
    save_order,
    update_status,
    user_exists,
    user_orders,
)
