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
symbol_to_id_map = {}

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🕒 Обрати частоту", callback_data="select_frequency")],
        [InlineKeyboardButton(text="📈 Дивитися ціни", callback_data="get_prices")],
        [InlineKeyboardButton(text="⚙️ Обрати монети", callback_data="select_coins")],
        [InlineKeyboardButton(text="🔄 Скинути налаштування", callback_data="reset_settings")]
    ])
    await message.answer("Привіт! Натисни кнопку нижче, щоб отримати ціни.", reply_markup=keyboard)


@router.callback_query(F.data == "reset_settings")
async def handle_reset(callback: types.CallbackQuery):
    user_settings[callback.from_user.id] = {}
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🕒 Обрати частоту", callback_data="select_frequency")],
        [InlineKeyboardButton(text="📈 Дивитися ціни", callback_data="get_prices")],
        [InlineKeyboardButton(text="⚙️ Обрати монети", callback_data="select_coins")],
        [InlineKeyboardButton(text="🔄 Скинути налаштування", callback_data="reset_settings")]
    ])
    await callback.message.answer("🔄 Налаштування скинуто. Ви можете почати заново:", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "select_coins")
async def ask_coin_selection(callback: types.CallbackQuery):
    user_data = user_settings.setdefault(callback.from_user.id, {})
    user_data["coins"] = []
    user_data["mode"] = "selecting_coins"
    await callback.message.answer("Введіть назву або ID монети (наприклад, bitcoin, solana, dogecoin). Введіть 'готово', коли завершите.")
    await callback.answer()


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
    await callback.message.answer(f"✅ Частоту встановлено: {freq}")
    await callback.answer()


@router.callback_query(F.data == "get_prices")
async def handle_prices(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    coins = user_settings.get(user_id, {}).get("coins", ["bitcoin", "ethereum"])
    text = "📈 Поточні ціни:\n"
    try:
        async with aiohttp.ClientSession() as session:
            for coin in coins:
                url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=usd"
                try:
                    async with session.get(url) as resp:
                        if resp.status != 200:
                            raise Exception(f"Bad response: {resp.status}")
                        data = await resp.json()
                        price = data.get(coin, {}).get("usd")
                        if price is not None:
                            text += f"{coin.capitalize()}: ${price}\n"
                        else:
                            text += f"{coin.capitalize()}: ⚠️ Немає даних\n"
                except Exception as e:
                    logger.warning(f"Помилка з монетою {coin}: {e}")
                    text += f"{coin.capitalize()}: ❌ Помилка отримання даних\n"
        await callback.message.answer(text.strip())
    except Exception as e:
        logger.warning(f"❌ Помилка отримання цін: {e}")
        await callback.message.answer("❌ Помилка отримання цін. Спробуйте пізніше.")
    await callback.answer()


@router.message(F.text)
async def handle_coin_input(message: types.Message):
    user_id = message.from_user.id
    user_data = user_settings.setdefault(user_id, {})
    if user_data.get("mode") != "selecting_coins":
        return

    coin_input = message.text.lower().strip()

    if coin_input == "готово":
        user_data["mode"] = None
        await message.answer("✅ Монети збережено. Тепер натисніть 'Дивитися ціни'.")
        return

    global coin_list_cache, symbol_to_id_map
    if not coin_list_cache:
        async with aiohttp.ClientSession() as session:
            url = "https://api.coingecko.com/api/v3/coins/list"
            async with session.get(url) as resp:
                coin_list_cache = await resp.json()
                symbol_to_id_map = {c['symbol'].lower(): c['id'] for c in coin_list_cache}
                symbol_to_id_map.update({c['id'].lower(): c['id'] for c in coin_list_cache})

    coin_id = symbol_to_id_map.get(coin_input)

    if not coin_id:
        await message.answer("❌ Такої монети не знайдено. Спробуйте ще раз.")
        return

    coins = user_data.setdefault("coins", [])
    if coin_id in coins:
        await message.answer("ℹ️ Цю монету вже додано.")
    elif len(coins) >= 3:
        await message.answer("⚠️ Можна обрати максимум 3 монети.")
    else:
        coins.append(coin_id)
        await message.answer(f"✅ Додано монету: <b>{coin_input.upper()}</b> ({len(coins)}/3)", parse_mode=ParseMode.HTML)


if __name__ == "__main__":
    app = web.Application()
    app.on_startup.append(lambda app: bot.set_webhook(WEBHOOK_URL))
    app.on_shutdown.append(lambda app: bot.session.close())
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    web.run_app(app, host="0.0.0.0", port=PORT)
