import logging
from typing import List, Dict, Any
from aiogram import Bot
from database.db import Database
from utils.formatter import MessageFormatter

logger = logging.getLogger(__name__)


class NotificationService:
    """Сервис для отправки уведомлений пользователям"""
    
    def __init__(self, bot: Bot, db: Database):
        self.bot = bot
        self.db = db
        self.formatter = MessageFormatter()
    
    async def notify_new_appointments(self, appointments: List[Dict[str, Any]]):
        """
        Отправить уведомления о новых записях всем активным пользователям
        
        Args:
            appointments: Список новых записей
        """
        if not appointments:
            logger.info("Нет новых записей для уведомления")
            return
        
        # Получаем список активных пользователей
        active_users = await self.db.get_active_users()
        
        if not active_users:
            logger.warning("Нет активных пользователей для отправки уведомлений")
            return
        
        logger.info(f"Отправка {len(appointments)} уведомлений {len(active_users)} пользователям")
        
        # Отправляем уведомления каждому пользователю
        for user_id in active_users:
            for appointment in appointments:
                try:
                    # Проверяем, не отправляли ли уже это уведомление
                    was_sent = await self.db.was_notified(
                        user_id=user_id,
                        doctor_id=appointment['id'],
                        date=appointment['date'],
                        notification_type='new_appointment',
                        hours=24  # Не отправляем повторно в течение 24 часов
                    )
                    
                    if was_sent:
                        logger.debug(
                            f"Уведомление для пользователя {user_id} уже отправлялось, пропускаем"
                        )
                        continue
                    
                    # Форматируем сообщение
                    message_text = self.formatter.format_appointment(appointment)
                    
                    # Отправляем сообщение
                    await self.bot.send_message(
                        chat_id=user_id,
                        text=message_text,
                        parse_mode="HTML"
                    )
                    
                    # Сохраняем информацию об отправленном уведомлении
                    await self.db.add_notification(
                        user_id=user_id,
                        doctor_id=appointment['id'],
                        date=appointment['date'],
                        notification_type='new_appointment',
                        message_text=message_text
                    )
                    
                    logger.info(
                        f"Уведомление отправлено пользователю {user_id}: "
                        f"{appointment['display_name']}, {appointment['date']}"
                    )
                    
                except Exception as e:
                    logger.error(
                        f"Ошибка при отправке уведомления пользователю {user_id}: {e}"
                    )
    
    async def notify_stats(self, user_id: int, stats: Dict[str, Any]):
        """
        Отправить статистику конкретному пользователю
        
        Args:
            user_id: ID пользователя
            stats: Статистика по отделениям
        """
        try:
            message_text = self.formatter.format_stats(stats)
            await self.bot.send_message(
                chat_id=user_id,
                text=message_text,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке статистики пользователю {user_id}: {e}")
