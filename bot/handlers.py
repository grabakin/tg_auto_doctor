import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from database.db import Database
from monitor.scheduler import MonitorScheduler
from monitor.tracker import AppointmentTracker
from utils.formatter import MessageFormatter
from config import Config

logger = logging.getLogger(__name__)

# Создаем роутер для обработчиков
router = Router()


class BotHandlers:
    """Обработчики команд бота"""
    
    def __init__(self, db: Database, scheduler: MonitorScheduler, tracker: AppointmentTracker):
        self.db = db
        self.scheduler = scheduler
        self.tracker = tracker
        self.formatter = MessageFormatter()
    
    def register_handlers(self, router: Router):
        """Регистрация всех обработчиков"""
        
        @router.message(Command("start"))
        async def cmd_start(message: Message):
            """Команда /start - включение уведомлений"""
            user = message.from_user
            
            # Добавляем пользователя в БД
            await self.db.add_user(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name
            )
            
            # Включаем уведомления
            await self.db.set_notifications(user.id, True)
            
            logger.info(f"Пользователь {user.id} ({user.username}) активировал бота")
            
            await message.answer(
                self.formatter.format_welcome(),
                parse_mode="HTML"
            )
        
        @router.message(Command("stop"))
        async def cmd_stop(message: Message):
            """Команда /stop - отключение уведомлений"""
            user_id = message.from_user.id
            
            # Отключаем уведомления
            await self.db.set_notifications(user_id, False)
            
            logger.info(f"Пользователь {user_id} отключил уведомления")
            
            await message.answer(
                self.formatter.format_notifications_disabled(),
                parse_mode="HTML"
            )
        
        @router.message(Command("status"))
        async def cmd_status(message: Message):
            """Команда /status - текущий статус"""
            user_id = message.from_user.id
            
            is_active = await self.db.is_user_active(user_id)
            
            await message.answer(
                self.formatter.format_status(is_active, Config.CHECK_INTERVAL),
                parse_mode="HTML"
            )
        
        @router.message(Command("check"))
        async def cmd_check(message: Message):
            """Команда /check - ручная проверка записей"""
            user_id = message.from_user.id
            
            # Получаем настройки пользователя
            settings = await self.db.get_user_settings(user_id)
            
            if not settings or not settings['patient_number'] or not settings['patient_birthday']:
                await message.answer(
                    "⚠️ <b>Настройки не заполнены</b>\n\n"
                    "Сначала настройте свой профиль командой /setup",
                    parse_mode="HTML"
                )
                return
            
            await message.answer("🔄 Проверяю доступные записи...")
            
            # Выполняем ручную проверку с персональными данными
            stats = await self.tracker.manual_check(
                settings['patient_number'],
                settings['patient_birthday']
            )
            
            # Форматируем и отправляем результаты с ближайшей записью
            result_message = self.formatter.format_check_results(stats)
            await message.answer(result_message, parse_mode="HTML")
            
            logger.info(f"Пользователь {user_id} запустил ручную проверку")
        
        @router.message(Command("help"))
        async def cmd_help(message: Message):
            """Команда /help - показать список команд"""
            await message.answer(
                "<b>📋 Основные команды:</b>\n"
                "/start - Включить уведомления\n"
                "/stop - Выключить уведомления\n"
                "/check - Проверить записи\n"
                "/status - Статус мониторинга\n"
                "/help - Показать команды\n\n"
                "<b>⚙️ Настройки:</b>\n"
                "/setup - Первоначальная настройка\n"
                "/settings - Посмотреть настройки\n"
                "/setpolicy - Изменить полис\n"
                "/setbirthday - Изменить дату рождения\n"
                "/setinterval - Изменить частоту\n"
                "/setperiod - Изменить период фильтрации",
                parse_mode="HTML"
            )
