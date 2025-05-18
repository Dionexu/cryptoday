import os
import asyncio
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v3: main.py почав виконуватися. (Мінімальна версія для діагностики TelegramConflictError)")

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = os.getenv("BOT_TOKEN") 
PLACEHOLDER_TOKEN = "ВАШ_БОТ_ТОКЕН_ТУТ_ЗАМЕНИТЕ_ИЛИ_УСТАНОВИТЕ_ПЕРЕМЕННУЮ" 

if not BOT_TOKEN or BOT_TOKEN == PLACEHOLDER_TOKEN:
    print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v3: КРИТИЧНО: BOT_TOKEN не встановлено або є плейсхолдером.")
    exit(1) 

print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v3: BOT_TOKEN отримано.")

try:
    bot = Bot(token=BOT_TOKEN)
    print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v3: Об'єкт Bot успішно створено.")
except Exception as e:
    print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v3: КРИТИЧНА ПОМИЛКА при створенні об'єкта Bot: {e}")
    exit(1)

dp = Dispatcher()
print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v3: Об'єкт Dispatcher успішно створено.")

# --- МІНІМАЛЬНИЙ ОБРОБНИК КОМАНДИ ---
@dp.message(Command("ping"))
async def send_pong(message: types.Message):
    print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v3: Отримано команду /ping від {message.from_user.id}")
    try:
        await message.answer("pong (minimal test version v3)")
        print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v3: Відповідь 'pong' надіслано.")
    except Exception as e:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v3: Помилка при відправці 'pong': {e}")

# --- ЗАПУСК БОТА ---
async def main(): 
    print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v3: Початок функції main.")
    
    # --- ДОБАВЛЕНО ДЛЯ ТЕСТА v3: Попытка удалить вебхук и увеличенная задержка ---
    print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v3: Спроба видалити вебхук, якщо він є...")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v3: Вебхук (можливо) видалено.")
    except Exception as e_wh:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v3: Помилка при спробі видалити вебхук: {e_wh}")
    
    print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v3: Затримка 10 секунд перед start_polling...")
    await asyncio.sleep(10) # Увеличиваем задержку
    # --- КОНЕЦ ДОБАВЛЕННОГО ДЛЯ ТЕСТА v3 ---

    print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v3: Бот запускається (dp.start_polling)...")
    try:
        await dp.start_polling(bot, skip_updates=True)
        print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v3: dp.start_polling завершився штатно (без винятків у цьому try-блоці).")
    except asyncio.CancelledError:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v3: dp.start_polling було скасовано (CancelledError).")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v3: КРИТИЧНА ПОМИЛКА В START_POLLING: {e}")
        print(f"[{datetime.now(timezone.utc).isoformat()}] Тип помилки: {type(e).__name__}")
        import traceback
        traceback.print_exc() 
    finally:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v3: Блок finally - зупинка бота.")
        if bot.session and hasattr(bot.session, 'closed') and not bot.session.closed:
            print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v3: Закриття сесії бота...")
            await bot.session.close()
            print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v3: Сесію бота закрито.")
        elif bot.session and not hasattr(bot.session, 'closed'):
             print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v3: Сесія бота не має атрибуту 'closed'. Спроба закрити...")
             await bot.session.close() 
             print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v3: Сесію бота (можливо) закрито.")
        else:
            print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v3: Сесія бота відсутня або вже закрита.")
            
        print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v3: Бот остаточно зупинено. Скрипт завершує роботу.")

if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v3: __main__: Запуск asyncio.run(main()).")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v3: __main__: Зупинка бота вручну (Ctrl+C).")
    except Exception as e: 
        print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v3: __main__: Виникла неперехоплена критична помилка під час запуску asyncio.run(main()): {e}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ТЕСТОВИЙ СКРИПТ v3: __main__: Скрипт main.py остаточно завершив роботу.")
