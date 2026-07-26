from aiogram import Router, F, types
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# 1. ОБЪЕКТ РОУТЕРА (строго на верхнем уровне, без отступов)
router = Router()


# 2. КЛАССЫ CALLBACK DATA (внутри них ТОЛЬКО поля типов данных)

class PayPlanCallback(CallbackData, prefix="pay"):
    plan_key: str
    mode: str  # "new" | "renew" | "gift"


class DeviceCountCallback(CallbackData, prefix="dcnt"):
    plan_key: str
    mode: str
    count: int


class ConfirmDevicesCallback(CallbackData, prefix="dconf"):
    plan_key: str
    mode: str
    count: int


class BackToPlansCallback(CallbackData, prefix="btp"):
    mode: str


class PaymentMethodCallback(CallbackData, prefix="pm"):
    method: str  # "stars" | "cryptobot" | "qr" | "card"
    plan_key: str
    mode: str
    count: int


class GiftRedeemCallback(CallbackData, prefix="grd"):
    code: str


class AdminNavCallback(CallbackData, prefix="adm"):
    action: str


class NavCallback(CallbackData, prefix="nav"):
    target: str


# 3. ИНСТРУКЦИИ ПО ПОДКЛЮЧЕНИЮ
@router.callback_query(F.data == "instructions")
async def choose_device_instruction(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🍎 iOS (iPhone/iPad)", callback_data="inst_ios")],
        [InlineKeyboardButton(text="🤖 Android", callback_data="inst_android")],
        [InlineKeyboardButton(text="💻 Windows / macOS", callback_data="inst_pc")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_home")]
    ])
    await callback.message.edit_text(
        "📖 **ИНСТРУКЦИЯ ПО НАСТРОЙКЕ**\n\nВыберите ваше устройство:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("inst_"))
async def show_device_instruction(callback: types.CallbackQuery):
    dev_type = callback.data.split("_")[1]
    if dev_type == "ios":
        text = "🍎 **Настройка на iOS:**\n\n1. Установите **FoXray** или **Happ** из App Store.\n2. Скопируйте ваш VLESS-ключ в кабинете.\n3. Откройте приложение — оно предложит добавить скопированный ключ."
    elif dev_type == "android":
        text = "🤖 **Настройка на Android:**\n\n1. Установите **v2rayNG** из Google Play.\n2. Скопируйте ключ из бота.\n3. Откройте приложение, нажмите `+` -> «Импортировать профиль из буфера обмена»."
    else:
        text = "💻 **Настройка на ПК (Windows / macOS):**\n\n1. Скачайте клиент **Hiddify** или **v2rayN**.\n2. Скопируйте ваш ключ доступа.\n3. Нажмите кнопку добавления профиля из буфера обмена."

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ К выбору устройств", callback_data="instructions")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_home")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()


# 4. ПОДДЕРЖКА
@router.callback_query(F.data == "support")
async def support_handler(callback: types.CallbackQuery):
    admin_username = "ITJempo"  # Твой юзернейм без @
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Написать админу", url=f"https://t.me/{admin_username}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_home")]
    ])
    await callback.message.edit_text(
        f"💬 **ПОДДЕРЖКА ПОЛЬЗОВАТЕЛЕЙ**\n\n"
        f"Если у вас возникли вопросы по настройке или оплате, свяжитесь с нами напрямую:\n"
        f"Контакты: @{admin_username}",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await callback.answer()
