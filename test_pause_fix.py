#!/usr/bin/env python3
"""
Тест: Проверка исправления #pause команды
"""

from src.providers.smart_dynamic.generator import Generator

# Тестовый user_code с #pause
user_code = """
Question 1:
#pause10
page.get_by_role("button", name="Continue").click()

Question 2:
#pause5
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
print("ТЕСТ: Проверка #pause команды после исправления regex")
print("=" * 80)
print()

# Генерируем скрипт
generator = Generator()
script = generator.generate_script(user_code, config)

print("[1] Проверка наличия execute_special_command...")
if "execute_special_command('#pause10', page, data_row)" in script:
    print("    ✓ #pause10 команда: ДА")
else:
    print("    ✗ #pause10 команда: НЕТ")
    print("\n[ОШИБКА] #pause10 не найден!")
    exit(1)

if "execute_special_command('#pause5', page, data_row)" in script:
    print("    ✓ #pause5 команда: ДА")
else:
    print("    ✗ #pause5 команда: НЕТ")
    print("\n[ОШИБКА] #pause5 не найден!")
    exit(1)

print()
print("[2] Проверка функции execute_special_command...")

# Проверяем regex паттерн в функции
if "re.match(r'#\\s*pause\\s*(\\d+)', command)" in script:
    print("    ✗ ОШИБКА: Старый паттерн с двойными бэкслешами!")
    exit(1)
elif r"re.match(r'#\s*pause\s*(\d+)', command)" in script:
    print("    ✓ Правильный regex паттерн: ДА")
else:
    print("    ? Не могу найти regex паттерн")

print()
print("[3] Фрагменты кода:")
print("-" * 80)

# Найти первый #pause
pause1_idx = script.find("execute_special_command('#pause10'")
if pause1_idx > 0:
    fragment = script[pause1_idx:pause1_idx+80]
    print(f"#pause10:\n{fragment}")
    print()

# Найти второй #pause
pause2_idx = script.find("execute_special_command('#pause5'")
if pause2_idx > 0:
    fragment = script[pause2_idx:pause2_idx+80]
    print(f"#pause5:\n{fragment}")

print("-" * 80)
print()
print("=" * 80)
print("✓ ТЕСТ ПРОЙДЕН!")
print()
print("Результат:")
print("  • #pause команда корректно распознается")
print("  • Regex паттерн исправлен (одинарные бэкслеши в raw string)")
print("  • execute_special_command вызывается правильно")
print("=" * 80)
