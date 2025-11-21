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

# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================

# Octobrowser API
API_BASE_URL = "https://app.octobrowser.net/api/v2/automation"
API_TOKEN = "test_token_12345"
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
        "tags": ["auto-test"]
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
        "special_commands": [
            "# Вопросы о машине"
        ]
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
        "special_commands": [
            "# Дата рождения (несколько полей)"
        ]
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
        "special_commands": [
            "# Еще вопросы"
        ]
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
    "What's your credit score?": {
        "actions": [
            {
                "type": "button_click",
                "value": "Excellent (720+)"
            }
        ],
        "special_commands": [
            "# Popup окно"
        ]
    }
}


# ============================================================
# ФУНКЦИЯ МОМЕНТАЛЬНОГО ПОИСКА И ОТВЕТА НА ВОПРОСЫ
# ============================================================

def answer_questions(page, data_row: Dict, max_questions: int = 100):
    """
    Находит все вопросы на странице и отвечает на них

    АЛГОРИТМ:
    1. Получить все heading элементы на странице
    2. Для каждого heading:
       - Извлечь текст вопроса
       - Найти в QUESTIONS_POOL (O(1) lookup!)
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
        for heading in headings:
            try:
                # Получить текст вопроса
                question_text = heading.inner_text().strip()

                # Пропустить если уже отвечали
                if question_text in answered_questions:
                    continue

                # Пропустить пустые или слишком короткие
                if not question_text or len(question_text) < 3:
                    continue

                # МОМЕНТАЛЬНЫЙ ПОИСК В СЛОВАРЕ O(1)
                if question_text in QUESTIONS_POOL:
                    print(f"\n[DYNAMIC_QA] ✓ Найден вопрос: {question_text}")
                    question_data = QUESTIONS_POOL[question_text]

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
                                print(f"[DYNAMIC_QA]   → Кликаю кнопку: {button_text}")
                                page.get_by_role("button", name=button_text).click(timeout=10000)
                                time.sleep(0.3)

                            # Заполнение текстового поля
                            elif action_type == 'textbox_fill':
                                field_name = action.get('field_name')
                                data_key = action.get('data_key')
                                static_value = action.get('value')

                                value = data_row.get(data_key, static_value) if data_key else static_value

                                print(f"[DYNAMIC_QA]   → Заполняю поле '{field_name}': {value}")
                                textbox = page.get_by_role("textbox", name=field_name).first
                                textbox.click(timeout=5000)
                                textbox.fill(value, timeout=5000)
                                time.sleep(0.2)

                            # Нажатие клавиши
                            elif action_type == 'press_key':
                                key = action.get('key')
                                print(f"[DYNAMIC_QA]   → Нажимаю клавишу: {key}")
                                page.keyboard.press(key)
                                time.sleep(0.2)

                            # Клик по locator
                            elif action_type == 'locator_click':
                                selector = action.get('selector')
                                print(f"[DYNAMIC_QA]   → Кликаю элемент: {selector[:50]}...")
                                page.locator(selector).first.click(timeout=10000)
                                time.sleep(0.3)

                        except Exception as e:
                            print(f"[DYNAMIC_QA]   [ERROR] Не удалось выполнить действие: {e}")
                            # Продолжаем выполнение других действий

                    # Отметить вопрос как отвеченный
                    answered_questions.add(question_text)
                    answered_count += 1
                    found_new_question = True

                    print(f"[DYNAMIC_QA] ✓ Вопрос обработан ({answered_count}/{max_questions})")

                    # Пауза для загрузки следующего вопроса
                    time.sleep(1)

                    # Выйти из цикла headings и искать новые вопросы
                    break

            except Exception as e:
                # Ошибка при обработке конкретного heading - продолжаем со следующим
                continue

        # Если не нашли новых вопросов - выходим
        if not found_new_question:
            print(f"[DYNAMIC_QA] Новых вопросов не найдено, завершаю поиск")
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
    """
    print(f"\n============================================================")
    print(f"[ITERATION {iteration_number}] Начало")
    print(f"============================================================")

    try:
        # ============================================================
        # НАЧАЛЬНЫЕ ДЕЙСТВИЯ (до вопросов)
        # ============================================================
        page.goto("https://www.mytest.com/")
        #pause10
        try:
            page.get_by_role("textbox", name="Enter your ZIP code").click()
        except PlaywrightTimeout:
            print("[ACTION] [WARNING] Timeout - элемент не найден", flush=True)
            print("[ACTION] [INFO] Продолжаем выполнение...", flush=True)
            pass
        try:
            page.get_by_role("textbox", name="Enter your ZIP code").fill(data_row["Field1"])
        except PlaywrightTimeout:
            print("[ACTION] [WARNING] Timeout - элемент не найден", flush=True)
            print("[ACTION] [INFO] Продолжаем выполнение...", flush=True)
            pass
        try:
            page.get_by_role("button", name="See My Quotes").click()
        except PlaywrightTimeout:
            print("[ACTION] [WARNING] Timeout - элемент не найден", flush=True)
            print("[ACTION] [INFO] Продолжаем выполнение...", flush=True)
            pass
        # Первые 3 вопроса

        # ============================================================
        # ДИНАМИЧЕСКИЙ ОТВЕТ НА ВОПРОСЫ
        # ============================================================
        answered_count = answer_questions(page, data_row, max_questions=100)
        print(f"[ITERATION {iteration_number}] Отвечено на {answered_count} вопросов")

        # ============================================================
        # ДЕЙСТВИЯ ПОСЛЕ ВОПРОСОВ (popup окна, финальные действия)
        # ============================================================
        with page.expect_popup() as page1_info:
            # Retry logic for critical action
            max_retries = 5
            for retry_attempt in range(max_retries):
                try:
                    if retry_attempt > 0:
                        wait_time = retry_attempt * 3  # 3s, 6s, 9s, 12s, 15s
                        print(f'[RETRY] Attempt {retry_attempt+1}/{max_retries} after {wait_time}s...', flush=True)
                        time.sleep(wait_time)
                    page.get_by_role("button", name="View my quotes").click()
                    print(f'[ACTION] [OK] Success', flush=True)
                    break
                except PlaywrightTimeout:
                    if retry_attempt == max_retries - 1:
                        print(f'[ACTION] [ERROR] Failed after {max_retries} retries', flush=True)
                        raise
                    print(f'[RETRY] Timeout, retrying...', flush=True)
        page1 = page1_info.value
        #optional
        try:
            page.get_by_role("button", name="Not Now").click()
        except PlaywrightTimeout:
            print("[ACTION] [WARNING] Timeout - элемент не найден", flush=True)
            print("[ACTION] [INFO] Продолжаем выполнение...", flush=True)
            pass
        #pause40
        #optional
        #scroll_search
        try:
            page1.get_by_role("button", name="Show More").click()
        except PlaywrightTimeout:
            print("[ACTION] [WARNING] Timeout - элемент не найден", flush=True)
            print("[ACTION] [INFO] Продолжаем выполнение...", flush=True)
            pass

        print(f"[ITERATION {iteration_number}] [OK] Завершено успешно")
        return True

    except Exception as e:
        print(f"[ITERATION {iteration_number}] [ERROR] Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# WORKER ФУНКЦИЯ (для многопоточности)
# ============================================================

def process_task(task_data: tuple) -> Dict:
    """Обработать одну задачу в отдельном потоке"""
    thread_id, iteration_number, data_row, total_count = task_data

    print(f"\n{'#'*60}")
    print(f"# THREAD {thread_id} | ROW {iteration_number}/{total_count}")
    print(f"{'#'*60}")

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
                    print(f"[MAIN] [OK] Итерация {result['iteration']} завершена")
                else:
                    fail_count += 1
                    print(f"[MAIN] [ERROR] Итерация {result['iteration']} завершена с ошибкой")

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
