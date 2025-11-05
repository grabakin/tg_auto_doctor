from typing import Dict, Any, List
from datetime import datetime


class MessageFormatter:
    """Форматирование сообщений для Telegram"""
    
    @staticmethod
    def format_appointment(appointment: Dict[str, Any]) -> str:
        """
        Форматировать информацию о записи для отправки в Telegram
        
        Args:
            appointment: Данные о записи
            
        Returns:
            Отформатированное сообщение
        """
        # Иконки для типов
        type_icon = "👨‍⚕️" if appointment.get('type') == 1 else "🚪"
        
        # Форматируем дату
        try:
            date_obj = datetime.strptime(appointment['date'], '%Y-%m-%d')
            formatted_date = date_obj.strftime('%d.%m.%Y (%A)')
            # Переводим день недели на русский
            days_ru = {
                'Monday': 'Понедельник',
                'Tuesday': 'Вторник', 
                'Wednesday': 'Среда',
                'Thursday': 'Четверг',
                'Friday': 'Пятница',
                'Saturday': 'Суббота',
                'Sunday': 'Воскресенье'
            }
            for en, ru in days_ru.items():
                formatted_date = formatted_date.replace(en, ru)
        except:
            formatted_date = appointment['date']
        
        # Формируем сообщение
        lines = [
            f"🔔 <b>Доступна запись!</b>\n",
            f"{type_icon} <b>{appointment['display_name']}</b>"
        ]
        
        if appointment.get('position'):
            lines.append(f"📋 {appointment['position']}")
        
        lines.append(f"\n📅 <b>Дата:</b> {formatted_date}")
        
        if appointment.get('time_from') and appointment.get('time_to'):
            lines.append(f"🕐 <b>Время:</b> {appointment['time_from']} - {appointment['time_to']}")
        elif appointment.get('time_from'):
            lines.append(f"🕐 <b>Время от:</b> {appointment['time_from']}")
        
        if appointment.get('count_tickets') > 0:
            lines.append(f"🎫 <b>Талонов:</b> {appointment['count_tickets']}")
        
        if appointment.get('closest_entry_time'):
            try:
                closest_dt = datetime.fromisoformat(appointment['closest_entry_time'].replace('+03:00', ''))
                closest_formatted = closest_dt.strftime('%d.%m.%Y %H:%M')
                lines.append(f"⏰ <b>Ближайшая запись:</b> {closest_formatted}")
            except:
                pass
        
        if appointment.get('room'):
            lines.append(f"🏥 <b>Кабинет:</b> {appointment['room']}")
        
        if appointment.get('lpu_name'):
            lines.append(f"\n🏛 <b>{appointment['lpu_name']}</b>")
        
        if appointment.get('lpu_address'):
            lines.append(f"📍 {appointment['lpu_address']}")
        
        if appointment.get('separation'):
            lines.append(f"🏢 {appointment['separation']}")
        
        if appointment.get('phone'):
            lines.append(f"📞 {appointment['phone']}")
        
        return '\n'.join(lines)
    
    @staticmethod
    def format_stats(stats: Dict[str, Any]) -> str:
        """
        Форматировать статистику для отображения
        
        Args:
            stats: Статистика по отделениям
            
        Returns:
            Отформатированное сообщение
        """
        lines = [
            "📊 <b>Статистика доступных записей</b>\n",
            f"<b>Всего найдено:</b> {stats['total_appointments']} записей\n"
        ]
        
        for dept_id, dept_data in stats['by_department'].items():
            if dept_data['status'] == 'error':
                lines.append(f"❌ <b>Отделение {dept_id}:</b> Ошибка получения данных")
            else:
                count = dept_data['count']
                lines.append(f"✅ <b>Отделение {dept_id}:</b> {count} записей")
                
                # Показываем врачей с доступными талонами
                if count > 0:
                    doctors_set = set()
                    for apt in dept_data['appointments']:
                        if apt['count_tickets'] > 0:
                            doctors_set.add(apt['display_name'])
                    
                    if doctors_set:
                        lines.append(f"   <i>Врачи: {', '.join(list(doctors_set)[:3])}" + 
                                   (f" и ещё {len(doctors_set)-3}" if len(doctors_set) > 3 else "") + "</i>")
        
        return '\n'.join(lines)
    
    @staticmethod
    def format_welcome() -> str:
        """Приветственное сообщение"""
        return (
            "👋 <b>Добро пожаловать в бот мониторинга записей к врачам!</b>\n\n"
            "Я буду отслеживать появление новых талонов на запись и сразу сообщу вам.\n\n"
            "📋 <b>Доступные команды:</b>\n"
            "/start - Включить уведомления\n"
            "/stop - Выключить уведомления\n"
            "/status - Статус мониторинга\n"
            "/check - Проверить записи сейчас\n\n"
            "✅ Уведомления включены!"
        )
    
    @staticmethod
    def format_access_denied() -> str:
        """Сообщение об отказе в доступе"""
        return (
            "⛔️ <b>Доступ запрещен</b>\n\n"
            "К сожалению, у вас нет доступа к этому боту.\n"
            "Обратитесь к администратору для получения доступа."
        )
    
    @staticmethod
    def format_notifications_disabled() -> str:
        """Сообщение об отключении уведомлений"""
        return (
            "🔕 <b>Уведомления отключены</b>\n\n"
            "Вы больше не будете получать уведомления о новых записях.\n"
            "Используйте /start чтобы включить их снова."
        )
    
    @staticmethod
    def format_status(is_active: bool, check_interval: int) -> str:
        """Форматировать статус бота"""
        status_icon = "✅" if is_active else "⏸"
        status_text = "активен" if is_active else "приостановлен"
        
        return (
            f"{status_icon} <b>Статус мониторинга: {status_text}</b>\n\n"
            f"⏱ <b>Интервал проверки:</b> {check_interval} минут\n"
            f"📍 <b>Отслеживаемые отделения:</b> департаменты из конфига\n\n"
            "Используйте /check для ручной проверки записей."
        )
    
    @staticmethod
    def format_check_results(stats: Dict[str, Any]) -> str:
        """
        Форматировать результаты проверки с ближайшими записями
        
        Args:
            stats: Статистика по отделениям
            
        Returns:
            Отформатированное сообщение
        """
        total = stats['total_appointments']
        
        # Собираем все записи
        all_appointments = []
        for dept_data in stats['by_department'].values():
            if dept_data['status'] == 'ok':
                all_appointments.extend(dept_data['appointments'])
        
        if not all_appointments:
            return (
                "❌ <b>Доступных записей не найдено</b>\n\n"
                "На данный момент нет свободных талонов в отслеживаемых отделениях."
            )
        
        # Сортируем по дате (ближайшие первыми)
        all_appointments.sort(key=lambda x: (x['date'], x.get('time_from', '')))
        
        # Берем только записи с талонами > 0
        with_tickets = [apt for apt in all_appointments if apt['count_tickets'] > 0]
        
        if not with_tickets:
            # Показываем самую ближайшую запись даже если талонов 0
            closest = all_appointments[0]
        else:
            closest = with_tickets[0]
        
        # Форматируем дату
        try:
            date_obj = datetime.strptime(closest['date'], '%Y-%m-%d')
            formatted_date = date_obj.strftime('%d.%m.%Y')
            day_name = date_obj.strftime('%A')
            days_ru = {
                'Monday': 'Пн',
                'Tuesday': 'Вт', 
                'Wednesday': 'Ср',
                'Thursday': 'Чт',
                'Friday': 'Пт',
                'Saturday': 'Сб',
                'Sunday': 'Вс'
            }
            day_ru = days_ru.get(day_name, day_name)
            formatted_date = f"{formatted_date} ({day_ru})"
        except:
            formatted_date = closest['date']
        
        # Формируем сообщение
        lines = [
            f"✅ <b>Найдено: {total} записей</b>\n",
            "🔔 <b>Ближайшая запись:</b>\n"
        ]
        
        # Врач/кабинет
        type_icon = "👨‍⚕️" if closest.get('type') == 1 else "🚪"
        lines.append(f"{type_icon} <b>{closest['display_name']}</b>")
        
        if closest.get('position'):
            lines.append(f"📋 {closest['position']}")
        
        # Дата и время
        lines.append(f"\n📅 <b>Дата:</b> {formatted_date}")
        
        if closest.get('time_from'):
            if closest.get('time_to'):
                lines.append(f"🕐 <b>Время:</b> {closest['time_from']} - {closest['time_to']}")
            else:
                lines.append(f"🕐 <b>Время:</b> от {closest['time_from']}")
        
        # Талоны
        if closest['count_tickets'] > 0:
            lines.append(f"🎫 <b>Талонов:</b> {closest['count_tickets']}")
        
        # Адрес
        if closest.get('lpu_name'):
            lines.append(f"\n🏛 {closest['lpu_name']}")
        if closest.get('lpu_address'):
            lines.append(f"📍 {closest['lpu_address']}")
        
        return '\n'.join(lines)
