from aiogram import Router, F, types
from aiogram.types import FSInputFile, InputMediaPhoto

from bot.database.db import db
from bot.keyboards.callbacks import NavCallback
from bot.keyboards.inline import get_referral_keyboard

# Пытаемся импортировать значение из конфигурации, либо берем 7 дней по умолчанию
try:
    from bot.config import REFERRAL_DAYS
except ImportError:
    REFERRAL_DAYS = 7

router = Router()

BANNER_REF = "bot/assets/referral_banner.png"


async def safe_edit_message(callback: types.CallbackQuery, photo_path: str, caption: str, reply_markup=None):
    """Безопасно заменяет баннер и текст сообщения."""
    try:
        if callback.message.photo:
            await callback.message.edit_media(
                media=InputMediaPhoto(
                    media=FSInputFile(photo_path),
                    caption=caption,
                    parse_mode="Markdown"
                ),
                reply_markup=reply_markup
            )
        else:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=FSInputFile(photo_path),
                caption=caption,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
    except Exception:
        try:
            await callback.message.answer_photo(
                photo=FSInputFile(photo_path),
                caption=caption,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        except Exception:
            pass


@router.callback_query(NavCallback.filter(F.target == "referral"))
async def referral_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    bot_info = await callback.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"

    # Получаем количество рефералов
    ref_count = await db.get_referrals_count(user_id) if hasattr(db, 'get_referrals_count') else 0

    text = (
        "🤝 **РЕФЕРАЛЬНАЯ ПРОГРАММА**\n\n"
        "Делитесь своей ссылкой с друзьями и получайте бесплатные дни использования!\n\n"
        f"🎁 **Бонус:** +{REFERRAL_DAYS} дней подписки за каждого приглашённого друга!\n\n"
        f"🔗 **Ваша реферальная ссылка:**\n`{ref_link}`\n\n"
        f"👥 **Приглашено друзей:** `{ref_count}`\n\n"
        "💡 _Нажмите на ссылку, чтобы скопировать её в буфер обмена._"
    )

    # Универсальный вызов генератора клавиатуры
    try:
        keyboard = get_referral_keyboard(user_id, ref_link)
    except TypeError:
        try:
            keyboard = get_referral_keyboard(user_id)
        except TypeError:
            keyboard = get_referral_keyboard(ref_link)

    await safe_edit_message(callback, BANNER_REF, text, reply_markup=keyboard)
    await callback.answer()