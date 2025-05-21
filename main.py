@router.message()
async def handle_coin_input(message: types.Message):
    user_id = message.from_user.id
    user_data = user_settings.setdefault(user_id, {})
    if user_data.get("mode") != "selecting_coins":
        return

    coin_input = message.text.lower().strip()

    if coin_input == "готово":
        user_data["mode"] = None
        await message.answer("✅ Монети збережено. Тепер натисніть 'Дивитися ціни'.")
        return

    global coin_list_cache
    if not coin_list_cache:
        async with aiohttp.ClientSession() as session:
            url = "https://api.coingecko.com/api/v3/coins/list"
            async with session.get(url) as resp:
                coin_list_cache = await resp.json()

    matched_coin = next((c for c in coin_list_cache if coin_input == c['id'] or coin_input == c['symbol'].lower()), None)

    if not matched_coin:
        await message.answer("❌ Такої монети не знайдено. Спробуйте ще раз.")
        return

    coin_id = matched_coin['id']
    coin_symbol = matched_coin['symbol']
    coins = user_data.setdefault("coins", [])

    if coin_id in coins:
        await message.answer("ℹ️ Цю монету вже додано.")
    elif len(coins) >= 5:
        await message.answer("⚠️ Можна обрати максимум 5 монет.")
    else:
        coins.append(coin_id)
        await message.answer(f"✅ Додано монету: <b>{coin_symbol.upper()}</b> ({len(coins)}/5)", parse_mode=ParseMode.HTML)
