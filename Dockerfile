FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Переменные окружения (задаются на хосте):
#   BOT_TOKEN     - токен бота из BotFather
#   ADMIN_ID      - ID администратора (можно несколько через запятую)
#   YOOMONEY_API  - ключ API ЮMoney (пока опционально, работает заглушка)
#   WEB_BASE_URL  - публичный адрес веб-приложения (опционально)
#   WEB_PORT      - порт веба (по умолчанию 8000)
CMD ["python", "app.py"]
