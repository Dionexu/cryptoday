import os
import json
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
PORT = int(os.environ["PORT"])
print(f"🚀 Starting on port {PORT}")

bot = Bot(TOKEN, parse_mode=ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

dp.include_router(router)

user_settings = {}
coin_list_cache = None

async def load_coin_list():
    global coin_list_cache
    try:
        if os.path.exists("coin_list.json"):
            with open("coin_list.json", "r") as f:
                coin_list_cache = json.load(f)
                logger.info("✅ Coin list loaded from file")
        else:
            async with aiohttp.ClientSession() as session:
                url = "https://api.coingecko.com/api/v3/coins/list"
                async with session.get(url) as resp:
                    if resp.status != 200:
                        logger.warning(f"CoinGecko API error: {resp.status}")
                        return
                    coin_list_cache = await resp.json()
                    with open("coin_list.json", "w") as f:
                        json.dump(coin_list_cache, f)
                    logger.info("✅ Coin list saved to file")
    except Exception as e:
        logger.error(f"❌ Error loading coin list: {e}")


@router.callback_query(F.data == "select_frequency")
async def ask_frequency(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Щогодини", callback_data="freq_1h")],
        [InlineKeyboardButton(text="Кожні 2 години", callback_data="freq_2h")],
        [InlineKeyboardButton(text="2 рази на день", callback_data="freq_12h")],
        [InlineKeyboardButton(text="1 раз на день", callback_data="freq_24h")]
    ])
    await callback.message.answer("Оберіть як часто надсилати ціни:", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("freq_"))
async def handle_frequency(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    freq = callback.data.replace("freq_", "")
    user_data = user_settings.setdefault(user_id, {})
    user_data["frequency"] = freq

    if freq in ["12h", "24h"]:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="08:00", callback_data="time_08:00"), InlineKeyboardButton(text="12:00", callback_data="time_12:00")],
            [InlineKeyboardButton(text="16:00", callback_data="time_16:00"), InlineKeyboardButton(text="20:00", callback_data="time_20:00")]
        ])
        await callback.message.answer("🕐 Оберіть перший час розсилки (UTC):", reply_markup=keyboard)
    else:
        await callback.message.answer(f"✅ Частоту встановлено: {freq}")
    await callback.answer()


@router.callback_query(F.data.startswith("time_"))
async def handle_time(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    time_val = callback.data.replace("time_", "")
    user_data = user_settings.setdefault(user_id, {})

    if "time" not in user_data:
        user_data["time"] = time_val
        freq = user_data.get("frequency")
        if freq == "12h":
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="08:00", callback_data="time2_08:00"), InlineKeyboardButton(text="12:00", callback_data="time2_12:00")],
                [InlineKeyboardButton(text="16:00", callback_data="time2_16:00"), InlineKeyboardButton(text="20:00", callback_data="time2_20:00")]
            ])
            await callback.message.answer("🕑 Оберіть другий час розсилки (UTC):", reply_markup=keyboard)
        else:
            await callback.message.answer(f"✅ Час встановлено: {time_val}")
    else:
        await callback.message.answer("⚠️ Час уже встановлено. Якщо хочете змінити — скиньте налаштування.")
    await callback.answer()


@router.callback_query(F.data.startswith("time2_"))
async def handle_second_time(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    second_time = callback.data.replace("time2_", "")
    user_data = user_settings.setdefault(user_id, {})
    user_data["second_time"] = second_time
    await callback.message.answer(f"✅ Другий час встановлено: {second_time}")
    await callback.answer()


@router.callback_query(F.data == "get_prices")
async def handle_prices(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    coins = user_settings.get(user_id, {}).get("coins", ["bitcoin", "ethereum"])
    text = "📈 Поточні ціни:\n"
    try:
        async with aiohttp.ClientSession() as session:
            for coin in coins:
                url = "https://api.coingecko.com/api/v3/simple/price"
                params = {"ids": coin, "vs_currencies": "usd"}
                async with session.get(url, params=params) as resp:
                    data = await resp.json()
                    price = data.get(coin, {}).get("usd")
                    if price:
                        text += f"{coin.capitalize()}: ${price}\n"
        await callback.message.answer(text.strip())
    except Exception as e:
        logger.warning(f"❌ Помилка отримання цін: {e}")
        await callback.message.answer("❌ Помилка отримання цін. Спробуйте пізніше.")
    await callback.answer()


# === Run server ===
if __name__ == "__main__":
    app = web.Application()
    app.on_startup.append(lambda app: bot.set_webhook(WEBHOOK_URL))
    app.on_shutdown.append(lambda app: bot.session.close())
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    web.run_app(app, host="0.0.0.0", port=PORT)
