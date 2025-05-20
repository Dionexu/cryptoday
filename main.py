import os
import logging
import asyncio
from aiohttp import web
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage

import json
import aiohttp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
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

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Налаштувати монети", callback_data="setup_coins")]
    ])
    await message.answer("Привіт! Я бот-сводка курсу криптовалют. Обери монети для відстеження:", reply_markup=keyboard)

@router.message(Command("debug"))
async def cmd_debug(message: types.Message):
    uid = message.from_user.id
    settings = user_settings.get(uid)
    if not settings:
        await message.answer("⚠️ Немає збережених налаштувань.")
        return
    formatted = json.dumps(settings, indent=2, ensure_ascii=False)
    await message.answer(f"🛠 Твої налаштування:\n<pre>{formatted}</pre>", parse_mode=ParseMode.HTML)

@router.message(Command("test"))
async def cmd_test(message: types.Message):
    uid = message.from_user.id
    settings = user_settings.get(uid)
    if not settings:
        await message.answer("⚠️ Немає збережених налаштувань.")
        return
    coins = settings.get("coins", [])
    tz = settings.get("timezone", "+00:00")
    text = f"📈 Тест: Ціни на {', '.join(coins).upper()} (UTC{tz}):\n"
    async with aiohttp.ClientSession() as session:
        for coin in coins:
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {"ids": coin, "vs_currencies": "usd"}
            async with session.get(url, params=params) as resp:
                data = await resp.json()
                price = data.get(coin, {}).get("usd")
                if price:
                    text += f"{coin.capitalize()}: ${price}\n"
    await message.answer(text.strip())

# ... остальной код без изменений до price_notifier ...

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
                    text = f"📈 Ціни на {', '.join(coins).upper()} (UTC{tz}):\n"
                    async with aiohttp.ClientSession() as session:
                        for coin in coins:
                            url = "https://api.coingecko.com/api/v3/simple/price"
                            params = {"ids": coin, "vs_currencies": "usd"}
                            async with session.get(url, params=params) as resp:
                                data = await resp.json()
                                price = data.get(coin, {}).get("usd")
                                if price:
                                    text += f"{coin.capitalize()}: ${price}\n"
                    await bot.send_message(uid, text.strip())
                except Exception as e:
                    logger.warning(f"❌ Помилка надсилання повідомлення користувачу {uid}: {e}")
        await asyncio.sleep(60)
