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

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "ВАШ_БОТ_ТОКЕН_ТУТ_ЗАМЕНИТЕ_ИЛИ_УСТАНОВИТЕ_ПЕРЕМЕННУЮ") 

if BOT_TOKEN == "ВАШ_БОТ_ТОКЕН_ТУТ_ЗАМЕНИТЕ_ИЛИ_УСТАНОВИТЕ_ПЕРЕМЕННУЮ":
    print(f"[{datetime.now(timezone.utc).isoformat()}] ПОПЕРЕДЖЕННЯ: КРИТИЧНО! Будь ласка, встановіть ваш справжній BOT_TOKEN!")
    # exit() # Consider if you want to exit or allow running with a placeholder for testing offline parts

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

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
            headers = {'User-Agent': 'TelegramBot/CryptoNotifier (Python/Aiohttp)'} # More specific User-Agent
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
                        coin = coins[0] # Taking the first result
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
    """Converts HH:MM UTC string to HH:MM local time string."""
    if not user_timezone_str:
        return f"{utc_time_str} UTC"
    try:
        user_tz = pytz.timezone(user_timezone_str)
        utc_time_obj = datetime.strptime(utc_time_str, "%H:%M").time()
        
        # Use today's date in UTC to make a datetime object
        now_in_utc = datetime.now(pytz.utc)
        dt_to_convert = now_in_utc.replace(hour=utc_time_obj.hour, minute=utc_time_obj.minute, second=0, microsecond=0)
        
        dt_in_user_local = dt_to_convert.astimezone(user_tz)
        return dt_in_user_local.strftime("%H:%M %Z") # e.g., "09:00 EET"
    except Exception as e:
        print(f"Error converting UTC to local string: {e}")
        return f"{utc_time_str} UTC (помилка конвертації)"

def convert_local_to_utc_str(local_time_str: str, user_timezone_str: str) -> str | None:
    """Converts HH:MM local time string to HH:MM UTC string."""
    if not user_timezone_str:
        return None
    try:
        user_tz = pytz.timezone(user_timezone_str)
        local_time_obj = datetime.strptime(local_time_str, "%H:%M").time()

        # Use today's date in user's local timezone to make a datetime object
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
    # The next text message from the user will be handled by the generic text handler,
    # which will need logic to see if it's a timezone string.
    # For a more robust solution, FSM (Finite State Machine) would be better.
    # For now, we'll rely on a special check in handle_text_input or a dedicated state.
    # Simpler: user sends text, we try to parse it as timezone in handle_text_input.
    # This is not ideal as any text could be misinterpreted.
    # A better way: this command sets a temporary state for the user.
    # For now, let's make handle_text_input try to process it if it looks like a timezone.
    # This is a placeholder for a more robust FSM-based input handling.
    # For this version, we'll just let `handle_text_input` try to deal with it if it's not a command.
    # This is not implemented here, user must send `/settimezone Actual/Timezone` or similar.
    # Correct approach: use a state machine or register a next_step_handler.
    # For simplicity in this iteration, we'll make /settimezone accept an argument.

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

    new_frequency = user_config.get("frequency") # Keep current if only asking for time
    new_times_utc = user_config.get("notification_times_utc", [])

    msg_text = ""

    if action == "setfreq_off":
        new_frequency = None
        new_times_utc = []
        msg_text = "Сповіщення вимкнено."
    elif action == "setfreq_hourly":
        new_frequency = "hourly"
        new_times_utc = [] # No specific times for hourly
        msg_text = "Частоту встановлено: Щогодини."
    elif action == "setfreq_2_hours":
        new_frequency = "2_hours"
        new_times_utc = [] # No specific times for 2-hourly
        msg_text = "Частоту встановлено: Кожні 2 години."
    elif action == "setfreq_config_daily_1":
        # Don't change frequency yet, just prompt for time
        await callback_query.message.answer(
            f"Для налаштування часу для '1 раз на день', використайте команду:\n"
            f"`/setnotifytime <ЧАС>`\n"
            f"Наприклад: `/setnotifytime 09:00`\n"
            f"Час буде інтерпретовано у вашому поточному часовому поясі: {current_tz}.",
            parse_mode="HTML"
        )
        await callback_query.answer("Вкажіть час командою")
        return # Don't save yet, wait for /setnotifytime
    elif action == "setfreq_config_daily_2":
        await callback_query.message.answer(
            f"Для налаштування часу для '2 рази на день', використайте команду:\n"
            f"`/setnotifytime <ЧАС1> <ЧАС2>`\n"
            f"Наприклад: `/setnotifytime 09:00 21:00`\n"
            f"Час буде інтерпретовано у вашому поточному часовому поясі: {current_tz}.",
            parse_mode="HTML"
        )
        await callback_query.answer("Вкажіть час командою")
        return # Don't save yet, wait for /setnotifytime
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
    args = message.text.split()[1:] # Get arguments after /setnotifytime

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
            # Validate HH:MM format
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
    
    utc_times_to_store.sort() # Store sorted UTC times

    if len(utc_times_to_store) == 1:
        user_config["frequency"] = "daily_1"
        user_config["notification_times_utc"] = utc_times_to_store
    elif len(utc_times_to_store) == 2:
        user_config["frequency"] = "daily_2"
        user_config["notification_times_utc"] = utc_times_to_store
    else: # Should not happen due to arg check, but as a safeguard
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
    user_config = da
if __name__ == "__main__":
    web.run_app(create_app(), port=10000)
