import os
import asyncio
import logging
from aiohttp import web
from datetime import datetime, timedelta
import aiohttp

from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("No BOT_TOKEN provided.")

WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
if not WEBHOOK_HOST:
    raise RuntimeError("No WEBHOOK_HOST provided.")

if not WEBHOOK_HOST.startswith(("http://", "https://")):
    WEBHOOK_HOST = "https://" + WEBHOOK_HOST

WEBHOOK_PATH = f"/webhook/{TOKEN.split(':')[0]}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
PORT = int(os.getenv("PORT", "3000"))

bot = Bot(TOKEN, parse_mode=ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

user_settings = {}



async def on_startup(bot_instance: Bot):
    await bot_instance.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
    me = await bot_instance.get_me()
    logger.info(f"Bot @{me.username} (ID: {me.id}) started with webhook: {WEBHOOK_URL}")

async def on_shutdown(bot_instance: Bot):
    await bot_instance.session.close()

async def price_notifier():
    while True:
        logger.info("[DEBUG] price_notifier активний")
        now = datetime.utcnow()
        for uid, settings in user_settings.items():
            coins = settings.get("coins")
            freq = settings.get("frequency")
            tz = settings.get("timezone", "+00:00")
            time_str = settings.get("time")
            second_time = settings.get("second_time")
            sleep = settings.get("sleep")

            offset_hours = int(tz.split(":")[0])
            local_hour = (now + timedelta(hours=offset_hours)).strftime("%H:%M")

            if not coins or not freq or not time_str:
                continue

            if sleep and sleep.get("start") and sleep.get("end"):
                start, end = sleep["start"], sleep["end"]
                if start < end:
                    if start <= local_hour < end:
                        continue
                else:
                    if local_hour >= start or local_hour < end:
                        continue

            should_send = False
            if freq == "24h" and local_hour == time_str:
                should_send = True
            elif freq == "12h" and second_time and local_hour in [time_str, second_time]:
                should_send = True
            elif freq == "1h" and now.minute == 0:
                should_send = True
            elif freq == "2h" and now.minute == 0 and now.hour % 2 == 0:
                should_send = True

            logger.info(f"[DEBUG] UID: {uid}, freq: {freq}, local_hour: {local_hour}, time_str: {time_str}, should_send: {should_send}")

            if should_send:
                try:
                    text = f"📈 Ціни на {', '.join(coins).upper()} (UTC{tz}):
"


                    async with aiohttp.ClientSession() as session:
                        for coin in coins:
                            url = "https://api.coingecko.com/api/v3/simple/price"
                            params = {"ids": coin, "vs_currencies": "usd"}
                            async with session.get(url, params=params) as resp:
                                data = await resp.json()
                                price = data.get(coin, {}).get("usd")
                                if price:
                                    text += f"{coin.capitalize()}: ${price}
"


                    await bot.send_message(uid, text.strip())
                except Exception as e:
                    logger.warning(f"❌ Помилка надсилання повідомлення користувачу {uid}: {e}")
        await asyncio.sleep(60)


async def main():
    app = web.Application()
    webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    app.router.add_route("POST", WEBHOOK_PATH, webhook_handler.handle)
    setup_application(app, dp, bot=bot, on_startup=on_startup, on_shutdown=on_shutdown)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=PORT)
    logger.info(f"🚀 Starting web server on http://0.0.0.0:{PORT}")
    await site.start()

    asyncio.create_task(price_notifier())
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped manually (KeyboardInterrupt/SystemExit)!")
