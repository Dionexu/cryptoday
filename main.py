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
PORT = int(os.environ.get("PORT", 8080))

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

# --- Helper Functions ---
def get_user_data(user_id):
    """Helper to get user data, initializing if not present."""
    return user_settings.setdefault(user_id, {"coins": [], "frequency": None, "current_step": "INIT"})

async def ensure_coin_list_loaded(message_or_callback):
    """Checks if coin list is loaded, sends message if not."""
    if not coin_list_cache or not isinstance(coin_list_cache, list):
        text = "⚠️ Список монет ще не завантажено або має невірний формат. Будь ласка, зачекайте кілька секунд і спробуйте знову, або натисніть /start."
        if isinstance(message_or_callback, types.Message):
            await message_or_callback.answer(text)
        elif isinstance(message_or_callback, types.CallbackQuery):
            await message_or_callback.message.answer(text)
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
        # text="" # Not always needed, depends on the handler
    )

# --- CoinGecko API Interaction ---
async def load_coin_list():
    global coin_list_cache
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://api.coingecko.com/api/v3/coins/list"
            async with session.get(url) as resp:
                if resp.status == 200:
                    coin_list_cache = await resp.json()
                    if isinstance(coin_list_cache, list):
                        logger.info(f"✅ Coin list loaded successfully. Total: {len(coin_list_cache)} coins.")
                    else:
                        logger.error(f"⚠️ Coin list loaded but is not a list. Type: {type(coin_list_cache)}. Data: {str(coin_list_cache)[:200]}")
                        coin_list_cache = []
                else:
                    logger.error(f"⚠️ Failed to load coin list. Status: {resp.status}, Response: {await resp.text()}")
                    coin_list_cache = []
    except Exception as e:
        logger.error(f"⚠️ Error loading coin list: {e}")
        coin_list_cache = []

# --- Sequential Setup Steps ---

async def start_coin_selection(message_or_callback: types.Union[types.Message, types.CallbackQuery]):
    """Initiates the coin selection step."""
    user_id = message_or_callback.from_user.id
    user_data = get_user_data(user_id)
    user_data["current_step"] = "SELECTING_COINS"
    user_data["selected_coins_buffer"] = list(user_data.get("coins", [])) # Use existing coins if any

    if not await ensure_coin_list_loaded(message_or_callback):
        return

    current_coins_text_parts = []
    if coin_list_cache: # Already checked for list type in ensure_coin_list_loaded
        for coin_id_in_buffer in user_data["selected_coins_buffer"]:
            found_coin = next((c for c in coin_list_cache if c.get('id') == coin_id_in_buffer), None)
            current_coins_text_parts.append(
                f"{found_coin.get('name', coin_id_in_buffer.capitalize())} ({found_coin.get('symbol','N/A').upper()})" if found_coin else coin_id_in_buffer.capitalize()
            )
    else:
         current_coins_text_parts = [c.capitalize() for c in user_data["selected_coins_buffer"]]


    current_coins_text = ", ".join(current_coins_text_parts) if current_coins_text_parts else "не обрано"
    
    text = (
        "👋 Давайте налаштуємо вашого крипто-помічника!\n\n"
        "<b>Крок 1: Оберіть монети</b> (максимум 3)\n"
        f"Поточний вибір: {current_coins_text}\n\n"
        "Введіть назву або символ монети (наприклад, bitcoin, solana, doge).\n"
        "Коли завершите, введіть 'готово'."
    )
    
    if isinstance(message_or_callback, types.Message):
        await message_or_callback.answer(text, parse_mode=ParseMode.HTML)
    elif isinstance(message_or_callback, types.CallbackQuery):
        try:
            await message_or_callback.message.edit_text(text, parse_mode=ParseMode.HTML)
        except Exception as e: # Handle potential "message not modified" or other edit errors
            logger.debug(f"Error editing message in start_coin_selection: {e}, sending new one.")
            await message_or_callback.message.answer(text, parse_mode=ParseMode.HTML)
        await message_or_callback.answer()


async def start_frequency_selection(message_or_callback: types.Union[types.Message, types.CallbackQuery]):
    """Initiates the frequency selection step."""
    user_id = message_or_callback.from_user.id
    user_data = get_user_data(user_id)
    user_data["current_step"] = "SELECTING_FREQUENCY"

    current_freq_code = user_data.get("frequency")
    frequency_options_display = {
        "2h": "Один раз на 2 години",
        "12h": "Один раз на 12 годин",
        "24h": "Один раз на добу"
    }

    def freq_text(text, value):
        return f"✅ {text}" if current_freq_code == value else text

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=freq_text(frequency_options_display["2h"], "2h"), callback_data="setfreq_2h")],
        [InlineKeyboardButton(text=freq_text(frequency_options_display["12h"], "12h"), callback_data="setfreq_12h")],
        [InlineKeyboardButton(text=freq_text(frequency_options_display["24h"], "24h"), callback_data="setfreq_24h")]
    ])
    
    text = (
        "<b>Крок 2: Оберіть частоту оновлення цін</b>\n\n"
        "Як часто ви бажаєте отримувати автоматичні оновлення? (Ця функція буде додана пізніше, зараз це налаштування зберігається для майбутнього використання)."
    )

    if isinstance(message_or_callback, types.Message):
        await message_or_callback.answer(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    elif isinstance(message_or_callback, types.CallbackQuery):
        try:
            await message_or_callback.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        except Exception:
            await message_or_callback.message.answer(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        await message_or_callback.answer()


async def display_main_menu(message_or_callback: types.Union[types.Message, types.CallbackQuery]):
    """Displays the main operational menu after setup is complete."""
    user_id = message_or_callback.from_user.id
    user_data = get_user_data(user_id)
    user_data["current_step"] = "SETUP_COMPLETE"

    selected_coins = user_data.get("coins", [])
    frequency_code = user_data.get("frequency")
    frequency_options_display = {
        "2h": "кожні 2 години", "12h": "кожні 12 годин", "24h": "щодня"
    }
    freq_display = frequency_options_display.get(frequency_code, "не встановлено")

    coins_display_parts = []
    if coin_list_cache:
        for coin_id in selected_coins:
            coin_info = next((c for c in coin_list_cache if c.get('id') == coin_id), None)
            coins_display_parts.append(coin_info.get('name', coin_id.capitalize()) if coin_info else coin_id.capitalize())
    else: # Fallback
        coins_display_parts = [c.capitalize() for c in selected_coins]
    
    coins_text = ", ".join(coins_display_parts) if coins_display_parts else "не обрано"

    text = (
        "✅ Налаштування завершено!\n\n"
        f"<b>Обрані монети:</b> {coins_text}\n"
        f"<b>Частота (для майбутніх авто-оновлень):</b> {freq_display}\n\n"
        "Тепер ви можете:"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 Дивитися ціни зараз", callback_data="get_prices")],
        [InlineKeyboardButton(text="🔄 Скинути налаштування", callback_data="reset_settings_sequential")]
    ])

    if isinstance(message_or_callback, types.Message):
        await message_or_callback.answer(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    elif isinstance(message_or_callback, types.CallbackQuery):
        try:
            await message_or_callback.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        except Exception:
             await message_or_callback.message.answer(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        await message_or_callback.answer()

# --- Command Handlers & Main Flow ---
@router.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    
    # If setup is complete, show main menu, otherwise start/continue setup
    if user_data.get("current_step") == "SETUP_COMPLETE" and user_data.get("coins") and user_data.get("frequency"):
        await display_main_menu(message)
    else:
        # Reset if coming from an unknown state or explicit start
        user_data["coins"] = []
        user_data["frequency"] = None
        await start_coin_selection(message)

@router.callback_query(F.data == "reset_settings_sequential")
async def handle_reset_settings_sequential(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_data = get_user_data(user_id)
    user_data["coins"] = []
    user_data["frequency"] = None
    user_data["current_step"] = "INIT" # Reset step
    logger.info(f"User {user_id} reset settings.")
    await callback.answer("🔄 Налаштування скинуто.")
    await start_coin_selection(callback) # Restart setup

# --- Coin Selection Handlers ---
@router.message(F.text)
async def handle_message_input(message: types.Message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)

    if user_data.get("current_step") == "SELECTING_COINS":
        if not await ensure_coin_list_loaded(message):
            return

        coin_input_text = message.text.lower().strip()

        if coin_input_text == "готово":
            user_data["coins"] = list(user_data.get("selected_coins_buffer", []))
            if not user_data["coins"]:
                await message.answer("⚠️ Будь ласка, оберіть хоча б одну монету перед тим, як продовжити, або введіть 'скасувати', щоб почати знову з /start.")
                return

            logger.info(f"User {user_id} finished coin selection: {user_data['coins']}")
            del user_data["selected_coins_buffer"] # Clean up buffer
            await start_frequency_selection(message)
            return
        
        if coin_input_text == "скасувати": # Allow cancelling coin selection
            user_data["current_step"] = "INIT"
            if "selected_coins_buffer" in user_data: del user_data["selected_coins_buffer"]
            await message.answer("🚫 Вибір монет скасовано. Введіть /start, щоб почати знову.")
            return

        query = coin_input_text
        derivative_filters = ['wrapped', 'amm', 'pool', 'bpt', 'tokenized', 'wormhole', 'peg', 'staked', 'leveraged']
        
        potential_matches = []
        for coin in coin_list_cache: # coin_list_cache is confirmed to be a list here
            coin_id_lower = coin.get('id', '').lower()
            coin_symbol_lower = coin.get('symbol', '').lower()
            coin_name_lower = coin.get('name', '').lower()

            if not coin_id_lower or not coin_symbol_lower or not coin.get('name'): continue
            if any(f_word in coin_id_lower for f_word in derivative_filters): continue

            if query == coin_symbol_lower or query == coin_id_lower or query in coin_name_lower:
                potential_matches.append(coin)

        matches = sorted(potential_matches, key=lambda c: (
            query != c.get('symbol','').lower(), 
            query != c.get('id','').lower(), 
            query not in c.get('name','').lower()
        ))

        if not matches:
            await message.answer(f"❌ Монету '{message.text}' не знайдено. Спробуйте іншу назву або символ.")
            return
        
        keyboard_buttons = []
        for c in matches[:5]:
            coin_id = c.get('id')
            coin_name = c.get('name', 'Unknown Coin')
            coin_symbol = c.get('symbol', 'N/A').upper()
            action_text = "➕"
            callback_action = f"addselcoin_{coin_id}"
            if coin_id in user_data.get("selected_coins_buffer", []):
                action_text = "➖"
                callback_action = f"removeselcoin_{coin_id}"
            keyboard_buttons.append([InlineKeyboardButton(text=f"{action_text} {coin_name} ({coin_symbol})", callback_data=callback_action)])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        buffer_coins_display = []
        for coin_id_in_buffer in user_data.get("selected_coins_buffer", []):
            found_coin = next((c_info for c_info in coin_list_cache if c_info.get('id') == coin_id_in_buffer), None)
            buffer_coins_display.append(f"{found_coin.get('name', coin_id_in_buffer.capitalize())} ({found_coin.get('symbol','N/A').upper()})" if found_coin else coin_id_in_buffer.capitalize())
        current_coins_text = ", ".join(buffer_coins_display) if buffer_coins_display else "не обрано"

        await message.answer(
            f"🔎 Знайдено варіанти для '{message.text}':\n"
            f"<b>Поточний вибір:</b> {current_coins_text} ({len(user_data.get('selected_coins_buffer',[]))}/3)\n"
            "Оберіть одну зі списку, введіть іншу назву, 'готово' або 'скасувати':",
            reply_markup=keyboard, parse_mode=ParseMode.HTML
        )
    else:
        # Default message if bot is not in a specific input step but receives text
        await message.answer("Не розумію вас. Будь ласка, використовуйте команди або кнопки. Введіть /start, щоб почати.")


@router.callback_query(F.data.startswith("addselcoin_"))
async def handle_add_sel_coin_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_data = get_user_data(user_id)

    if user_data.get("current_step") != "SELECTING_COINS":
        await callback.answer("Помилка: не той етап для додавання монет.", show_alert=True)
        return

    coin_id_to_add = callback.data.replace("addselcoin_", "")
    buffer = user_data.setdefault("selected_coins_buffer", [])

    if coin_id_to_add in buffer:
        await callback.answer("ℹ️ Цю монету вже додано.", show_alert=True)
    elif len(buffer) >= 3:
        await callback.answer("⚠️ Можна обрати максимум 3 монети.", show_alert=True)
    else:
        buffer.append(coin_id_to_add)
        coin_info = next((c for c in coin_list_cache if c.get('id') == coin_id_to_add), None) if coin_list_cache else None
        await callback.answer(f"✅ Додано: {coin_info.get('name', coin_id_to_add.capitalize()) if coin_info else coin_id_to_add.capitalize()}", show_alert=False)
    
    # Re-display coin selection prompt with updated buffer
    # This requires the original message object or callback to edit.
    # We can call start_coin_selection with the callback.
    await start_coin_selection(callback) # This will edit the message


@router.callback_query(F.data.startswith("removeselcoin_"))
async def handle_remove_sel_coin_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_data = get_user_data(user_id)

    if user_data.get("current_step") != "SELECTING_COINS":
        await callback.answer("Помилка: не той етап для видалення монет.", show_alert=True)
        return

    coin_id_to_remove = callback.data.replace("removeselcoin_", "")
    buffer = user_data.setdefault("selected_coins_buffer", [])

    if coin_id_to_remove in buffer:
        buffer.remove(coin_id_to_remove)
        coin_info = next((c for c in coin_list_cache if c.get('id') == coin_id_to_remove), None) if coin_list_cache else None
        await callback.answer(f"➖ Видалено: {coin_info.get('name', coin_id_to_remove.capitalize()) if coin_info else coin_id_to_remove.capitalize()}", show_alert=False)
    else:
        await callback.answer("ℹ️ Цієї монети немає у списку.", show_alert=True)
    
    await start_coin_selection(callback) # Re-display prompt


# --- Frequency Selection Handler ---
@router.callback_query(F.data.startswith("setfreq_"))
async def handle_set_frequency_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_data = get_user_data(user_id)

    if user_data.get("current_step") != "SELECTING_FREQUENCY":
        await callback.answer("Помилка: не той етап для вибору частоти.", show_alert=True)
        return

    freq_code = callback.data.replace("setfreq_", "")
    user_data["frequency"] = freq_code
    logger.info(f"User {user_id} set frequency to {freq_code}.")
    
    await display_main_menu(callback)


# --- Price Fetching Handler ---
@router.callback_query(F.data == "get_prices")
async def handle_get_prices_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_data = get_user_data(user_id)

    if user_data.get("current_step") != "SETUP_COMPLETE" or not user_data.get("coins"):
        await callback.answer("Спочатку завершіть налаштування монет.", show_alert=True)
        # Optionally, redirect to setup
        # mock_msg = create_mock_message_from_callback(callback)
        # await cmd_start(mock_msg) # This will restart setup if incomplete
        return

    coins_to_fetch = user_data["coins"]
    await callback.answer("⏳ Отримую ціни...") 

    text_parts = ["📈 <b>Поточні ціни (USD):</b>\n"]
    try:
        async with aiohttp.ClientSession() as session:
            ids_param = ",".join(coins_to_fetch)
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids_param}&vs_currencies=usd"
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for coin_id in coins_to_fetch:
                        price_data = data.get(coin_id)
                        coin_name_display, coin_symbol_display = coin_id.capitalize(), ""
                        if coin_list_cache:
                            coin_info = next((c for c in coin_list_cache if c.get('id') == coin_id), None)
                            if coin_info:
                                coin_name_display = coin_info.get('name', coin_id.capitalize())
                                coin_symbol_display = f" ({coin_info.get('symbol', '').upper()})"
                        
                        if price_data and "usd" in price_data:
                            text_parts.append(f"<b>{coin_name_display}</b>{coin_symbol_display}: ${price_data['usd']:,.2f}")
                        else:
                            text_parts.append(f"<b>{coin_name_display}</b>{coin_symbol_display}: ❌ Помилка даних")
                else:
                    logger.error(f"CoinGecko API error for {user_id}: {resp.status} - {await resp.text()}")
                    text_parts.append(f"❌ Помилка API CoinGecko (статус {resp.status}).")
        
        final_text = "\n".join(text_parts)
        # Re-use main menu keyboard
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Оновити ціни", callback_data="get_prices")],
            [InlineKeyboardButton(text="⚙️ Змінити налаштування (скинути)", callback_data="reset_settings_sequential")]
        ])
        
        # Try to edit, if fails (e.g. message too old or same), send new.
        try:
            if callback.message.text != final_text or callback.message.reply_markup != keyboard :
                await callback.message.edit_text(final_text.strip(), parse_mode=ParseMode.HTML, reply_markup=keyboard)
            # else: await callback.answer("Ціни не змінилися.") # Optional feedback
        except Exception:
            await callback.message.answer(final_text.strip(), parse_mode=ParseMode.HTML, reply_markup=keyboard)

    except Exception as e:
        logger.exception(f"Error in handle_get_prices_callback for {user_id}: {e}")
        await callback.message.answer("❌ Невідома помилка при отриманні цін.", 
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                         [InlineKeyboardButton(text="↩️ Головне меню", callback_data="back_to_main_menu_from_error")]
                                         ])) # Simple back button on error

@router.callback_query(F.data == "back_to_main_menu_from_error")
async def handle_back_to_main_from_error(callback: types.CallbackQuery):
    """Handles going back to main menu if an error occurred during price fetching."""
    mock_msg = create_mock_message_from_callback(callback)
    await display_main_menu(mock_msg) # This should show the main menu correctly
    await callback.answer()


# --- Webhook Setup & Application Start ---
async def on_startup(app: web.Application):
    logger.info(f"Setting webhook to: {WEBHOOK_URL}")
    await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
    asyncio.create_task(load_coin_list())

async def on_shutdown(app: web.Application):
    logger.info("Shutting down...")
    await bot.session.close()

if __name__ == "__main__":
    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot) # Ensure dispatcher is correctly configured with the app
    web.run_app(app, host="0.0.0.0", port=PORT)
