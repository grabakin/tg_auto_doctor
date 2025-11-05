import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import Config
from database.db import Database
from api.client import ZdravAPIClient
from monitor.tracker import AppointmentTracker
from monitor.scheduler import MonitorScheduler
from bot.handlers import BotHandlers, router
from bot.middlewares import WhitelistMiddleware
from bot.notifier import NotificationService

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


class DoctorNotificationBot:
    """Главный класс бота для мониторинга записей к врачам"""
    
    def __init__(self):
        # Валидация конфигурации
        try:
            Config.validate()
        except ValueError as e:
            logger.error(f"Ошибка конфигурации: {e}")
            sys.exit(1)
        
        # Инициализация компонентов
        self.bot = Bot(
            token=Config.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        self.dp = Dispatcher()
        self.db = Database(Config.DATABASE_PATH)
        self.api_client = ZdravAPIClient()
        self.tracker = AppointmentTracker(self.db, self.api_client)
        self.scheduler = MonitorScheduler()
        self.notifier = NotificationService(self.bot, self.db)
        
        # Регистрация middleware для проверки белого списка
        self.dp.message.middleware(WhitelistMiddleware())
        
        # Регистрация обработчиков
        handlers = BotHandlers(self.db, self.scheduler, self.tracker)
        handlers.register_handlers(router)
        self.dp.include_router(router)
        
        logger.info("Бот инициализирован")
    
    async def check_appointments_callback(self):
        """
        Callback функция для периодической проверки записей
        Вызывается планировщиком
        """
        try:
            logger.info("Начинаем проверку новых записей...")
            
            # Проверяем наличие новых записей
            new_appointments = await self.tracker.check_for_updates()
            
            if new_appointments:
                logger.info(f"Найдено {len(new_appointments)} новых записей")
                
                # Отправляем уведомления
                await self.notifier.notify_new_appointments(new_appointments)
            else:
                logger.info("Новых записей не найдено")
                
        except Exception as e:
            logger.error(f"Ошибка при проверке записей: {e}", exc_info=True)
    
    async def on_startup(self):
        """Действия при запуске бота"""
        logger.info("Запуск бота...")
        
        # Инициализация базы данных
        await self.db.init_db()
        logger.info("База данных инициализирована")
        
        # Настройка планировщика
        self.scheduler.set_check_callback(self.check_appointments_callback)
        self.scheduler.start()
        logger.info(f"Планировщик запущен с интервалом {Config.CHECK_INTERVAL} минут")
        
        # Выполняем первую проверку сразу
        logger.info("Выполняем первую проверку...")
        await self.check_appointments_callback()
        
        logger.info(f"Бот успешно запущен! Мониторинг отделений: {Config.DEPARTMENT_IDS}")
        logger.info(f"Пользователей в белом списке: {len(Config.WHITELIST_USER_IDS)}")
    
    async def on_shutdown(self):
        """Действия при остановке бота"""
        logger.info("Остановка бота...")
        
        # Останавливаем планировщик
        self.scheduler.stop()
        
        # Закрываем бота
        await self.bot.session.close()
        
        logger.info("Бот остановлен")
    
    async def start(self):
        """Запустить бота"""
        try:
            await self.on_startup()
            
            # Запускаем polling
            await self.dp.start_polling(self.bot)
            
        except Exception as e:
            logger.error(f"Критическая ошибка: {e}", exc_info=True)
        finally:
            await self.on_shutdown()


async def main():
    """Точка входа в приложение"""
    bot = DoctorNotificationBot()
    await bot.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}", exc_info=True)
        sys.exit(1)
