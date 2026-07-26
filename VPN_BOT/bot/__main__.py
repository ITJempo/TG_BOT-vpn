import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat

from bot.config import config
from bot.database.db import db
from bot.utils.logger import setup_logger
from bot.middlewares.throttling import ThrottlingMiddleware
from bot.services.reminder import start_reminder_service

# Импорт роутеров
from bot.handlers.start import router as start_router
from bot.handlers.payments import router as payments_router
from bot.handlers.referral import router as referral_router
from bot.handlers.admin import router as admin_router
from bot.keyboards.callbacks import router as callbacks_router
from bot.handlers.support import router as support_router  # ИИ-поддержка


async def set_bot_commands(bot: Bot):
    # Команды для всех пользователей в меню Telegram (кнопка Menu)
    user_commands = [
        BotCommand(command="start", description="🚀 Запустить бота"),
        BotCommand(command="menu", description="⚡ Главное меню"),
        BotCommand(command="help", description="📖 Инструкция по подключению"),
        BotCommand(command="info", description="ℹ️ О сервисе"),
    ]
    await bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())

    # Персональные команды для администратора (дополнительная команда /admin)
    if hasattr(config, "ADMIN_ID") and config.ADMIN_ID:
        admin_commands = user_commands + [
            BotCommand(command="admin", description="👑 Панель администратора")
        ]
        try:
            await bot.set_my_commands(
                admin_commands, 
                scope=BotCommandScopeChat(chat_id=config.ADMIN_ID)
            )
        except Exception:
            pass


async def main():
    setup_logger()
    logging.info("Инициализация проекта...")

    # Инициализация локальной БД
    await db.init()

    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Регистрация функции установки команд при старте бота
    dp.startup.register(set_bot_commands)

    # Глобальные мидлвари
    dp.message.middleware(ThrottlingMiddleware(rate_limit=0.6))
    dp.callback_query.middleware(ThrottlingMiddleware(rate_limit=0.6))

    # Регистрация роутеров
    dp.include_router(start_router)
    dp.include_router(payments_router)
    dp.include_router(referral_router)
    dp.include_router(callbacks_router)
    dp.include_router(admin_router)
    dp.include_router(support_router)  # Подключили ИИ-поддержку

    # Очистка старых хэндлеров
    await bot.delete_webhook(drop_pending_updates=True)

    # Запуск асинхронного таска напоминаний
    asyncio.create_task(start_reminder_service(bot))

    logging.info("Бот успешно запущен!")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())