import os
import json
import aiohttp
import asyncio
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

DATA_FILE = "user_data.json"
POPULAR_TOKENS = ['btc', 'eth', 'solana', 'ton', 'dogecoin', 'link', 'ada', 'dot', 'matic', 'arb']

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

async def fetch_price(symbol):
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={symbol}&vs_currencies=usd"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            return data.get(symbol, {}).get("usd", "N/A")

async def search_token(query):
    url = f"https://api.coingecko.com/api/v3/search?query={query}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            result = await resp.json()
            coins = result.get("coins", [])
            if coins:
                return coins[0]["id"], coins[0]["name"]
    return None, None

@dp.message_handler(commands=["start"])
async def start_cmd(message: types.Message):
    user_id = str(message.chat.id)
    data = load_data()
    data[user_id] = {"tokens": [], "time": None}
    save_data(data)

    kb = InlineKeyboardMarkup(row_width=2)
    for token in POPULAR_TOKENS:
        kb.insert(InlineKeyboardButton(token.upper(), callback_data=f"add_{token}"))
    await message.answer("👋 Вибери до 5 монет:", reply_markup=kb)
    await message.answer("🔎 Або напиши скорочення монети (наприклад: `arb`) щоб знайти її через пошук.")

@dp.message_handler(commands=["settime"])
async def set_time(message: types.Message):
    await message.answer("🕐 Напиши час сповіщення у форматі `09:00`, `18:30` і т.д.")

@dp.message_handler(commands=["reset"])
async def reset_cmd(message: types.Message):
    user_id = str(message.chat.id)
    data = load_data()
    data[user_id] = {"tokens": [], "time": None}
    save_data(data)
    await message.answer("♻️ Дані скинуто. Введи /start щоб почати знову.")

@dp.message_handler()
async def handle_text(message: types.Message):
    user_id = str(message.chat.id)
    text = message.text.strip().lower()
    data = load_data()

    if user_id not in data:
        data[user_id] = {"tokens": [], "time": None}

    if ":" in text:
        data[user_id]["time"] = text
        save_data(data)
        await message.answer(f"✅ Час встановлено на {text}")
        return

    if text.isalpha():
        token_id, token_name = await search_token(text)
        if not token_id:
            await message.answer("❌ Монету не знайдено.")
            return
        if len(data[user_id]["tokens"]) >= 5:
            await message.answer("❗ Ти вже вибрав 5 монет.")
            return
        if token_id in data[user_id]["tokens"]:
            await message.answer("ℹ️ Ця монета вже вибрана.")
            return
        data[user_id]["tokens"].append(token_id)
        save_data(data)
        await message.answer(f"✅ Додано: {token_name} ({token_id})")

@dp.callback_query_handler(lambda c: c.data.startswith("add_"))
async def add_token_callback(callback_query: types.CallbackQuery):
    user_id = str(callback_query.from_user.id)
    token = callback_query.data.replace("add_", "")
    data = load_data()
    if user_id not in data:
        data[user_id] = {"tokens": [], "time": None}
    if token in data[user_id]["tokens"]:
        await callback_query.answer("Вже вибрано")
        return
    if len(data[user_id]["tokens"]) >= 5:
        await callback_query.answer("Вибрано 5 монет")
        return
    data[user_id]["tokens"].append(token)
    save_data(data)
    await callback_query.answer(f"Додано {token.upper()}")
    await bot.send_message(user_id, f"✅ Додано монету: {token.upper()}")

async def daily_summary():
    while True:
        now = datetime.now().strftime("%H:%M")
        data = load_data()
        for user_id, info in data.items():
            if info.get("time") == now and info.get("tokens"):
                prices = []
                for token in info["tokens"]:
                    price = await fetch_price(token)
                    prices.append(f"{token.upper()} = ${price}")
                msg = "📊 Щоденна сводка:\n" + "\n".join(prices)
                try:
                    await bot.send_message(user_id, msg)
                except:
                    pass
        await asyncio.sleep(60)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(daily_summary())
    executor.start_polling(dp, skip_updates=True)