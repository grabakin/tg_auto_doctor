import logging
import asyncio
from typing import Callable
from database.db import Database

logger = logging.getLogger(__name__)


class UserScheduler:
    """Планировщик для проверки каждого пользователя по его индивидуальному расписанию"""
    
    def __init__(self, db: Database):
        self.db = db
        self.check_callback = None
        self.is_running = False
        self._task = None
    
    def set_check_callback(self, callback: Callable):
        """
        Установить callback функцию для проверки пользователя
        
        Args:
            callback: Async функция с параметрами (user_id, patient_number, patient_birthday, filter_period_days)
        """
        self.check_callback = callback
    
    async def _check_loop(self):
        """Основной цикл проверки пользователей"""
        logger.info("Планировщик пользователей запущен")
        
        while self.is_running:
            try:
                # Получаем список пользователей, которым пора делать проверку
                users_to_check = await self.db.get_users_to_check()
                
                if users_to_check:
                    logger.info(f"Найдено {len(users_to_check)} пользователей для проверки")
                    
                    # Проверяем каждого пользователя
                    for user in users_to_check:
                        try:
                            if self.check_callback:
                                await self.check_callback(
                                    user['user_id'],
                                    user['patient_number'],
                                    user['patient_birthday'],
                                    user['filter_period_days']
                                )
                                
                                # Обновляем время последней проверки
                                await self.db.update_last_check_time(user['user_id'])
                                
                        except Exception as e:
                            logger.error(
                                f"Ошибка при проверке пользователя {user['user_id']}: {e}",
                                exc_info=True
                            )
                else:
                    logger.debug("Нет пользователей для проверки в данный момент")
                
                # Пауза между циклами проверки (1 минута)
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Ошибка в цикле планировщика: {e}", exc_info=True)
                await asyncio.sleep(60)
    
    def start(self):
        """Запустить планировщик"""
        if not self.check_callback:
            raise ValueError("Callback функция не установлена. Используйте set_check_callback()")
        
        if self.is_running:
            logger.warning("Планировщик уже запущен")
            return
        
        self.is_running = True
        self._task = asyncio.create_task(self._check_loop())
        logger.info("Планировщик пользователей стартовал")
    
    async def stop(self):
        """Остановить планировщик"""
        if not self.is_running:
            return
        
        logger.info("Остановка планировщика пользователей...")
        self.is_running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("Планировщик пользователей остановлен")
    
    async def trigger_user_check(self, user_id: int):
        """
        Запустить проверку для конкретного пользователя немедленно
        
        Args:
            user_id: ID пользователя
        """
        if not self.check_callback:
            logger.error("Callback функция не установлена")
            return
        
        settings = await self.db.get_user_settings(user_id)
        if not settings or not settings['patient_number'] or not settings['patient_birthday']:
            logger.warning(f"У пользователя {user_id} не заполнены настройки")
            return
        
        logger.info(f"Запуск внеплановой проверки для пользователя {user_id}")
        
        try:
            await self.check_callback(
                user_id,
                settings['patient_number'],
                settings['patient_birthday'],
                settings['filter_period_days']
            )
            
            # Обновляем время последней проверки
            await self.db.update_last_check_time(user_id)
            
        except Exception as e:
            logger.error(f"Ошибка при внеплановой проверке пользователя {user_id}: {e}", exc_info=True)
