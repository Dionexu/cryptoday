import os
import asyncio
from datetime import datetime, timezone
from aiogram import Bot, Dispatcher
from aiohttp import web

BOT_TOKEN = os.getenv("BOT_TOKEN")
PLACEHOLDER_TOKEN = "ВАШ_БОТ_ТОКЕН_ТУТ_ЗАМЕНИТЕ_ИЛИ_УСТАНОВИТЕ_ПЕРЕМЕННУЮ"

if not BOT_TOKEN or BOT_TOKEN == PLACEHOLDER_TOKEN:
    print(f"[{datetime.now(timezone.utc).isoformat()}] ❌ BOT_TOKEN не встановлено або є плейсхолдером.")
    exit(1)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- Health-check для Render ---
async def handle_healthz(request):
    return web.Response(text="OK", status=200)

async def start_web_server():
    app = web.Application()
    app.router.add_get("/healthz", handle_healthz)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 10000)
    await site.start()
    print(f"[{datetime.now(timezone.utc).isoformat()}] 🌐 HTTP-сервер запущено на порту 10000 (Render health check)")

# --- Telegram polling ---
async def start_bot():
    await bot.delete_webhook(drop_pending_updates=True)
    print(f"[{datetime.now(timezone.utc).isoformat()}] 🤖 Вебхук видалено. Стартує polling...")
    await dp.start_polling(bot, skip_updates=True)

# --- Головна точка входу ---
async def main():
    print(f"[{datetime.now(timezone.utc).isoformat()}] 🚀 Стартуємо main()")
    await asyncio.gather(
        start_web_server(),
        start_bot()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"[{datetime.now(timezone.utc).isoformat()}] 🛑 Зупинка вручну (Ctrl+C)")
    except Exception as e:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ❗️ Критична помилка: {e}")
