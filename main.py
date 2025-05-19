import os
import logging
import asyncio
from aiohttp import web

from aiogram import Bot, Dispatcher, Router, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.webhook.aiohttp_server import setup_application

# Настройка логирования для вывода информации в консоль
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s", # Более подробный формат логов
)
logger = logging.getLogger(__name__) # Получаем логгер для текущего модуля

# --- Загрузка переменных окружения ---
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    logger.critical("CRITICAL: No BOT_TOKEN provided. Exiting.")
    raise RuntimeError("No BOT_TOKEN provided. Задайте BOT_TOKEN в переменных окружения.")

WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
if not WEBHOOK_HOST:
    logger.critical("CRITICAL: No WEBHOOK_HOST provided. Exiting.")
    raise RuntimeError("No WEBHOOK_HOST provided. Задайте WEBHOOK_HOST в переменных окружения.")

# Убедимся, что WEBHOOK_HOST начинается с https://
if not WEBHOOK_HOST.startswith(("http://", "https://")):
    WEBHOOK_HOST = "https://" + WEBHOOK_HOST
    logger.warning(f"WEBHOOK_HOST did not have a scheme, prepended https://. New host: {WEBHOOK_HOST}")

# WEBHOOK_PATH: Путь для вебхука. Используем ID бота для уникальности.
# TOKEN.split(':')[0] извлекает ID бота из полного токена.
WEBHOOK_PATH = f"/webhook/{TOKEN.split(':')[0]}" # Убрал os.getenv, чтобы путь был всегда таким
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# PORT: Render предоставляет переменную PORT автоматически.
# Используем 3000 по умолчанию, если запускаем локально и PORT не задан.
PORT = int(os.getenv("PORT", "3000"))

# --- Инициализация Aiogram ---
bot = Bot(TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
router = Router() # Создаем экземпляр роутера для обработки сообщений

# --- ОБРАБОТЧИКИ КОМАНД И СООБЩЕНИЙ ---
# Сюда вы будете добавлять свои функции

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    logger.info(f"User {message.from_user.id} ({message.from_user.full_name}) triggered /start command.")
    try:
        await message.answer(
            f"Привет, {message.from_user.full_name}!\n"
            "Я твой бот, готовый к работе.\n"
            "Пока я умею только это, но ты можешь научить меня новому!"
        )
        logger.info(f"Successfully replied to /start for user {message.from_user.id}")
    except Exception as e:
        logger.error(f"Error in cmd_start for user {message.from_user.id}: {e}")

# ПРИМЕР: Обработчик для команды /help
# @router.message(Command("help"))
# async def cmd_help(message: types.Message):
#     logger.info(f"User {message.from_user.id} triggered /help command.")
#     help_text = (
#         "Это справочное сообщение.\n"
#         "Доступные команды:\n"
#         "/start - начало работы\n"
#         "/help - эта справка\n"
#         # ... добавьте сюда описание других ваших команд ...
#     )
#     await message.answer(help_text)

# МЕСТО ДЛЯ ВАШИХ ДРУГИХ ОБРАБОТЧИКОВ:
# Например, для выбора монет, настройки частоты, часовых поясов.
# Они будут выглядеть похоже:
# @router.message(Command("settings"))
# async def cmd_settings(message: types.Message):
#     # ваша логика для настроек
#     await message.answer("Открываю меню настроек...")
#
# @router.message(F.text == "Выбрать монету") # Пример обработчика текста или callback-кнопок
# async def handle_select_coin_text(message: types.Message):
#     # ваша логика
#     await message.answer("Какую монету вы хотите выбрать?")
#
# И так далее...

# --- Функции запуска и остановки вебхука ---
async def on_startup(bot_instance: Bot, dispatcher: Dispatcher): # Передаем и dispatcher
    webhook_info = await bot_instance.get_webhook_info()
    if webhook_info.url != WEBHOOK_URL: # Устанавливаем вебхук, только если он еще не установлен или URL другой
        await bot_instance.set_webhook(
            url=WEBHOOK_URL,
            allowed_updates=dispatcher.resolve_used_update_types(), # Отправлять только те типы обновлений, которые используются
            drop_pending_updates=True # Пропустить накопленные обновления (рекомендуется)
        )
        logger.info(f"🌐 Webhook SET to: {WEBHOOK_URL}")
    else:
        logger.info(f"🌐 Webhook already set to: {WEBHOOK_URL}")
    
    me = await bot_instance.get_me()
    logger.info(f"Bot @{me.username} (ID: {me.id}) started!")

async def on_shutdown(bot_instance: Bot):
    logger.info("Shutting down bot...")
    # Можно удалить вебхук при остановке, но это необязательно,
    # особенно если URL вебхука не меняется.
    # Если Render часто перезапускает сервис, постоянное удаление/установка может быть излишним.
    # Но для чистоты эксперимента оставим:
    try:
        await bot_instance.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhook deleted successfully.")
    except Exception as e:
        logger.error(f"Error deleting webhook: {e}")

    await bot_instance.session.close()
    logger.info("💤 Bot session closed.")

# --- Основная функция для запуска бота ---
async def main():
    # Включаем роутер в диспетчер. Все обработчики из router станут активны.
    dp.include_router(router)

    # Регистрируем функции, которые выполнятся при запуске и остановке бота.
    # Передаем bot и dp в on_startup через аргументы kwargs для setup_application
    # или напрямую, если регистрируем для dp.
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Создаем веб-приложение aiohttp
    app = web.Application()

    # Передаем нужные данные в обработчики startup/shutdown через workflow_data
    # В данном случае, bot_instance будет доступен как аргумент в on_startup и on_shutdown
    workflow_data = {
        "bot_instance": bot,
        "dispatcher": dp # Передаем dispatcher в on_startup для allowed_updates
    }

    # Настраиваем маршруты aiogram для веб-приложения aiohttp
    # Это связывает aiogram с веб-сервером для приема обновлений от Telegram
    setup_application(app, dp, **workflow_data)

    # Запускаем веб-сервер
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=PORT) # Слушаем на всех интерфейсах
    logger.info(f"🚀 Starting web server on http://0.0.0.0:{PORT}")
    await site.start()

    # Держим приложение живым (пока не будет остановлено вручную или системой)
    try:
        await asyncio.Event().wait()
    finally:
        logger.info("Application is shutting down...")
        await runner.cleanup() # Корректное завершение работы AppRunner
        logger.info("Application has been shut down.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped manually (KeyboardInterrupt/SystemExit)!")
    except RuntimeError as e:
        # Эта ошибка уже логируется выше при проверке TOKEN и WEBHOOK_HOST
        # logger.error(f"Critical runtime error during startup: {e}")
        pass # Уже залогировано
    except Exception as e:
        logger.exception(f"An unhandled exception occurred at the top level: {e}")
