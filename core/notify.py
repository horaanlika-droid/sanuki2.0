"""Шина событий между ядром, ботом и веб-приложением.

Ядро (core.orders) ничего не знает про aiogram — оно просто публикует
события. Бот подписывается на них и отправляет уведомления в Telegram.
Так статусы всегда синхронны в обеих сторонах.
"""

import asyncio
import logging
from typing import Awaitable, Callable

log = logging.getLogger("sanuki.notify")

Subscriber = Callable[[str, dict], Awaitable[None]]

_subscribers: list[Subscriber] = []


def subscribe(fn: Subscriber) -> None:
    _subscribers.append(fn)


def unsubscribe(fn: Subscriber) -> None:
    if fn in _subscribers:
        _subscribers.remove(fn)


async def emit(event: str, payload: dict) -> None:
    """event: 'order_created' | 'order_status_changed' | 'staff_call' | 'payment'."""
    for fn in list(_subscribers):
        try:
            await fn(event, payload)
        except Exception:  # pragma: no cover - уведомление не должно ронять заказ
            log.exception("Ошибка в подписчике события %s", event)
