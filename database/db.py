import aiosqlite
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


class Database:
    """Класс для работы с SQLite базой данных"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        
    async def init_db(self):
        """Инициализация базы данных и создание таблиц"""
        async with aiosqlite.connect(self.db_path) as db:
            # Таблица пользователей (белый список)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    is_notifications_enabled BOOLEAN DEFAULT 1,
                    patient_number TEXT,
                    patient_birthday TEXT,
                    check_interval_minutes INTEGER DEFAULT 5,
                    filter_period_days INTEGER DEFAULT 7,
                    last_check_time TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица врачей/кабинетов
            await db.execute("""
                CREATE TABLE IF NOT EXISTS doctors (
                    id TEXT PRIMARY KEY,
                    department_id INTEGER NOT NULL,
                    display_name TEXT NOT NULL,
                    person_id TEXT,
                    position TEXT,
                    position_code TEXT,
                    room TEXT,
                    lpu_name TEXT,
                    lpu_address TEXT,
                    separation TEXT,
                    type INTEGER,
                    type_name TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица состояний расписания (для отслеживания изменений)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS schedule_state (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doctor_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    count_tickets INTEGER NOT NULL,
                    time_from TEXT,
                    time_to TEXT,
                    doc_busy_type TEXT,
                    closest_entry_time TEXT,
                    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (doctor_id) REFERENCES doctors(id)
                )
            """)
            
            # Таблица отправленных уведомлений (чтобы не дублировать)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    doctor_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    notification_type TEXT NOT NULL,
                    message_text TEXT,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    FOREIGN KEY (doctor_id) REFERENCES doctors(id)
                )
            """)
            
            # Индексы для быстрого поиска
            await db.execute("CREATE INDEX IF NOT EXISTS idx_schedule_doctor_date ON schedule_state(doctor_id, date)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, sent_at)")
            
            await db.commit()
            logger.info("База данных инициализирована")
    
    async def add_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None):
        """Добавить или обновить пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO users (user_id, username, first_name, last_name, last_activity)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    last_name = excluded.last_name,
                    last_activity = CURRENT_TIMESTAMP
            """, (user_id, username, first_name, last_name))
            await db.commit()
    
    async def is_user_active(self, user_id: int) -> bool:
        """Проверить, активен ли пользователь"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT is_active, is_notifications_enabled FROM users WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return bool(row and row[0] and row[1]) if row else False
    
    async def set_notifications(self, user_id: int, enabled: bool):
        """Включить/выключить уведомления для пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET is_notifications_enabled = ? WHERE user_id = ?",
                (enabled, user_id)
            )
            await db.commit()
    
    async def get_active_users(self) -> List[int]:
        """Получить список активных пользователей с включенными уведомлениями"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT user_id FROM users WHERE is_active = 1 AND is_notifications_enabled = 1"
            ) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
    
    async def save_doctor(self, doctor_data: Dict[str, Any]):
        """Сохранить или обновить информацию о враче/кабинете"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO doctors (
                    id, department_id, display_name, person_id, position, position_code,
                    room, lpu_name, lpu_address, separation, type, type_name, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    display_name = excluded.display_name,
                    room = excluded.room,
                    last_updated = CURRENT_TIMESTAMP
            """, (
                doctor_data['id'],
                doctor_data['department_id'],
                doctor_data['display_name'],
                doctor_data.get('person_id'),
                doctor_data.get('position'),
                doctor_data.get('position_code'),
                doctor_data.get('room'),
                doctor_data.get('lpu_name'),
                doctor_data.get('lpu_address'),
                doctor_data.get('separation'),
                doctor_data.get('type'),
                doctor_data.get('type_name')
            ))
            await db.commit()
    
    async def get_last_schedule_state(self, doctor_id: str, date: str) -> Optional[Dict[str, Any]]:
        """Получить последнее состояние расписания для врача на дату"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM schedule_state
                WHERE doctor_id = ? AND date = ?
                ORDER BY checked_at DESC LIMIT 1
            """, (doctor_id, date)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
    
    async def save_schedule_state(self, schedule_data: Dict[str, Any]):
        """Сохранить текущее состояние расписания"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO schedule_state (
                    doctor_id, date, count_tickets, time_from, time_to,
                    doc_busy_type, closest_entry_time, checked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                schedule_data['doctor_id'],
                schedule_data['date'],
                schedule_data['count_tickets'],
                schedule_data.get('time_from'),
                schedule_data.get('time_to'),
                schedule_data.get('doc_busy_type'),
                schedule_data.get('closest_entry_time')
            ))
            await db.commit()
    
    async def add_notification(self, user_id: int, doctor_id: str, date: str, 
                              notification_type: str, message_text: str):
        """Сохранить информацию об отправленном уведомлении"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO notifications (
                    user_id, doctor_id, date, notification_type, message_text, sent_at
                ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (user_id, doctor_id, date, notification_type, message_text))
            await db.commit()
    
    async def was_notified(self, user_id: int, doctor_id: str, date: str, 
                          notification_type: str, hours: int = 24) -> bool:
        """Проверить, было ли отправлено уведомление за последние N часов"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT COUNT(*) FROM notifications
                WHERE user_id = ? AND doctor_id = ? AND date = ? 
                AND notification_type = ?
                AND sent_at > datetime('now', '-' || ? || ' hours')
            """, (user_id, doctor_id, date, notification_type, hours)) as cursor:
                row = await cursor.fetchone()
                return row[0] > 0 if row else False
    
    # Методы для персональных настроек пользователей
    
    async def get_user_settings(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получить настройки пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT patient_number, patient_birthday, check_interval_minutes, 
                       filter_period_days, last_check_time
                FROM users WHERE user_id = ?
            """, (user_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
    
    async def update_patient_info(self, user_id: int, patient_number: str, patient_birthday: str):
        """Обновить данные полиса пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE users 
                SET patient_number = ?, patient_birthday = ?
                WHERE user_id = ?
            """, (patient_number, patient_birthday, user_id))
            await db.commit()
    
    async def update_check_interval(self, user_id: int, interval_minutes: int):
        """Обновить интервал проверки (5 минут - 1 день)"""
        # Валидация: минимум 5 минут, максимум 1440 минут (24 часа)
        interval_minutes = max(5, min(1440, interval_minutes))
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE users 
                SET check_interval_minutes = ?
                WHERE user_id = ?
            """, (interval_minutes, user_id))
            await db.commit()
    
    async def update_filter_period(self, user_id: int, period_days: int):
        """Обновить период фильтрации записей (1-30 дней)"""
        # Валидация: минимум 1 день, максимум 30 дней
        period_days = max(1, min(30, period_days))
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE users 
                SET filter_period_days = ?
                WHERE user_id = ?
            """, (period_days, user_id))
            await db.commit()
    
    async def update_last_check_time(self, user_id: int):
        """Обновить время последней проверки"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE users 
                SET last_check_time = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (user_id,))
            await db.commit()
    
    async def get_users_to_check(self) -> List[Dict[str, Any]]:
        """Получить список пользователей, которым пора делать проверку"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT user_id, patient_number, patient_birthday, 
                       check_interval_minutes, filter_period_days
                FROM users 
                WHERE is_active = 1 
                  AND is_notifications_enabled = 1
                  AND patient_number IS NOT NULL 
                  AND patient_birthday IS NOT NULL
                  AND (
                    last_check_time IS NULL 
                    OR datetime(last_check_time, '+' || check_interval_minutes || ' minutes') <= datetime('now')
                  )
            """) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
