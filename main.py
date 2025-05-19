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
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# --- Временное хранилище ---
user_settings = {}

# --- ОБРАБОТЧИКИ ---
@router.message(Command("start"))
async def cmd_start(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Налаштувати монети", callback_data="setup_coins")],
        [InlineKeyboardButton(text="⏰ Час та частота", callback_data="setup_time")],
        [InlineKeyboardButton(text="🌍 Таймзона", callback_data="setup_timezone")],
        [InlineKeyboardButton(text="🔄 Скинути налаштування", callback_data="reset_settings")]
    ])
    await message.answer(
        "Привіт! Я бот-сводка курсу криптовалют. Обери, що хочеш налаштувати:",
        reply_markup=keyboard
    )

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer("/start — налаштування\n/help — допомога\nВибір монет, часу, частоти, таймзони, скидання налаштувань через кнопки")

@router.callback_query(F.data == "setup_coins")
async def setup_coins(callback: types.CallbackQuery):
    await callback.message.answer("Введи назву монети або її частину (наприклад: btc або ethereum):")
    user_settings[callback.from_user.id] = user_settings.get(callback.from_user.id, {})
    user_settings[callback.from_user.id]["coins"] = []
    await callback.answer()

@router.message()
async def search_coin(message: types.Message):
    if "coins" not in user_settings.get(message.from_user.id, {}):
        return

    query = message.text.strip().lower()
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get("https://api.coingecko.com/api/v3/coins/list") as resp:
                all_coins = await resp.json()
                matches = [c for c in all_coins if query in c['id'] or query in c['symbol'] or query in c['name'].lower()]
                if not matches:
                    await message.answer("❌ Монету не знайдено. Спробуйте ще раз.")
                    return

                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=c['name'], callback_data=f"coin_{c['id']}") for c in matches[:3]],
                    [InlineKeyboardButton(text="✅ Готово", callback_data="coin_done")]
                ])
                await message.answer("Оберіть монету зі списку:", reply_markup=keyboard)
        except Exception as e:
            await message.answer(f"❌ Помилка при пошуку: {e}")

@router.callback_query(F.data.startswith("coin_"))
async def select_coin(callback: types.CallbackQuery):
    uid = callback.from_user.id
    coin = callback.data.split("_")[1]
    if coin == "done":
        coins = user_settings.get(uid, {}).get("coins", [])
        await callback.message.answer(f"🔘 Монети обрано: {', '.join(map(str.capitalize, coins))}")
    else:
        if coin not in user_settings[uid]["coins"]:
            user_settings[uid]["coins"].append(coin)
    await callback.answer()

@router.callback_query(F.data == "setup_time")
async def setup_time(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="07:00", callback_data="time_07:00"),
         InlineKeyboardButton(text="09:00", callback_data="time_09:00"),
         InlineKeyboardButton(text="12:00", callback_data="time_12:00")]
    ])
    await callback.message.answer("Оберіть час надсилання:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("time_"))
async def select_time(callback: types.CallbackQuery):
    time = callback.data.split("_")[1]
    user_settings[callback.from_user.id] = user_settings.get(callback.from_user.id, {})
    user_settings[callback.from_user.id]["time"] = time
    await callback.message.answer(f"🕒 Час встановлено на {time} (UTC)")
    await callback.answer()

@router.callback_query(F.data == "setup_timezone")
async def setup_timezone(callback: types.CallbackQuery):
    user_settings[callback.from_user.id] = user_settings.get(callback.from_user.id, {})
    user_settings[callback.from_user.id]["timezone"] = "+03:00"
    await callback.message.answer("🌐 Таймзона встановлена на +03:00")
    await callback.answer()

@router.callback_query(F.data == "reset_settings")
async def reset_settings(callback: types.CallbackQuery):
    user_settings.pop(callback.from_user.id, None)
    await callback.message.answer("🔄 Всі налаштування скинуто. Почнемо знову з /start")
    await callback.answer()

@router.message(Command("test"))
async def test_api(message: types.Message):
    coins = user_settings.get(message.from_user.id, {}).get("coins", ["bitcoin"])
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get("https://api.coingecko.com/api/v3/simple/price", params={
                "ids": ",".join(coins),
                "vs_currencies": "usd"
            }) as resp:
                data = await resp.json()
                text = "\n".join([f"{coin.title()}: ${data[coin]['usd']}" for coin in coins if coin in data])
                await message.answer(f"📈 Поточні ціни:\n{text}")
        except Exception as e:
            await message.answer(f"❌ Помилка при отриманні даних: {e}")

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
