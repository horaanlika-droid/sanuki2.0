"""Каталог блюд.

menu.json — единственный источник правды: из него меню читают и бот,
и веб-приложение. Модуль приводит JSON к нормальной форме и умеет
собирать удон (основа + белок + топпинг + допы) с подсчётом цены.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
MENU_PATH = BASE_DIR / "menu.json"
SETTINGS_PATH = BASE_DIR / "setting.json"

ORDER_TYPES = {
    "dine_in": "В кафе 🍽",
    "takeaway": "С собой 🥡",
    "delivery": "Доставка 🛵",
}

EMOJI_BY_CATEGORY = {
    "FRESH": "🥗",
    "STARTERS": "🍗",
    "UDON": "🍜",
    "Дополнительные топпинги": "➕",
    "Напитки": "🥤",
}

PROTEIN_EMOJI = {
    "криспи курица": "🍗",
    "креветки темпура": "🦐",
    "томлёная говядина": "🥩",
    "хрустящий бекон": "🥓",
    "томлёная курица": "🍗",
}

BASE_EMOJI = {
    "Говяжий бульон": "🥩",
    "Цую бульон": "🍜",
    "Соус карри": "🍛",
    "Сырный соус": "🧀",
}

TOPPING_EMOJI = {
    "Овощи темпура": "🥬",
    "Вешенки темпура": "🍄",
    "Тофу темпура": "🧈",
}

EXTRA_EMOJI = {
    "Яйцо маринованное": "🥚",
    "Яйцо термальное": "🥚",
    "Крабовая палка": "🦀",
}

DEFAULT_SETTINGS = {
    "work_hours": "11:00 - 23:00",
    "phone": "+7 (XXX) XXX-XX-XX",
    "address": "Санкт-Петербург, Гороховая 34",
}


def _read_json(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def load_raw_menu() -> dict:
    return _read_json(MENU_PATH)


def load_settings() -> dict:
    data = DEFAULT_SETTINGS.copy()
    data.update(_read_json(SETTINGS_PATH) or {})
    return data


def _find_category(menu: dict, name: str) -> dict:
    for cat in menu.get("categories", []):
        if cat.get("name") == name:
            return cat
    return {}


def _is_stopped(name: str, stop_list: Iterable[str]) -> bool:
    return (name or "").strip().lower() in {s.strip().lower() for s in stop_list}


def get_catalog(stop_list: Optional[Iterable[str]] = None) -> dict:
    """Нормализованный каталог для API, веба и бота."""
    menu = load_raw_menu()
    stop = list(stop_list or [])

    categories: list[dict] = []
    udon: dict = {"bases": [], "proteins": [], "toppings": []}

    for cat in menu.get("categories", []):
        name = cat.get("name", "")
        if name == "UDON":
            udon = {
                "bases": [
                    {
                        "name": b.get("name", ""),
                        "description": b.get("description", ""),
                        "emoji": BASE_EMOJI.get(b.get("name", ""), "🍜"),
                        "available": not _is_stopped(b.get("name", ""), stop),
                    }
                    for b in cat.get("bases", [])
                ],
                "proteins": [
                    {
                        "name": p.get("name", ""),
                        "price": int(p.get("price", 0)),
                        "emoji": PROTEIN_EMOJI.get(p.get("name", ""), "🍖"),
                        "available": not _is_stopped(p.get("name", ""), stop),
                    }
                    for p in cat.get("proteins", [])
                ],
                "toppings": [
                    {
                        "name": t.get("name", ""),
                        "price": int(t.get("price", 0)),
                        "emoji": TOPPING_EMOJI.get(t.get("name", ""), "🌿"),
                        "available": not _is_stopped(t.get("name", ""), stop),
                    }
                    for t in cat.get("toppings", [])
                ],
            }
            categories.append(
                {
                    "name": "UDON",
                    "emoji": EMOJI_BY_CATEGORY.get("UDON", "🍜"),
                    "kind": "constructor",
                    "description": "Собери свой идеальный удон за 4 шага",
                }
            )
            continue

        items = [
            {
                "id": f"{name}:{item.get('name', '')}",
                "name": item.get("name", ""),
                "price": int(item.get("price", 0)),
                "description": item.get("description", ""),
                "emoji": EXTRA_EMOJI.get(item.get("name", ""), "•"),
                "category": name,
                "available": not _is_stopped(item.get("name", ""), stop),
            }
            for item in cat.get("items", [])
        ]
        categories.append(
            {
                "name": name,
                "emoji": EMOJI_BY_CATEGORY.get(name, "🍽"),
                "kind": "items",
                "description": cat.get("description", ""),
                "items": items,
            }
        )

    return {
        "categories": categories,
        "udon": udon,
        "order_types": [
            {"code": code, "title": title} for code, title in ORDER_TYPES.items()
        ],
        "settings": load_settings(),
    }


def find_menu_item(name: str) -> Optional[dict]:
    """Найти позицию по имени (для серверной проверки цен)."""
    menu = load_raw_menu()
    for cat in menu.get("categories", []):
        for item in cat.get("items", []):
            if (item.get("name") or "").strip().lower() == (name or "").strip().lower():
                return {"name": item["name"], "price": int(item.get("price", 0))}
        for section in ("proteins", "toppings"):
            for item in cat.get(section, []):
                if (item.get("name") or "").strip().lower() == (name or "").strip().lower():
                    return {"name": item["name"], "price": int(item.get("price", 0))}
    return None


def find_protein(name: str) -> Optional[dict]:
    udon = _find_category(load_raw_menu(), "UDON")
    for protein in udon.get("proteins", []):
        if (protein.get("name") or "").strip().lower() == (name or "").strip().lower():
            return {"name": protein["name"], "price": int(protein.get("price", 0))}
    return None


def base_exists(name: str) -> bool:
    udon = _find_category(load_raw_menu(), "UDON")
    return any(
        (b.get("name") or "").strip().lower() == (name or "").strip().lower()
        for b in udon.get("bases", [])
    )


def topping_exists(name: str) -> bool:
    udon = _find_category(load_raw_menu(), "UDON")
    return any(
        (t.get("name") or "").strip().lower() == (name or "").strip().lower()
        for t in udon.get("toppings", [])
    )


def extras_prices() -> dict[str, int]:
    """Цены дополнительных топпингов.

    Берём ТОЛЬКО категорию «Дополнительные топпинги»: названия позиций
    могут повторяться в других разделах (например, «Крабовая палка» есть
    и в STARTERS), и цена допов должна быть однозначной.
    """
    menu = load_raw_menu()
    prices: dict[str, int] = {}
    for cat in menu.get("categories", []):
        if cat.get("name") != "Дополнительные топпинги":
            continue
        for item in cat.get("items", []):
            prices[(item.get("name") or "").strip().lower()] = int(item.get("price", 0))
    return prices


def build_udon(base: str, protein: str, topping: str = "", extras: Optional[list[str]] = None) -> dict:
    """Собрать удон и посчитать его стоимость (цены берём из меню)."""
    protein_info = find_protein(protein) or {"name": protein, "price": 0}
    prices = extras_prices()

    extra_items: list[dict] = []
    total = int(protein_info["price"])
    for extra in extras or []:
        key = (extra or "").strip().lower()
        price = prices.get(key, 0)
        total += price
        extra_items.append({"name": extra, "price": price})

    title = f"Удон «{base}» с {protein_info['name']}"
    return {
        "kind": "udon",
        "title": title,
        "base": base,
        "protein": protein_info["name"],
        "topping": topping or "Без топпинга",
        "extras": extra_items,
        "price": total,
        "qty": 1,
    }


def build_simple_item(name: str, qty: int = 1) -> Optional[dict]:
    info = find_menu_item(name)
    if not info:
        return None
    return {
        "kind": "item",
        "title": info["name"],
        "name": info["name"],
        "price": int(info["price"]),
        "qty": max(1, int(qty or 1)),
    }


def items_total(items: list[dict]) -> int:
    total = 0
    for item in items or []:
        total += int(item.get("price", 0)) * max(1, int(item.get("qty", 1) or 1))
    return total


def describe_item(item: dict) -> str:
    """Короткое описание позиции для бота и веба."""
    if item.get("kind") == "udon":
        parts = [f"🍜 {item.get('base', '')} + {item.get('protein', '')}"]
        if item.get("topping") and item.get("topping") != "Без топпинга":
            parts.append(f"   🌿 {item['topping']}")
        for extra in item.get("extras", []) or []:
            parts.append(f"   ➕ {extra['name']} (+{extra['price']} ₽)")
        return "\n".join(parts)

    qty = int(item.get("qty", 1) or 1)
    name = item.get("name") or item.get("title") or ""
    line = f"• {name}"
    if qty > 1:
        line += f" × {qty}"
    return line


def describe_items(items: list[dict]) -> str:
    return "\n".join(describe_item(item) for item in items or [])
