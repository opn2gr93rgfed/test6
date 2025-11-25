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
            config: Конфигурация (API token, proxy, profile settings, threads_count, proxy_list, nine_proxy)

        Returns:
            Полный исполняемый Python скрипт
        """
        api_token = config.get('api_token', '')

        # 🔥 Защита от передачи строк вместо словарей
        proxy_config = config.get('proxy', {})
        if not isinstance(proxy_config, dict):
            proxy_config = {}

        proxy_list_config = config.get('proxy_list', {})
        if not isinstance(proxy_list_config, dict):
            proxy_list_config = {}

        profile_config = config.get('profile', {})
        if not isinstance(profile_config, dict):
            profile_config = {}

        threads_count = config.get('threads_count', 1)
        max_iterations = config.get('max_iterations', None)  # None = все строки CSV
        network_capture_patterns = config.get('network_capture_patterns', [])

        # 🔥 9Proxy настройки
        nine_proxy_enabled = config.get('nine_proxy_enabled', False)
        nine_proxy_api_url = config.get('nine_proxy_api_url', 'http://localhost:50000')
        nine_proxy_ports = config.get('nine_proxy_ports', [])
        nine_proxy_strategy = config.get('nine_proxy_strategy', 'sequential')
        nine_proxy_auto_rotate = config.get('nine_proxy_auto_rotate', True)

        # 🔥 Получить фильтры из nine_proxy config
        nine_proxy_config = config.get('nine_proxy', {})
        nine_proxy_filters = nine_proxy_config.get('filters', {})
        nine_proxy_country = nine_proxy_filters.get('country', '')
        nine_proxy_state = nine_proxy_filters.get('state', '')
        nine_proxy_city = nine_proxy_filters.get('city', '')
        nine_proxy_isp = nine_proxy_filters.get('isp', '')
        nine_proxy_plan = nine_proxy_filters.get('plan', 'all')

        # Debug вывод
        print(f"[GENERATOR DEBUG] 9Proxy настройки получены:")
        print(f"[GENERATOR DEBUG]   - nine_proxy_enabled: {nine_proxy_enabled}")
        print(f"[GENERATOR DEBUG]   - nine_proxy_ports: {nine_proxy_ports}")
        print(f"[GENERATOR DEBUG]   - nine_proxy_api_url: {nine_proxy_api_url}")
        print(f"[GENERATOR DEBUG]   - nine_proxy_strategy: {nine_proxy_strategy}")
        print(f"[GENERATOR DEBUG]   - nine_proxy_auto_rotate: {nine_proxy_auto_rotate}")
        print(f"[GENERATOR DEBUG]   - nine_proxy_country: {nine_proxy_country}")
        print(f"[GENERATOR DEBUG]   - nine_proxy_state: {nine_proxy_state}")
        print(f"[GENERATOR DEBUG]   - nine_proxy_city: {nine_proxy_city}")

        # Симуляция ввода текста
        self.simulate_typing = config.get('simulate_typing', True)
        self.typing_delay = config.get('typing_delay', 100)

        # Задержка между действиями (клики, заполнения)
        self.action_delay = config.get('action_delay', 0.5)

        # ПАРСИНГ: Извлекаем вопросы и действия из user_code
        questions_pool, pre_questions_code, post_questions_code = self._parse_user_code(user_code)

        script = self._generate_imports()
        script += self._generate_config(api_token, proxy_config, proxy_list_config, threads_count, max_iterations,
                                        nine_proxy_enabled, nine_proxy_api_url, nine_proxy_ports, nine_proxy_strategy, nine_proxy_auto_rotate,
                                        nine_proxy_country, nine_proxy_state, nine_proxy_city, nine_proxy_isp, nine_proxy_plan)
        script += self._generate_proxy_rotation()
        script += self._generate_nine_proxy_rotation()  # 🔥 9Proxy функция ротации
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
        skip_boilerplate = True  # Пропускаем всё до первого реального действия

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Пропускаем пустые строки и импорты
            if not stripped or stripped.startswith('import ') or stripped.startswith('from '):
                continue

            # 🔥 Улучшенное пропускание boilerplate
            # Пропускаем всё до первого реального действия (page.goto, page.get_by_role, etc)
            if skip_boilerplate:
                # Список паттернов которые означают начало реального кода
                real_code_patterns = [
                    'page.goto(',
                    'page.get_by_role(',
                    'page.get_by_text(',
                    'page.get_by_label(',
                    'page.locator(',
                    'page.fill(',
                    'page.click(',
                    '#pause'
                ]

                # Если это реальный код - перестаём пропускать
                if any(pattern in stripped for pattern in real_code_patterns):
                    skip_boilerplate = False
                else:
                    # Пропускаем эту строку (это boilerplate)
                    continue

            # Отслеживание popup окон - переключаем в post_section
            if 'with page.expect_popup()' in stripped or '= page1_info.value' in stripped:
                in_post_section = True
                in_questions_section = False

                # КРИТИЧНО: Проверяем предыдущую строку на наличие #auto_conditional_popup
                # Если она была добавлена в current_actions - удаляем оттуда и добавляем в post
                if current_question and current_actions:
                    last_action = current_actions[-1].strip() if current_actions else ""
                    if last_action.startswith('#auto_conditional_popup'):
                        # Удаляем маркер из действий вопроса
                        current_actions = current_actions[:-1]
                        print(f"[PARSER] DEBUG: Перемещаю #auto_conditional_popup из вопроса '{current_question}' в post_questions_lines")
                        # Добавляем маркер в post_questions (он будет обработан дальше)
                        post_questions_lines.append(last_action)

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

        # 🔥 Удалить остатки boilerplate из post_questions_lines
        filtered_post_lines = []
        for line in post_questions_lines:
            stripped = line.strip()
            # Пропускаем финальный boilerplate
            if any(pattern in stripped for pattern in [
                'with sync_playwright()',
                'run(playwright)',
                'playwright.sync_api',
                '.close()'  # Финальные close() тоже не нужны
            ]):
                continue
            filtered_post_lines.append(line)

        pre_questions_code = '\n'.join(pre_questions_lines)
        post_questions_code = '\n'.join(filtered_post_lines)

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
- Автоматическое отслеживание прогресса (не обрабатывает повторно уже выполненные строки)
"""

import csv
import json
import time
import requests
import threading
import random
import re
import os
import datetime
from tkinter import Tk, filedialog
from concurrent.futures import ThreadPoolExecutor, as_completed
from playwright.sync_api import sync_playwright, expect, TimeoutError as PlaywrightTimeout
from typing import Dict, List, Optional

'''

    def _generate_config(self, api_token: str, proxy_config: Dict, proxy_list_config: Dict, threads_count: int, max_iterations: int = None,
                         nine_proxy_enabled: bool = False, nine_proxy_api_url: str = '', nine_proxy_ports: List = [],
                         nine_proxy_strategy: str = 'sequential', nine_proxy_auto_rotate: bool = True,
                         nine_proxy_country: str = '', nine_proxy_state: str = '', nine_proxy_city: str = '',
                         nine_proxy_isp: str = '', nine_proxy_plan: str = 'all') -> str:
        config = f'''# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================

# Octobrowser API
API_BASE_URL = "https://app.octobrowser.net/api/v2/automation"
API_TOKEN = "{api_token}"
LOCAL_API_URL = "http://localhost:58888/api"

'''

        # Многопоточность и лимит итераций
        config += f'''# Многопоточность
THREADS_COUNT = {threads_count}

# Лимит итераций (None = обработать все строки CSV)
MAX_ITERATIONS = {max_iterations if max_iterations is not None else 'None'}

# Lock для синхронизации записи в CSV файл (защита от race condition)
csv_write_lock = threading.Lock()

# Thread-local storage для закрепления портов за реальными worker threads
_thread_to_port_lock = threading.Lock()
_thread_to_port_map = {}  # Mapping: thread_ident -> port_index
_next_port_index = 0  # Счетчик для назначения портов

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

        # 🔥 9Proxy конфигурация
        if nine_proxy_enabled and nine_proxy_ports:
            plan_value = '1' if nine_proxy_plan == 'premium' else '2' if nine_proxy_plan == 'free' else ''
            config += f'''# 🔥 9Proxy API Dynamic Rotation
NINE_PROXY_ENABLED = True
NINE_PROXY_API_URL = "{nine_proxy_api_url}"
NINE_PROXY_PORTS = {nine_proxy_ports}  # [6001, 6002, ...]
NINE_PROXY_STRATEGY = "{nine_proxy_strategy}"
NINE_PROXY_AUTO_ROTATE = {nine_proxy_auto_rotate}

# 9Proxy фильтры
NINE_PROXY_COUNTRY = "{nine_proxy_country}"
NINE_PROXY_STATE = "{nine_proxy_state}"
NINE_PROXY_CITY = "{nine_proxy_city}"
NINE_PROXY_ISP = "{nine_proxy_isp}"
NINE_PROXY_PLAN = "{plan_value}"

'''
        else:
            config += '''# 9Proxy отключен
NINE_PROXY_ENABLED = False
NINE_PROXY_PORTS = []

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

    def _generate_nine_proxy_rotation(self) -> str:
        """Генерация функции ротации 9Proxy"""
        return '''# ============================================================
# 9PROXY API ROTATION
# ============================================================

def rotate_proxy_for_port(port: int) -> bool:
    """
    Обновить IP для конкретного порта через 9Proxy API

    Args:
        port: Локальный порт для обновления

    Returns:
        True если успешно, False если ошибка
    """
    if not NINE_PROXY_ENABLED:
        return False

    try:
        import requests

        # Подготовить параметры запроса с фильтрами
        params = {'num': 1, 't': 2}

        # Добавить фильтры если они указаны
        if NINE_PROXY_COUNTRY:
            params['country'] = NINE_PROXY_COUNTRY
        if NINE_PROXY_STATE:
            params['state'] = NINE_PROXY_STATE
        if NINE_PROXY_CITY:
            params['city'] = NINE_PROXY_CITY
        if NINE_PROXY_ISP:
            params['isp'] = NINE_PROXY_ISP
        if NINE_PROXY_PLAN:
            params['plan'] = NINE_PROXY_PLAN

        # Логирование запроса с фильтрами
        filter_info = []
        if NINE_PROXY_COUNTRY:
            filter_info.append(f"country={NINE_PROXY_COUNTRY}")
        if NINE_PROXY_STATE:
            filter_info.append(f"state={NINE_PROXY_STATE}")
        if NINE_PROXY_CITY:
            filter_info.append(f"city={NINE_PROXY_CITY}")
        if NINE_PROXY_ISP:
            filter_info.append(f"isp={NINE_PROXY_ISP}")
        if NINE_PROXY_PLAN:
            filter_info.append(f"plan={NINE_PROXY_PLAN}")

        filter_str = ", ".join(filter_info) if filter_info else "без фильтров"
        print(f"[9PROXY] Запрос прокси для порта {port} ({filter_str})")

        # Получить новый прокси из API с фильтрами
        response = requests.get(
            f"{NINE_PROXY_API_URL}/api/proxy",
            params=params,
            timeout=5
        )

        if response.status_code != 200:
            print(f"[9PROXY] [ERROR] Ошибка получения прокси: HTTP {response.status_code}")
            return False

        data = response.json()
        if data.get('error') or not data.get('data'):
            print(f"[9PROXY] [ERROR] Нет доступных прокси с указанными фильтрами")
            return False

        proxy = data['data'][0]
        proxy_id = proxy.get('id')
        proxy_ip = proxy.get('ip', 'unknown')
        proxy_country = proxy.get('country_code', 'unknown')

        if not proxy_id:
            print(f"[9PROXY] [ERROR] Прокси не имеет ID")
            return False

        # Определить план для forward запроса
        forward_plan = NINE_PROXY_PLAN if NINE_PROXY_PLAN else '2'  # default to free

        # Переадресовать на наш порт
        forward_params = {'id': proxy_id, 'port': port, 't': 2}
        if forward_plan:
            forward_params['plan'] = forward_plan

        forward_response = requests.get(
            f"{NINE_PROXY_API_URL}/api/forward",
            params=forward_params,
            timeout=5
        )

        if forward_response.status_code == 200:
            forward_data = forward_response.json()
            if not forward_data.get('error'):
                print(f"[9PROXY] [OK] Порт {port} обновлен -> {proxy_ip} ({proxy_country}) [ID: {proxy_id}]")
                return True
            else:
                print(f"[9PROXY] [ERROR] Forward ошибка: {forward_data.get('message')}")
                return False
        else:
            print(f"[9PROXY] [ERROR] Ошибка forward: HTTP {forward_response.status_code}")
            return False

    except Exception as e:
        print(f"[9PROXY] [ERROR] Ошибка ротации порта {port}: {e}")
        return False

def get_nine_proxy_for_thread(thread_id: int) -> Optional[Dict]:
    """
    Получить конфигурацию 9Proxy для потока

    Использует реальный worker thread ID для постоянного назначения портов.
    Каждый worker thread получает свой порт при первом вызове и использует его всегда.

    Args:
        thread_id: ID потока из task (игнорируется, используется реальный thread)

    Returns:
        Dict с настройками прокси для Octobrowser или None
    """
    if not NINE_PROXY_ENABLED or not NINE_PROXY_PORTS:
        return None

    import threading
    global _thread_to_port_lock, _thread_to_port_map, _next_port_index

    # Получить реальный ID текущего worker thread
    real_thread_id = threading.current_thread().ident

    # Потокобезопасно проверить/назначить порт для этого worker thread
    with _thread_to_port_lock:
        if real_thread_id not in _thread_to_port_map:
            # Первый вызов для этого worker thread - назначаем порт
            port_index = _next_port_index % len(NINE_PROXY_PORTS)
            _thread_to_port_map[real_thread_id] = port_index
            _next_port_index += 1
            print(f"[9PROXY MAPPING] Worker Thread {real_thread_id} -> Port Index {port_index} (ПЕРВОЕ НАЗНАЧЕНИЕ)")
        else:
            # Worker thread уже имеет назначенный порт
            port_index = _thread_to_port_map[real_thread_id]

    port = NINE_PROXY_PORTS[port_index]

    # Детальное логирование
    print(f"[9PROXY MAPPING] Worker Thread {real_thread_id} -> Port Index: {port_index} -> Port: {port}")

    return {
        'type': 'socks5',
        'host': '127.0.0.1',
        'port': str(port),
        'login': '',
        'password': ''
    }

def initialize_nine_proxy_ports() -> bool:
    """
    Проверить доступность портов 9Proxy

    9Proxy API возвращает готовые локальные порты (127.0.0.1:6000-6009),
    которые УЖЕ переадресуют на реальные IP. Не нужно вручную назначать прокси.

    Returns:
        True если успешно, False если ошибка
    """
    if not NINE_PROXY_ENABLED or not NINE_PROXY_PORTS:
        return True

    print(f"[9PROXY INIT] Проверка {len(NINE_PROXY_PORTS)} портов...")
    print(f"[9PROXY INIT] API URL: {NINE_PROXY_API_URL}")
    print(f"[9PROXY INIT] Порты: {NINE_PROXY_PORTS}")

    try:
        import requests

        # Просто проверим что API доступен
        response = requests.get(
            f"{NINE_PROXY_API_URL}/api/proxy",
            params={'num': 1, 't': 2},
            timeout=5
        )

        if response.status_code == 200:
            print(f"[9PROXY INIT] [OK] API доступен")

            # Проинициализировать каждый порт с правильными фильтрами
            print(f"[9PROXY INIT] Инициализация портов с фильтрами...")
            for port in NINE_PROXY_PORTS:
                print(f"[9PROXY INIT] Настройка порта {port}...")
                rotate_proxy_for_port(port)

            print(f"[9PROXY INIT] [OK] Все порты настроены")
            return True
        else:
            print(f"[9PROXY INIT] [WARNING] API недоступен: HTTP {response.status_code}")
            return False

    except Exception as e:
        print(f"[9PROXY INIT] [ERROR] Ошибка подключения к API: {e}")
        return False

'''

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
    """Получить прокси для потока (приоритет: 9Proxy → Список прокси → Единый прокси)"""
    global _proxy_counter

    # 🔥 Приоритет 1: 9Proxy API (если включен)
    if NINE_PROXY_ENABLED and NINE_PROXY_PORTS:
        # Преобразуем thread_id из 1-based в 0-based для индексации
        thread_index = thread_id - 1
        nine_proxy_dict = get_nine_proxy_for_thread(thread_index)
        if nine_proxy_dict:
            print(f"[9PROXY ASSIGN] Thread {thread_id} (1-based), Iteration {iteration_number} -> Port {nine_proxy_dict['port']}")
            return nine_proxy_dict

    # Приоритет 2: Список прокси (если USE_PROXY_LIST включен)
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
                locator = page.get_by_test_id(by_test_id)
                print(f"[SCROLL_SEARCH] [DEBUG] Ищу по test_id='{by_test_id}'")
            elif by_role:
                locator = page.get_by_role(by_role, name=name)
                print(f"[SCROLL_SEARCH] [DEBUG] Ищу по role='{by_role}', name='{name}'")
            else:
                locator = page.locator(selector)
                print(f"[SCROLL_SEARCH] [DEBUG] Ищу по selector='{selector}'")

            # Проверяем сколько элементов найдено
            count = locator.count()
            print(f"[SCROLL_SEARCH] [DEBUG] Найдено элементов: {count}")

            if count == 0:
                print(f"[SCROLL_SEARCH] [DEBUG] Элементов не найдено!")
                return False

            # Проверяем ВСЕ элементы, не только first
            for i in range(count):
                element = locator.nth(i)
                print(f"[SCROLL_SEARCH] [DEBUG] Проверяю элемент #{i} is_visible(timeout=5000)...")
                try:
                    if element.is_visible(timeout=5000):
                        print(f"[SCROLL_SEARCH] [DEBUG] Элемент #{i} ВИДИМЫЙ! Использую его.")
                        # Прокрутить к элементу
                        element.scroll_into_view_if_needed(timeout=2000)
                        time.sleep(0.5)
                        return True
                    else:
                        print(f"[SCROLL_SEARCH] [DEBUG] Элемент #{i} невидимый, пробую следующий...")
                except:
                    print(f"[SCROLL_SEARCH] [DEBUG] Элемент #{i} timeout/error, пробую следующий...")
                    continue

            print(f"[SCROLL_SEARCH] [DEBUG] Все {count} элементов проверены - все невидимые")
            return False

        except Exception as e:
            print(f"[SCROLL_SEARCH] [DEBUG] Exception: {type(e).__name__}: {str(e)[:100]}")
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
# ЗАГРУЗКА CSV И ОТСЛЕЖИВАНИЕ ПРОГРЕССА
# ============================================================

def mark_row_in_progress(csv_file_path: str, row_index: int, fieldnames: list):
    """
    Помечает строку как взятую в работу - ставит звездочку (*) в колонку с индексом 1

    ПОТОКОБЕЗОПАСНО: использует csv_write_lock для синхронизации

    Args:
        csv_file_path: Путь к CSV файлу
        row_index: Индекс строки в CSV (0-based, не считая заголовок)
        fieldnames: Список имен полей (заголовков)
    """
    # КРИТИЧНО: блокируем доступ к файлу для избежания race condition
    with csv_write_lock:
        try:
            # Читаем весь CSV
            all_rows = []
            actual_fieldnames = []

            with open(csv_file_path, 'r', encoding='utf-8', newline='') as f:
                reader = csv.DictReader(f)
                actual_fieldnames = list(reader.fieldnames) if reader.fieldnames else fieldnames
                all_rows = list(reader)

            # Проверяем что файл не пустой
            if not all_rows:
                print(f"[MARK] [ERROR] CSV файл пустой!")
                return

            # Проверяем что индекс валидный
            if row_index < 0 or row_index >= len(all_rows):
                print(f"[MARK] [ERROR] Неверный индекс строки: {row_index} (всего строк: {len(all_rows)})")
                return

            # Получаем имя второго поля (индекс 1)
            if len(actual_fieldnames) < 2:
                print(f"[MARK] [ERROR] CSV должен иметь минимум 2 колонки")
                return

            second_field_name = actual_fieldnames[1]

            # Ставим звездочку в колонке с индексом 1
            all_rows[row_index][second_field_name] = "*"

            # Перезаписываем файл
            with open(csv_file_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=actual_fieldnames)
                writer.writeheader()
                writer.writerows(all_rows)

            print(f"[MARK] [OK] Строка {row_index + 1} помечена как взятая в работу (*)")

        except Exception as e:
            print(f"[MARK] [ERROR] Не удалось пометить строку: {e}")
            import traceback
            traceback.print_exc()


def load_csv_data() -> tuple:
    """
    Загрузить данные из CSV файла через диалог и отфильтровать уже обработанные

    Обработанные строки определяются по наличию звездочки (*) в колонке с индексом 1

    Returns:
        Tuple (csv_file_path, fieldnames, unprocessed_data)
    """
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
        return ("", [], [])

    if not os.path.exists(csv_file_path):
        print(f"[CSV] [ERROR] Файл не существует: {csv_file_path}")
        return ("", [], [])

    print(f"[CSV] Загрузка файла: {csv_file_path}")

    # Загружаем CSV данные
    all_data = []
    fieldnames = []

    try:
        with open(csv_file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = list(reader.fieldnames) if reader.fieldnames else []
            all_data = list(reader)

        print(f"[CSV] [OK] Загружено {len(all_data)} строк из CSV")
        print(f"[CSV] Заголовки: {', '.join(fieldnames)}")

        # Проверяем что есть минимум 2 колонки
        if len(fieldnames) < 2:
            print(f"[CSV] [ERROR] CSV должен иметь минимум 2 колонки")
            return ("", [], [])

    except Exception as e:
        print(f"[CSV] [ERROR] Ошибка загрузки: {e}")
        return ("", [], [])

    # Имя второй колонки (индекс 1) - здесь проверяем звездочку
    second_field_name = fieldnames[1]
    print(f"[CSV] Колонка маркера обработки: '{second_field_name}' (индекс 1)")

    # Фильтруем строки со звездочкой в колонке индекс 1
    unprocessed_data = []
    processed_count = 0

    for csv_row_idx, data_row in enumerate(all_data):
        # Сохраняем индекс строки в CSV (0-based, не считая заголовок)
        data_row['__csv_row_index__'] = csv_row_idx

        # Проверяем есть ли звездочка в колонке с индексом 1
        marker_value = data_row.get(second_field_name, "").strip()

        if marker_value == "*":
            processed_count += 1
            continue  # Пропускаем строки со звездочкой

        unprocessed_data.append(data_row)

    print(f"[CSV] Пропущено строк со звездочкой (*): {processed_count}")
    print(f"[CSV] К обработке: {len(unprocessed_data)} новых строк")

    return (csv_file_path, fieldnames, unprocessed_data)


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
        # Конвертируем typing_delay из миллисекунд в секунды для Playwright
        typing_delay_sec = self.typing_delay / 1000
        action_delay_sec = self.action_delay

        code = '''# ============================================================
# ФУНКЦИЯ МОМЕНТАЛЬНОГО ПОИСКА И ОТВЕТА НА ВОПРОСЫ
# ============================================================

def normalize_text(text: str) -> str:
    """Нормализует текст для сравнения - убирает спецсимволы, лишние пробелы"""
    import re
    # Убираем ВСЕ знаки препинания, включая Unicode апострофы и кавычки
    # ASCII: ' " `
    # Unicode: ' ' " " – — (типографские кавычки, апострофы, тире)
    # Дефис в конце класса символов, чтобы избежать SyntaxWarning
    text = re.sub(r'[*?.!,;:\\'\\\"''""`()-]', '', text)
    # Убираем множественные пробелы
    text = re.sub(r'\\s+', ' ', text)
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
        print(f"[SEARCH] Длина нормализованного: {len(normalized_question)}")

    best_match = None
    best_ratio = 0

    for pool_key in pool.keys():
        normalized_key = normalize_text(pool_key)

        # Точное совпадение нормализованных
        if normalized_question == normalized_key:
            if debug:
                print(f"[SEARCH] [OK] НАЙДЕНО (точное совпадение): '{pool_key}'")
            return pool_key

        # Частичное совпадение - pool_key содержится в question_text или наоборот
        if normalized_key in normalized_question or normalized_question in normalized_key:
            # Проверяем что это действительно похожие вопросы (>45% совпадение длины)
            len_ratio = min(len(normalized_key), len(normalized_question)) / max(len(normalized_key), len(normalized_question))

            if debug:
                print(f"[SEARCH] Проверка '{pool_key[:60]}...': ratio={len_ratio:.2f}")

            if len_ratio > 0.45:  # Снижен порог с 0.50 до 0.45
                if len_ratio > best_ratio:
                    best_match = pool_key
                    best_ratio = len_ratio

    if best_match:
        if debug:
            print(f"[SEARCH] [OK] НАЙДЕНО (частичное, ratio={best_ratio:.2f}): '{best_match}'")
        return best_match

    # ЖЕСТКОЕ РЕШЕНИЕ: Fallback поиск по ключевым словам (если fuzzy matching не сработал)
    if debug:
        print(f"[SEARCH] Fuzzy matching не нашел, пробую поиск по ключевым словам...")

    # Извлекаем ключевые слова (слова длиной > 3 символов)
    question_words = set([w for w in normalized_question.split() if len(w) > 3])

    if debug:
        print(f"[SEARCH] Ключевые слова в вопросе: {question_words}")

    best_keyword_match = None
    best_keyword_score = 0

    for pool_key in pool.keys():
        normalized_key = normalize_text(pool_key)
        key_words = set([w for w in normalized_key.split() if len(w) > 3])

        # Считаем процент совпадающих ключевых слов
        if question_words and key_words:
            common_words = question_words & key_words  # Пересечение
            keyword_score = len(common_words) / len(question_words)  # Процент от вопроса

            if debug and keyword_score > 0.3:
                print(f"[SEARCH] Проверка '{pool_key[:60]}...': keyword_score={keyword_score:.2f}, common={common_words}")

            # Если совпадает 40%+ ключевых слов - это кандидат
            if keyword_score > 0.40:
                if keyword_score > best_keyword_score:
                    best_keyword_match = pool_key
                    best_keyword_score = keyword_score

    if best_keyword_match:
        if debug:
            print(f"[SEARCH] [OK] НАЙДЕНО (по ключевым словам, score={best_keyword_score:.2f}): '{best_keyword_match}'")
        return best_keyword_match

    if debug:
        print(f"[SEARCH] [FAIL] НЕ НАЙДЕНО")
        print(f"[SEARCH] Доступные ключи в пуле (всего {len(pool)}):")
        # Показываем ВСЕ вопросы с их нормализованной версией И len_ratio
        for i, key in enumerate(list(pool.keys()), 1):
            normalized = normalize_text(key)
            # Считаем ratio для диагностики
            if normalized_key in normalized_question or normalized_question in normalized:
                ratio = min(len(normalized), len(normalized_question)) / max(len(normalized), len(normalized_question))
                print(f"[SEARCH]   {i}. ratio={ratio:.2f} '{key}' -> '{normalized}'")
            else:
                print(f"[SEARCH]   {i}. ratio=N/A '{key}' -> '{normalized}'")

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

    # КРИТИЧНО: Ждем полной загрузки страницы перед поиском вопросов
    print(f"[DYNAMIC_QA] Ожидание загрузки страницы...")
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except:
        print(f"[DYNAMIC_QA] [WARN] Таймаут networkidle, продолжаю...")
    time.sleep(2)  # Дополнительная пауза для рендеринга

    # DEBUG: показываем ВСЕ вопросы ИЗ ПУЛА (чтобы видеть все что распарсилось)
    print(f"[DYNAMIC_QA] [DEBUG] Все вопросы в пуле:")
    for i, (key, value) in enumerate(list(QUESTIONS_POOL.items()), 1):
        actions_count = len(value.get('actions', []))
        print(f"[DYNAMIC_QA]   {i}. '{key}' (действий: {actions_count})")

    # Цикл поиска и ответа на вопросы
    while answered_count < max_questions:
        # КРИТИЧНО: Ждем появления хотя бы одного видимого heading элемента
        try:
            print(f"[DYNAMIC_QA] Ожидание появления heading элементов...")
            page.wait_for_selector("role=heading", state="visible", timeout=10000)
            time.sleep(1)  # Дополнительная пауза для стабильности
        except Exception as e:
            print(f"[DYNAMIC_QA] [WARN] Таймаут ожидания heading: {e}")

        # Найти все heading на странице
        try:
            headings = page.get_by_role("heading").all()
            print(f"[DYNAMIC_QA] Найдено {len(headings)} заголовков на странице")
        except Exception as e:
            print(f"[DYNAMIC_QA] [ERROR] Не удалось получить headings: {e}")
            break

        found_new_question = False
        visible_headings_count = 0

        # Проверить каждый heading
        for idx, heading in enumerate(headings):
            try:
                # ПРОВЕРКА ВИДИМОСТИ: пропускаем невидимые элементы
                is_visible = False
                try:
                    is_visible = heading.is_visible()
                except:
                    pass  # Если проверка failed - считаем невидимым

                if not is_visible:
                    continue  # Пропускаем невидимые headings

                visible_headings_count += 1

                # Получить текст вопроса с агрессивным retry (элемент может быть не готов)
                question_text = ""
                max_retries = 5  # Увеличено с 3 до 5 для максимальной стабильности

                for attempt in range(max_retries):
                    try:
                        # КРИТИЧНО: Скроллим к элементу чтобы он был в viewport
                        heading.scroll_into_view_if_needed(timeout=2000)

                        # Дополнительная пауза после скролла для рендеринга
                        time.sleep(0.3)

                        question_text = heading.inner_text().strip()

                        # Если текст есть и не пустой - отлично
                        if question_text and len(question_text) >= 3:
                            break

                        # Если пустой и это не последняя попытка - ждем дольше
                        if attempt < max_retries - 1:
                            wait_time = 1.5 * (attempt + 1)  # 1.5s, 3s, 4.5s, 6s
                            time.sleep(wait_time)
                    except Exception as e:
                        if attempt < max_retries - 1:
                            time.sleep(1.5)
                        else:
                            pass  # Последняя попытка failed - пропускаем

                # DEBUG: показываем все heading что находим
                if answered_count == 0 and visible_headings_count <= 5:  # Первые 5 видимых
                    print(f"[DYNAMIC_QA] [DEBUG] Обрабатываю heading #{visible_headings_count} (visible): '{question_text}'")

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
                                print(f"[DYNAMIC_QA]   -> Кликаю кнопку: {button_text}")
                                page.get_by_role("button", name=button_text).click(timeout=10000)
                                time.sleep(__ACTION_DELAY__)

                            # Заполнение текстового поля
                            elif action_type == 'textbox_fill':
                                field_name = action.get('field_name')
                                data_key = action.get('data_key')
                                static_value = action.get('value')

                                value = data_row.get(data_key, static_value) if data_key else static_value

                                print(f"[DYNAMIC_QA]   -> Заполняю поле '{field_name}': {value}")
                                textbox = page.get_by_role("textbox", name=field_name).first
                                textbox.click(timeout=5000)
                                textbox.press_sequentially(value, delay=__TYPING_DELAY__)
                                time.sleep(__ACTION_DELAY__)

                            # Нажатие клавиши
                            elif action_type == 'press_key':
                                key = action.get('key')
                                print(f"[DYNAMIC_QA]   -> Нажимаю клавишу: {key}")
                                page.keyboard.press(key)
                                time.sleep(__ACTION_DELAY__)

                            # Клик по locator
                            elif action_type == 'locator_click':
                                selector = action.get('selector')
                                print(f"[DYNAMIC_QA]   -> Кликаю элемент: {selector[:50]}...")
                                page.locator(selector).first.click(timeout=10000)
                                time.sleep(__ACTION_DELAY__)

                        except Exception as e:
                            print(f"[DYNAMIC_QA]   [ERROR] Не удалось выполнить действие: {e}")
                            # Продолжаем выполнение других действий

                    # Отметить вопрос как отвеченный
                    answered_questions.add(question_text)
                    answered_count += 1
                    found_new_question = True

                    print(f"[DYNAMIC_QA] [OK] Вопрос обработан ({answered_count}/{max_questions})")

                    # Пауза для загрузки следующего вопроса (увеличена до 4 сек для стабильности)
                    print(f"[DYNAMIC_QA] Ожидание загрузки следующего вопроса (4 сек)...")
                    time.sleep(4)

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
            print(f"[DYNAMIC_QA] Видимых headings на этой итерации: {visible_headings_count}")

            # DEBUG: показываем первые 5 heading что были на странице
            try:
                headings = page.get_by_role("heading").all()
                if len(headings) > 0:
                    print(f"[DYNAMIC_QA] [DEBUG] Примеры heading на странице (всего {len(headings)}):")
                    shown = 0
                    for i, h in enumerate(headings):
                        if shown >= 5:
                            break
                        try:
                            is_vis = h.is_visible()
                            text = h.inner_text().strip()
                            visibility_mark = "[VISIBLE]" if is_vis else "[HIDDEN]"
                            print(f"[DYNAMIC_QA]   {i+1}. {visibility_mark} '{text}'")
                            shown += 1
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

        # Подставляем реальные значения вместо плейсхолдеров
        code = code.replace('__TYPING_DELAY__', str(typing_delay_sec))
        code = code.replace('__ACTION_DELAY__', str(action_delay_sec))

        return code

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

        # 🌐 Парсинг и генерация network capture кода
        # ВСЕГДА генерируем базовый код для сохранения validate запросов
        network_capture_code = ""
        network_return_code = ""

        # Парсим паттерны если они есть
        parsed_patterns = []
        if network_capture_patterns and len(network_capture_patterns) > 0:
            # Парсим паттерны формата "pattern:field1,field2" или просто "pattern"
            current_pattern = None
            current_fields = []

            try:
                for item in network_capture_patterns:
                    # Пропускаем не-строковые элементы (на случай ошибки конфигурации)
                    if not isinstance(item, str):
                        print(f"[WARNING] network_capture_patterns содержит не-строковый элемент: {type(item)} = {item}")
                        continue

                    if ':' in item:
                        # Новый паттерн с полями: "validate:bind_profile.drivers.0.model"
                        if current_pattern:
                            # Сохраняем предыдущий паттерн
                            parsed_patterns.append({'pattern': current_pattern, 'fields': current_fields})

                        pattern, field = item.split(':', 1)
                        current_pattern = pattern.strip()
                        current_fields = [field.strip()]
                    elif current_pattern:
                        # Продолжение полей для текущего паттерна
                        current_fields.append(item.strip())
                    else:
                        # Паттерн без полей
                        parsed_patterns.append({'pattern': item.strip(), 'fields': []})

                # Не забываем последний паттерн
                if current_pattern:
                    parsed_patterns.append({'pattern': current_pattern, 'fields': current_fields})

            except Exception as e:
                print(f"[ERROR] Ошибка парсинга network_capture_patterns: {e}")
                print(f"[ERROR] network_capture_patterns = {network_capture_patterns}")
                parsed_patterns = []

        patterns_str = json.dumps(parsed_patterns, ensure_ascii=False)

        # ВСЕГДА генерируем код сохранения (независимо от наличия паттернов)
        network_capture_code = f'''
        # ============================================================
        # 🌐 ЗАХВАТ NETWORK RESPONSES (Developer Tools) + СОХРАНЕНИЕ VALIDATE В ФАЙЛЫ
        # ============================================================
        captured_data = {{}}
        extracted_fields = {{}}  # Словарь для извлеченных полей: {{field_name: value}}
        capture_patterns_config = {patterns_str}
        validate_counter = 0  # Счетчик validate запросов
        total_responses_counter = 0  # Счетчик всех обработанных responses для диагностики

        # Создаем папку для сохранения network responses
        network_responses_dir = os.path.join(os.getcwd(), "network_responses")
        os.makedirs(network_responses_dir, exist_ok=True)
        print(f"[NETWORK_CAPTURE] Папка для сохранения: {{network_responses_dir}}", flush=True)

        def save_network_response_to_file(pattern, url, status, json_data, iteration_num, counter=None):
            """
            Сохраняет полный response в отдельный JSON файл

            Args:
                pattern: Паттерн URL (например, 'validate')
                url: Полный URL запроса
                status: HTTP статус
                json_data: Данные response в формате JSON
                iteration_num: Номер итерации
                counter: Порядковый номер запроса (опционально)
            """
            try:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                if counter is not None:
                    filename = f"{{pattern}}_{{counter:03d}}_iteration_{{iteration_num}}_{{timestamp}}.json"
                else:
                    filename = f"{{pattern}}_iteration_{{iteration_num}}_{{timestamp}}.json"
                filepath = os.path.join(network_responses_dir, filename)

                # Формируем полный объект для сохранения
                full_response = {{
                    'url': url,
                    'status': status,
                    'pattern': pattern,
                    'iteration': iteration_num,
                    'timestamp': timestamp,
                    'response_data': json_data
                }}

                # Сохраняем в файл с красивым форматированием
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(full_response, f, ensure_ascii=False, indent=2)

                print(f"[NETWORK_CAPTURE] [OK] Response сохранен в файл: {{filename}}", flush=True)
                return filepath
            except Exception as e:
                print(f"[NETWORK_CAPTURE] [ERROR] Ошибка сохранения в файл: {{e}}", flush=True)
                return None

        def get_nested_value(data, field_path):
            """
            Извлекает значение по пути field.subfield.subsubfield
            Поддерживает массивы: field.array.0.subfield
            """
            keys = field_path.split('.')
            value = data
            for key in keys:
                # Проверяем, является ли ключ числовым индексом для массива
                if isinstance(value, list):
                    try:
                        index = int(key)
                        if 0 <= index < len(value):
                            value = value[index]
                        else:
                            return None
                    except ValueError:
                        return None
                elif isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return None
            return value

        def handle_response(response):
            """Обработчик network responses - ВСЕГДА сохраняет ВСЕ validate запросы без остановки"""
            nonlocal validate_counter, total_responses_counter  # Доступ к счетчикам из внешней области

            try:
                url = response.url
                total_responses_counter += 1  # Подсчитываем все responses

                # ДИАГНОСТИКА: Логируем ВСЕ API запросы для отладки
                if '/api/' in url or '/bind' in url or response.request.resource_type == 'xhr':
                    print(f"[NETWORK_DEBUG] API Request: {{response.status}} {{url}}", flush=True)

                # 🔥 ЖЕСТКАЯ ПРОВЕРКА: Если это запрос validate - ОБЯЗАТЕЛЬНО сохраняем в файл
                # ВАЖНО: Записываем ВСЕ validate запросы, без остановки!
                # Проверяем:
                # 1. Общая проверка: 'validate' в URL
                # 2. ЖЕСТКИЙ URL: конкретный путь bind_api/web/validate
                # 3. Домены: joinroot.com, joinroci.com, compare.com
                is_validate = (
                    'validate' in url.lower() or
                    'bind_api/web/validate' in url or
                    ('joinroot.com' in url and '/bind' in url) or
                    ('joinroci.com' in url and '/bind' in url) or
                    ('compare.com' in url and '/validate' in url)
                )

                if is_validate:
                    validate_counter += 1
                    print(f"[NETWORK_CAPTURE] [VALIDATE #{{validate_counter}}] Перехвачен validate запрос: {{url}}", flush=True)
                    try:
                        json_data = response.json()
                        saved_file = save_network_response_to_file(
                            pattern='validate',
                            url=url,
                            status=response.status,
                            json_data=json_data,
                            iteration_num=iteration_number,
                            counter=validate_counter
                        )
                        if saved_file:
                            print(f"[NETWORK_CAPTURE] [OK] Validate #{{validate_counter}} сохранен: {{saved_file}}", flush=True)
                        else:
                            print(f"[NETWORK_CAPTURE] [ERROR] Validate #{{validate_counter}} НЕ сохранен!", flush=True)
                    except Exception as e:
                        print(f"[NETWORK_CAPTURE] [ERROR] Ошибка сохранения validate #{{validate_counter}}: {{e}}", flush=True)

                # Дополнительно проверяем паттерны (если они заданы)
                if capture_patterns_config:
                    for pattern_config in capture_patterns_config:
                        pattern = pattern_config.get('pattern', '')
                        fields = pattern_config.get('fields', [])

                        if pattern.lower() in url.lower():
                            print(f"[NETWORK_CAPTURE] Перехвачен ответ по паттерну '{{pattern}}': {{url}}", flush=True)
                            try:
                                # Получаем JSON данные из ответа
                                json_data = response.json()

                                # Сохраняем полные данные в памяти для отладки
                                if pattern not in captured_data:
                                    captured_data[pattern] = []
                                captured_data[pattern].append({{
                                    'url': url,
                                    'status': response.status,
                                    'data': json_data
                                }})

                                # 🔥 ИЗВЛЕЧЕНИЕ КОНКРЕТНЫХ ПОЛЕЙ
                                if fields:
                                    print(f"[NETWORK_CAPTURE] Извлекаю поля: {{fields}}", flush=True)
                                    for field in fields:
                                        field_value = get_nested_value(json_data, field)
                                        if field_value is not None:
                                            extracted_fields[field] = field_value
                                            print(f"[NETWORK_CAPTURE]   {{field}} = {{field_value}}", flush=True)
                                        else:
                                            print(f"[NETWORK_CAPTURE]   {{field}} не найдено в response", flush=True)
                                else:
                                    # Если полей нет - сохраняем весь response
                                    print(f"[NETWORK_CAPTURE] Полный response сохранен для '{{pattern}}'", flush=True)
                                    print(f"[NETWORK_CAPTURE] Preview: {{str(json_data)[:200]}}...", flush=True)
                            except Exception as e:
                                print(f"[NETWORK_CAPTURE] Не удалось распарсить JSON: {{e}}", flush=True)
                            break
            except Exception as e:
                # Игнорируем ошибки при обработке - не должны ломать основной флоу
                pass

        # Регистрируем обработчик для всех network responses на главной странице
        page.on("response", handle_response)
        print("[NETWORK_CAPTURE] Обработчик зарегистрирован для page", flush=True)

        # 🔥 КРИТИЧНО: Регистрируем обработчик для ВСЕХ новых popup страниц
        def handle_new_page(new_page):
            """Автоматически подключает обработчик к новым popup окнам (page1, page2, page3)"""
            print(f"[NETWORK_CAPTURE] [NEW_PAGE] Новая страница обнаружена, подключаю обработчик response", flush=True)
            new_page.on("response", handle_response)

        page.context.on("page", handle_new_page)
        print("[NETWORK_CAPTURE] Обработчик для popup страниц зарегистрирован", flush=True)
        print(f"[NETWORK_CAPTURE] Паттерны и поля: {{capture_patterns_config}}", flush=True)
'''

        # Единый return code (всегда возвращаем extracted_fields, даже если они пустые)
        network_return_code = '''
        # Ожидание финальных validate запросов (они приходят асинхронно после последних действий)
        print("[NETWORK_CAPTURE] Ожидание финальных validate запросов (20 сек)...", flush=True)
        page2.wait_for_timeout(20000)

        # 🌐 Вывод захваченных данных (если есть)
        print(f"\\n[NETWORK_CAPTURE] === ИТОГОВЫЕ ДАННЫЕ ===")
        print(f"[NETWORK_CAPTURE] Обработано network responses: {{total_responses_counter}}", flush=True)
        print(f"[NETWORK_CAPTURE] Всего validate запросов записано: {{validate_counter}}", flush=True)

        if captured_data:
            for pattern, entries in captured_data.items():
                print(f"[NETWORK_CAPTURE] Паттерн '{{pattern}}': {{len(entries)}} ответов")
                for i, entry in enumerate(entries, 1):
                    print(f"[NETWORK_CAPTURE]   {{i}}. URL: {{entry['url']}}")
                    print(f"[NETWORK_CAPTURE]      Status: {{entry['status']}}")
                    print(f"[NETWORK_CAPTURE]      Data keys: {{list(entry['data'].keys()) if isinstance(entry['data'], dict) else 'Not a dict'}}")

        if extracted_fields:
            print(f"[NETWORK_CAPTURE] Извлеченные поля: {{extracted_fields}}", flush=True)

        print(f"[ITERATION {{iteration_number}}] [OK] Завершено успешно")
        return (True, extracted_fields)
'''

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

    Returns:
        Tuple (success: bool, extracted_fields: dict)
    """
    print(f"\\n{'='*60}")
    print(f"[ITERATION {{iteration_number}}] Начало")
    print(f"{'='*60}")

    try:{network_capture_code}
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
{network_return_code}
    except Exception as e:
        print(f"[ITERATION {{iteration_number}}] [ERROR] Ошибка: {{e}}")
        import traceback
        traceback.print_exc()
        return (False, {{}})


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
        """
        import re  # Импортируем в начале функции, т.к. используется в нескольких местах

        if not code or not code.strip():
            return code

        # ВАЖНО: Заменяем .fill() на .press_sequentially() с симуляцией ввода
        if self.simulate_typing and '.fill(' in code:
            typing_delay_sec = self.typing_delay / 1000  # Конвертация мс в секунды
            # Паттерн: .fill("text") или .fill('text') или .fill(variable)
            pattern = r'\.fill\(([^)]+)\)'
            replacement = f'.press_sequentially(\\1, delay={typing_delay_sec})'
            code = re.sub(pattern, replacement, code)

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
        conditional_popup_next = False  # Флаг для #auto_conditional_popup
        current_page_context = 'page'  # Отслеживание текущего контекста страницы (page, page1, page2, page3)

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

            # Отслеживание переключения контекста страницы
            if '= page1_info.value' in stripped:
                current_page_context = 'page1'
                result_lines.append(line)
                i += 1
                continue
            elif '= page2_info.value' in stripped:
                current_page_context = 'page2'
                # Добавляем дебаг маркер для page2
                indent_str = ' ' * current_indent
                result_lines.append(line)
                result_lines.append(f"{indent_str}print('[PAGE2_DEBUG] ===== НАЧАЛО РАБОТЫ С PAGE2 =====', flush=True)")
                i += 1
                continue
            elif '= page3_info.value' in stripped:
                current_page_context = 'page3'
                # Добавляем дебаг маркер для page3
                indent_str = ' ' * current_indent
                result_lines.append(line)
                result_lines.append(f"{indent_str}print('[PAGE3_DEBUG] ===== НАЧАЛО РАБОТЫ С PAGE3 =====', flush=True)")
                i += 1
                continue

            # Отслеживаем вход в with блок
            if stripped.startswith('with '):
                # Проверяем, является ли это условным popup
                if conditional_popup_next and 'page.expect_popup()' in stripped:
                    # УНИВЕРСАЛЬНАЯ ОБРАБОТКА УСЛОВНОГО POPUP
                    indent_str = ' ' * current_indent

                    # Извлекаем переменную popup (page1_info, page2_info, etc.)
                    popup_var_match = re.search(r'with\s+(\w+)\.expect_popup\(\)\s+as\s+(\w+):', stripped)
                    if popup_var_match:
                        page_var = popup_var_match.group(1)  # page
                        popup_info_var = popup_var_match.group(2)  # page1_info

                        # Извлекаем имя результирующей переменной (page1, page2, etc.) из следующих строк
                        result_page_var = None
                        button_name = None
                        button_selector = None

                        # Ищем следующие несколько строк для извлечения кнопки и результата
                        for j in range(i + 1, min(i + 10, len(lines))):
                            next_line = lines[j].strip()

                            # Извлекаем кнопку из клика
                            if '.click()' in next_line and button_name is None:
                                # Пробуем get_by_role с name
                                btn_match = re.search(r'get_by_role\(["\']button["\']\s*,\s*name=["\']([^"\']+)["\']\)', next_line)
                                if btn_match:
                                    button_name = btn_match.group(1)
                                    button_selector = f'{page_var}.get_by_role("button", name="{button_name}")'

                            # Извлекаем результирующую переменную (page1 = page1_info.value)
                            if f'= {popup_info_var}.value' in next_line:
                                result_match = re.search(r'(\w+)\s*=\s*' + re.escape(popup_info_var) + r'\.value', next_line)
                                if result_match:
                                    result_page_var = result_match.group(1)
                                break

                        if button_name and result_page_var:
                            # Генерируем универсальный код для условного popup
                            result_lines.append(f"{indent_str}# УНИВЕРСАЛЬНАЯ ОБРАБОТКА УСЛОВНОГО POPUP (после заполнения телефона)")
                            result_lines.append(f"{indent_str}{result_page_var} = None")
                            result_lines.append(f"{indent_str}max_popup_attempts = 2")
                            result_lines.append(f"{indent_str}for popup_attempt in range(max_popup_attempts):")
                            result_lines.append(f"{indent_str}    try:")
                            result_lines.append(f"{indent_str}        print(f'[CONDITIONAL_POPUP] Попытка {{popup_attempt + 1}}/{{max_popup_attempts}} открыть popup...', flush=True)")
                            result_lines.append(f"{indent_str}        with {page_var}.expect_popup(timeout=8000) as {popup_info_var}:")
                            result_lines.append(f"{indent_str}            if popup_attempt == 0:")
                            result_lines.append(f"{indent_str}                # Первая попытка - обычный клик")
                            result_lines.append(f"{indent_str}                {button_selector}.click()")
                            result_lines.append(f"{indent_str}            else:")
                            result_lines.append(f"{indent_str}                # Вторая попытка - ищем кнопку на промежуточной странице")
                            result_lines.append(f"{indent_str}                print('[CONDITIONAL_POPUP] Ищу кнопку на промежуточной странице...', flush=True)")
                            result_lines.append(f"{indent_str}                try:")
                            result_lines.append(f"{indent_str}                    # Ждем появления кнопки на промежуточной странице")
                            result_lines.append(f"{indent_str}                    button = {button_selector}")
                            result_lines.append(f"{indent_str}                    button.wait_for(state='visible', timeout=5000)")
                            result_lines.append(f"{indent_str}                    print('[CONDITIONAL_POPUP] Кнопка найдена на промежуточной странице', flush=True)")
                            result_lines.append(f"{indent_str}                    button.click()")
                            result_lines.append(f"{indent_str}                except Exception as btn_err:")
                            result_lines.append(f"{indent_str}                    print(f'[CONDITIONAL_POPUP] Кнопка не найдена: {{btn_err}}', flush=True)")
                            result_lines.append(f"{indent_str}                    raise")
                            result_lines.append(f"")
                            result_lines.append(f"{indent_str}        {result_page_var} = {popup_info_var}.value")
                            result_lines.append(f"{indent_str}        print(f'[CONDITIONAL_POPUP] Popup успешно открыт с попытки {{popup_attempt + 1}}', flush=True)")
                            result_lines.append(f"{indent_str}        break")
                            result_lines.append(f"")
                            result_lines.append(f"{indent_str}    except Exception as e:")
                            result_lines.append(f"{indent_str}        if popup_attempt == 0:")
                            result_lines.append(f"{indent_str}            print(f'[CONDITIONAL_POPUP] Popup не открылся, проверяю промежуточную страницу...', flush=True)")
                            result_lines.append(f"{indent_str}            try:")
                            result_lines.append(f"{indent_str}                # Ждем загрузки промежуточной страницы")
                            result_lines.append(f"{indent_str}                {page_var}.wait_for_load_state('domcontentloaded', timeout=8000)")
                            result_lines.append(f"{indent_str}                time.sleep(1)  # Дополнительная пауза для стабильности")
                            result_lines.append(f"{indent_str}            except:")
                            result_lines.append(f"{indent_str}                pass")
                            result_lines.append(f"{indent_str}            continue")
                            result_lines.append(f"{indent_str}        else:")
                            result_lines.append(f"{indent_str}            print(f'[CONDITIONAL_POPUP] КРИТИЧЕСКАЯ ОШИБКА: {{e}}', flush=True)")
                            result_lines.append(f"{indent_str}            raise Exception(f'Не удалось открыть popup после {{max_popup_attempts}} попыток')")
                            result_lines.append(f"")
                            result_lines.append(f"{indent_str}if not {result_page_var}:")
                            result_lines.append(f"{indent_str}    raise Exception('FATAL: {result_page_var} не был создан')")

                            # Пропускаем следующие строки, которые уже обработаны (клик и присваивание)
                            i += 1
                            while i < len(lines):
                                next_stripped = lines[i].strip()
                                if f'= {popup_info_var}.value' in next_stripped:
                                    i += 1  # Пропускаем строку присваивания
                                    break
                                elif '.click()' in next_stripped and button_name in next_stripped:
                                    i += 1  # Пропускаем строку клика
                                elif not next_stripped:
                                    i += 1  # Пропускаем пустые строки
                                else:
                                    break

                            conditional_popup_next = False  # Сбрасываем флаг
                            continue
                        else:
                            # Не удалось извлечь кнопку или результат - используем стандартную обработку
                            print("[GENERATOR] WARNING: Не удалось извлечь кнопку или результат для условного popup, используем стандартную обработку")
                            result_lines.append(line)
                            inside_with_block = True
                            with_block_indent = current_indent
                            conditional_popup_next = False
                            i += 1
                            continue
                    else:
                        # Не удалось распарсить with блок - используем стандартную обработку
                        result_lines.append(line)
                        inside_with_block = True
                        with_block_indent = current_indent
                        conditional_popup_next = False
                        i += 1
                        continue
                else:
                    # Обычный with блок
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
                    # Дебаг только для page2 и page3
                    if current_page_context in ['page2', 'page3']:
                        result_lines.append(f"{indent_str}print(f'[{current_page_context.upper()}_DEBUG] [PAUSE] Waiting {seconds} seconds...', flush=True)")
                    result_lines.append(f"{indent_str}time.sleep({seconds})")
                    i += 1
                    continue

                # #scrolldown or #scroll
                if special_cmd in ['#scrolldown', '#scroll']:
                    # Дебаг только для page2 и page3
                    if current_page_context in ['page2', 'page3']:
                        result_lines.append(f"{indent_str}print(f'[{current_page_context.upper()}_DEBUG] [SCROLL] Scrolling down...', flush=True)")
                    result_lines.append(f"{indent_str}page.evaluate('window.scrollTo(0, document.body.scrollHeight)')")
                    result_lines.append(f"{indent_str}time.sleep(0.5)")
                    i += 1
                    continue

                # #scrollup
                if special_cmd == '#scrollup':
                    # Дебаг только для page2 и page3
                    if current_page_context in ['page2', 'page3']:
                        result_lines.append(f"{indent_str}print(f'[{current_page_context.upper()}_DEBUG] [SCROLL] Scrolling up...', flush=True)")
                    result_lines.append(f"{indent_str}page.evaluate('window.scrollTo(0, 0)')")
                    result_lines.append(f"{indent_str}time.sleep(0.5)")
                    i += 1
                    continue

                # #scrollmid
                if special_cmd == '#scrollmid':
                    # Дебаг только для page2 и page3
                    if current_page_context in ['page2', 'page3']:
                        result_lines.append(f"{indent_str}print(f'[{current_page_context.upper()}_DEBUG] [SCROLL] Scrolling to middle...', flush=True)")
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

                # #optional:N - группа из N действий (появляются вместе или не появляются)
                # Синтаксис: #optional или #optional:N
                # N - количество следующих действий для группировки (default: 1)
                optional_match = re.match(r'#\s*optional(?::(\d+))?$', special_cmd)
                if optional_match:
                    group_size = int(optional_match.group(1)) if optional_match.group(1) else 1

                    if group_size == 1:
                        # Обычный optional - одно действие
                        optional_next_action = True
                        result_lines.append(f"{indent_str}# Optional element (may not be present)")
                        i += 1
                        continue
                    else:
                        # Optional группа - несколько действий в одном try-except
                        result_lines.append(f"{indent_str}# Optional group: {group_size} actions (may not be present together)")
                        result_lines.append(f"{indent_str}print('[OPTIONAL_GROUP] Trying optional group ({group_size} actions)...', flush=True)")
                        result_lines.append(f"{indent_str}# Устанавливаем короткий timeout (3 сек) для optional группы")
                        result_lines.append(f"{indent_str}{current_page_context}.set_default_timeout(3000)")
                        result_lines.append(f"{indent_str}try:")

                        # Собираем следующие N действий
                        i += 1
                        actions_collected = 0
                        while i < len(lines) and actions_collected < group_size:
                            action_line = lines[i]
                            action_stripped = action_line.strip()

                            # Пропускаем пустые строки и комментарии (кроме специальных команд)
                            if not action_stripped or (action_stripped.startswith('#') and not action_stripped.startswith('#pause')):
                                i += 1
                                continue

                            # Добавляем действие с отступом для try блока
                            action_indent = ' ' * (current_indent + 4)
                            result_lines.append(f"{action_indent}{action_stripped}")
                            actions_collected += 1
                            i += 1

                        result_lines.append(f"{indent_str}    print('[OPTIONAL_GROUP] [OK] All actions completed', flush=True)")
                        result_lines.append(f"{indent_str}except Exception as e:")
                        result_lines.append(f"{indent_str}    print(f'[OPTIONAL_GROUP] [SKIP] Elements not found: {{type(e).__name__}} (this is OK)', flush=True)")
                        result_lines.append(f"{indent_str}    pass")
                        result_lines.append(f"{indent_str}finally:")
                        result_lines.append(f"{indent_str}    # Восстанавливаем стандартный timeout (30 сек)")
                        result_lines.append(f"{indent_str}    {current_page_context}.set_default_timeout(30000)")
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

                # #auto_conditional_popup - следующий with page.expect_popup() должен обрабатываться универсально
                # (для случаев, когда popup может открыться сразу или через промежуточную страницу)
                if special_cmd == '#auto_conditional_popup':
                    conditional_popup_next = True
                    result_lines.append(f"{indent_str}# Conditional popup handling enabled for next with block")
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
                '.press_sequentially(',  # ВАЖНО: для симуляции набора текста
                '.type(',
                '.select_option(',
                '.check(',
                '.uncheck(',
            ])

            if is_action:
                # Получаем индент
                indent_str = ' ' * current_indent

                # Если установлен флаг scroll_next_action - добавляем scroll_to_element() перед действием
                if scroll_next_action:
                    # Парсим действие чтобы определить page, selector, role
                    page_var = 'page'  # По умолчанию
                    if 'page1.' in stripped:
                        page_var = 'page1'
                    elif 'page2.' in stripped:
                        page_var = 'page2'
                    elif 'page3.' in stripped:
                        page_var = 'page3'

                    # Определяем тип действия
                    if 'get_by_test_id(' in stripped:
                        # Извлекаем test_id
                        test_id_match = re.search(r'get_by_test_id\(["\']([^"\']+)["\']\)', stripped)
                        if test_id_match:
                            test_id = test_id_match.group(1)
                            result_lines.append(f"{indent_str}# Scroll search for element")
                            result_lines.append(f'{indent_str}scroll_to_element({page_var}, None, by_test_id="{test_id}")')
                    elif 'get_by_role(' in stripped:
                        # Извлекаем роль и имя
                        role_match = re.search(r'get_by_role\("(\w+)"\s*,\s*name="([^"]+)"', stripped)
                        if role_match:
                            role = role_match.group(1)
                            name = role_match.group(2)
                            result_lines.append(f"{indent_str}# Scroll search for element")
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
                            result_lines.append(f"{indent_str}# Scroll search for element")
                            result_lines.append(f'{indent_str}scroll_to_element({page_var}, "{selector}")')

                    scroll_next_action = False  # Сбрасываем флаг

                # Действия внутри with блока критичны - нужен retry с прогрессивными задержками
                if inside_with_block:
                    # RETRY ЛОГИКА для критичных действий (popup открытие, navigation)
                    # Дебаг только для page2/page3
                    if current_page_context in ['page2', 'page3']:
                        result_lines.append(f"{indent_str}print(f'[{current_page_context.upper()}_DEBUG] Retry logic for critical action', flush=True)")
                    result_lines.append(f"{indent_str}max_retries = 5")
                    result_lines.append(f"{indent_str}for retry_attempt in range(max_retries):")
                    result_lines.append(f"{indent_str}    try:")
                    result_lines.append(f"{indent_str}        if retry_attempt > 0:")
                    result_lines.append(f"{indent_str}            wait_time = retry_attempt * 3  # 3s, 6s, 9s, 12s, 15s")
                    # Всегда показываем retry (это важно)
                    result_lines.append(f"{indent_str}            print(f'[RETRY] Attempt {{retry_attempt+1}}/{{max_retries}} after {{wait_time}}s...', flush=True)")
                    result_lines.append(f"{indent_str}            time.sleep(wait_time)")
                    result_lines.append(f"{indent_str}        {stripped}")
                    # Дебаг успеха только для page2/page3
                    if current_page_context in ['page2', 'page3']:
                        result_lines.append(f"{indent_str}        print(f'[{current_page_context.upper()}_DEBUG] [ACTION] [OK] Success', flush=True)")
                    result_lines.append(f"{indent_str}        break")
                    result_lines.append(f"{indent_str}    except PlaywrightTimeout:")
                    result_lines.append(f"{indent_str}        if retry_attempt == max_retries - 1:")
                    # Всегда показываем ошибки (критично)
                    result_lines.append(f"{indent_str}            print(f'[CRASH] [ERROR] Failed after {{max_retries}} retries - {stripped[:50]}', flush=True)")
                    result_lines.append(f"{indent_str}            raise")
                    # Дебаг retry только для page2/page3
                    if current_page_context in ['page2', 'page3']:
                        result_lines.append(f"{indent_str}        print(f'[{current_page_context.upper()}_DEBUG] [RETRY] Timeout, retrying...', flush=True)")
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
                        # Всегда показываем optional (важно)
                        result_lines.append(f"{indent_str}print('[OPTIONAL] Trying optional element...', flush=True)")

                        # КРИТИЧНО: Устанавливаем короткий timeout для optional элементов
                        result_lines.append(f"{indent_str}# Устанавливаем короткий timeout (3 сек) для optional элементов")
                        result_lines.append(f"{indent_str}{current_page_context}.set_default_timeout(3000)")

                        result_lines.append(f"{indent_str}try:")
                        result_lines.append(f"{indent_str}    {stripped}")
                        result_lines.append(f"{indent_str}    print('[OPTIONAL] [OK] Element found and action completed', flush=True)")
                        result_lines.append(f"{indent_str}except Exception as e:")
                        result_lines.append(f"{indent_str}    print(f'[OPTIONAL] [SKIP] Element not found or error: {{type(e).__name__}} (this is OK)', flush=True)")
                        result_lines.append(f"{indent_str}    pass")
                        result_lines.append(f"{indent_str}finally:")
                        result_lines.append(f"{indent_str}    # Восстанавливаем стандартный timeout (30 сек)")
                        result_lines.append(f"{indent_str}    {current_page_context}.set_default_timeout(30000)")

                        optional_next_action = False  # Сбрасываем флаг
                    else:
                        # Обычные действия вне with блока
                        # Детектим кнопку "Let's go" для специального дебага
                        is_lets_go_button = ("Let's go" in stripped or "Let\\'s go" in stripped) and '.click()' in stripped and current_page_context == 'page2'

                        # Дебаг для page2/page3 или критичной кнопки Let's go
                        if current_page_context in ['page2', 'page3'] or is_lets_go_button:
                            if is_lets_go_button:
                                result_lines.append(f"{indent_str}# ===== СПЕЦИАЛЬНЫЙ ДЕБАГ ДЛЯ КНОПКИ LET'S GO =====")
                                result_lines.append(f"{indent_str}print('[LETS_GO_DEBUG] Попытка найти и кликнуть кнопку Let\\'s go...', flush=True)")
                                result_lines.append(f"{indent_str}try:")
                                result_lines.append(f"{indent_str}    # Проверяем видимость кнопки")
                                result_lines.append(f"{indent_str}    button = page2.get_by_role('button', name=\"Let's go\")")
                                result_lines.append(f"{indent_str}    print(f'[LETS_GO_DEBUG] Кнопка найдена, count={{button.count()}}', flush=True)")
                                result_lines.append(f"{indent_str}    print(f'[LETS_GO_DEBUG] Проверяю видимость...', flush=True)")
                                result_lines.append(f"{indent_str}    is_visible = button.is_visible(timeout=5000)")
                                result_lines.append(f"{indent_str}    print(f'[LETS_GO_DEBUG] is_visible={{is_visible}}', flush=True)")
                                result_lines.append(f"{indent_str}    print(f'[LETS_GO_DEBUG] Проверяю enabled...', flush=True)")
                                result_lines.append(f"{indent_str}    is_enabled = button.is_enabled(timeout=5000)")
                                result_lines.append(f"{indent_str}    print(f'[LETS_GO_DEBUG] is_enabled={{is_enabled}}', flush=True)")
                                result_lines.append(f"{indent_str}    print(f'[LETS_GO_DEBUG] Попытка клика...', flush=True)")
                                result_lines.append(f"{indent_str}    {stripped}")
                                result_lines.append(f"{indent_str}    print('[LETS_GO_DEBUG] [SUCCESS] Клик выполнен успешно!', flush=True)")
                                result_lines.append(f"{indent_str}except Exception as e:")
                                result_lines.append(f"{indent_str}    print(f'[LETS_GO_DEBUG] [ERROR] Ошибка: {{type(e).__name__}}: {{e}}', flush=True)")
                                result_lines.append(f"{indent_str}    # Пробуем альтернативные методы")
                                result_lines.append(f"{indent_str}    print('[LETS_GO_DEBUG] Попытка force=True...', flush=True)")
                                result_lines.append(f"{indent_str}    try:")
                                result_lines.append(f"{indent_str}        page2.get_by_role('button', name=\"Let's go\").click(force=True, timeout=5000)")
                                result_lines.append(f"{indent_str}        print('[LETS_GO_DEBUG] [SUCCESS] Force click сработал!', flush=True)")
                                result_lines.append(f"{indent_str}    except Exception as e2:")
                                result_lines.append(f"{indent_str}        print(f'[LETS_GO_DEBUG] [ERROR] Force click не сработал: {{e2}}', flush=True)")
                                result_lines.append(f"{indent_str}        print('[LETS_GO_DEBUG] Попытка JavaScript click...', flush=True)")
                                result_lines.append(f"{indent_str}        try:")
                                result_lines.append(f"{indent_str}            page2.evaluate(\"document.querySelector('button[form=\\\\\"prefill_review_form\\\\\"]').click()\")")
                                result_lines.append(f"{indent_str}            print('[LETS_GO_DEBUG] [SUCCESS] JavaScript click сработал!', flush=True)")
                                result_lines.append(f"{indent_str}        except Exception as e3:")
                                result_lines.append(f"{indent_str}            print(f'[CRASH] [ERROR] Все методы клика не сработали: {{e3}}', flush=True)")
                                result_lines.append(f"{indent_str}            raise")
                            else:
                                # Обычный дебаг для page2/page3 (без вывода кода - чтобы избежать проблем с кавычками)
                                result_lines.append(f"{indent_str}print(f'[{current_page_context.upper()}_DEBUG] Выполнение действия...', flush=True)")
                                result_lines.append(f"{indent_str}try:")
                                result_lines.append(f"{indent_str}    {stripped}")
                                result_lines.append(f"{indent_str}    print(f'[{current_page_context.upper()}_DEBUG] [OK] Действие выполнено', flush=True)")
                                result_lines.append(f"{indent_str}except PlaywrightTimeout:")
                                result_lines.append(f'{indent_str}    print(f"[{current_page_context.upper()}_DEBUG] [WARNING] Timeout - элемент не найден", flush=True)')
                                result_lines.append(f'{indent_str}    print(f"[{current_page_context.upper()}_DEBUG] [INFO] Продолжаем выполнение...", flush=True)')
                                result_lines.append(f"{indent_str}    pass")
                        else:
                            # Минимальный дебаг для page и page1
                            result_lines.append(f"{indent_str}try:")
                            result_lines.append(f"{indent_str}    {stripped}")
                            result_lines.append(f"{indent_str}except PlaywrightTimeout:")
                            # Только ошибки для page/page1
                            result_lines.append(f'{indent_str}    print("[ACTION] [WARNING] Timeout - элемент не найден", flush=True)')
                            result_lines.append(f"{indent_str}    pass")
                            result_lines.append(f"{indent_str}except Exception as e:")
                            # Всегда показываем критичные ошибки
                            result_lines.append(f'{indent_str}    print(f"[CRASH] [ERROR] Критическая ошибка: {{type(e).__name__}}: {{e}}", flush=True)')
                            result_lines.append(f"{indent_str}    raise")
            else:
                # Не действие - оставляем как есть
                result_lines.append(line)

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
    thread_id, iteration_number, data_row, total_count, csv_file_path, fieldnames = task_data

    # Получаем индекс строки в CSV (0-based, не считая заголовок)
    csv_row_index = data_row.get('__csv_row_index__', 0)
    display_row_number = csv_row_index + 1  # Для отображения (1-based)

    print(f"\\n{'#'*60}")
    print(f"# THREAD {thread_id} | ITERATION {iteration_number}/{total_count} | CSV ROW {display_row_number}")
    print(f"{'#'*60}")

    # Помечаем строку как взятую в работу (ставим звездочку в колонке индекс 1)
    mark_row_in_progress(csv_file_path, csv_row_index, fieldnames)

    # Задержка для разнесения запусков Octobrowser (снижение нагрузки на систему)
    startup_delay = (thread_id - 1) * 3  # 0s, 3s, 6s, 9s, 12s...
    if startup_delay > 0:
        print(f"[THREAD {thread_id}] Задержка запуска: {startup_delay}s (снижение нагрузки)")
        time.sleep(startup_delay)

    profile_uuid = None
    result = {
        'thread_id': thread_id,
        'iteration': iteration_number,
        'csv_row': display_row_number,
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
            print(f"[THREAD {thread_id}] [ERROR] {result['error']}")
            return result

        print(f"[THREAD {thread_id}] Ожидание синхронизации (5 сек)...")
        time.sleep(5)

        start_data = start_profile(profile_uuid)
        if not start_data:
            result['error'] = "Profile start failed"
            print(f"[THREAD {thread_id}] [ERROR] {result['error']}")
            return result

        debug_url = start_data.get('ws_endpoint')
        if not debug_url:
            result['error'] = "No CDP endpoint"
            print(f"[THREAD {thread_id}] [ERROR] {result['error']}")
            return result

        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(debug_url)
            context = browser.contexts[0]
            page = context.pages[0]

            page.set_default_timeout(DEFAULT_TIMEOUT)
            page.set_default_navigation_timeout(NAVIGATION_TIMEOUT)

            # run_iteration теперь возвращает tuple (success, extracted_fields)
            iteration_success, extracted_fields = run_iteration(page, data_row, iteration_number)

            if iteration_success:
                result['success'] = True
            else:
                result['error'] = "Iteration failed"

            time.sleep(2)
            browser.close()

        stop_profile(profile_uuid)

        # 🔥 Ротация 9Proxy после завершения итерации
        if NINE_PROXY_ENABLED and NINE_PROXY_AUTO_ROTATE and NINE_PROXY_PORTS:
            # Получаем порт для этого worker thread (использует реальный thread ID)
            nine_proxy_dict = get_nine_proxy_for_thread(thread_id)
            if nine_proxy_dict:
                port = int(nine_proxy_dict['port'])
                print(f"[9PROXY ROTATION] Worker Thread (task thread_id={thread_id}) -> Rotating port {port}")
                rotate_proxy_for_port(port)

        # Итоги обработки
        if result['success']:
            print(f"[ITERATION {iteration_number}] [OK] Завершено успешно")
        else:
            print(f"[ITERATION {iteration_number}] [FAIL] Завершено с ошибкой: {result.get('error', 'Unknown error')}")

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

    # 🔥 Инициализация портов 9Proxy перед началом работы
    if NINE_PROXY_ENABLED and NINE_PROXY_PORTS:
        print("\\n" + "="*60)
        if not initialize_nine_proxy_ports():
            print("[MAIN] [WARNING] Не удалось инициализировать 9Proxy, продолжаем без него...")
            # Не прерываем выполнение, просто прокси не будут работать
        print("="*60 + "\\n")

    # Загружаем CSV и получаем отфильтрованные данные
    csv_file_path, fieldnames, csv_data = load_csv_data()

    if not csv_file_path or not fieldnames:
        print("[ERROR] Не удалось загрузить CSV файл")
        return

    print(f"[MAIN] CSV файл: {csv_file_path}")
    print(f"[MAIN] К обработке: {len(csv_data)} новых строк")

    if not csv_data:
        print("[MAIN] Нет новых данных для обработки (все строки уже обработаны)")
        return

    # ПРИМЕНЯЕМ ЛИМИТ ИТЕРАЦИЙ
    if MAX_ITERATIONS is not None and MAX_ITERATIONS > 0:
        original_count = len(csv_data)
        csv_data = csv_data[:MAX_ITERATIONS]
        print(f"[MAIN] Лимит итераций: {MAX_ITERATIONS}")
        print(f"[MAIN] Обрабатываем: {len(csv_data)} из {original_count} строк")
    else:
        print(f"[MAIN] Лимит итераций: НЕТ (обрабатываем все строки)")

    # Формируем задачи с новой системой (передаем csv_file_path и fieldnames)
    tasks = []
    for iteration_number, data_row in enumerate(csv_data, 1):
        thread_id = (iteration_number - 1) % THREADS_COUNT + 1
        task_data = (thread_id, iteration_number, data_row, len(csv_data), csv_file_path, fieldnames)
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
                    print(f"[MAIN] [OK] Итерация {result['iteration']} (CSV строка {result['csv_row']}) завершена успешно")
                else:
                    fail_count += 1
                    print(f"[MAIN] [ERROR] Итерация {result['iteration']} (CSV строка {result['csv_row']}) завершена с ошибкой")

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


