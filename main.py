import os
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import CommandStart
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "abc123")
PORT = int(os.getenv("PORT", 10000))

BASE_WEBHOOK_PATH = f"/webhook/{WEBHOOK_SECRET}"
WEBHOOK_URL = f"https://bot-b14f.onrender.com{BASE_WEBHOOK_PATH}"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

@dp.message(CommandStart())
async def start_handler(message):
    await message.answer("👋 Привіт! Я твій бот і вже працюю.")

@dp.message()
async def echo_handler(message):
    await message.reply("✉️ Ти написав: " + message.text)

async def webhook_handler(request: web.Request):
    try:
        data = await request.json()
        print(f"📩 Запит отримано: {data}")
        update = Update.model_validate(data)
        await dp.feed_update(bot, update)
    except Exception as e:
        print(f"❗ Webhook error: {e}")
    return web.Response()

async def ping_handler(request):
    return web.Response(text="OK", status=200)

async def on_startup(app):
    await bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
    print(f"[{datetime.now().isoformat()}] 🚀 Webhook встановлено: {WEBHOOK_URL}")

async def on_shutdown(app):
    print(f"[{datetime.now().isoformat()}] 🛑 Бот зупиняється...")
    await bot.session.close()

def create_app():
    app = web.Application()
    app.router.add_post(BASE_WEBHOOK_PATH, webhook_handler)
    app.router.add_get("/", ping_handler)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    return app

if __name__ == "__main__":
    web.run_app(create_app(), port=PORT)
