import asyncio
import logging
from aiogram import Bot, Dispatcher, executor
from aiogram.types import ParseMode
from config import BOT_TOKEN
from db import init_db
from menu import router

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(bot)
dp.include_router(router)

async def on_startup(dp):
    init_db()
    logging.info("SANUKI BOT запущен!")

if __name__ == "__main__":
    executor.start_polling(dp, on_startup=on_startup, skip_updates=True)