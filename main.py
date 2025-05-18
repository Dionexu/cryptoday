import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(F.text == "/start")
async def start(message: Message):
    await message.answer("Бот працює. Вітаю 👋")

async def main():
    print("🚀 Бот запущено через polling")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
