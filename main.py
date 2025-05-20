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
PORT = int(os.getenv("PORT", "3000"))

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


@router.callback_query(F.data == "refresh_coin_list")
async def refresh_coin_list(callback: types.CallbackQuery):
    global coin_list_cache
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://api.coingecko.com/api/v3/coins/list"
            async with session.get(url) as resp:
                if resp.status != 200:
                    await callback.message.answer("❌ Не вдалося оновити список монет.")
                    return
                coin_list_cache = await resp.json()
                with open("coin_list.json", "w") as f:
                    json.dump(coin_list_cache, f)
                await callback.message.answer("🔁 Список монет оновлено!")
    except Exception as e:
        logger.error(f"❌ Error refreshing coin list: {e}")
        await callback.message.answer("❌ Сталася помилка під час оновлення.")
    await callback.answer()


@router.callback_query(F.data == "select_coins")
async def ask_coin_selection(callback: types.CallbackQuery):
    user_data = user_settings.setdefault(callback.from_user.id, {})
    user_data["coins"] = []
    user_data["mode"] = "selecting_coins"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Оновити список монет", callback_data="refresh_coin_list")]
    ])
    await callback.message.answer(
        "Введіть назву або ID монети англійською (наприклад, bitcoin, solana, dogecoin). Введіть 'готово', коли завершите вибір.",
        reply_markup=keyboard
    )
    await callback.answer()


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


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    logger.info(f"✅ Received /start from user {message.from_user.id}")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🕒 Обрати частоту", callback_data="select_frequency")],
        [InlineKeyboardButton(text="📈 Дивитися ціни", callback_data="get_prices")],
        [InlineKeyboardButton(text="⚙️ Обрати монети", callback_data="select_coins")],
        [InlineKeyboardButton(text="🔄 Скинути налаштування", callback_data="reset_settings")]
    ])
    await message.answer("Привіт! Натисни кнопку нижче, щоб отримати ціни.", reply_markup=keyboard)


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
            await load_coin_list()
            if coin_list_cache is None:
                await message.answer("❌ CoinGecko недоступний. Спробуйте пізніше.")
                return

        all_coins = coin_list_cache
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
            return

        if len(coins) >= 5:
            await message.answer("⚠️ Можна обрати максимум 5 монет.")
            return

        coins.append(coin)
        await message.answer(f"✅ Додано монету: <b>{coin.upper()}</b> ({len(coins)}/5)")

    except Exception as e:
        logger.warning(f"❌ Помилка обробки монети: {e}")
        await message.answer("❌ Сталася помилка. Спробуйте ще раз пізніше.")


async def on_startup(app):
    await load_coin_list()
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
