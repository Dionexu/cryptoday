import socket
import sys

def prevent_multiple_instances():
    """Гарантує, що бот не запуститься двічі одночасно (навіть якщо Render намагається)."""
    lock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        lock_id = "aiogram-telegram-bot-lock"
        lock_socket.bind("\0" + lock_id)
    except OSError:
        print("❌ Інша інстанція вже запущена. Вихід.")
        sys.exit(1)
import os
import asyncio
from datetime import datetime, timezone
from aiogram import Bot, Dispatcher

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ BOT_TOKEN не встановлено")
    exit(1)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def main():
    print(f"[{datetime.now(timezone.utc).isoformat()}] 🤖 Стартує бот...")

    await bot.delete_webhook(drop_pending_updates=True)
    print(f"[{datetime.now(timezone.utc).isoformat()}] 🧹 Вебхук видалено")

    try:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ⏳ Старт polling...")
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ❌ Помилка polling: {e}")
    finally:
        print(f"[{datetime.now(timezone.utc).isoformat()}] 🛑 polling завершився")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Зупинено вручну")
    except Exception as e:
        print(f"❗️ Критична помилка: {e}")
