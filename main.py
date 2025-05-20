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
    user_settings[callback.from_user.id] = {"coins": []}
    await callback.message.answer("Введіть назву або ID монети англійською (наприклад, bitcoin, solana, dogecoin). Введіть 'готово', коли завершите вибір.")
    await callback.answer()


@router.callback_query(F.data == "reset_settings")
async def handle_reset(callback: types.CallbackQuery):
    user_settings.pop(callback.from_user.id, None)
    await callback.message.answer("🔄 Налаштування скинуто. Ви можете почати заново командою /start або обрати монети.")
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
        await callback.message.answer("❌ Помилка при отриманні даних.")
        logger.error(f"Callback price error: {e}")
    await callback.answer()


@router.message(F.text.regexp(r"^[a-z0-9\-]+$"))
async def handle_coin_text(message: types.Message):
    user_id = message.from_user.id
    coin = message.text.lower()

    if coin == "готово":
        coins = user_settings.get(user_id, {}).get("coins", [])
        if coins:
            await message.answer(f"✅ Ви обрали: {', '.join(coins).upper()}")
        else:
            await message.answer("⚠️ Ви ще не вибрали жодної монети.")
        return

    async with aiohttp.ClientSession() as session:
        url = "https://api.coingecko.com/api/v3/coins/list"
        async with session.get(url) as resp:
            all_coins = await resp.json()
            logger.warning(f"[DEBUG] all_coins (partial): {str(all_coins)[:500]}")
            if not isinstance(all_coins, list) or not all(isinstance(c, dict) for c in all_coins):
                await message.answer("❌ Помилка отримання списку монет. Спробуйте пізніше.")
                return
        id_map = {c['id']: c['id'] for c in all_coins}
        symbol_map = {c['symbol']: c['id'] for c in all_coins}
        valid_ids = set(id_map.keys()).union(symbol_map.keys())

    if coin not in valid_ids:
        await message.answer("❌ Такої монети не знайдено. Спробуйте ще раз.")
        return

    # Перетворити символ у ID, якщо потрібно
    if coin in symbol_map:
        coin = symbol_map[coin]

    user_data = user_settings.setdefault(user_id, {"coins": []})
    coins = user_data["coins"]

    if coin in coins:
        await message.answer("ℹ️ Цю монету вже додано.")
    elif len(coins) >= 5:
        await message.answer("⚠️ Можна обрати максимум 5 монет.")
    else:
        coins.append(coin)
        await message.answer(f"✅ Додано {coin.upper()} ({len(coins)}/5)")
@router.message(Command("start"))
async def cmd_start(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🕒 Обрати частоту", callback_data="select_frequency")],
        [InlineKeyboardButton(text="📊 Дивитися ціни", callback_data="get_prices")],
        [InlineKeyboardButton(text="⚙️ Обрати монети", callback_data="select_coins")],
        [InlineKeyboardButton(text="🔄 Скинути налаштування", callback_data="reset_settings")]
    ])
    await message.answer("Привіт! Натисни кнопку нижче, щоб отримати ціни.", reply_markup=keyboard)




async def on_startup(bot_instance: Bot):
    await bot_instance.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
    me = await bot_instance.get_me()
    logger.info(f"Bot @{me.username} (ID: {me.id}) started with webhook: {WEBHOOK_URL}")

async def on_shutdown(bot_instance: Bot):
    await bot_instance.session.close()

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


async def healthcheck(request):
    return web.Response(text="OK")


async def main():
    app = web.Application()
    webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    app.router.add_route("POST", WEBHOOK_PATH, webhook_handler.handle)
    setup_application(app, dp, bot=bot, on_startup=on_startup, on_shutdown=on_shutdown)
    app.router.add_get("/", healthcheck)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=PORT)
    logger.info(f"🚀 Starting web server on http://0.0.0.0:{PORT}")
    await site.start()

    asyncio.create_task(price_notifier())
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped manually (KeyboardInterrupt/SystemExit)!")
