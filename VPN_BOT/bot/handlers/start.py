import time
from datetime import datetime
from aiogram import Router, F, types
from aiogram.filters import CommandStart, CommandObject, Command

from bot.config import config, TRIAL_DAYS, BASE_DEVICES, TRIAL_DEVICES
from bot.database.db import db
from bot.keyboards.inline import get_main_menu, get_pricing_keyboard, get_start_options_keyboard, get_plan_list_keyboard
from bot.keyboards.callbacks import NavCallback
from bot.services.vpn_panel import VPNPanelService
from bot.utils.xui import add_extra_device

router = Router()


# --- 1. КОМАНДА /start ---
@router.message(CommandStart())
async def cmd_start(message: types.Message, command: CommandObject):
    user_id = message.from_user.id
    username = message.from_user.username or "User"
    referrer_id = None

    if command.args and command.args.startswith("ref_"):
        try:
            parsed_ref = int(command.args.replace("ref_", ""))
            if parsed_ref != user_id:
                referrer_id = parsed_ref
        except ValueError:
            pass

    user = await db.get_user(user_id)
    if not user:
        await db.add_or_update_user(
            user_id=user_id, 
            username=username, 
            email=f"tg_{user_id}", 
            expiry_time=0, 
            referrer_id=referrer_id
        )
        user = await db.get_user(user_id)

    # Погашение подарочного сертификата по диплинку /start gift_<code>
    if command.args and command.args.startswith("gift_"):
        from bot.handlers.payments import redeem_gift_code
        gift_code = command.args.replace("gift_", "")
        result_text = await redeem_gift_code(gift_code, user_id, message.from_user.username or "User")
        await message.answer(result_text, parse_mode="Markdown")

    expiry_time = user.get("expiry_time", 0) if user else 0
    has_sub = bool(expiry_time > int(time.time() * 1000)) if expiry_time > 0 else False
    
    menu = await get_main_menu(user_id, has_sub)
    
    welcome_text = (
        f"✨ **Приветствую, {message.from_user.first_name}!**\n\n"
        f"⚡ **Добро пожаловать в самый быстрый и стабильный VPN — JempoVPN!**\n\n"
        f"— Работаем уже больше года\n"
        f"— Высокая скорость соединения\n"
        f"— Полная приватность, без логов\n"
        f"— Реферальная система 50%\n"
        f"— Быстрая поддержка 24/7\n"
        f"— Поддержка ПК, Телефонов и Телевизоров!\n\n"
        f"🔒 VPN прямо в Telegram — без сторонних приложений для настройки.\n\n"
        f"🎁 **{TRIAL_DAYS} дня бесплатной подписки — просто нажми «Начать»!**"
    )

    await message.answer(
        welcome_text,
        reply_markup=menu,
        parse_mode="Markdown"
    )


# --- 1.1 КОМАНДА /menu — быстрый вызов главного меню ---
@router.message(Command("menu"))
async def cmd_menu(message: types.Message):
    user = await db.get_user(message.from_user.id)
    expiry_time = user.get("expiry_time", 0) if user else 0
    has_sub = bool(expiry_time > int(time.time() * 1000)) if expiry_time > 0 else False
    menu = await get_main_menu(message.from_user.id, has_sub)
    await message.answer("⚡ **Главное меню JempoVPN**", reply_markup=menu, parse_mode="Markdown")


# --- 1.2 КОМАНДА /help — инструкция по подключению ---
@router.message(Command("help"))
async def cmd_help(message: types.Message):
    text = (
        "📖 **ИНСТРУКЦИЯ ПО НАСТРОЙКЕ**\n\n"
        "1️⃣ Скопируйте ваш ключ из **Мой кабинет**.\n"
        "2️⃣ Установите подходящий клиент на устройство:\n\n"
        "🍏 **iOS / iPhone:** `v2box` или `Streisand`\n"
        "🤖 **Android:** `v2rayNG` или `Happ`\n"
        "💻 **Windows:** `v2rayN` или `Nekoray`\n"
        "🍏 **macOS:** `v2box` или `Streisand`\n\n"
        "3️⃣ Вставьте ключ из буфера обмена в приложение и нажмите **Подключить**."
    )
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⚡ Главное меню", callback_data=NavCallback(target="home").pack())]
    ])
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")


# --- 1.3 КОМАНДА /info — о сервисе ---
@router.message(Command("info"))
async def cmd_info(message: types.Message):
    text = (
        f"ℹ️ **О СЕРВИСЕ JempoVPN**\n\n"
        f"— Работаем уже больше года\n"
        f"— Высокая скорость соединения, современный протокол VLESS Reality\n"
        f"— Полная приватность, без логов\n"
        f"— Реферальная система 50%\n"
        f"— Быстрая поддержка 24/7\n"
        f"— Поддержка ПК, Телефонов и Телевизоров\n\n"
        f"🎁 Новым пользователям — {TRIAL_DAYS} дня бесплатно."
    )
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⚡ Главное меню", callback_data=NavCallback(target="home").pack())]
    ])
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")


# --- 2. ВОЗВРАТ В ГЛАВНОЕ МЕНЮ ---
@router.callback_query(NavCallback.filter(F.target == "home"))
async def back_home_handler(callback: types.CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    expiry_time = user.get("expiry_time", 0) if user else 0
    has_sub = bool(expiry_time > int(time.time() * 1000)) if expiry_time > 0 else False
    
    menu = await get_main_menu(callback.from_user.id, has_sub)
    await callback.message.edit_text("⚡ **Главное меню JempoVPN**", reply_markup=menu, parse_mode="Markdown")
    await callback.answer()


# --- 3. МОЙ КАБИНЕТ И УПРАВЛЕНИЕ КЛЮЧАМИ (my_sub) ---
@router.callback_query(NavCallback.filter(F.target == "my_sub"))
async def my_sub_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    expiry_ms = user.get("expiry_time", 0) if user else 0
    now_ms = int(time.time() * 1000)
    has_sub = expiry_ms > now_ms

    # Получаем все ключи пользователя из панели 3X-UI по его Telegram ID
    from bot.utils.xxy import get_clients_by_tg_id 
    user_keys = await get_clients_by_tg_id(user_id)
    device_limit = await db.get_device_limit(user_id, default=BASE_DEVICES)

    if has_sub:
        expiry_date = datetime.fromtimestamp(expiry_ms / 1000).strftime("%d.%m.%Y в %H:%M")
        status = f"🟢 **Активна до:** `{expiry_date}`"
    else:
        status = "🔴 **Подписка не активна**"

    text = (
        f"👤 **ЛИЧНЫЙ КАБИНЕТ И УСТРОЙСТВА**\n\n"
        f"🆔 **Ваш ID:** `{user_id}`\n"
        f"Статус: {status}\n\n"
        f"📱 **Ваши активные устройства (ключи):** `{len(user_keys)}` из `{device_limit}`\n"
        f"Выберите устройство для просмотра ключа или добавьте новое:"
    )

    from bot.keyboards.inline import get_my_sub_keyboard
    keyboard = get_my_sub_keyboard(has_sub, user_keys, device_limit)

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()


# --- ПРОСМОТР КОНКРЕТНОГО КЛЮЧА ---
@router.callback_query(F.data.startswith("manage_key_"))
async def manage_single_key(callback: types.CallbackQuery):
    client_uuid = callback.data.replace("manage_key_", "")
    
    # Ищем клиента в панели по UUID и генерируем для него VLESS строку
    from bot.utils.xxy import get_vless_link_by_uuid
    vless_link = await get_vless_link_by_uuid(client_uuid)

    if not vless_link:
        await callback.answer("❌ Ключ не найден или был удален.", show_alert=True)
        return

    from bot.keyboards.inline import get_single_key_keyboard
    keyboard = get_single_key_keyboard(client_uuid)

    text = (
        f"🔑 **УПРАВЛЕНИЕ КЛЮЧОМ**\n\n"
        f"Скопируйте вашу персональную ссылку для подключения:\n\n"
        f"`{vless_link}`\n\n"
        f"💡 _Нажмите на ключ, чтобы скопировать его в буфер обмена._"
    )
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()


# --- СОЗДАНИЕ НОВОГО КЛЮЧА (УСТРОЙСТВА) ---
@router.callback_query(F.data == "create_new_key")
async def create_device_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    expiry_ms = user.get("expiry_time", 0) if user else 0
    now_ms = int(time.time() * 1000)

    if expiry_ms <= now_ms:
        await callback.answer("❌ Для создания новых устройств необходима активная подписка!", show_alert=True)
        return

    from bot.utils.xxy import get_clients_by_tg_id
    current_keys = await get_clients_by_tg_id(user_id)
    device_limit = await db.get_device_limit(user_id, default=BASE_DEVICES)

    if len(current_keys) >= device_limit:
        await callback.answer(
            f"❌ Достигнут лимит устройств для вашего тарифа ({device_limit}). "
            f"Купите больше устройств при продлении подписки.",
            show_alert=True
        )
        return

    # Новое устройство должно жить ровно до конца текущей подписки
    remaining_days = max(1, -(-(expiry_ms - now_ms) // (24 * 60 * 60 * 1000)))  # округление вверх

    new_config = await add_extra_device(user_id, days=remaining_days)

    if new_config and str(new_config).startswith("vless://"):
        await callback.answer("✅ Новое устройство успешно добавлено!", show_alert=True)
        # Возвращаем в кабинет
        await my_sub_handler(callback)
    else:
        await callback.answer("⚠️ Ошибка панели, попробуйте позже.", show_alert=True)


# --- УДАЛЕНИЕ КЛЮЧА ---
@router.callback_query(F.data.startswith("delete_key_"))
async def delete_device_handler(callback: types.CallbackQuery):
    client_uuid = callback.data.replace("delete_key_", "")
    
    from bot.utils.xxy import delete_client_by_uuid
    success = await delete_client_by_uuid(client_uuid)

    if success:
        await callback.answer("🗑 Устройство успешно удалено!", show_alert=True)
    else:
        await callback.answer("❌ Не удалось удалить устройство.", show_alert=True)
        
    await my_sub_handler(callback)


# --- 4. "СТАРТУЕМ СЕЙЧАС!" — ТОЧКА ВХОДА В ПОКУПКУ ПОДПИСКИ (buy_sub) ---
@router.callback_query(NavCallback.filter(F.target == "buy_sub"))
async def buy_sub_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    expiry_ms = user.get("expiry_time", 0) if user else 0
    has_sub = expiry_ms > int(time.time() * 1000)

    header = (
        "🚀 **СТАРТУЕМ СЕЙЧАС!**\n"
        "Выберите оптимальный тариф для себя, друзей и близких.\n\n"
    )

    if has_sub:
        text = header + "У вас уже есть активная подписка. Что вы хотите сделать?"
        keyboard = get_start_options_keyboard()
    else:
        trial_used = bool(user.get("trial_used")) if user else False
        text = header + "Выберите тариф ниже, чтобы подключиться:"
        keyboard = get_plan_list_keyboard(mode="new", show_trial=not trial_used)

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(NavCallback.filter(F.target == "renew_current"))
async def renew_current_handler(callback: types.CallbackQuery):
    order_tag = str(callback.from_user.id)[-5:]
    text = (
        f"🔄 **Продление подписки #{order_tag}**\n\n"
        f"Выберите новый тариф (будет установлен как текущий) или тот же самый. Дни суммируются."
    )
    keyboard = get_plan_list_keyboard(mode="renew")
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(NavCallback.filter(F.target == "buy_new"))
async def buy_new_handler(callback: types.CallbackQuery):
    text = "➕ **Новая подписка**\n\nВыберите тариф для нового ключа:"
    keyboard = get_plan_list_keyboard(mode="new")
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()


# --- 5. АКТИВАЦИЯ ТРИАЛА ---
@router.callback_query(NavCallback.filter(F.target == "claim_trial"))
async def claim_trial_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)

    if user and user.get("trial_used"):
        await callback.answer("❌ Вы уже использовали бесплатный пробный период!", show_alert=True)
        return

    await callback.message.edit_text("⏳ Активируем ваш тестовый период...")
    vpn_config = await VPNPanelService.generate_vpn_key(user_id, callback.from_user.username or "TrialUser", days=TRIAL_DAYS)
    
    if vpn_config and str(vpn_config).startswith("vless://"):
        new_expiry = int((time.time() + TRIAL_DAYS * 86400) * 1000)
        await db.add_or_update_user(
            user_id=user_id, 
            username=callback.from_user.username or "User", 
            email=f"tg_{user_id}", 
            expiry_time=new_expiry,
            trial_used=1
        )

        await db.set_device_limit(user_id, TRIAL_DEVICES)

        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="📖 Инструкция", callback_data=NavCallback(target="instructions").pack())],
            [types.InlineKeyboardButton(text="◀️ В меню", callback_data=NavCallback(target="home").pack())]
        ])

        await callback.message.edit_text(
            f"✅ **Пробный доступ активирован**\n\n"
            f"⏳ Срок: {TRIAL_DAYS} дн.\n"
            f"📱 Устройств: {TRIAL_DEVICES}\n"
            f"🔗 Конфигурация:\n\n"
            f"`{vpn_config}`\n\n"
            f"Откройте ссылку в приложении на вашем устройстве. Подсказки — в разделе «🧭 Инструкция».",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

        # Небольшой апсейл сразу после активации триала, как у Kakadu
        try:
            hot_plan = None
            from bot.config import PRICING_PLANS
            hot_plan = PRICING_PLANS.get("sub_30_days")
            if hot_plan:
                upsell_kb = types.InlineKeyboardMarkup(inline_keyboard=[[
                    types.InlineKeyboardButton(
                        text=f"🔥 Купить за {hot_plan['stars']}⭐",
                        callback_data=NavCallback(target="buy_new").pack()
                    )
                ]])
                await callback.message.answer("😏 Забирай тариф по вкусной цене!", reply_markup=upsell_kb)
        except Exception:
            pass
    else:
        await callback.message.edit_text(f"❌ Ошибка генерации ключа: {vpn_config}")
    
    await callback.answer()


# --- 6. ИНСТРУКЦИИ ПО ПОДКЛЮЧЕНИЮ (instructions) ---
@router.callback_query(NavCallback.filter(F.target == "instructions"))
async def instructions_handler(callback: types.CallbackQuery):
    text = (
        "📖 **ИНСТРУКЦИЯ ПО НАСТРОЙКЕ**\n\n"
        "1️⃣ Скопируйте ваш ключ из **Моих ключей**.\n"
        "2️⃣ Установите подходящий клиент на устройство:\n\n"
        "🍏 **iOS / iPhone:** `v2box` или `Streisand`\n"
        "🤖 **Android:** `v2rayNG` или `Happ`\n"
        "💻 **Windows:** `v2rayN` или `Nekoray`\n"
        "🍏 **macOS:** `v2box` или `Streisand`\n\n"
        "3️⃣ Вставьте ключ из буфера обмена в приложение и нажмите **Подключить**."
    )
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="◀️ Назад", callback_data=NavCallback(target="home").pack())]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()


# --- 7. ПОДДЕРЖКА (support) ---
@router.callback_query(NavCallback.filter(F.target == "support"))
async def support_handler(callback: types.CallbackQuery):
    admin_username = getattr(config, 'ADMIN_USERNAME', 'ITJempo')
    text = (
        "👨‍💻 **СЛУЖБА ПОДДЕРЖКИ**\n\n"
        "Возникли вопросы по настройке или работе сервиса?\n"
        f"Напишите нашему администратору напрямую:"
    )
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="💬 Написать администратору", url=f"https://t.me/{admin_username}")],
        [types.InlineKeyboardButton(text="◀️ Назад", callback_data=NavCallback(target="home").pack())]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()


# --- 8. СТАТУС СЕРВЕРА (server_stats) ---
@router.callback_query(NavCallback.filter(F.target == "server_stats"))
async def server_stats_handler(callback: types.CallbackQuery):
    await callback.answer("🟢 Все узлы работают штатно. Аптайм 99.9%", show_alert=True)


# --- 9. УСЛОВИЯ ИСПОЛЬЗОВАНИЯ (terms) ---
@router.callback_query(NavCallback.filter(F.target == "terms"))
async def terms_handler(callback: types.CallbackQuery):
    text = (
        "📄 **УСЛОВИЯ ИСПОЛЬЗОВАНИЯ**\n\n"
        "1. Сервис предоставляется «как есть», без гарантий бесперебойной работы 24/7.\n"
        "2. Оплаченные периоды подписки возврату не подлежат, кроме случаев технической неисправности по вине сервиса.\n"
        "3. Запрещено использовать сервис для противоправной деятельности.\n"
        "4. Один тариф допускает ограниченное количество одновременных устройств — при превышении лимита старые подключения могут быть отключены.\n"
        "5. Администрация оставляет за собой право заблокировать доступ при нарушении правил использования.\n\n"
        "По всем вопросам — раздел «💬 Поддержка»."
    )
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="◀️ Назад", callback_data=NavCallback(target="home").pack())]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()
