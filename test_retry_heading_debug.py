#!/usr/bin/env python3
"""
Тест: DEBUG #retry для heading
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

# Генерируем скрипт
generator = Generator()
script = generator.generate_script(user_code, config)

# Показываем POST_QUESTIONS_CODE
post_start = script.find("# POST_QUESTIONS_CODE_START")
post_end = script.find("# POST_QUESTIONS_CODE_END")

if post_start > 0 and post_end > 0:
    print("=" * 80)
    print("POST_QUESTIONS_CODE:")
    print("=" * 80)
    print(script[post_start:post_end].strip())
    print("=" * 80)
else:
    print("POST_QUESTIONS_CODE не найден, показываю весь скрипт:")
    print(script[:2000])
