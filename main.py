import os
import json
import asyncio
import logging
from aiohttp import web
from datetime import datetime, timedelta
import aiohttp

from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger(__name__)

# --- Environment Variables & Configuration ---
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("No BOT_TOKEN provided in environment variables.")

WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
if not WEBHOOK_HOST:
    raise RuntimeError("No WEBHOOK_HOST provided in environment variables.")

if not WEBHOOK_HOST.startswith(("http://", "https://")):
    WEBHOOK_HOST = "https://" + WEBHOOK_HOST

WEBHOOK_PATH = f"/webhook/{TOKEN.split(':')[0]}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
PORT = int(os.environ.get("PORT", 8080)) # Render.com sets PORT env var

logger.info(f"🚀 Starting on port {PORT}")
logger.info(f"Webhook URL configured: {WEBHOOK_URL}")

# --- Bot Initialization ---
bot = Bot(TOKEN, parse_mode=ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# --- Global Variables & Caches ---
user_settings = {} # Stores {"coins": [], "frequency": None, "current_step": "INIT"}
coin_list_cache = None
COIN_LIST_LOAD_ATTEMPTED = False # Flag to ensure we don't get stuck in loops if API is down

# --- Helper Functions ---
def get_user_data(user_id):
    """Helper to get user data, initializing if not present."""
    return user_settings.setdefault(user_id, {"coins": [], "frequency": None, "current_step": "INIT"})

async def ensure_coin_list_loaded(message_or_callback: types.Union[types.Message, types.CallbackQuery]):
    """Checks if coin list is loaded, sends message if not."""
    global COIN_LIST_LOAD_ATTEMPTED
    if not coin_list_cache or not isinstance(coin_list_cache, list):
        text = "⚠️ Список монет наразі недоступний. Можливо, є проблеми з API CoinGecko або перевищено ліміт запитів. Спробуйте пізніше. Натисніть /start, щоб спробувати оновити."
        if not COIN_LIST_LOAD_ATTEMPTED: # If first attempt after startup failed
             logger.warning("Coin list not loaded. Attempting to load now.")
             await load_coin_list() # Try to load it again
             if not coin_list_cache or not isinstance(coin_list_cache, list): # Check again after attempt
                logger.warning("Coin list still not loaded after explicit attempt in ensure_coin_list_loaded.")
             else:
                logger.info("Coin list successfully loaded after explicit attempt in ensure_coin_list_loaded.")
                return True # Successfully loaded
        else:
            logger.warning("Coin list not loaded or not a list when ensure_coin_list_loaded was called, and load was already attempted.")

        # Send message only if still not loaded
        if not coin_list_cache or not isinstance(coin_list_cache, list):
            if isinstance(message_or_callback, types.Message):
                await message_or_callback.answer(text)
            elif isinstance(message_or_callback, types.CallbackQuery):
                try:
                    await message_or_callback.message.answer(text)
                except Exception as e: # If original message is too old to reply to
                    await bot.send_message(message_or_callback.from_user.id, text)
                await message_or_callback.answer()
            return False
    return True


def create_mock_message_from_callback(callback: types.CallbackQuery) -> types.Message:
    """Creates a mock Message object from a CallbackQuery for handler reuse."""
    return types.Message(
        message_id=callback.message.message_id,
        date=callback.message.date,
        chat=callback.message.chat,
        from_user=callback.from_user,
    )

# --- CoinGecko API Interaction ---
async def load_coin_list():
    global coin_list_cache, COIN_LIST_LOAD_ATTEMPTED
    COIN_LIST_LOAD_ATTEMPTED = True # Mark that an attempt is being made/has been made
    max_retries = 3
    base_delay = 10  # seconds

    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting to load coin list (Attempt {attempt + 1}/{max_retries})...")
            async with aiohttp.ClientSession() as session:
                url = "https://api.coingecko.com/api/v3/coins/list"
                async with session.get(url, timeout=15) as resp: # Added timeout
                    if resp.status == 200:
                        data = await resp.json()
                        if isinstance(data, list):
                            coin_list_cache = data
                            logger.info(f"✅ Coin list loaded successfully. Total: {len(coin_list_cache)} coins.")
                            return True # Success
                        else:
                            logger.error(f"⚠️ Coin list loaded but is not a list. Type: {type(data)}. Data: {str(data)[:200]}")
                            coin_list_cache = [] # Set to empty list to avoid type errors
                    elif resp.status == 429:
                        logger.warning(f"⚠️ Rate limit exceeded (429) on attempt {attempt + 1}. Waiting to retry...")
                        # Don't return here, let it retry after delay
                    else:
                        logger.error(f"⚠️ Failed to load coin list. Status: {resp.status}, Response: {await resp.text()}")
                        coin_list_cache = []
                    # For any non-200 or non-429 error that's not a client error, break retry if not last attempt
                    if resp.status not in [200, 429] and attempt < max_retries -1:
                         logger.error(f"Non-retryable API error {resp.status}. Stopping retries.")
                         break


        except aiohttp.ClientError as e: # Handles connection errors, timeouts
            logger.error(f"⚠️ ClientError loading coin list on attempt {attempt + 1}: {e}")
        except asyncio.TimeoutError:
            logger.error(f"⚠️ TimeoutError loading coin list on attempt {attempt + 1}.")
        except Exception as e:
            logger.error(f"⚠️ Unexpected error loading coin list on attempt {attempt + 1}: {e}")
        
        if attempt < max_retries - 1:
            delay = base_delay * (2 ** attempt) # Exponential backoff
            logger.info(f"Waiting {delay} seconds before next attempt...")
            await asyncio.sleep(delay)
        else:
            logger.error("Max retries reached for loading coin list. List remains unavailable.")
            coin_list_cache = [] # Ensure it's empty
            return False # Failed after all retries
    
    if not coin_list_cache: # If loop finished without success
        coin_list_cache = []
        return False
    return False # Should not be reached if logic is correct, but as a fallback


# --- Sequential Setup Steps ---

async def start_coin_selection(message_or_callback: types.Union[types.Message, types.CallbackQuery]):
    user_id = message_or_callback.from_user.id
    logger.info(f"[User {user_id}] Entering start_coin_selection. Type: {type(message_or_callback)}")
    user_data = get_user_data(user_id)
    user_data["current_step"] = "SELECTING_COINS"
    user_data["selected_coins_buffer"] = list(user_data.get("coins", [])) 

    if not await ensure_coin_list_loaded(message_or_callback):
        # ensure_coin_list_loaded already sends a message if it fails
        return

    current_coins_text_parts = []
    if coin_list_cache: 
        for coin_id_in_buffer in user_data["selected_coins_buffer"]:
            found_coin = next((c for c in coin_list_cache if c.get('id') == coin_id_in_buffer), None)
            current_coins_text_parts.append(
                f"{found_coin.get('name', coin_id_in_buffer.capitalize())} ({found_coin.get('symbol','N/A').upper()})" if found_coin else coin_id_in_buffer.capitalize()
            )
    else: # Should not happen if ensure_coin_list_loaded passed
         current_coins_text_parts = [c.capitalize() for c in user_data["selected_coins_buffer"]]


    current_coins_text = ", ".join(current_coins_text_parts) if current_coins_text_parts else "не обрано"
    
    text = (
        "👋 Давайте налаштуємо вашого крипто-помічника!\n\n"
        "<b>Крок 1: Оберіть монети</b> (максимум 3)\n"
        f"Поточний вибір: {current_coins_text}\n\n"
        "Введіть назву або символ монети (наприклад, bitcoin, solana, doge).\n"
        "Коли завершите, введіть 'готово'."
    )
    
    try:
        if isinstance(message_or_callback, types.Message):
            await message_or_callback.answer(text, parse_mode=ParseMode.HTML)
        elif isinstance(message_or_callback, types.CallbackQuery):
            await message_or_callback.message.edit_text(text, parse_mode=ParseMode.HTML)
        if isinstance(message_or_callback, types.CallbackQuery): await message_or_callback.answer()
        logger.info(f"[User {user_id}] Sent coin selection prompt.")
    except Exception as e:
        logger.error(f"[User {user_id}] Error sending/editing message in start_coin_selection: {e}")


async def start_frequency_selection(message_or_callback: types.Union[types.Message, types.CallbackQuery]):
    user_id = message_or_callback.from_user.id
    logger.info(f"[User {user_id}] Entering start_frequency_selection.")
    user_data = get_user_data(user_id)
    user_data["current_step"] = "SELECTING_FREQUENCY"

    current_freq_code = user_data.get("frequency")
    frequency_options_display = {
        "2h": "Один раз на 2 години", "12h": "Один раз на 12 годин", "24h": "Один раз на добу"
    }
    def freq_text(text, value): return f"✅ {text}" if current_freq_code == value else text
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=freq_text(frequency_options_display["2h"], "2h"), callback_data="setfreq_2h")],
        [InlineKeyboardButton(text=freq_text(frequency_options_display["12h"], "12h"), callback_data="setfreq_12h")],
        [InlineKeyboardButton(text=freq_text(frequency_options_display["24h"], "24h"), callback_data="setfreq_24h")]
    ])
    text = ("<b>Крок 2: Оберіть частоту оновлення цін</b>\n\n"
            "Як часто ви бажаєте отримувати автоматичні оновлення? (Ця функція буде додана пізніше, зараз це налаштування зберігається для майбутнього використання).")
    try:
        if isinstance(message_or_callback, types.Message):
            await message_or_callback.answer(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        elif isinstance(message_or_callback, types.CallbackQuery):
            await message_or_callback.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        if isinstance(message_or_callback, types.CallbackQuery): await message_or_callback.answer()
        logger.info(f"[User {user_id}] Sent frequency selection prompt.")
    except Exception as e:
        logger.error(f"[User {user_id}] Error sending/editing message in start_frequency_selection: {e}")


async def display_main_menu(message_or_callback: types.Union[types.Message, types.CallbackQuery]):
    user_id = message_or_callback.from_user.id
    logger.info(f"[User {user_id}] Entering display_main_menu.")
    user_data = get_user_data(user_id)
    user_data["current_step"] = "SETUP_COMPLETE"
    selected_coins = user_data.get("coins", [])
    frequency_code = user_data.get("frequency")
    frequency_options_display = {"2h": "кожні 2 години", "12h": "кожні 12 годин", "24h": "щодня"}
    freq_display = frequency_options_display.get(frequency_code, "не встановлено")
    coins_display_parts = []
    if coin_list_cache: # Check if cache is available
        for coin_id in selected_coins:
            coin_info = next((c for c in coin_list_cache if c.get('id') == coin_id), None)
            coins_display_parts.append(coin_info.get('name', coin_id.capitalize()) if coin_info else coin_id.capitalize())
    else: # Fallback if coin_list_cache is still None
        coins_display_parts = [c.capitalize() for c in selected_coins]
        if selected_coins: # Add a note if cache is unavailable but coins are selected
            coins_display_parts.append("(інформація про назви монет тимчасово недоступна)")

    coins_text = ", ".join(coins_display_parts) if coins_display_parts else "не обрано"
    text = (f"✅ Налаштування завершено!\n\n<b>Обрані монети:</b> {coins_text}\n"
            f"<b>Частота (для майбутніх авто-оновлень):</b> {freq_display}\n\nТепер ви можете:")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 Дивитися ціни зараз", callback_data="get_prices")],
        [InlineKeyboardButton(text="🔄 Скинути налаштування", callback_data="reset_settings_sequential")]
    ])
    try:
        if isinstance(message_or_callback, types.Message):
            await message_or_callback.answer(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        elif isinstance(message_or_callback, types.CallbackQuery):
            await message_or_callback.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        if isinstance(message_or_callback, types.CallbackQuery): await message_or_callback.answer()
        logger.info(f"[User {user_id}] Displayed main menu.")
    except Exception as e:
        logger.error(f"[User {user_id}] Error sending/editing message in display_main_menu: {e}")

# --- Command Handlers & Main Flow ---
@router.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    logger.info(f"[User {user_id}] Received /start command.")
    user_data = get_user_data(user_id)
    
    # Attempt to load coin list if not already loaded or if an attempt hasn't been made yet
    # This is crucial for the first interaction or after a long downtime.
    if not coin_list_cache and not COIN_LIST_LOAD_ATTEMPTED:
        logger.info(f"[User {user_id}] Coin list not cached and no load attempt made. Triggering load_coin_list from /start.")
        await load_coin_list() # This will set COIN_LIST_LOAD_ATTEMPTED

    if user_data.get("current_step") == "SETUP_COMPLETE" and user_data.get("coins") and user_data.get("frequency"):
        await display_main_menu(message)
    else:
        logger.info(f"[User {user_id}] Setup not complete or explicit /start. Resetting and starting coin selection.")
        user_data["coins"] = [] # Reset coins for a fresh setup if not complete
        user_data["frequency"] = None # Reset frequency
        await start_coin_selection(message)

@router.callback_query(F.data == "reset_settings_sequential")
async def handle_reset_settings_sequential(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_data = get_user_data(user_id)
    user_data["coins"] = []
    user_data["frequency"] = None
    user_data["current_step"] = "INIT"
    logger.info(f"User {user_id} reset settings via callback.")
    await callback.answer("🔄 Налаштування скинуто.")
    await start_coin_selection(callback)

# --- Coin Selection Handlers ---
@router.message(F.text)
async def handle_message_input(message: types.Message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    logger.info(f"[User {user_id}] Received text: '{message.text}'. Current step: {user_data.get('current_step')}")

    if user_data.get("current_step") == "SELECTING_COINS":
        logger.info(f"[User {user_id}] In SELECTING_COINS step.")
        if not await ensure_coin_list_loaded(message):
            logger.warning(f"[User {user_id}] Coin list not loaded, exiting handle_message_input for coin selection.")
            return # ensure_coin_list_loaded sends a message

        coin_input_text = message.text.lower().strip()
        logger.info(f"[User {user_id}] Coin input text: '{coin_input_text}'")

        if coin_input_text == "готово":
            user_data["coins"] = list(user_data.get("selected_coins_buffer", []))
            if not user_data["coins"]:
                logger.info(f"[User {user_id}] 'готово' entered but no coins selected.")
                try: await message.answer("⚠️ Будь ласка, оберіть хоча б одну монету перед тим, як продовжити, або введіть 'скасувати', щоб почати знову з /start.")
                except Exception as e: logger.error(f"Error sending 'no coins selected' message: {e}")
                return
            logger.info(f"[User {user_id}] 'готово' entered. Coins: {user_data['coins']}. Proceeding to frequency selection.")
            if "selected_coins_buffer" in user_data: del user_data["selected_coins_buffer"]
            await start_frequency_selection(message)
            return
        
        if coin_input_text == "скасувати":
            logger.info(f"[User {user_id}] 'скасувати' entered during coin selection.")
            user_data["current_step"] = "INIT"
            if "selected_coins_buffer" in user_data: del user_data["selected_coins_buffer"]
            try: await message.answer("🚫 Вибір монет скасовано. Введіть /start, щоб почати знову.")
            except Exception as e: logger.error(f"Error sending 'coin selection cancelled' message: {e}")
            return

        query = coin_input_text
        logger.info(f"[User {user_id}] Searching for coin: '{query}'")
        derivative_filters = ['wrapped', 'amm', 'pool', 'bpt', 'tokenized', 'wormhole', 'peg', 'staked', 'leveraged']
        potential_matches = []
        for coin in coin_list_cache: # coin_list_cache is confirmed by ensure_coin_list_loaded
            coin_id_lower = coin.get('id', '').lower()
            coin_symbol_lower = coin.get('symbol', '').lower()
            coin_name_lower = coin.get('name', '').lower()
            if not coin_id_lower or not coin_symbol_lower or not coin.get('name'): continue
            if any(f_word in coin_id_lower for f_word in derivative_filters): continue
            if query == coin_symbol_lower or query == coin_id_lower or query in coin_name_lower:
                potential_matches.append(coin)
        matches = sorted(potential_matches, key=lambda c: (query != c.get('symbol','').lower(), query != c.get('id','').lower(), query not in c.get('name','').lower()))

        try:
            if not matches:
                logger.info(f"[User {user_id}] No matches found for '{query}'.")
                await message.answer(f"❌ Монету '{message.text}' не знайдено. Спробуйте іншу назву або символ.")
            else:
                logger.info(f"[User {user_id}] Matches found for '{query}': {[m.get('id') for m in matches[:5]]}. Creating keyboard.")
                keyboard_buttons = []
                for c in matches[:5]:
                    coin_id, coin_name, coin_symbol = c.get('id'), c.get('name', 'Unknown Coin'), c.get('symbol', 'N/A').upper()
                    action_text, callback_action = ("➖", f"removeselcoin_{coin_id}") if coin_id in user_data.get("selected_coins_buffer", []) else ("➕", f"addselcoin_{coin_id}")
                    keyboard_buttons.append([InlineKeyboardButton(text=f"{action_text} {coin_name} ({coin_symbol})", callback_data=callback_action)])
                keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
                
                buffer_display_parts = []
                for s_id in user_data.get("selected_coins_buffer", []):
                    coin_info = next((ci for ci in coin_list_cache if ci.get('id') == s_id), None)
                    if coin_info:
                        buffer_display_parts.append(f"{coin_info.get('name', s_id.capitalize())} ({coin_info.get('symbol','N/A').upper()})")
                    else: # Should ideally not happen if coin was added from cache
                        buffer_display_parts.append(s_id.capitalize())
                current_coins_text = ", ".join(buffer_display_parts) if buffer_display_parts else "не обрано"

                await message.answer(
                    f"🔎 Знайдено варіанти для '{message.text}':\n<b>Поточний вибір:</b> {current_coins_text} ({len(user_data.get('selected_coins_buffer',[]))}/3)\n"
                    "Оберіть одну зі списку, введіть іншу назву, 'готово' або 'скасувати':",
                    reply_markup=keyboard, parse_mode=ParseMode.HTML
                )
                logger.info(f"[User {user_id}] Sent coin options keyboard for '{query}'.")
        except Exception as e:
            logger.error(f"[User {user_id}] Error sending message in coin search result: {e}")
            try: await message.answer("Помилка під час відображення результатів пошуку. Спробуйте ще раз.")
            except Exception as e2: logger.error(f"Error sending fallback error message: {e2}")
    else:
        logger.info(f"[User {user_id}] Text received but not in SELECTING_COINS step. Sending 'Не розумію вас'.")
        try: await message.answer("Не розумію вас. Будь ласка, використовуйте команди або кнопки. Введіть /start, щоб почати.")
        except Exception as e: logger.error(f"Error sending 'Не розумію вас' message: {e}")


@router.callback_query(F.data.startswith("addselcoin_"))
async def handle_add_sel_coin_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_data = get_user_data(user_id)
    logger.info(f"[User {user_id}] addselcoin callback: {callback.data}. Current step: {user_data.get('current_step')}")
    if user_data.get("current_step") != "SELECTING_COINS":
        await callback.answer("Помилка: не той етап для додавання монет.", show_alert=True); return
    
    if not await ensure_coin_list_loaded(callback): return # Check again, crucial for callbacks

    coin_id_to_add = callback.data.replace("addselcoin_", "")
    buffer = user_data.setdefault("selected_coins_buffer", [])
    if coin_id_to_add in buffer: await callback.answer("ℹ️ Цю монету вже додано.", show_alert=True)
    elif len(buffer) >= 3: await callback.answer("⚠️ Можна обрати максимум 3 монети.", show_alert=True)
    else:
        buffer.append(coin_id_to_add)
        coin_info = next((c for c in coin_list_cache if c.get('id') == coin_id_to_add), None) if coin_list_cache else None
        await callback.answer(f"✅ Додано: {coin_info.get('name', coin_id_to_add.capitalize()) if coin_info else coin_id_to_add.capitalize()}", show_alert=False)
    await start_coin_selection(callback)


@router.callback_query(F.data.startswith("removeselcoin_"))
async def handle_remove_sel_coin_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_data = get_user_data(user_id)
    logger.info(f"[User {user_id}] removeselcoin callback: {callback.data}. Current step: {user_data.get('current_step')}")
    if user_data.get("current_step") != "SELECTING_COINS":
        await callback.answer("Помилка: не той етап для видалення монет.", show_alert=True); return

    if not await ensure_coin_list_loaded(callback): return # Check again

    coin_id_to_remove = callback.data.replace("removeselcoin_", "")
    buffer = user_data.setdefault("selected_coins_buffer", [])
    if coin_id_to_remove in buffer:
        buffer.remove(coin_id_to_remove)
        coin_info = next((c for c in coin_list_cache if c.get('id') == coin_id_to_remove), None) if coin_list_cache else None
        await callback.answer(f"➖ Видалено: {coin_info.get('name', coin_id_to_remove.capitalize()) if coin_info else coin_id_to_remove.capitalize()}", show_alert=False)
    else: await callback.answer("ℹ️ Цієї монети немає у списку.", show_alert=True)
    await start_coin_selection(callback)


@router.callback_query(F.data.startswith("setfreq_"))
async def handle_set_frequency_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_data = get_user_data(user_id)
    logger.info(f"[User {user_id}] setfreq callback: {callback.data}. Current step: {user_data.get('current_step')}")
    if user_data.get("current_step") != "SELECTING_FREQUENCY":
        await callback.answer("Помилка: не той етап для вибору частоти.", show_alert=True); return
    user_data["frequency"] = callback.data.replace("setfreq_", "")
    logger.info(f"User {user_id} set frequency to {user_data['frequency']}.")
    await display_main_menu(callback)


@router.callback_query(F.data == "get_prices")
async def handle_get_prices_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_data = get_user_data(user_id)
    logger.info(f"[User {user_id}] get_prices callback. Current step: {user_data.get('current_step')}")
    if user_data.get("current_step") != "SETUP_COMPLETE" or not user_data.get("coins"):
        await callback.answer("Спочатку завершіть налаштування монет.", show_alert=True); return
    
    if not await ensure_coin_list_loaded(callback): # Check if coin list is available for names
        # If not available, prices can still be fetched, but names might be just IDs
        logger.warning(f"[User {user_id}] Coin list not available for get_prices, names might be IDs.")
        # Proceed with fetching prices anyway

    coins_to_fetch = user_data["coins"]
    await callback.answer("⏳ Отримую ціни...") 
    text_parts = ["📈 <b>Поточні ціни (USD):</b>\n"]
    try:
        async with aiohttp.ClientSession() as session:
            ids_param = ",".join(coins_to_fetch)
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids_param}&vs_currencies=usd"
            async with session.get(url, timeout=10) as resp: # Added timeout
                if resp.status == 200:
                    data = await resp.json()
                    for coin_id in coins_to_fetch:
                        price_data = data.get(coin_id)
                        coin_name_display, sym_display = coin_id.capitalize(),""
                        if coin_list_cache: # Use cache for names if available
                            info = next((c for c in coin_list_cache if c.get('id')==coin_id),None)
                            if info: coin_name_display, sym_display = info.get('name',coin_id.capitalize()), f" ({info.get('symbol','').upper()})"
                        
                        if price_data and "usd" in price_data: text_parts.append(f"<b>{coin_name_display}</b>{sym_display}: ${price_data['usd']:,.2f}")
                        else: text_parts.append(f"<b>{coin_name_display}</b>{sym_display}: ❌ Помилка даних")
                elif resp.status == 429:
                    logger.warning(f"Rate limit (429) hit during get_prices for user {user_id}.")
                    text_parts.append("❌ Перевищено ліміт запитів до API. Спробуйте пізніше.")
                else:
                    logger.error(f"CoinGecko API error for {user_id} during get_prices: {resp.status} - {await resp.text()}")
                    text_parts.append(f"❌ Помилка API CoinGecko (статус {resp.status}).")
        final_text = "\n".join(text_parts)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Оновити ціни", callback_data="get_prices")],
            [InlineKeyboardButton(text="⚙️ Змінити налаштування (скинути)", callback_data="reset_settings_sequential")]])
        try:
            if callback.message.text != final_text or callback.message.reply_markup != keyboard :
                await callback.message.edit_text(final_text.strip(), parse_mode=ParseMode.HTML, reply_markup=keyboard)
            else: await callback.answer() 
        except Exception: # Fallback to sending new message
             await callback.message.answer(final_text.strip(), parse_mode=ParseMode.HTML, reply_markup=keyboard)
    except aiohttp.ClientError as e:
        logger.error(f"ClientError in get_prices for {user_id}: {e}")
        text_parts.append("❌ Мережева помилка при отриманні цін.")
    except asyncio.TimeoutError:
        logger.error(f"TimeoutError in get_prices for {user_id}.")
        text_parts.append("❌ Час очікування відповіді від API вичерпано.")
    except Exception as e:
        logger.exception(f"Error in handle_get_prices_callback for {user_id}: {e}")
        text_parts.append("❌ Невідома помилка при отриманні цін.")
    
    # If any error occurred and text_parts was modified beyond the initial header
    if len(text_parts) > 1 and "❌" in text_parts[-1]: # Check if last added part indicates an error
        final_text_on_error = "\n".join(text_parts)
        error_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ Головне меню", callback_data="back_to_main_menu_from_error")]
        ])
        try:
            # Try to edit the original message first
            await callback.message.edit_text(final_text_on_error.strip(), parse_mode=ParseMode.HTML, reply_markup=error_keyboard)
        except Exception:
            # If editing fails (e.g., message too old), send a new one
            await callback.message.answer(final_text_on_error.strip(), parse_mode=ParseMode.HTML, reply_markup=error_keyboard)


@router.callback_query(F.data == "back_to_main_menu_from_error")
async def handle_back_to_main_from_error(callback: types.CallbackQuery):
    logger.info(f"[User {callback.from_user.id}] Going back to main menu from error.")
    mock_msg = create_mock_message_from_callback(callback)
    await display_main_menu(mock_msg) # This should show the main menu correctly
    await callback.answer()

# --- Webhook Setup & Application Start ---
async def on_startup(bot_instance: Bot): # Pass bot instance explicitly
    logger.info(f"Setting webhook to: {WEBHOOK_URL}")
    await bot_instance.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
    # Initial load attempt. If it fails, COIN_LIST_LOAD_ATTEMPTED will be True,
    # and ensure_coin_list_loaded will handle further user interactions.
    asyncio.create_task(load_coin_list()) 

async def on_shutdown(bot_instance: Bot): # Pass bot instance explicitly
    logger.info("Shutting down...")
    await bot_instance.session.close()

if __name__ == "__main__":
    # It's better to create the Application object and then pass it around
    # if needed, or access bot/dp via context if using newer aiogram patterns.
    # For this structure, passing bot explicitly to on_startup/on_shutdown is fine.
    
    # Pass bot to on_startup and on_shutdown
    dp.startup.register(lambda: on_startup(bot))
    dp.shutdown.register(lambda: on_shutdown(bot))

    app = web.Application()
    # The SimpleRequestHandler should be configured with the dispatcher.
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        # any other kwargs for SimpleRequestHandler
    )
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    
    # setup_application is a utility from aiogram.webhook.aiohttp_server
    # It typically sets up routes for the dispatcher and can handle bot context.
    # If you register routes manually as above, ensure it doesn't conflict.
    # For this setup, explicit registration is clear.
    # setup_application(app, dp, bot=bot) # This might be redundant if routes are manually set.
                                        # If used, ensure it's configured correctly.
                                        # For now, let's rely on manual registration.

    web.run_app(app, host="0.0.0.0", port=PORT)
