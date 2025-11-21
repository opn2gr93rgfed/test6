#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест логики динамического поиска вопросов
Проверяет normalize_text и find_question_in_pool БЕЗ API и браузера
"""

import re
from typing import Dict, Optional


def normalize_text(text: str) -> str:
    """
    Нормализует текст для сравнения (удаляет *, ?, !, .)
    """
    text = re.sub(r'[*?.!]+\s*', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip().lower()


def find_question_in_pool(question_text: str, pool: Dict, debug: bool = False) -> Optional[str]:
    """
    Ищет вопрос в пуле с fuzzy matching

    Три уровня поиска:
    1. Точное совпадение
    2. Нормализованное совпадение (без *, ?, !, .)
    3. Substring matching с проверкой длины (>70% совпадения)

    Returns:
        Ключ вопроса из pool или None
    """
    if debug:
        print(f"\n[SEARCH] Ищем: '{question_text}'")
        print(f"[SEARCH] В пуле {len(pool)} вопросов")

    # Уровень 1: Точное совпадение
    if question_text in pool:
        if debug:
            print(f"[SEARCH] ✓ Найдено точное совпадение!")
        return question_text

    # Уровень 2: Нормализованное совпадение
    normalized_search = normalize_text(question_text)

    for pool_question in pool.keys():
        normalized_pool = normalize_text(pool_question)

        if normalized_search == normalized_pool:
            if debug:
                print(f"[SEARCH] ✓ Найдено нормализованное совпадение: '{pool_question}'")
            return pool_question

    # Уровень 3: Substring matching
    for pool_question in pool.keys():
        normalized_pool = normalize_text(pool_question)

        # Проверяем вхождение substring в обе стороны
        if normalized_search in normalized_pool or normalized_pool in normalized_search:
            # Проверяем что длины примерно совпадают (>70%)
            len_ratio = min(len(normalized_search), len(normalized_pool)) / max(len(normalized_search), len(normalized_pool))

            if len_ratio > 0.7:
                if debug:
                    print(f"[SEARCH] ✓ Найдено substring совпадение: '{pool_question}' (ratio: {len_ratio:.2f})")
                return pool_question

    if debug:
        print(f"[SEARCH] ✗ Вопрос не найден в пуле")
        print(f"[SEARCH] Первые 5 вопросов в пуле:")
        for i, q in enumerate(list(pool.keys())[:5], 1):
            print(f"[SEARCH]   {i}. '{q}' → normalized: '{normalize_text(q)}'")

    return None


# ТЕСТОВЫЙ ПУЛ ВОПРОСОВ (из USER_CODE)
QUESTIONS_POOL = {
    "Are you currently insured?": {
        "actions": [
            {"type": "button_click", "value": "No"}
        ],
        "special_commands": []
    },
    "Are you looking to buy": {
        "actions": [
            {"type": "button_click", "value": "No"}
        ],
        "special_commands": []
    },
    "Do you own or rent your home?": {
        "actions": [
            {"type": "button_click", "value": "Own"}
        ],
        "special_commands": []
    },
    "What's your car year?": {
        "actions": [
            {"type": "button_click", "value": "2017"}
        ],
        "special_commands": []
    },
    "What's your car make?": {
        "actions": [
            {"type": "button_click", "value": "Ford icon Ford"}
        ],
        "special_commands": []
    },
    "What's your date of birth?": {
        "actions": [
            {"type": "textbox_fill", "field_name": "MM", "data_key": "Field2"},
            {"type": "textbox_fill", "field_name": "DD", "data_key": "Field3"},
            {"type": "textbox_fill", "field_name": "YYYY", "data_key": "Field4"},
            {"type": "button_click", "value": "Next"}
        ],
        "special_commands": []
    },
    "What's your gender?": {
        "actions": [
            {"type": "button_click", "value": "Female"}
        ],
        "special_commands": []
    },
    "What's your credit score?": {
        "actions": [
            {"type": "button_click", "value": "Excellent (720+)"}
        ],
        "special_commands": []
    }
}


def test_exact_match():
    """Тест 1: Точное совпадение"""
    print("\n" + "="*80)
    print("ТЕСТ 1: Точное совпадение")
    print("="*80)

    question = "Are you currently insured?"
    result = find_question_in_pool(question, QUESTIONS_POOL, debug=True)

    if result == question:
        print("✓ PASSED: Точное совпадение работает")
        return True
    else:
        print(f"✗ FAILED: Ожидали '{question}', получили '{result}'")
        return False


def test_normalized_match():
    """Тест 2: Совпадение с нормализацией (символы *, ?, !, .)"""
    print("\n" + "="*80)
    print("ТЕСТ 2: Нормализованное совпадение")
    print("="*80)

    test_cases = [
        ("Are you currently insured? *", "Are you currently insured?"),
        ("What's your gender? !", "What's your gender?"),
        ("Do you own or rent your home? ??", "Do you own or rent your home?"),
    ]

    all_passed = True
    for search_text, expected in test_cases:
        print(f"\n- Поиск: '{search_text}'")
        result = find_question_in_pool(search_text, QUESTIONS_POOL, debug=False)

        if result == expected:
            print(f"  ✓ PASSED: Найдено '{result}'")
        else:
            print(f"  ✗ FAILED: Ожидали '{expected}', получили '{result}'")
            all_passed = False

    return all_passed


def test_substring_match():
    """Тест 3: Substring matching (частичное совпадение)"""
    print("\n" + "="*80)
    print("ТЕСТ 3: Substring matching")
    print("="*80)

    test_cases = [
        ("What's your car make? *", "What's your car make?"),  # С символами
        ("What's your car year", "What's your car year?"),  # Без знака вопроса
        ("Do you own or rent your home", "Do you own or rent your home?"),  # Без знака вопроса
    ]

    all_passed = True
    for search_text, expected in test_cases:
        print(f"\n- Поиск: '{search_text}'")
        result = find_question_in_pool(search_text, QUESTIONS_POOL, debug=True)

        if result == expected:
            print(f"  ✓ PASSED: Найдено '{result}'")
        else:
            print(f"  ✗ FAILED: Ожидали '{expected}', получили '{result}'")
            all_passed = False

    return all_passed


def test_not_found():
    """Тест 4: Вопрос НЕ в пуле"""
    print("\n" + "="*80)
    print("ТЕСТ 4: Вопрос НЕ найден в пуле")
    print("="*80)

    question = "This question does not exist in the pool"
    result = find_question_in_pool(question, QUESTIONS_POOL, debug=True)

    if result is None:
        print("✓ PASSED: Корректно вернул None для несуществующего вопроса")
        return True
    else:
        print(f"✗ FAILED: Ожидали None, получили '{result}'")
        return False


def test_dynamic_order():
    """Тест 5: Симуляция динамического порядка вопросов"""
    print("\n" + "="*80)
    print("ТЕСТ 5: Динамический порядок вопросов")
    print("="*80)
    print("\nСимулируем ситуацию: вопросы на странице идут в разном порядке\n")

    # Порядок 1: Обычный (1, 2, 3)
    order1 = [
        "Are you currently insured?",
        "Are you looking to buy",
        "Do you own or rent your home?"
    ]

    # Порядок 2: Перемешанный (3, 1, 2)
    order2 = [
        "Do you own or rent your home?",
        "Are you currently insured?",
        "Are you looking to buy"
    ]

    # Порядок 3: С вариациями текста (символы, лишние слова)
    order3 = [
        "What's your gender? *",
        "Are you currently insured? !",
        "What's your car year? ?"
    ]

    all_passed = True

    for order_num, questions in enumerate([order1, order2, order3], 1):
        print(f"\n--- Порядок {order_num} ---")
        for q in questions:
            result = find_question_in_pool(q, QUESTIONS_POOL, debug=False)
            if result:
                print(f"  ✓ '{q}' → найден как '{result}'")
            else:
                print(f"  ✗ '{q}' → НЕ НАЙДЕН!")
                all_passed = False

    if all_passed:
        print("\n✓ PASSED: Все вопросы найдены во всех порядках")
    else:
        print("\n✗ FAILED: Некоторые вопросы не найдены")

    return all_passed


def test_performance():
    """Тест 6: Проверка производительности O(1) lookup"""
    print("\n" + "="*80)
    print("ТЕСТ 6: Производительность (100 вопросов)")
    print("="*80)

    import time

    # Создаем большой пул (100 вопросов)
    large_pool = {}
    for i in range(100):
        large_pool[f"Question number {i}?"] = {
            "actions": [{"type": "button_click", "name": f"Answer {i}"}]
        }

    # Ищем вопрос в конце пула
    search_question = "Question number 99?"

    start = time.time()
    result = find_question_in_pool(search_question, large_pool, debug=False)
    elapsed = time.time() - start

    print(f"\nПул: {len(large_pool)} вопросов")
    print(f"Поиск: '{search_question}'")
    print(f"Результат: '{result}'")
    print(f"Время: {elapsed*1000:.3f} мс")

    if result and elapsed < 0.001:  # Должно быть < 1 мс
        print("\n✓ PASSED: Поиск моментальный (O(1))")
        return True
    else:
        print("\n✗ FAILED: Поиск слишком медленный или не найден")
        return False


def main():
    """Запуск всех тестов"""
    print("="*80)
    print("ТЕСТ ДИНАМИЧЕСКОЙ СИСТЕМЫ ПОИСКА ВОПРОСОВ")
    print("="*80)
    print(f"\nВсего вопросов в пуле: {len(QUESTIONS_POOL)}")
    print("\nПеречень вопросов:")
    for i, q in enumerate(QUESTIONS_POOL.keys(), 1):
        print(f"  {i}. '{q}'")

    tests = [
        ("Exact Match", test_exact_match),
        ("Normalized Match", test_normalized_match),
        ("Substring Match", test_substring_match),
        ("Not Found", test_not_found),
        ("Dynamic Order", test_dynamic_order),
        ("Performance", test_performance),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n✗ EXCEPTION in {test_name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    # Итоги
    print("\n" + "="*80)
    print("ИТОГИ ТЕСТИРОВАНИЯ")
    print("="*80)

    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{status}: {test_name}")

    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)

    print("\n" + "="*80)
    print(f"Пройдено: {passed_count}/{total_count}")

    if passed_count == total_count:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("\nСИСТЕМА ДИНАМИЧЕСКОГО ПОИСКА РАБОТАЕТ КОРРЕКТНО:")
        print("  • Точное совпадение - OK")
        print("  • Нормализация текста (*, ?, !, .) - OK")
        print("  • Fuzzy matching (substring) - OK")
        print("  • Динамический порядок вопросов - OK")
        print("  • Производительность O(1) - OK")
        print("\nТеперь можно тестировать с реальным Octobrowser API токеном!")
    else:
        print("\n⚠️  ЕСТЬ ОШИБКИ - см. детали выше")

    print("="*80)

    return passed_count == total_count


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
