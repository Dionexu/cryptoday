import os
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web
from datetime import datetime

# === Налаштування ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "supersecrettoken")
BASE_WEBHOOK_PATH = f"/webhook/{WEBHOOK_SECRET}"
PORT = int(os.getenv("PORT", "10000"))  # Render запускає на цьому порту

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# === Обробка оновлень від Telegram ===
@dp.message()
async def echo_message(message):
    await message.reply("👋 Привіт! Бот працює через webhook!")

# === HTTP-сервер (Aiohttp) ===
async def handle_webhook(request: web.Request):
    try:
        data = await request.json()
        update = Update.model_validate(data)
        await dp.feed_update(bot, update)
    except Exception as e:
        print(f"[ERROR] handle_webhook: {e}")
    return web.Response()

async def on_startup(app):
    webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_URL')}{BASE_WEBHOOK_PATH}"
    await bot.set_webhook(url=webhook_url, drop_pending_updates=True)
    print(f"[{datetime.now().isoformat()}] 🚀 Webhook встановлено на {webhook_url}")

async def on_shutdown(app):
    await bot.delete_webhook()
    await bot.session.close()
    print(f"[{datetime.now().isoformat()}] 🧹 Webhook видалено, бот завершив роботу.")

# === Створення і запуск сервера ===
def create_app():
    app = web.Application()
    app.router.add_post(BASE_WEBHOOK_PATH, handle_webhook)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    return app

if __name__ == "__main__":
    web.run_app(create_app(), port=PORT)
