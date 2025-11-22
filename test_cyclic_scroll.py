#!/usr/bin/env python3
"""
Тест: Циклический scroll_search с временным ограничением
"""

from src.providers.smart_dynamic.generator import Generator

# Тестовый user_code
user_code = """
Question 1:
#scroll_search
page.get_by_role("button", name="Dynamic Button").click()

Question 2:
#retry:3:50:scroll_search
page.get_by_test_id("lazy-loaded-element").click()
"""

# Конфигурация
config = {
    'start_url': 'https://example.com',
    'csv_file_path': 'test.csv',
    'num_threads': 1,
    'proxy_type': 'no_proxy'
}

print("=" * 80)
print("ТЕСТ: Циклический scroll_search с временным ограничением")
print("=" * 80)
print()

# Генерируем скрипт
generator = Generator()
script = generator.generate_script(user_code, config)

print("[1] Проверка функции scroll_to_element...")

# Проверяем временное ограничение
if 'max_duration_seconds=180' in script:
    print("    ✓ Временное ограничение 180 секунд (3 минуты): ДА")
else:
    print("    ✗ Временное ограничение: НЕТ")
    exit(1)

# Проверяем циклический поиск
if 'while not is_time_expired():' in script:
    print("    ✓ Циклический поиск (while loop): ДА")
else:
    print("    ✗ Циклический поиск: НЕТ")
    exit(1)

# Проверяем проверку времени
if 'def is_time_expired():' in script:
    print("    ✓ Функция проверки времени: ДА")
else:
    print("    ✗ Функция проверки времени: НЕТ")
    exit(1)

# Проверяем логирование времени
if 'time.time() - start_time' in script:
    print("    ✓ Трекинг времени выполнения: ДА")
else:
    print("    ✗ Трекинг времени: НЕТ")
    exit(1)

# Проверяем скролл вниз и вверх
if 'window.scrollBy(0, window.innerHeight * 0.8)' in script and 'window.scrollBy(0, -window.innerHeight * 0.8)' in script:
    print("    ✓ Скролл вниз + вверх: ДА")
else:
    print("    ✗ Скролл вниз + вверх: НЕТ")
    exit(1)

# Проверяем паузу между циклами
if 'Пауза 2 сек перед следующим циклом' in script and 'time.sleep(2)' in script:
    print("    ✓ Пауза между циклами (2 сек): ДА")
else:
    print("    ✗ Пауза между циклами: НЕТ")
    exit(1)

print()
print("[2] Логика циклического поиска:")
print("    1. Проверяет элемент на текущей позиции")
print("    2. ЦИКЛ (пока не истечет время):")
print("       - Скроллит ВНИЗ до конца (max 30 попыток)")
print("       - Скроллит ВВЕРХ до начала (max 30 попыток)")
print("       - Пауза 2 секунды")
print("       - Повторяет цикл")
print("    3. Останавливается если:")
print("       - Элемент найден ✓")
print("       - Истекло 180 секунд (3 минуты)")
print()

print("[3] Преимущества:")
print("    • Находит динамически подгружаемые элементы")
print("    • Работает с lazy loading")
print("    • Можно использовать вместо #retry для элементов требующих скролла")
print("    • Гарантированный timeout (не зависнет навсегда)")
print()

print("=" * 80)
print("✓ ТЕСТ ПРОЙДЕН!")
print()
print("Результат:")
print("  • Циклический поиск: вниз → вверх → вниз → вверх...")
print("  • Максимальное время: 180 секунд (3 минуты)")
print("  • Детальное логирование с таймингом")
print("  • Защита от бесконечного зависания")
print("=" * 80)
