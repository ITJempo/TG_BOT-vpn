import asyncio
import logging
from aiogram import Bot
from bot.database.db import db
from bot.keyboards.inline import get_pricing_keyboard

async def start_reminder_service(bot: Bot):
    """Фоновая задача проверок окончания подписок"""
    while True:
        try:
            expiring_users = await db.get_expiring_users()
            for user in expiring_users:
                try:
                    await bot.send_message(
                        chat_id=user["user_id"],
                        text="⚠️ **Внимание! Ваша VPN подписка истекает в течение 24 часов.**\n\nПродлите подписку заранее, чтобы не потерять доступ!",
                        parse_mode="Markdown",
                        reply_markup=get_pricing_keyboard()
                    )
                except Exception as e:
                    logging.warning(f"Не удалось отправить пуш юзеру {user['user_id']}: {e}")
        except Exception as e:
            logging.error(f"Ошибка в сервисе напоминаний: {e}")

        await asyncio.sleep(3600)  # Цикл раз в час