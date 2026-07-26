from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.config import PRICING_PLANS, config, BASE_DEVICES, MAX_DEVICES, EXTRA_DEVICE_STARS, TRIAL_DAYS
from bot.keyboards.callbacks import (
    PayPlanCallback, NavCallback, AdminNavCallback,
    DeviceCountCallback, ConfirmDevicesCallback, BackToPlansCallback,
    PaymentMethodCallback,
)


def strike(text: str) -> str:
    """Юникод-зачёркивание для текста кнопок (Telegram не рендерит Markdown в кнопках)."""
    return "".join(f"{ch}\u0336" for ch in text)


# ──────────────────────────────────────────────────────────────
# ГЛАВНОЕ МЕНЮ (в стиле Kakadu VPN)
# ──────────────────────────────────────────────────────────────
async def get_main_menu(user_id: int, has_subscription: bool) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="🚀 Начать", callback_data=NavCallback(target="buy_sub").pack())],
        [
            InlineKeyboardButton(text="🔑 Мои ключи", callback_data=NavCallback(target="my_sub").pack()),
            InlineKeyboardButton(text="📖 Инструкция", callback_data=NavCallback(target="instructions").pack())
        ],
        [
            InlineKeyboardButton(text="🤝 Партнёрам", callback_data=NavCallback(target="referral").pack()),
            InlineKeyboardButton(text="📄 Условия", callback_data=NavCallback(target="terms").pack())
        ],
        [
            InlineKeyboardButton(text="💬 Поддержка", callback_data=NavCallback(target="support").pack()),
            InlineKeyboardButton(text="📊 Состояние сети", callback_data=NavCallback(target="server_stats").pack())
        ],
    ]

    if user_id == config.ADMIN_ID:
        keyboard.append([InlineKeyboardButton(text="👑 Админ-Панель", callback_data=AdminNavCallback(action="main").pack())])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ──────────────────────────────────────────────────────────────
# ПРОМЕЖУТОЧНЫЙ ЭКРАН "Стартуем сейчас!" — когда у юзера УЖЕ есть подписка
# ──────────────────────────────────────────────────────────────
def get_start_options_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Продлить текущую", callback_data=NavCallback(target="renew_current").pack())],
        [InlineKeyboardButton(text="➕ Купить новую", callback_data=NavCallback(target="buy_new").pack())],
        [InlineKeyboardButton(text="🎁 Купить в подарок", callback_data=NavCallback(target="gift_flow").pack())],
        [InlineKeyboardButton(text="🎟 Ввести промокод", callback_data=NavCallback(target="promo_flow").pack())],
        [InlineKeyboardButton(text="📖 Инструкция", callback_data=NavCallback(target="instructions").pack())],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=NavCallback(target="home").pack())]
    ])


# ──────────────────────────────────────────────────────────────
# СПИСОК ТАРИФОВ (с "зачёркнутой" старой ценой)
# mode: "new" | "renew" | "gift"
# show_trial: показать строку с бесплатным пробным периодом (только для новых юзеров)
# ──────────────────────────────────────────────────────────────
def get_plan_list_keyboard(mode: str, show_trial: bool = False) -> InlineKeyboardMarkup:
    keyboard = []

    if show_trial:
        keyboard.append([InlineKeyboardButton(
            text=f"🎁 Активировать {TRIAL_DAYS} дня бесплатно",
            callback_data=NavCallback(target="claim_trial").pack()
        )])

    for key, plan in PRICING_PLANS.items():
        old_part = f"{strike(str(plan['old_stars']) + '⭐')} | " if plan.get("old_stars") else ""
        text = f"{plan['title']} ✦ {old_part}{plan['stars']}⭐ 🎯"
        keyboard.append([InlineKeyboardButton(
            text=text,
            callback_data=PayPlanCallback(plan_key=key, mode=mode).pack()
        )])

    keyboard.append([InlineKeyboardButton(text="🎟 Ввести промокод", callback_data=NavCallback(target="promo_flow").pack())])
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data=NavCallback(target="buy_sub").pack())])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ──────────────────────────────────────────────────────────────
# ВЫБОР КОЛИЧЕСТВА УСТРОЙСТВ
# ──────────────────────────────────────────────────────────────
def get_device_count_keyboard(plan_key: str, mode: str, selected_count: int) -> InlineKeyboardMarkup:
    keyboard = []
    row = []
    for n in range(BASE_DEVICES, MAX_DEVICES + 1):
        label = f"✅ {n}" if n == selected_count else str(n)
        row.append(InlineKeyboardButton(
            text=label,
            callback_data=DeviceCountCallback(plan_key=plan_key, mode=mode, count=n).pack()
        ))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton(
        text="✅ Подтвердить",
        callback_data=ConfirmDevicesCallback(plan_key=plan_key, mode=mode, count=selected_count).pack()
    )])
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data=BackToPlansCallback(mode=mode).pack())])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ──────────────────────────────────────────────────────────────
# ВЫБОР СПОСОБА ОПЛАТЫ
# Реально работает только "stars" (Telegram Stars). Остальные — заглушки,
# пока к боту не подключены другие платёжные провайдеры.
# ──────────────────────────────────────────────────────────────
def get_payment_method_keyboard(plan_key: str, mode: str, count: int) -> InlineKeyboardMarkup:
    def cb(method: str) -> str:
        return PaymentMethodCallback(method=method, plan_key=plan_key, mode=mode, count=count).pack()

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Оплатить звёздами", callback_data=cb("stars"))],
        [InlineKeyboardButton(text="🌐 CryptoBot", callback_data=cb("cryptobot"))],
        [InlineKeyboardButton(text="📱 Рубли QR СБП", callback_data=cb("qr"))],
        [InlineKeyboardButton(text="💳 Оплата картой", callback_data=cb("card"))],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=BackToPlansCallback(mode=mode).pack())]
    ])


def get_pricing_keyboard() -> InlineKeyboardMarkup:
    """Оставлено для обратной совместимости (используется реминдером о продлении)."""
    return get_plan_list_keyboard(mode="renew")


def get_referral_keyboard(bot_username: str, user_id: int) -> InlineKeyboardMarkup:
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    share_text = f"🚀 Быстрый и надежный VPN! Подключайся по моей ссылке: {ref_link}"
    share_url = f"https://t.me/share/url?url={ref_link}&text={share_text}"

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Поделиться с другом", url=share_url)],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=NavCallback(target="home").pack())]
    ])


def get_my_sub_keyboard(has_sub: bool, user_keys: list, device_limit: int) -> InlineKeyboardMarkup:
    keyboard = []

    for idx, client in enumerate(user_keys, start=1):
        email = client.get("email", f"Устройство {idx}")
        c_uuid = client.get("id", "")
        keyboard.append([
            InlineKeyboardButton(text=f"📱 Устройство #{idx} ({email.split('_')[-1]})", callback_data=f"manage_key_{c_uuid}")
        ])

    if has_sub and len(user_keys) < device_limit:
        keyboard.append([InlineKeyboardButton(text="➕ Создать новое устройство", callback_data="create_new_key")])

    if has_sub and len(user_keys) < MAX_DEVICES:
        keyboard.append([InlineKeyboardButton(
            text=f"💳 Докупить устройство (+{EXTRA_DEVICE_STARS}⭐)",
            callback_data="buy_extra_device"
        )])

    keyboard.append([InlineKeyboardButton(text="💳 Продлить / Купить", callback_data=NavCallback(target="buy_sub").pack())])
    keyboard.append([InlineKeyboardButton(text="◀️ Назад в меню", callback_data=NavCallback(target="home").pack())])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_single_key_keyboard(client_uuid: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Удалить устройство", callback_data=f"delete_key_{client_uuid}")],
        [InlineKeyboardButton(text="◀️ К списку устройств", callback_data=NavCallback(target="my_sub").pack())]
    ])
