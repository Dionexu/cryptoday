import os
import json
import aiohttp
import asyncio
from datetime import datetime, timezone
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.filters import Command
from aiogram.utils.markdown import hcode

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "ВАШ_БОТ_ТОКЕН_ТУТ") 
if BOT_TOKEN == "ВАШ_БОТ_ТОКЕН_ТУТ":
    print("ПОПЕРЕДЖЕННЯ: Будь ласка, встановіть ваш справжній BOT_TOKEN!")
    # exit() 

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

DATA_FILE = "user_crypto_preferences_simplified.json" 

POPULAR_TOKENS_MAP = {
    'BTC': 'bitcoin', 'ETH': 'ethereum', 'SOL': 'solana', 
    'TON': 'the-open-network', 'DOGE': 'dogecoin', 'LINK': 'chainlink', 
    'ADA': 'cardano', 'DOT': 'polkadot', 'MATIC': 'matic-network', 'ARB': 'arbitrum'
}
POPULAR_TOKENS_ORDER = ['BTC', 'ETH', 'SOL', 'TON', 'DOGE', 'LINK', 'ADA', 'DOT', 'MATIC', 'ARB']

ADMIN_IDS = [696165311, 7923967086] 

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
            print(f"Помилка декодування JSON з файлу {DATA_FILE}.")
            return {}
        except Exception as e:
            print(f"Не вдалося завантажити дані: {e}")
            return {}
    return {}

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Не вдалося зберегти дані: {e}")

def get_default_user_config():
    return {
        "tokens_id": [],            
        "tokens_display": [],       
        "frequency": None,          
        "notification_times_utc": []
    }

# --- ФУНКЦИИ ДЛЯ API COINGECKO ---
async def fetch_price(symbol_id: str) -> str | float: 
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={symbol_id}&vs_currencies=usd"
    log_prefix = f"[{datetime.now(timezone.utc).isoformat()}] FetchPrice ({symbol_id}):"
    try:
        async with aiohttp.ClientSession() as session:
            headers = {'User-Agent': 'Mozilla/5.0 (TelegramBot/1.0)'}
            async with session.get(url, timeout=15, headers=headers) as resp:
                response_text = await resp.text()
                if resp.status == 200:
                    data = json.loads(response_text)
                    price_data = data.get(symbol_id, {})
                    price = price_data.get("usd")
                    if price is not None:
                        return float(price) 
                    else:
                        print(f"{log_prefix} 'usd' price not found in response: {data}")
                        return "NoPriceData"
                else:
                    print(f"{log_prefix} API Error. Status: {resp.status}, Response: {response_text}")
                    return "ErrorAPI" 
    except asyncio.TimeoutError:
        print(f"{log_prefix} API Timeout.")
        return "Timeout"
    except aiohttp.ClientConnectorError as e:
        print(f"{log_prefix} API Connection Error: {e}")
        return "ConnectionError"
    except Exception as e:
        print(f"{log_prefix} API General Error: {e}")
        return "Error"
    return "N/A"

async def fetch_prices_batch(symbol_ids: list[str]) -> dict:
    if not symbol_ids:
        return {}
    
    ids_query_param = ",".join(symbol_ids)
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids_query_param}&vs_currencies=usd"
    results = {sym_id: "N/A" for sym_id in symbol_ids}
    log_prefix = f"[{datetime.now(timezone.utc).isoformat()}] FetchPricesBatch ({ids_query_param}):"

    try:
        async with aiohttp.ClientSession() as session:
            headers = {'User-Agent': 'Mozilla/5.0 (TelegramBot/1.0)'}
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
            headers = {'User-Agent': 'Mozilla/5.0 (TelegramBot/1.0)'}
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

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def get_frequency_description_text(freq_code: str | None, notification_times_utc: list | None = None) -> str:
    if not freq_code:
        return "не встановлена (сповіщення вимкнені)"
    if freq_code == "hourly":
        return "Щогодини"
    elif freq_code == "2_hours":
        return "Кожні 2 години"
    elif freq_code == "daily_1":
        time_str = notification_times_utc[0] if notification_times_utc and notification_times_utc[0] else "09:00"
        return f"1 раз на день (о {time_str} UTC)"
    elif freq_code == "daily_2":
        t1 = notification_times_utc[0] if notification_times_utc and len(notification_times_utc) > 0 else "09:00"
        t2 = notification_times_utc[1] if notification_times_utc and len(notification_times_utc) > 1 else "21:00"
        return f"2 рази на день (о {t1} та {t2} UTC)"
    return "Невідома частота"

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
        "Після вибору монет, налаштуй частоту сповіщень командою /setfrequency.\n\n"
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
    
    frequency_code = user_config.get("frequency")
    notification_times = user_config.get("notification_times_utc")
    freq_desc = get_frequency_description_text(frequency_code, notification_times)

    await message.answer(
        f"<b>⚙️ Ваші поточні налаштування:</b>\n\n"
        f"<b>Обрані монети:</b> {tokens_display_str}\n"
        f"<b>Частота сповіщень:</b> {freq_desc}\n\n"
        "Щоб змінити монети, просто додайте нові або використайте /resetcrypto.\n"
        "Щоб змінити частоту, використайте /setfrequency.",
        parse_mode="HTML"
    )

@dp.callback_query(lambda c: c.data.startswith("add_"))
async def add_token_callback(callback_query: types.CallbackQuery):
    user_id = str(callback_query.from_user.id)
    try:
        _, coin_id, display_ticker = callback_query.data.split("_", 2)
    except ValueError:
        await callback_query.answer("Помилка даних кнопки.", show_alert=True)
        print(f"Неправильний формат callback_data: {callback_query.data}")
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
        [InlineKeyboardButton(text="1 раз на день (09:00 UTC)", callback_data="setfreq_daily_1_09:00")],
        [InlineKeyboardButton(text="2 рази на день (09:00, 21:00 UTC)", callback_data="setfreq_daily_2_09:00_21:00")],
        [InlineKeyboardButton(text="🚫 Вимкнути сповіщення", callback_data="setfreq_off")]
    ])
    await message.answer("⏰ Оберіть частоту сповіщень (час вказано в UTC):", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("setfreq_"))
async def process_frequency_callback(callback_query: types.CallbackQuery):
    user_id = str(callback_query.from_user.id)
    action_parts = callback_query.data.split("_") 
    
    frequency_selection = action_parts[1] 
    
    data = load_data()
    user_config = data.get(user_id, get_default_user_config())

    new_frequency = None
    new_times_utc = []

    if frequency_selection == "off":
        new_frequency = None
    elif frequency_selection == "hourly":
        new_frequency = "hourly"
    elif frequency_selection == "2": 
        new_frequency = "2_hours"
    elif frequency_selection == "daily":
        if action_parts[2] == "1": 
            new_frequency = "daily_1"
            new_times_utc = [action_parts[3]] 
        elif action_parts[2] == "2": 
            new_frequency = "daily_2"
            new_times_utc = [action_parts[3], action_parts[4]] 
    
    user_config["frequency"] = new_frequency
    user_config["notification_times_utc"] = new_times_utc
        
    data[user_id] = user_config
    save_data(data)
    
    final_freq_desc = get_frequency_description_text(new_frequency, new_times_utc)
    await callback_query.message.edit_text(f"✅ Частоту сповіщень оновлено: <b>{final_freq_desc}</b>", parse_mode="HTML")
    if new_frequency: 
      await callback_query.answer(f"Частоту встановлено: {final_freq_desc}", show_alert=False)
    else:
      await callback_query.answer("Сповіщення вимкнено.", show_alert=False)

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
        print(f"[{datetime.now(timezone.utc).isoformat()}] Немає даних про ціни для відправки користувачу {user_id_int}")
        return

    freq_text_for_msg = get_frequency_description_text(frequency, user_config.get("notification_times_utc"))
    header = f"<b>📈 Оновлення цін ({freq_text_for_msg.lower()})</b>"
    message_body = "\n".join(prices_info)
    final_message = f"{header}\n{message_body}"
    
    kb_after_price = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="♻️ Скинути налаштування", callback_data="reset_all_crypto")],
        [InlineKeyboardButton(text="❌ Зупинити ці сповіщення", callback_data="setfreq_off")] 
    ])
    try:
        await bot.send_message(user_id_int, final_message, reply_markup=kb_after_price, parse_mode="HTML")
    except Exception as e:
        error_msg = str(e).lower()
        user_id_str = str(user_id_int) 
        if "bot was blocked" in error_msg or "user is deactivated" in error_msg or "chat not found" in error_msg:
            print(f"Користувач {user_id_int} заблокував бота або не існує. Видалення даних...")
            current_data_for_delete = load_data()
            if user_id_str in current_data_for_delete:
                del current_data_for_delete[user_id_str]
                save_data(current_data_for_delete)
        else:
            print(f"Не вдалося надіслати повідомлення користувачу {user_id_int}: {e}")

async def price_update_scheduler():
    await asyncio.sleep(10) 
    print(f"[{datetime.now(timezone.utc).isoformat()}] Планувальник регулярних сповіщень запущено (інтервал 5 хвилин).") # ИЗМЕНЕНО
    
    while True:
        now_utc = datetime.now(timezone.utc) 
        current_time_utc_str = now_utc.strftime("%H:%M")
        current_hour_utc = now_utc.hour
        
        all_users_data = load_data() 
        active_tasks_for_gather = []

        for user_id_str, user_config_original in all_users_data.items():
            try:
                user_id_int = int(user_id_str) 
            except ValueError:
                continue

            user_config = user_config_original.copy() 

            frequency = user_config.get("frequency")
            tokens_id_list = user_config.get("tokens_id")
            should_send_regular = False

            if frequency and tokens_id_list:
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
            current_iso_time = datetime.now(timezone.utc).isoformat()
            print(f"[{current_iso_time}] Знайдено {len(active_tasks_for_gather)} регулярних сповіщень для відправки.")
            
            results = await asyncio.gather(*active_tasks_for_gather, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    task_name = "task"
                    try:
                        original_coro = active_tasks_for_gather[i]
                        task_name = original_coro.__qualname__ if hasattr(original_coro, '__qualname__') else original_coro.__name__
                    except Exception:
                        pass
                    print(f"[{current_iso_time}] Помилка у фоновому завданні '{task_name}': {result}")
        
        await asyncio.sleep(300) # ИНТЕРВАЛ 5 МИНУТ (300 секунд)

# --- ОБРАБОТЧИК ТЕКСТОВЫХ СООБЩЕНИЙ (АДМИН / ПОИСК ТОКЕНА) ---
@dp.message() 
async def handle_text_input(message: types.Message):
    user_id_str = str(message.chat.id)
    text = message.text.strip()
    
    if not text or text.startswith("/"):
        return 

    is_admin = message.from_user.id in ADMIN_IDS
    all_users_data = load_data()
    user_config = all_users_data.get(user_id_str, get_default_user_config())

    coin_id_search, coin_name_search, coin_symbol_api_search = await search_token(text.lower())
    was_coin_addition_attempt = bool(coin_id_search) 

    if is_admin:
        is_long_message_for_broadcast = len(text.split()) > 3 or len(text) > 20 
        user_tokens_id_list_for_admin = user_config.get("tokens_id", [])

        if (not was_coin_addition_attempt or 
            len(user_tokens_id_list_for_admin) >= 5 or 
            is_long_message_for_broadcast):
            
            print(f"Адміністратор {message.from_user.id} надсилає розсилку: '{text}'")
            sent_count = 0
            failed_count = 0
            active_subscribers = [uid_s for uid_s, info in all_users_data.items() if info.get("frequency")]

            if not active_subscribers:
                await message.answer("Немає активних користувачів для розсилки (з налаштованою частотою).")
                return

            for uid_to_send_str in active_subscribers:
                if uid_to_send_str == user_id_str: 
                    continue
                try:
                    await bot.send_message(uid_to_send_str, text)
                    sent_count += 1
                except Exception as e:
                    failed_count += 1
                    print(f"Помилка розсилки адміном користувачу {uid_to_send_str}: {e}")
            
            await message.answer(f"✅ Повідомлення для розсилки оброблено.\n"
                                 f"Активних користувачів для розсилки: {len(active_subscribers)}\n"
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

        if coin_id_search in tokens_id_list:
            await message.answer(f"ℹ️ Монета {display_name_to_add} (ID: {hcode(coin_id_search)}) вже обрана.", parse_mode="HTML")
            return

        tokens_id_list.append(coin_id_search)
        tokens_display_list.append(display_name_to_add)
        
        user_config["tokens_id"] = tokens_id_list
        user_config["tokens_display"] = tokens_display_list
        all_users_data[user_id_str] = user_config
        save_data(all_users_data)

        await message.answer(f"✅ Додано: {display_name_to_add} (ID: {hcode(coin_id_search)})", parse_mode="HTML")
        
        if len(tokens_id_list) >= 5:
            await message.answer("Ви обрали 5 монет. Тепер налаштуйте частоту сповіщень: /setfrequency")
        elif len(tokens_id_list) > 0:
            await message.answer("Щоб налаштувати частоту сповіщень, використайте /setfrequency")
        return
    
    if not is_admin and not was_coin_addition_attempt : 
        await message.reply(f"Не вдалося розпізнати '{text}' як тікер монети. Спробуйте ще раз або використайте /start для допомоги.")

# --- ЗАПУСК БОТА ---
async def main(): 
    dp.message.register(start_cmd, Command(commands=["start"]))
    dp.message.register(my_config_cmd, Command(commands=["mycryptoconfig"]))
    dp.message.register(set_frequency_cmd, Command(commands=["setfrequency"]))
    
    dp.message.register(reset_crypto_all_cmd, Command(commands=["resetcrypto"]))
    dp.message.register(stop_crypto_notifications_cmd, Command(commands=["stopcryptonotifications"]))
    
    dp.callback_query.register(add_token_callback, lambda c: c.data.startswith("add_"))
    dp.callback_query.register(process_frequency_callback, lambda c: c.data.startswith("setfreq_"))
    dp.callback_query.register(reset_crypto_all_callback, lambda c: c.data == "reset_all_crypto")

    dp.message.register(handle_text_input) 

    asyncio.create_task(price_update_scheduler())
    
    print(f"[{datetime.now(timezone.utc).isoformat()}] Бот запускається...")
    try:
        await dp.start_polling(bot, skip_updates=True)
    finally:
        await bot.session.close() 
        print(f"[{datetime.now(timezone.utc).isoformat()}] Бот зупинено.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"[{datetime.now(timezone.utc).isoformat()}] Зупинка бота вручну (Ctrl+C)")
    except Exception as e:
        print(f"[{datetime.now(timezone.utc).isoformat()}] Виникла критична помилка під час запуску: {e}")
