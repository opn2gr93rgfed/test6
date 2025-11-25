"""
🌐 9Proxy Manager - Интеграция с 9Proxy API

Функции:
- Получение списка прокси через API
- Динамическая ротация прокси
- Переадресация через /api/forward
- Проверка статуса прокси
- Поддержка фильтров (country, city, ISP, plan)

API Endpoints:
- GET /api/proxy - Получить список прокси
- GET /api/today_list - Получить список today's proxies
- GET /api/forward - Переадресация на конкретный прокси
- GET /api/port_status - Статус портов
- GET /api/set_port_range - Установить диапазон портов
"""

import requests
import random
from typing import List, Dict, Optional, Literal
from datetime import datetime


class NineProxyManager:
    """
    Менеджер для работы с 9Proxy API

    Поддерживает:
    - Получение прокси через /api/proxy и /api/today_list
    - Ротацию прокси (sequential/random)
    - Фильтрацию по country, city, ISP, plan
    - Проверку доступности прокси
    - Retry logic при ошибках
    """

    def __init__(self, api_base_url: str = "http://localhost:50000"):
        """
        Инициализация менеджера

        Args:
            api_base_url: Базовый URL API (default: http://localhost:50000)
        """
        self.api_base_url = api_base_url.rstrip('/')
        self.proxy_pool: List[Dict] = []
        self.current_index: int = 0
        self.current_proxy: Optional[Dict] = None
        self.enabled: bool = False

        # Статистика
        self.total_requests: int = 0
        self.failed_requests: int = 0
        self.last_fetch_time: Optional[datetime] = None

        # 🔥 Многопоточная поддержка с отдельными портами
        self.port_proxy_map: Dict[int, Dict] = {}  # Карта порт → прокси
        self.base_port: int = 6000  # Начальный порт для переадресации

    def test_connection(self) -> tuple[bool, str]:
        """
        Проверить соединение с 9Proxy API

        Returns:
            (success: bool, message: str)
        """
        try:
            response = requests.get(
                f"{self.api_base_url}/api/proxy",
                params={'num': 1, 't': 2},
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                if not data.get('error'):
                    return True, f"✅ Подключено! Доступно прокси: {len(data.get('data', []))}"
                else:
                    return False, f"❌ API вернул ошибку: {data.get('message', 'Unknown')}"
            else:
                return False, f"❌ HTTP {response.status_code}: {response.text}"

        except requests.exceptions.Timeout:
            return False, "❌ Timeout: Не удалось подключиться к API"
        except requests.exceptions.ConnectionError:
            return False, "❌ Connection Error: Убедитесь что 9Proxy запущен"
        except Exception as e:
            return False, f"❌ Ошибка: {str(e)}"

    def fetch_proxies(self,
                     country: Optional[str] = None,
                     state: Optional[str] = None,
                     city: Optional[str] = None,
                     zip_code: Optional[str] = None,
                     isp: Optional[str] = None,
                     plan: Optional[str] = None,
                     today: bool = False,
                     num: int = 10) -> tuple[bool, str, List[Dict]]:
        """
        Получить список прокси через API

        Args:
            country: Код страны (US, VN, RU, DE, FR, GB и т.д.)
            state: Штат/регион
            city: Город
            zip_code: Почтовый индекс
            isp: Провайдер интернета
            plan: Тип плана (premium, free, all)
            today: Использовать /api/today_list (только сегодняшние прокси)
            num: Количество прокси (1-100)

        Returns:
            (success: bool, message: str, proxies: List[Dict])
        """
        try:
            # Выбрать endpoint
            endpoint = "/api/today_list" if today else "/api/proxy"

            # Параметры запроса
            params = {
                't': 2  # API требует 1 или 2 (тип прокси)
            }

            # Добавить фильтры
            if country:
                params['country'] = country.upper()
            if state:
                params['state'] = state
            if city:
                params['city'] = city
            if zip_code:
                params['zipcode'] = zip_code
            if isp:
                params['isp'] = isp
            if plan and plan != 'all':
                params['plan'] = '1' if plan == 'premium' else '2'
            if num:
                params['num'] = min(num, 100)  # Ограничение 100

            # Запрос к API
            response = requests.get(
                f"{self.api_base_url}{endpoint}",
                params=params,
                timeout=10
            )

            if response.status_code != 200:
                return False, f"HTTP {response.status_code}: {response.text}", []

            data = response.json()

            # 🔥 DEBUG: Посмотреть структуру ответа
            print(f"[9PROXY DEBUG] API Response keys: {list(data.keys())}")
            print(f"[9PROXY DEBUG] data.get('error'): {data.get('error')}")
            print(f"[9PROXY DEBUG] data.get('data') type: {type(data.get('data'))}")

            # Проверить ошибки
            if data.get('error'):
                return False, f"API Error: {data.get('message', 'Unknown error')}", []

            # Получить прокси
            proxies = data.get('data', [])

            # 🔥 DEBUG: Проверяем тип данных
            print(f"[9PROXY DEBUG] API вернул data: type={type(proxies)}, len={len(proxies) if isinstance(proxies, list) else 'N/A'}")
            if proxies and len(proxies) > 0:
                print(f"[9PROXY DEBUG] Первый элемент: type={type(proxies[0])}, value={proxies[0]}")

            if not proxies:
                return False, "Прокси не найдены с указанными фильтрами", []

            # 🔥 Защита: убедиться что proxies - это список словарей
            if not isinstance(proxies, list):
                return False, f"API вернул неправильный тип данных: {type(proxies)}", []

            # Проверить первый элемент
            if proxies and not isinstance(proxies[0], dict):
                print(f"[9PROXY WARNING] API вернул не словари! Первый элемент: {type(proxies[0])}")
                # Попробуем конвертировать если это строки
                if isinstance(proxies[0], str):
                    # Возможно это список строк вида "ip:port"
                    print(f"[9PROXY] Попытка парсинга строк...")
                    return False, "API вернул строки вместо объектов прокси", []

            # Обновить пул
            self.proxy_pool = proxies
            self.current_index = 0
            self.last_fetch_time = datetime.now()

            return True, f"Загружено {len(proxies)} прокси", proxies

        except requests.exceptions.Timeout:
            return False, "Timeout: Превышено время ожидания", []
        except requests.exceptions.ConnectionError:
            return False, "Connection Error: Не удалось подключиться к API", []
        except Exception as e:
            return False, f"Ошибка: {str(e)}", []

    def forward_to_proxy(self, proxy_id: str, port: int, plan: str = "1") -> tuple[bool, str, Optional[Dict]]:
        """
        Переадресация через /api/forward

        Args:
            proxy_id: ID прокси из списка
            port: Локальный порт для переадресации
            plan: План (1=premium, 2=free)

        Returns:
            (success: bool, message: str, forward_info: Dict)
        """
        try:
            params = {
                'id': proxy_id,
                'port': port,
                'plan': plan,
                't': 2
            }

            response = requests.get(
                f"{self.api_base_url}/api/forward",
                params=params,
                timeout=10
            )

            if response.status_code != 200:
                return False, f"HTTP {response.status_code}", None

            data = response.json()

            if data.get('error'):
                return False, data.get('message', 'Unknown error'), None

            return True, "Forward успешен", data.get('data')

        except Exception as e:
            return False, f"Ошибка: {str(e)}", None

    def get_next_proxy(self, strategy: Literal["sequential", "random"] = "sequential") -> Optional[Dict]:
        """
        Получить следующий прокси из пула

        Args:
            strategy: Стратегия выбора (sequential, random)

        Returns:
            Dict с прокси или None
        """
        if not self.proxy_pool:
            return None

        if strategy == "random":
            proxy = random.choice(self.proxy_pool)
        else:  # sequential
            proxy = self.proxy_pool[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.proxy_pool)

        self.current_proxy = proxy
        self.total_requests += 1

        return proxy

    def rotate_proxy(self, strategy: Literal["sequential", "random"] = "sequential") -> Optional[Dict]:
        """
        Принудительная ротация на следующий прокси

        Args:
            strategy: Стратегия выбора (sequential, random)

        Returns:
            Dict с прокси или None
        """
        return self.get_next_proxy(strategy)

    def check_proxy_online(self, proxy: Dict, timeout: int = 5) -> tuple[bool, str]:
        """
        Проверить доступность прокси

        Args:
            proxy: Словарь с данными прокси (должен содержать 'ip' и поле 'is_online')
            timeout: Таймаут проверки (секунды)

        Returns:
            (is_online: bool, message: str)
        """
        # Проверить поле is_online из API
        if 'is_online' in proxy:
            if proxy['is_online']:
                return True, "Online (по данным API)"
            else:
                return False, "Offline (по данным API)"

        # Если поля нет - попробовать реальную проверку
        try:
            proxy_url = f"http://{proxy.get('ip')}:{proxy.get('port', 8080)}"
            proxies = {
                'http': proxy_url,
                'https': proxy_url
            }

            response = requests.get(
                'http://httpbin.org/ip',
                proxies=proxies,
                timeout=timeout
            )

            if response.status_code == 200:
                return True, f"Online (проверен, IP: {response.json().get('origin')})"
            else:
                return False, f"Offline (HTTP {response.status_code})"

        except requests.exceptions.Timeout:
            return False, "Timeout"
        except requests.exceptions.ConnectionError:
            return False, "Connection Error"
        except Exception as e:
            return False, f"Error: {str(e)}"

    def get_port_status(self) -> tuple[bool, str, List[Dict]]:
        """
        Получить статус портов через /api/port_status

        Returns:
            (success: bool, message: str, ports: List[Dict])
        """
        try:
            response = requests.get(
                f"{self.api_base_url}/api/port_status",
                params={'t': 2},
                timeout=10
            )

            if response.status_code != 200:
                return False, f"HTTP {response.status_code}", []

            data = response.json()

            if data.get('error'):
                return False, data.get('message', 'Unknown error'), []

            ports = data.get('data', [])
            return True, f"Получено {len(ports)} портов", ports

        except Exception as e:
            return False, f"Ошибка: {str(e)}", []

    def set_port_range(self, start: int, count: int) -> tuple[bool, str]:
        """
        Установить диапазон портов через /api/set_port_range

        Args:
            start: Начальный порт
            count: Количество портов

        Returns:
            (success: bool, message: str)
        """
        try:
            response = requests.get(
                f"{self.api_base_url}/api/set_port_range",
                params={
                    'start': start,
                    'num': count,
                    't': 2
                },
                timeout=10
            )

            if response.status_code != 200:
                return False, f"HTTP {response.status_code}"

            data = response.json()

            if data.get('error'):
                return False, data.get('message', 'Unknown error')

            return True, f"Порты установлены: {start}-{start+count-1}"

        except Exception as e:
            return False, f"Ошибка: {str(e)}"

    def get_current_proxy_for_requests(self) -> Optional[Dict[str, str]]:
        """
        Получить текущий прокси в формате для библиотеки requests

        Returns:
            {'http': 'http://ip:port', 'https': 'http://ip:port'} или None
        """
        if not self.current_proxy:
            return None

        ip = self.current_proxy.get('ip')
        # Используем порт из прокси или дефолтный 8080
        port = self.current_proxy.get('port', 8080)

        if not ip:
            return None

        proxy_url = f"http://{ip}:{port}"

        return {
            'http': proxy_url,
            'https': proxy_url
        }

    def get_current_proxy_for_playwright(self) -> Optional[Dict[str, str]]:
        """
        Получить текущий прокси в формате для Playwright

        Returns:
            {'server': 'http://ip:port'} или None
        """
        if not self.current_proxy:
            return None

        ip = self.current_proxy.get('ip')
        port = self.current_proxy.get('port', 8080)

        if not ip:
            return None

        return {
            'server': f"http://{ip}:{port}"
        }

    def get_stats(self) -> Dict:
        """
        Получить статистику использования

        Returns:
            Dict со статистикой
        """
        return {
            'total_proxies': len(self.proxy_pool),
            'current_index': self.current_index,
            'total_requests': self.total_requests,
            'failed_requests': self.failed_requests,
            'success_rate': f"{((self.total_requests - self.failed_requests) / self.total_requests * 100):.1f}%" if self.total_requests > 0 else "N/A",
            'last_fetch': self.last_fetch_time.strftime("%Y-%m-%d %H:%M:%S") if self.last_fetch_time else "Never",
            'current_proxy': f"{self.current_proxy.get('ip')}:{self.current_proxy.get('port', 8080)}" if self.current_proxy else "None"
        }

    def skip_to_next_on_failure(self, strategy: Literal["sequential", "random"] = "sequential") -> Optional[Dict]:
        """
        Пропустить текущий прокси при ошибке и перейти к следующему

        Args:
            strategy: Стратегия выбора следующего прокси

        Returns:
            Следующий прокси или None
        """
        self.failed_requests += 1
        return self.get_next_proxy(strategy)

    def clear_pool(self):
        """Очистить пул прокси"""
        self.proxy_pool = []
        self.current_index = 0
        self.current_proxy = None

    def setup_ports_for_threads(self, num_threads: int) -> List[int]:
        """
        Подготовить порты для многопоточной работы

        Args:
            num_threads: Количество потоков

        Returns:
            Список портов [6001, 6002, ..., 6000+num_threads]
        """
        if not self.proxy_pool:
            print("[9PROXY] Нет прокси в пуле для назначения портам")
            return []

        ports = []
        for i in range(num_threads):
            port = self.base_port + i + 1
            ports.append(port)

            # Назначить прокси на порт
            proxy = self.proxy_pool[i % len(self.proxy_pool)]
            success, message = self.assign_proxy_to_port(proxy, port)

            if success:
                print(f"[9PROXY] Порт {port} → {proxy.get('ip')} (ID: {proxy.get('id')})")
            else:
                print(f"[9PROXY] Ошибка назначения порта {port}: {message}")

        return ports

    def assign_proxy_to_port(self, proxy: Dict, port: int, plan: str = "2") -> tuple[bool, str]:
        """
        Назначить прокси на конкретный порт через /api/forward

        Args:
            proxy: Прокси из пула (должен содержать 'id')
            port: Локальный порт для переадресации
            plan: План (1=premium, 2=free, по умолчанию 2)

        Returns:
            (success, message)
        """
        proxy_id = proxy.get('id')
        if not proxy_id:
            return False, "Прокси не имеет ID"

        success, message, data = self.forward_to_proxy(proxy_id, port, plan)

        if success:
            self.port_proxy_map[port] = proxy
            print(f"[9PROXY] ✅ Порт {port} назначен: {proxy.get('ip')} ({proxy.get('country_code')})")

        return success, message

    def rotate_port(self, port: int, strategy: Literal["sequential", "random"] = "sequential", plan: str = "2") -> tuple[bool, str, Optional[Dict]]:
        """
        Обновить IP для конкретного порта

        Args:
            port: Порт, для которого нужно обновить IP
            strategy: Стратегия выбора нового прокси
            plan: План прокси

        Returns:
            (success, message, new_proxy)
        """
        # Получить следующий прокси
        new_proxy = self.get_next_proxy(strategy)

        if not new_proxy:
            return False, "Нет доступных прокси", None

        # Назначить на порт
        success, message = self.assign_proxy_to_port(new_proxy, port, plan)

        if success:
            return True, f"Порт {port} обновлён: {new_proxy.get('ip')}", new_proxy
        else:
            return False, message, None

    def get_proxy_for_port(self, port: int) -> Optional[str]:
        """
        Получить строку прокси для конкретного порта

        Returns:
            "socks5://127.0.0.1:{port}" или None
        """
        if port in self.port_proxy_map:
            return f"socks5://127.0.0.1:{port}"
        return None

    def get_proxy_config_for_port(self, port: int) -> Optional[Dict]:
        """
        Получить конфигурацию прокси для Octobrowser для конкретного порта

        Args:
            port: Локальный порт

        Returns:
            Dict с конфигурацией прокси для Octobrowser или None
        """
        if port in self.port_proxy_map:
            return {
                'type': 'socks5',
                'host': '127.0.0.1',
                'port': str(port),
                'login': '',
                'password': ''
            }
        return None

    def __repr__(self):
        return f"<NineProxyManager: {len(self.proxy_pool)} proxies, {len(self.port_proxy_map)} ports, {self.api_base_url}>"
