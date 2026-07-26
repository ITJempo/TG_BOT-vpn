import time
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, rate_limit: float = 0.6):
        self.rate_limit = rate_limit
        self.user_timestamps: Dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user = data.get("event_from_user")
        if user:
            now = time.time()
            last_time = self.user_timestamps.get(user.id, 0)
            if now - last_time < self.rate_limit:
                if isinstance(event, Message):
                    await event.answer("⚠️ Пожалуйста, не спамьте кнопками!")
                elif isinstance(event, CallbackQuery):
                    await event.answer("⚠️ Слишком частые клики!", show_alert=True)
                return
            self.user_timestamps[user.id] = now
        return await handler(event, data)