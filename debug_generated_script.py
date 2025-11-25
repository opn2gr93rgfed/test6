#!/usr/bin/env python3
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

# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================

# Octobrowser API
API_BASE_URL = "https://app.octobrowser.net/api/v2/automation"
API_TOKEN = "test_token"
LOCAL_API_URL = "http://localhost:58888/api"

# Многопоточность
THREADS_COUNT = 1

# Прокси (одиночный)
USE_PROXY_LIST = False
USE_PROXY = False

# Таймауты
DEFAULT_TIMEOUT = 10000  # 10 секунд
NAVIGATION_TIMEOUT = 60000  # 60 секунд
QUESTION_SEARCH_TIMEOUT = 5000  # 5 секунд для поиска вопроса

# Thread-safe счетчик для round-robin
_proxy_counter = 0
_proxy_lock = threading.Lock()

# ============================================================
# ПРОКСИ РОТАЦИЯ
# ============================================================

def parse_proxy_string(proxy_string: str) -> Optional[Dict]:
    """Парсинг прокси строки"""
    try:
        proxy_string = proxy_string.strip()

        # type://login:password@host:port
        match = re.match(r'^(https?|socks5)://([^:]+):([^@]+)@([^:]+):(\d+)$', proxy_string)
        if match:
            return {
                'type': match.group(1),
                'login': match.group(2),
                'password': match.group(3),
                'host': match.group(4),
                'port': match.group(5)
            }

        # type://host:port
        match = re.match(r'^(https?|socks5)://([^:]+):(\d+)$', proxy_string)
        if match:
            return {
                'type': match.group(1),
                'host': match.group(2),
                'port': match.group(3),
                'login': '',
                'password': ''
            }

        # host:port:login:password
        match = re.match(r'^([^:]+):(\d+):([^:]+):([^:]+)$', proxy_string)
        if match:
            return {
                'type': 'http',
                'host': match.group(1),
                'port': match.group(2),
                'login': match.group(3),
                'password': match.group(4)
            }

        # host:port
        match = re.match(r'^([^:]+):(\d+)$', proxy_string)
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


# ============================================================
# OCTOBROWSER API ФУНКЦИИ
# ============================================================

def create_profile(title: str = "Auto Profile", proxy_dict: Optional[Dict] = None) -> Optional[str]:
    """Создать профиль через Octobrowser API с прокси"""
    url = f"{API_BASE_URL}/profiles"
    headers = {"X-Octo-Api-Token": API_TOKEN}

    profile_data = {
        "title": title,
        "fingerprint": {"os": "win"},
        "tags": []
    }

    if proxy_dict:
        profile_data["proxy"] = {
            "type": proxy_dict.get('type', 'http'),
            "host": proxy_dict['host'],
            "port": proxy_dict['port'],
            "login": proxy_dict.get('login', ''),
            "password": proxy_dict.get('password', '')
        }
        print(f"[PROFILE] [!] ПРОКСИ: {proxy_dict['type']}://{proxy_dict['host']}:{proxy_dict['port']}")

    if None:
        profile_data['geolocation'] = None

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=profile_data, timeout=60)

            if response.status_code == 429:
                wait_time = 2 ** attempt * 5
                print(f"[PROFILE] [!] Rate limit, waiting {wait_time}s")
                time.sleep(wait_time)
                continue

            if response.status_code in [200, 201]:
                result = response.json()
                if result.get('success') and 'data' in result:
                    profile_uuid = result['data']['uuid']
                    print(f"[PROFILE] [OK] Профиль создан: {profile_uuid}")
                    return profile_uuid
            else:
                print(f"[PROFILE] [ERROR] Ошибка API: {response.status_code}")
                return None
        except Exception as e:
            print(f"[PROFILE] [ERROR] Exception: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
                continue
            return None

    return None


def check_local_api() -> bool:
    """Проверить доступность локального Octobrowser API"""
    try:
        response = requests.get(f"{LOCAL_API_URL}/profiles", timeout=5)
        if response.status_code in [200, 404]:
            print(f"[LOCAL_API] [OK] Доступен на {LOCAL_API_URL}")
            return True
        return False
    except:
        print(f"[LOCAL_API] [ERROR] Недоступен")
        return False


def start_profile(profile_uuid: str) -> Optional[Dict]:
    """Запустить профиль и получить CDP endpoint"""
    url = f"{LOCAL_API_URL}/profiles/start"

    max_retries = 8
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                wait_time = 2 ** (attempt - 1) * 2
                print(f"[PROFILE] Ожидание синхронизации: {wait_time}s")
                time.sleep(wait_time)

            response = requests.post(
                url,
                json={
                    "uuid": profile_uuid,
                    "debug_port": True,
                    "headless": False,
                    "only_local": True,
                    "timeout": 120
                },
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
                print(f"[PROFILE] [ERROR] Ошибка запуска: {response.status_code}")
                return None
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"[PROFILE] [ERROR] Exception: {e}")
            continue

    return None


def stop_profile(profile_uuid: str):
    """Остановить профиль"""
    url = f"{LOCAL_API_URL}/profiles/{profile_uuid}/stop"
    try:
        requests.get(url, timeout=10)
        print(f"[PROFILE] [OK] Профиль остановлен")
    except:
        pass


def delete_profile(profile_uuid: str):
    """Удалить профиль"""
    url = f"{API_BASE_URL}/profiles/{profile_uuid}"
    headers = {"X-Octo-Api-Token": API_TOKEN}
    try:
        requests.delete(url, headers=headers, timeout=10)
        print(f"[PROFILE] [OK] Профиль удалён")
    except:
        pass


# ============================================================
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


# ============================================================
# ЗАГРУЗКА CSV И ОТСЛЕЖИВАНИЕ ПРОГРЕССА
# ============================================================

def load_processed_rows(results_file_path: str) -> set:
    """
    Читает файл результатов и возвращает set номеров уже обработанных строк

    Args:
        results_file_path: Путь к файлу результатов

    Returns:
        Set номеров строк, которые уже были обработаны (любой статус)
    """
    processed_rows = set()

    if not os.path.exists(results_file_path):
        print(f"[RESULTS] Файл результатов не найден (это нормально для первого запуска): {results_file_path}")
        return processed_rows

    try:
        with open(results_file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if 'row_number' in row:
                    processed_rows.add(int(row['row_number']))

        print(f"[RESULTS] Загружено {len(processed_rows)} обработанных строк из результатов")
    except Exception as e:
        print(f"[RESULTS] [WARNING] Ошибка чтения результатов: {e}")

    return processed_rows


def write_row_status(results_file_path: str, row_number: int, status: str, start_time: str, end_time: str = "", error_msg: str = "", data_row: Dict = None, extracted_fields: Dict = None):
    """
    Записывает или обновляет статус обработки строки в файл результатов

    Args:
        results_file_path: Путь к файлу результатов
        row_number: Номер строки в исходном CSV (1-based)
        status: Статус - "processing", "success", "failed", "error"
        start_time: Время начала обработки (ISO format)
        end_time: Время завершения (пусто для "processing")
        error_msg: Сообщение об ошибке (для failed/error)
        data_row: Данные строки из CSV (для reference)
        extracted_fields: Извлеченные поля из Network responses (словарь field_name: value)
    """
    import datetime

    # Проверяем существует ли файл
    file_exists = os.path.exists(results_file_path)

    # Если файл существует, читаем его и ищем строку
    existing_rows = {}
    base_fieldnames = ['row_number', 'status', 'start_time', 'end_time', 'error_msg', 'data']

    if file_exists:
        try:
            with open(results_file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                fieldnames = list(reader.fieldnames) if reader.fieldnames else base_fieldnames
                for row in reader:
                    if 'row_number' in row:
                        existing_rows[int(row['row_number'])] = row
        except Exception as e:
            print(f"[RESULTS] [WARNING] Ошибка чтения результатов для обновления: {e}")
            existing_rows = {}
            fieldnames = base_fieldnames
    else:
        fieldnames = base_fieldnames

    # Создаем или обновляем запись
    row_data = {
        'row_number': row_number,
        'status': status,
        'start_time': start_time,
        'end_time': end_time,
        'error_msg': error_msg,
        'data': json.dumps(data_row, ensure_ascii=False) if data_row else ""
    }

    # 🌐 Добавляем извлеченные поля из Network responses
    if extracted_fields:
        for field_name, field_value in extracted_fields.items():
            # Добавляем колонку если ее еще нет
            if field_name not in fieldnames:
                fieldnames.append(field_name)
                print(f"[RESULTS] [NETWORK] Добавлена новая колонка: {field_name}", flush=True)

            # Записываем значение
            row_data[field_name] = str(field_value)
            print(f"[RESULTS] [NETWORK] Строка {row_number}: {field_name} = {field_value}", flush=True)

    existing_rows[row_number] = row_data

    # Перезаписываем весь файл
    try:
        with open(results_file_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            # Сортируем по номеру строки
            for rn in sorted(existing_rows.keys()):
                writer.writerow(existing_rows[rn])

        # print(f"[RESULTS] Записан статус для строки {row_number}: {status}")
    except Exception as e:
        print(f"[RESULTS] [ERROR] Не удалось записать результат: {e}")


def load_csv_data() -> tuple:
    """
    Загрузить данные из CSV файла через диалог и отфильтровать уже обработанные

    Returns:
        Tuple (csv_file_path, results_file_path, unprocessed_data)
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
        return ("", "", [])

    if not os.path.exists(csv_file_path):
        print(f"[CSV] [ERROR] Файл не существует: {csv_file_path}")
        return ("", "", [])

    print(f"[CSV] Загрузка файла: {csv_file_path}")

    # Создаем путь к файлу результатов
    csv_dir = os.path.dirname(csv_file_path)
    csv_basename = os.path.splitext(os.path.basename(csv_file_path))[0]
    results_file_path = os.path.join(csv_dir, f"{csv_basename}_results.csv")

    print(f"[CSV] Файл результатов: {results_file_path}")

    # Загружаем обработанные строки
    processed_rows = load_processed_rows(results_file_path)

    # Загружаем CSV данные
    all_data = []
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            all_data = list(reader)

        print(f"[CSV] [OK] Загружено {len(all_data)} строк из CSV")

        if all_data and len(all_data) > 0:
            headers = list(all_data[0].keys())
            print(f"[CSV] Заголовки: {', '.join(headers)}")

    except Exception as e:
        print(f"[CSV] [ERROR] Ошибка загрузки: {e}")
        return ("", "", [])

    # Фильтруем уже обработанные строки
    unprocessed_data = []
    for row_idx, data_row in enumerate(all_data, 1):
        # Добавляем номер строки в данные
        data_row['__row_number__'] = row_idx

        # Пропускаем уже обработанные
        if row_idx in processed_rows:
            continue

        unprocessed_data.append(data_row)

    skipped_count = len(all_data) - len(unprocessed_data)
    print(f"[CSV] Пропущено {skipped_count} обработанных строк")
    print(f"[CSV] К обработке: {len(unprocessed_data)} новых строк")

    return (csv_file_path, results_file_path, unprocessed_data)


# ============================================================
# СЛОВАРЬ ВОПРОСОВ И ОТВЕТОВ (МОМЕНТАЛЬНЫЙ ПОИСК O(1))
# ============================================================

QUESTIONS_POOL = {
    "Are you currently insured?": {
        "actions": [
            {
                "type": "button_click",
                "value": "No"
            }
        ],
        "special_commands": []
    },
    "Are you looking to buy": {
        "actions": [
            {
                "type": "button_click",
                "value": "No"
            }
        ],
        "special_commands": []
    },
    "Do you own or rent your home?": {
        "actions": [
            {
                "type": "button_click",
                "value": "Own"
            }
        ],
        "special_commands": []
    },
    "Why are you shopping for": {
        "actions": [
            {
                "type": "button_click",
                "value": "My policy expired"
            }
        ],
        "special_commands": []
    },
    "How soon do you need your": {
        "actions": [
            {
                "type": "button_click",
                "value": "More than a month from now"
            }
        ],
        "special_commands": []
    },
    "When do you plan to purchase your new insurance policy?": {
        "actions": [
            {
                "type": "button_click",
                "value": "More than a month from now"
            }
        ],
        "special_commands": []
    },
    "What's your car year?": {
        "actions": [
            {
                "type": "button_click",
                "value": "2017"
            }
        ],
        "special_commands": []
    },
    "What's your car make?": {
        "actions": [
            {
                "type": "button_click",
                "value": "Ford icon Ford"
            }
        ],
        "special_commands": []
    },
    "What's your car model?": {
        "actions": [
            {
                "type": "button_click",
                "value": "Edge"
            }
        ],
        "special_commands": []
    },
    "What's your car trim?": {
        "actions": [
            {
                "type": "button_click",
                "value": "I don't know"
            }
        ],
        "special_commands": []
    },
    "What's your car body style?": {
        "actions": [
            {
                "type": "button_click",
                "value": "I don't know"
            }
        ],
        "special_commands": []
    },
    "What's the main use of your": {
        "actions": [
            {
                "type": "button_click",
                "value": "Commuting or personal use"
            }
        ],
        "special_commands": []
    },
    "How many miles do you drive": {
        "actions": [
            {
                "type": "button_click",
                "value": "Miles National average"
            }
        ],
        "special_commands": []
    },
    "Do you own or lease this car?": {
        "actions": [
            {
                "type": "button_click",
                "value": "Owned"
            }
        ],
        "special_commands": []
    },
    "Would you like to include": {
        "actions": [
            {
                "type": "button_click",
                "value": "No"
            }
        ],
        "special_commands": []
    },
    "Would you like to add another driver?": {
        "actions": [
            {
                "type": "button_click",
                "value": "No"
            }
        ],
        "special_commands": []
    },
    "What's your date of birth?": {
        "actions": [
            {
                "type": "textbox_fill",
                "field_name": "MM",
                "data_key": "Field2"
            },
            {
                "type": "textbox_fill",
                "field_name": "DD",
                "data_key": "Field3"
            },
            {
                "type": "textbox_fill",
                "field_name": "YYYY",
                "data_key": "Field4"
            },
            {
                "type": "button_click",
                "value": "Next"
            }
        ],
        "special_commands": []
    },
    "What's your gender?": {
        "actions": [
            {
                "type": "button_click",
                "value": "Female"
            }
        ],
        "special_commands": []
    },
    "Do you have an active U.S.": {
        "actions": [
            {
                "type": "button_click",
                "value": "Yes"
            }
        ],
        "special_commands": []
    },
    "How old were you when you first got your US driver's license?": {
        "actions": [
            {
                "type": "button_click",
                "value": "16"
            }
        ],
        "special_commands": []
    },
    "What's your credit score?": {
        "actions": [
            {
                "type": "button_click",
                "value": "Excellent (720+)"
            }
        ],
        "special_commands": []
    },
    "What's your highest level of": {
        "actions": [
            {
                "type": "button_click",
                "value": "High School/GED"
            }
        ],
        "special_commands": []
    },
    "Have you or an immediate family member honorably or actively served in the U.S. military?": {
        "actions": [
            {
                "type": "button_click",
                "value": "No"
            }
        ],
        "special_commands": []
    },
    "Do any of these apply to you?": {
        "actions": [
            {
                "type": "button_click",
                "value": "Continue"
            }
        ],
        "special_commands": []
    },
    "Would you also like to receive a home insurance quote? to": {
        "actions": [
            {
                "type": "button_click",
                "value": "No"
            }
        ],
        "special_commands": []
    },
    "Why don't you have insurance?": {
        "actions": [
            {
                "type": "button_click",
                "value": "My policy expired"
            }
        ],
        "special_commands": []
    },
    "How long has it been since you had car insurance?": {
        "actions": [
            {
                "type": "button_click",
                "value": "More than a month"
            }
        ],
        "special_commands": []
    },
    "How many at-fault accidents have you had in the past 3 years?": {
        "actions": [
            {
                "type": "button_click",
                "value": "0"
            }
        ],
        "special_commands": []
    },
    "How many cars you are looking to insure?": {
        "actions": [
            {
                "type": "button_click",
                "value": "1 car"
            }
        ],
        "special_commands": []
    },
    "How many speeding tickets have you had in the past 3 years?": {
        "actions": [
            {
                "type": "button_click",
                "value": "0"
            }
        ],
        "special_commands": []
    },
    "How many insurance claims have you had in the past 3 years?": {
        "actions": [
            {
                "type": "button_click",
                "value": "0"
            }
        ],
        "special_commands": []
    },
    "Want to get more quotes for your": {
        "actions": [
            {
                "type": "button_click",
                "value": "View my quotes"
            }
        ],
        "special_commands": []
    },
    "How many DUI/DWI convictions have you had in the past 3 years?": {
        "actions": [
            {
                "type": "button_click",
                "value": "0"
            }
        ],
        "special_commands": []
    },
    "Do you require an SR-22 Certificate?": {
        "actions": [
            {
                "type": "button_click",
                "value": "No Common choice"
            }
        ],
        "special_commands": []
    },
    "You're so close! Let's wrap this up": {
        "actions": [
            {
                "type": "textbox_fill",
                "field_name": "First name",
                "data_key": "Field5"
            },
            {
                "type": "textbox_fill",
                "field_name": "Last name",
                "data_key": "Field6"
            },
            {
                "type": "button_click",
                "value": "Next"
            }
        ],
        "special_commands": []
    },
    "Would you like to add another": {
        "actions": [
            {
                "type": "button_click",
                "value": "No"
            }
        ],
        "special_commands": []
    },
    "Where do you park your car overnight?": {
        "actions": [
            {
                "type": "textbox_fill",
                "field_name": "Enter location",
                "data_key": "Field7"
            },
            {
                "type": "press_key",
                "key": "ArrowDown"
            },
            {
                "type": "press_key",
                "key": "Enter"
            },
            {
                "type": "button_click",
                "value": "Next"
            }
        ],
        "special_commands": [
            "#pause10",
            "#pause5",
            "#pause5"
        ]
    },
    "Where would you like to receive a copy of your quotes?": {
        "actions": [
            {
                "type": "textbox_fill",
                "field_name": "Email address",
                "data_key": "Field8"
            },
            {
                "type": "press_key",
                "key": "ArrowDown"
            },
            {
                "type": "button_click",
                "value": "Next"
            }
        ],
        "special_commands": []
    },
    "One final step": {
        "actions": [
            {
                "type": "textbox_fill",
                "field_name": "Phone number",
                "data_key": "Field9"
            }
        ],
        "special_commands": []
    }
}


# ============================================================
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

    print(f"\n[DYNAMIC_QA] Начинаю поиск вопросов на странице...")
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
                    print(f"\n[DYNAMIC_QA] [DEBUG] Вопрос не найден в пуле, включаю детальный поиск...")
                    print(f"[DYNAMIC_QA] [DEBUG] Вопрос на странице: '{question_text}'")
                    pool_key = find_question_in_pool(question_text, QUESTIONS_POOL, debug=True)

                if pool_key:
                    print(f"\n[DYNAMIC_QA] [OK] Найден вопрос на странице: {question_text}")
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
                                time.sleep(0.5)

                            # Заполнение текстового поля
                            elif action_type == 'textbox_fill':
                                field_name = action.get('field_name')
                                data_key = action.get('data_key')
                                static_value = action.get('value')

                                value = data_row.get(data_key, static_value) if data_key else static_value

                                print(f"[DYNAMIC_QA]   -> Заполняю поле '{field_name}': {value}")
                                textbox = page.get_by_role("textbox", name=field_name).first
                                textbox.click(timeout=5000)
                                textbox.press_sequentially(value, delay=0.1)
                                time.sleep(0.5)

                            # Нажатие клавиши
                            elif action_type == 'press_key':
                                key = action.get('key')
                                print(f"[DYNAMIC_QA]   -> Нажимаю клавишу: {key}")
                                page.keyboard.press(key)
                                time.sleep(0.5)

                            # Клик по locator
                            elif action_type == 'locator_click':
                                selector = action.get('selector')
                                print(f"[DYNAMIC_QA]   -> Кликаю элемент: {selector[:50]}...")
                                page.locator(selector).first.click(timeout=10000)
                                time.sleep(0.5)

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

    print(f"\n[DYNAMIC_QA] ===== ИТОГ =====")
    print(f"[DYNAMIC_QA] Всего отвечено на вопросов: {answered_count}")
    print(f"[DYNAMIC_QA] ====================\n")

    return answered_count


# ============================================================
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
    print(f"\n============================================================")
    print(f"[ITERATION {iteration_number}] Начало")
    print(f"============================================================")

    try:
        # ============================================================
        # 🌐 ЗАХВАТ NETWORK RESPONSES (Developer Tools) + СОХРАНЕНИЕ VALIDATE В ФАЙЛЫ
        # ============================================================
        captured_data = {}
        extracted_fields = {}  # Словарь для извлеченных полей: {field_name: value}
        capture_patterns_config = []
        validate_counter = 0  # Счетчик validate запросов
        total_responses_counter = 0  # Счетчик всех обработанных responses для диагностики

        # Создаем папку для сохранения network responses
        network_responses_dir = os.path.join(os.getcwd(), "network_responses")
        os.makedirs(network_responses_dir, exist_ok=True)
        print(f"[NETWORK_CAPTURE] Папка для сохранения: {network_responses_dir}", flush=True)

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
                    filename = f"{pattern}_{counter:03d}_iteration_{iteration_num}_{timestamp}.json"
                else:
                    filename = f"{pattern}_iteration_{iteration_num}_{timestamp}.json"
                filepath = os.path.join(network_responses_dir, filename)

                # Формируем полный объект для сохранения
                full_response = {
                    'url': url,
                    'status': status,
                    'pattern': pattern,
                    'iteration': iteration_num,
                    'timestamp': timestamp,
                    'response_data': json_data
                }

                # Сохраняем в файл с красивым форматированием
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(full_response, f, ensure_ascii=False, indent=2)

                print(f"[NETWORK_CAPTURE] [OK] Response сохранен в файл: {filename}", flush=True)
                return filepath
            except Exception as e:
                print(f"[NETWORK_CAPTURE] [ERROR] Ошибка сохранения в файл: {e}", flush=True)
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
                    print(f"[NETWORK_DEBUG] API Request: {response.status} {url}", flush=True)

                # ТОЧНАЯ ПРОВЕРКА: Сохраняем ТОЛЬКО запросы с конкретного URL
                is_validate = url == 'https://app.joinroot.com/bind_api/web/validate'

                if is_validate:
                    validate_counter += 1
                    print(f"[NETWORK_CAPTURE] [VALIDATE #{validate_counter}] Перехвачен validate запрос: {url}", flush=True)
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
                            print(f"[NETWORK_CAPTURE] [OK] Validate #{validate_counter} сохранен: {saved_file}", flush=True)
                        else:
                            print(f"[NETWORK_CAPTURE] [ERROR] Validate #{validate_counter} НЕ сохранен!", flush=True)
                    except Exception as e:
                        print(f"[NETWORK_CAPTURE] [ERROR] Ошибка сохранения validate #{validate_counter}: {e}", flush=True)

                # Дополнительно проверяем паттерны (если они заданы)
                if capture_patterns_config:
                    for pattern_config in capture_patterns_config:
                        pattern = pattern_config.get('pattern', '')
                        fields = pattern_config.get('fields', [])

                        if pattern.lower() in url.lower():
                            print(f"[NETWORK_CAPTURE] Перехвачен ответ по паттерну '{pattern}': {url}", flush=True)
                            try:
                                # Получаем JSON данные из ответа
                                json_data = response.json()

                                # Сохраняем полные данные в памяти для отладки
                                if pattern not in captured_data:
                                    captured_data[pattern] = []
                                captured_data[pattern].append({
                                    'url': url,
                                    'status': response.status,
                                    'data': json_data
                                })

                                # 🔥 ИЗВЛЕЧЕНИЕ КОНКРЕТНЫХ ПОЛЕЙ
                                if fields:
                                    print(f"[NETWORK_CAPTURE] Извлекаю поля: {fields}", flush=True)
                                    for field in fields:
                                        field_value = get_nested_value(json_data, field)
                                        if field_value is not None:
                                            extracted_fields[field] = field_value
                                            print(f"[NETWORK_CAPTURE]   {field} = {field_value}", flush=True)
                                        else:
                                            print(f"[NETWORK_CAPTURE]   {field} не найдено в response", flush=True)
                                else:
                                    # Если полей нет - сохраняем весь response
                                    print(f"[NETWORK_CAPTURE] Полный response сохранен для '{pattern}'", flush=True)
                                    print(f"[NETWORK_CAPTURE] Preview: {str(json_data)[:200]}...", flush=True)
                            except Exception as e:
                                print(f"[NETWORK_CAPTURE] Не удалось распарсить JSON: {e}", flush=True)
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
        print(f"[NETWORK_CAPTURE] Паттерны и поля: {capture_patterns_config}", flush=True)

        # ============================================================
        # НАЧАЛЬНЫЕ ДЕЙСТВИЯ (до вопросов)
        # ============================================================
        page.goto("https://www.compare.com/")
        try:
            page.get_by_role("textbox", name="Enter your ZIP code").click()
        except PlaywrightTimeout:
            print("[ACTION] [WARNING] Timeout - элемент не найден", flush=True)
            pass
        except Exception as e:
            print(f"[CRASH] [ERROR] Критическая ошибка: {type(e).__name__}: {e}", flush=True)
            raise
        try:
            page.get_by_role("textbox", name="Enter your ZIP code").click()
        except PlaywrightTimeout:
            print("[ACTION] [WARNING] Timeout - элемент не найден", flush=True)
            pass
        except Exception as e:
            print(f"[CRASH] [ERROR] Критическая ошибка: {type(e).__name__}: {e}", flush=True)
            raise
        page.get_by_role("textbox", name="Enter your ZIP code").press_sequentially(data_row["Field1"], delay=0.1)
        try:
            page.get_by_role("button", name="See My Quotes").click()
        except PlaywrightTimeout:
            print("[ACTION] [WARNING] Timeout - элемент не найден", flush=True)
            pass
        except Exception as e:
            print(f"[CRASH] [ERROR] Критическая ошибка: {type(e).__name__}: {e}", flush=True)
            raise
        time.sleep(15)

        # ============================================================
        # ДИНАМИЧЕСКИЙ ОТВЕТ НА ВОПРОСЫ
        # ============================================================
        answered_count = answer_questions(page, data_row, max_questions=100)
        print(f"[ITERATION {iteration_number}] Отвечено на {answered_count} вопросов")

        # ============================================================
        # ДЕЙСТВИЯ ПОСЛЕ ВОПРОСОВ (popup окна, финальные действия)
        # ============================================================
        # Conditional popup handling enabled for next with block
        # УНИВЕРСАЛЬНАЯ ОБРАБОТКА УСЛОВНОГО POPUP (после заполнения телефона)
        page1 = None
        max_popup_attempts = 2
        for popup_attempt in range(max_popup_attempts):
            try:
                print(f'[CONDITIONAL_POPUP] Попытка {popup_attempt + 1}/{max_popup_attempts} открыть popup...', flush=True)
                with page.expect_popup(timeout=4000) as page1_info:
                    if popup_attempt == 0:
                        # Первая попытка - обычный клик
                        page.get_by_role("button", name="View my quotes").click()
                    else:
                        # Вторая попытка - ищем кнопку на промежуточной странице
                        button = page.get_by_role("button", name="View my quotes")
                        if button.is_visible(timeout=2000):
                            print('[CONDITIONAL_POPUP] Кнопка найдена на промежуточной странице', flush=True)
                            button.click()
                        else:
                            raise Exception('Кнопка не найдена')

                page1 = page1_info.value
                print(f'[CONDITIONAL_POPUP] Popup успешно открыт с попытки {popup_attempt + 1}', flush=True)
                break

            except Exception as e:
                if popup_attempt == 0:
                    print(f'[CONDITIONAL_POPUP] Popup не открылся, проверяю промежуточную страницу...', flush=True)
                    try:
                        page.wait_for_load_state('networkidle', timeout=5000)
                    except:
                        pass
                    continue
                else:
                    print(f'[CONDITIONAL_POPUP] КРИТИЧЕСКАЯ ОШИБКА: {e}', flush=True)
                    raise Exception(f'Не удалось открыть popup после {max_popup_attempts} попыток')

        if not page1:
            raise Exception('FATAL: page1 не был создан')
        # Optional element (may not be present)
        print('[OPTIONAL] Trying optional element...', flush=True)
        try:
            page1.get_by_role("button", name="Not Now").click()
            print('[OPTIONAL] [OK] Element found and clicked', flush=True)
        except Exception as e:
            print(f'[OPTIONAL] [SKIP] Element not found or error: {type(e).__name__} (this is OK)', flush=True)
            pass
        page1.locator('[data-testid="quote_skeleton_card"]').wait_for(state='detached', timeout=120000)
        time.sleep(2)
        # Scroll search enabled for next action
        # Scroll search for element
        scroll_to_element(page1, "[data-testid=\"show-more\"] span")
        try:
            page1.locator('[data-testid="show-more"] span').click()
        except PlaywrightTimeout:
            print("[ACTION] [WARNING] Timeout - элемент не найден", flush=True)
            pass
        except Exception as e:
            print(f"[CRASH] [ERROR] Критическая ошибка: {type(e).__name__}: {e}", flush=True)
            raise
        # Scroll search enabled for next action
        # Scroll search for element
        scroll_to_element(page1, "xpath=//img[@alt=\"Root\" and contains(@src, \"high-definition/root.svg\")]")
        try:
            page1.locator('xpath=//img[@alt="Root" and contains(@src, "high-definition/root.svg")]').click()
        except PlaywrightTimeout:
            print("[ACTION] [WARNING] Timeout - элемент не найден", flush=True)
            pass
        except Exception as e:
            print(f"[CRASH] [ERROR] Критическая ошибка: {type(e).__name__}: {e}", flush=True)
            raise
        with page1.expect_popup() as page2_info:
            max_retries = 5
            for retry_attempt in range(max_retries):
                try:
                    if retry_attempt > 0:
                        wait_time = retry_attempt * 3  # 3s, 6s, 9s, 12s, 15s
                        print(f'[RETRY] Attempt {retry_attempt+1}/{max_retries} after {wait_time}s...', flush=True)
                        time.sleep(wait_time)
                    page1.get_by_role("button", name="Buy online").click()
                    break
                except PlaywrightTimeout:
                    if retry_attempt == max_retries - 1:
                        print(f'[CRASH] [ERROR] Failed after {max_retries} retries - page1.get_by_role("button", name="Buy online").cli', flush=True)
                        raise
        page2 = page2_info.value
        print('[PAGE2_DEBUG] ===== НАЧАЛО РАБОТЫ С PAGE2 =====', flush=True)
        print(f'[PAGE2_DEBUG] [PAUSE] Waiting 15 seconds...', flush=True)
        time.sleep(15)
        print(f'[PAGE2_DEBUG] Выполнение действия...', flush=True)
        try:
            page2.get_by_role("button", name="Looks good").click()
            print(f'[PAGE2_DEBUG] [OK] Действие выполнено', flush=True)
        except PlaywrightTimeout:
            print(f"[PAGE2_DEBUG] [WARNING] Timeout - элемент не найден", flush=True)
            print(f"[PAGE2_DEBUG] [INFO] Продолжаем выполнение...", flush=True)
            pass
        print(f'[PAGE2_DEBUG] [PAUSE] Waiting 5 seconds...', flush=True)
        time.sleep(5)
        # Optional element (may not be present)
        print('[OPTIONAL] Trying optional element...', flush=True)
        try:
            page2.get_by_role("button", name="Continue with this address").click()
            print('[OPTIONAL] [OK] Element found and clicked', flush=True)
        except Exception as e:
            print(f'[OPTIONAL] [SKIP] Element not found or error: {type(e).__name__} (this is OK)', flush=True)
            pass
        print(f'[PAGE2_DEBUG] [PAUSE] Waiting 15 seconds...', flush=True)
        time.sleep(15)
        print(f'[PAGE2_DEBUG] Выполнение действия...', flush=True)
        try:
            page2.get_by_role("button", name="Let", exact=False).click()
            print(f'[PAGE2_DEBUG] [OK] Действие выполнено', flush=True)
        except PlaywrightTimeout:
            print(f"[PAGE2_DEBUG] [WARNING] Timeout - элемент не найден", flush=True)
            print(f"[PAGE2_DEBUG] [INFO] Продолжаем выполнение...", flush=True)
            pass
        print(f'[PAGE2_DEBUG] [PAUSE] Waiting 15 seconds...', flush=True)
        time.sleep(15)
        print(f'[PAGE2_DEBUG] Выполнение действия...', flush=True)
        try:
            page2.get_by_role("button", name="Continue").click()
            print(f'[PAGE2_DEBUG] [OK] Действие выполнено', flush=True)
        except PlaywrightTimeout:
            print(f"[PAGE2_DEBUG] [WARNING] Timeout - элемент не найден", flush=True)
            print(f"[PAGE2_DEBUG] [INFO] Продолжаем выполнение...", flush=True)
            pass
        # Optional element (may not be present)
        print(f'[PAGE2_DEBUG] [PAUSE] Waiting 15 seconds...', flush=True)
        time.sleep(15)
        print('[OPTIONAL] Trying optional element...', flush=True)
        try:
            page2.get_by_role("button", name="Continue and exclude").click()
            print('[OPTIONAL] [OK] Element found and clicked', flush=True)
        except Exception as e:
            print(f'[OPTIONAL] [SKIP] Element not found or error: {type(e).__name__} (this is OK)', flush=True)
            pass
        print(f'[PAGE2_DEBUG] [PAUSE] Waiting 10 seconds...', flush=True)
        time.sleep(10)
        all_switches = page2.locator('form#prefill_vehicles_form input[type="checkbox"][role="switch"]')
        print(f'[PAGE2_DEBUG] Выполнение действия...', flush=True)
        try:
            all_switches.nth(0).click()  # Было Covered → станет Not Covered
            print(f'[PAGE2_DEBUG] [OK] Действие выполнено', flush=True)
        except PlaywrightTimeout:
            print(f"[PAGE2_DEBUG] [WARNING] Timeout - элемент не найден", flush=True)
            print(f"[PAGE2_DEBUG] [INFO] Продолжаем выполнение...", flush=True)
            pass
        print(f'[PAGE2_DEBUG] [PAUSE] Waiting 3 seconds...', flush=True)
        time.sleep(3)
        print(f'[PAGE2_DEBUG] Выполнение действия...', flush=True)
        try:
            all_switches.nth(1).click()  # Было Not Covered → станет Covered
            print(f'[PAGE2_DEBUG] [OK] Действие выполнено', flush=True)
        except PlaywrightTimeout:
            print(f"[PAGE2_DEBUG] [WARNING] Timeout - элемент не найден", flush=True)
            print(f"[PAGE2_DEBUG] [INFO] Продолжаем выполнение...", flush=True)
            pass
        print(f'[PAGE2_DEBUG] [PAUSE] Waiting 5 seconds...', flush=True)
        time.sleep(5)
        print(f'[PAGE2_DEBUG] Выполнение действия...', flush=True)
        try:
            page2.get_by_role("button", name="Continue").click()
            print(f'[PAGE2_DEBUG] [OK] Действие выполнено', flush=True)
        except PlaywrightTimeout:
            print(f"[PAGE2_DEBUG] [WARNING] Timeout - элемент не найден", flush=True)
            print(f"[PAGE2_DEBUG] [INFO] Продолжаем выполнение...", flush=True)
            pass
        print(f'[PAGE2_DEBUG] [PAUSE] Waiting 10 seconds...', flush=True)
        time.sleep(10)
        page2.get_by_role("button", name="Continue to quote").dblclick()

        # 🌐 Вывод захваченных данных (если есть)
        print(f"\n[NETWORK_CAPTURE] === ИТОГОВЫЕ ДАННЫЕ ===")
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

    except Exception as e:
        print(f"[ITERATION {iteration_number}] [ERROR] Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return (False, {})


# ============================================================
# WORKER ФУНКЦИЯ (для многопоточности)
# ============================================================

def process_task(task_data: tuple) -> Dict:
    """Обработать одну задачу в отдельном потоке"""
    thread_id, iteration_number, data_row, total_count, results_file_path = task_data

    # Получаем номер строки из данных
    row_number = data_row.get('__row_number__', iteration_number)

    print(f"\n{'#'*60}")
    print(f"# THREAD {thread_id} | ROW {row_number}/{total_count}")
    print(f"{'#'*60}")

    # Записываем начало обработки
    import datetime
    start_time = datetime.datetime.now().isoformat()
    write_row_status(results_file_path, row_number, "processing", start_time, data_row=data_row)
    print(f"[PROGRESS] Строка {row_number} отмечена как 'processing'")

    # Задержка для разнесения запусков Octobrowser (снижение нагрузки на систему)
    startup_delay = (thread_id - 1) * 3  # 0s, 3s, 6s, 9s, 12s...
    if startup_delay > 0:
        print(f"[THREAD {thread_id}] Задержка запуска: {startup_delay}s (снижение нагрузки)")
        time.sleep(startup_delay)

    profile_uuid = None
    result = {
        'thread_id': thread_id,
        'iteration': iteration_number,
        'row_number': row_number,
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
            end_time = datetime.datetime.now().isoformat()
            write_row_status(results_file_path, row_number, "failed", start_time, end_time, error_msg=result['error'], data_row=data_row)
            print(f"[PROGRESS] Строка {row_number} отмечена как 'failed': {result['error']}")
            return result

        print(f"[THREAD {thread_id}] Ожидание синхронизации (5 сек)...")
        time.sleep(5)

        start_data = start_profile(profile_uuid)
        if not start_data:
            result['error'] = "Profile start failed"
            end_time = datetime.datetime.now().isoformat()
            write_row_status(results_file_path, row_number, "failed", start_time, end_time, error_msg=result['error'], data_row=data_row)
            print(f"[PROGRESS] Строка {row_number} отмечена как 'failed': {result['error']}")
            return result

        debug_url = start_data.get('ws_endpoint')
        if not debug_url:
            result['error'] = "No CDP endpoint"
            end_time = datetime.datetime.now().isoformat()
            write_row_status(results_file_path, row_number, "failed", start_time, end_time, error_msg=result['error'], data_row=data_row)
            print(f"[PROGRESS] Строка {row_number} отмечена как 'failed': {result['error']}")
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

        # Записываем финальный статус с extracted_fields
        end_time = datetime.datetime.now().isoformat()
        if result['success']:
            write_row_status(results_file_path, row_number, "success", start_time, end_time, data_row=data_row, extracted_fields=extracted_fields)
            print(f"[PROGRESS] Строка {row_number} отмечена как 'success'")
        else:
            write_row_status(results_file_path, row_number, "failed", start_time, end_time, error_msg=result.get('error', 'Unknown error'), data_row=data_row)
            print(f"[PROGRESS] Строка {row_number} отмечена как 'failed'")

    except Exception as e:
        print(f"[THREAD {thread_id}] [ERROR] Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        result['error'] = str(e)

        # Записываем ошибку
        end_time = datetime.datetime.now().isoformat()
        write_row_status(results_file_path, row_number, "error", start_time, end_time, error_msg=str(e), data_row=data_row)
        print(f"[PROGRESS] Строка {row_number} отмечена как 'error': {e}")

    finally:
        if profile_uuid:
            time.sleep(1)

    return result


# ============================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================

def main():
    """Главная функция запуска"""
    print("[MAIN] Запуск автоматизации через Octobrowser API...")
    print(f"[MAIN] Потоков: {THREADS_COUNT}")

    if not check_local_api():
        print("[MAIN] [ERROR] Локальный Octobrowser недоступен!")
        return

    # Загружаем CSV и получаем пути к файлам + отфильтрованные данные
    csv_file_path, results_file_path, csv_data = load_csv_data()

    if not csv_file_path or not results_file_path:
        print("[ERROR] Не удалось загрузить CSV файл")
        return

    print(f"[MAIN] CSV файл: {csv_file_path}")
    print(f"[MAIN] Файл результатов: {results_file_path}")
    print(f"[MAIN] К обработке: {len(csv_data)} новых строк")

    if not csv_data:
        print("[MAIN] Нет новых данных для обработки (все строки уже обработаны)")
        return

    # Формируем задачи с учетом results_file_path
    tasks = []
    for iteration_number, data_row in enumerate(csv_data, 1):
        thread_id = (iteration_number - 1) % THREADS_COUNT + 1
        task_data = (thread_id, iteration_number, data_row, len(csv_data), results_file_path)
        tasks.append(task_data)

    actual_threads = min(THREADS_COUNT, len(csv_data))
    print(f"\n[MAIN] Запуск {len(tasks)} задач в {actual_threads} потоках...")

    success_count = 0
    fail_count = 0

    with ThreadPoolExecutor(max_workers=actual_threads) as executor:
        future_to_task = {executor.submit(process_task, task): task for task in tasks}

        for future in as_completed(future_to_task):
            try:
                result = future.result()

                if result['success']:
                    success_count += 1
                    print(f"[MAIN] [OK] Строка {result.get('row_number', result['iteration'])} завершена успешно")
                else:
                    fail_count += 1
                    print(f"[MAIN] [ERROR] Строка {result.get('row_number', result['iteration'])} завершена с ошибкой")

            except Exception as e:
                fail_count += 1
                print(f"[MAIN] [ERROR] Ошибка: {e}")

    print(f"\n{'='*60}")
    print(f"[MAIN] ЗАВЕРШЕНО")
    print(f"[MAIN] Успешно: {success_count}/{len(csv_data)}")
    print(f"[MAIN] Ошибок: {fail_count}/{len(csv_data)}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
