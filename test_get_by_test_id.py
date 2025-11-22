#!/usr/bin/env python3
"""
Тест: Проверка поддержки get_by_test_id в #retry и #scroll_search
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

print("=" * 80)
print("ТЕСТ: Проверка get_by_test_id в #retry и #scroll_search")
print("=" * 80)
print()

# Генерируем скрипт
generator = Generator()
script = generator.generate_script(user_code, config)

# Извлекаем post_questions_code
post_start = script.find("# POST_QUESTIONS_CODE_START")
post_end = script.find("# POST_QUESTIONS_CODE_END")
post_code = script[post_start:post_end].strip()

print("[1] Проверка наличия scroll_to_element для get_by_test_id...")
print()

# Проверяем наличие by_test_id в retry блоке
if 'by_test_id="show-more"' in post_code:
    print("    ✓ #retry:scroll_search + get_by_test_id: ДА")
else:
    print("    ✗ #retry:scroll_search + get_by_test_id: НЕТ")
    print("\n[ОШИБКА] get_by_test_id не найден в retry блоке!")
    exit(1)

# Проверяем наличие by_test_id в обычном scroll_search
if 'by_test_id="submit-button"' in post_code:
    print("    ✓ #scroll_search + get_by_test_id: ДА")
else:
    print("    ✗ #scroll_search + get_by_test_id: НЕТ")
    print("\n[ОШИБКА] get_by_test_id не найден в scroll_search!")
    exit(1)

print()
print("[2] Фрагменты сгенерированного кода:")
print("-" * 80)

# Найти retry блок
retry_start = post_code.find("# Retry enabled:")
retry_end = post_code.find("# Scroll search enabled", retry_start)
if retry_start > 0 and retry_end > 0:
    print("\nRETRY блок:")
    print(post_code[retry_start:retry_end].strip())

# Найти scroll_search блок (после retry)
scroll_start = post_code.find("# Scroll search for element")
scroll_end = post_code.find("page1.get_by_test_id", scroll_start) + 50
if scroll_start > 0:
    print("\nSCROLL_SEARCH блок:")
    print(post_code[scroll_start:scroll_end].strip())

print("-" * 80)
print()
print("=" * 80)
print("✓ ТЕСТ ПРОЙДЕН!")
print()
print("Результат:")
print("  • get_by_test_id корректно обработан в #retry")
print("  • get_by_test_id корректно обработан в #scroll_search")
print("  • scroll_to_element вызывается с правильным параметром by_test_id")
print("=" * 80)
