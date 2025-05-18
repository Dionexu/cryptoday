import os
import asyncio
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ: main.py почав виконуватися. (Мінімальна версія для діагностики TelegramConflictError)")

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = os.getenv("BOT_TOKEN") 
PLACEHOLDER_TOKEN = "ВАШ_БОТ_ТОКЕН_ТУТ_ЗАМЕНИТЕ_ИЛИ_УСТАНОВИТЕ_ПЕРЕМЕННУЮ" 

if not BOT_TOKEN or BOT_TOKEN == PLACEHOLDER_TOKEN:
    print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ: КРИТИЧНО: BOT_TOKEN не встановлено або є плейсхолдером.")
    exit(1) 

print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ: BOT_TOKEN отримано.")

try:
    bot = Bot(token=BOT_TOKEN)
    print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ: Об'єкт Bot успішно створено.")
except Exception as e:
    print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ: КРИТИЧНА ПОМИЛКА при створенні об'єкта Bot: {e}")
    exit(1)

dp = Dispatcher()
print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ: Об'єкт Dispatcher успішно створено.")

# --- МІНІМАЛЬНИЙ ОБРОБНИК КОМАНДИ ---
@dp.message(Command("ping"))
async def send_pong(message: types.Message):
    print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ: Отримано команду /ping від {message.from_user.id}")
    try:
        await message.answer("pong (minimal test version)")
        print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ: Відповідь 'pong' надіслано.")
    except Exception as e:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ: Помилка при відправці 'pong': {e}")

# --- ЗАПУСК БОТА ---
async def main(): 
    print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ: Початок функції main.")
    
    print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ: Бот запускається (dp.start_polling)...")
    try:
        # Убираем создание scheduler_task, так как планировщик отключен для теста
        await dp.start_polling(bot, skip_updates=True)
        print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ: dp.start_polling завершився штатно (без винятків у цьому try-блоці).")
    except asyncio.CancelledError:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ: dp.start_polling було скасовано (CancelledError).")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ: КРИТИЧНА ПОМИЛКА В START_POLLING: {e}")
        print(f"[{datetime.now(timezone.utc).isoformat()}] Тип помилки: {type(e).__name__}")
        import traceback
        traceback.print_exc() 
    finally:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ: Блок finally - зупинка бота.")
        # Закрытие сессии бота, если она была открыта
        if bot.session and hasattr(bot.session, 'closed') and not bot.session.closed:
            print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ: Закриття сесії бота...")
            await bot.session.close()
            print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ: Сесію бота закрито.")
        elif bot.session and not hasattr(bot.session, 'closed'):
             print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ: Сесія бота не має атрибуту 'closed'. Спроба закрити...")
             await bot.session.close() 
             print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ: Сесію бота (можливо) закрито.")
        else:
            print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ: Сесія бота відсутня або вже закрита.")
            
        print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ: Бот остаточно зупинено. Скрипт завершує роботу.")

if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ: __main__: Запуск asyncio.run(main()).")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ: __main__: Зупинка бота вручну (Ctrl+C).")
    except Exception as e: 
        print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ: __main__: Виникла неперехоплена критична помилка під час запуску asyncio.run(main()): {e}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ: __main__: Скрипт main.py остаточно завершив роботу.")
