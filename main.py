import os
import json
import aiohttp
import asyncio
from datetime import datetime, timezone, timedelta, time # Added time
import pytz # Added for timezone handling

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.filters import Command
from aiogram.utils.markdown import hcode

print(f"[{datetime.now(timezone.utc).isoformat()}] Скрипт main.py почав виконуватися.")

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = os.getenv("BOT_TOKEN") # Отримуємо токен, може бути None
PLACEHOLDER_TOKEN = "ВАШ_БОТ_ТОКЕН_ТУТ_ЗАМЕНИТЕ_ИЛИ_УСТАНОВИТЕ_ПЕРЕМЕННУЮ" # Стандартний плейсхолдер

if not BOT_TOKEN or BOT_TOKEN == PLACEHOLDER_TOKEN:
    print(f"[{datetime.now(timezone.utc).isoformat()}] КРИТИЧНО: BOT_TOKEN не встановлено або є плейсхолдером. Перевірте змінні середовища на Render та переконайтеся, що токен дійсний.")
    exit(1) # Завершуємо роботу, якщо токен невалідний

print(f"[{datetime.now(timezone.utc).isoformat()}] BOT_TOKEN отримано з середовища.")

try:
    bot = Bot(token=BOT_TOKEN)
    print(f"[{datetime.now(timezone.utc).isoformat()}] Об'єкт Bot успішно створено.")
except Exception as e:
    print(f"[{datetime.now(timezone.utc).isoformat()}] КРИТИЧНА ПОМИЛКА при створенні об'єкта Bot: {e}")
    print(f"[{datetime.now(timezone.utc).isoformat()}] Перевірте правильність BOT_TOKEN.")
    exit(1)

dp = Dispatcher()
print(f"[{datetime.now(timezone.utc).isoformat()}] Об'єкт Dispatcher успішно створено.")

DATA_FILE = "user_crypto_stable_final.json" 

POPULAR_TOKENS_MAP = {
    'BTC': 'bitcoin', 'ETH': 'ethereum', 'SOL': 'solana', 
    'TON': 'the-open-network', 'DOGE': 'dogecoin', 'LINK': 'chainlink', 
    'ADA': 'cardano', 'DOT': 'polkadot', 'MATIC': 'matic-network', 'ARB': 'arbitrum'
}
POPULAR_TOKENS_ORDER = ['BTC', 'ETH', 'SOL', 'TON', 'DOGE', 'LINK', 'ADA', 'DOT', 'MATIC', 'ARB']
ADMIN_IDS = [696165311, 7923967086] # Example IDs

# --- ФУНКЦИИ ДЛЯ РАБОТЫ С ДАННЫМИ ---
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding='utf-8') as f:
                content = f.read()
                if not content: 
                    return {}
                return json.loads(content)
        except json.JSONDecodeError:
            print(f"[{datetime.now(timezone.utc).isoformat()}] Помилка декодування JSON з файлу {DATA_FILE}.")
            return {}
        except Exception as e:
            print(f"[{datetime.now(timezone.utc).isoformat()}] Не вдалося завантажити дані: {e}")
            return {}
    return {}

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[{datetime.now(timezone.utc).isoformat()}] Не вдалося зберегти дані: {e}")

def get_default_user_config():
    return {
        "tokens_id": [],            
        "tokens_display": [],       
        "frequency": None,          
        "notification_times_utc": [], # Stores HH:MM strings in UTC
        "timezone": None,             # User's timezone string e.g., "Europe/Kyiv"
        "sleep_enabled": False,
        "sleep_start_local": None,    # Local HH:MM string e.g., "22:00"
        "sleep_end_local": None       # Local HH:MM string e.g., "07:00"
    }

# --- ФУНКЦИИ ДЛЯ API COINGECKO ---
async def fetch_prices_batch(symbol_ids: list[str]) -> dict:
    if not symbol_ids:
        return {}
    
    ids_query_param = ",".join(symbol_ids)
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids_query_param}&vs_currencies=usd"
    results = {sym_id: "N/A" for sym_id in symbol_ids}
    log_prefix = f"[{datetime.now(timezone.utc).isoformat()}] FetchPricesBatch ({ids_query_param}):"
    try:
        async with aiohttp.ClientSession() as session:
            headers = {'User-Agent': 'TelegramBot/CryptoNotifier (Python/Aiohttp)'} 
            async with session.get(url, timeout=15, headers=headers) as resp:
                response_text = await resp.text()
                if resp.status == 200:
                    data = json.loads(response_text)
                    for symbol_id in symbol_ids:
                        price_data = data.get(symbol_id, {})
                        price = price_data.get("usd")
                        if price is not None:
                            results[symbol_id] = float(price)
                        else:
                            results[symbol_id] = "NoPriceData"
                    return results
                else:
                    print(f"{log_prefix} API Error. Status: {resp.status}, Response: {response_text}")
                    for symbol_id in symbol_ids: results[symbol_id] = "ErrorAPI"
                    return results
    except asyncio.TimeoutError:
        print(f"{log_prefix} API Timeout.")
        for symbol_id in symbol_ids: results[symbol_id] = "Timeout"
    except aiohttp.ClientConnectorError as e:
        print(f"{log_prefix} API Connection Error: {e}")
        for symbol_id in symbol_ids: results[symbol_id] = "ConnectionError"
    except Exception as e:
        print(f"{log_prefix} API General Error: {e}")
        for symbol_id in symbol_ids: results[symbol_id] = "Error"
    return results

async def search_token(query: str):
    url = f"https://api.coingecko.com/api/v3/search?query={query}"
    log_prefix = f"[{datetime.now(timezone.utc).isoformat()}] SearchToken ({query}):"
    try:
        async with aiohttp.ClientSession() as session:
            headers = {'User-Agent': 'TelegramBot/CryptoNotifier (Python/Aiohttp)'}
            async with session.get(url, timeout=10, headers=headers) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    coins = result.get("coins", [])
                    if coins:
                        coin = coins[0] 
                        return coin.get("id"), coin.get("name"), coin.get("symbol")
                else:
                    print(f"{log_prefix} API Error. Status: {resp.status}, Response: {await resp.text()}")
    except asyncio.TimeoutError:
        print(f"{log_prefix} API Timeout.")
    except Exception as e:
        print(f"{log_prefix} API General Error: {e}")
    return None, None, None

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ВРЕМЕНИ И ОПИСАНИЙ ---

def convert_utc_to_local_str(utc_time_str: str, user_timezone_str: str) -> str:
    if not user_timezone_str:
        return f"{utc_time_str} UTC"
    try:
        user_tz = pytz.timezone(user_timezone_str)
        utc_time_obj = datetime.strptime(utc_time_str, "%H:%M").time()
        now_in_utc = datetime.now(pytz.utc)
        dt_to_convert = now_in_utc.replace(hour=utc_time_obj.hour, minute=utc_time_obj.minute, second=0, microsecond=0)
        dt_in_user_local = dt_to_convert.astimezone(user_tz)
        return dt_in_user_local.strftime("%H:%M %Z") 
    except Exception as e:
        print(f"Error converting UTC to local string: {e}")
        return f"{utc_time_str} UTC (помилка конвертації)"

def convert_local_to_utc_str(local_time_str: str, user_timezone_str: str) -> str | None:
    if not user_timezone_str:
        return None
    try:
        user_tz = pytz.timezone(user_timezone_str)
        local_time_obj = datetime.strptime(local_time_str, "%H:%M").time()
        now_in_user_tz = datetime.now(user_tz)
        dt_to_convert = now_in_user_tz.replace(hour=local_time_obj.hour, minute=local_time_obj.minute, second=0, microsecond=0)
        dt_in_utc = dt_to_convert.astimezone(pytz.utc)
        return dt_in_utc.strftime("%H:%M")
    except Exception as e:
        print(f"Error converting local to UTC string: {e}")
        return None

def get_frequency_description_text(user_config: dict) -> str:
    freq_code = user_config.get("frequency")
    notification_times_utc = user_config.get("notification_times_utc", [])
    user_tz_str = user_config.get("timezone")

    if not freq_code:
        return "не встановлена (сповіщення вимкнені)"
    
    desc = ""
    if freq_code == "hourly": desc = "Щогодини"
    elif freq_code == "2_hours": desc = "Кожні 2 години"
    elif freq_code == "daily_1":
        desc = "1 раз на день"
        if notification_times_utc:
            local_time_str = convert_utc_to_local_str(notification_times_utc[0], user_tz_str)
            desc += f" о {local_time_str}"
        else:
            desc += " (час не налаштовано)"
    elif freq_code == "daily_2":
        desc = "2 рази на день"
        if len(notification_times_utc) == 2:
            local_t1_str = convert_utc_to_local_str(notification_times_utc[0], user_tz_str)
            local_t2_str = convert_utc_to_local_str(notification_times_utc[1], user_tz_str)
            desc += f" о {local_t1_str} та {local_t2_str}"
        else:
            desc += " (час не налаштовано)"
    else:
        return "Невідома частота"
    return desc

# --- ОБРАБОТЧИКИ КОМАНД И CALLBACK ---
# ... (остальные обработчики команд и callback без изменений) ...
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user_id = str(message.chat.id)
    data = load_data()
    if user_id not in data:
        data[user_id] = get_default_user_config()
        save_data(data)

    kb_buttons = []
    for i in range(0, len(POPULAR_TOKENS_ORDER), 2):
        row = []
        display_ticker1 = POPULAR_TOKENS_ORDER[i]
        coin_id1 = POPULAR_TOKENS_MAP[display_ticker1]
        row.append(InlineKeyboardButton(text=display_ticker1, callback_data=f"add_{coin_id1}_{display_ticker1}"))
        
        if i + 1 < len(POPULAR_TOKENS_ORDER):
            display_ticker2 = POPULAR_TOKENS_ORDER[i+1]
            coin_id2 = POPULAR_TOKENS_MAP[display_ticker2]
            row.append(InlineKeyboardButton(text=display_ticker2, callback_data=f"add_{coin_id2}_{display_ticker2}"))
        kb_buttons.append(row)
    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    
    await message.answer(
        "Привіт! Я допоможу тобі відслідковувати ціни на криптовалюти.\n\n"
        "📥 <b>Обери до 5 монет зі списку популярних:</b>", 
        reply_markup=kb, parse_mode="HTML"
    )
    await message.answer(
        "🔍 <b>Або напиши скорочення (тікер) монети</b> (наприклад: `arb` або `Bitcoin`), щоб знайти її через пошук.\n\n"
        "Після вибору монет, налаштуй частоту та час сповіщень командою /setfrequency.\n"
        "Встанови свій часовий пояс: /settimezone\n"
        "Налаштуй режим сну (щоб не отримувати сповіщення вночі): /setsleep\n\n"
        "<b>Інші команди:</b>\n"
        "/mycryptoconfig - переглянути поточні налаштування\n"
        "/resetcrypto - скинути всі налаштування\n"
        "/stopcryptonotifications - зупинити сповіщення",
        parse_mode="HTML"
    )

@dp.message(Command("mycryptoconfig"))
async def my_config_cmd(message: types.Message):
    user_id = str(message.chat.id)
    data = load_data()
    user_config = data.get(user_id)

    if not user_config:
        await message.answer("У вас ще немає налаштувань. Почніть з команди /start.")
        return

    tokens_display_str = ", ".join(user_config.get("tokens_display", []))
    if not tokens_display_str:
        tokens_display_str = "не обрано"
    
    freq_desc = get_frequency_description_text(user_config) 
    
    timezone_str = user_config.get("timezone")
    if not timezone_str:
        timezone_str = "не встановлено (буде використовуватись UTC)"
    
    sleep_mode_desc = "вимкнено"
    if user_config.get("sleep_enabled"):
        start_sleep = user_config.get("sleep_start_local", "??:??")
        end_sleep = user_config.get("sleep_end_local", "??:??")
        sleep_mode_desc = f"увімкнено (з {start_sleep} до {end_sleep} вашого локального часу)"

    await message.answer(
        f"<b>⚙️ Ваші поточні налаштування:</b>\n\n"
        f"<b>Обрані монети:</b> {tokens_display_str}\n"
        f"<b>Частота сповіщень:</b> {freq_desc}\n"
        f"<b>Ваш часовий пояс:</b> {timezone_str}\n"
        f"<b>Режим сну:</b> {sleep_mode_desc}\n\n"
        "Щоб змінити монети, просто додайте нові або використайте /resetcrypto.\n"
        "Щоб змінити частоту, використайте /setfrequency (потім /setnotifytime, якщо потрібно).\n"
        "Щоб змінити часовий пояс: /settimezone\n"
        "Щоб налаштувати режим сну: /setsleep (потім /setsleeptime, якщо потрібно).",
        parse_mode="HTML"
    )

@dp.callback_query(lambda c: c.data.startswith("add_"))
async def add_token_callback(callback_query: types.CallbackQuery):
    user_id = str(callback_query.from_user.id)
    try:
        _, coin_id, display_ticker = callback_query.data.split("_", 2)
    except ValueError:
        await callback_query.answer("Помилка даних кнопки.", show_alert=True)
        print(f"[{datetime.now(timezone.utc).isoformat()}] Неправильний формат callback_data: {callback_query.data}")
        return

    data = load_data()
    user_config = data.get(user_id, get_default_user_config()) 
    tokens_id_list = user_config.get("tokens_id", [])
    tokens_display_list = user_config.get("tokens_display", [])

    if coin_id in tokens_id_list:
        await callback_query.answer(f"{display_ticker} вже обрано", show_alert=False)
        return

    if len(tokens_id_list) >= 5: 
        await callback_query.answer("Вже обрано 5 монет. Максимум.", show_alert=True)
        return

    tokens_id_list.append(coin_id)
    tokens_display_list.append(display_ticker)
    
    user_config["tokens_id"] = tokens_id_list
    user_config["tokens_display"] = tokens_display_list
    data[user_id] = user_config
    save_data(data)

    await callback_query.answer(f"Додано {display_ticker}", show_alert=False)
    await bot.send_message(user_id, f"✅ Додано: {display_ticker} (ID: {hcode(coin_id)})", parse_mode="HTML")

    if len(tokens_id_list) >= 5: 
        await bot.send_message(user_id, "Ви обрали 5 монет. Тепер налаштуйте частоту сповіщень: /setfrequency")
    elif len(tokens_id_list) > 0: 
        await bot.send_message(user_id, "Щоб налаштувати частоту сповіщень, використайте /setfrequency")

@dp.message(Command("settimezone"))
async def set_timezone_cmd(message: types.Message):
    await message.answer(
        "Будь ласка, надішліть ваш часовий пояс.\n"
        "Наприклад: `Europe/Kyiv`, `America/New_York`, `Asia/Tokyo`.\n"
        "Ви можете знайти свій часовий пояс у списку (наприклад, на Wikipedia за запитом 'list of tz database time zones').\n"
        "Популярні варіанти: Europe/London, Europe/Berlin, Europe/Warsaw, America/Toronto, Asia/Dubai, Australia/Sydney.",
        parse_mode="HTML"
    )

@dp.message(Command("setfrequency"))
async def set_frequency_cmd(message: types.Message):
    user_id = str(message.chat.id)
    data = load_data()
    user_config = data.get(user_id)

    if not user_config or not user_config.get("tokens_id"):
        await message.answer("Будь ласка, спочатку оберіть хоча б одну монету.\n"
                             "Ви можете зробити це через /start або написавши тікер монети в чат.")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Щогодини", callback_data="setfreq_hourly")],
        [InlineKeyboardButton(text="Кожні 2 години", callback_data="setfreq_2_hours")],
        [InlineKeyboardButton(text="1 раз на день (налаштувати час)", callback_data="setfreq_config_daily_1")],
        [InlineKeyboardButton(text="2 рази на день (налаштувати час)", callback_data="setfreq_config_daily_2")],
        [InlineKeyboardButton(text="🚫 Вимкнути сповіщення", callback_data="setfreq_off")]
    ])
    await message.answer("⏰ Оберіть частоту сповіщень:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("setfreq_"))
async def process_frequency_callback(callback_query: types.CallbackQuery):
    user_id = str(callback_query.from_user.id)
    action = callback_query.data
    
    data = load_data()
    user_config = data.get(user_id, get_default_user_config())
    
    current_tz = user_config.get("timezone")
    if not current_tz and (action == "setfreq_config_daily_1" or action == "setfreq_config_daily_2"):
        await callback_query.message.answer(
            "❗️ Будь ласка, спочатку встановіть ваш часовий пояс командою /settimezone.\n"
            "Потім ви зможете налаштувати час для щоденних сповіщень.",
            parse_mode="HTML"
        )
        await callback_query.answer()
        return

    new_frequency = user_config.get("frequency") 
    new_times_utc = user_config.get("notification_times_utc", [])
    msg_text = ""

    if action == "setfreq_off":
        new_frequency = None
        new_times_utc = []
        msg_text = "Сповіщення вимкнено."
    elif action == "setfreq_hourly":
        new_frequency = "hourly"
        new_times_utc = [] 
        msg_text = "Частоту встановлено: Щогодини."
    elif action == "setfreq_2_hours":
        new_frequency = "2_hours"
        new_times_utc = [] 
        msg_text = "Частоту встановлено: Кожні 2 години."
    elif action == "setfreq_config_daily_1":
        await callback_query.message.answer(
            f"Для налаштування часу для '1 раз на день', використайте команду:\n"
            f"`/setnotifytime <ЧАС>`\n"
            f"Наприклад: `/setnotifytime 09:00`\n"
            f"Час буде інтерпретовано у вашому поточному часовому поясі: {current_tz}.",
            parse_mode="HTML"
        )
        await callback_query.answer("Вкажіть час командою")
        return 
    elif action == "setfreq_config_daily_2":
        await callback_query.message.answer(
            f"Для налаштування часу для '2 рази на день', використайте команду:\n"
            f"`/setnotifytime <ЧАС1> <ЧАС2>`\n"
            f"Наприклад: `/setnotifytime 09:00 21:00`\n"
            f"Час буде інтерпретовано у вашому поточному часовому поясі: {current_tz}.",
            parse_mode="HTML"
        )
        await callback_query.answer("Вкажіть час командою")
        return 
    else:
        await callback_query.answer("Невідома дія.", show_alert=True)
        return

    user_config["frequency"] = new_frequency
    user_config["notification_times_utc"] = new_times_utc
    data[user_id] = user_config
    save_data(data)
    
    final_freq_desc = get_frequency_description_text(user_config)
    await callback_query.message.edit_text(f"✅ Частоту сповіщень оновлено: <b>{final_freq_desc}</b>", parse_mode="HTML")
    await callback_query.answer(msg_text if msg_text else "Налаштування оновлено")

@dp.message(Command("setnotifytime"))
async def set_notify_time_cmd(message: types.Message):
    user_id = str(message.chat.id)
    args = message.text.split()[1:] 

    data = load_data()
    user_config = data.get(user_id)

    if not user_config:
        await message.answer("Спочатку налаштуйте базові параметри через /start.")
        return

    user_tz_str = user_config.get("timezone")
    if not user_tz_str:
        await message.answer("Будь ласка, спочатку встановіть ваш часовий пояс: /settimezone")
        return

    if not args or len(args) > 2:
        await message.answer("Неправильний формат. Використовуйте:\n"
                             "`/setnotifytime <ЧАС>` (для 1 разу на день)\n"
                             "або `/setnotifytime <ЧАС1> <ЧАС2>` (для 2 разів на день)\n"
                             "Наприклад: `/setnotifytime 09:00` або `/setnotifytime 08:00 20:00`", parse_mode="HTML")
        return

    local_times_str = args
    utc_times_to_store = []

    for lt_str in local_times_str:
        try:
            datetime.strptime(lt_str, "%H:%M") 
            utc_t_str = convert_local_to_utc_str(lt_str, user_tz_str)
            if utc_t_str:
                utc_times_to_store.append(utc_t_str)
            else:
                await message.answer(f"Не вдалося конвертувати час {lt_str} в UTC. Перевірте часовий пояс.")
                return
        except ValueError:
            await message.answer(f"Неправильний формат часу: {lt_str}. Використовуйте ГГ:ХХ (наприклад, 09:30).")
            return
    
    utc_times_to_store.sort() 

    if len(utc_times_to_store) == 1:
        user_config["frequency"] = "daily_1"
        user_config["notification_times_utc"] = utc_times_to_store
    elif len(utc_times_to_store) == 2:
        user_config["frequency"] = "daily_2"
        user_config["notification_times_utc"] = utc_times_to_store
    else: 
        await message.answer("Помилка при встановленні часу. Спробуйте ще раз.")
        return

    data[user_id] = user_config
    save_data(data)

    final_freq_desc = get_frequency_description_text(user_config)
    await message.answer(f"✅ Час сповіщень успішно встановлено: <b>{final_freq_desc}</b>.", parse_mode="HTML")

@dp.message(Command("setsleep"))
async def set_sleep_cmd(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="😴 Увімкнути/Змінити години сну", callback_data="sleep_config")],
        [InlineKeyboardButton(text="☀️ Вимкнути режим сну", callback_data="sleep_disable")]
    ])
    await message.answer("Налаштування режиму сну:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("sleep_"))
async def process_sleep_callback(callback_query: types.CallbackQuery):
    user_id = str(callback_query.from_user.id)
    action = callback_query.data
    
    data = load_data()
    user_config = data.get(user_id, get_default_user_config())

    if action == "sleep_config":
        current_tz = user_config.get("timezone")
        if not current_tz:
            await callback_query.message.answer(
                "❗️ Будь ласка, спочатку встановіть ваш часовий пояс командою /settimezone.\n"
                "Потім ви зможете налаштувати режим сну.",
                parse_mode="HTML"
            )
            await callback_query.answer()
            return
            
        await callback_query.message.answer(
            f"Щоб налаштувати години сну, використайте команду:\n"
            f"`/setsleeptime <СТАРТ_ГГ:ХХ> <КІНЕЦЬ_ГГ:ХХ>`\n"
            f"Наприклад: `/setsleeptime 22:00 07:00`\n"
            f"Час буде інтерпретовано у вашому поточному часовому поясі ({current_tz}).",
            parse_mode="HTML"
        )
        await callback_query.answer("Вкажіть години сну командою")
    elif action == "sleep_disable":
        user_config["sleep_enabled"] = False
        data[user_id] = user_config
        save_data(data)
        await callback_query.message.edit_text("🌙 Режим сну вимкнено.")
        await callback_query.answer("Режим сну вимкнено")
    else:
        await callback_query.answer("Невідома дія.", show_alert=True)

@dp.message(Command("setsleeptime"))
async def set_sleep_time_cmd(message: types.Message):
    user_id = str(message.chat.id)
    args = message.text.split()[1:]

    if len(args) != 2:
        await message.answer("Неправильний формат. Використовуйте: `/setsleeptime <СТАРТ_ГГ:ХХ> <КІНЕЦЬ_ГГ:ХХ>`\n"
                             "Наприклад: `/setsleeptime 22:00 07:00`", parse_mode="HTML")
        return

    start_time_str, end_time_str = args[0], args[1]

    try:
        datetime.strptime(start_time_str, "%H:%M")
        datetime.strptime(end_time_str, "%H:%M")
    except ValueError:
        await message.answer("Неправильний формат часу. Використовуйте ГГ:ХХ (наприклад, 22:00).")
        return

    data = load_data()
    user_config = data.get(user_id)
    if not user_config: 
        user_config = get_default_user_config()
    
    if not user_config.get("timezone"):
        await message.answer("Будь ласка, спочатку встановіть ваш часовий пояс: /settimezone")
        return

    user_config["sleep_start_local"] = start_time_str
    user_config["sleep_end_local"] = end_time_str
    user_config["sleep_enabled"] = True
    data[user_id] = user_config
    save_data(data)

    await message.answer(f"🌙 Режим сну встановлено з {start_time_str} до {end_time_str} (ваш локальний час).")

@dp.message(Command("resetcrypto")) 
async def reset_crypto_all_cmd(message: types.Message):
    user_id = str(message.from_user.id)
    data = load_data()
    if user_id in data:
        data[user_id] = get_default_user_config() 
        save_data(data)
        await message.answer("♻️ Всі ваші налаштування для криптовалют скинуто. /start щоб почати знову.")
    else:
        await message.answer("У вас ще немає налаштувань для скидання.")

@dp.callback_query(lambda c: c.data == "reset_all_crypto") 
async def reset_crypto_all_callback(callback_query: types.CallbackQuery):
    user_id = str(callback_query.from_user.id)
    data = load_data()
    if user_id in data:
        data[user_id] = get_default_user_config()
        save_data(data)
    try:
        await callback_query.message.edit_text("♻️ Всі ваші налаштування для криптовалют скинуто. /start щоб почати знову.")
    except Exception: 
        await bot.send_message(user_id, "♻️ Всі ваші налаштування для криптовалют скинуто. /start щоб почати знову.")
    await callback_query.answer("Налаштування скинуто", show_alert=False)

@dp.message(Command("stopcryptonotifications"))
async def stop_crypto_notifications_cmd(message: types.Message):
    user_id = str(message.from_user.id)
    data = load_data()
    user_config = data.get(user_id)

    if user_config and user_config.get("frequency") is not None:
        user_config["frequency"] = None
        user_config["notification_times_utc"] = [] 
        data[user_id] = user_config
        save_data(data)
        await message.answer("❌ Сповіщення про криптовалюти зупинені.")
    else:
        await message.answer("Сповіщення вже вимкнені або не були налаштовані.")

# --- ПЛАНИРОВЩИК ---
async def send_user_price_update(user_id_int: int, user_config: dict, frequency: str):
    tokens_id_list = user_config.get("tokens_id", [])
    if not tokens_id_list:
        return

    prices_info = []
    display_names = user_config.get("tokens_display", [])
    if not display_names or len(display_names) != len(tokens_id_list):
        display_names = [tid.capitalize() for tid in tokens_id_list] 

    fetched_prices_map = await fetch_prices_batch(tokens_id_list)

    for i, token_cg_id in enumerate(tokens_id_list):
        price_result = fetched_prices_map.get(token_cg_id, "N/A") 
        token_display_name = display_names[i] if i < len(display_names) else token_cg_id.capitalize()
        
        if isinstance(price_result, (int, float)):
            prices_info.append(f"{token_display_name}: ${price_result:,.2f}")
        else: 
            error_display_text = "немає даних"
            if price_result == "ErrorAPI": error_display_text = "помилка API"
            elif price_result == "Timeout": error_display_text = "таймаут API"
            elif price_result == "ConnectionError": error_display_text = "помилка зʼєднання"
            elif price_result == "NoPriceData": error_display_text = "ціну не знайдено"
            elif price_result == "N/A": error_display_text = "недоступно"
            prices_info.append(f"{token_display_name}: {error_display_text}")
    
    if not prices_info:
        print(f"[{datetime.now(timezone.utc).isoformat()}] send_user_price_update: Немає даних про ціни для формування повідомлення користувачу {user_id_int}")
        return

    freq_text_for_msg = get_frequency_description_text(user_config) 
    header = f"<b>📈 Оновлення цін ({freq_text_for_msg.lower()})</b>" 
    message_body = "\n".join(prices_info)
    final_message = f"{header}\n{message_body}"
    
    kb_after_price = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Мої налаштування", callback_data="show_my_config_inline")], 
        [InlineKeyboardButton(text="❌ Зупинити ці сповіщення", callback_data="setfreq_off")] 
    ])
    try:
        await bot.send_message(user_id_int, final_message, reply_markup=kb_after_price, parse_mode="HTML")
        print(f"[{datetime.now(timezone.utc).isoformat()}] send_user_price_update: Надіслано регулярне сповіщення для {user_id_int}")
    except Exception as e:
        error_msg = str(e).lower()
        user_id_str = str(user_id_int) 
        if "bot was blocked" in error_msg or "user is deactivated" in error_msg or "chat not found" in error_msg:
            print(f"[{datetime.now(timezone.utc).isoformat()}] send_user_price_update: Користувач {user_id_int} заблокував бота або не існує. Видалення даних...")
            current_data_for_delete = load_data()
            if user_id_str in current_data_for_delete:
                del current_data_for_delete[user_id_str]
                save_data(current_data_for_delete)
        else:
            print(f"[{datetime.now(timezone.utc).isoformat()}] send_user_price_update: Не вдалося надіслати повідомлення користувачу {user_id_int}: {e}")

@dp.callback_query(lambda c: c.data == "show_my_config_inline")
async def show_my_config_inline_callback(callback_query: types.CallbackQuery):
    await my_config_cmd(callback_query.message) 
    await callback_query.answer()

async def price_update_scheduler():
    print(f"[{datetime.now(timezone.utc).isoformat()}] price_update_scheduler: ЗАПУСК ФУНКЦІЇ.")
    await asyncio.sleep(10) 
    print(f"[{datetime.now(timezone.utc).isoformat()}] Планувальник регулярних сповіщень запущено (початковий sleep пройдено, основний інтервал ~60 хвилин).")
    
    cycle_count = 0 
    while True:
        cycle_count += 1
        current_iso_time_loop_start = datetime.now(timezone.utc).isoformat()
        # print(f"[{current_iso_time_loop_start}] price_update_scheduler: Початок циклу #{cycle_count}") # Може бути занадто багато логів
        
        now_utc = datetime.now(pytz.utc) 
        current_time_utc_str = now_utc.strftime("%H:%M")
        current_hour_utc = now_utc.hour
        
        all_users_data = load_data() 
        active_tasks_for_gather = []

        for user_id_str, user_config_original in all_users_data.items():
            try:
                user_id_int = int(user_id_str) 
            except ValueError:
                print(f"[{datetime.now(timezone.utc).isoformat()}] Неправильний user_id_str у файлі даних: {user_id_str}")
                continue
            
            user_config = user_config_original.copy() 
            frequency = user_config.get("frequency")
            tokens_id_list = user_config.get("tokens_id")

            if not frequency or not tokens_id_list:
                continue

            if user_config.get("sleep_enabled"):
                user_tz_str = user_config.get("timezone")
                sleep_start_local_str = user_config.get("sleep_start_local")
                sleep_end_local_str = user_config.get("sleep_end_local")

                if user_tz_str and sleep_start_local_str and sleep_end_local_str:
                    try:
                        user_pytz_tz = pytz.timezone(user_tz_str)
                        now_local = now_utc.astimezone(user_pytz_tz)
                        current_local_time_obj = now_local.time()

                        sleep_start_time = datetime.strptime(sleep_start_local_str, "%H:%M").time()
                        sleep_end_time = datetime.strptime(sleep_end_local_str, "%H:%M").time()
                        
                        is_sleeping = False
                        if sleep_start_time <= sleep_end_time: 
                            if sleep_start_time <= current_local_time_obj < sleep_end_time:
                                is_sleeping = True
                        else: 
                            if current_local_time_obj >= sleep_start_time or current_local_time_obj < sleep_end_time:
                                is_sleeping = True
                        
                        if is_sleeping:
                            continue 
                    except Exception as e:
                        print(f"[{datetime.now(timezone.utc).isoformat()}] Помилка перевірки режиму сну для користувача {user_id_int}: {e}")
            
            should_send_regular = False
            if frequency == "hourly":
                if now_utc.minute == 0: 
                    should_send_regular = True
            elif frequency == "2_hours":
                if current_hour_utc % 2 == 0 and now_utc.minute == 0: 
                    should_send_regular = True
            elif frequency == "daily_1":
                times_utc = user_config.get("notification_times_utc", [])
                if times_utc and current_time_utc_str == times_utc[0]:
                    should_send_regular = True
            elif frequency == "daily_2":
                times_utc = user_config.get("notification_times_utc", [])
                if times_utc and current_time_utc_str in times_utc: 
                    should_send_regular = True
            
            if should_send_regular:
                active_tasks_for_gather.append(send_user_price_update(user_id_int, user_config, frequency))
        
        if active_tasks_for_gather:
            current_iso_time_gather = datetime.now(timezone.utc).isoformat()
            print(f"[{current_iso_time_gather}] price_update_scheduler: Знайдено {len(active_tasks_for_gather)} регулярних сповіщень для відправки.")
            
            results = await asyncio.gather(*active_tasks_for_gather, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    task_name = f"task_{i}" 
                    try:
                        original_coro = active_tasks_for_gather[i]
                        if asyncio.iscoroutine(original_coro):
                             task_name = original_coro.__qualname__ if hasattr(original_coro, '__qualname__') else original_coro.__name__
                    except Exception:
                        pass 
                    print(f"[{datetime.now(timezone.utc).isoformat()}] price_update_scheduler: Помилка у фоновому завданні '{task_name}': {result}")
        
        await asyncio.sleep(3600) # ИНТЕРВАЛ 60 МИНУТ (3600 секунд).

# --- ОБРАБОТЧИК ТЕКСТОВЫХ СООБЩЕНИЙ (АДМИН / ПОИСК ТОКЕНА / УСТАНОВКА ЧАСОВОГО ПОЯСА) ---
@dp.message() 
async def handle_text_input(message: types.Message):
    user_id_str = str(message.chat.id)
    text = message.text.strip()
    
    if not text or text.startswith("/"): 
        return 

    is_potential_timezone = "/" in text and len(text) > 5 
    
    data = load_data() 
    user_config = data.get(user_id_str, get_default_user_config())

    if is_potential_timezone:
        try:
            pytz.timezone(text) 
            user_config["timezone"] = text
            data[user_id_str] = user_config
            save_data(data)
            await message.answer(f"✅ Ваш часовий пояс встановлено на: {text}\n"
                                 f"Тепер ви можете налаштувати час сповіщень у вашому локальному часі за допомогою /setfrequency та /setnotifytime.")
            return 
        except pytz.exceptions.UnknownTimeZoneError:
            pass 
        except Exception as e:
            print(f"Error setting timezone for {user_id_str} with text '{text}': {e}")

    is_admin = message.from_user.id in ADMIN_IDS
    
    coin_id_search, coin_name_search, coin_symbol_api_search = await search_token(text.lower())
    was_coin_addition_attempt = bool(coin_id_search) 

    if is_admin:
        is_long_message_for_broadcast = len(text.split()) > 3 or len(text) > 20 
        user_tokens_id_list_for_admin = user_config.get("tokens_id", [])
        
        is_broadcast = False
        if not was_coin_addition_attempt: 
            is_broadcast = True
        elif len(user_tokens_id_list_for_admin) >= 5 and was_coin_addition_attempt: 
             is_broadcast = True 
        elif is_long_message_for_broadcast and not was_coin_addition_attempt:
             is_broadcast = True
        
        if is_broadcast:
            print(f"[{datetime.now(timezone.utc).isoformat()}] Адміністратор {message.from_user.id} надсилає розсилку: '{text}'")
            sent_count = 0
            failed_count = 0
            active_subscribers = [uid_s for uid_s, info in data.items() if info.get("tokens_id") or info.get("frequency")]
            
            if not active_subscribers:
                await message.answer("Немає активних користувачів для розсилки.")
                return

            for uid_to_send_str in active_subscribers:
                if uid_to_send_str == user_id_str: 
                    continue
                try:
                    await bot.send_message(uid_to_send_str, f"📢 <b>Повідомлення від адміністратора:</b>\n\n{text}", parse_mode="HTML")
                    sent_count += 1
                except Exception as e:
                    failed_count += 1
                    print(f"Помилка розсилки адміном користувачу {uid_to_send_str}: {e}")
            
            await message.answer(f"✅ Повідомлення для розсилки оброблено.\n"
                                 f"Кількість потенційних отримувачів: {len(active_subscribers)}\n"
                                 f"Успішно надіслано: {sent_count}\n"
                                 f"Помилок: {failed_count}")
            return 

    if was_coin_addition_attempt:
        tokens_id_list = user_config.get("tokens_id", []) 
        tokens_display_list = user_config.get("tokens_display", [])

        if len(tokens_id_list) >= 5:
            await message.answer("❗ Ти вже обрав 5 монет. Максимум.\nЩоб змінити, використай /resetcrypto і додай нові.")
            return

        display_name_to_add = coin_symbol_api_search.upper() if coin_symbol_api_search else coin_name_search
        if not display_name_to_add: display_name_to_add = text.upper() 

        if coin_id_search in tokens_id_list:
            await message.answer(f"ℹ️ Монета {display_name_to_add} (ID: {hcode(coin_id_search)}) вже обрана.", parse_mode="HTML")
            return

        tokens_id_list.append(coin_id_search)
        tokens_display_list.append(display_name_to_add)
        
        user_config["tokens_id"] = tokens_id_list
        user_config["tokens_display"] = tokens_display_list
        data[user_id_str] = user_config 
        save_data(data)

        await message.answer(f"✅ Додано: {display_name_to_add} (ID: {hcode(coin_id_search)})", parse_mode="HTML")
        
        if len(tokens_id_list) >= 5:
            await message.answer("Ви обрали 5 монет. Тепер налаштуйте частоту сповіщень: /setfrequency")
        elif len(tokens_id_list) > 0:
            await message.answer("Щоб налаштувати частоту сповіщень, використайте /setfrequency")
        return
    
    if not is_admin and not was_coin_addition_attempt and not is_potential_timezone : 
        await message.reply(f"Не вдалося розпізнати '{text}' як тікер монети або часовий пояс. Спробуйте ще раз або використайте /start для допомоги.")

# --- ЗАПУСК БОТА ---
async def main(): 
    print(f"[{datetime.now(timezone.utc).isoformat()}] main: Початок функції main.")
    print(f"[{datetime.now(timezone.utc).isoformat()}] main: РЕЄСТРАЦІЯ ХЕНДЛЕРІВ...")
    
    dp.message.register(start_cmd, Command(commands=["start"]))
    dp.message.register(my_config_cmd, Command(commands=["mycryptoconfig"]))
    dp.message.register(set_timezone_cmd, Command(commands=["settimezone"])) 
    dp.message.register(set_frequency_cmd, Command(commands=["setfrequency"]))
    dp.message.register(set_notify_time_cmd, Command(commands=["setnotifytime"]))
    dp.message.register(set_sleep_cmd, Command(commands=["setsleep"]))
    dp.message.register(set_sleep_time_cmd, Command(commands=["setsleeptime"]))
    dp.message.register(reset_crypto_all_cmd, Command(commands=["resetcrypto"]))
    dp.message.register(stop_crypto_notifications_cmd, Command(commands=["stopcryptonotifications"]))
    
    dp.callback_query.register(add_token_callback, lambda c: c.data.startswith("add_"))
    dp.callback_query.register(process_frequency_callback, lambda c: c.data.startswith("setfreq_"))
    dp.callback_query.register(process_sleep_callback, lambda c: c.data.startswith("sleep_"))
    dp.callback_query.register(reset_crypto_all_callback, lambda c: c.data == "reset_all_crypto")
    dp.callback_query.register(show_my_config_inline_callback, lambda c: c.data == "show_my_config_inline")

    dp.message.register(handle_text_input) 
    
    print(f"[{datetime.now(timezone.utc).isoformat()}] main: ХЕНДЛЕРИ ЗАРЕЄСТРОВАНІ.")
    print(f"[{datetime.now(timezone.utc).isoformat()}] main: СТВОРЕННЯ ЗАВДАННЯ ДЛЯ ПЛАНУВАЛЬНИКА...")
    scheduler_task = asyncio.create_task(price_update_scheduler())
    print(f"[{datetime.now(timezone.utc).isoformat()}] main: ЗАВДАННЯ ПЛАНУВАЛЬНИКА СТВОРЕНО.")
    
    print(f"[{datetime.now(timezone.utc).isoformat()}] main: Бот запускається (dp.start_polling)...")
    try:
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        print(f"[{datetime.now(timezone.utc).isoformat()}] main: КРИТИЧНА ПОМИЛКА В START_POLLING: {e}")
        print(f"[{datetime.now(timezone.utc).isoformat()}] Тип помилки: {type(e).__name__}")
        import traceback
        traceback.print_exc() # Друкуємо повний traceback для діагностики
        # raise # Можна повторно викликати помилку, щоб Render точно зафіксував її як збій
    finally:
        print(f"[{datetime.now(timezone.utc).isoformat()}] main: Блок finally - зупинка бота.")
        if scheduler_task and not scheduler_task.done():
            print(f"[{datetime.now(timezone.utc).isoformat()}] main: Скасування завдання планувальника...")
            scheduler_task.cancel()
            try:
                await scheduler_task 
            except asyncio.CancelledError:
                print(f"[{datetime.now(timezone.utc).isoformat()}] main: Завдання планувальника успішно скасовано.")
            except Exception as e_task: 
                 print(f"[{datetime.now(timezone.utc).isoformat()}] main: Помилка під час очікування скасованого завдання планувальника: {e_task}")
        
        if bot.session and hasattr(bot.session, 'closed') and not bot.session.closed:
            print(f"[{datetime.now(timezone.utc).isoformat()}] main: Закриття сесії бота...")
            await bot.session.close()
            print(f"[{datetime.now(timezone.utc).isoformat()}] main: Сесію бота закрито.")
        elif bot.session and not hasattr(bot.session, 'closed'):
             print(f"[{datetime.now(timezone.utc).isoformat()}] main: Сесія бота не має атрибуту 'closed'. Спроба закрити...")
             await bot.session.close() 
             print(f"[{datetime.now(timezone.utc).isoformat()}] main: Сесію бота (можливо) закрито.")
        else:
            print(f"[{datetime.now(timezone.utc).isoformat()}] main: Сесія бота відсутня або вже закрита.")
            
        print(f"[{datetime.now(timezone.utc).isoformat()}] main: Бот остаточно зупинено. Скрипт завершує роботу.")

if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] __main__: Запуск asyncio.run(main()).")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"[{datetime.now(timezone.utc).isoformat()}] __main__: Зупинка бота вручну (Ctrl+C).")
    except Exception as e: 
        print(f"[{datetime.now(timezone.utc).isoformat()}] __main__: Виникла неперехоплена критична помилка під час запуску asyncio.run(main()): {e}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"[{datetime.now(timezone.utc).isoformat()}] __main__: Скрипт main.py остаточно завершив роботу.")
