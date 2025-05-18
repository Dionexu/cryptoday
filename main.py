import os
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web
from datetime import datetime

# === Налаштування ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "abc123")
PORT = int(os.getenv("PORT", "10000"))
BASE_WEBHOOK_PATH = f"/webhook/{WEBHOOK_SECRET}"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# === Обробка повідомлень
@dp.message()
async def echo_message(message):
    await message.reply("✅ Привіт! Я працюю через webhook на Render!")

# === Обробка вебхуку
async def handle_webhook(request: web.Request):
    try:
        data = await request.json()
        update = Update.model_validate(data)
        await dp.feed_update(bot, update)
    except Exception as e:
        print(f"[ERROR] handle_webhook: {e}")
    return web.Response()

# === Старт / стоп
async def on_startup(app):
    webhook_url = f"https://bot-b14f.onrender.com{BASE_WEBHOOK_PATH}"  # ← твій URL
    await bot.set_webhook(url=webhook_url, drop_pending_updates=True)
    print(f"[{datetime.now().isoformat()}] 🚀 Webhook встановлено: {webhook_url}")

async def on_shutdown(app):
    await bot.delete_webhook()
    await bot.session.close()
    print(f"[{datetime.now().isoformat()}] 🧹 Webhook видалено. Бот завершив роботу.")

# === Aiohttp app
def create_app():
    app = web.Application()
    app.router.add_post(BASE_WEBHOOK_PATH, handle_webhook)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    return app

if __name__ == "__main__":
    web.run_app(create_app(), port=PORT)
