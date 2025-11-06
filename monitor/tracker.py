import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from database.db import Database
from api.client import ZdravAPIClient
from api.parser import AppointmentParser

logger = logging.getLogger(__name__)


class AppointmentTracker:
    """Отслеживание изменений в доступных записях"""
    
    def __init__(self, db: Database, api_client: ZdravAPIClient):
        self.db = db
        self.api_client = api_client
        self.parser = AppointmentParser()
    
    async def check_for_updates(self) -> List[Dict[str, Any]]:
        """
        Проверить все отделения на наличие новых записей
        
        Returns:
            Список новых/измененных записей
        """
        new_appointments = []
        
        # Получаем данные из API для всех отделений
        all_data = await self.api_client.get_all_departments()
        
        for department_id, api_response in all_data.items():
            if not api_response:
                logger.warning(f"Не удалось получить данные для department {department_id}")
                continue
            
            # Извлекаем доступные записи
            available_appointments = self.parser.extract_available_appointments(
                api_response, department_id
            )
            
            # Проверяем каждую запись на новизну
            for appointment in available_appointments:
                is_new = await self._is_new_or_changed(appointment)
                
                if is_new:
                    new_appointments.append(appointment)
                    logger.info(
                        f"Новая запись: {appointment['display_name']}, "
                        f"дата: {appointment['date']}, талонов: {appointment['count_tickets']}"
                    )
                
                # Сохраняем врача и состояние расписания
                await self._save_appointment_state(appointment)
        
        return new_appointments
    
    async def _is_new_or_changed(self, appointment: Dict[str, Any]) -> bool:
        """
        Проверить, является ли запись новой или измененной
        
        Args:
            appointment: Данные о записи
            
        Returns:
            True если запись новая или изменилась
        """
        doctor_id = appointment['id']
        date = appointment['date']
        
        # Получаем последнее сохраненное состояние
        last_state = await self.db.get_last_schedule_state(doctor_id, date)
        
        # Если записи нет в БД - это новая запись
        if not last_state:
            return True
        
        # Проверяем изменения
        current_tickets = appointment['count_tickets']
        last_tickets = last_state['count_tickets']
        
        # Новые талоны появились
        if current_tickets > 0 and last_tickets == 0:
            return True
        
        # Количество талонов увеличилось (кто-то отказался от записи)
        if current_tickets > last_tickets:
            return True
        
        # Проверяем изменение ближайшей записи
        current_closest = appointment.get('closest_entry_time', '')
        last_closest = last_state.get('closest_entry_time', '')
        
        if current_closest and current_closest != last_closest:
            return True
        
        return False
    
    async def _save_appointment_state(self, appointment: Dict[str, Any]):
        """
        Сохранить текущее состояние записи
        
        Args:
            appointment: Данные о записи
        """
        # Сохраняем информацию о враче
        await self.db.save_doctor(appointment)
        
        # Сохраняем состояние расписания
        schedule_data = {
            'doctor_id': appointment['id'],
            'date': appointment['date'],
            'count_tickets': appointment['count_tickets'],
            'time_from': appointment.get('time_from'),
            'time_to': appointment.get('time_to'),
            'doc_busy_type': appointment.get('doc_busy_type'),
            'closest_entry_time': appointment.get('closest_entry_time')
        }
        
        await self.db.save_schedule_state(schedule_data)
    
    async def manual_check(self, patient_number: str = None, patient_birthday: str = None) -> Dict[str, Any]:
        """
        Ручная проверка текущего состояния (без учета истории)
        
        Args:
            patient_number: Номер полиса (опционально)
            patient_birthday: Дата рождения (опционально)
        
        Returns:
            Статистика по всем отделениям
        """
        stats = {
            'total_appointments': 0,
            'by_department': {}
        }
        
        all_data = await self.api_client.get_all_departments(patient_number, patient_birthday)
        
        for department_id, api_response in all_data.items():
            if not api_response:
                stats['by_department'][department_id] = {
                    'status': 'error',
                    'appointments': []
                }
                continue
            
            appointments = self.parser.extract_available_appointments(
                api_response, department_id
            )
            
            stats['total_appointments'] += len(appointments)
            stats['by_department'][department_id] = {
                'status': 'ok',
                'count': len(appointments),
                'appointments': appointments
            }
        
        return stats
    
    async def check_user_appointments(self, user_id: int, patient_number: str, 
                                     patient_birthday: str, filter_period_days: int) -> List[Dict[str, Any]]:
        """
        Проверить записи для конкретного пользователя с фильтрацией
        
        Args:
            user_id: ID пользователя
            patient_number: Номер полиса пользователя
            patient_birthday: Дата рождения пользователя
            filter_period_days: За сколько дней вперед смотреть записи
            
        Returns:
            Список реально новых записей (не появившихся из-за нового дня)
        """
        new_appointments = []
        
        # Вычисляем максимальную дату для фильтрации
        max_date = (datetime.now() + timedelta(days=filter_period_days)).date()
        
        # Получаем данные из API
        all_data = await self.api_client.get_all_departments(patient_number, patient_birthday)
        
        for department_id, api_response in all_data.items():
            if not api_response:
                continue
            
            # Извлекаем доступные записи
            available_appointments = self.parser.extract_available_appointments(
                api_response, department_id
            )
            
            # Проверяем каждую запись
            for appointment in available_appointments:
                # Фильтр по дате - только записи в пределах периода
                try:
                    apt_date = datetime.strptime(appointment['date'], '%Y-%m-%d').date()
                    if apt_date > max_date:
                        continue  # Пропускаем записи слишком далеко в будущем
                except:
                    continue
                
                # Проверяем, является ли запись реально новой
                is_really_new = await self._is_really_new_appointment(appointment, user_id)
                
                if is_really_new:
                    new_appointments.append(appointment)
                    logger.info(
                        f"Новая запись для пользователя {user_id}: "
                        f"{appointment['display_name']}, дата: {appointment['date']}, "
                        f"талонов: {appointment['count_tickets']}"
                    )
                
                # Сохраняем состояние с привязкой к пользователю
                await self._save_user_appointment_state(appointment, user_id)
        
        return new_appointments
    
    async def _is_really_new_appointment(self, appointment: Dict[str, Any], user_id: int) -> bool:
        """
        Проверить, является ли запись РЕАЛЬНО новой (не просто новый день в расписании)
        
        Args:
            appointment: Данные о записи
            user_id: ID пользователя
            
        Returns:
            True если запись реально новая (кто-то отказался, появились талоны и т.д.)
        """
        doctor_id = appointment['id']
        date = appointment['date']
        
        # Получаем последнее состояние для этого пользователя
        last_state = await self.db.get_last_schedule_state(doctor_id, date)
        
        current_tickets = appointment['count_tickets']
        
        # Если записи никогда не было в БД
        if not last_state:
            # Проверяем дату записи - если это завтрашний или более поздний день,
            # и талонов > 0, то это может быть просто новый день в расписании
            try:
                apt_date = datetime.strptime(date, '%Y-%m-%d').date()
                today = datetime.now().date()
                
                # Если дата записи более чем через 1 день и это первая проверка
                if apt_date > today + timedelta(days=1) and current_tickets > 0:
                    # Это новый день в расписании, не реальная новая запись
                    return False
                
                # Если это завтра или сегодня и есть талоны - это интересно
                if apt_date <= today + timedelta(days=1) and current_tickets > 0:
                    return True
                    
            except:
                pass
            
            # Если есть талоны - считаем новой записью
            return current_tickets > 0
        
        last_tickets = last_state['count_tickets']
        
        # РЕАЛЬНО новая запись - увеличилось количество талонов
        # (кто-то отказался от записи)
        if current_tickets > last_tickets:
            return True
        
        # Талоны появились там, где их не было
        if current_tickets > 0 and last_tickets == 0:
            return True
        
        return False
    
    async def _save_user_appointment_state(self, appointment: Dict[str, Any], user_id: int):
        """
        Сохранить состояние записи для пользователя
        
        Args:
            appointment: Данные о записи
            user_id: ID пользователя
        """
        # Сохраняем информацию о враче (общая для всех)
        await self.db.save_doctor(appointment)
        
        # Сохраняем состояние расписания
        schedule_data = {
            'doctor_id': appointment['id'],
            'date': appointment['date'],
            'count_tickets': appointment['count_tickets'],
            'time_from': appointment.get('time_from'),
            'time_to': appointment.get('time_to'),
            'doc_busy_type': appointment.get('doc_busy_type'),
            'closest_entry_time': appointment.get('closest_entry_time')
        }
        
        await self.db.save_schedule_state(schedule_data)
