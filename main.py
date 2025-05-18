import os
import asyncio
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v2: main.py почав виконуватися. (Мінімальна версія для діагностики TelegramConflictError)")

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = os.getenv("BOT_TOKEN") 
PLACEHOLDER_TOKEN = "ВАШ_БОТ_ТОКЕН_ТУТ_ЗАМЕНИТЕ_ИЛИ_УСТАНОВИТЕ_ПЕРЕМЕННУЮ" 

if not BOT_TOKEN or BOT_TOKEN == PLACEHOLDER_TOKEN:
    print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v2: КРИТИЧНО: BOT_TOKEN не встановлено або є плейсхолдером.")
    exit(1) 

print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v2: BOT_TOKEN отримано.")

try:
    bot = Bot(token=BOT_TOKEN)
    print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v2: Об'єкт Bot успішно створено.")
except Exception as e:
    print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v2: КРИТИЧНА ПОМИЛКА при створенні об'єкта Bot: {e}")
    exit(1)

dp = Dispatcher()
print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v2: Об'єкт Dispatcher успішно створено.")

# --- МІНІМАЛЬНИЙ ОБРОБНИК КОМАНДИ ---
@dp.message(Command("ping"))
async def send_pong(message: types.Message):
    print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v2: Отримано команду /ping від {message.from_user.id}")
    try:
        await message.answer("pong (minimal test version v2)")
        print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v2: Відповідь 'pong' надіслано.")
    except Exception as e:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v2: Помилка при відправці 'pong': {e}")

# --- ЗАПУСК БОТА ---
async def main(): 
    print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v2: Початок функції main.")
    
    # --- ДОБАВЛЕНО ДЛЯ ТЕСТА: Попытка закрыть предыдущую сессию и добавить задержку ---
    print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v2: Спроба закрити попередню сесію, якщо вона існує...")
    if bot.session and hasattr(bot.session, 'closed') and not bot.session.closed:
        try:
            await bot.session.close()
            print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v2: Попередня сесія (можливо) закрита.")
        except Exception as e_close:
            print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v2: Помилка при спробі закрити попередню сесію: {e_close}")
    
    print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v2: Затримка 5 секунд перед start_polling...")
    await asyncio.sleep(5) # Добавляем небольшую задержку
    # --- КОНЕЦ ДОБАВЛЕННОГО ДЛЯ ТЕСТА ---

    print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v2: Бот запускається (dp.start_polling)...")
    try:
        await dp.start_polling(bot, skip_updates=True)
        print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v2: dp.start_polling завершився штатно (без винятків у цьому try-блоці).")
    except asyncio.CancelledError:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v2: dp.start_polling було скасовано (CancelledError).")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v2: КРИТИЧНА ПОМИЛКА В START_POLLING: {e}")
        print(f"[{datetime.now(timezone.utc).isoformat()}] Тип помилки: {type(e).__name__}")
        import traceback
        traceback.print_exc() 
    finally:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v2: Блок finally - зупинка бота.")
        if bot.session and hasattr(bot.session, 'closed') and not bot.session.closed:
            print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v2: Закриття сесії бота...")
            await bot.session.close()
            print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v2: Сесію бота закрито.")
        elif bot.session and not hasattr(bot.session, 'closed'):
             print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v2: Сесія бота не має атрибуту 'closed'. Спроба закрити...")
             await bot.session.close() 
             print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v2: Сесію бота (можливо) закрито.")
        else:
            print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v2: Сесія бота відсутня або вже закрита.")
            
        print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v2: Бот остаточно зупинено. Скрипт завершує роботу.")

if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v2: __main__: Запуск asyncio.run(main()).")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v2: __main__: Зупинка бота вручну (Ctrl+C).")
    except Exception as e: 
        print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v2: __main__: Виникла неперехоплена критична помилка під час запуску asyncio.run(main()): {e}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v2: __main__: Скрипт main.py остаточно завершив роботу.")
