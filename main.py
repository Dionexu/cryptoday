import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.enums.parse_mode import ParseMode
from aiogram.filters import Command
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

BOT_TOKEN = "8006649444:AAFa1DsYuT8riikAqv6wUz3Qs_IC5KNotIw"
WEBHOOK_SECRET = "abc123"
WEBHOOK_PATH = f"/webhook/{WEBHOOK_SECRET}"
BASE_WEBHOOK_URL = "https://bot-b14f.onrender.com"
WEBHOOK_URL = BASE_WEBHOOK_URL + WEBHOOK_PATH

ADMIN_IDS = [123456789]  # Замінити на справжній Telegram ID

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# ======= СТАРТ =======
@dp.message(Command("start"))
async def start_handler(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Обрати монети", callback_data="select_coins")]
    ])
    await message.answer("👋 Вітаю! Почнемо налаштування моніторингу:", reply_markup=kb)

# ======= ВИБІР МОНЕТ =======
@dp.callback_query(F.data == "select_coins")
async def choose_coins(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="BTC", callback_data="coin_btc")],
        [InlineKeyboardButton(text="ETH", callback_data="coin_eth")],
        [InlineKeyboardButton(text="✅ Завершити", callback_data="coins_done")]
    ])
    await callback.message.edit_text("🪙 Обери монети для моніторингу:", reply_markup=kb)

# ======= ЗБЕРЕЖЕННЯ МОНЕТ =======
user_config = {}

@dp.callback_query(lambda c: c.data.startswith("coin_"))
async def add_coin(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    coin = callback.data.replace("coin_", "")
    if user_id not in user_config:
        user_config[user_id] = {"coins": []}
    if coin not in user_config[user_id]["coins"]:
        user_config[user_id]["coins"].append(coin)
    await callback.answer(f"{coin.upper()} додано ✅")

@dp.callback_query(F.data == "coins_done")
async def coins_done(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏰ Частота оновлень", callback_data="set_frequency")]
    ])
    await callback.message.edit_text("✅ Монети збережено. Тепер обери частоту оновлень:", reply_markup=kb)

# ======= ЧАСТОТА ОНОВЛЕНЬ =======
@dp.callback_query(F.data == "set_frequency")
async def choose_frequency(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Кожні 6 год", callback_data="freq_6h")],
        [InlineKeyboardButton(text="Кожні 12 год", callback_data="freq_12h")],
        [InlineKeyboardButton(text="Кожні 24 год", callback_data="freq_24h")]
    ])
    await callback.message.edit_text("📅 Обери частоту отримання даних:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("freq_"))
async def save_frequency(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    freq = callback.data.replace("freq_", "")
    user_config[user_id]["frequency"] = freq
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌍 Часовий пояс", callback_data="set_timezone")]
    ])
    await callback.message.edit_text(f"✅ Частоту встановлено: {freq} год.\nТепер обери часовий пояс:", reply_markup=kb)

# ======= ЧАСОВИЙ ПОЯС =======
@dp.callback_query(F.data == "set_timezone")
async def choose_timezone(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="GMT+2", callback_data="tz_2")],
        [InlineKeyboardButton(text="GMT+3", callback_data="tz_3")],
        [InlineKeyboardButton(text="GMT+4", callback_data="tz_4")]
    ])
    await callback.message.edit_text("🕒 Обери часовий пояс:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("tz_"))
async def save_timezone(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    tz = callback.data.replace("tz_", "")
    user_config[user_id]["timezone"] = tz
    await callback.message.edit_text(f"✅ Налаштування завершено! Моніторинг активовано.")

# ======= РОЗСИЛКА ДЛЯ АДМІНІВ =======
async def notify_admins(text: str):
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, f"📢 <b>Адмін-розсилка:</b>\n{text}")
        except Exception as e:
            print(f"Не вдалося надіслати адміну {admin_id}: {e}")

# ======= ЗАПУСК =======
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
    web.run_app(create_app(), port=10000)
