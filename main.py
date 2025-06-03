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

# Ensure WEBHOOK_HOST has a scheme
if not WEBHOOK_HOST.startswith(("http://", "https://")):
    WEBHOOK_HOST = "https://" + WEBHOOK_HOST

WEBHOOK_PATH = f"/webhook/{TOKEN.split(':')[0]}" # Using the bot ID part of the token for the path
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
PORT = int(os.environ.get("PORT", 8080)) # Use a default port if not set

logger.info(f"🚀 Starting on port {PORT}")
logger.info(f"Webhook URL configured: {WEBHOOK_URL}")

# --- Bot Initialization ---
bot = Bot(TOKEN, parse_mode=ParseMode.HTML)
storage = MemoryStorage() # In-memory storage for FSM and user data
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# --- Global Variables & Caches ---
user_settings = {} # Stores user-specific preferences (coins, frequency)
coin_list_cache = None # Cache for the list of all available coins from CoinGecko

# --- CoinGecko API Interaction ---
async def load_coin_list():
    """
    Asynchronously loads the list of all coins from CoinGecko API
    and populates the coin_list_cache.
    """
    global coin_list_cache
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://api.coingecko.com/api/v3/coins/list"
            async with session.get(url) as resp:
                if resp.status == 200:
                    coin_list_cache = await resp.json()
                    if isinstance(coin_list_cache, list): # Ensure it's a list
                        logger.info(f"✅ Coin list loaded successfully. Total: {len(coin_list_cache)} coins.")
                    else:
                        logger.error(f"⚠️ Coin list loaded but is not a list. Type: {type(coin_list_cache)}. Data: {str(coin_list_cache)[:200]}")
                        coin_list_cache = []
                else:
                    logger.error(f"⚠️ Failed to load coin list. Status: {resp.status}, Response: {await resp.text()}")
                    coin_list_cache = [] # Ensure it's an empty list on failure to prevent errors
    except aiohttp.ClientError as e:
        logger.error(f"⚠️ ClientError loading coin list: {e}")
        coin_list_cache = []
    except Exception as e:
        logger.error(f"⚠️ Unexpected error loading coin list: {e}")
        coin_list_cache = []

# --- Command Handlers & Main Menu ---
@router.message(Command("start"))
async def cmd_start(message: types.Message):
    """
    Handles the /start command. Displays the main menu.
    """
    user_id = message.from_user.id
    user_settings.setdefault(user_id, {"coins": ["bitcoin", "ethereum"], "frequency": "1h", "mode": None}) # Initialize default settings

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🕒 Обрати частоту", callback_data="select_frequency")],
        [InlineKeyboardButton(text="📈 Дивитися ціни", callback_data="get_prices")],
        [InlineKeyboardButton(text="⚙️ Обрати монети", callback_data="select_coins")],
        [InlineKeyboardButton(text="🔄 Скинути налаштування", callback_data="reset_settings")]
    ])
    await message.answer(
        "Привіт! Я твій крипто-помічник.\n"
        "Ти можеш обрати до 3 монет для відстеження та частоту оновлення цін.\n"
        "За замовчуванням відстежуються Bitcoin та Ethereum щогодини.\n\n"
        "Натисни кнопку нижче, щоб налаштувати або отримати ціни:",
        reply_markup=keyboard
    )

# --- Callback Query Handlers for Main Menu ---
@router.callback_query(F.data == "reset_settings")
async def handle_reset_settings(callback: types.CallbackQuery):
    """
    Resets the user's settings to default.
    """
    user_id = callback.from_user.id
    user_settings[user_id] = {"coins": ["bitcoin", "ethereum"], "frequency": "1h", "mode": None} # Reset to defaults
    await callback.message.edit_text("🔄 Налаштування скинуто до значень за замовчуванням.")
    # It's better to call the message handler for /start to resend the welcome message with keyboard
    # Re-create a message object to pass to cmd_start
    mock_message = types.Message(
        message_id=callback.message.message_id,
        date=callback.message.date,
        chat=callback.message.chat,
        from_user=callback.from_user, # Or bot if appropriate for context
        # text="/start" # Not strictly needed if cmd_start doesn't parse text
    )
    await cmd_start(mock_message)
    await callback.answer()

@router.callback_query(F.data == "select_coins")
async def ask_coin_selection_start(callback: types.CallbackQuery):
    """
    Initiates the coin selection process.
    """
    user_id = callback.from_user.id
    user_data = user_settings.setdefault(user_id, {})
    # Initialize buffer with currently saved coins, or empty if none
    user_data["selected_coins_buffer"] = list(user_data.get("coins", []))
    user_data["mode"] = "selecting_coins"

    current_coins_text_parts = []
    if coin_list_cache and isinstance(coin_list_cache, list):
        for coin_id_in_buffer in user_data["selected_coins_buffer"]:
            found_coin = next((c for c in coin_list_cache if c.get('id') == coin_id_in_buffer), None)
            if found_coin:
                current_coins_text_parts.append(f"{found_coin.get('name', coin_id_in_buffer.capitalize())} ({found_coin.get('symbol','N/A').upper()})")
            else:
                current_coins_text_parts.append(coin_id_in_buffer.capitalize())
    else: # Fallback if coin_list_cache is not ready
        current_coins_text_parts = [c.capitalize() for c in user_data["selected_coins_buffer"]]

    current_coins_text = ", ".join(current_coins_text_parts)
    if not current_coins_text:
        current_coins_text = "не обрано"

    await callback.message.edit_text(
        f"⚙️ <b>Обрані монети:</b> {current_coins_text}\n\n"
        "Введіть назву або символ монети (наприклад, bitcoin, solana, doge).\n"
        "Максимум 3 монети. Введіть 'готово', щоб зберегти, або 'скасувати', щоб повернутися.",
        parse_mode=ParseMode.HTML
    )
    await callback.answer()

# --- Message Handler for Coin Input ---
@router.message(F.text)
async def handle_coin_input(message: types.Message):
    """
    Handles user input when they are in 'selecting_coins' mode.
    """
    user_id = message.from_user.id
    user_data = user_settings.get(user_id)

    if not user_data or user_data.get("mode") != "selecting_coins":
        await message.answer("Щоб почати, введіть /start")
        return

    coin_input_text = message.text.lower().strip()

    if coin_input_text == "готово":
        user_data["coins"] = list(user_data.get("selected_coins_buffer", []))
        user_data["mode"] = None
        if "selected_coins_buffer" in user_data: # Ensure buffer exists before deleting
            del user_data["selected_coins_buffer"]
        
        final_selected_coins_names = []
        if coin_list_cache and isinstance(coin_list_cache, list):
             for coin_id_final in user_data.get("coins", []):
                found_coin = next((c for c in coin_list_cache if c.get('id') == coin_id_final), None)
                if found_coin:
                    final_selected_coins_names.append(f"{found_coin.get('name', coin_id_final.capitalize())} ({found_coin.get('symbol','N/A').upper()})")
                else:
                    final_selected_coins_names.append(coin_id_final.capitalize())
        else:
            final_selected_coins_names = [c.capitalize() for c in user_data.get("coins", [])]

        await message.answer(f"✅ Монети збережено: {', '.join(final_selected_coins_names) if final_selected_coins_names else 'не обрано'}.")
        # Re-create a message object to pass to cmd_start
        mock_message = types.Message(message_id=message.message_id, date=message.date, chat=message.chat, from_user=message.from_user)
        await cmd_start(mock_message)
        return
    
    if coin_input_text == "скасувати":
        user_data["mode"] = None
        if "selected_coins_buffer" in user_data:
            del user_data["selected_coins_buffer"]
        await message.answer("🚫 Вибір монет скасовано.")
        mock_message = types.Message(message_id=message.message_id, date=message.date, chat=message.chat, from_user=message.from_user)
        await cmd_start(mock_message)
        return

    if not coin_list_cache or not isinstance(coin_list_cache, list): # Also check type
        await message.answer("⚠️ Список монет ще не завантажено або має невірний формат. Будь ласка, зачекайте кілька секунд і спробуйте знову або натисніть /start.")
        return

    query = coin_input_text
    derivative_filters = ['wrapped', 'amm', 'pool', 'bpt', 'tokenized', 'wormhole', 'peg', 'staked', 'leveraged']
    
    potential_matches = []
    for coin in coin_list_cache:
        coin_id_lower = coin.get('id', '').lower()
        coin_symbol_lower = coin.get('symbol', '').lower()
        coin_name_lower = coin.get('name', '').lower()

        if not coin_id_lower or not coin_symbol_lower or not coin.get('name'): # Check name presence too
            continue

        is_derivative = any(f_word in coin_id_lower for f_word in derivative_filters)
        if is_derivative:
            continue

        if query == coin_symbol_lower or query == coin_id_lower or query in coin_name_lower:
            potential_matches.append(coin)

    def sort_key_for_coin(c, q):
        s = c.get('symbol', '').lower()
        i = c.get('id', '').lower()
        n = c.get('name', '').lower()
        return (q != s, q != i, q not in n)

    matches = sorted(potential_matches, key=lambda c: sort_key_for_coin(c, query))
    # logger.info(f"User {user_id} searched for '{query}'. Found {len(matches)} matches. Top 5: {[m.get('id') for m in matches[:5]]}")


    if not matches:
        await message.answer(f"❌ Монету '{message.text}' не знайдено. Спробуйте іншу назву або символ.")
        return
    
    # Removed auto-add for single match. Always show selection.
    
    keyboard_buttons = []
    for c in matches[:5]: # Show top 5 matches
        coin_id = c.get('id')
        coin_name = c.get('name', 'Unknown Coin')
        coin_symbol = c.get('symbol', 'N/A').upper()

        action_text = "➕"
        callback_action = f"addcoin_{coin_id}"
        if coin_id in user_data.get("selected_coins_buffer", []):
            action_text = "➖"
            callback_action = f"removecoin_{coin_id}"
        
        keyboard_buttons.append(
            [InlineKeyboardButton(text=f"{action_text} {coin_name} ({coin_symbol})", callback_data=callback_action)]
        )
    
    if not keyboard_buttons: # Should ideally not happen if matches were found
        await message.answer(f"❌ Монету '{message.text}' не знайдено або сталася помилка. Спробуйте ще раз.")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    buffer_coins_display = []
    for coin_id_in_buffer in user_data.get("selected_coins_buffer", []):
        found_coin = next((c_info for c_info in coin_list_cache if c_info.get('id') == coin_id_in_buffer), None)
        if found_coin:
            buffer_coins_display.append(f"{found_coin.get('name', coin_id_in_buffer.capitalize())} ({found_coin.get('symbol','N/A').upper()})")
        else:
            buffer_coins_display.append(coin_id_in_buffer.capitalize())
            
    current_coins_text = ", ".join(buffer_coins_display)
    if not current_coins_text: current_coins_text = "не обрано"

    await message.answer(
        f"🔎 Знайдено варіанти для '{message.text}':\n"
        f"<b>Поточний вибір:</b> {current_coins_text} ({len(user_data.get('selected_coins_buffer',[]))}/3)\n"
        "Оберіть одну зі списку, введіть іншу назву, 'готово' або 'скасувати':",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )

# --- Callback Query Handlers for Coin Selection (Add/Remove) ---
@router.callback_query(F.data.startswith("addcoin_"))
async def handle_add_coin_callback(callback: types.CallbackQuery):
    """
    Adds a coin to the user's buffered selection list.
    """
    coin_id_to_add = callback.data.replace("addcoin_", "")
    user_id = callback.from_user.id
    user_data = user_settings.get(user_id)

    if not user_data or "selected_coins_buffer" not in user_data or user_data.get("mode") != "selecting_coins":
        await callback.answer("Помилка: сесія вибору монет не активна або завершена. Почніть з /start та оберіть 'Обрати монети'.", show_alert=True)
        return

    if coin_id_to_add in user_data["selected_coins_buffer"]:
        await callback.answer("ℹ️ Цю монету вже додано до вашого списку.", show_alert=True)
    elif len(user_data["selected_coins_buffer"]) >= 3:
        await callback.answer("⚠️ Можна обрати максимум 3 монети.", show_alert=True)
    else:
        user_data["selected_coins_buffer"].append(coin_id_to_add)
        coin_info = next((c for c in coin_list_cache if c.get('id') == coin_id_to_add), None) if coin_list_cache else None
        added_coin_name = coin_info.get('name', coin_id_to_add.capitalize()) if coin_info else coin_id_to_add.capitalize()
        await callback.answer(f"✅ Додано: {added_coin_name}", show_alert=False)
    
    # Update the message with current selection and prompt for next action
    # This will effectively re-render the state as if the user typed something new
    # We need to call a function that shows the current state and asks for input.
    # Let's reuse the text part of ask_coin_selection_start or handle_coin_input's reply.
    
    buffer_coins_display = []
    if coin_list_cache and isinstance(coin_list_cache, list):
        for c_id in user_data.get("selected_coins_buffer", []):
            fc = next((c_info for c_info in coin_list_cache if c_info.get('id') == c_id), None)
            if fc: buffer_coins_display.append(f"{fc.get('name', c_id.capitalize())} ({fc.get('symbol','N/A').upper()})")
            else: buffer_coins_display.append(c_id.capitalize())
    else:
        buffer_coins_display = [c.capitalize() for c in user_data.get("selected_coins_buffer", [])]
        
    current_coins_text = ", ".join(buffer_coins_display)
    if not current_coins_text: current_coins_text = "не обрано"

    # We should keep the previous keyboard if possible, or regenerate it based on last search if we stored it.
    # For simplicity, just update the text. The user will type a new coin or 'готово'.
    # To make it more interactive, we could try to re-present the last search results keyboard.
    # However, the callback.message.reply_markup might be from a different context if user clicks fast.
    # For now, just update the text prompt.
    await callback.message.edit_text(
        f"⚙️ <b>Обрані монети:</b> {current_coins_text} ({len(user_data.get('selected_coins_buffer',[]))}/3)\n\n"
        "Введіть назву або символ монети (наприклад, bitcoin, solana, doge).\n"
        "Введіть 'готово', щоб зберегти, або 'скасувати', щоб повернутися.",
        # reply_markup=callback.message.reply_markup, # This might show the old buttons, which is fine
        parse_mode=ParseMode.HTML
    )


@router.callback_query(F.data.startswith("removecoin_"))
async def handle_remove_coin_callback(callback: types.CallbackQuery):
    """
    Removes a coin from the user's buffered selection list.
    """
    coin_id_to_remove = callback.data.replace("removecoin_", "")
    user_id = callback.from_user.id
    user_data = user_settings.get(user_id)

    if not user_data or "selected_coins_buffer" not in user_data or user_data.get("mode") != "selecting_coins":
        await callback.answer("Помилка: сесія вибору монет не активна або завершена. Почніть з /start та оберіть 'Обрати монети'.", show_alert=True)
        return

    if coin_id_to_remove in user_data["selected_coins_buffer"]:
        user_data["selected_coins_buffer"].remove(coin_id_to_remove)
        coin_info = next((c for c in coin_list_cache if c.get('id') == coin_id_to_remove), None) if coin_list_cache else None
        removed_coin_name = coin_info.get('name', coin_id_to_remove.capitalize()) if coin_info else coin_id_to_remove.capitalize()
        await callback.answer(f"➖ Видалено: {removed_coin_name}", show_alert=False)
    else:
        await callback.answer("ℹ️ Цієї монети немає у вашому списку.", show_alert=True)

    buffer_coins_display = []
    if coin_list_cache and isinstance(coin_list_cache, list):
        for c_id in user_data.get("selected_coins_buffer", []):
            fc = next((c_info for c_info in coin_list_cache if c_info.get('id') == c_id), None)
            if fc: buffer_coins_display.append(f"{fc.get('name', c_id.capitalize())} ({fc.get('symbol','N/A').upper()})")
            else: buffer_coins_display.append(c_id.capitalize())
    else:
        buffer_coins_display = [c.capitalize() for c in user_data.get("selected_coins_buffer", [])]
        
    current_coins_text = ", ".join(buffer_coins_display)
    if not current_coins_text: current_coins_text = "не обрано"
    
    await callback.message.edit_text(
        f"⚙️ <b>Обрані монети:</b> {current_coins_text} ({len(user_data.get('selected_coins_buffer',[]))}/3)\n\n"
        "Введіть назву або символ монети (наприклад, bitcoin, solana, doge).\n"
        "Введіть 'готово', щоб зберегти, або 'скасувати', щоб повернутися.",
        parse_mode=ParseMode.HTML
    )


# --- Frequency Selection ---
@router.callback_query(F.data == "select_frequency")
async def ask_frequency(callback: types.CallbackQuery):
    """
    Displays options for selecting notification frequency.
    """
    user_id = callback.from_user.id
    current_freq = user_settings.get(user_id, {}).get("frequency", "1h") 

    def freq_text(text, value):
        return f"✅ {text}" if current_freq == value else text

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=freq_text("Щогодини", "1h"), callback_data="freq_1h")],
        [InlineKeyboardButton(text=freq_text("Кожні 2 години", "2h"), callback_data="freq_2h")],
        [InlineKeyboardButton(text=freq_text("2 рази на день (кожні 12 год)", "12h"), callback_data="freq_12h")],
        [InlineKeyboardButton(text=freq_text("1 раз на день (кожні 24 год)", "24h"), callback_data="freq_24h")],
        [InlineKeyboardButton(text="↩️ Назад до меню", callback_data="back_to_main_menu")]
    ])
    await callback.message.edit_text("🕒 Оберіть як часто надсилати ціни:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("freq_"))
async def handle_frequency_selection(callback: types.CallbackQuery):
    """
    Handles the user's frequency selection.
    """
    user_id = callback.from_user.id
    freq_code = callback.data.replace("freq_", "")
    
    frequency_map = {
        "1h": "Щогодини", "2h": "Кожні 2 години",
        "12h": "2 рази на день", "24h": "1 раз на день"
    }
    
    user_data = user_settings.setdefault(user_id, {})
    user_data["frequency"] = freq_code
    
    await callback.message.edit_text(f"✅ Частоту оновлення цін встановлено: <b>{frequency_map.get(freq_code, freq_code)}</b>.")
    mock_message = types.Message(message_id=callback.message.message_id, date=callback.message.date, chat=callback.message.chat, from_user=callback.from_user)
    await cmd_start(mock_message)
    await callback.answer()

@router.callback_query(F.data == "back_to_main_menu")
async def back_to_main_menu_handler(callback: types.CallbackQuery):
    mock_message = types.Message(message_id=callback.message.message_id, date=callback.message.date, chat=callback.message.chat, from_user=callback.from_user)
    await cmd_start(mock_message)
    await callback.answer()


# --- Price Fetching ---
@router.callback_query(F.data == "get_prices")
async def handle_get_prices(callback: types.CallbackQuery):
    """
    Fetches and displays current prices for the user's selected coins.
    """
    user_id = callback.from_user.id
    coins_to_fetch = user_settings.get(user_id, {}).get("coins", ["bitcoin", "ethereum"])

    if not coins_to_fetch:
        keyboard_no_coins = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⚙️ Обрати монети", callback_data="select_coins")],
                [InlineKeyboardButton(text="↩️ Назад до меню", callback_data="back_to_main_menu")]
            ])
        await callback.message.edit_text(
            "⚠️ Ви ще не обрали жодної монети. Будь ласка, оберіть монети через меню '⚙️ Обрати монети'.",
            reply_markup=keyboard_no_coins
        )
        await callback.answer()
        return

    await callback.answer("⏳ Отримую ціни...") 

    text_parts = ["📈 <b>Поточні ціни (USD):</b>\n"]
    try:
        async with aiohttp.ClientSession() as session:
            ids_param = ",".join(coins_to_fetch)
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids_param}&vs_currencies=usd"
            logger.info(f"Fetching prices for user {user_id}: {ids_param} from {url}")
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.debug(f"CoinGecko API response for user {user_id}: {data}")
                    for coin_id in coins_to_fetch:
                        price_data = data.get(coin_id)
                        coin_name_display = coin_id.capitalize()
                        coin_symbol_display = ""
                        
                        if coin_list_cache and isinstance(coin_list_cache, list):
                            coin_info = next((c for c in coin_list_cache if c.get('id') == coin_id), None)
                            if coin_info:
                                coin_name_display = coin_info.get('name', coin_id.capitalize())
                                coin_symbol_display = f" ({coin_info.get('symbol', '').upper()})"

                        if price_data and "usd" in price_data:
                            price = price_data["usd"]
                            text_parts.append(f"<b>{coin_name_display}</b>{coin_symbol_display}: ${price:,.2f}")
                        else:
                            text_parts.append(f"<b>{coin_name_display}</b>{coin_symbol_display}: ❌ Помилка отримання даних")
                else:
                    error_message = await resp.text()
                    logger.error(f"❌ Помилка отримання цін від CoinGecko для {user_id}. Статус: {resp.status}. Відповідь: {error_message}")
                    text_parts.append(f"❌ Помилка API CoinGecko (статус {resp.status}). Спробуйте пізніше.")
        
        final_text = "\n".join(text_parts)
        # Always include a back button
        keyboard_prices = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Оновити ціни", callback_data="get_prices")],
            [InlineKeyboardButton(text="↩️ Назад до меню", callback_data="back_to_main_menu")]
        ])

        if callback.message.text != final_text or callback.message.reply_markup != keyboard_prices : # Avoid MessageNotModified
             await callback.message.edit_text(final_text.strip(), parse_mode=ParseMode.HTML, reply_markup=keyboard_prices)

    except aiohttp.ClientError as e:
        logger.error(f"❌ ClientError під час отримання цін для {user_id}: {e}")
        await callback.message.edit_text("❌ Мережева помилка при отриманні цін. Спробуйте пізніше.", 
                                         reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="↩️ Назад до меню", callback_data="back_to_main_menu")]]))
    except Exception as e:
        logger.exception(f"❌ Неочікувана помилка під час отримання цін для {user_id}: {e}")
        await callback.message.edit_text("❌ Невідома помилка при отриманні цін. Спробуйте пізніше.",
                                         reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="↩️ Назад до меню", callback_data="back_to_main_menu")]]))

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
    setup_application(app, dp, bot=bot)
    web.run_app(app, host="0.0.0.0", port=PORT)
