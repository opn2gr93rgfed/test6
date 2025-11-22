#!/usr/bin/env python3
"""
Тест: #retry для heading элемента
"""

from src.providers.smart_dynamic.generator import Generator

# Тестовый user_code
user_code = """
One final step:
#retry:3:50
page.get_by_role("heading", name="Are you currently insured?").click()

page.get_by_role("button", name="Submit").click()
"""

# Конфигурация
config = {
    'start_url': 'https://example.com',
    'csv_file_path': 'test.csv',
    'num_threads': 1,
    'proxy_type': 'no_proxy'
}

print("=" * 80)
print("ТЕСТ: #retry для heading элемента")
print("=" * 80)
print()

# Генерируем скрипт
generator = Generator()
script = generator.generate_script(user_code, config)

# Проверяем что retry блок существует
if 'for retry_attempt in range(3):' in script:
    print("[1] ✓ Retry loop сгенерирован")
else:
    print("[1] ✗ Retry loop НЕ сгенерирован!")
    exit(1)

if 'time.sleep(50)' in script:
    print("[2] ✓ Ожидание 50 секунд")
else:
    print("[2] ✗ Ожидание НЕ найдено!")
    exit(1)

if 'get_by_role("heading", name="Are you currently insured?")' in script:
    print("[3] ✓ Heading элемент найден")
else:
    print("[3] ✗ Heading элемент НЕ найден!")
    exit(1)

print()
print("Фрагмент кода:")
print("=" * 80)

# Найти retry блок
retry_start = script.find("for retry_attempt in range(3):")
retry_end = script.find("page.get_by_role(\"button\", name=\"Submit\")", retry_start)

if retry_start > 0 and retry_end > 0:
    fragment = script[retry_start:retry_end]
    print(fragment)
else:
    # План Б - показать всё что после POST_QUESTIONS
    post_start = script.find("# POST_QUESTIONS_CODE_START")
    post_end = script.find("# POST_QUESTIONS_CODE_END")
    if post_start > 0 and post_end > 0:
        print(script[post_start:post_end].strip())

print("=" * 80)
print()
print("✓ ТЕСТ ПРОЙДЕН!")
print()
print("Результат:")
print("  • #retry работает с heading элементами")
print("  • Retry loop: 3 попытки")
print("  • Ожидание: 50 секунд между попытками")
print("=" * 80)
