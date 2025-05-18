import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.types import Message
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "abc123")
WEBHOOK_PATH = f"/webhook/{WEBHOOK_SECRET}"
WEBHOOK_BASE = os.getenv("WEBHOOK_BASE", "https://bot-b14f.onrender.com")
WEBHOOK_URL = f"{WEBHOOK_BASE}{WEBHOOK_PATH}"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(F.text == "/start")
async def start_handler(message: Message):
    await message.answer("Бот працює. Вітаю 👋")

async def on_startup(app: web.Application):
    await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
    print(f"🚀 Webhook встановлено: {WEBHOOK_URL}")

async def on_shutdown(app: web.Application):
    await bot.delete_webhook()
    print("🧹 Webhook видалено. Бот завершив роботу.")

def create_app():
    app = web.Application()
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Реєстрація хендлера для обробки Telegram запитів
    webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_handler.register(app, path=WEBHOOK_PATH)

    setup_application(app, dp)
    return app

if __name__ == "__main__":
    web.run_app(create_app(), port=10000)
