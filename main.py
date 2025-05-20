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
coin_list_cache = None

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

    if freq not in ["1h", "2h", "12h", "24h"]:
        await callback.message.answer("❌ Невірне значення частоти.")
        return

    user_data = user_settings.setdefault(user_id, {})
    user_data["frequency"] = freq

    if freq in ["12h", "24h"]:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="08:00", callback_data="time_08:00"),
             InlineKeyboardButton(text="12:00", callback_data="time_12:00")],
            [InlineKeyboardButton(text="16:00", callback_data="time_16:00"),
             InlineKeyboardButton(text="20:00", callback_data="time_20:00")]
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
                [InlineKeyboardButton(text="08:00", callback_data="time2_08:00"),
                 InlineKeyboardButton(text="12:00", callback_data="time2_12:00")],
                [InlineKeyboardButton(text="16:00", callback_data="time2_16:00"),
                 InlineKeyboardButton(text="20:00", callback_data="time2_20:00")]
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


@router.callback_query(F.data == "select_coins")
async def ask_coin_selection(callback: types.CallbackQuery):
    user_data = user_settings.setdefault(callback.from_user.id, {})
    user_data["coins"] = []
    user_data["mode"] = "selecting_coins"
    await callback.message.answer("Введіть назву або ID монети англійською (наприклад, bitcoin, solana, dogecoin). Введіть 'готово', коли завершите вибір.")
    await callback.answer()


@router.callback_query(F.data == "reset_settings")
async def handle_reset(callback: types.CallbackQuery):
    user_settings.pop(callback.from_user.id, None)
    await callback.message.answer("🔄 Налаштування скинуто. Ви можете почати заново командою /start або обрати монети.")
    await callback.answer()


@router.message()
async def handle_coin_text(message: types.Message):
    global coin_list_cache
    user_id = message.from_user.id
    user_data = user_settings.get(user_id)

    if not user_data:
        user_settings[user_id] = {}
        return

    if user_data.get("mode") != "selecting_coins":
        return

    coin = message.text.lower()

    if coin == "готово":
        user_data["mode"] = None
        await message.answer("✅ Монети збережено. Тепер натисніть 'Дивитися ціни'.")
        return

    try:
        if coin_list_cache is None:
            async with aiohttp.ClientSession() as session:
                url = "https://api.coingecko.com/api/v3/coins/list"
                async with session.get(url) as resp:
                    coin_list_cache = await resp.json()

        all_coins = coin_list_cache
        if not isinstance(all_coins, list) or not all(isinstance(c, dict) for c in all_coins):
            await message.answer("❌ Помилка отримання списку монет. Спробуйте пізніше.")
            return

        id_map = {c['id']: c['id'] for c in all_coins}
        symbol_map = {c['symbol']: c['id'] for c in all_coins}
        valid_ids = set(id_map.keys()).union(symbol_map.keys())

        if coin not in valid_ids:
            await message.answer("❌ Такої монети не знайдено. Спробуйте ще раз.")
            return

        if coin in symbol_map:
            coin = symbol_map[coin]

        coins = user_data.setdefault("coins", [])

        if coin in coins:
            await message.answer("ℹ️ Цю монету вже додано.")
        elif len(coins) >= 5:
            await message.answer("⚠️ Можна обрати максимум 5 монет.")
        else:
            coins.append(coin)
            await message.answer(f"✅ Додано {coin.upper()} ({len(coins)}/5)")

    except Exception as e:
        logger.warning(f"❌ Помилка обробки монети: {e}")
        await message.answer("❌ Сталася помилка. Спробуйте ще раз пізніше.")


@router.callback_query(F.data == "get_prices")
async def handle_prices(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    coins = user_settings.get(user_id, {}).get("coins", ["bitcoin", "ethereum"])
    text = "📈 Поточні ціни:"

    try:
        async with aiohttp.ClientSession() as session:
            for coin in coins:
                url = "https://api.coingecko.com/api/v3/simple/price"
                params = {"ids": coin, "vs_currencies": "usd"}
                async with session.get(url, params=params) as resp:
                    data = await resp.json()
                    price = data.get(coin, {}).get("usd")
                    if price:
                        text += f"{coin.capitalize()}: ${price}"
        await callback.message.answer(text.strip())
    except Exception as e:
        logger.warning(f"❌ Помилка отримання цін: {e}")
        await callback.message.answer("❌ Помилка отримання цін. Спробуйте пізніше.")

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🕒 Обрати частоту", callback_data="select_frequency")],
        [InlineKeyboardButton(text="📈 Дивитися ціни", callback_data="get_prices")],
        [InlineKeyboardButton(text="⚙️ Обрати монети", callback_data="select_coins")],
        [InlineKeyboardButton(text="🔄 Скинути налаштування", callback_data="reset_settings")]
    ])
    await message.answer("Привіт! Натисни кнопку нижче, щоб отримати ціни.", reply_markup=keyboard)


# === Webhook server setup ===

async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(app):
    await bot.delete_webhook()
    await bot.session.close()

app = web.Application()
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
setup_application(app, dp, bot=bot)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)
