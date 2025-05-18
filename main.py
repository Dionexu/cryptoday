import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "abc123")
BASE_WEBHOOK_URL = os.getenv("WEBHOOK_BASE", "https://bot-b14f.onrender.com")
WEBHOOK_PATH = f"/webhook/{WEBHOOK_SECRET}"
WEBHOOK_URL = BASE_WEBHOOK_URL + WEBHOOK_PATH
PORT = int(os.getenv("PORT", 10000))

ADMIN_IDS = [800664944]  # Вкажи список ID адміністраторів

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

user_settings = {}

coins = ["BTC", "ETH", "VIRTUAL", "PENGU", "TON"]

# Головне меню
@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 Обрати монети", callback_data="choose_coins")],
        [InlineKeyboardButton(text="⏱ Частота надсилання", callback_data="choose_freq")],
        [InlineKeyboardButton(text="🌍 Часовий пояс", callback_data="choose_timezone")]
    ])
    await message.answer("👋 Вітаю! Налаштуй свого бота:", reply_markup=kb)

# Обрати монети
@dp.callback_query(F.data == "choose_coins")
async def show_coin_options(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=coin, callback_data=f"coin_{coin}")] for coin in coins
    ])
    await callback.message.edit_text("🪙 Обери монети:", reply_markup=kb)

@dp.callback_query(F.data.startswith("coin_"))
async def set_coin(callback: CallbackQuery):
    coin = callback.data.split("_")[1]
    uid = str(callback.from_user.id)
    user_settings.setdefault(uid, {})["coin"] = coin
    await callback.message.answer(f"✅ Обрана монета: <b>{coin}</b>")
    await cmd_start(callback.message)

# Частота надсилання
@dp.callback_query(F.data == "choose_freq")
async def choose_frequency(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📬 Щодня", callback_data="freq_daily")],
        [InlineKeyboardButton(text="⏰ Щогодини", callback_data="freq_hourly")],
        [InlineKeyboardButton(text="❌ Вимкнути", callback_data="freq_off")]
    ])
    await callback.message.edit_text("⏱ Обери частоту надсилання:", reply_markup=kb)

@dp.callback_query(F.data.startswith("freq_"))
async def set_frequency(callback: CallbackQuery):
    freq = callback.data.split("_")[1]
    uid = str(callback.from_user.id)
    user_settings.setdefault(uid, {})["frequency"] = freq
    await callback.message.answer(f"✅ Частота надсилання встановлена: <b>{freq}</b>")
    await cmd_start(callback.message)

# Часовий пояс
@dp.callback_query(F.data == "choose_timezone")
async def choose_timezone(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇺🇦 Київ (UTC+3)", callback_data="tz_3")],
        [InlineKeyboardButton(text="🇬🇧 Лондон (UTC+0)", callback_data="tz_0")],
        [InlineKeyboardButton(text="🇺🇸 Нью-Йорк (UTC-5)", callback_data="tz_-5")]
    ])
    await callback.message.edit_text("🌍 Обери свій часовий пояс:", reply_markup=kb)

@dp.callback_query(F.data.startswith("tz_"))
async def set_timezone(callback: CallbackQuery):
    tz = callback.data.split("_")[1]
    uid = str(callback.from_user.id)
    user_settings.setdefault(uid, {})["timezone"] = tz
    await callback.message.answer(f"✅ Часовий пояс встановлено: <b>UTC{tz}</b>")
    await cmd_start(callback.message)

# Розсилка для адміністраторів
async def broadcast_to_admins(text: str):
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            pass

# Webhook startup/shutdown
async def on_startup(app: web.Application):
    await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
    print(f"🚀 Webhook встановлено: {WEBHOOK_URL}")

async def on_shutdown(app: web.Application):
    await bot.delete_webhook()
    print("🧹 Webhook видалено. Бот завершив роботу.")

def create_app():
    app = web.Application()
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp)
    return app

if __name__ == "__main__":
    web.run_app(create_app(), port=PORT)
