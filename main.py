import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from aiogram.types import Message

BOT_TOKEN = "8006649444:AAFa1DsYuT8riikAqv6wUz3Qs_IC5KNotIw"
WEBHOOK_SECRET = "abc123"
WEBHOOK_PATH = f"/webhook/{WEBHOOK_SECRET}"
BASE_WEBHOOK_URL = "https://bot-b14f.onrender.com"
WEBHOOK_URL = BASE_WEBHOOK_URL + WEBHOOK_PATH

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(F.text == "/start")
async def start(message: Message):
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
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp)
    return app

if __name__ == "__main__":
    web.run_app(create_app(), port=10000)
