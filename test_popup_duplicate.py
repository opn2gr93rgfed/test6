#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест для проверки что "View my quotes" не кликается дважды
"""

import sys
sys.path.insert(0, '/home/user/test6')

from src.providers.smart_dynamic.generator import Generator

# USER CODE с проблемой дубликата "View my quotes"
USER_CODE = '''
page.goto("https://www.test.com/")
page.get_by_role("textbox", name="Enter your ZIP code").fill("12345")
page.get_by_role("button", name="See My Quotes").click()
#pause10

page.get_by_role("heading", name="Are you currently insured?").click()
page.get_by_role("button", name="No").click()

page.get_by_role("heading", name="What's your gender?").click()
page.get_by_role("button", name="Female").click()

page.get_by_role("heading", name="One final step").click()
page.get_by_role("textbox", name="Phone number").fill(data_row["Field9"])
page.get_by_role("button", name="View my quotes").click()

with page.expect_popup() as page1_info:
    page.get_by_role("button", name="View my quotes")
page1 = page1_info.value

#optional
page.get_by_role("heading", name="How did you hear about us?").click()
page.get_by_role("button", name="Not Now").click()
'''

def main():
    print("=" * 80)
    print("ТЕСТ: Проверка дубликата 'View my quotes'")
    print("=" * 80)

    generator = Generator()

    # Парсим код
    questions_pool, pre_code, post_code = generator._parse_user_code(USER_CODE)

    print(f"\n[1] Проверка вопросов...")
    print(f"    Всего вопросов: {len(questions_pool)}")

    # Проверяем что "One final step" НЕ содержит клик "View my quotes"
    if "One final step" in questions_pool:
        actions = questions_pool["One final step"]["actions"]
        print(f"\n[2] Вопрос 'One final step':")
        print(f"    Действий: {len(actions)}")

        for i, action in enumerate(actions, 1):
            print(f"    {i}. {action}")

        # Проверяем что нет клика по "View my quotes"
        has_view_quotes = any(
            action.get('type') == 'button_click' and
            action.get('value') == 'View my quotes'
            for action in actions
        )

        if has_view_quotes:
            print("\n    ✗ FAILED: 'View my quotes' найден в действиях вопроса!")
            print("    Это вызовет двойной клик (в вопросе + в post_code)")
        else:
            print("\n    ✓ PASSED: 'View my quotes' удален из действий вопроса")
    else:
        print("\n✗ FAILED: Вопрос 'One final step' не найден!")
        return False

    print(f"\n[3] Проверка post_questions_code...")
    print(f"    Строк кода: {len(post_code.split(chr(10)))}")
    print("\n    Содержимое:")
    for i, line in enumerate(post_code.split('\n')[:10], 1):
        if line.strip():
            print(f"    {i}. {line}")

    # Проверяем что в post_code есть with page.expect_popup() с .click()
    has_with_block = 'with page.expect_popup()' in post_code
    has_click = '.click()' in post_code and 'View my quotes' in post_code

    if has_with_block:
        print("\n    ✓ with page.expect_popup() найден")
    else:
        print("\n    ✗ with page.expect_popup() НЕ найден!")

    if has_click:
        print("    ✓ .click() добавлен к 'View my quotes'")
    else:
        print("    ✗ .click() НЕ добавлен!")

    print("\n" + "=" * 80)
    if not has_view_quotes and has_with_block and has_click:
        print("✓ ТЕСТ ПРОЙДЕН!")
        print("\nРезультат:")
        print("  • 'View my quotes' удален из вопроса 'One final step'")
        print("  • 'View my quotes' с .click() находится в with page.expect_popup()")
        print("  • Двойной клик устранен!")
        return True
    else:
        print("✗ ТЕСТ НЕ ПРОЙДЕН!")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
