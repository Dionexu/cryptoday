import os
import json
import aiohttp
import asyncio
from datetime import datetime, timezone, timedelta, time
import pytz

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.filters import Command
from aiogram.utils.markdown import hcode

print(f"[{datetime.now(timezone.utc).isoformat()}] Скрипт main.py почав виконуватися.")

# --- КОНФІГУРАЦІЯ ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
PLACEHOLDER_TOKEN = "ВАШ_БОТ_ТОКЕН_ТУТ_ЗАМЕНИТЕ_ИЛИ_УСТАНОВИТЕ_ПЕРЕМЕННУЮ"

if not BOT_TOKEN or BOT_TOKEN == PLACEHOLDER_TOKEN:
    print(f"[{datetime.now(timezone.utc).isoformat()}] ❌ КРИТИЧНО: BOT_TOKEN не встановлено або є плейсхолдером.")
    exit(1)

# --- ІНІЦІАЛІЗАЦІЯ БОТА ТА ДИСПЕТЧЕРА ---
try:
    bot = Bot(token=BOT_TOKEN)
    print(f"[{datetime.now(timezone.utc).isoformat()}] ✅ Об'єкт Bot створено.")
except Exception as e:
    print(f"[{datetime.now(timezone.utc).isoformat()}] ❌ ПОМИЛКА: Не вдалося створити Bot: {e}")
    exit(1)

dp = Dispatcher()
print(f"[{datetime.now(timezone.utc).isoformat()}] ✅ Об'єкт Dispatcher створено.")

# --- ГОЛОВНА ФУНКЦІЯ ---
async def main():
    print(f"[{datetime.now(timezone.utc).isoformat()}] ▶️ main: Початок функції main.")

    # ВАЖЛИВО: Зняти вебхук — вирішує помилку "Conflict"
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        print(f"[{datetime.now(timezone.utc).isoformat()}] 🔧 Вебхук успішно видалено.")
    except Exception as e:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ⚠️ ПОПЕРЕДЖЕННЯ: Не вдалося видалити вебхук: {e}")

    # Тут можна реєструвати хендлери, якщо потрібно
    print(f"[{datetime.now(timezone.utc).isoformat()}] 🧩 main: ХЕНДЛЕРИ ЗАРЕЄСТРОВАНІ.")

    # Запуск polling
    print(f"[{datetime.now(timezone.utc).isoformat()}] 🚀 Запуск polling...")
    try:
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ❌ ПОМИЛКА в start_polling: {e}")
        raise

# --- ЗАПУСК ---
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"[{datetime.now(timezone.utc).isoformat()}] 🛑 Зупинка вручну (Ctrl+C)")
    except Exception as e:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ❗️ Критична помилка під час запуску: {e}")
