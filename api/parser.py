from typing import Dict, Any, List
from datetime import datetime
import logging
from config import Config

logger = logging.getLogger(__name__)


class AppointmentParser:
    """Парсер данных о записях к врачам"""
    
    @staticmethod
    def parse_doctor_data(doctor: Dict[str, Any], lpu: Dict[str, Any], department_id: int) -> Dict[str, Any]:
        """
        Парсинг данных врача/кабинета
        
        Args:
            doctor: Данные о враче из API
            lpu: Данные о медучреждении
            department_id: ID отделения
            
        Returns:
            Словарь с обработанными данными
        """
        return {
            'id': doctor.get('id'),
            'department_id': department_id,
            'display_name': doctor.get('displayName', 'Неизвестно'),
            'person_id': doctor.get('person_id'),
            'position': doctor.get('position'),
            'position_code': doctor.get('positionCode'),
            'room': doctor.get('room'),
            'lpu_name': lpu.get('name'),
            'lpu_address': lpu.get('address'),
            'separation': doctor.get('separation'),
            'type': doctor.get('type'),
            'type_name': doctor.get('type_name'),
            'rating': doctor.get('rating'),
            'phone': lpu.get('phone')
        }
    
    @staticmethod
    def parse_schedule_item(schedule_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Парсинг элемента расписания
        
        Args:
            schedule_item: Элемент расписания из API
            
        Returns:
            Обработанные данные расписания
        """
        doc_busy_type = schedule_item.get('docBusyType', {})
        
        return {
            'date': schedule_item.get('date', '').split('T')[0],  # Только дата без времени
            'time_from': schedule_item.get('time_from', ''),
            'time_to': schedule_item.get('time_to', ''),
            'count_tickets': schedule_item.get('count_tickets', 0),
            'doc_busy_type': doc_busy_type.get('name'),
            'doc_busy_type_code': doc_busy_type.get('code')
        }
    
    @staticmethod
    def parse_closest_entry(closest_entry: Dict[str, Any]) -> str:
        """
        Парсинг ближайшей записи
        
        Args:
            closest_entry: Данные о ближайшей записи
            
        Returns:
            Время начала в виде строки
        """
        if closest_entry:
            return closest_entry.get('beginTime', '')
        return ''
    
    @staticmethod
    def extract_available_appointments(api_response: Dict[str, Any], department_id: int) -> List[Dict[str, Any]]:
        """
        Извлечь доступные записи из ответа API
        
        Args:
            api_response: Полный ответ от API
            department_id: ID отделения
            
        Returns:
            Список доступных записей с полной информацией
        """
        available_appointments = []
        
        if not api_response or 'items' not in api_response:
            return available_appointments
        
        for lpu_item in api_response['items']:
            lpu = lpu_item.get('lpu', {})
            doctors = lpu_item.get('doctors', [])
            
            for doctor in doctors:
                # Парсим данные врача
                doctor_info = AppointmentParser.parse_doctor_data(doctor, lpu, department_id)
                
                # Фильтр 1: Белый список врачей (приоритет выше)
                # Если список не пустой - показываем ТОЛЬКО врачей из списка
                if Config.ALLOWED_DOCTORS:
                    if doctor_info.get('display_name') not in Config.ALLOWED_DOCTORS:
                        logger.debug(f"Пропускаем врача (не в белом списке): {doctor_info.get('display_name')}")
                        continue
                
                # Фильтр 2: Исключаем нежелательные специальности (если белый список пустой)
                elif doctor_info.get('position') in Config.EXCLUDED_POSITIONS:
                    logger.debug(f"Пропускаем врача с исключенной специальностью: {doctor_info.get('position')}")
                    continue
                
                # Парсим расписание
                schedule = doctor.get('schedule', [])
                closest_entry = doctor.get('closestEntry')
                
                for schedule_item in schedule:
                    parsed_schedule = AppointmentParser.parse_schedule_item(schedule_item)
                    
                    # Интересуют только дни с доступными талонами
                    if parsed_schedule['count_tickets'] > 0:
                        appointment = {
                            **doctor_info,
                            **parsed_schedule,
                            'closest_entry_time': AppointmentParser.parse_closest_entry(closest_entry)
                        }
                        available_appointments.append(appointment)
                
                # Также добавляем информацию о ближайшей записи, если есть
                if closest_entry:
                    # Проверяем, не добавили ли мы уже эту запись
                    closest_time = AppointmentParser.parse_closest_entry(closest_entry)
                    if closest_time:
                        closest_date = closest_time.split('T')[0]
                        
                        # Ищем, есть ли уже запись на эту дату
                        date_exists = any(
                            apt['date'] == closest_date and apt['id'] == doctor_info['id']
                            for apt in available_appointments
                        )
                        
                        if not date_exists:
                            appointment = {
                                **doctor_info,
                                'date': closest_date,
                                'time_from': closest_time.split('T')[1].split('+')[0] if 'T' in closest_time else '',
                                'time_to': '',
                                'count_tickets': 0,  # Не знаем точное количество
                                'doc_busy_type': 'Ближайшая доступная запись',
                                'doc_busy_type_code': 'closest',
                                'closest_entry_time': closest_time
                            }
                            available_appointments.append(appointment)
        
        logger.info(f"Department {department_id}: найдено {len(available_appointments)} доступных записей")
        return available_appointments
