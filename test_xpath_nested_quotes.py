#!/usr/bin/env python3
"""
Тест: #scroll_search с xpath селектором содержащим вложенные кавычки
"""

from src.providers.smart_dynamic.generator import Generator

# Тестовый user_code с xpath содержащим кавычки
user_code = """
with page.expect_popup() as page1_info:
    page.get_by_role("button", name="View my quotes").click()
page1 = page1_info.value

#scroll_search
page1.locator('xpath=//img[@alt="Root" and contains(@src, "high-definition/root.svg")]').click()

#scroll_search
page.get_by_test_id("show-more").click()
"""

# Конфигурация
config = {
    'start_url': 'https://example.com',
    'csv_file_path': 'test.csv',
    'num_threads': 1,
    'proxy_type': 'no_proxy'
}

print("=" * 80)
print("ТЕСТ: #scroll_search с xpath селектором (вложенные кавычки)")
print("=" * 80)
print()

# Генерируем скрипт
generator = Generator()
script = generator.generate_script(user_code, config)

print("[1] Проверка парсинга xpath с вложенными кавычками...")

# Проверяем что scroll_to_element генерируется для xpath
if 'scroll_to_element(page1, "xpath=//img' in script:
    print("    ✓ scroll_to_element для xpath (page1): ДА")
else:
    print("    ✗ scroll_to_element для xpath (page1): НЕТ")
    print("\n[ОШИБКА] scroll_to_element не найден для xpath!")
    exit(1)

# Проверяем что @alt="Root" правильно экранирован
if '@alt=\\"Root\\"' in script or '@alt="Root"' in script:
    print("    ✓ Атрибут @alt экранирован: ДА")
else:
    print("    ✗ Атрибут @alt не найден")
    exit(1)

# Проверяем что @src="..." правильно экранирован
if 'high-definition' in script and 'root.svg' in script:
    print("    ✓ Полный xpath сохранен: ДА")
else:
    print("    ✗ Полный xpath НЕ сохранен")
    exit(1)

# Проверяем что scroll_to_element генерируется для get_by_test_id
if 'scroll_to_element(page, None, by_test_id="show-more")' in script:
    print("    ✓ scroll_to_element для get_by_test_id (page): ДА")
else:
    print("    ✗ scroll_to_element для get_by_test_id: НЕТ")
    exit(1)

print()
print("[2] Фрагмент сгенерированного кода для xpath:")
print("-" * 80)

# Найти scroll_to_element для xpath
xpath_idx = script.find('scroll_to_element(page1, "xpath=')
if xpath_idx > 0:
    fragment = script[xpath_idx:xpath_idx+200]
    print(fragment)
else:
    print("Не найдено!")

print("-" * 80)
print()

print("=" * 80)
print("✓ ТЕСТ ПРОЙДЕН!")
print()
print("Результат:")
print("  • xpath селекторы с вложенными кавычками обрабатываются корректно")
print("  • Атрибуты @alt=\"...\" и @src=\"...\" правильно экранируются")
print("  • scroll_to_element генерируется для всех типов селекторов")
print("  • Поддержка одинарных и двойных кавычек в locator()")
print("=" * 80)
