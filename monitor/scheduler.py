import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from typing import Callable
from config import Config

logger = logging.getLogger(__name__)


class MonitorScheduler:
    """Планировщик для периодической проверки API"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.check_callback = None
    
    def set_check_callback(self, callback: Callable):
        """
        Установить callback функцию для проверки
        
        Args:
            callback: Async функция, которая будет вызываться периодически
        """
        self.check_callback = callback
    
    def start(self):
        """Запустить планировщик"""
        if not self.check_callback:
            raise ValueError("Callback функция не установлена. Используйте set_check_callback()")
        
        # Добавляем задачу на периодическое выполнение
        self.scheduler.add_job(
            self.check_callback,
            trigger=IntervalTrigger(minutes=Config.CHECK_INTERVAL),
            id='check_appointments',
            name='Проверка доступных записей',
            replace_existing=True
        )
        
        logger.info(f"Планировщик запущен. Интервал проверки: {Config.CHECK_INTERVAL} минут")
        self.scheduler.start()
    
    def stop(self):
        """Остановить планировщик"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Планировщик остановлен")
    
    def is_running(self) -> bool:
        """Проверить, работает ли планировщик"""
        return self.scheduler.running
    
    async def trigger_now(self):
        """Запустить проверку немедленно"""
        if self.check_callback:
            logger.info("Запуск внеплановой проверки")
            await self.check_callback()
        else:
            logger.error("Callback функция не установлена")
