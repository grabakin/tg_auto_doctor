from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message
from config import Config
import logging

logger = logging.getLogger(__name__)


class WhitelistMiddleware(BaseMiddleware):
    """Middleware для проверки пользователей по белому списку"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """
        Проверяет, есть ли пользователь в белом списке
        
        Args:
            handler: Следующий обработчик
            event: Событие (сообщение, callback и т.д.)
            data: Данные контекста
            
        Returns:
            Результат обработчика или None если доступ запрещен
        """
        user = data.get("event_from_user")
        
        if not user:
            return await handler(event, data)
        
        user_id = user.id
        
        # Проверяем, есть ли пользователь в белом списке
        if user_id not in Config.WHITELIST_USER_IDS:
            logger.warning(
                f"Попытка доступа от неавторизованного пользователя: "
                f"ID={user_id}, username={user.username}"
            )
            
            # Если это сообщение, отправляем уведомление об отказе
            if isinstance(event, Message):
                from utils.formatter import MessageFormatter
                await event.answer(
                    MessageFormatter.format_access_denied(),
                    parse_mode="HTML"
                )
            
            return  # Прерываем обработку
        
        # Пользователь в белом списке, продолжаем обработку
        logger.info(f"Доступ разрешен для пользователя: ID={user_id}, username={user.username}")
        return await handler(event, data)
