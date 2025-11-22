# SMART DYNAMIC PROVIDER - МОМЕНТАЛЬНЫЙ ПОИСК ОТВЕТОВ
"""
Provider: smart_dynamic
Генератор скриптов с динамичной системой поиска ответов по заголовкам вопросов

ФИЛОСОФИЯ:
Вместо линейного перебора всех возможных вопросов (медленно при 100+ вопросах),
используем hash-map (словарь Python) для моментального поиска O(1).

WORKFLOW:
1. Парсим user_code и извлекаем все пары "вопрос -> действие"
2. Создаем словарь QUESTIONS_POOL
3. На каждом шаге скрипт:
   - Находит все heading на странице
   - Ищет каждый heading в словаре (моментально!)
   - Выполняет соответствующее действие

ПОДДЕРЖКА:
- Динамический порядок вопросов (1,2,3 или 1,3,2 или любой другой)
- До 100+ вопросов без потери производительности
- Специальные команды (#pause, #scroll_search, #optional, etc.)
- Popup окна (page1, page2, page3)
- Многопоточность и прокси (из smart_no_api)
"""

import json
import re
from typing import Dict, List, Tuple, Optional


class Generator:
    """Генератор с динамичной системой поиска ответов"""

    def generate_script(self, user_code: str, config: Dict) -> str:
        """
        Генерирует Playwright скрипт с динамичным поиском ответов

        Args:
            user_code: Код из Playwright recorder
            config: Конфигурация (API token, proxy, profile settings, threads_count, proxy_list)

        Returns:
            Полный исполняемый Python скрипт
        """
        api_token = config.get('api_token', '')
        proxy_config = config.get('proxy', {})
        proxy_list_config = config.get('proxy_list', {})
        profile_config = config.get('profile', {})
        threads_count = config.get('threads_count', 1)
        network_capture_patterns = config.get('network_capture_patterns', [])

        # Симуляция ввода текста
        self.simulate_typing = config.get('simulate_typing', True)
        self.typing_delay = config.get('typing_delay', 100)

        # Задержка между действиями (клики, заполнения)
        self.action_delay = config.get('action_delay', 0.5)

        # ПАРСИНГ: Извлекаем вопросы и действия из user_code
        questions_pool, pre_questions_code, post_questions_code = self._parse_user_code(user_code)

        script = self._generate_imports()
        script += self._generate_config(api_token, proxy_config, proxy_list_config, threads_count)
        script += self._generate_proxy_rotation()
        script += self._generate_octobrowser_functions(profile_config)
        script += self._generate_helpers()
        script += self._generate_csv_loader()
        script += self._generate_questions_pool(questions_pool)  # 🔥 СЛОВАРЬ ВОПРОСОВ
        script += self._generate_answer_question_function()  # 🔥 ФУНКЦИЯ ПОИСКА И ОТВЕТА
        script += self._generate_main_iteration(pre_questions_code, post_questions_code, network_capture_patterns)
        script += self._generate_worker_function()
        script += self._generate_main_function()

        return script

    def _parse_user_code(self, user_code: str) -> Tuple[Dict, str, str]:
        """
        Парсит user_code и извлекает:
        1. Словарь вопросов и ответов (QUESTIONS_POOL)
        2. Код до первого вопроса (навигация, начальные действия)
        3. Код после всех вопросов (popup окна, финальные действия)

        Returns:
            Tuple[questions_pool, pre_questions_code, post_questions_code]
        """
        # Нормализация табов в пробелы
        user_code = user_code.replace('\t', '    ')
        lines = user_code.split('\n')

        questions_pool = {}
        pre_questions_lines = []
        post_questions_lines = []
        current_question = None
        current_actions = []
        in_questions_section = False
        in_post_section = False
        page_context = 'page'  # Текущий контекст страницы (page, page1, page2, page3)

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Пропускаем пустые строки и импорты
            if not stripped or stripped.startswith('import ') or stripped.startswith('from '):
                continue

            # Пропускаем boilerplate
            if any(pattern in stripped for pattern in [
                'def run(', 'with sync_playwright()', 'run(playwright)',
                'browser = playwright', 'context = browser', 'page = context',
                '.close()'
            ]):
                continue

            # Отслеживание popup окон - переключаем в post_section
            if 'with page.expect_popup()' in stripped or '= page1_info.value' in stripped:
                in_post_section = True
                in_questions_section = False

                # Проверяем следующую строку в with блоке на наличие .click()
                # Если последнее действие текущего вопроса - клик по той же кнопке,
                # то удаляем его из вопроса (он должен быть внутри with блока)
                if current_question and current_actions and 'with page.expect_popup()' in stripped:
                    # Ищем следующую непустую строку (элемент внутри with блока)
                    next_line_idx = i + 1
                    while next_line_idx < len(lines) and not lines[next_line_idx].strip():
                        next_line_idx += 1

                    if next_line_idx < len(lines):
                        next_line = lines[next_line_idx].strip()

                        # Извлекаем имя кнопки из with блока
                        button_in_with = None
                        if 'get_by_role("button"' in next_line or "get_by_role('button'" in next_line:
                            match = re.search(r'get_by_role\(["\']button["\']\s*,\s*name=["\']([^"\']+)["\']', next_line)
                            if match:
                                button_in_with = match.group(1)

                        # Проверяем последнюю строку текущего вопроса
                        if button_in_with and current_actions:
                            last_action = current_actions[-1].strip()
                            if '.click()' in last_action and button_in_with in last_action:
                                # Удаляем последнее действие из вопроса - оно дублируется
                                print(f"[PARSER] DEBUG: Удаляю дубликат клика '{button_in_with}' из вопроса '{current_question}'")
                                current_actions = current_actions[:-1]

                # Сохраняем текущий вопрос если есть
                if current_question and current_actions:
                    questions_pool[current_question] = self._parse_actions(current_actions)
                    current_question = None
                    current_actions = []

            # Post-section код (popup окна)
            if in_post_section:
                # Обновляем page context
                if '= page1_info.value' in stripped:
                    page_context = 'page1'
                elif '= page2_info.value' in stripped:
                    page_context = 'page2'
                elif '= page3_info.value' in stripped:
                    page_context = 'page3'

                # Добавляем .click() если его нет внутри with блока
                # Playwright Recorder иногда записывает без .click()
                if ('get_by_role("button"' in stripped or "get_by_role('button'" in stripped) and '.click()' not in stripped:
                    # Проверяем, что это внутри with блока (предыдущая строка содержит with page.expect_popup)
                    if i > 0 and 'with page.expect_popup()' in lines[i-1]:
                        # Добавляем .click() к строке
                        fixed_line = line.rstrip() + '.click()'
                        post_questions_lines.append(fixed_line)
                        continue

                post_questions_lines.append(line)
                continue

            # Обнаружение heading (вопроса)
            # ВАЖНО: Если у heading есть .click() - это НЕ маркер вопроса, а действие!
            if 'get_by_role("heading"' in stripped or "get_by_role('heading'" in stripped:
                # Если у heading есть .click() - это кликабельный элемент, обрабатываем как обычное действие
                if '.click()' in stripped:
                    # Это действие, не маркер вопроса - обрабатываем ниже как обычную строку
                    pass  # Продолжаем обработку ниже
                else:
                    # Сохранить предыдущий вопрос если был
                    if current_question and current_actions:
                        questions_pool[current_question] = self._parse_actions(current_actions)

                    # Извлечь текст нового вопроса (улучшенный парсинг с поддержкой апострофов)
                    # Сначала пробуем двойные кавычки
                    match = re.search(r'get_by_role\("heading"\s*,\s*name="([^"]+)"', stripped)
                    if not match:
                        # Затем одинарные кавычки
                        match = re.search(r"get_by_role\('heading'\s*,\s*name='([^']+)'", stripped)

                    if match:
                        current_question = match.group(1)
                        current_actions = []
                        in_questions_section = True
                    continue

            # Если мы в секции вопросов, собираем действия
            if in_questions_section and current_question:
                # Это действие, относящееся к текущему вопросу
                current_actions.append(line)
            elif not in_questions_section and not in_post_section:
                # Это код до начала вопросов (навигация, начальные действия)
                pre_questions_lines.append(line)

        # Сохранить последний вопрос если есть
        if current_question and current_actions:
            questions_pool[current_question] = self._parse_actions(current_actions)

        # DEBUG: вывод всех распарсенных вопросов
        print(f"\n[PARSER] DEBUG: Найдено {len(questions_pool)} вопросов в user_code:")
        for i, (q, data) in enumerate(list(questions_pool.items())[:10], 1):
            actions_count = len(data.get('actions', []))
            print(f"[PARSER]   {i}. '{q}' -> {actions_count} действий")
            if actions_count == 0:
                print(f"[PARSER]      WARNING: НЕТ ДЕЙСТВИЙ! current_actions было: {len(current_actions) if current_actions else 0} строк")

        pre_questions_code = '\n'.join(pre_questions_lines)
        post_questions_code = '\n'.join(post_questions_lines)

        return questions_pool, pre_questions_code, post_questions_code

    def _parse_actions(self, action_lines: List[str]) -> Dict:
        """
        Парсит действия для одного вопроса и создает структуру данных

        Returns:
            Dict с информацией о том, как ответить на вопрос
        """
        actions = []
        special_commands = []

        # DEBUG
        debug_enabled = False  # Включать только при отладке
        if debug_enabled:
            print(f"[PARSER] _parse_actions: получено {len(action_lines)} строк")

        for line in action_lines:
            stripped = line.strip()

            if debug_enabled:
                print(f"[PARSER]   Парсю: '{stripped[:80]}...'")  # Первые 80 символов

            # Специальные команды
            if stripped.startswith('#'):
                special_commands.append(stripped)
                continue

            # Клик по кнопке (НЕ по heading - heading это маркер вопроса, не действие!)
            if '.click()' in stripped and 'get_by_role(' in stripped and 'button' in stripped:
                # Улучшенный парсинг с поддержкой апострофов
                match = re.search(r'get_by_role\("button"\s*,\s*name="([^"]+)"', stripped)
                if not match:
                    match = re.search(r"get_by_role\('button'\s*,\s*name='([^']+)'", stripped)
                if match:
                    button_text = match.group(1)
                    actions.append({
                        'type': 'button_click',
                        'value': button_text
                    })

            # ВАЖНО: Клик по heading НЕ является действием - это просто маркер вопроса
            # Он уже обработан выше в _parse_user_code() и НЕ должен попасть в actions
            # Поэтому мы проверяем специально 'button' в строке выше

            # Заполнение текстового поля
            elif '.fill(' in stripped:
                # Извлечь название поля (улучшенный парсинг)
                field_name = None
                if 'get_by_role(' in stripped and 'textbox' in stripped:
                    match = re.search(r'get_by_role\("textbox"\s*,\s*name="([^"]+)"', stripped)
                    if not match:
                        match = re.search(r"get_by_role\('textbox'\s*,\s*name='([^']+)'", stripped)
                    if match:
                        field_name = match.group(1)

                # Извлечь значение (data_row["FieldX"] или строку)
                fill_match = re.search(r'\.fill\(([^)]+)\)', stripped)
                if fill_match:
                    fill_value = fill_match.group(1).strip()
                    # Проверить, это data_row или строка
                    data_key_match = re.search(r'data_row\[["\']([^"\']+)["\']\]', fill_value)
                    if data_key_match:
                        data_key = data_key_match.group(1)
                        actions.append({
                            'type': 'textbox_fill',
                            'field_name': field_name,
                            'data_key': data_key
                        })
                    else:
                        # Статичное значение
                        actions.append({
                            'type': 'textbox_fill',
                            'field_name': field_name,
                            'value': fill_value.strip('"\'')
                        })

            # Press (Enter, ArrowDown, etc.)
            elif '.press(' in stripped:
                press_match = re.search(r'\.press\(["\']([^"\']+)["\']', stripped)
                if press_match:
                    key = press_match.group(1)
                    actions.append({
                        'type': 'press_key',
                        'key': key
                    })

            # Locator click
            elif '.click()' in stripped and 'locator(' in stripped:
                locator_match = re.search(r'locator\(["\']([^"\']+)["\']', stripped)
                if locator_match:
                    selector = locator_match.group(1)
                    actions.append({
                        'type': 'locator_click',
                        'selector': selector
                    })

        return {
            'actions': actions,
            'special_commands': special_commands
        }

    def _generate_imports(self) -> str:
        return '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Автоматически сгенерированный скрипт
Provider: smart_dynamic (DYNAMIC QUESTION ANSWERING + OCTOBROWSER API + PROXY + MULTITHREADING)

ОСОБЕННОСТИ:
- Моментальный поиск ответов через словарь O(1)
- Работает с динамическим порядком вопросов (может быть любой!)
- Поддержка до 100+ вопросов без потери производительности
- Octobrowser API + прокси + многопоточность
"""

import csv
import time
import requests
import threading
import random
import re
import os
from tkinter import Tk, filedialog
from concurrent.futures import ThreadPoolExecutor, as_completed
from playwright.sync_api import sync_playwright, expect, TimeoutError as PlaywrightTimeout
from typing import Dict, List, Optional

'''

    def _generate_config(self, api_token: str, proxy_config: Dict, proxy_list_config: Dict, threads_count: int) -> str:
        config = f'''# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================

# Octobrowser API
API_BASE_URL = "https://app.octobrowser.net/api/v2/automation"
API_TOKEN = "{api_token}"
LOCAL_API_URL = "http://localhost:58888/api"

'''

        # Многопоточность
        config += f'''# Многопоточность
THREADS_COUNT = {threads_count}

'''

        # Прокси конфигурация
        proxies_list = proxy_list_config.get('proxies', [])
        rotation_mode = proxy_list_config.get('rotation_mode', 'random')
        use_proxy_list = len(proxies_list) > 0

        if use_proxy_list:
            config += f'''# Прокси список с ротацией
USE_PROXY_LIST = True
PROXY_LIST = {json.dumps(proxies_list, ensure_ascii=False, indent=2)}
PROXY_ROTATION_MODE = "{rotation_mode}"

'''
        else:
            proxy_enabled = proxy_config.get('enabled', False)
            config += f'''# Прокси (одиночный)
USE_PROXY_LIST = False
USE_PROXY = {proxy_enabled}
'''

            if proxy_enabled:
                config += f'''PROXY_TYPE = "{proxy_config.get('type', 'http')}"
PROXY_HOST = "{proxy_config.get('host', '')}"
PROXY_PORT = "{proxy_config.get('port', '')}"
PROXY_LOGIN = "{proxy_config.get('login', '')}"
PROXY_PASSWORD = "{proxy_config.get('password', '')}"
'''

        config += '''
# Таймауты
DEFAULT_TIMEOUT = 10000  # 10 секунд
NAVIGATION_TIMEOUT = 60000  # 60 секунд
QUESTION_SEARCH_TIMEOUT = 5000  # 5 секунд для поиска вопроса

# Thread-safe счетчик для round-robin
_proxy_counter = 0
_proxy_lock = threading.Lock()

'''
        return config

    # Копируем функции из smart_no_api (прокси, octobrowser, helpers, csv_loader)
    # Они идентичны, поэтому просто возвращаем тот же код

    def _generate_proxy_rotation(self) -> str:
        """Копия из smart_no_api"""
        return '''# ============================================================
# ПРОКСИ РОТАЦИЯ
# ============================================================

def parse_proxy_string(proxy_string: str) -> Optional[Dict]:
    """Парсинг прокси строки"""
    try:
        proxy_string = proxy_string.strip()

        # type://login:password@host:port
        match = re.match(r'^(https?|socks5)://([^:]+):([^@]+)@([^:]+):(\\d+)$', proxy_string)
        if match:
            return {
                'type': match.group(1),
                'login': match.group(2),
                'password': match.group(3),
                'host': match.group(4),
                'port': match.group(5)
            }

        # type://host:port
        match = re.match(r'^(https?|socks5)://([^:]+):(\\d+)$', proxy_string)
        if match:
            return {
                'type': match.group(1),
                'host': match.group(2),
                'port': match.group(3),
                'login': '',
                'password': ''
            }

        # host:port:login:password
        match = re.match(r'^([^:]+):(\\d+):([^:]+):([^:]+)$', proxy_string)
        if match:
            return {
                'type': 'http',
                'host': match.group(1),
                'port': match.group(2),
                'login': match.group(3),
                'password': match.group(4)
            }

        # host:port
        match = re.match(r'^([^:]+):(\\d+)$', proxy_string)
        if match:
            return {
                'type': 'http',
                'host': match.group(1),
                'port': match.group(2),
                'login': '',
                'password': ''
            }

        print(f"[PROXY] [WARNING] Не удалось распарсить: {proxy_string}")
        return None

    except Exception as e:
        print(f"[PROXY] [ERROR] Ошибка парсинга: {e}")
        return None


def get_proxy_for_thread(thread_id: int, iteration_number: int) -> Optional[Dict]:
    """Получить прокси для потока"""
    global _proxy_counter

    if not USE_PROXY_LIST:
        if not USE_PROXY:
            return None
        return {
            'type': PROXY_TYPE,
            'host': PROXY_HOST,
            'port': PROXY_PORT,
            'login': PROXY_LOGIN,
            'password': PROXY_PASSWORD
        }

    if not PROXY_LIST or len(PROXY_LIST) == 0:
        print("[PROXY] [WARNING] Список прокси пуст!")
        return None

    proxy_string = None

    if PROXY_ROTATION_MODE == 'random':
        proxy_string = random.choice(PROXY_LIST)
        print(f"[PROXY] [RANDOM] Thread {thread_id}, Iteration {iteration_number}: выбран случайный прокси")
    elif PROXY_ROTATION_MODE == 'round-robin':
        with _proxy_lock:
            index = _proxy_counter % len(PROXY_LIST)
            proxy_string = PROXY_LIST[index]
            _proxy_counter += 1
        print(f"[PROXY] [ROUND-ROBIN] Thread {thread_id}, Iteration {iteration_number}: прокси #{index + 1}/{len(PROXY_LIST)}")
    elif PROXY_ROTATION_MODE == 'sticky':
        index = thread_id % len(PROXY_LIST)
        proxy_string = PROXY_LIST[index]
        print(f"[PROXY] [STICKY] Thread {thread_id}: закреплен за прокси #{index + 1}")
    else:
        proxy_string = PROXY_LIST[0]

    proxy_dict = parse_proxy_string(proxy_string)
    if proxy_dict:
        print(f"[PROXY] [OK] {proxy_dict['type']}://{proxy_dict['host']}:{proxy_dict['port']}")

    return proxy_dict


'''

    def _generate_octobrowser_functions(self, profile_config: Dict) -> str:
        """Копия из smart_no_api (сокращенная версия для краткости)"""
        if not profile_config:
            profile_config = {}

        fingerprint = profile_config.get('fingerprint') or {"os": "win"}
        tags = profile_config.get('tags', [])
        geolocation = profile_config.get('geolocation')

        fingerprint_json = json.dumps(fingerprint, ensure_ascii=False)
        tags_json = json.dumps(tags, ensure_ascii=False)
        geolocation_json = json.dumps(geolocation, ensure_ascii=False) if geolocation else 'None'

        return f'''# ============================================================
# OCTOBROWSER API ФУНКЦИИ
# ============================================================

def create_profile(title: str = "Auto Profile", proxy_dict: Optional[Dict] = None) -> Optional[str]:
    """Создать профиль через Octobrowser API с прокси"""
    url = f"{{API_BASE_URL}}/profiles"
    headers = {{"X-Octo-Api-Token": API_TOKEN}}

    profile_data = {{
        "title": title,
        "fingerprint": {fingerprint_json},
        "tags": {tags_json}
    }}

    if proxy_dict:
        profile_data["proxy"] = {{
            "type": proxy_dict.get('type', 'http'),
            "host": proxy_dict['host'],
            "port": proxy_dict['port'],
            "login": proxy_dict.get('login', ''),
            "password": proxy_dict.get('password', '')
        }}
        print(f"[PROFILE] [!] ПРОКСИ: {{proxy_dict['type']}}://{{proxy_dict['host']}}:{{proxy_dict['port']}}")

    if {geolocation_json}:
        profile_data['geolocation'] = {geolocation_json}

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=profile_data, timeout=60)

            if response.status_code == 429:
                wait_time = 2 ** attempt * 5
                print(f"[PROFILE] [!] Rate limit, waiting {{wait_time}}s")
                time.sleep(wait_time)
                continue

            if response.status_code in [200, 201]:
                result = response.json()
                if result.get('success') and 'data' in result:
                    profile_uuid = result['data']['uuid']
                    print(f"[PROFILE] [OK] Профиль создан: {{profile_uuid}}")
                    return profile_uuid
            else:
                print(f"[PROFILE] [ERROR] Ошибка API: {{response.status_code}}")
                return None
        except Exception as e:
            print(f"[PROFILE] [ERROR] Exception: {{e}}")
            if attempt < max_retries - 1:
                time.sleep(5)
                continue
            return None

    return None


def check_local_api() -> bool:
    """Проверить доступность локального Octobrowser API"""
    try:
        response = requests.get(f"{{LOCAL_API_URL}}/profiles", timeout=5)
        if response.status_code in [200, 404]:
            print(f"[LOCAL_API] [OK] Доступен на {{LOCAL_API_URL}}")
            return True
        return False
    except:
        print(f"[LOCAL_API] [ERROR] Недоступен")
        return False


def start_profile(profile_uuid: str) -> Optional[Dict]:
    """Запустить профиль и получить CDP endpoint"""
    url = f"{{LOCAL_API_URL}}/profiles/start"

    max_retries = 8
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                wait_time = 2 ** (attempt - 1) * 2
                print(f"[PROFILE] Ожидание синхронизации: {{wait_time}}s")
                time.sleep(wait_time)

            response = requests.post(
                url,
                json={{
                    "uuid": profile_uuid,
                    "debug_port": True,
                    "headless": False,
                    "only_local": True,
                    "timeout": 120
                }},
                timeout=120
            )

            if response.status_code == 200:
                data = response.json()
                print(f"[PROFILE] [OK] Профиль запущен")
                return data
            elif response.status_code == 404:
                print(f"[PROFILE] [!] Профиль еще не синхронизирован")
                continue
            else:
                print(f"[PROFILE] [ERROR] Ошибка запуска: {{response.status_code}}")
                return None
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"[PROFILE] [ERROR] Exception: {{e}}")
            continue

    return None


def stop_profile(profile_uuid: str):
    """Остановить профиль"""
    url = f"{{LOCAL_API_URL}}/profiles/{{profile_uuid}}/stop"
    try:
        requests.get(url, timeout=10)
        print(f"[PROFILE] [OK] Профиль остановлен")
    except:
        pass


def delete_profile(profile_uuid: str):
    """Удалить профиль"""
    url = f"{{API_BASE_URL}}/profiles/{{profile_uuid}}"
    headers = {{"X-Octo-Api-Token": API_TOKEN}}
    try:
        requests.delete(url, headers=headers, timeout=10)
        print(f"[PROFILE] [OK] Профиль удалён")
    except:
        pass


'''

    def _generate_helpers(self) -> str:
        """Базовые helper функции"""
        return '''# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def wait_for_navigation(page, timeout=30000):
    """Ожидание завершения навигации"""
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
        print("[NAVIGATION] [OK] Страница загружена")
        return True
    except:
        print("[NAVIGATION] [!] Таймаут навигации")
        return False


def scroll_to_element(page, selector, by_role=None, name=None, by_test_id=None, max_duration_seconds=180):
    """
    Циклически скроллит страницу вниз-вверх-вниз-вверх пока не найдет элемент

    Подходит для динамически подгружаемых элементов, которые появляются при скролле.
    Можно использовать как замену #retry для элементов требующих скролла.

    Args:
        page: Playwright page
        selector: CSS selector (если by_role=None и by_test_id=None)
        by_role: Тип роли (button, heading, textbox)
        name: Имя элемента для get_by_role
        by_test_id: Test ID элемента для get_by_test_id
        max_duration_seconds: Максимальное время поиска в секундах (по умолчанию 180 = 3 минуты)

    Returns:
        True если элемент найден, False если нет
    """
    print(f"[SCROLL_SEARCH] Ищу элемент с циклическим скроллом (max {max_duration_seconds}s)...")

    start_time = time.time()

    def check_element_visible():
        """Проверяет видимость элемента"""
        try:
            if by_test_id:
                element = page.get_by_test_id(by_test_id).first
            elif by_role:
                element = page.get_by_role(by_role, name=name).first
            else:
                element = page.locator(selector).first

            if element.is_visible(timeout=1000):
                # Прокрутить к элементу
                element.scroll_into_view_if_needed(timeout=2000)
                time.sleep(0.5)
                return True
        except:
            pass
        return False

    def is_time_expired():
        """Проверяет не истекло ли время"""
        elapsed = time.time() - start_time
        if elapsed >= max_duration_seconds:
            print(f"[SCROLL_SEARCH] [!] Превышен лимит времени ({elapsed:.1f}s / {max_duration_seconds}s)")
            return True
        return False

    # 1. Проверяем элемент на текущей позиции
    if check_element_visible():
        print(f"[SCROLL_SEARCH] [OK] Элемент найден на текущей позиции")
        return True

    scroll_count = 0
    cycle = 0

    # 2. ЦИКЛИЧЕСКИЙ ПОИСК: вниз → вверх → вниз → вверх...
    while not is_time_expired():
        cycle += 1
        elapsed = time.time() - start_time
        print(f"[SCROLL_SEARCH] === Цикл {cycle} (время: {elapsed:.1f}s / {max_duration_seconds}s) ===")

        # 2.1. Скроллим ВНИЗ до конца страницы
        print(f"[SCROLL_SEARCH] Скроллю вниз...")
        max_down_scrolls = 30  # Максимум попыток вниз
        for _ in range(max_down_scrolls):
            if is_time_expired():
                break

            current_scroll = page.evaluate('window.pageYOffset')
            page.evaluate('window.scrollBy(0, window.innerHeight * 0.8)')  # Скролл на 80% высоты экрана
            time.sleep(0.5)
            scroll_count += 1

            # Проверяем элемент
            if check_element_visible():
                elapsed = time.time() - start_time
                print(f"[SCROLL_SEARCH] [OK] Элемент найден после {scroll_count} прокруток за {elapsed:.1f}s (цикл {cycle}, вниз)")
                return True

            # Проверяем достигли ли конца страницы
            new_scroll = page.evaluate('window.pageYOffset')
            if new_scroll == current_scroll:
                print(f"[SCROLL_SEARCH] Достигнут конец страницы")
                break

        if is_time_expired():
            break

        # 2.2. Скроллим ВВЕРХ до начала страницы
        print(f"[SCROLL_SEARCH] Скроллю вверх...")
        max_up_scrolls = 30  # Максимум попыток вверх
        for _ in range(max_up_scrolls):
            if is_time_expired():
                break

            current_scroll = page.evaluate('window.pageYOffset')

            # Скроллим вверх
            page.evaluate('window.scrollBy(0, -window.innerHeight * 0.8)')  # Скролл вверх
            time.sleep(0.5)
            scroll_count += 1

            # Проверяем элемент
            if check_element_visible():
                elapsed = time.time() - start_time
                print(f"[SCROLL_SEARCH] [OK] Элемент найден после {scroll_count} прокруток за {elapsed:.1f}s (цикл {cycle}, вверх)")
                return True

            # Проверяем достигли ли начала страницы
            new_scroll = page.evaluate('window.pageYOffset')
            if new_scroll == current_scroll or new_scroll <= 0:
                print(f"[SCROLL_SEARCH] Достигнуто начало страницы")
                break

        # Пауза между циклами (чтобы дать элементу время загрузиться)
        if not is_time_expired():
            print(f"[SCROLL_SEARCH] Пауза 2 сек перед следующим циклом...")
            time.sleep(2)

    elapsed = time.time() - start_time
    print(f"[SCROLL_SEARCH] [!] Элемент не найден после {scroll_count} прокруток за {elapsed:.1f}s ({cycle} циклов)")
    return False


def execute_special_command(command: str, page, data_row: Dict):
    """
    Выполнить специальную команду (#pause, #scroll, etc.)

    Args:
        command: Команда (например, "#pause10", "#scrolldown")
        page: Playwright page
        data_row: Данные из CSV
    """
    command = command.strip().lower()

    # #pause10, #pause5, etc.
    pause_match = re.match(r'#\s*pause\s*(\d+)', command)
    if pause_match:
        seconds = int(pause_match.group(1))
        print(f'[PAUSE] Waiting {seconds} seconds...', flush=True)
        time.sleep(seconds)
        return

    # #scrolldown или #scroll
    if command in ['#scrolldown', '#scroll']:
        print(f'[SCROLL] Scrolling down...', flush=True)
        page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        time.sleep(0.5)
        return

    # #scrollup
    if command == '#scrollup':
        print(f'[SCROLL] Scrolling up...', flush=True)
        page.evaluate('window.scrollTo(0, 0)')
        time.sleep(0.5)
        return

    # #scrollmid
    if command == '#scrollmid':
        print(f'[SCROLL] Scrolling to middle...', flush=True)
        page.evaluate('window.scrollTo(0, document.body.scrollHeight / 2)')
        time.sleep(0.5)
        return

    # #toggle_switches
    if command == '#toggle_switches':
        print(f'[SWITCHES] Toggling switches...', flush=True)
        try:
            switches = page.get_by_role('switch').all()
            # Uncheck first checked
            for switch in switches:
                if switch.is_checked():
                    switch.uncheck()
                    time.sleep(0.3)
                    break
            # Check first unchecked
            for switch in switches:
                if not switch.is_checked():
                    switch.check()
                    time.sleep(0.3)
                    break
        except Exception as e:
            print(f'[SWITCHES] [ERROR] {e}', flush=True)
        return


'''

    def _generate_csv_loader(self) -> str:
        """Копия из smart_no_api"""
        return '''# ============================================================
# ЗАГРУЗКА CSV
# ============================================================

def load_csv_data() -> List[Dict]:
    """Загрузить данные из CSV файла через диалог"""
    print("[CSV] Выберите CSV файл с данными...")

    root = Tk()
    root.withdraw()
    root.attributes('-topmost', True)

    csv_file_path = filedialog.askopenfilename(
        title="Выберите CSV файл с данными",
        filetypes=[("CSV файлы", "*.csv"), ("Все файлы", "*.*")],
        initialdir=os.path.expanduser("~")
    )

    root.destroy()

    if not csv_file_path:
        print("[CSV] [ERROR] Файл не выбран")
        return []

    if not os.path.exists(csv_file_path):
        print(f"[CSV] [ERROR] Файл не существует: {csv_file_path}")
        return []

    print(f"[CSV] Загрузка файла: {csv_file_path}")

    data = []
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            data = list(reader)

        print(f"[CSV] [OK] Загружено {len(data)} строк")

        if data and len(data) > 0:
            headers = list(data[0].keys())
            print(f"[CSV] Заголовки: {', '.join(headers)}")

    except Exception as e:
        print(f"[CSV] [ERROR] Ошибка загрузки: {e}")
        return []

    return data


'''

    def _generate_questions_pool(self, questions_pool: Dict) -> str:
        """
        Генерирует словарь QUESTIONS_POOL с парами "вопрос -> действие"

        Args:
            questions_pool: Извлеченный словарь вопросов из user_code
        """
        # Конвертируем в JSON для вставки в код
        pool_json = json.dumps(questions_pool, ensure_ascii=False, indent=4)

        return f'''# ============================================================
# СЛОВАРЬ ВОПРОСОВ И ОТВЕТОВ (МОМЕНТАЛЬНЫЙ ПОИСК O(1))
# ============================================================

QUESTIONS_POOL = {pool_json}


'''

    def _generate_answer_question_function(self) -> str:
        """
        Генерирует функцию answer_questions() для моментального поиска и ответа
        """
        return '''# ============================================================
# ФУНКЦИЯ МОМЕНТАЛЬНОГО ПОИСКА И ОТВЕТА НА ВОПРОСЫ
# ============================================================

def normalize_text(text: str) -> str:
    """Нормализует текст для сравнения - убирает спецсимволы, лишние пробелы"""
    import re
    # Убираем звездочки, точки, восклицательные знаки в конце
    text = re.sub(r'[*?.!]+\s*$', '', text)
    # Убираем множественные пробелы
    text = re.sub(r'\s+', ' ', text)
    return text.strip().lower()


def find_question_in_pool(question_text: str, pool: Dict, debug: bool = False) -> Optional[str]:
    """
    Ищет вопрос в пуле с нечетким сопоставлением

    Пробует разные варианты:
    1. Точное совпадение
    2. Нормализованное совпадение (lowercase, убраны спецсимволы)
    3. Частичное совпадение (substring)

    Returns:
        Ключ из pool если найден, иначе None
    """
    # 1. Точное совпадение
    if question_text in pool:
        return question_text

    # 2. Нормализованное совпадение
    normalized_question = normalize_text(question_text)

    if debug:
        print(f"[SEARCH] Ищу вопрос: '{question_text}'")
        print(f"[SEARCH] Нормализован: '{normalized_question}'")

    for pool_key in pool.keys():
        normalized_key = normalize_text(pool_key)

        # Точное совпадение нормализованных
        if normalized_question == normalized_key:
            if debug:
                print(f"[SEARCH] [OK] НАЙДЕНО (нормализованное): '{pool_key}'")
            return pool_key

        # Частичное совпадение - pool_key содержится в question_text или наоборот
        if normalized_key in normalized_question or normalized_question in normalized_key:
            # Проверяем что это действительно похожие вопросы (>55% совпадение длины)
            len_ratio = min(len(normalized_key), len(normalized_question)) / max(len(normalized_key), len(normalized_question))
            if len_ratio > 0.55:
                if debug:
                    print(f"[SEARCH] [OK] НАЙДЕНО (частичное, ratio={len_ratio:.2f}): '{pool_key}'")
                return pool_key

    if debug:
        print(f"[SEARCH] [FAIL] НЕ НАЙДЕНО")
        print(f"[SEARCH] Доступные ключи в пуле (всего {len(pool)}):")
        # Показываем ВСЕ вопросы, чтобы увидеть что в пуле
        for i, key in enumerate(list(pool.keys()), 1):
            normalized = normalize_text(key)
            print(f"[SEARCH]   {i}. '{key}' -> '{normalized}'")

    return None


def answer_questions(page, data_row: Dict, max_questions: int = 100):
    """
    Находит все вопросы на странице и отвечает на них

    АЛГОРИТМ:
    1. Получить все heading элементы на странице
    2. Для каждого heading:
       - Извлечь текст вопроса
       - Найти в QUESTIONS_POOL (нечеткий поиск!)
       - Выполнить соответствующие действия
    3. Повторять пока есть новые вопросы

    Args:
        page: Playwright page
        data_row: Данные из CSV
        max_questions: Максимум вопросов для обработки (защита от бесконечного цикла)

    Returns:
        int: Количество отвеченных вопросов
    """
    answered_count = 0
    answered_questions = set()  # Чтобы не отвечать дважды на один вопрос

    print(f"\\n[DYNAMIC_QA] Начинаю поиск вопросов на странице...")
    print(f"[DYNAMIC_QA] В пуле доступно {len(QUESTIONS_POOL)} вопросов")

    # DEBUG: показываем ВСЕ вопросы ИЗ ПУЛА (чтобы видеть все что распарсилось)
    print(f"[DYNAMIC_QA] [DEBUG] Все вопросы в пуле:")
    for i, (key, value) in enumerate(list(QUESTIONS_POOL.items()), 1):
        actions_count = len(value.get('actions', []))
        print(f"[DYNAMIC_QA]   {i}. '{key}' (действий: {actions_count})")

    # Цикл поиска и ответа на вопросы
    while answered_count < max_questions:
        # Найти все heading на странице
        try:
            headings = page.get_by_role("heading").all()
            print(f"[DYNAMIC_QA] Найдено {len(headings)} заголовков на странице")
        except Exception as e:
            print(f"[DYNAMIC_QA] [ERROR] Не удалось получить headings: {e}")
            break

        found_new_question = False

        # Проверить каждый heading
        for idx, heading in enumerate(headings):
            try:
                # Получить текст вопроса
                question_text = heading.inner_text().strip()

                # DEBUG: показываем все heading что находим
                if answered_count == 0 and idx < 3:  # Только первые 3 и только на первом проходе
                    print(f"[DYNAMIC_QA] [DEBUG] Обрабатываю heading #{idx+1}: '{question_text}'")

                # Пропустить если уже отвечали
                if question_text in answered_questions:
                    if answered_count == 0:
                        print(f"[DYNAMIC_QA] [DEBUG] Пропускаю - уже отвечали на '{question_text}'")
                    continue

                # Пропустить пустые или слишком короткие
                if not question_text or len(question_text) < 3:
                    if answered_count == 0:
                        print(f"[DYNAMIC_QA] [DEBUG] Пропускаю - слишком короткий (len={len(question_text)})")
                    continue

                # УМНЫЙ ПОИСК В СЛОВАРЕ (точное + нечеткое сопоставление)
                # Первая попытка - обычный поиск
                pool_key = find_question_in_pool(question_text, QUESTIONS_POOL, debug=False)

                # Если не нашли - повторяем с debug для диагностики
                if not pool_key:
                    print(f"\\n[DYNAMIC_QA] [DEBUG] Вопрос не найден в пуле, включаю детальный поиск...")
                    print(f"[DYNAMIC_QA] [DEBUG] Вопрос на странице: '{question_text}'")
                    pool_key = find_question_in_pool(question_text, QUESTIONS_POOL, debug=True)

                if pool_key:
                    print(f"\\n[DYNAMIC_QA] [OK] Найден вопрос на странице: {question_text}")
                    if pool_key != question_text:
                        print(f"[DYNAMIC_QA] [OK] Сопоставлен с пулом: {pool_key}")

                    question_data = QUESTIONS_POOL[pool_key]

                    # Выполнить специальные команды (если есть)
                    for command in question_data.get('special_commands', []):
                        execute_special_command(command, page, data_row)

                    # Выполнить действия
                    actions = question_data.get('actions', [])
                    for action in actions:
                        try:
                            action_type = action.get('type')

                            # Клик по кнопке
                            if action_type == 'button_click':
                                button_text = action.get('value')
                                print(f"[DYNAMIC_QA]   -> Ищу кнопку: {button_text}")
                                scroll_to_element(page, None, by_role="button", name=button_text, max_duration_seconds=30)
                                print(f"[DYNAMIC_QA]   -> Кликаю кнопку: {button_text}")
                                page.get_by_role("button", name=button_text).click(timeout=10000)
                                time.sleep({self.action_delay})

                            # Заполнение текстового поля
                            elif action_type == 'textbox_fill':
                                field_name = action.get('field_name')
                                data_key = action.get('data_key')
                                static_value = action.get('value')

                                value = data_row.get(data_key, static_value) if data_key else static_value

                                print(f"[DYNAMIC_QA]   -> Ищу поле '{field_name}'")
                                scroll_to_element(page, None, by_role="textbox", name=field_name, max_duration_seconds=30)
                                print(f"[DYNAMIC_QA]   -> Заполняю поле '{field_name}': {value}")
                                textbox = page.get_by_role("textbox", name=field_name).first
                                textbox.click(timeout=5000)
                                textbox.press_sequentially(value, delay={self.typing_delay})
                                time.sleep({self.action_delay})

                            # Нажатие клавиши
                            elif action_type == 'press_key':
                                key = action.get('key')
                                print(f"[DYNAMIC_QA]   -> Нажимаю клавишу: {key}")
                                page.keyboard.press(key)
                                time.sleep({self.action_delay})

                            # Клик по locator
                            elif action_type == 'locator_click':
                                selector = action.get('selector')
                                print(f"[DYNAMIC_QA]   -> Ищу элемент: {selector[:50]}...")
                                scroll_to_element(page, selector, max_duration_seconds=30)
                                print(f"[DYNAMIC_QA]   -> Кликаю элемент: {selector[:50]}...")
                                page.locator(selector).first.click(timeout=10000)
                                time.sleep({self.action_delay})

                        except Exception as e:
                            print(f"[DYNAMIC_QA]   [ERROR] Не удалось выполнить действие: {e}")
                            # Продолжаем выполнение других действий

                    # Отметить вопрос как отвеченный
                    answered_questions.add(question_text)
                    answered_count += 1
                    found_new_question = True

                    print(f"[DYNAMIC_QA] [OK] Вопрос обработан ({answered_count}/{max_questions})")

                    # Пауза для загрузки следующего вопроса (увеличена до 3 сек)
                    print(f"[DYNAMIC_QA] Ожидание загрузки следующего вопроса (3 сек)...")
                    time.sleep(3)

                    # Попробовать дождаться изменения DOM (новый вопрос)
                    try:
                        page.wait_for_load_state("domcontentloaded", timeout=2000)
                    except:
                        pass  # Игнорируем таймаут - продолжаем

                    # Выйти из цикла headings и искать новые вопросы
                    break

            except Exception as e:
                # Ошибка при обработке конкретного heading - продолжаем со следующим
                if answered_count == 0:
                    print(f"[DYNAMIC_QA] [DEBUG] Исключение при обработке heading: {type(e).__name__}: {e}")
                continue

        # Если не нашли новых вопросов - выходим
        if not found_new_question:
            print(f"[DYNAMIC_QA] Новых вопросов не найдено, завершаю поиск")

            # DEBUG: показываем первые 5 heading что были на странице
            try:
                headings = page.get_by_role("heading").all()
                if len(headings) > 0:
                    print(f"[DYNAMIC_QA] [DEBUG] Примеры heading на странице:")
                    for i, h in enumerate(headings[:5]):
                        try:
                            text = h.inner_text().strip()
                            print(f"[DYNAMIC_QA]   {i+1}. '{text}'")
                        except:
                            pass
            except:
                pass

            break

        # Небольшая пауза перед следующей итерацией поиска
        time.sleep(0.5)

    print(f"\\n[DYNAMIC_QA] ===== ИТОГ =====")
    print(f"[DYNAMIC_QA] Всего отвечено на вопросов: {answered_count}")
    print(f"[DYNAMIC_QA] ====================\\n")

    return answered_count


'''

    def _generate_main_iteration(self, pre_questions_code: str, post_questions_code: str, network_capture_patterns: List) -> str:
        """
        Генерирует основную функцию итерации

        Args:
            pre_questions_code: Код до вопросов (навигация)
            post_questions_code: Код после вопросов (popup окна)
            network_capture_patterns: Паттерны для захвата network responses
        """
        # Очистка кода от boilerplate
        pre_code_clean = self._clean_code_section(pre_questions_code)
        post_code_clean = self._clean_code_section(post_questions_code)

        return f'''# ============================================================
# ОСНОВНАЯ ФУНКЦИЯ ИТЕРАЦИИ
# ============================================================

def run_iteration(page, data_row: Dict, iteration_number: int):
    """
    Запуск одной итерации автоматизации

    Args:
        page: Playwright page
        data_row: Данные из CSV
        iteration_number: Номер итерации
    """
    print(f"\\n{'='*60}")
    print(f"[ITERATION {{iteration_number}}] Начало")
    print(f"{'='*60}")

    try:
        # ============================================================
        # НАЧАЛЬНЫЕ ДЕЙСТВИЯ (до вопросов)
        # ============================================================
{self._indent_code(pre_code_clean, 8)}

        # ============================================================
        # ДИНАМИЧЕСКИЙ ОТВЕТ НА ВОПРОСЫ
        # ============================================================
        answered_count = answer_questions(page, data_row, max_questions=100)
        print(f"[ITERATION {{iteration_number}}] Отвечено на {{answered_count}} вопросов")

        # ============================================================
        # ДЕЙСТВИЯ ПОСЛЕ ВОПРОСОВ (popup окна, финальные действия)
        # ============================================================
{self._indent_code(post_code_clean, 8)}

        print(f"[ITERATION {{iteration_number}}] [OK] Завершено успешно")
        return True

    except Exception as e:
        print(f"[ITERATION {{iteration_number}}] [ERROR] Ошибка: {{e}}")
        import traceback
        traceback.print_exc()
        return False


'''

    def _clean_code_section(self, code: str) -> str:
        """
        Очищает секцию кода от лишних строк, нормализует и добавляет обработку ошибок
        """
        if not code or not code.strip():
            return "        # Нет дополнительных действий"

        lines = code.split('\n')
        cleaned = []

        # Определяем минимальный indent для нормализации
        min_indent = float('inf')
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                indent = len(line) - len(line.lstrip())
                min_indent = min(min_indent, indent)

        if min_indent == float('inf'):
            min_indent = 0

        for line in lines:
            stripped = line.strip()
            # Пропускаем пустые
            if not stripped:
                continue
            # Пропускаем heading БЕЗ .click() (они маркеры вопросов в QUESTIONS_POOL)
            # Но heading С .click() - это кликабельные элементы, их НЕ пропускаем
            if ('get_by_role("heading"' in stripped or "get_by_role('heading'" in stripped) and '.click()' not in stripped:
                continue

            # Убираем базовый indent для нормализации
            if min_indent > 0 and len(line) >= min_indent:
                normalized_line = line[min_indent:]
            else:
                normalized_line = line

            cleaned.append(normalized_line)

        cleaned_code = '\n'.join(cleaned) if cleaned else "        # Нет дополнительных действий"

        # Применяем обработку ошибок для resilience (особенно важно для post_questions_code)
        return self._add_error_handling_to_actions(cleaned_code)

    def _add_error_handling_to_actions(self, code: str) -> str:
        """
        Добавляет обработку ошибок для Playwright действий

        Оборачивает клики, fill и другие действия в try-except или retry логику
        НОВАЯ ФУНКЦИОНАЛЬНОСТЬ: Автоматически добавляет scroll_to_element() перед всеми действиями
        """
        if not code or not code.strip():
            return code

        lines = code.split('\n')
        result_lines = []
        i = 0
        inside_with_block = False
        with_block_indent = 0
        scroll_next_action = False  # Флаг для #scroll_search
        optional_next_action = False  # Флаг для #optional
        retry_next_action = False  # Флаг для #retry
        retry_attempts = 3  # Количество попыток для #retry
        retry_wait = 30  # Время ожидания между попытками (сек)
        retry_scroll_search = False  # Использовать ли scroll_search в retry
        last_line_was_goto = False  # Флаг для отслеживания page.goto()

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Пропускаем пустые строки
            if not stripped:
                result_lines.append(line)
                i += 1
                continue

            # Определяем текущий indent
            current_indent = len(line) - len(line.lstrip())

            # Отслеживаем вход в with блок
            if stripped.startswith('with '):
                result_lines.append(line)
                inside_with_block = True
                with_block_indent = current_indent
                i += 1
                continue

            # Отслеживаем выход из with блока
            if inside_with_block and current_indent <= with_block_indent and not stripped.startswith('with '):
                inside_with_block = False

            # Специальные команды (#pause, #scroll, etc.) - преобразуем в выполняемый код
            if stripped.startswith('#'):
                indent_str = ' ' * current_indent
                special_cmd = stripped.lower()

                # #pause10, #pause5, etc.
                pause_match = re.match(r'#\s*pause\s*(\d+)', special_cmd)
                if pause_match:
                    seconds = pause_match.group(1)
                    result_lines.append(f"{indent_str}print(f'[PAUSE] Waiting {seconds} seconds...', flush=True)")
                    result_lines.append(f"{indent_str}time.sleep({seconds})")
                    i += 1
                    continue

                # #scrolldown or #scroll
                if special_cmd in ['#scrolldown', '#scroll']:
                    result_lines.append(f"{indent_str}print(f'[SCROLL] Scrolling down...', flush=True)")
                    result_lines.append(f"{indent_str}page.evaluate('window.scrollTo(0, document.body.scrollHeight)')")
                    result_lines.append(f"{indent_str}time.sleep(0.5)")
                    i += 1
                    continue

                # #scrollup
                if special_cmd == '#scrollup':
                    result_lines.append(f"{indent_str}print(f'[SCROLL] Scrolling up...', flush=True)")
                    result_lines.append(f"{indent_str}page.evaluate('window.scrollTo(0, 0)')")
                    result_lines.append(f"{indent_str}time.sleep(0.5)")
                    i += 1
                    continue

                # #scrollmid
                if special_cmd == '#scrollmid':
                    result_lines.append(f"{indent_str}print(f'[SCROLL] Scrolling to middle...', flush=True)")
                    result_lines.append(f"{indent_str}page.evaluate('window.scrollTo(0, document.body.scrollHeight / 2)')")
                    result_lines.append(f"{indent_str}time.sleep(0.5)")
                    i += 1
                    continue

                # #scroll_search - флаг для следующего действия
                if special_cmd == '#scroll_search':
                    scroll_next_action = True
                    result_lines.append(f"{indent_str}# Scroll search enabled for next action")
                    i += 1
                    continue

                # #optional - следующее действие опциональное (может не быть на странице)
                if special_cmd == '#optional':
                    optional_next_action = True
                    result_lines.append(f"{indent_str}# Optional element (may not be present)")
                    i += 1
                    continue

                # #retry - повторять попытки найти элемент с ожиданием между попытками
                # Синтаксис: #retry или #retry:N или #retry:N:S или #retry:N:S:scroll_search
                # N - количество попыток (default: 3)
                # S - секунды ожидания между попытками (default: 30)
                # scroll_search - использовать scroll_to_element (опционально)
                retry_match = re.match(r'#\s*retry(?::(\d+))?(?::(\d+))?(?::(\w+))?$', special_cmd)
                if retry_match:
                    retry_next_action = True
                    retry_attempts = int(retry_match.group(1)) if retry_match.group(1) else 3
                    retry_wait = int(retry_match.group(2)) if retry_match.group(2) else 30
                    retry_scroll_search = retry_match.group(3) == 'scroll_search' if retry_match.group(3) else False
                    result_lines.append(f"{indent_str}# Retry enabled: {retry_attempts} attempts, {retry_wait}s wait{', with scroll_search' if retry_scroll_search else ''}")
                    i += 1
                    continue

                # Неизвестная команда - оставляем как комментарий
                result_lines.append(line)
                i += 1
                continue

            # Присваивания (page1 = ...) - оставляем как есть, но выходим из with блока
            if '=' in stripped and not any(op in stripped for op in ['.click(', '.fill(', '.press(']):
                result_lines.append(line)
                if inside_with_block and current_indent <= with_block_indent:
                    inside_with_block = False
                i += 1
                continue

            # Проверяем, является ли это Playwright действием
            is_action = any(pattern in stripped for pattern in [
                '.click(',
                '.fill(',
                '.press(',
                '.type(',
                '.select_option(',
                '.check(',
                '.uncheck(',
            ])

            if is_action:
                # Получаем индент
                indent_str = ' ' * current_indent

                # Определяем нужно ли автоматически добавить scroll_to_element()
                # Авто-детекция НЕ работает если:
                # 1. Внутри with блока (критичные действия для popup)
                # 2. Сразу после page.goto() (элемент в начале страницы)
                # 3. Уже установлен флаг scroll_next_action (явный #scroll_search)
                auto_scroll_enabled = not inside_with_block and not last_line_was_goto and not scroll_next_action

                # Если установлен флаг scroll_next_action - добавляем scroll_to_element() перед действием
                if scroll_next_action or auto_scroll_enabled:
                    # Парсим действие чтобы определить page, selector, role
                    page_var = 'page'  # По умолчанию
                    if 'page1.' in stripped:
                        page_var = 'page1'
                    elif 'page2.' in stripped:
                        page_var = 'page2'
                    elif 'page3.' in stripped:
                        page_var = 'page3'

                    # Определяем комментарий в зависимости от источника
                    if auto_scroll_enabled:
                        scroll_comment = "# AUTO-SCROLL: Automatically scrolling to element"
                    else:
                        scroll_comment = "# Scroll search for element"

                    # Определяем тип действия
                    if 'get_by_test_id(' in stripped:
                        # Извлекаем test_id
                        test_id_match = re.search(r'get_by_test_id\(["\']([^"\']+)["\']\)', stripped)
                        if test_id_match:
                            test_id = test_id_match.group(1)
                            result_lines.append(f"{indent_str}{scroll_comment}")
                            result_lines.append(f'{indent_str}scroll_to_element({page_var}, None, by_test_id="{test_id}")')
                    elif 'get_by_role(' in stripped:
                        # Извлекаем роль и имя
                        role_match = re.search(r'get_by_role\("(\w+)"\s*,\s*name="([^"]+)"', stripped)
                        if role_match:
                            role = role_match.group(1)
                            name = role_match.group(2)
                            result_lines.append(f"{indent_str}{scroll_comment}")
                            result_lines.append(f'{indent_str}scroll_to_element({page_var}, None, by_role="{role}", name="{name}")')
                    elif 'locator(' in stripped:
                        # Извлекаем селектор (поддержка вложенных кавычек в xpath)
                        # Пробуем одинарные кавычки с поддержкой экранирования
                        selector_match = re.search(r"locator\('((?:[^'\\]|\\.)*)'\)", stripped)
                        if not selector_match:
                            # Пробуем двойные кавычки с поддержкой экранирования
                            selector_match = re.search(r'locator\("((?:[^"\\]|\\.)*)"\)', stripped)
                        if selector_match:
                            selector = selector_match.group(1)
                            # Экранируем кавычки в селекторе для генерации кода
                            selector = selector.replace('\\', '\\\\').replace('"', '\\"')
                            result_lines.append(f"{indent_str}{scroll_comment}")
                            result_lines.append(f'{indent_str}scroll_to_element({page_var}, "{selector}")')

                    scroll_next_action = False  # Сбрасываем флаг

                # Действия внутри with блока критичны - нужен retry с прогрессивными задержками
                if inside_with_block:
                    # RETRY ЛОГИКА для критичных действий (popup открытие, navigation)
                    result_lines.append(f"{indent_str}# Retry logic for critical action")
                    result_lines.append(f"{indent_str}max_retries = 5")
                    result_lines.append(f"{indent_str}for retry_attempt in range(max_retries):")
                    result_lines.append(f"{indent_str}    try:")
                    result_lines.append(f"{indent_str}        if retry_attempt > 0:")
                    result_lines.append(f"{indent_str}            wait_time = retry_attempt * 3  # 3s, 6s, 9s, 12s, 15s")
                    result_lines.append(f"{indent_str}            print(f'[RETRY] Attempt {{retry_attempt+1}}/{{max_retries}} after {{wait_time}}s...', flush=True)")
                    result_lines.append(f"{indent_str}            time.sleep(wait_time)")
                    result_lines.append(f"{indent_str}        {stripped}")
                    result_lines.append(f"{indent_str}        print(f'[ACTION] [OK] Success', flush=True)")
                    result_lines.append(f"{indent_str}        break")
                    result_lines.append(f"{indent_str}    except PlaywrightTimeout:")
                    result_lines.append(f"{indent_str}        if retry_attempt == max_retries - 1:")
                    result_lines.append(f"{indent_str}            print(f'[ACTION] [ERROR] Failed after {{max_retries}} retries', flush=True)")
                    result_lines.append(f"{indent_str}            raise")
                    result_lines.append(f"{indent_str}        print(f'[RETRY] Timeout, retrying...', flush=True)")
                else:
                    # Действия вне with блока - retry, optional, или простой try-except
                    if retry_next_action:
                        # RETRY ЛОГИКА с ожиданием между попытками
                        # Парсим действие для определения page и селектора (для scroll_search)
                        page_var = 'page'
                        if 'page1.' in stripped:
                            page_var = 'page1'
                        elif 'page2.' in stripped:
                            page_var = 'page2'
                        elif 'page3.' in stripped:
                            page_var = 'page3'

                        result_lines.append(f"{indent_str}# Retry loop: {retry_attempts} attempts, {retry_wait}s wait between attempts")
                        result_lines.append(f"{indent_str}retry_success = False")
                        result_lines.append(f"{indent_str}for retry_attempt in range({retry_attempts}):")
                        result_lines.append(f"{indent_str}    if retry_attempt > 0:")
                        result_lines.append(f"{indent_str}        print(f'[RETRY] Waiting {retry_wait}s before attempt {{retry_attempt+1}}/{retry_attempts}...', flush=True)")
                        result_lines.append(f"{indent_str}        time.sleep({retry_wait})")
                        result_lines.append(f"{indent_str}    else:")
                        result_lines.append(f"{indent_str}        print(f'[RETRY] Attempt {{retry_attempt+1}}/{retry_attempts}...', flush=True)")

                        # Добавляем scroll_to_element если retry_scroll_search=True
                        if retry_scroll_search:
                            if 'get_by_test_id(' in stripped:
                                test_id_match = re.search(r'get_by_test_id\(["\']([^"\']+)["\']\)', stripped)
                                if test_id_match:
                                    test_id = test_id_match.group(1)
                                    result_lines.append(f"{indent_str}    # Scroll search before attempt")
                                    result_lines.append(f'{indent_str}    scroll_to_element({page_var}, None, by_test_id="{test_id}")')
                            elif 'get_by_role(' in stripped:
                                role_match = re.search(r'get_by_role\("(\w+)"\s*,\s*name="([^"]+)"', stripped)
                                if role_match:
                                    role = role_match.group(1)
                                    name = role_match.group(2)
                                    result_lines.append(f"{indent_str}    # Scroll search before attempt")
                                    result_lines.append(f'{indent_str}    scroll_to_element({page_var}, None, by_role="{role}", name="{name}")')
                            elif 'locator(' in stripped:
                                # Извлекаем селектор (поддержка вложенных кавычек в xpath)
                                selector_match = re.search(r"locator\('((?:[^'\\]|\\.)*)'\)", stripped)
                                if not selector_match:
                                    selector_match = re.search(r'locator\("((?:[^"\\]|\\.)*)"\)', stripped)
                                if selector_match:
                                    selector = selector_match.group(1)
                                    # Экранируем кавычки в селекторе для генерации кода
                                    selector = selector.replace('\\', '\\\\').replace('"', '\\"')
                                    result_lines.append(f"{indent_str}    # Scroll search before attempt")
                                    result_lines.append(f'{indent_str}    scroll_to_element({page_var}, "{selector}")')

                        result_lines.append(f"{indent_str}    try:")
                        result_lines.append(f"{indent_str}        {stripped}")
                        result_lines.append(f"{indent_str}        print('[RETRY] [SUCCESS] Element found and action completed', flush=True)")
                        result_lines.append(f"{indent_str}        retry_success = True")
                        result_lines.append(f"{indent_str}        break")
                        result_lines.append(f"{indent_str}    except PlaywrightTimeout:")
                        result_lines.append(f"{indent_str}        if retry_attempt == {retry_attempts} - 1:")
                        result_lines.append(f"{indent_str}            print('[RETRY] [FAILED] All {retry_attempts} attempts exhausted', flush=True)")
                        result_lines.append(f"{indent_str}            raise")
                        result_lines.append(f"{indent_str}        else:")
                        result_lines.append(f"{indent_str}            print(f'[RETRY] Timeout on attempt {{retry_attempt+1}}, will retry...', flush=True)")

                        retry_next_action = False  # Сбрасываем флаг
                        retry_scroll_search = False  # Сбрасываем флаг scroll_search
                    elif optional_next_action:
                        # Более понятные сообщения для опциональных элементов
                        result_lines.append(f"{indent_str}print('[OPTIONAL] Trying optional element...', flush=True)")
                        result_lines.append(f"{indent_str}try:")
                        result_lines.append(f"{indent_str}    {stripped}")
                        result_lines.append(f"{indent_str}    print('[OPTIONAL] [OK] Element found and clicked', flush=True)")
                        result_lines.append(f"{indent_str}except PlaywrightTimeout:")
                        result_lines.append(f"{indent_str}    print('[OPTIONAL] [SKIP] Element not found (this is OK)', flush=True)")
                        result_lines.append(f"{indent_str}    pass")
                        optional_next_action = False  # Сбрасываем флаг
                    else:
                        # Обычные действия вне with блока
                        result_lines.append(f"{indent_str}try:")
                        result_lines.append(f"{indent_str}    {stripped}")
                        result_lines.append(f"{indent_str}except PlaywrightTimeout:")
                        result_lines.append(f'{indent_str}    print("[ACTION] [WARNING] Timeout - элемент не найден", flush=True)')
                        result_lines.append(f'{indent_str}    print("[ACTION] [INFO] Продолжаем выполнение...", flush=True)')
                        result_lines.append(f"{indent_str}    pass")
            else:
                # Не действие - оставляем как есть
                result_lines.append(line)

            # Обновляем флаг last_line_was_goto для следующей итерации
            # Проверяем является ли текущая строка page.goto()
            if '.goto(' in stripped:
                last_line_was_goto = True
            elif is_action or (stripped and not stripped.startswith('#')):
                # Сбрасываем флаг если это действие или обычная строка кода
                last_line_was_goto = False

            i += 1

        return '\n'.join(result_lines)

    def _indent_code(self, code: str, spaces: int) -> str:
        """Добавить отступы к коду"""
        if not code or not code.strip():
            return ' ' * spaces + "pass"

        indent = ' ' * spaces
        lines = code.split('\n')
        return '\n'.join(indent + line if line.strip() else '' for line in lines)

    def _generate_worker_function(self) -> str:
        """Копия из smart_no_api"""
        return '''# ============================================================
# WORKER ФУНКЦИЯ (для многопоточности)
# ============================================================

def process_task(task_data: tuple) -> Dict:
    """Обработать одну задачу в отдельном потоке"""
    thread_id, iteration_number, data_row, total_count = task_data

    print(f"\\n{'#'*60}")
    print(f"# THREAD {thread_id} | ROW {iteration_number}/{total_count}")
    print(f"{'#'*60}")

    # Задержка для разнесения запусков Octobrowser (снижение нагрузки на систему)
    startup_delay = (thread_id - 1) * 3  # 0s, 3s, 6s, 9s, 12s...
    if startup_delay > 0:
        print(f"[THREAD {thread_id}] Задержка запуска: {startup_delay}s (снижение нагрузки)")
        time.sleep(startup_delay)

    profile_uuid = None
    result = {
        'thread_id': thread_id,
        'iteration': iteration_number,
        'success': False,
        'error': None
    }

    try:
        proxy_dict = get_proxy_for_thread(thread_id, iteration_number)

        profile_title = f"Auto Profile T{thread_id} #{iteration_number}"
        print(f"[THREAD {thread_id}] Создание профиля: {profile_title}")
        profile_uuid = create_profile(profile_title, proxy_dict)

        if not profile_uuid:
            result['error'] = "Profile creation failed"
            return result

        print(f"[THREAD {thread_id}] Ожидание синхронизации (5 сек)...")
        time.sleep(5)

        start_data = start_profile(profile_uuid)
        if not start_data:
            result['error'] = "Profile start failed"
            return result

        debug_url = start_data.get('ws_endpoint')
        if not debug_url:
            result['error'] = "No CDP endpoint"
            return result

        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(debug_url)
            context = browser.contexts[0]
            page = context.pages[0]

            page.set_default_timeout(DEFAULT_TIMEOUT)
            page.set_default_navigation_timeout(NAVIGATION_TIMEOUT)

            iteration_result = run_iteration(page, data_row, iteration_number)

            if iteration_result:
                result['success'] = True
            else:
                result['error'] = "Iteration failed"

            time.sleep(2)
            browser.close()

        stop_profile(profile_uuid)

    except Exception as e:
        print(f"[THREAD {thread_id}] [ERROR] Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        result['error'] = str(e)

    finally:
        if profile_uuid:
            time.sleep(1)

    return result


'''

    def _generate_main_function(self) -> str:
        """Копия из smart_no_api"""
        return '''# ============================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================

def main():
    """Главная функция запуска"""
    print("[MAIN] Запуск автоматизации через Octobrowser API...")
    print(f"[MAIN] Потоков: {THREADS_COUNT}")

    if not check_local_api():
        print("[MAIN] [ERROR] Локальный Octobrowser недоступен!")
        return

    csv_data = load_csv_data()
    print(f"[MAIN] Загружено {len(csv_data)} строк данных")

    if not csv_data:
        print("[ERROR] Нет данных для обработки")
        return

    tasks = []
    for iteration_number, data_row in enumerate(csv_data, 1):
        thread_id = (iteration_number - 1) % THREADS_COUNT + 1
        task_data = (thread_id, iteration_number, data_row, len(csv_data))
        tasks.append(task_data)

    actual_threads = min(THREADS_COUNT, len(csv_data))
    print(f"\\n[MAIN] Запуск {len(tasks)} задач в {actual_threads} потоках...")

    success_count = 0
    fail_count = 0

    with ThreadPoolExecutor(max_workers=actual_threads) as executor:
        future_to_task = {executor.submit(process_task, task): task for task in tasks}

        for future in as_completed(future_to_task):
            try:
                result = future.result()

                if result['success']:
                    success_count += 1
                    print(f"[MAIN] [OK] Итерация {result['iteration']} завершена")
                else:
                    fail_count += 1
                    print(f"[MAIN] [ERROR] Итерация {result['iteration']} завершена с ошибкой")

            except Exception as e:
                fail_count += 1
                print(f"[MAIN] [ERROR] Ошибка: {e}")

    print(f"\\n{'='*60}")
    print(f"[MAIN] ЗАВЕРШЕНО")
    print(f"[MAIN] Успешно: {success_count}/{len(csv_data)}")
    print(f"[MAIN] Ошибок: {fail_count}/{len(csv_data)}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
'''


