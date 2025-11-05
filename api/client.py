import aiohttp
import logging
from typing import Optional, Dict, Any
from config import Config

logger = logging.getLogger(__name__)


class ZdravAPIClient:
    """Клиент для работы с API zdrav.mosreg.ru"""
    
    def __init__(self):
        self.base_url = f"https://{Config.API_BASE_URL}"
        self.headers = {
            'Accept': "application/json",
            'Accept-Encoding': "gzip, deflate, br, zstd",
            'Accept-Language': "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3",
            'Connection': "keep-alive",
            'Content-Type': "application/json",
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0"
        }
    
    async def get_doctors(self, department_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить список врачей для указанного отделения
        
        Args:
            department_id: ID отделения (52, 53, 54)
            
        Returns:
            JSON ответ с данными о врачах или None в случае ошибки
        """
        endpoint = "/api/v2/emias/iemk/doctors"
        params = {
            'number': Config.PATIENT_NUMBER,
            'birthday': Config.PATIENT_BIRTHDAY,
            'departmentId': department_id,
            'days': Config.API_DAYS
        }
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=self.headers, ssl=True) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Получены данные для department {department_id}: {len(data.get('items', []))} организаций")
                        return data
                    else:
                        logger.error(f"Ошибка при запросе для department {department_id}: статус {response.status}")
                        return None
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка сети при запросе для department {department_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при запросе для department {department_id}: {e}")
            return None
    
    async def get_all_departments(self) -> Dict[int, Optional[Dict[str, Any]]]:
        """
        Получить данные для всех настроенных отделений
        
        Returns:
            Словарь {department_id: данные}
        """
        results = {}
        for dept_id in Config.DEPARTMENT_IDS:
            logger.info(f"Запрашиваем данные для department {dept_id}")
            results[dept_id] = await self.get_doctors(dept_id)
        return results
