from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
from bot.config import ADMIN_ID


class AdminMiddleware(BaseMiddleware):
    """
    Мидлварь для проверки прав администратора.
    Пропускает выполнение хэндлеров только если Telegram ID пользователя совпадает с ADMIN_ID.
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user: User = data.get("event_from_user")

        # Если пользователя нет или его ID не совпадает с ADMIN_ID — скипаем обработку
        if not user or user.id != ADMIN_ID:
            # Для CallbackQuery можно подсветить уведомление
            if hasattr(event, "answer"):
                await event.answer("❌ У вас нет прав администратора", show_alert=True)
            return

        # Если проверка прошла, передаем управление дальше в хэндлер
        return await handler(event, data)