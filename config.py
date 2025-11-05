import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()


class Config:
    """Конфигурация приложения"""
    
    # Telegram Bot
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    # Данные пациента
    PATIENT_NUMBER = os.getenv("PATIENT_NUMBER")
    PATIENT_BIRTHDAY = os.getenv("PATIENT_BIRTHDAY")
    
    # Department IDs для мониторинга
    DEPARTMENT_IDS = [int(d.strip()) for d in os.getenv("DEPARTMENT_IDS", "52,53,54").split(",")]
    
    # Интервал проверки (в минутах)
    CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "3"))
    
    # Белый список пользователей (Telegram User IDs)
    WHITELIST_USER_IDS = [int(uid.strip()) for uid in os.getenv("WHITELIST_USER_IDS", "").split(",") if uid.strip()]
    
    # API настройки
    API_BASE_URL = "zdrav.mosreg.ru"
    API_DAYS = 21  # Количество дней для проверки
    
    # База данных
    DATABASE_PATH = "doctor_bot.db"
    
    # Логирование
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    @classmethod
    def validate(cls):
        """Проверка обязательных параметров"""
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN не установлен в .env файле")
        if not cls.PATIENT_NUMBER:
            raise ValueError("PATIENT_NUMBER не установлен в .env файле")
        if not cls.PATIENT_BIRTHDAY:
            raise ValueError("PATIENT_BIRTHDAY не установлен в .env файле")
        if not cls.WHITELIST_USER_IDS:
            raise ValueError("WHITELIST_USER_IDS не установлен в .env файле")
        
        return True
