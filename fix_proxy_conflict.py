#!/usr/bin/env python3
"""
Скрипт для исправления конфликта прокси в сгенерированных скриптах

Проблемы:
1. USE_PROXY_LIST = True и NINE_PROXY_ENABLED = True одновременно
2. Порт 6000 в NINE_PROXY_PORTS (проблемный)

Решение:
- Если 9Proxy включен -> отключаем обычные прокси
- Исключаем порт 6000 из списка портов
"""

import re
import sys
import os
from pathlib import Path


def fix_proxy_conflict(script_content):
    """
    Исправляет конфликт прокси в скрипте

    Returns:
        (fixed_content, changes_made)
    """
    changes = []

    # Проверяем, есть ли 9Proxy
    has_nine_proxy = 'NINE_PROXY_ENABLED = True' in script_content

    if not has_nine_proxy:
        return script_content, ["[INFO] 9Proxy не включен, пропускаю"]

    # 1. Исправление конфликта: отключаем USE_PROXY_LIST если 9Proxy включен
    if 'USE_PROXY_LIST = True' in script_content and has_nine_proxy:
        script_content = script_content.replace(
            'USE_PROXY_LIST = True',
            'USE_PROXY_LIST = False  # Отключено: 9Proxy активен'
        )
        changes.append("[FIX] USE_PROXY_LIST отключен (9Proxy активен)")

    # 2. Отключаем USE_PROXY если включен
    if 'USE_PROXY = True' in script_content and has_nine_proxy:
        script_content = script_content.replace(
            'USE_PROXY = True',
            'USE_PROXY = False  # Отключено: 9Proxy активен'
        )
        changes.append("[FIX] USE_PROXY отключен (9Proxy активен)")

    # 3. Исключаем порт 6000 из NINE_PROXY_PORTS
    # Паттерн: NINE_PROXY_PORTS = [6000, 6001, 6002]
    ports_pattern = r'NINE_PROXY_PORTS\s*=\s*\[([^\]]+)\]'
    match = re.search(ports_pattern, script_content)

    if match:
        ports_str = match.group(1)
        # Парсим порты
        ports = [int(p.strip()) for p in ports_str.split(',') if p.strip().isdigit()]

        if 6000 in ports:
            # Исключаем порт 6000
            new_ports = [p for p in ports if p != 6000]

            if not new_ports:
                # Если после исключения не осталось портов - добавляем дефолтные
                new_ports = [6001, 6002]
                changes.append("[WARNING] После исключения 6000 не осталось портов. Добавлены дефолтные: [6001, 6002]")

            new_ports_str = ', '.join(map(str, new_ports))
            new_line = f'NINE_PROXY_PORTS = [{new_ports_str}]  # Порт 6000 исключен (таймауты)'

            script_content = re.sub(ports_pattern, new_line, script_content)
            changes.append(f"[FIX] Порт 6000 исключен. Новые порты: {new_ports}")

    return script_content, changes


def process_file(filepath):
    """Обрабатывает один файл"""
    print(f"\n{'='*80}")
    print(f"Обработка: {filepath}")
    print('='*80)

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        fixed_content, changes = fix_proxy_conflict(content)

        if not changes or all('[INFO]' in c for c in changes):
            print("[INFO] Изменения не требуются")
            return False

        # Показываем изменения
        for change in changes:
            print(change)

        # Сохраняем исправленный файл
        backup_path = str(filepath) + '.backup'
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"\n[BACKUP] Создан: {backup_path}")

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(fixed_content)
        print(f"[SAVE] Исправлен: {filepath}")

        return True

    except Exception as e:
        print(f"[ERROR] Ошибка обработки: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("="*80)
    print("ИСПРАВЛЕНИЕ КОНФЛИКТА ПРОКСИ В СГЕНЕРИРОВАННЫХ СКРИПТАХ")
    print("="*80)

    # Ищем сгенерированные скрипты
    generated_dir = Path('generated_scripts')

    if not generated_dir.exists():
        print("[ERROR] Папка generated_scripts не найдена!")
        return 1

    # Находим все Python файлы
    scripts = list(generated_dir.glob('*.py'))

    if not scripts:
        print("[INFO] Нет сгенерированных скриптов для обработки")
        return 0

    print(f"\n[INFO] Найдено скриптов: {len(scripts)}")

    # Спрашиваем подтверждение
    if len(sys.argv) > 1 and sys.argv[1] == '--auto':
        process_all = True
    else:
        answer = input("\nОбработать все скрипты? (y/n): ")
        process_all = answer.lower() in ['y', 'yes', 'да']

    if not process_all:
        print("[CANCEL] Отменено пользователем")
        return 0

    # Обрабатываем файлы
    fixed_count = 0
    for script_path in scripts:
        if process_file(script_path):
            fixed_count += 1

    print("\n" + "="*80)
    print(f"ЗАВЕРШЕНО: Исправлено {fixed_count} из {len(scripts)} скриптов")
    print("="*80)

    return 0


if __name__ == '__main__':
    sys.exit(main())
