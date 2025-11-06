import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import Config
from database.db import Database
from api.client import ZdravAPIClient
from monitor.tracker import AppointmentTracker
from monitor.user_scheduler import UserScheduler
from bot.handlers import BotHandlers, router
from bot.settings_handlers import SettingsHandlers, settings_router
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
        # Валидация конфигурации (теперь без обязательных PATIENT_NUMBER и PATIENT_BIRTHDAY)
        try:
            if not Config.BOT_TOKEN:
                raise ValueError("BOT_TOKEN не установлен в .env файле")
            if not Config.WHITELIST_USER_IDS:
                raise ValueError("WHITELIST_USER_IDS не установлен в .env файле")
        except ValueError as e:
            logger.error(f"Ошибка конфигурации: {e}")
            sys.exit(1)
        
        # Инициализация компонентов
        self.bot = Bot(
            token=Config.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        # Используем MemoryStorage для FSM (состояния настроек)
        self.dp = Dispatcher(storage=MemoryStorage())
        self.db = Database(Config.DATABASE_PATH)
        self.api_client = ZdravAPIClient()
        self.tracker = AppointmentTracker(self.db, self.api_client)
        self.scheduler = UserScheduler(self.db)
        self.notifier = NotificationService(self.bot, self.db)
        
        # Регистрация middleware для проверки белого списка
        self.dp.message.middleware(WhitelistMiddleware())
        
        # ВАЖНО: Регистрация обработчиков настроек ПЕРВЫМИ
        # Они должны быть приоритетнее основных обработчиков
        settings_handlers = SettingsHandlers(self.db)
        settings_handlers.register_handlers(settings_router)
        self.dp.include_router(settings_router)
        
        # Регистрация основных обработчиков
        handlers = BotHandlers(self.db, self.scheduler, self.tracker)
        handlers.register_handlers(router)
        self.dp.include_router(router)
        
        logger.info("Бот инициализирован")
    
    async def check_user_appointments_callback(self, user_id: int, patient_number: str, 
                                              patient_birthday: str, filter_period_days: int):
        """
        Callback функция для проверки записей конкретного пользователя
        Вызывается планировщиком для каждого пользователя индивидуально
        
        Args:
            user_id: ID пользователя
            patient_number: Номер полиса пользователя
            patient_birthday: Дата рождения пользователя
            filter_period_days: Период фильтрации в днях
        """
        try:
            logger.info(f"Проверка записей для пользователя {user_id}")
            
            # Проверяем наличие новых записей для пользователя
            new_appointments = await self.tracker.check_user_appointments(
                user_id,
                patient_number,
                patient_birthday,
                filter_period_days
            )
            
            if new_appointments:
                logger.info(f"Найдено {len(new_appointments)} новых записей для пользователя {user_id}")
                
                # Отправляем уведомления конкретному пользователю
                for appointment in new_appointments:
                    try:
                        # Проверяем, не отправляли ли уже
                        was_sent = await self.db.was_notified(
                            user_id=user_id,
                            doctor_id=appointment['id'],
                            date=appointment['date'],
                            notification_type='new_appointment',
                            hours=24
                        )
                        
                        if was_sent:
                            continue
                        
                        # Форматируем и отправляем сообщение
                        from utils.formatter import MessageFormatter
                        formatter = MessageFormatter()
                        message_text = formatter.format_appointment(appointment)
                        
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
                        
                        logger.info(f"Уведомление отправлено пользователю {user_id}: {appointment['display_name']}")
                        
                    except Exception as e:
                        logger.error(f"Ошибка при отправке уведомления пользователю {user_id}: {e}")
            else:
                logger.debug(f"Новых записей для пользователя {user_id} не найдено")
                
        except Exception as e:
            logger.error(f"Ошибка при проверке записей для пользователя {user_id}: {e}", exc_info=True)
    
    async def on_startup(self):
        """Действия при запуске бота"""
        logger.info("Запуск бота...")
        
        # Инициализация базы данных
        await self.db.init_db()
        logger.info("База данных инициализирована")
        
        # Настройка планировщика для персональных проверок
        self.scheduler.set_check_callback(self.check_user_appointments_callback)
        self.scheduler.start()
        logger.info("Планировщик персональных проверок запущен")
        
        logger.info(f"Бот успешно запущен! Мониторинг отделений: {Config.DEPARTMENT_IDS}")
        logger.info(f"Пользователей в белом списке: {len(Config.WHITELIST_USER_IDS)}")
    
    async def on_shutdown(self):
        """Действия при остановке бота"""
        logger.info("Остановка бота...")
        
        # Останавливаем планировщик
        await self.scheduler.stop()
        
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
