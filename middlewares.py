from typing import Any, Awaitable, Callable, Dict
import time

from aiogram import BaseMiddleware
from aiogram.types import Message

class ThrottlingMiddleware(BaseMiddleware):
    """
    Spam va ortiqcha so'rovlarning oldini olish uchun oddiy Throttling (Anti-spam).
    """
    def __init__(self, limit: float = 1.0):
        self.limit = limit
        self.users = {}

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id
        now = time.time()
        last_time = self.users.get(user_id, 0)
        
        if now - last_time < self.limit:
            # Drop silently
            return
            
        self.users[user_id] = now
        return await handler(event, data)
