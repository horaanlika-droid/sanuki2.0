"""Оплата через ЮMoney.

Сейчас работает ЗАГЛУШКА (YOOMONEY_MODE=stub):
    • платеж создаётся локально, реального списания нет;
    • веб-приложение открывает внутреннюю страницу «оплаты»;
    • после подтверждения статус заказа и оплаты меняются так же,
      как это будет происходить с настоящим webhook'ом ЮMoney.

Когда будете подключать реальную кассу:
    YOOMONEY_MODE=live
    YOOMONEY_API=<токен>
    YOOMONEY_WALLET=<номер кошелька>
    YOOMONEY_SECRET=<secret для проверки уведомлений>
    YOOMONEY_RETURN_URL=https://ваш-домен/
HTTP-вызовы к api.yoomoney.ru уже заготовлены, но в режиме заглушки
не выполняются.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import urllib.parse
from typing import Optional

import config
from core import orders as orders_core

log = logging.getLogger("sanuki.payments")

YOOMONEY_API_URL = "https://yoomoney.ru/api"
QUICKPAY_URL = "https://yoomoney.ru/quickpay/confirm.xml"

PAYMENT_METHODS = {
    "cash": "Наличными при получении 💵",
    "card": "Картой при получении 💳",
    "yoomoney": "ЮMoney онлайн 💜",
}

PAYMENT_STATUSES = {
    "unpaid": "Не оплачен",
    "pending": "Ожидает оплаты",
    "paid": "Оплачен",
    "failed": "Оплата не прошла",
    "refunded": "Возврат",
}


def is_stub() -> bool:
    return config.YOOMONEY_MODE != "live" or not config.YOOMONEY_API


def payment_methods() -> list[dict]:
    return [
        {"code": code, "title": title, "online": code == "yoomoney"}
        for code, title in PAYMENT_METHODS.items()
    ]


def payment_status_title(code: str) -> str:
    return PAYMENT_STATUSES.get(code, code)


# --------------------------------------------------------------------------
# Создание платежа
# --------------------------------------------------------------------------
async def create_payment(order: dict, method: str = "yoomoney") -> dict:
    """Возвращает {'payment_id', 'payment_url', 'stub': bool}."""
    if method != "yoomoney":
        return {
            "payment_id": "",
            "payment_url": "",
            "stub": False,
            "message": "Оплата при получении",
        }

    label = f"sanuki-{order['code']}-{secrets.token_hex(3)}"

    if is_stub():
        payment_id = f"stub-{label}"
        base = config.webapp_url()
        url = f"{base}/#/pay/{order['code']}" if base else f"#/pay/{order['code']}"
        await orders_core.set_payment(order["id"], "pending", payment_id, url)
        return {
            "payment_id": payment_id,
            "payment_url": url,
            "stub": True,
            "label": label,
            "message": "Заглушка ЮMoney: реального списания нет",
        }

    # ---- реальный режим ----
    params = {
        "receiver": config.YOOMONEY_WALLET,
        "quickpay-form": "shop",
        "targets": f"Заказ SANUKI #{order['code']}",
        "sum": f"{int(order['total'])}",
        "paymentType": "AC",
        "label": label,
        "successURL": config.YOOMONEY_RETURN_URL or (config.webapp_url() + f"/#/order/{order['code']}"
                                                     if config.webapp_url() else ""),
    }
    url = f"{QUICKPAY_URL}?{urllib.parse.urlencode(params)}"
    await orders_core.set_payment(order["id"], "pending", label, url)
    return {"payment_id": label, "payment_url": url, "stub": False, "label": label}


async def confirm_stub_payment(code: str) -> dict:
    """Подтвердить оплату в режиме заглушки (кнопка «Я оплатил»)."""
    order = await orders_core.get_order_by_code(code)
    if not order:
        raise ValueError("Заказ не найден")
    await orders_core.set_payment(order["id"], "paid", order.get("payment_id") or "stub",
                                  order.get("payment_url") or "")
    return await orders_core.get_order(order["id"])


# --------------------------------------------------------------------------
# Webhook ЮMoney
# --------------------------------------------------------------------------
def verify_notification(data: dict) -> bool:
    """Проверка подписи уведомления ЮMoney (HTTP-notification)."""
    secret = config.YOOMONEY_SECRET
    if not secret:
        # Без секрета проверять нечего — в боевом режиме обязательно задайте его.
        return config.YOOMONEY_MODE != "live"

    parts = [
        data.get("notification_type", ""),
        data.get("operation_id", ""),
        data.get("amount", ""),
        data.get("currency", ""),
        data.get("datetime", ""),
        data.get("sender", ""),
        data.get("codepro", ""),
        secret,
        data.get("label", ""),
    ]
    expected = hashlib.sha1("&".join(parts).encode("utf-8")).hexdigest()
    received = (data.get("sha1_hash") or "").lower()
    return hmac.compare_digest(expected, received)


async def handle_notification(data: dict) -> dict:
    """Обработка уведомления от ЮMoney (один и тот же путь для stub и live)."""
    if not verify_notification(data):
        raise PermissionError("Неверная подпись уведомления")

    label = (data.get("label") or "").strip()
    code = ""
    if label.startswith("sanuki-"):
        code = label.split("-", 2)[1] if len(label.split("-", 2)) > 1 else ""
    if not code:
        raise ValueError("Не удалось определить заказ")

    order = await orders_core.get_order_by_code(code)
    if not order:
        raise ValueError(f"Заказ {code} не найден")

    if data.get("unaccepted") == "true":
        await orders_core.set_payment(order["id"], "failed", label)
        return await orders_core.get_order(order["id"])

    await orders_core.set_payment(order["id"], "paid", label)
    return await orders_core.get_order(order["id"])


async def operation_details(operation_id: str) -> Optional[dict]:
    """Запрос статуса операции (только для live-режима)."""
    if is_stub():
        return None
    import aiohttp  # импорт здесь, чтобы заглушка не требовала зависимость

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{YOOMONEY_API_URL}/operation-details",
            data={"operation_id": operation_id},
            headers={
                "Authorization": f"Bearer {config.YOOMONEY_API}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=20,
        ) as resp:
            return await resp.json(content_type=None)
