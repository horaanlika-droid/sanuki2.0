import os

from dotenv import load_dotenv

load_dotenv()

# ============================================================
# ВСЕ настройки — только эти три переменные окружения.
# На BotHost задаёшь именно их, больше ничего не нужно.
# ============================================================

# 1) Токен бота из BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# 2) ID администратора (можно несколько через запятую)
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_ID", "").replace(" ", "").split(",") if x]

# 3) API ЮMoney (секретный ключ / OAuth-токен кассы).
#    Пока интеграция не готова — можно оставить пустым, работает заглушка.
YOOMONEY_API = os.getenv("YOOMONEY_API", "")

# Веб-приложение: публичный базовый URL (для кнопки-меню бота).
# Если не задан — используется адрес, на котором запущен веб (WEB_PORT).
WEB_BASE_URL = os.getenv("WEB_BASE_URL", "")
WEB_PORT = int(os.getenv("WEB_PORT", "8000"))

def web_app_url() -> str:
    return WEB_BASE_URL or f"http://localhost:{WEB_PORT}/"
