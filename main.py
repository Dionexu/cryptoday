import os
import json
import aiohttp
import asyncio
from datetime import datetime, timezone
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.filters import Command
from aiogram.utils.markdown import hcode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "ВАШ_БОТ_ТОКЕН_ТУТ") 
if BOT_TOKEN == "ВАШ_БОТ_ТОКЕН_ТУТ":
    print("ПОПЕРЕДЖЕННЯ: Будь ласка, встановіть ваш справжній BOT_TOKEN!")
    # exit() # Раскомментируйте, если хотите остановить бота, если токен не установлен

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

DATA_FILE = "user_crypto_preferences.json" 

POPULAR_TOKENS_MAP = {
    'BTC': 'bitcoin', 'ETH': 'ethereum', 'SOL': 'solana', 
    'TON': 'the-open-network', 'DOGE': 'dogecoin', 'LINK': 'chainlink', 
    'ADA': 'cardano', 'DOT': 'polkadot', 'MATIC': 'matic-network', 'ARB': 'arbitrum'
}
POPULAR_TOKENS_ORDER = ['BTC', 'ETH', 'SOL', 'TON', 'DOGE', 'LINK', 'ADA', 'DOT', 'MATIC', 'ARB']

ADMIN_IDS = [696165311, 7923967086] 

# --- СОСТОЯНИЯ FSM ДЛЯ ЦЕНОВЫХ АЛЕРТОВ ---
class PriceAlertStates(StatesGroup):
    waiting_coin_ticker = State()
    waiting_lower_target = State()
    waiting_upper_target = State()

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
        "notification_times_utc": [],
        "price_alert_config": None 
    }

# --- ФУНКЦИИ ДЛЯ API COINGECKO (С УЛУЧШЕННЫМ ЛОГИРОВАНИЕМ) ---
async def fetch_price(symbol_id: str) -> str | float: # Возвращает цену или строку ошибки
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={symbol_id}&vs_currencies=usd"
    log_prefix = f"[{datetime.now(timezone.utc).isoformat()}] FetchPrice ({symbol_id}):"
    try:
        async with aiohttp.ClientSession() as session:
            headers = {'User-Agent': 'Mozilla/5.0 (TelegramBot/1.0)'} # Простой User-Agent
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
                            print(f"{log_prefix} 'usd' price not found for {symbol_id} in batch response: {data}")
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

async def search_token(query: str): # Остается как было, но с таймаутом и базовой обработкой
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
    # ... (код этой функции без изменений, как в предыдущем ответе) ...
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

# --- ОБРАБОТЧИКИ КОМАНД И CALLBACK (Включая FSM для Price Alerts) ---
# /start
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    # ... (код этой функции без изменений, как в предыдущем ответе) ...
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
        "Після вибору монет, налаштуй частоту сповіщень командою /setfrequency.\n"
        "Також можеш налаштувати <b>цінове сповіщення</b> на одну монету: /setpricealert\n\n" # Добавлено про price alert
        "<b>Інші команди:</b>\n"
        "/mycryptoconfig - переглянути поточні налаштування регулярних сповіщень\n"
        "/mypricealert - переглянути налаштування цінового сповіщення\n" # Добавлено
        "/resetcrypto - скинути всі налаштування криптовалют (включаючи цінове сповіщення)\n"
        "/stopcryptonotifications - зупинити регулярні сповіщення про ціни\n"
        "/removepricealert - вимкнути цінове сповіщення", # Добавлено
        parse_mode="HTML"
    )

# /mycryptoconfig
@dp.message(Command("mycryptoconfig"))
async def my_config_cmd(message: types.Message):
    # ... (код этой функции без изменений) ...
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
        f"<b>⚙️ Ваші поточні налаштування регулярних сповіщень:</b>\n\n"
        f"<b>Обрані монети:</b> {tokens_display_str}\n"
        f"<b>Частота сповіщень:</b> {freq_desc}\n\n"
        "Щоб змінити монети, просто додайте нові або використайте /resetcrypto.\n"
        "Щоб змінити частоту, використайте /setfrequency.",
        parse_mode="HTML"
    )

# Callback add_
@dp.callback_query(lambda c: c.data.startswith("add_"))
async def add_token_callback(callback_query: types.CallbackQuery):
    # ... (код этой функции без изменений) ...
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

# /setfrequency
@dp.message(Command("setfrequency"))
async def set_frequency_cmd(message: types.Message):
    # ... (код этой функции без изменений) ...
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

# Callback setfreq_
@dp.callback_query(lambda c: c.data.startswith("setfreq_"))
async def process_frequency_callback(callback_query: types.CallbackQuery):
    # ... (код этой функции без изменений) ...
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

# --- FSM для /setpricealert ---
@dp.message(Command("setpricealert"))
async def cmd_set_price_alert_start(message: types.Message, state: FSMContext):
    # ... (код этой функции из предыдущего ответа) ...
    await state.set_state(PriceAlertStates.waiting_coin_ticker)
    await message.answer(
        "<b>Налаштування цінового сповіщення.</b>\n"
        "Напишіть тікер монети, для якої ви хочете встановити сповіщення (наприклад, BTC, ETH, SOL):",
        parse_mode="HTML"
    )

@dp.message(PriceAlertStates.waiting_coin_ticker)
async def process_alert_coin_ticker(message: types.Message, state: FSMContext):
    # ... (код этой функции из предыдущего ответа) ...
    ticker_input = message.text.strip().lower()
    if not ticker_input or len(ticker_input) > 15:
        await message.answer("Будь ласка, введіть коректний тікер (наприклад, BTC). Спробуйте ще раз або напишіть /cancelalert.")
        return

    coin_id, coin_name, coin_symbol_api = await search_token(ticker_input)

    if not coin_id:
        await message.answer(f"❌ Монету '{message.text.strip()}' не знайдено. Спробуйте інший тікер або напишіть /cancelalert.")
        return

    display_name = coin_symbol_api.upper() if coin_symbol_api else coin_name

    await state.update_data(alert_coin_id=coin_id, alert_coin_display=display_name)
    await state.set_state(PriceAlertStates.waiting_lower_target)
    await message.answer(
        f"Обрано монету: <b>{display_name}</b> (ID: {hcode(coin_id)}).\n"
        "Тепер введіть <b>нижній</b> поріг ціни (в USD), при досягненні якого ви отримаєте сповіщення (наприклад, 29500.50):",
        parse_mode="HTML"
    )

@dp.message(PriceAlertStates.waiting_lower_target)
async def process_alert_lower_target(message: types.Message, state: FSMContext):
    # ... (код этой функции из предыдущего ответа) ...
    try:
        lower_target = float(message.text.strip().replace(',', '.')) 
        if lower_target <= 0:
            raise ValueError("Ціна повинна бути позитивною.")
    except ValueError:
        await message.answer("Будь ласка, введіть коректне числове значення для нижнього порогу (наприклад, 29500.50) або напишіть /cancelalert.")
        return

    await state.update_data(lower_target=lower_target)
    await state.set_state(PriceAlertStates.waiting_upper_target)
    await message.answer(
        f"Нижній поріг встановлено: <b>${lower_target:,.2f}</b>.\n"
        "Тепер введіть <b>верхній</b> поріг ціни (в USD), він має бути більшим за нижній (наприклад, 31000):",
        parse_mode="HTML"
    )

@dp.message(PriceAlertStates.waiting_upper_target)
async def process_alert_upper_target(message: types.Message, state: FSMContext):
    # ... (код этой функции из предыдущего ответа) ...
    try:
        upper_target = float(message.text.strip().replace(',', '.'))
        user_fsm_data = await state.get_data()
        lower_target = user_fsm_data.get('lower_target')

        if upper_target <= 0:
             raise ValueError("Ціна повинна бути позитивною.")
        if lower_target is not None and upper_target <= lower_target:
            await message.answer(f"Верхній поріг (<b>${upper_target:,.2f}</b>) має бути більшим за нижній (<b>${lower_target:,.2f}</b>). "
                                 "Спробуйте ще раз або напишіть /cancelalert.", parse_mode="HTML")
            return
    except ValueError:
        await message.answer("Будь ласка, введіть коректне числове значення для верхнього порогу (наприклад, 31000) або напишіть /cancelalert.")
        return

    user_id = str(message.from_user.id)
    all_data = load_data()
    user_config = all_data.get(user_id, get_default_user_config())

    user_config["price_alert_config"] = {
        "coin_id": user_fsm_data.get('alert_coin_id'),
        "coin_display": user_fsm_data.get('alert_coin_display'),
        "lower_target": lower_target,
        "upper_target": upper_target,
        "alert_sent_lower": False, 
        "alert_sent_upper": False,
        "is_active": True
    }
    all_data[user_id] = user_config
    save_data(all_data)

    await state.clear() 
    await message.answer(
        f"✅ <b>Цінове сповіщення налаштовано!</b>\n"
        f"Монета: <b>{user_config['price_alert_config']['coin_display']}</b>\n"
        f"Нижній поріг: <b>${user_config['price_alert_config']['lower_target']:,.2f}</b>\n"
        f"Верхній поріг: <b>${user_config['price_alert_config']['upper_target']:,.2f}</b>\n\n"
        "Ви отримаєте повідомлення, коли ціна досягне одного з цих порогів.",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove() 
    )

@dp.message(Command("cancelalert"), PriceAlertStates.any_state)
async def cancel_alert_setup(message: types.Message, state: FSMContext):
    # ... (код этой функции из предыдущего ответа) ...
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Немає активної сесії налаштування для скасування.")
        return

    await state.clear()
    await message.answer("Налаштування цінового сповіщення скасовано.", reply_markup=ReplyKeyboardRemove())

# /mypricealert
@dp.message(Command("mypricealert"))
async def cmd_my_price_alert(message: types.Message):
    # ... (код этой функции из предыдущего ответа) ...
    user_id = str(message.chat.id)
    data = load_data()
    user_config = data.get(user_id)
    alert_config = user_config.get("price_alert_config") if user_config else None

    if alert_config and alert_config.get("is_active"):
        await message.answer(
            f"<b>🔔 Ваше поточне цінове сповіщення:</b>\n"
            f"Монета: <b>{alert_config['coin_display']}</b> (ID: {hcode(alert_config['coin_id'])})\n"
            f"Нижній поріг: <b>${alert_config['lower_target']:,.2f}</b>\n"
            f"Верхній поріг: <b>${alert_config['upper_target']:,.2f}</b>\n\n"
            "Щоб змінити, використайте /setpricealert.\n"
            "Щоб вимкнути, використайте /removepricealert.",
            parse_mode="HTML"
        )
    else:
        await message.answer("У вас немає активних цінових сповіщень. Налаштуйте за допомогою /setpricealert.")

# /removepricealert
@dp.message(Command("removepricealert"))
async def cmd_remove_price_alert(message: types.Message):
    # ... (код этой функции из предыдущего ответа) ...
    user_id = str(message.chat.id)
    data = load_data()
    user_config = data.get(user_id)

    if user_config and user_config.get("price_alert_config") and user_config["price_alert_config"].get("is_active"):
        user_config["price_alert_config"]["is_active"] = False 
        data[user_id] = user_config
        save_data(data)
        await message.answer("🗑️ Ваше цінове сповіщення вимкнено. Ви більше не отримуватимете повідомлень по ньому.\n"
                             "Щоб налаштувати нове, використайте /setpricealert.")
    else:
        await message.answer("У вас немає активних цінових сповіщень для вимкнення.")

# /resetcrypto (теперь сбрасывает и price_alert_config)
@dp.message(Command("resetcrypto")) 
async def reset_crypto_all_cmd(message: types.Message):
    user_id = str(message.from_user.id)
    data = load_data()
    if user_id in data:
        data[user_id] = get_default_user_config() # Сбрасываем на дефолтные значения, включая price_alert_config = None
        save_data(data)
        await message.answer("♻️ Всі ваші налаштування для криптовалют (включаючи цінове сповіщення) скинуто. /start щоб почати знову.")
    else:
        await message.answer("У вас ще немає налаштувань для скидання.")

# Callback reset_all_crypto (теперь сбрасывает и price_alert_config)
@dp.callback_query(lambda c: c.data == "reset_all_crypto")
async def reset_crypto_all_callback(callback_query: types.CallbackQuery):
    user_id = str(callback_query.from_user.id)
    data = load_data()
    if user_id in data:
        data[user_id] = get_default_user_config()
        save_data(data)
    try:
        await callback_query.message.edit_text("♻️ Всі ваші налаштування для криптовалют (включаючи цінове сповіщення) скинуто. /start щоб почати знову.")
    except Exception: 
        await bot.send_message(user_id, "♻️ Всі ваші налаштування для криптовалют (включаючи цінове сповіщення) скинуто. /start щоб почати знову.")
    await callback_query.answer("Налаштування скинуто", show_alert=False)

# /stopcryptonotifications
@dp.message(Command("stopcryptonotifications"))
async def stop_crypto_notifications_cmd(message: types.Message):
    # ... (код этой функции без изменений, останавливает только регулярные уведомления) ...
    user_id = str(message.from_user.id)
    data = load_data()
    user_config = data.get(user_id)

    if user_config and user_config.get("frequency") is not None:
        user_config["frequency"] = None
        user_config["notification_times_utc"] = [] 
        data[user_id] = user_config
        save_data(data)
        await message.answer("❌ Регулярні сповіщення про криптовалюти зупинені.")
    else:
        await message.answer("Регулярні сповіщення вже вимкнені або не були налаштовані.")


# --- ПЛАНИРОВЩИК (ОБЪЕДИНЕННЫЙ) ---
async def check_and_process_price_alerts(user_id_int: int, user_config: dict):
    # ... (код этой функции из предыдущего ответа, с улучшенной обработкой цены) ...
    alert_config = user_config.get("price_alert_config")
    if not alert_config or not alert_config.get("is_active"):
        return 

    coin_id_to_check = alert_config.get("coin_id")
    if not coin_id_to_check:
        return

    current_price_result = await fetch_price(coin_id_to_check) # Это уже возвращает float или строку ошибки
    
    if not isinstance(current_price_result, (int, float)):
        # print(f"[{datetime.now(timezone.utc).isoformat()}] Не вдалося отримати числову ціну для {coin_id_to_check} для алерту користувача {user_id_int}. Отримано: {current_price_result}")
        return 

    current_price = current_price_result # Теперь это точно float

    lower_target = alert_config.get("lower_target")
    upper_target = alert_config.get("upper_target")
    alert_sent_lower = alert_config.get("alert_sent_lower", False)
    alert_sent_upper = alert_config.get("alert_sent_upper", False)
    coin_display = alert_config.get("coin_display", coin_id_to_check.capitalize())

    data_changed = False 

    # Проверка нижнего порога
    if lower_target is not None: # Убедимся, что порог установлен
        if not alert_sent_lower and current_price <= lower_target:
            message_text = (f"⚠️ <b>Ціновий ALERT!</b> ⚠️\n"
                            f"Монета: <b>{coin_display}</b>\n"
                            f"Ціна досягла або опустилася нижче вашого порогу: <b>${lower_target:,.2f}</b>\n"
                            f"Поточна ціна: <b>${current_price:,.2f}</b>")
            try:
                await bot.send_message(user_id_int, message_text, parse_mode="HTML")
                alert_config["alert_sent_lower"] = True
                data_changed = True
                print(f"[{datetime.now(timezone.utc).isoformat()}] Відправлено ALERT (нижній) для {user_id_int} по монеті {coin_display}")
            except Exception as e:
                print(f"Помилка відправки ALERT (нижній) для {user_id_int}: {e}")
        
        elif alert_sent_lower and current_price > lower_target * 1.002: 
            alert_config["alert_sent_lower"] = False
            data_changed = True
            print(f"[{datetime.now(timezone.utc).isoformat()}] 'Перезаряджено' нижній ALERT для {user_id_int} по монеті {coin_display} (ціна: ${current_price:,.2f})")

    # Проверка верхнего порога
    if upper_target is not None: # Убедимся, что порог установлен
        if not alert_sent_upper and current_price >= upper_target:
            message_text = (f"⚠️ <b>Ціновий ALERT!</b> ⚠️\n"
                            f"Монета: <b>{coin_display}</b>\n"
                            f"Ціна досягла або перевищила ваш поріг: <b>${upper_target:,.2f}</b>\n"
                            f"Поточна ціна: <b>${current_price:,.2f}</b>")
            try:
                await bot.send_message(user_id_int, message_text, parse_mode="HTML")
                alert_config["alert_sent_upper"] = True
                data_changed = True
                print(f"[{datetime.now(timezone.utc).isoformat()}] Відправлено ALERT (верхній) для {user_id_int} по монеті {coin_display}")
            except Exception as e:
                print(f"Помилка відправки ALERT (верхній) для {user_id_int}: {e}")

        elif alert_sent_upper and current_price < upper_target * 0.998: 
            alert_config["alert_sent_upper"] = False
            data_changed = True
            print(f"[{datetime.now(timezone.utc).isoformat()}] 'Перезаряджено' верхній ALERT для {user_id_int} по монеті {coin_display} (ціна: ${current_price:,.2f})")

    if data_changed:
        all_users_data_local = load_data() 
        if str(user_id_int) in all_users_data_local: 
            # Обновляем только price_alert_config внутри существующего user_config
            if "price_alert_config" in all_users_data_local[str(user_id_int)]:
                 all_users_data_local[str(user_id_int)]["price_alert_config"].update(alert_config)
            else: # Если вдруг его там не было, но должен быть после настройки
                 all_users_data_local[str(user_id_int)]["price_alert_config"] = alert_config
            save_data(all_users_data_local)

async def send_user_price_update(user_id_int: int, user_config: dict, frequency: str):
    # ... (код этой функции с использованием fetch_prices_batch, без изменений логики отображения ошибок) ...
    tokens_id_list = user_config.get("tokens_id", [])
    if not tokens_id_list:
        return

    prices_info = []
    display_names = user_config.get("tokens_display", [])
    if not display_names or len(display_names) != len(tokens_id_list):
        display_names = [tid.capitalize() for tid in tokens_id_list] 

    fetched_prices_map = await fetch_prices_batch(tokens_id_list)
    # any_price_fetched = False # Можно удалить, если не используется для решения отправлять/не отправлять

    for i, token_cg_id in enumerate(tokens_id_list):
        price_result = fetched_prices_map.get(token_cg_id, "N/A") 
        token_display_name = display_names[i] if i < len(display_names) else token_cg_id.capitalize()
        
        if isinstance(price_result, (int, float)):
            prices_info.append(f"{token_display_name}: ${price_result:,.2f}")
            # any_price_fetched = True
        else: 
            error_display_text = "немає даних"
            if price_result == "ErrorAPI": error_display_text = "помилка API"
            elif price_result == "Timeout": error_display_text = "таймаут API"
            elif price_result == "ConnectionError": error_display_text = "помилка зʼєднання"
            elif price_result == "NoPriceData": error_display_text = "ціну не знайдено"
            elif price_result == "N/A": error_display_text = "недоступно"
            prices_info.append(f"{token_display_name}: {error_display_text}")
    
    if not prices_info:
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
    # ... (обновленный код этой функции с вызовом send_user_price_update и check_and_process_price_alerts)
    await asyncio.sleep(15) 
    print(f"[{datetime.now(timezone.utc).isoformat()}] Планувальник сповіщень (регулярні + цінові алерти) запущено.")
    
    while True:
        now_utc = datetime.now(timezone.utc) 
        current_time_utc_str = now_utc.strftime("%H:%M")
        current_hour_utc = now_utc.hour
        
        all_users_data = load_data() 
        
        active_tasks = [] # Собираем все задачи (регулярные и алерты) в один список

        for user_id_str, user_config in all_users_data.items():
            try:
                user_id_int = int(user_id_str) 
            except ValueError:
                continue

            # --- Логика для регулярных обновлений ---
            frequency = user_config.get("frequency")
            tokens_id_list = user_config.get("tokens_id")
            should_send_regular = False
            if frequency and tokens_id_list:
                if frequency == "hourly" and now_utc.minute == 0: should_send_regular = True
                elif frequency == "2_hours" and current_hour_utc % 2 == 0 and now_utc.minute == 0: should_send_regular = True
                elif frequency == "daily_1":
                    times_utc = user_config.get("notification_times_utc", [])
                    if times_utc and current_time_utc_str == times_utc[0]: should_send_regular = True
                elif frequency == "daily_2":
                    times_utc = user_config.get("notification_times_utc", [])
                    if times_utc and current_time_utc_str in times_utc: should_send_regular = True
            
            if should_send_regular:
                active_tasks.append(send_user_price_update(user_id_int, user_config.copy(), frequency)) # .copy() для безопасности
            
            # --- Логика для ценовых алертов ---
            if user_config.get("price_alert_config") and user_config["price_alert_config"].get("is_active"):
                active_tasks.append(check_and_process_price_alerts(user_id_int, user_config.copy())) # .copy()
        
        if active_tasks:
            print(f"[{datetime.now(timezone.utc).isoformat()}] Знайдено {len(active_tasks)} завдань для виконання (регулярні/алерти).")
            # Выполняем все задачи параллельно, обрабатывая исключения, чтобы одна упавшая задача не остановила все
            results = await asyncio.gather(*active_tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    print(f"[{datetime.now(timezone.utc).isoformat()}] Помилка у фоновому завданні {active_tasks[i].__name__ if hasattr(active_tasks[i], '__name__') else 'task'}: {result}")

        await asyncio.sleep(60)

# --- ОБРАБОТЧИК ТЕКСТОВЫХ СООБЩЕНИЙ (АДМИН / ПОИСК ТОКЕНА) ---
@dp.message() 
async def handle_text_input(message: types.Message, state: FSMContext): # Добавили state
    # Сначала проверяем, не находимся ли мы в каком-либо состоянии FSM
    current_fsm_state = await state.get_state()
    if current_fsm_state is not None:
        # Если мы в состоянии FSM, этот хендлер не должен перехватывать ввод,
        # предназначенный для FSM. Хендлеры состояний должны сработать раньше.
        # Однако, если они не сработали, можно вывести сообщение или ничего не делать.
        # print(f"Сообщение '{message.text}' получено в состоянии FSM: {current_fsm_state}, но не обработано хендлером состояния.")
        return 
        
    user_id_str = str(message.chat.id)
    text = message.text.strip()
    
    if message.from_user.id in ADMIN_IDS:
        if not text.startswith("/"): 
            all_users_data = load_data()
            sent_count = 0
            failed_count = 0
            
            active_subscribers = [uid_s for uid_s, info in all_users_data.items() if info.get("frequency") or (info.get("price_alert_config") and info["price_alert_config"].get("is_active"))] # Админ пишет всем активным

            if not active_subscribers:
                await message.answer("Немає активних користувачів для розсилки (з налаштованою частотою або ціновим алертом).")
                return

            for uid_to_send_str in active_subscribers:
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

    if text and not text.startswith("/"):
        all_users_data = load_data() 
        user_config = all_users_data.get(user_id_str, get_default_user_config())

        tokens_id_list = user_config.get("tokens_id", [])
        tokens_display_list = user_config.get("tokens_display", [])

        if len(tokens_id_list) >= 5:
            await message.answer("❗ Ти вже обрав 5 монет для регулярних сповіщень. Максимум.\nЩоб змінити, використай /resetcrypto і додай нові.")
            return

        coin_id, coin_name, coin_symbol_api = await search_token(text.lower())

        if not coin_id:
            await message.answer(f"❌ Монету '{text}' не знайдено. Спробуй інший запит або тікер.")
            return
        
        display_name_to_add = coin_symbol_api.upper() if coin_symbol_api else coin_name

        if coin_id in tokens_id_list:
            await message.answer(f"ℹ️ Монета {display_name_to_add} (ID: {hcode(coin_id)}) вже обрана для регулярних сповіщень.", parse_mode="HTML")
            return

        tokens_id_list.append(coin_id)
        tokens_display_list.append(display_name_to_add)
        
        user_config["tokens_id"] = tokens_id_list
        user_config["tokens_display"] = tokens_display_list
        all_users_data[user_id_str] = user_config
        save_data(all_users_data)

        await message.answer(f"✅ Додано для регулярних сповіщень: {display_name_to_add} (ID: {hcode(coin_id)})", parse_mode="HTML")
        
        if len(tokens_id_list) >= 5:
            await message.answer("Ви обрали 5 монет для регулярних сповіщень. Тепер налаштуйте частоту: /setfrequency")
        elif len(tokens_id_list) > 0:
            await message.answer("Щоб налаштувати частоту регулярних сповіщень, використайте /setfrequency")
        return 

# --- ЗАПУСК БОТА ---
async def main(): 
    # Регистрация хендлеров
    dp.message.register(start_cmd, Command(commands=["start"]))
    dp.message.register(my_config_cmd, Command(commands=["mycryptoconfig"]))
    dp.message.register(set_frequency_cmd, Command(commands=["setfrequency"]))
    
    # FSM для price alert
    dp.message.register(cmd_set_price_alert_start, Command(commands=["setpricealert"]))
    dp.message.register(process_alert_coin_ticker, PriceAlertStates.waiting_coin_ticker)
    dp.message.register(process_alert_lower_target, PriceAlertStates.waiting_lower_target)
    dp.message.register(process_alert_upper_target, PriceAlertStates.waiting_upper_target)
    dp.message.register(cancel_alert_setup, Command(commands=["cancelalert"]), PriceAlertStates.any_state)

    dp.message.register(cmd_my_price_alert, Command(commands=["mypricealert"]))
    dp.message.register(cmd_remove_price_alert, Command(commands=["removepricealert"]))

    dp.message.register(reset_crypto_all_cmd, Command(commands=["resetcrypto"]))
    dp.message.register(stop_crypto_notifications_cmd, Command(commands=["stopcryptonotifications"]))
    
    dp.callback_query.register(add_token_callback, lambda c: c.data.startswith("add_"))
    dp.callback_query.register(process_frequency_callback, lambda c: c.data.startswith("setfreq_"))
    dp.callback_query.register(reset_crypto_all_callback, lambda c: c.data == "reset_all_crypto")
    # Callback для `setfreq_off` (остановка регулярных уведомлений) уже обрабатывается в `process_frequency_callback`

    # Текстовый обработчик должен быть последним из dp.message.register
    dp.message.register(handle_text_input) 

    asyncio.create_task(price_update_scheduler())
    
    print(f"[{datetime.now(timezone.utc).isoformat()}] Бот запускається...")
    try:
        await dp.start_polling(bot, skip_updates=True) # skip_updates=True может быть полезно при перезапуске
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
