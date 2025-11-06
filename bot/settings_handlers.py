import logging
import re
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.db import Database

logger = logging.getLogger(__name__)

# Создаем роутер для настроек
settings_router = Router()


class SettingsStates(StatesGroup):
    """Состояния для настройки профиля"""
    waiting_for_policy = State()
    waiting_for_birthday = State()
    waiting_for_interval = State()
    waiting_for_period = State()


class SettingsHandlers:
    """Обработчики команд настроек"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def register_handlers(self, router: Router):
        """Регистрация обработчиков настроек"""
        
        @router.message(Command("settings"))
        async def cmd_settings(message: Message):
            """Показать текущие настройки"""
            user_id = message.from_user.id
            settings = await self.db.get_user_settings(user_id)
            
            if not settings:
                await message.answer(
                    "⚙️ <b>Настройки не найдены</b>\n\n"
                    "Используйте /setup для первоначальной настройки.",
                    parse_mode="HTML"
                )
                return
            
            # Форматируем настройки
            policy_text = settings['patient_number'] or "❌ Не указан"
            birthday_text = settings['patient_birthday'] or "❌ Не указана"
            interval_text = f"{settings['check_interval_minutes']} минут"
            period_text = f"{settings['filter_period_days']} дней"
            
            await message.answer(
                "⚙️ <b>Ваши настройки:</b>\n\n"
                f"📋 <b>Номер полиса:</b> {policy_text}\n"
                f"🎂 <b>Дата рождения:</b> {birthday_text}\n"
                f"⏱ <b>Частота проверки:</b> {interval_text}\n"
                f"📅 <b>Период фильтрации:</b> {period_text}\n\n"
                "<b>Команды для изменения:</b>\n"
                "/setpolicy - Изменить номер полиса\n"
                "/setbirthday - Изменить дату рождения\n"
                "/setinterval - Изменить частоту проверки\n"
                "/setperiod - Изменить период фильтрации",
                parse_mode="HTML"
            )
        
        @router.message(Command("setup"))
        async def cmd_setup(message: Message, state: FSMContext):
            """Первоначальная настройка профиля"""
            await message.answer(
                "🔧 <b>Настройка профиля</b>\n\n"
                "Для начала работы необходимо указать данные вашего полиса ОМС.\n\n"
                "📋 Введите <b>номер полиса</b> (16 цифр):",
                parse_mode="HTML"
            )
            await state.set_state(SettingsStates.waiting_for_policy)
        
        @router.message(SettingsStates.waiting_for_policy)
        async def process_policy(message: Message, state: FSMContext):
            """Обработка ввода номера полиса"""
            policy = message.text.strip().replace(" ", "")
            
            # Проверка формата (16 цифр)
            if not re.match(r'^\d{16}$', policy):
                await message.answer(
                    "❌ Неверный формат номера полиса.\n\n"
                    "Номер полиса должен содержать 16 цифр.\n"
                    "Попробуйте еще раз:",
                    parse_mode="HTML"
                )
                return
            
            # Сохраняем во временном состоянии
            await state.update_data(policy=policy)
            
            await message.answer(
                "✅ Номер полиса сохранен!\n\n"
                "🎂 Теперь введите <b>дату рождения</b> в формате ГГГГ-ММ-ДД\n"
                "Например: 2005-06-21",
                parse_mode="HTML"
            )
            await state.set_state(SettingsStates.waiting_for_birthday)
        
        @router.message(SettingsStates.waiting_for_birthday)
        async def process_birthday(message: Message, state: FSMContext):
            """Обработка ввода даты рождения"""
            birthday = message.text.strip()
            
            # Проверка формата ГГГГ-ММ-ДД
            if not re.match(r'^\d{4}-\d{2}-\d{2}$', birthday):
                await message.answer(
                    "❌ Неверный формат даты.\n\n"
                    "Дата должна быть в формате ГГГГ-ММ-ДД\n"
                    "Например: 2005-06-21\n\n"
                    "Попробуйте еще раз:",
                    parse_mode="HTML"
                )
                return
            
            # Получаем сохраненный полис
            data = await state.get_data()
            policy = data.get('policy')
            
            # Сохраняем в БД
            await self.db.update_patient_info(message.from_user.id, policy, birthday)
            
            await message.answer(
                "✅ <b>Настройка завершена!</b>\n\n"
                f"📋 Полис: {policy}\n"
                f"🎂 Дата рождения: {birthday}\n"
                f"⏱ Частота проверки: 5 минут (по умолчанию)\n"
                f"📅 Период фильтрации: 7 дней (по умолчанию)\n\n"
                "Используйте /settings для просмотра и изменения настроек.\n"
                "Используйте /check для проверки записей.",
                parse_mode="HTML"
            )
            await state.clear()
            
            logger.info(f"Пользователь {message.from_user.id} завершил первоначальную настройку")
        
        @router.message(Command("setpolicy"))
        async def cmd_set_policy(message: Message, state: FSMContext):
            """Изменить номер полиса"""
            await message.answer(
                "📋 Введите новый <b>номер полиса</b> (16 цифр):",
                parse_mode="HTML"
            )
            await state.set_state(SettingsStates.waiting_for_policy)
        
        @router.message(Command("setbirthday"))
        async def cmd_set_birthday(message: Message, state: FSMContext):
            """Изменить дату рождения"""
            settings = await self.db.get_user_settings(message.from_user.id)
            
            if not settings or not settings['patient_number']:
                await message.answer(
                    "❌ Сначала укажите номер полиса командой /setpolicy",
                    parse_mode="HTML"
                )
                return
            
            # Сохраняем текущий полис
            await state.update_data(policy=settings['patient_number'])
            
            await message.answer(
                "🎂 Введите новую <b>дату рождения</b> в формате ГГГГ-ММ-ДД:",
                parse_mode="HTML"
            )
            await state.set_state(SettingsStates.waiting_for_birthday)
        
        @router.message(Command("setinterval"))
        async def cmd_set_interval(message: Message, state: FSMContext):
            """Изменить частоту проверки"""
            await message.answer(
                "⏱ <b>Настройка частоты проверки</b>\n\n"
                "Введите интервал проверки в минутах.\n\n"
                "📊 Допустимые значения:\n"
                "• Минимум: 5 минут\n"
                "• Максимум: 1440 минут (24 часа)\n\n"
                "Например: 10, 30, 60, 180",
                parse_mode="HTML"
            )
            await state.set_state(SettingsStates.waiting_for_interval)
        
        @router.message(SettingsStates.waiting_for_interval)
        async def process_interval(message: Message, state: FSMContext):
            """Обработка ввода интервала"""
            try:
                interval = int(message.text.strip())
                
                if interval < 5 or interval > 1440:
                    await message.answer(
                        "❌ Неверное значение.\n\n"
                        "Интервал должен быть от 5 до 1440 минут.\n"
                        "Попробуйте еще раз:",
                        parse_mode="HTML"
                    )
                    return
                
                await self.db.update_check_interval(message.from_user.id, interval)
                
                # Форматируем вывод
                if interval < 60:
                    interval_text = f"{interval} минут"
                else:
                    hours = interval // 60
                    minutes = interval % 60
                    if minutes == 0:
                        interval_text = f"{hours} ч"
                    else:
                        interval_text = f"{hours} ч {minutes} мин"
                
                await message.answer(
                    f"✅ Частота проверки изменена на <b>{interval_text}</b>",
                    parse_mode="HTML"
                )
                await state.clear()
                
                logger.info(f"Пользователь {message.from_user.id} изменил интервал на {interval} минут")
                
            except ValueError:
                await message.answer(
                    "❌ Введите число.\n\nНапример: 10",
                    parse_mode="HTML"
                )
        
        @router.message(Command("setperiod"))
        async def cmd_set_period(message: Message, state: FSMContext):
            """Изменить период фильтрации"""
            await message.answer(
                "📅 <b>Настройка периода фильтрации</b>\n\n"
                "Укажите за сколько дней вперед показывать появившиеся записи.\n\n"
                "Это позволит фильтровать записи, которые появились не потому что кто-то отказался, "
                "а просто потому что стал доступен новый день в расписании.\n\n"
                "📊 Допустимые значения:\n"
                "• Минимум: 1 день\n"
                "• Максимум: 30 дней\n\n"
                "Рекомендуется: 3-7 дней\n\n"
                "Введите количество дней:",
                parse_mode="HTML"
            )
            await state.set_state(SettingsStates.waiting_for_period)
        
        @router.message(SettingsStates.waiting_for_period)
        async def process_period(message: Message, state: FSMContext):
            """Обработка ввода периода"""
            try:
                period = int(message.text.strip())
                
                if period < 1 or period > 30:
                    await message.answer(
                        "❌ Неверное значение.\n\n"
                        "Период должен быть от 1 до 30 дней.\n"
                        "Попробуйте еще раз:",
                        parse_mode="HTML"
                    )
                    return
                
                await self.db.update_filter_period(message.from_user.id, period)
                
                await message.answer(
                    f"✅ Период фильтрации изменен на <b>{period} дней</b>\n\n"
                    f"Теперь вы будете получать уведомления только о записях на ближайшие {period} дней.",
                    parse_mode="HTML"
                )
                await state.clear()
                
                logger.info(f"Пользователь {message.from_user.id} изменил период фильтрации на {period} дней")
                
            except ValueError:
                await message.answer(
                    "❌ Введите число.\n\nНапример: 7",
                    parse_mode="HTML"
                )
