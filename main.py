import os
import logging
import asyncio
from aiohttp import web

from aiogram import Bot, Dispatcher, Router, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.webhook.aiohttp_server import setup_application # Import setup_application

logging.basicConfig(level=logging.INFO)

# Load environment variables
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    logging.critical("No BOT_TOKEN provided. Exiting.")
    raise RuntimeError("No BOT_TOKEN provided")

WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")  # e.g., "https://your-bot.onrender.com"
if not WEBHOOK_HOST:
    logging.critical("No WEBHOOK_HOST provided. Exiting.")
    raise RuntimeError("No WEBHOOK_HOST provided")

# Ensure WEBHOOK_HOST starts with https://
if not WEBHOOK_HOST.startswith(("http://", "https://")):
    # Default to https if no scheme is provided, common for Render.
    WEBHOOK_HOST = "https://" + WEBHOOK_HOST
    logging.warning(f"WEBHOOK_HOST did not have a scheme, prepended https://. New host: {WEBHOOK_HOST}")


WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", f"/webhook/{TOKEN.split(':')[0]}") # Using only bot ID for a cleaner path, still unique.
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# Render provides a PORT environment variable
PORT = int(os.getenv("PORT", "3000")) # Default to 3000 if not on Render for local testing

# Initialize bot and dispatcher
bot = Bot(TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
router = Router() # Create a router instance

# --- Your Bot Logic Handlers Will Go Here ---
@router.message(Command("start"))
async def cmd_start(message: types.Message):
    # Existing logic for showing the menu goes here
    # For now, just a placeholder:
    await message.answer(
        "Привет! Я твой бот. Пока что я умею только это.\n"
        "Ты можешь добавить другие команды и функции."
    )
    logging.info(f"Handled /start command from user {message.from_user.id}")

# ... (Other handlers for coin selection, setting frequency, timezones, etc. should be here)
# Example:
# @router.message(Command("help"))
# async def cmd_help(message: types.Message):
#     await message.answer("This is a help message.")

async def on_startup(dispatcher: Dispatcher, bot_instance: Bot): # Modified to accept dispatcher too
    # Set the webhook when the bot starts
    await bot_instance.set_webhook(WEBHOOK_URL, allowed_updates=dispatcher.resolve_used_update_types())
    logging.info(f"🌐 Webhook set to: {WEBHOOK_URL}")
    logging.info(f"Bot username: @{(await bot_instance.get_me()).username}")

async def on_shutdown(bot_instance: Bot):
    logging.info("Shutting down... Deleting webhook")
    try:
        await bot_instance.delete_webhook()
        logging.info("✅ Webhook deleted")
    except Exception as e:
        logging.error(f"Error deleting webhook: {e}")
    
    # Gracefully close the Bot session
    # In aiogram 3.x, the session is typically managed within the Bot instance
    # or explicitly if you created your own aiohttp.ClientSession for the bot.
    # If using default bot session handling, closing the bot itself handles it.
    await bot_instance.session.close()
    logging.info("💤 Bot session closed")


async def main():
    # Include the router in the dispatcher
    dp.include_router(router)

    # Register startup and shutdown handlers
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Create web application
    app = web.Application()

    # Pass bot instance to startup/shutdown handlers via workflow_data
    # This makes 'bot_instance' available in on_startup and on_shutdown
    workflow_data = {"bot_instance": bot}

    # Setup aiogram routes and middlwares
    # This will also pass the bot and dispatcher to the handlers.
    setup_application(app, dp, **workflow_data)

    # Run the web application
    # For Render, host should be '0.0.0.0' and port from env var 'PORT'
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=PORT)
    logging.info(f"🚀 Starting web server on http://0.0.0.0:{PORT}")
    await site.start()

    # Keep the application running
    await asyncio.Event().wait() # Keep alive until interrupted

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped manually!")
    except RuntimeError as e: # Catch the RuntimeError from missing env vars
        logging.error(f"Runtime error during startup: {e}")
