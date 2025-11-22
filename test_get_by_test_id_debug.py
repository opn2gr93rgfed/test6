#!/usr/bin/env python3
"""
Тест: Отладка get_by_test_id
"""

from src.providers.smart_dynamic.generator import Generator

# Тестовый user_code с get_by_test_id
user_code = """
One final step:
#retry:3:50:scroll_search
page.get_by_test_id("show-more").click()

#scroll_search
page1.get_by_test_id("submit-button").click()
"""

# Конфигурация
config = {
    'start_url': 'https://example.com',
    'csv_file_path': 'test.csv',
    'num_threads': 5,
    'proxy_type': 'no_proxy'
}

print("Генерируем скрипт...")
generator = Generator()
script = generator.generate_script(user_code, config)

# Извлекаем post_questions_code
post_start = script.find("# POST_QUESTIONS_CODE_START")
post_end = script.find("# POST_QUESTIONS_CODE_END")

if post_start > 0 and post_end > 0:
    post_code = script[post_start:post_end].strip()
    print("\n=== POST_QUESTIONS_CODE ===")
    print(post_code)
    print("=== END ===\n")
else:
    print("\n[ОШИБКА] Не найден POST_QUESTIONS_CODE")
    print("\nПолный скрипт:")
    print(script)
