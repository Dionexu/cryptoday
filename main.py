import os
import logging
import asyncio
from aiohttp import web

from aiogram import Bot, Dispatcher, Router, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# --- Загрузка переменных окружения ---
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    logger.critical("CRITICAL: No BOT_TOKEN provided. Exiting.")
    raise RuntimeError("No BOT_TOKEN provided. Задайте BOT_TOKEN в переменных окружения.")

WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
if not WEBHOOK_HOST:
    logger.critical("CRITICAL: No WEBHOOK_HOST provided. Exiting.")
    raise RuntimeError("No WEBHOOK_HOST provided. Задайте WEBHOOK_HOST в переменных окружения.")

if not WEBHOOK_HOST.startswith(("http://", "https://")):
    WEBHOOK_HOST = "https://" + WEBHOOK_HOST
    logger.warning(f"WEBHOOK_HOST did not have a scheme, prepended https://. New host: {WEBHOOK_HOST}")

WEBHOOK_PATH = f"/webhook/{TOKEN.split(':')[0]}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
PORT = int(os.getenv("PORT", "3000"))

# --- Инициализация Aiogram ---
bot = Bot(TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# --- ОБРАБОТЧИКИ ---
@router.message(Command("start"))
async def cmd_start(message: types.Message):
    logger.info(f"User {message.from_user.id} ({message.from_user.full_name}) triggered /start command.")
    try:
        await message.answer(
            f"Привет, {message.from_user.full_name}!\n"
            "Я твой бот, готовый к работе.\n"
            "Пока я умею только это, но ты можешь научить меня новому!"
        )
        logger.info(f"Successfully replied to /start for user {message.from_user.id}")
    except Exception as e:
        logger.error(f"Error in cmd_start for user {message.from_user.id}: {e}")

# --- Webhook Startup/Shutdown ---
async def on_startup(bot_instance: Bot):
    await bot_instance.set_webhook(
        url=WEBHOOK_URL,
        drop_pending_updates=True
    )
    me = await bot_instance.get_me()
    logger.info(f"Bot @{me.username} (ID: {me.id}) started with webhook: {WEBHOOK_URL}")

    webhook_info = await bot_instance.get_webhook_info()
    logger.info(f"🔎 Current webhook info: URL={webhook_info.url}, has_custom_certificate={webhook_info.has_custom_certificate}, pending_update_count={webhook_info.pending_update_count}")

async def on_shutdown(bot_instance: Bot):
    try:
        await bot_instance.session.close()
        logger.info("Bot session closed successfully.")
    except Exception as e:
        logger.error(f"Error closing bot session: {e}")

# --- Основная функция ---
async def main():
    app = web.Application()

    # Обработка входящих webhook-запросов
    webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    app.router.add_route("POST", WEBHOOK_PATH, webhook_handler.handle)

    setup_application(app, dp, bot=bot, on_startup=on_startup, on_shutdown=on_shutdown)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=PORT)
    logger.info(f"🚀 Starting web server on http://0.0.0.0:{PORT}")
    await site.start()

    try:
        await asyncio.Event().wait()
    finally:
        logger.info("Application is shutting down...")
        await runner.cleanup()
        logger.info("Application has been shut down.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped manually (KeyboardInterrupt/SystemExit)!")
    except RuntimeError:
        pass
    except Exception as e:
        logger.exception(f"Unhandled exception at top level: {e}")
