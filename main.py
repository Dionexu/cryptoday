import os
import asyncio
import logging
from datetime import datetime, timedelta, timezone
import json # Для сохранения и загрузки настроек
import re # Для валидации времени и часовых поясов

import aiohttp
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.types import Message # InlineKeyboardMarkup, InlineKeyboardButton (пока не используем)
from aiogram.fsm.storage.memory import MemoryStorage # Для FSM, если понадобится в будущем

# --- Настройка логирования ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger(__name__)

# --- Конфигурация бота ---
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Не указан BOT_TOKEN в переменных окружения.")

WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
if not WEBHOOK_HOST:
    raise RuntimeError("Не указан WEBHOOK_HOST в переменных окружения.")

if not WEBHOOK_HOST.startswith(("http://", "https://")):
    WEBHOOK_HOST = "https://" + WEBHOOK_HOST

WEBHOOK_PATH = f"/webhook/{TOKEN.split(':')[0]}" # Можно использовать более секретный путь
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
PORT = int(os.getenv("PORT", "3000")) # Порт по умолчанию 80 или 443 для вебхуков, или 3000/8080 для локального теста

# --- Инициализация бота и диспетчера ---
bot = Bot(TOKEN, parse_mode=ParseMode.HTML)
storage = MemoryStorage() # Пока используем хранилище в памяти для FSM
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# --- Настройки пользователей ---
USER_SETTINGS_FILE = "user_settings.json"
user_settings = {}

def load_user_settings():
    """Загружает настройки пользователей из файла."""
    global user_settings
    try:
        if os.path.exists(USER_SETTINGS_FILE):
            with open(USER_SETTINGS_FILE, "r", encoding="utf-8") as f:
                user_settings = json.load(f)
                # Конвертируем ключи user_id обратно в int, т.к. JSON хранит их как строки
                user_settings = {int(k): v for k, v in user_settings.items()}
                logger.info("Настройки пользователей успешно загружены.")
        else:
            user_settings = {}
            logger.info("Файл настроек не найден, используются настройки по умолчанию (пусто).")
    except Exception as e:
        logger.error(f"Ошибка загрузки настроек пользователей: {e}")
        user_settings = {}

def save_user_settings():
    """Сохраняет настройки пользователей в файл."""
    try:
        with open(USER_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(user_settings, f, indent=4, ensure_ascii=False)
        logger.debug("Настройки пользователей успешно сохранены.")
    except Exception as e:
        logger.error(f"Ошибка сохранения настроек пользователей: {e}")

def get_user_setting(user_id: int, key: str, default=None):
    """Получает настройку для пользователя, создавая запись, если ее нет."""
    if user_id not in user_settings:
        user_settings[user_id] = {}
    return user_settings[user_id].get(key, default)

def set_user_setting(user_id: int, key: str, value):
    """Устанавливает настройку для пользователя."""
    if user_id not in user_settings:
        user_settings[user_id] = {}
    user_settings[user_id][key] = value
    save_user_settings()

# --- Обработчики команд ---

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start."""
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    # Инициализация настроек по умолчанию для нового пользователя, если их нет
    if user_id not in user_settings:
        set_user_setting(user_id, "coins", [])
        set_user_setting(user_id, "frequency", "24h") # По умолчанию раз в 24 часа
        set_user_setting(user_id, "timezone", "+00:00") # По умолчанию UTC
        set_user_setting(user_id, "time", "10:00")      # По умолчанию в 10:00
        set_user_setting(user_id, "sleep", {"start": None, "end": None})
        logger.info(f"Новый пользователь {user_name} (ID: {user_id}). Установлены настройки по умолчанию.")

    await message.answer(
        f"Привет, {user_name}!\n"
        f"Я бот для уведомлений о ценах на криптовалюты.\n\n"
        f"Доступные команды:\n"
        f"/addcoin <название_монеты_coingecko> - добавить монету (например, /addcoin bitcoin)\n"
        f"/removecoin <название_монеты> - удалить монету\n"
        f"/setfrequency <частота> - установить частоту (1h, 2h, 12h, 24h)\n"
        f"/settime <ЧЧ:ММ> - установить время уведомления (для 12h и 24h)\n"
        f"/settimezone <смещение_UTC> - установить часовой пояс (например, +03:00 или -05:00)\n"
        f"/sleepon <ЧЧ:ММ> <ЧЧ:ММ> - установить 'тихий час' (начало конец)\n"
        f"/sleepoff - выключить 'тихий час'\n"
        f"/mysettings - показать текущие настройки\n"
        f"/help - показать это сообщение"
    )

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help."""
    await cmd_start(message) # Просто вызываем /start для отображения списка команд

@router.message(Command("addcoin"))
async def cmd_addcoin(message: Message, command: CommandObject):
    """Добавляет монету в список отслеживаемых."""
    user_id = message.from_user.id
    if command.args is None:
        await message.answer("Пожалуйста, укажите название монеты после команды.\nНапример: /addcoin bitcoin")
        return

    coin_name = command.args.lower().strip()
    if not coin_name:
        await message.answer("Название монеты не может быть пустым.")
        return

    # Проверка монеты через API (опционально, но рекомендуется)
    async with aiohttp.ClientSession() as session:
        try:
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {"ids": coin_name, "vs_currencies": "usd"}
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if not data or coin_name not in data:
                        await message.answer(f"Не удалось найти монету '{coin_name}' на CoinGecko. Проверьте правильность названия.")
                        return
                else:
                    await message.answer(f"Ошибка при проверке монеты '{coin_name}' на CoinGecko (статус: {resp.status}). Попробуйте позже.")
                    return
        except Exception as e:
            logger.error(f"Ошибка API при проверке монеты {coin_name}: {e}")
            await message.answer(f"Произошла ошибка при проверке монеты. Попробуйте позже.")
            return


    coins = get_user_setting(user_id, "coins", [])
    if coin_name not in coins:
        coins.append(coin_name)
        set_user_setting(user_id, "coins", coins)
        await message.answer(f"Монета {coin_name.capitalize()} добавлена в ваш список.")
    else:
        await message.answer(f"Монета {coin_name.capitalize()} уже есть в вашем списке.")

@router.message(Command("removecoin"))
async def cmd_removecoin(message: Message, command: CommandObject):
    """Удаляет монету из списка отслеживаемых."""
    user_id = message.from_user.id
    if command.args is None:
        await message.answer("Пожалуйста, укажите название монеты для удаления.\nНапример: /removecoin bitcoin")
        return

    coin_name = command.args.lower().strip()
    coins = get_user_setting(user_id, "coins", [])
    if coin_name in coins:
        coins.remove(coin_name)
        set_user_setting(user_id, "coins", coins)
        await message.answer(f"Монета {coin_name.capitalize()} удалена из вашего списка.")
    else:
        await message.answer(f"Монеты {coin_name.capitalize()} нет в вашем списке.")

@router.message(Command("setfrequency"))
async def cmd_setfrequency(message: Message, command: CommandObject):
    """Устанавливает частоту уведомлений."""
    user_id = message.from_user.id
    if command.args is None:
        await message.answer("Укажите частоту: 1h, 2h, 12h, 24h.\nНапример: /setfrequency 12h")
        return

    freq = command.args.lower().strip()
    valid_freqs = ["1h", "2h", "12h", "24h"]
    if freq in valid_freqs:
        set_user_setting(user_id, "frequency", freq)
        # Сбросим время последнего уведомления, чтобы логика сработала корректно
        set_user_setting(user_id, "last_notified_at", None)
        if freq == "12h":
            # Устанавливаем второе время для 12-часового интервала, если его нет
            current_time_str = get_user_setting(user_id, "time", "10:00")
            try:
                h, m = map(int, current_time_str.split(':'))
                second_h = (h + 12) % 24
                second_time_str = f"{second_h:02d}:{m:02d}"
                set_user_setting(user_id, "second_time", second_time_str)
                await message.answer(f"Частота установлена на {freq}. Уведомления будут приходить в {current_time_str} и {second_time_str} по вашему времени.")
            except ValueError:
                 await message.answer(f"Частота установлена на {freq}. Пожалуйста, убедитесь, что основное время установлено корректно (/settime).")
        else:
            await message.answer(f"Частота уведомлений установлена на: {freq}.")
    else:
        await message.answer(f"Неверная частота. Допустимые значения: {', '.join(valid_freqs)}.")

def is_valid_time_format(time_str: str) -> bool:
    """Проверяет, соответствует ли строка формату HH:MM."""
    return bool(re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", time_str))

@router.message(Command("settime"))
async def cmd_settime(message: Message, command: CommandObject):
    """Устанавливает время уведомлений (для 12h и 24h)."""
    user_id = message.from_user.id
    if command.args is None:
        await message.answer("Укажите время в формате ЧЧ:ММ.\nНапример: /settime 10:30")
        return

    time_str = command.args.strip()
    if is_valid_time_format(time_str):
        set_user_setting(user_id, "time", time_str)
        # Сбросим время последнего уведомления
        set_user_setting(user_id, "last_notified_at", None)
        
        freq = get_user_setting(user_id, "frequency")
        if freq == "12h":
            try:
                h, m = map(int, time_str.split(':'))
                second_h = (h + 12) % 24
                second_time_str = f"{second_h:02d}:{m:02d}"
                set_user_setting(user_id, "second_time", second_time_str)
                await message.answer(f"Время уведомлений установлено на {time_str} и {second_time_str} (для 12ч интервала).")
            except ValueError:
                 await message.answer(f"Время уведомлений установлено на {time_str}. Ошибка при расчете второго времени для 12ч.")
        else:
            await message.answer(f"Время уведомлений установлено на: {time_str}.")
    else:
        await message.answer("Неверный формат времени. Используйте ЧЧ:ММ (например, 09:00 или 22:15).")

def is_valid_timezone_format(tz_str: str) -> bool:
    """Проверяет формат часового пояса (+HH:MM, -HH:MM, +H, -H)."""
    return bool(re.fullmatch(r"[+-]((\d|0\d|1[0-2])(:[0-5]\d)?|0)", tz_str))


@router.message(Command("settimezone"))
async def cmd_settimezone(message: Message, command: CommandObject):
    """Устанавливает часовой пояс пользователя."""
    user_id = message.from_user.id
    if command.args is None:
        await message.answer("Укажите смещение UTC.\nНапример: /settimezone +03:00 или /settimezone -5")
        return

    tz_str = command.args.strip()
    if is_valid_timezone_format(tz_str):
        # Нормализация формата до +/-HH:MM
        if ":" not in tz_str:
            sign = tz_str[0]
            hours = int(tz_str[1:])
            tz_str_normalized = f"{sign}{hours:02d}:00"
        else:
            tz_str_normalized = tz_str
            if len(tz_str.split(":")[0]) == 2: # +H:MM or -H:MM
                 parts = tz_str.split(":")
                 sign = parts[0][0]
                 hour = parts[0][1:]
                 tz_str_normalized = f"{sign}{int(hour):02d}:{parts[1]}"


        set_user_setting(user_id, "timezone", tz_str_normalized)
        await message.answer(f"Ваш часовой пояс установлен на UTC{tz_str_normalized}.")
    else:
        await message.answer("Неверный формат часового пояса. Примеры: +03:00, -05:00, +3, -4.")


@router.message(Command("sleepon"))
async def cmd_sleepon(message: Message, command: CommandObject):
    """Устанавливает 'тихий час' (период без уведомлений)."""
    user_id = message.from_user.id
    args = command.args
    if not args:
        await message.answer("Укажите время начала и конца 'тихого часа' в формате ЧЧ:ММ ЧЧ:ММ.\nНапример: /sleepon 23:00 07:00")
        return

    try:
        start_str, end_str = args.split()
        if not (is_valid_time_format(start_str) and is_valid_time_format(end_str)):
            raise ValueError("Неверный формат времени.")
        
        set_user_setting(user_id, "sleep", {"start": start_str, "end": end_str})
        await message.answer(f"Тихий час установлен с {start_str} до {end_str} по вашему местному времени.")
    except ValueError:
        await message.answer("Неверный формат. Используйте: /sleepon ЧЧ:ММ ЧЧ:ММ (например, /sleepon 23:00 07:00).")


@router.message(Command("sleepoff"))
async def cmd_sleepoff(message: Message):
    """Выключает 'тихий час'."""
    user_id = message.from_user.id
    set_user_setting(user_id, "sleep", {"start": None, "end": None})
    await message.answer("Тихий час выключен. Уведомления будут приходить как обычно.")


@router.message(Command("mysettings"))
async def cmd_mysettings(message: Message):
    """Показывает текущие настройки пользователя."""
    user_id = message.from_user.id
    if user_id not in user_settings:
        await message.answer("У вас еще нет настроек. Начните с команды /start.")
        return

    settings = user_settings[user_id]
    coins_str = ", ".join(settings.get("coins", [])).upper() or "Не выбраны"
    freq_str = settings.get("frequency", "Не установлена")
    time_str = settings.get("time", "Не установлено")
    tz_str = settings.get("timezone", "UTC+00:00")
    second_time_str = settings.get("second_time", "")
    sleep_settings = settings.get("sleep", {})
    sleep_start = sleep_settings.get("start")
    sleep_end = sleep_settings.get("end")

    sleep_info = "Выключен"
    if sleep_start and sleep_end:
        sleep_info = f"С {sleep_start} до {sleep_end}"


    text = (
        f"<b>Ваши текущие настройки:</b>\n\n"
        f"νομισμάτων: {coins_str}\n"
        f"Частота уведомлений: {freq_str}\n"
        f"Время уведомлений (UTC{tz_str}): {time_str}"
    )
    if freq_str == "12h" and second_time_str:
        text += f" и {second_time_str}"
    text += f"\nТихий час (без уведомлений): {sleep_info}"

    await message.answer(text)


# --- Фоновый процесс уведомлений ---
async def price_notifier():
    """Периодически проверяет и отправляет уведомления о ценах."""
    await asyncio.sleep(10) # Небольшая задержка перед первым запуском
    
    async with aiohttp.ClientSession() as session: # Создаем сессию один раз
        while True:
            logger.debug("[DEBUG] price_notifier активен, проверка пользователей...")
            now_utc = datetime.now(timezone.utc)
            
            # Используем list(user_settings.items()) для безопасной итерации, если словарь может измениться
            for user_id, settings in list(user_settings.items()):
                coins = settings.get("coins")
                freq = settings.get("frequency")
                tz_offset_str = settings.get("timezone", "+00:00")
                notify_time_str = settings.get("time")
                second_notify_time_str = settings.get("second_time") # Для 12h
                sleep_config = settings.get("sleep", {})
                last_notified_at_str = settings.get("last_notified_at") # Строка ISO формата

                if not coins or not freq or not notify_time_str:
                    logger.debug(f"[DEBUG] UID: {user_id}, пропуск: нет монет, частоты или времени.")
                    continue

                try:
                    # Преобразование смещения часового пояса в timedelta
                    sign = -1 if tz_offset_str.startswith("-") else 1
                    if ":" in tz_offset_str:
                        hours_offset, minutes_offset = map(int, tz_offset_str[1:].split(':'))
                    else:
                        hours_offset = int(tz_offset_str[1:])
                        minutes_offset = 0
                    user_tz_delta = timedelta(hours=sign * hours_offset, minutes=sign * minutes_offset)
                    user_local_time = now_utc + user_tz_delta
                    current_local_hour_minute = user_local_time.strftime("%H:%M")
                    current_local_date_str = user_local_time.strftime("%Y-%m-%d")

                except ValueError as e:
                    logger.warning(f"Ошибка парсинга часового пояса для UID {user_id}: {tz_offset_str}, {e}. Используется UTC.")
                    user_local_time = now_utc
                    current_local_hour_minute = user_local_time.strftime("%H:%M")
                    current_local_date_str = user_local_time.strftime("%Y-%m-%d")


                # Проверка "тихого часа"
                if sleep_config and sleep_config.get("start") and sleep_config.get("end"):
                    sleep_start_str = sleep_config["start"]
                    sleep_end_str = sleep_config["end"]
                    
                    # Сравниваем только время, без даты
                    # current_time_obj = user_local_time.time() # Неправильно, если пересекает полночь
                    # sleep_start_obj = datetime.strptime(sleep_start_str, "%H:%M").time()
                    # sleep_end_obj = datetime.strptime(sleep_end_str, "%H:%M").time()

                    # Корректная проверка для "тихого часа", пересекающего полночь
                    if sleep_start_str < sleep_end_str: # Сон в течение одного дня (например, 10:00 - 18:00)
                        if sleep_start_str <= current_local_hour_minute < sleep_end_str:
                            logger.debug(f"[DEBUG] UID: {user_id}, тихий час (дневной) {sleep_start_str}-{sleep_end_str}, текущее: {current_local_hour_minute}. Пропуск.")
                            continue
                    else: # Сон пересекает полночь (например, 23:00 - 07:00)
                        if current_local_hour_minute >= sleep_start_str or current_local_hour_minute < sleep_end_str:
                            logger.debug(f"[DEBUG] UID: {user_id}, тихий час (ночной) {sleep_start_str}-{sleep_end_str}, текущее: {current_local_hour_minute}. Пропуск.")
                            continue
                
                should_send = False
                notification_key_time = None # Для отслеживания последнего уведомления

                if freq == "24h":
                    if current_local_hour_minute == notify_time_str:
                        notification_key_time = f"{current_local_date_str} {notify_time_str}"
                        if last_notified_at_str != notification_key_time:
                            should_send = True
                elif freq == "12h":
                    if current_local_hour_minute == notify_time_str:
                        notification_key_time = f"{current_local_date_str} {notify_time_str}"
                        if last_notified_at_str != notification_key_time:
                            should_send = True
                    elif second_notify_time_str and current_local_hour_minute == second_notify_time_str:
                        notification_key_time = f"{current_local_date_str} {second_notify_time_str}"
                        if last_notified_at_str != notification_key_time:
                            should_send = True
                elif freq == "1h":
                    if user_local_time.minute == 0: # В начале каждого часа по местному времени
                        notification_key_time = user_local_time.strftime("%Y-%m-%d %H:00")
                        if last_notified_at_str != notification_key_time:
                            should_send = True
                elif freq == "2h":
                     # В начале каждого второго часа по местному времени (00:00, 02:00, ...)
                    if user_local_time.minute == 0 and user_local_time.hour % 2 == 0:
                        notification_key_time = user_local_time.strftime("%Y-%m-%d %H:00")
                        if last_notified_at_str != notification_key_time:
                            should_send = True
                
                logger.debug(f"[DEBUG] UID: {user_id}, freq: {freq}, local_time: {current_local_hour_minute}, notify_time: {notify_time_str}, second_time: {second_notify_time_str}, should_send: {should_send}, last_notified: {last_notified_at_str}, current_key: {notification_key_time}")

                if should_send:
                    try:
                        prices_text_parts = []
                        for coin in coins:
                            api_url = "https://api.coingecko.com/api/v3/simple/price"
                            params = {"ids": coin, "vs_currencies": "usd"}
                            async with session.get(api_url, params=params) as resp:
                                if resp.status == 200:
                                    data = await resp.json()
                                    price = data.get(coin, {}).get("usd")
                                    if price:
                                        prices_text_parts.append(f"{coin.capitalize()}: ${price}")
                                    else:
                                        prices_text_parts.append(f"{coin.capitalize()}: Ошибка получения цены")
                                else:
                                    logger.warning(f"Ошибка API CoinGecko для {coin} (UID: {user_id}): статус {resp.status}")
                                    prices_text_parts.append(f"{coin.capitalize()}: Ошибка API ({resp.status})")
                        
                        if prices_text_parts:
                            full_text = f"📈 Цены на {', '.join(coins).upper()} (UTC{tz_offset_str}):\n" + "\n".join(prices_text_parts)
                            await bot.send_message(user_id, full_text.strip())
                            set_user_setting(user_id, "last_notified_at", notification_key_time) # Обновляем время последнего уведомления
                            logger.info(f"Отправлено уведомление пользователю {user_id} для монет: {', '.join(coins)}")
                        else:
                            logger.info(f"Нет цен для отправки пользователю {user_id}.")

                    except aiohttp.ClientError as e:
                        logger.error(f"❌ Сетевая ошибка при запросе к CoinGecko для UID {user_id}: {e}")
                    except Exception as e:
                        logger.error(f"❌ Ошибка отправки сообщения пользователю {user_id}: {e}")
            
            await asyncio.sleep(60) # Проверять каждую минуту


# --- Функции жизненного цикла приложения ---
async def on_startup(bot_instance: Bot):
    """Действия при запуске бота."""
    load_user_settings() # Загружаем настройки при старте
    await bot_instance.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
    me = await bot_instance.get_me()
    logger.info(f"Бот @{me.username} (ID: {me.id}) запущен с вебхуком: {WEBHOOK_URL}")

async def on_shutdown(bot_instance: Bot):
    """Действия при остановке бота."""
    save_user_settings() # Сохраняем настройки перед выключением
    # Закрытие сессии бота, если она была открыта явно (aiogram обычно управляет этим)
    # await bot_instance.session.close() # Это может быть не нужно или вызвать ошибку в зависимости от версии aiogram
    logger.info("Бот остановлен. Сессия закрыта.")


async def main():
    """Основная функция запуска."""
    app = web.Application()
    webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    
    # Добавляем обработчик вебхука
    app.router.add_route("POST", WEBHOOK_PATH, webhook_handler.handle)
    
    # Настраиваем приложение aiohttp с aiogram
    setup_application(app, dp, bot=bot) # on_startup/on_shutdown для dp передаются здесь неявно

    # Явно добавляем наши on_startup/on_shutdown для бота
    app.on_startup.append(lambda _: on_startup(bot))
    app.on_shutdown.append(lambda _: on_shutdown(bot))

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=PORT)
    logger.info(f"🚀 Запуск веб-сервера на http://0.0.0.0:{PORT}")
    await site.start()

    # Запускаем фоновую задачу уведомлений
    asyncio.create_task(price_notifier())
    
    # Ожидаем завершения (например, по Ctrl+C)
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
        logger.info("Веб-сервер и бот остановлены.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен вручную (KeyboardInterrupt/SystemExit)!")
    except RuntimeError as e:
        if "BOT_TOKEN" in str(e) or "WEBHOOK_HOST" in str(e):
            logger.critical(f"Критическая ошибка конфигурации: {e}")
        else:
            logger.exception("Непредвиденная ошибка RuntimeError при запуске:")
    except Exception as e:
        logger.exception("Непредвиденная ошибка при запуске:")

