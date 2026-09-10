"""
ЮMoney — ЗАГЛУШКА.

Реальная интеграция будет позже. Сейчас модуль эмулирует создание платежа
и подтверждение: заказ помечается как оплаченный «тестово», деньги не
списываются. Интерфейс модуля не изменится, когда подключим настоящую API.
"""
import secrets
import time

from core import get_connection, get_order, update_status, publish

# Признак того, что модуль — заглушка (веб показывает бейдж «тестовый платёж»)
IS_STUB = True

# То, что вернёт API ЮMoney в будущем; сейчас — фейковое поле
FAKE_CONFIRM_URL = "https://yoomoney.ru/checkout/pay?stub=1"


def create_payment(order_id: int, amount: int, purpose: str = "Заказ SANUKI") -> dict:
    """Создаёт «платёж». В реальности здесь будет вызов API ЮMoney."""
    payment_id = f"stub-{int(time.time())}-{secrets.token_hex(4)}"
    return {
        "payment_id": payment_id,
        "amount": amount,
        "purpose": purpose,
        "status": "pending",
        "confirmation_url": FAKE_CONFIRM_URL,
        "stub": True,
    }


def confirm_payment_stub(order_id: int, payment_id: str) -> dict:
    """Подтверждает заглушку: помечаем заказ как оплаченный (локально)."""
    order = get_order(order_id)
    if not order:
        return {"ok": False, "error": "order_not_found"}

    conn = get_connection()
    conn.execute(
        "UPDATE orders SET pay_method='yoomoney', payment_id=? WHERE id=?",
        (payment_id, order_id),
    )
    conn.commit()

    if order["status"] == "new":
        update_status(order_id, "accepted")

    publish({"type": "payment_stub_confirmed", "order_id": order_id,
             "payment_id": payment_id})
    return {"ok": True, "order_id": order_id, "payment_id": payment_id, "stub": True}
