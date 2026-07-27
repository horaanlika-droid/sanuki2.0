import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config import BOT_TOKEN
from db import init_db
from menu import router

logging.basicConfig(level=logging.INFO)

dp = Dispatcher()
dp.include_router(router)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

async def main():
    init_db()
    logging.info("SANUKI BOT запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())