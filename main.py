import os
import logging
import asyncio
from aiohttp import web

from aiogram import Bot, Dispatcher, Router, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

logging.basicConfig(level=logging.INFO)

# Load environment variables
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("No BOT_TOKEN provided")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")  # e.g. "https://your-bot.onrender.com"
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", f"/webhook/{TOKEN}")  # webhook path (can be set or default to /webhook/<token>)
if not WEBHOOK_HOST:
    raise RuntimeError("No WEBHOOK_HOST provided")
WEBHOOK_URL = WEBHOOK_HOST + WEBHOOK_PATH

# Initialize bot and dispatcher
bot = Bot(TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Preserve existing functionality (menu with coins, frequency, time zones)
@router.message(Command("start"))
async def cmd_start(message: types.Message):
    # Existing logic for showing the menu goes here
    await message.answer("Hello! Use the menu to set up coin alerts and preferences.")  # Placeholder response

# ... (Other handlers for coin selection, setting frequency, timezones, etc. should be here)

# Startup and shutdown events for webhook
async def on_startup(bot: Bot):
    # Set the webhook when the bot starts
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"🌐 Webhook set to: {WEBHOOK_URL}")

async def on_shutdown(bot: Bot):
    # Gracefully delete the webhook and close the aiohttp session on shutdown
    logging.info("Shutting down... Deleting webhook")
    try:
        await bot.delete_webhook()
        logging.info("✅ Webhook deleted")
    except Exception as e:
        logging.error(f"Error deleting webhook: {e}")
    await bot.session.close()
    logging.info("💤 Aiohttp session closed")

dp.startup.register(on_startup)
dp.shutdown.register(on_shutdown)

# Create web application and register the aiogram webhook handler
app = web.Application()
app["bot"] = bot  # Make bot accessible via aiohttp app (optional, for completeness)
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
setup_application(app, dp, bot=bot)

# Run the web application on host and port (Render supplies a PORT environment variable)
PORT = int(os.getenv("PORT", "3000"))
web.run_app(app, host="0.0.0.0", port=PORT)
