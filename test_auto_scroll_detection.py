#!/usr/bin/env python3
"""
Тест для проверки авто-детекции scroll_to_element()

Проверяет что генератор автоматически добавляет scroll_to_element() перед действиями
КРОМЕ случаев:
1. Внутри with блока
2. Сразу после page.goto()
3. Когда уже есть явный #scroll_search тег
"""

from src.providers.smart_dynamic.generator import Generator

def test_auto_scroll_normal_action():
    """Тест: обычные действия должны автоматически получать scroll_to_element()"""
    print("\n=== TEST 1: Normal action (should add auto-scroll) ===")

    provider = Generator()

    test_code = """page.get_by_role("button", name="Click me").click()"""

    result = provider._add_error_handling_to_actions(test_code)
    print("INPUT:")
    print(test_code)
    print("\nOUTPUT:")
    print(result)

    # Проверяем что есть AUTO-SCROLL комментарий
    assert "AUTO-SCROLL: Automatically scrolling to element" in result, "Should add auto-scroll comment"
    assert "scroll_to_element(page, None, by_role=" in result, "Should add scroll_to_element call"
    print("✅ PASSED: Auto-scroll added for normal action")


def test_no_auto_scroll_after_goto():
    """Тест: действия сразу после goto() НЕ должны получать auto-scroll"""
    print("\n=== TEST 2: Action after goto (should NOT add auto-scroll) ===")

    provider = Generator()

    test_code = """page.goto("https://example.com")
page.get_by_role("button", name="First button").click()"""

    result = provider._add_error_handling_to_actions(test_code)
    print("INPUT:")
    print(test_code)
    print("\nOUTPUT:")
    print(result)

    # Проверяем что НЕТ AUTO-SCROLL для первого действия после goto
    lines = result.split('\n')
    goto_index = -1
    for i, line in enumerate(lines):
        if '.goto(' in line:
            goto_index = i
            break

    # Проверяем что следующее действие НЕ имеет AUTO-SCROLL
    after_goto_lines = '\n'.join(lines[goto_index:goto_index+5])
    assert "AUTO-SCROLL" not in after_goto_lines, "Should NOT add auto-scroll after goto"
    print("✅ PASSED: No auto-scroll after goto()")


def test_no_auto_scroll_inside_with_block():
    """Тест: действия внутри with блока НЕ должны получать auto-scroll"""
    print("\n=== TEST 3: Action inside with block (should NOT add auto-scroll) ===")

    provider = Generator()

    test_code = """with page.expect_popup() as popup_info:
    page.get_by_role("button", name="Open popup").click()"""

    result = provider._add_error_handling_to_actions(test_code)
    print("INPUT:")
    print(test_code)
    print("\nOUTPUT:")
    print(result)

    # Проверяем что НЕТ AUTO-SCROLL внутри with блока
    assert "AUTO-SCROLL" not in result, "Should NOT add auto-scroll inside with block"
    print("✅ PASSED: No auto-scroll inside with block")


def test_explicit_scroll_search_tag():
    """Тест: явный #scroll_search тег должен использоваться вместо auto-scroll"""
    print("\n=== TEST 4: Explicit #scroll_search tag (should use explicit, not auto) ===")

    provider = Generator()

    test_code = """#scroll_search
page.get_by_role("button", name="Scroll to me").click()"""

    result = provider._add_error_handling_to_actions(test_code)
    print("INPUT:")
    print(test_code)
    print("\nOUTPUT:")
    print(result)

    # Проверяем что используется явный комментарий, НЕ AUTO-SCROLL
    assert "Scroll search for element" in result, "Should use explicit scroll search comment"
    assert "AUTO-SCROLL" not in result, "Should NOT use auto-scroll comment when explicit tag present"
    assert "scroll_to_element(page, None, by_role=" in result, "Should add scroll_to_element call"
    print("✅ PASSED: Explicit #scroll_search tag used correctly")


def test_multiple_actions_with_mixed_scenarios():
    """Тест: комплексный сценарий с разными типами действий"""
    print("\n=== TEST 5: Mixed scenario (goto + normal actions + with block) ===")

    provider = Generator()

    test_code = """page.goto("https://example.com")
page.get_by_role("button", name="First").click()
page.get_by_test_id("second-button").click()
with page.expect_popup() as popup_info:
    page.get_by_role("link", name="Open").click()
page1 = popup_info.value
page1.get_by_role("button", name="Submit").click()"""

    result = provider._add_error_handling_to_actions(test_code)
    print("INPUT:")
    print(test_code)
    print("\nOUTPUT:")
    print(result)

    # Подсчитываем AUTO-SCROLL комментарии
    auto_scroll_count = result.count("AUTO-SCROLL: Automatically scrolling to element")
    print(f"\nAuto-scroll count: {auto_scroll_count}")

    # Ожидаем:
    # - НЕТ для первого действия после goto (First)
    # - ДА для второго действия (second-button)
    # - НЕТ для действия внутри with блока (Open)
    # - ДА для действия после with блока (Submit)
    # ИТОГО: 2 auto-scroll

    assert auto_scroll_count == 2, f"Expected 2 auto-scrolls, got {auto_scroll_count}"
    print("✅ PASSED: Mixed scenario handled correctly")


def test_get_by_test_id_auto_scroll():
    """Тест: get_by_test_id должен получать правильный auto-scroll"""
    print("\n=== TEST 6: get_by_test_id with auto-scroll ===")

    provider = Generator()

    test_code = """page.get_by_test_id("show-more").click()"""

    result = provider._add_error_handling_to_actions(test_code)
    print("INPUT:")
    print(test_code)
    print("\nOUTPUT:")
    print(result)

    assert "AUTO-SCROLL: Automatically scrolling to element" in result, "Should add auto-scroll comment"
    assert 'scroll_to_element(page, None, by_test_id="show-more"' in result, "Should add scroll_to_element with test_id"
    assert 'max_duration_seconds=' in result, "Should include timeout parameter"
    print("✅ PASSED: get_by_test_id auto-scroll works")


def test_locator_xpath_auto_scroll():
    """Тест: locator с xpath должен получать правильный auto-scroll"""
    print("\n=== TEST 7: locator with xpath auto-scroll ===")

    provider = Generator()

    test_code = """page1.locator('xpath=//img[@alt="Root"]').click()"""

    result = provider._add_error_handling_to_actions(test_code)
    print("INPUT:")
    print(test_code)
    print("\nOUTPUT:")
    print(result)

    assert "AUTO-SCROLL: Automatically scrolling to element" in result, "Should add auto-scroll comment"
    assert "scroll_to_element(page1," in result, "Should use correct page variable (page1)"
    print("✅ PASSED: locator xpath auto-scroll works")


def test_no_auto_scroll_for_heading():
    """Тест: heading элементы НЕ должны получать auto-scroll (для динамических вопросов)"""
    print("\n=== TEST 8: heading elements (should NOT add auto-scroll) ===")

    provider = Generator()

    test_code = """page.get_by_role("heading", name="Are you currently insured?").click()"""

    result = provider._add_error_handling_to_actions(test_code)
    print("INPUT:")
    print(test_code)
    print("\nOUTPUT:")
    print(result)

    # Проверяем что НЕТ AUTO-SCROLL для heading
    assert "AUTO-SCROLL" not in result, "Should NOT add auto-scroll for heading elements"
    assert "scroll_to_element" not in result, "Should NOT call scroll_to_element for heading"
    print("✅ PASSED: No auto-scroll for heading elements")


def test_scroll_timeout_command():
    """Тест: команда #scroll_timeout:N должна изменять таймаут"""
    print("\n=== TEST 9: #scroll_timeout command ===")

    provider = Generator()

    test_code = """#scroll_timeout:30
page.get_by_role("button", name="Quick action").click()"""

    result = provider._add_error_handling_to_actions(test_code)
    print("INPUT:")
    print(test_code)
    print("\nOUTPUT:")
    print(result)

    # Проверяем что используется правильный таймаут
    assert "Scroll timeout set to 30s" in result, "Should acknowledge timeout setting"
    assert "max_duration_seconds=30" in result, "Should use custom timeout of 30s"
    print("✅ PASSED: scroll_timeout command works")


if __name__ == "__main__":
    print("="*60)
    print("AUTO-SCROLL DETECTION TESTS")
    print("="*60)

    tests = [
        test_auto_scroll_normal_action,
        test_no_auto_scroll_after_goto,
        test_no_auto_scroll_inside_with_block,
        test_explicit_scroll_search_tag,
        test_multiple_actions_with_mixed_scenarios,
        test_get_by_test_id_auto_scroll,
        test_locator_xpath_auto_scroll,
        test_no_auto_scroll_for_heading,
        test_scroll_timeout_command,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "="*60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*60)

    if failed == 0:
        print("✅ ALL TESTS PASSED!")
    else:
        print(f"❌ {failed} TESTS FAILED")
        exit(1)
