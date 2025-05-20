... (усі імпорти та налаштування залишаються без змін)

@router.callback_query(F.data == "setup_coins")
async def setup_coins(callback: types.CallbackQuery):
    logger.info(f"[CALLBACK] setup_coins від {callback.from_user.id}")
    try:
        await callback.message.answer("Введи назву монети або її частину (наприклад: btc або ethereum):")
        user_settings[callback.from_user.id] = user_settings.get(callback.from_user.id, {})
        user_settings[callback.from_user.id]["coins"] = []
        user_settings[callback.from_user.id]["coin_stage"] = True
    except Exception as e:
        logger.error(f"❌ setup_coins error: {e}")
        await callback.message.answer("⚠️ Виникла помилка.")
    await callback.answer()

@router.callback_query(F.data.startswith("coin_"))
async def select_coin(callback: types.CallbackQuery):
    logger.info(f"[CALLBACK] select_coin від {callback.from_user.id}, data={callback.data}")
    try:
        uid = callback.from_user.id
        coin_id = callback.data[len("coin_") :]
        if coin_id == "done":
            coins = user_settings.get(uid, {}).get("coins", [])
            if len(coins) < 5:
                await callback.message.answer(f"⚠️ Потрібно вибрати 5 монет. Ви вибрали: {len(coins)}")
            else:
                await callback.message.answer(f"🔘 Монети обрано: {', '.join(map(str.capitalize, coins))}")
                user_settings[uid].pop("coin_stage", None)
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Раз в годину", callback_data="freq_1h")],
                    [InlineKeyboardButton(text="Раз в 2 години", callback_data="freq_2h")],
                    [InlineKeyboardButton(text="Раз в 12 годин", callback_data="freq_12h")],
                    [InlineKeyboardButton(text="Раз на день", callback_data="freq_24h")],
                ])
                await callback.message.answer("Оберіть частоту надсилання:", reply_markup=keyboard)
        else:
            if "coin_stage" in user_settings.get(uid, {}) and len(user_settings[uid]["coins"]) < 5:
                if coin_id not in user_settings[uid]["coins"]:
                    user_settings[uid]["coins"].append(coin_id)
                    await callback.message.answer(f"✅ Монету обрано: {coin_id.replace('-', ' ').title()}")
            elif len(user_settings[uid]["coins"]) >= 5:
                await callback.message.answer("⚠️ Ви вже вибрали 5 монет.")
    except Exception as e:
        logger.error(f"❌ select_coin error: {e}")
        await callback.message.answer("⚠️ Помилка при виборі монети.")
    await callback.answer()

@router.callback_query(F.data.startswith("freq_"))
async def select_frequency(callback: types.CallbackQuery):
    logger.info(f"[CALLBACK] select_frequency від {callback.from_user.id}, data={callback.data}")
    try:
        freq = callback.data.split("_")[1]
        uid = callback.from_user.id
        user_settings[uid]["frequency"] = freq

        if freq in ["12h", "24h"]:
            times = [f"{str(h).zfill(2)}:00" for h in range(24)]
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=t, callback_data=f"settime_{t}")] for t in times
            ])
            await callback.message.answer("Оберіть час надсилання:", reply_markup=keyboard)
        else:
            await callback.message.answer(f"⏱ Частота встановлена: 1 раз в {freq[:-1]} годин")
            times = [f"{str(h).zfill(2)}:00" for h in range(24)]
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=t, callback_data=f"sleepstart_{t}")] for t in times
            ] + [[InlineKeyboardButton(text="❌ Вимкнути режим сну", callback_data="sleep_off")]])
            await callback.message.answer("🌙 Оберіть початок 'режиму сну' або вимкніть його:", reply_markup=keyboard)
    except Exception as e:
        logger.error(f"❌ select_frequency error: {e}")
        await callback.message.answer("⚠️ Помилка при виборі частоти.")
    await callback.answer()

@router.callback_query(F.data.startswith("settime_"))
async def choose_send_time(callback: types.CallbackQuery):
    logger.info(f"[CALLBACK] choose_send_time від {callback.from_user.id}, data={callback.data}")
    try:
        time = callback.data.split("_")[1]
        uid = callback.from_user.id
        freq = user_settings.get(uid, {}).get("frequency")
        user_settings[uid]["time"] = time

        if "timezone" not in user_settings[uid]:
            offset = datetime.now().astimezone().utcoffset()
            if offset:
                hours = int(offset.total_seconds() // 3600)
                user_settings[uid]["timezone"] = f"{hours:+03d}:00"
                await callback.message.answer(f"🌍 Таймзона автоматично встановлена на {user_settings[uid]['timezone']}")

        if freq == "12h":
            hour = int(time.split(":")[0])
            evening = (hour + 12) % 24
            user_settings[uid]["second_time"] = f"{str(evening).zfill(2)}:00"
            await callback.message.answer(f"⏱ Час встановлено: {time} та {str(evening).zfill(2)}:00 (12 годин)")
        else:
            await callback.message.answer(f"⏱ Час встановлено: {time} (раз на день)")
    except Exception as e:
        logger.error(f"❌ choose_send_time error: {e}")
        await callback.message.answer("⚠️ Помилка при встановленні часу.")
    await callback.answer()

@router.callback_query(F.data.startswith("sleepstart_"))
async def choose_sleep_start(callback: types.CallbackQuery):
    logger.info(f"[CALLBACK] choose_sleep_start від {callback.from_user.id}, data={callback.data}")
    try:
        uid = callback.from_user.id
        start = callback.data.split("_")[1]
        user_settings[uid]["sleep_start"] = start
        times = [f"{str(h).zfill(2)}:00" for h in range(24)]
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t, callback_data=f"sleepend_{t}")] for t in times
        ])
        await callback.message.answer("🌙 Оберіть завершення 'режиму сну':", reply_markup=keyboard)
    except Exception as e:
        logger.error(f"❌ choose_sleep_start error: {e}")
        await callback.message.answer("⚠️ Помилка при встановленні початку режиму сну.")
    await callback.answer()

@router.callback_query(F.data.startswith("sleepend_"))
async def choose_sleep_end(callback: types.CallbackQuery):
    logger.info(f"[CALLBACK] choose_sleep_end від {callback.from_user.id}, data={callback.data}")
    try:
        uid = callback.from_user.id
        end = callback.data.split("_")[1]
        start = user_settings[uid].get("sleep_start")
        if start:
            user_settings[uid]["sleep"] = {"start": start, "end": end}
            await callback.message.answer(f"🌙 Режим сну встановлено з {start} до {end}.")
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Скинути всі налаштування", callback_data="reset_settings")]
            ])
            await callback.message.answer("✅ Налаштування збережено. Ви можете скинути їх у будь-який момент:", reply_markup=keyboard)
        else:
            await callback.message.answer("⚠️ Спочатку виберіть початок режиму сну.")
    except Exception as e:
        logger.error(f"❌ choose_sleep_end error: {e}")
        await callback.message.answer("⚠️ Помилка при встановленні завершення режиму сну.")
    await callback.answer()

@router.callback_query(F.data == "sleep_off")
async def disable_sleep_mode(callback: types.CallbackQuery):
    logger.info(f"[CALLBACK] disable_sleep_mode від {callback.from_user.id}")
    try:
        uid = callback.from_user.id
        user_settings[uid].pop("sleep", None)
        user_settings[uid].pop("sleep_start", None)
        await callback.message.answer("❌ Режим сну вимкнено.")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Скинути всі налаштування", callback_data="reset_settings")]
        ])
        await callback.message.answer("✅ Налаштування збережено. Ви можете скинути їх у будь-який момент:", reply_markup=keyboard)
    except Exception as e:
        logger.error(f"❌ disable_sleep_mode error: {e}")
        await callback.message.answer("⚠️ Помилка при вимкненні режиму сну.")
    await callback.answer()

@router.callback_query(F.data == "reset_settings")
async def reset_settings(callback: types.CallbackQuery):
    logger.info(f"[CALLBACK] reset_settings від {callback.from_user.id}")
    try:
        user_settings.pop(callback.from_user.id, None)
        await callback.message.answer("🔄 Всі налаштування скинуто. Почнемо знову з /start")
    except Exception as e:
        logger.error(f"❌ reset_settings error: {e}")
        await callback.message.answer("⚠️ Помилка при скиданні налаштувань.")
    await callback.answer()
