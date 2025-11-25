#!/usr/bin/env python3
"""
Тест fuzzy matching для отладки проблемы
"""

def normalize_text(text: str) -> str:
    """Нормализует текст для сравнения"""
    # Убираем пунктуацию и делаем lowercase
    normalized = text.lower()
    for char in ['?', '!', '.', '*', ':', ',']:
        normalized = normalized.replace(char, '')
    return normalized.strip()

def find_question_in_pool(question_text: str, pool: dict):
    """Упрощенная версия find_question_in_pool с debug выводом"""
    print(f"\n{'='*80}")
    print(f"Ищу вопрос: '{question_text}'")
    print(f"{'='*80}")

    # 1. Точное совпадение
    if question_text in pool:
        print(f"✅ НАЙДЕНО (точное): '{question_text}'")
        return question_text

    # 2. Нормализованное совпадение
    normalized_question = normalize_text(question_text)
    print(f"Нормализован: '{normalized_question}'")

    for pool_key in pool.keys():
        normalized_key = normalize_text(pool_key)

        # Точное совпадение нормализованных
        if normalized_question == normalized_key:
            print(f"✅ НАЙДЕНО (нормализованное): '{pool_key}'")
            return pool_key

        # Частичное совпадение
        if normalized_key in normalized_question or normalized_question in normalized_key:
            len_ratio = min(len(normalized_key), len(normalized_question)) / max(len(normalized_key), len(normalized_question))
            print(f"  Проверяю частичное совпадение с '{pool_key}':")
            print(f"    Pool key normalized: '{normalized_key}'")
            print(f"    Len ratio: {len_ratio:.2f} (need > 0.55)")

            if len_ratio > 0.55:
                print(f"✅ НАЙДЕНО (частичное, ratio={len_ratio:.2f}): '{pool_key}'")
                return pool_key
            else:
                print(f"❌ Отклонено (ratio={len_ratio:.2f} < 0.55)")

    print(f"❌ НЕ НАЙДЕНО")
    return None


# Тестовый пул с неполными вопросами из вашего user_code
QUESTIONS_POOL = {
    "Are you currently insured?": {"actions": []},
    "Are you looking to buy": {"actions": []},  # Неполный!
    "Do you own or rent your home?": {"actions": []},
    "Why are you shopping for": {"actions": []},  # Неполный!
    "How soon do you need your": {"actions": []},  # Неполный!
    "What's your car year?": {"actions": []},
    "Want to get more quotes for your": {"actions": []},  # Неполный!
    "Do you have an active U.S.": {"actions": []},  # Неполный!
}

# Тестовые вопросы - полные версии того что может быть на странице
test_questions = [
    # Полные версии неполных вопросов
    "Are you looking to buy a home?",
    "Why are you shopping for insurance?",
    "How soon do you need your coverage?",
    "Want to get more quotes for your car?",
    "Do you have an active U.S. driver's license?",

    # Вопросы с дополнительными символами
    "Are you currently insured? *",
    "What's your car year? *",

    # Вопросы которых нет в пуле
    "Do you have any pets?",
    "What is your occupation?",
]

print("="*80)
print("ТЕСТ FUZZY MATCHING")
print("="*80)
print(f"\nВ пуле {len(QUESTIONS_POOL)} вопросов:")
for i, q in enumerate(QUESTIONS_POOL.keys(), 1):
    print(f"  {i}. '{q}'")

print(f"\n\nПроверяю {len(test_questions)} тестовых вопросов:\n")

success_count = 0
fail_count = 0

for test_q in test_questions:
    result = find_question_in_pool(test_q, QUESTIONS_POOL)
    if result:
        success_count += 1
    else:
        fail_count += 1

print("\n" + "="*80)
print(f"ИТОГИ:")
print(f"  ✅ Найдено: {success_count}/{len(test_questions)}")
print(f"  ❌ Не найдено: {fail_count}/{len(test_questions)}")
print("="*80)
