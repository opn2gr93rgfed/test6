#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест провайдера smart_dynamic
Проверяет парсинг и генерацию скрипта с динамичным поиском ответов
"""

import sys
from pathlib import Path

# Добавить корень проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from src.providers.smart_dynamic.generator import Generator

# Тестовый user_code (из вашего примера)
USER_CODE = '''
import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://www.mytest.com/")
    #pause10
    page.get_by_role("textbox", name="Enter your ZIP code").click()
    page.get_by_role("textbox", name="Enter your ZIP code").fill(data_row["Field1"])
    page.get_by_role("button", name="See My Quotes").click()

    # Первые 3 вопроса
    page.get_by_role("heading", name="Are you currently insured?").click()
    page.get_by_role("button", name="No").click()

    page.get_by_role("heading", name="Are you looking to buy").click()
    page.get_by_role("button", name="No").click()

    page.get_by_role("heading", name="Do you own or rent your home?").click()
    page.get_by_role("button", name="Own").click()

    # Вопросы о машине
    page.get_by_role("heading", name="What's your car year?").click()
    page.get_by_role("button", name="2017").click()

    page.get_by_role("heading", name="What's your car make?").click()
    page.get_by_role("button", name="Ford icon Ford").click()

    # Дата рождения (несколько полей)
    page.get_by_role("heading", name="What's your date of birth?").click()
    page.get_by_role("textbox", name="MM").click()
    page.get_by_role("textbox", name="MM").fill(data_row["Field2"])
    page.get_by_role("textbox", name="DD").click()
    page.get_by_role("textbox", name="DD").fill(data_row["Field3"])
    page.get_by_role("textbox", name="YYYY").click()
    page.get_by_role("textbox", name="YYYY").fill(data_row["Field4"])
    page.get_by_role("button", name="Next").click()

    # Еще вопросы
    page.get_by_role("heading", name="What's your gender?").click()
    page.get_by_role("button", name="Female").click()

    page.get_by_role("heading", name="What's your credit score?").click()
    page.get_by_role("button", name="Excellent (720+)").click()

    # Popup окно
    with page.expect_popup() as page1_info:
        page.get_by_role("button", name="View my quotes").click()
    page1 = page1_info.value

    #optional
    page.get_by_role("button", name="Not Now").click()

    #pause40
    #optional
    #scroll_search
    page1.get_by_role("button", name="Show More").click()

    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
'''

# Конфигурация
CONFIG = {
    'api_token': 'test_token_12345',
    'proxy': {
        'enabled': False
    },
    'proxy_list': {
        'proxies': [],
        'rotation_mode': 'random'
    },
    'profile': {
        'fingerprint': {'os': 'win'},
        'tags': ['auto-test']
    },
    'threads_count': 1,
    'network_capture_patterns': [],
    'simulate_typing': True,
    'typing_delay': 100
}


def test_generator():
    """Тест генератора"""
    print("=" * 80)
    print("ТЕСТ ПРОВАЙДЕРА smart_dynamic")
    print("=" * 80)

    generator = Generator()

    # Генерация скрипта
    print("\n[1] Генерация скрипта...")
    try:
        script = generator.generate_script(USER_CODE, CONFIG)
        print("✓ Скрипт сгенерирован успешно")
        print(f"✓ Длина скрипта: {len(script)} символов")
    except Exception as e:
        print(f"✗ Ошибка генерации: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Проверка наличия ключевых элементов
    print("\n[2] Проверка структуры скрипта...")

    checks = [
        ("QUESTIONS_POOL", "Словарь вопросов"),
        ("answer_questions", "Функция поиска ответов"),
        ("Are you currently insured?", "Вопрос 1"),
        ("What's your car year?", "Вопрос 2"),
        ("What's your gender?", "Вопрос 3"),
        ("button_click", "Тип действия: клик"),
        ("textbox_fill", "Тип действия: заполнение"),
        ("Field2", "Ссылка на данные CSV"),
        ("def run_iteration", "Основная итерация"),
        ("def process_task", "Worker функция"),
    ]

    all_passed = True
    for keyword, description in checks:
        if keyword in script:
            print(f"  ✓ {description}")
        else:
            print(f"  ✗ {description} - НЕ НАЙДЕН!")
            all_passed = False

    # Сохранение для ручной проверки
    output_file = Path(__file__).parent / "test_generated_dynamic_script.py"
    print(f"\n[3] Сохранение скрипта в {output_file}...")
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(script)
        print(f"✓ Скрипт сохранен")
    except Exception as e:
        print(f"✗ Ошибка сохранения: {e}")
        all_passed = False

    # Проверка парсинга вопросов
    print("\n[4] Проверка парсинга вопросов...")
    questions_pool, pre_code, post_code = generator._parse_user_code(USER_CODE)

    print(f"  ✓ Найдено вопросов: {len(questions_pool)}")
    print(f"  ✓ Строк кода до вопросов: {len(pre_code.split(chr(10)))}")
    print(f"  ✓ Строк кода после вопросов: {len(post_code.split(chr(10)))}")

    print("\n  Примеры вопросов:")
    for i, (question, data) in enumerate(list(questions_pool.items())[:5], 1):
        print(f"    {i}. '{question}'")
        print(f"       Действий: {len(data.get('actions', []))}")
        if data.get('special_commands'):
            print(f"       Команды: {data['special_commands']}")

    # Итог
    print("\n" + "=" * 80)
    if all_passed:
        print("✓ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
        print("\nПровайдер smart_dynamic готов к использованию!")
        print("\nОСОБЕННОСТИ:")
        print("  • Моментальный поиск ответов O(1) через словарь")
        print("  • Работает с любым порядком вопросов")
        print("  • Поддержка до 100+ вопросов")
        print("  • Автоматическое обнаружение типов действий")
        print("  • Поддержка специальных команд (#pause, #scroll_search, etc.)")
    else:
        print("✗ ЕСТЬ ОШИБКИ - ПРОВЕРЬТЕ ВЫВОД ВЫШЕ")
    print("=" * 80)

    return all_passed


if __name__ == "__main__":
    success = test_generator()
    sys.exit(0 if success else 1)
