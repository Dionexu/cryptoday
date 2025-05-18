
import os
import json
import aiohttp
import asyncio
from datetime import datetime
import pytz

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

BOT_TOKEN = "8006649444:AAFa1DsYuT8riikAqv6wUz3Qs_IC5KNotIw"
WEBHOOK_SECRET = "abc123"
WEBHOOK_PATH = f"/webhook/{WEBHOOK_SECRET}"
BASE_WEBHOOK_URL = "https://bot-b14f.onrender.com"
WEBHOOK_URL = BASE_WEBHOOK_URL + WEBHOOK_PATH

DATA_FILE = "user_data.json"
ADMIN_IDS = [696165311, 7923967086]
TOKEN_MAP = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "ARB": "arbitrum"
}

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_default_user():
    return {
        "tokens": [],
        "frequency": None,
        "timezone": None
    }

@dp.message(CommandStart())
async def handle_start(message: Message):
    user_id = str(message.chat.id)
    data = load_data()
    if user_id not in data:
        data[user_id] = get_default_user()
        save_data(data)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Обрати монети", callback_data="select_tokens")],
        [InlineKeyboardButton(text="Частота розсилки", callback_data="set_freq")],
        [InlineKeyboardButton(text="Часовий пояс", callback_data="set_tz")]
    ])
    await message.answer("👋 Привіт! Обери, з чого почнемо:", reply_markup=kb)

@dp.callback_query(lambda c: c.data == "select_tokens")
async def select_tokens(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=key, callback_data=f"add_{key}")]
        for key in TOKEN_MAP.keys()
    ])
    await callback.message.answer("Оберіть монети (до 5):", reply_markup=kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("add_"))
async def add_token(callback: types.CallbackQuery):
    token = callback.data.split("_")[1]
    user_id = str(callback.from_user.id)
    data = load_data()
    user = data.get(user_id, get_default_user())
    if token in user["tokens"]:
        await callback.answer("Вже додано")
    elif len(user["tokens"]) >= 5:
        await callback.answer("Максимум 5 монет")
    else:
        user["tokens"].append(token)
        data[user_id] = user
        save_data(data)
        await callback.message.answer(f"✅ Додано {token}")
        await callback.answer()

@dp.callback_query(lambda c: c.data == "set_freq")
async def set_freq(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 раз в день", callback_data="freq_daily")],
        [InlineKeyboardButton(text="Щогодини", callback_data="freq_hourly")]
    ])
    await callback.message.answer("Оберіть частоту:", reply_markup=kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("freq_"))
async def save_freq(callback: types.CallbackQuery):
    freq = callback.data.split("_")[1]
    user_id = str(callback.from_user.id)
    data = load_data()
    user = data.get(user_id, get_default_user())
    user["frequency"] = freq
    data[user_id] = user
    save_data(data)
    await callback.message.answer(f"✅ Частоту встановлено: {freq}")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "set_tz")
async def set_timezone(callback: types.CallbackQuery):
    await callback.message.answer("Введіть назву вашого часового поясу (наприклад, Europe/Kyiv):")
    await callback.answer()

@dp.message()
async def handle_text(message: Message):
    user_id = str(message.chat.id)
    text = message.text.strip()
    data = load_data()
    user = data.get(user_id, get_default_user())

    # Часовий пояс
    if "/" in text:
        try:
            pytz.timezone(text)
            user["timezone"] = text
            data[user_id] = user
            save_data(data)
            await message.answer(f"✅ Часовий пояс встановлено: {text}")
            return
        except:
            await message.answer("❌ Невірний часовий пояс")
            return

    # Розсилка для адмінів
    if message.from_user.id in ADMIN_IDS:
        sent = 0
        for uid in data:
            if uid != user_id:
                try:
                    await bot.send_message(uid, f"📢 {text}")
                    sent += 1
                except:
                    pass
        await message.answer(f"Розіслано {sent} користувачам.")

async def fetch_prices(tokens):
    ids = ",".join(TOKEN_MAP[t] for t in tokens if t in TOKEN_MAP)
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.json()

async def price_notifier():
    while True:
        data = load_data()
        for uid, cfg in data.items():
            if cfg.get("tokens") and cfg.get("frequency") == "daily":
                prices = await fetch_prices(cfg["tokens"])
                msg = "📈 Поточні ціни:"
" + "\n".join(
                    [f"{t}: ${prices.get(TOKEN_MAP[t], {}).get('usd', 'N/A')}" for t in cfg["tokens"]]
                )
                try:
                    await bot.send_message(int(uid), msg)
                except:
                    pass
        await asyncio.sleep(3600 * 24)  # раз на день

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

async def main():
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 10000)
    await site.start()
    asyncio.create_task(price_notifier())
    print("✅ Сервер запущено. Очікуємо webhook...")
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
