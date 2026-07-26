import asyncio
import time
import logging
from aiogram import Bot
from bot.database.db import db
from bot.keyboards.inline import get_pricing_keyboard

DAY_MS = 24 * 60 * 60 * 1000


async def _notify(bot: Bot, flag_column: str, min_ms: int, max_ms: int, text: str):
    try:
        users = await db.get_users_expiring_between(min_ms, max_ms, flag_column)
    except Exception as e:
        logging.error(f"Ошибка выборки пользователей для напоминания ({flag_column}): {e}")
        return

    for user in users:
        try:
            await bot.send_message(
                chat_id=user["user_id"],
                text=text,
                parse_mode="Markdown",
                reply_markup=get_pricing_keyboard()
            )
        except Exception as e:
            logging.warning(f"Не удалось отправить пуш юзеру {user['user_id']}: {e}")
        finally:
            # Отмечаем как отправленное независимо от результата доставки,
            # чтобы не пытаться слать повторно юзерам, заблокировавшим бота.
            try:
                await db.mark_reminder_sent(user["user_id"], flag_column)
            except Exception as e:
                logging.error(f"Не удалось отметить напоминание отправленным для {user['user_id']}: {e}")


async def start_reminder_service(bot: Bot):
    """Фоновая задача: предупреждает пользователей за 3 дня и за 24 часа до конца подписки."""
    while True:
        try:
            now_ms = int(time.time() * 1000)

            # За 3 дня (окно: от +24ч до +3 дней, чтобы не пересекаться с 24-часовым напоминанием)
            await _notify(
                bot,
                "reminder_3d_sent",
                now_ms + DAY_MS,
                now_ms + 3 * DAY_MS,
                "⏳ **Через 3 дня закончится ваша VPN подписка.**\n\n"
                "Продлите её заранее, чтобы не потерять доступ без перерывов!"
            )

            # За 24 часа
            await _notify(
                bot,
                "reminder_24h_sent",
                now_ms,
                now_ms + DAY_MS,
                "⚠️ **Внимание! Ваша VPN подписка истекает в течение 24 часов.**\n\n"
                "Продлите подписку заранее, чтобы не потерять доступ!"
            )
        except Exception as e:
            logging.error(f"Ошибка в сервисе напоминаний: {e}")

        await asyncio.sleep(3600)  # Проверка раз в час
