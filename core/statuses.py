"""Единые статусы заказа.

Один и тот же набор используется и в Telegram-боте, и в веб-приложении,
и в админ-панели, поэтому статусы всегда отображаются одинаково.
"""

from typing import Optional

# код -> (название, эмодзи, описание для клиента)
STATUSES: dict[str, tuple[str, str, str]] = {
    "new": (
        "Новый",
        "🆕",
        "Заказ получен, ждёт подтверждения",
    ),
    "accepted": (
        "Принят",
        "✅",
        "Заказ принят, скоро начнём готовить",
    ),
    "cooking": (
        "Готовится",
        "🔪",
        "Ваш удон уже на плите",
    ),
    "ready": (
        "Готов",
        "🍜",
        "Заказ готов — можно забирать",
    ),
    "on_the_way": (
        "В пути",
        "🛵",
        "Курьер уже везёт заказ",
    ),
    "completed": (
        "Выдан",
        "🎉",
        "Заказ получен. Спасибо, что выбрали SANUKI!",
    ),
    "cancelled": (
        "Отменён",
        "❌",
        "Заказ отменён",
    ),
}

# Порядок для таймлайна «История статусов».
STATUS_ORDER: list[str] = [
    "new",
    "accepted",
    "cooking",
    "ready",
    "on_the_way",
    "completed",
]

# Порядок для обычного (не доставка) заказа.
STATUS_ORDER_DINE_IN: list[str] = [
    "new",
    "accepted",
    "cooking",
    "ready",
    "completed",
]

ACTIVE_STATUSES: list[str] = ["new", "accepted", "cooking", "ready", "on_the_way"]

FINAL_STATUSES: list[str] = ["completed", "cancelled"]

# Разрешённые переходы: текущий статус -> список статусов, в которые можно
# перевести заказ. Пустой список — статус финальный.
ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    "new": ["accepted", "cooking", "cancelled"],
    "accepted": ["cooking", "cancelled"],
    "cooking": ["ready", "cancelled"],
    "ready": ["on_the_way", "completed", "cancelled"],
    "on_the_way": ["completed", "cancelled"],
    "completed": [],
    "cancelled": [],
}

# Кнопки, которые видит администратор.
ADMIN_ACTIONS: dict[str, str] = {
    "accepted": "✅ Принять",
    "cooking": "🔪 Готовить",
    "ready": "🍜 Готово",
    "on_the_way": "🛵 В пути",
    "completed": "🎉 Выдан",
    "cancelled": "❌ Отменить",
}


def status_title(status: str) -> str:
    return STATUSES.get(status, (status, "📦", ""))[0]


def status_emoji(status: str) -> str:
    return STATUSES.get(status, ("", "📦", ""))[1]


def status_description(status: str) -> str:
    return STATUSES.get(status, ("", "📦", ""))[2]


def status_label(status: str) -> str:
    """«🆕 Новый» — используется и в боте, и в вебе."""
    return f"{status_emoji(status)} {status_title(status)}"


def status_payload() -> list[dict]:
    return [
        {
            "code": code,
            "title": title,
            "emoji": emoji,
            "description": description,
            "final": code in FINAL_STATUSES,
        }
        for code, (title, emoji, description) in STATUSES.items()
    ]


def timeline_for(order_type: str) -> list[str]:
    """Какую цепочку статусов показывать клиенту."""
    if (order_type or "").lower() in ("delivery", "доставка", "🛵 доставка"):
        return list(STATUS_ORDER)
    return list(STATUS_ORDER_DINE_IN)


def is_delivery(order_type: str) -> bool:
    return (order_type or "").lower() in ("delivery", "доставка", "🛵 доставка")


def can_transit(current: str, new: str) -> bool:
    """Можно ли перевести заказ из current в new."""
    if current == new:
        return False
    return new in ALLOWED_TRANSITIONS.get(current, [])


def next_statuses(current: str, order_type: str = "") -> list[str]:
    """Статусы, в которые можно перевести заказ прямо сейчас.

    «В пути» предлагаем только для доставки, остальные — по общему графу.
    """
    result = []
    for code in ALLOWED_TRANSITIONS.get(current, []):
        if code == "on_the_way" and not is_delivery(order_type):
            continue
        result.append(code)
    return result
