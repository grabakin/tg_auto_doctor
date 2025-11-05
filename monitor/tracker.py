import logging
from typing import List, Dict, Any, Optional
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
    
    async def manual_check(self) -> Dict[str, Any]:
        """
        Ручная проверка текущего состояния (без учета истории)
        
        Returns:
            Статистика по всем отделениям
        """
        stats = {
            'total_appointments': 0,
            'by_department': {}
        }
        
        all_data = await self.api_client.get_all_departments()
        
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
