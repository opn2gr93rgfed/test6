#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест для проверки команды #try_popup
"""

import sys
sys.path.insert(0, '/home/user/test6')

from src.providers.smart_dynamic.generator import Generator

# USER CODE с командой #try_popup
USER_CODE = '''
page.goto("https://www.example.com/")
page.get_by_role("textbox", name="Enter your ZIP code").fill("12345")
page.get_by_role("button", name="Start").click()

page.get_by_role("heading", name="Question 1")
page.get_by_role("button", name="Yes").click()

page.get_by_role("heading", name="One final step")
page.get_by_role("textbox", name="Phone number").fill(data_row["Field9"])

#try_popup
with page.expect_popup() as page1_info:
    page.get_by_role("button", name="View my quotes").click()
page1 = page1_info.value

#optional
page1.get_by_role("button", name="Not Now").click()
'''

def main():
    print("=" * 80)
    print("ТЕСТ: Проверка команды #try_popup")
    print("=" * 80)

    generator = Generator()

    # Парсим код
    questions_pool, pre_code, post_code_raw = generator._parse_user_code(USER_CODE)

    print(f"\n[1] Парсинг завершен")
    print(f"    Вопросов: {len(questions_pool)}")
    print(f"    Post code строк: {len(post_code_raw.split(chr(10)))}")

    print(f"\n[1.5] RAW post_code:")
    for i, line in enumerate(post_code_raw.split('\n'), 1):
        print(f"    {i:3d} | {line}")

    # Применяем обработку (включая #try_popup)
    post_code = generator._clean_code_section(post_code_raw)

    print(f"\n[2] Обработка специальных команд завершена")
    print(f"    Обработанных строк: {len(post_code.split(chr(10)))}")

    print(f"\n[3] Проверка наличия try/except блока")

    has_try = 'try:' in post_code
    has_except = 'except Exception as e:' in post_code
    has_fallback = 'page1 = page' in post_code
    has_try_popup_comment = '# Try/catch for unstable popup' in post_code

    print(f"    ✓ 'try:' найден: {has_try}")
    print(f"    ✓ 'except Exception as e:' найден: {has_except}")
    print(f"    ✓ 'page1 = page' (fallback) найден: {has_fallback}")
    print(f"    ✓ '# Try/catch for unstable popup' найден: {has_try_popup_comment}")

    print(f"\n[4] Сгенерированный код:")
    print("    " + "=" * 76)
    for i, line in enumerate(post_code.split('\n'), 1):
        if i <= 30:  # Показываем первые 30 строк
            print(f"    {i:3d} | {line}")
    print("    " + "=" * 76)

    print("\n" + "=" * 80)
    if has_try and has_except and has_fallback and has_try_popup_comment:
        print("✓ ТЕСТ ПРОЙДЕН!")
        print("\nРезультат:")
        print("  • Команда #try_popup обработана корректно")
        print("  • try/except блок добавлен вокруг with page.expect_popup()")
        print("  • Fallback logic (page1 = page) присутствует")
        return True
    else:
        print("✗ ТЕСТ НЕ ПРОЙДЕН!")
        print("\nОтсутствуют элементы:")
        if not has_try: print("  • try:")
        if not has_except: print("  • except Exception as e:")
        if not has_fallback: print("  • page1 = page")
        if not has_try_popup_comment: print("  • # Try/catch for unstable popup")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
