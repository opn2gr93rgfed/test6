#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест для проверки работы #retry команды
"""

import sys
sys.path.insert(0, '/home/user/test6')

from src.providers.smart_dynamic.generator import Generator

# USER CODE с #retry командой для "Show More" button
USER_CODE = '''
page.goto("https://www.test.com/")
page.get_by_role("textbox", name="Enter your ZIP code").fill("12345")
page.get_by_role("button", name="See My Quotes").click()

page.get_by_role("heading", name="One final step").click()
page.get_by_role("textbox", name="Phone number").fill(data_row["Field9"])

with page.expect_popup() as page1_info:
    page.get_by_role("button", name="View my quotes").click()
page1 = page1_info.value

#optional
page1.locator('button.fairing__skip-action').click()

# Retry для "Show More" с 3 попытками, 50 секунд ожидания, scroll_search
#retry:3:50:scroll_search
page1.get_by_role("button", name="Show More").click()

#scroll_search
page1.locator('xpath=//img[@alt="Root"]').click()

#scroll_search
page1.get_by_role("button", name="Buy online").click()
'''

def main():
    print("=" * 80)
    print("ТЕСТ: Проверка #retry команды")
    print("=" * 80)

    generator = Generator()

    # Парсим код
    questions_pool, pre_code, post_code_raw = generator._parse_user_code(USER_CODE)

    # Применяем обработку (включая #retry, #optional, #scroll_search)
    post_code = generator._clean_code_section(post_code_raw)

    print(f"\n[1] Проверка post_questions_code...")
    print(f"    Строк кода: {len(post_code.split(chr(10)))}")

    print("\n[DEBUG] Полный post_code (после обработки):")
    print("=" * 80)
    print(post_code)
    print("=" * 80)

    # Проверяем что в post_code есть retry логика
    has_retry_loop = 'for retry_attempt in range(3)' in post_code
    has_retry_wait = 'time.sleep(50)' in post_code
    has_scroll_search = 'scroll_to_element(page1' in post_code
    has_show_more = 'Show More' in post_code
    has_success_msg = '[RETRY] [SUCCESS]' in post_code
    has_failed_msg = '[RETRY] [FAILED]' in post_code

    print("\n[2] Проверка элементов retry логики:")
    print(f"    ✓ Retry loop (3 attempts): {'ДА' if has_retry_loop else 'НЕТ'}")
    print(f"    ✓ Wait 50 seconds: {'ДА' if has_retry_wait else 'НЕТ'}")
    print(f"    ✓ Scroll search: {'ДА' if has_scroll_search else 'НЕТ'}")
    print(f"    ✓ 'Show More' action: {'ДА' if has_show_more else 'НЕТ'}")
    print(f"    ✓ Success message: {'ДА' if has_success_msg else 'НЕТ'}")
    print(f"    ✓ Failed message: {'ДА' if has_failed_msg else 'НЕТ'}")

    # Проверяем что ожидание происходит ПОСЛЕ первой попытки (retry_attempt > 0)
    has_conditional_wait = 'if retry_attempt > 0:' in post_code

    print(f"\n[3] Проверка оптимизации:")
    print(f"    ✓ Ожидание только после первой попытки: {'ДА' if has_conditional_wait else 'НЕТ'}")

    if has_conditional_wait:
        print("       → Первая попытка: 0 секунд ожидания")
        print("       → Вторая попытка: 50 секунд ожидания")
        print("       → Третья попытка: 50 секунд ожидания")

    # Печатаем фрагмент кода для визуального осмотра
    print("\n[4] Фрагмент сгенерированного кода:")
    print("    " + "-" * 76)
    lines = post_code.split('\n')
    retry_start = None
    for i, line in enumerate(lines):
        if 'Retry loop:' in line or 'Retry enabled:' in line:
            retry_start = i
            break

    if retry_start is not None:
        for i in range(retry_start, min(retry_start + 25, len(lines))):
            if i < len(lines):
                print(f"    {lines[i]}")
    print("    " + "-" * 76)

    print("\n" + "=" * 80)
    if all([has_retry_loop, has_retry_wait, has_scroll_search, has_show_more,
            has_success_msg, has_failed_msg, has_conditional_wait]):
        print("✓ ТЕСТ ПРОЙДЕН!")
        print("\nРезультат:")
        print("  • #retry:3:50:scroll_search корректно обработан")
        print("  • Генерируется retry loop с 3 попытками и 50 сек ожидания")
        print("  • Scroll search вызывается перед каждой попыткой")
        print("  • Ожидание происходит только ПОСЛЕ неудачной попытки")
        print("  • Нет лишних ожиданий при успехе с первой попытки")
        return True
    else:
        print("✗ ТЕСТ НЕ ПРОЙДЕН!")
        print("\nОтсутствующие элементы:")
        if not has_retry_loop:
            print("  • Retry loop с 3 попытками")
        if not has_retry_wait:
            print("  • Ожидание 50 секунд")
        if not has_scroll_search:
            print("  • Scroll search")
        if not has_show_more:
            print("  • 'Show More' action")
        if not has_success_msg:
            print("  • Success message")
        if not has_failed_msg:
            print("  • Failed message")
        if not has_conditional_wait:
            print("  • Условное ожидание (только после первой попытки)")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
