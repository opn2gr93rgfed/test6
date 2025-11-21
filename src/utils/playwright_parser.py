"""
Парсер для Playwright кода
Конвертирует Playwright тесты в формат auto2tesst с параметризацией
"""

import re
from typing import Dict, List, Optional
from .phone_detector import PhoneAndOTPDetector


class PlaywrightParser:
    """Парсер для Playwright тестов"""

    def __init__(self, otp_enabled: bool = False):
        self.extracted_values = []  # Извлеченные значения для параметризации
        self.variable_names = []     # Имена переменных
        self.field_types = []         # Типы полей ('phone', 'otp', 'unknown')
        self.detector = PhoneAndOTPDetector()
        self.otp_enabled = otp_enabled  # Флаг включения OTP-обработки

        # Ручные подсказки от пользователя
        self.manual_phone_value = None  # Значение номера телефона из кода (например: "8434756290")
        self.manual_otp_value = None    # Значение OTP кода из кода (например: "3131323")

    def parse_playwright_code(self, code: str) -> Dict:
        """
        Парсит Playwright код и извлекает действия

        Args:
            code: Исходный код Playwright теста

        Returns:
            Dict с информацией:
            {
                'url': '...',
                'actions': [...],
                'values': [...],
                'csv_headers': [...],
                'converted_code': '...'
            }
        """
        self.extracted_values = []
        self.variable_names = []

        # Извлечь URL
        url = self._extract_url(code)

        # Извлечь все действия
        actions = self._extract_actions(code)

        # Оптимизировать действия
        optimized_actions = self._optimize_actions(actions)

        # Извлечь значения для параметризации
        self._extract_values_from_actions(optimized_actions)

        # Сгенерировать конвертированный код
        converted_code = self._generate_converted_code(optimized_actions, url)

        return {
            'url': url,
            'actions': optimized_actions,
            'values': self.extracted_values,
            'csv_headers': self.variable_names,
            'converted_code': converted_code
        }

    def set_manual_field_hints(self, phone_value: Optional[str] = None, otp_value: Optional[str] = None):
        """
        Установить ручные подсказки для определения типов полей

        Args:
            phone_value: Значение номера телефона из кода (например: "8434756290")
            otp_value: Значение OTP кода из кода (например: "3131323")

        Пример:
            parser.set_manual_field_hints(phone_value="8434756290", otp_value="3131323")
            # Теперь fill("8434756290") будет помечено как phone_number
            # А fill("3131323") будет помечено как otp_code
        """
        self.manual_phone_value = phone_value
        self.manual_otp_value = otp_value
        print(f"[PARSER] Ручные подсказки установлены:")
        if phone_value:
            print(f"  - Номер телефона: {phone_value}")
        if otp_value:
            print(f"  - OTP код: {otp_value}")

    def _extract_url(self, code: str) -> str:
        """Извлекает URL из page.goto()"""
        match = re.search(r'page\.goto\(["\'](.+?)["\']\)', code)
        if match:
            return match.group(1)
        return ''

    def _extract_actions(self, code: str) -> List[Dict]:
        """Извлекает действия из Playwright кода"""
        actions = []
        lines = code.split('\n')

        # Переменные для отслеживания блоков альтернатив
        in_alternative_block = False
        current_alternative_group = []
        current_alternative_variant = []

        # === OCTO BROWSER POPUP HANDLER ===
        # Переменные для отслеживания блоков с попапами
        in_popup_block = False
        popup_info_var = None
        popup_trigger_lines = []
        popup_base_indent = 0

        for i, line in enumerate(lines):
            line = line.strip()

            # Обработка маркеров альтернатив
            if line.startswith('# ALTERNATIVE START') or (line == '# ALTERNATIVE' and not in_alternative_block):
                # Начало блока альтернатив
                in_alternative_block = True
                current_alternative_group = []
                current_alternative_variant = []
                continue

            elif line == '# ALTERNATIVE' and in_alternative_block:
                # Разделитель между вариантами
                if current_alternative_variant:
                    current_alternative_group.append(current_alternative_variant)
                    current_alternative_variant = []
                continue

            elif line.startswith('# ALTERNATIVE END'):
                # Конец блока альтернатив
                if current_alternative_variant:
                    current_alternative_group.append(current_alternative_variant)

                # Добавить блок альтернатив как одно действие
                if current_alternative_group:
                    actions.append({
                        'type': 'alternatives',
                        'variants': current_alternative_group,
                        'line': i
                    })

                in_alternative_block = False
                current_alternative_group = []
                current_alternative_variant = []
                continue

            # === RANDOM ANSWER SUPPORT ADDED ===
            # Проверить на маркер #random или #random[min-max]
            if line.strip().startswith('#random'):
                # Извлечь параметры min-max если есть
                min_opt = 1
                max_opt = 100
                range_match = re.search(r'#random\[(\d+)-(\d+)\]', line)
                if range_match:
                    min_opt = int(range_match.group(1))
                    max_opt = int(range_match.group(2))

                action = {
                    'type': 'random_marker',
                    'min_options': min_opt,
                    'max_options': max_opt,
                    'line': i
                }
                if in_alternative_block:
                    current_alternative_variant.append(action)
                else:
                    actions.append(action)
                continue

            # === OCTO BROWSER POPUP HANDLER ===
            # Обработка with page.expect_popup()
            original_line = lines[i]

            # Начало popup блока
            popup_match = re.search(r'^\s*with\s+page\.expect_popup\(\)\s+as\s+(\w+):', original_line)
            if popup_match:
                in_popup_block = True
                popup_info_var = popup_match.group(1)
                popup_trigger_lines = []
                popup_base_indent = len(original_line) - len(original_line.lstrip())
                continue

            # Внутри popup блока - собираем trigger действия
            if in_popup_block:
                current_indent = len(original_line) - len(original_line.lstrip())

                # Если отступ вернулся на уровень with или меньше - блок закончился
                if current_indent <= popup_base_indent and line:
                    # Проверяем, это pageX = xxx_info.value?
                    value_match = re.search(rf'^\s*(\w+)\s*=\s*{re.escape(popup_info_var)}\.value', original_line)
                    if value_match:
                        page_var = value_match.group(1)

                        # Создаем action для popup
                        action = {
                            'type': 'popup',
                            'page_var': page_var,
                            'trigger_lines': popup_trigger_lines,
                            'line': i
                        }
                        if in_alternative_block:
                            current_alternative_variant.append(action)
                        else:
                            actions.append(action)

                    # Выходим из popup блока
                    in_popup_block = False
                    popup_info_var = None
                    popup_trigger_lines = []
                    # Не continue - обработаем эту строку как обычно
                else:
                    # Внутри блока - сохраняем строку trigger
                    if line:  # Пропускаем пустые строки
                        popup_trigger_lines.append(line)
                    continue

            # Пропустить обычные комментарии и пустые строки
            if not line or line.startswith('#') or line.startswith('//'):
                continue

            # page.goto() - переход на страницу
            if 'page.goto(' in line:
                url_match = re.search(r'page\.goto\(["\'](.+?)["\']\)', line)
                if url_match:
                    action = {
                        'type': 'goto',
                        'url': url_match.group(1),
                        'line': i
                    }
                    if in_alternative_block:
                        current_alternative_variant.append(action)
                    else:
                        actions.append(action)
                continue

            # .click() - клик
            if '.click()' in line:
                selector = self._extract_playwright_selector(line)
                if selector:
                    action = {
                        'type': 'click',
                        'selector': selector,
                        'line': i
                    }
                    if in_alternative_block:
                        current_alternative_variant.append(action)
                    else:
                        actions.append(action)
                continue

            # .fill() - ввод текста
            if '.fill(' in line:
                selector = self._extract_playwright_selector(line)
                value_match = re.search(r"\.fill\(['\"](.+?)['\"]\)", line)
                if value_match:
                    # Даже если селектор не распознан, сохраняем действие
                    action = {
                        'type': 'fill',
                        'selector': selector or {'type': 'unknown', 'original': line},
                        'value': value_match.group(1),
                        'line': i
                    }
                    if in_alternative_block:
                        current_alternative_variant.append(action)
                    else:
                        actions.append(action)
                continue

            # .type() - постепенный ввод текста
            if '.type(' in line:
                selector = self._extract_playwright_selector(line)
                value_match = re.search(r"\.type\(['\"](.+?)['\"]\)", line)
                if value_match:
                    # Даже если селектор не распознан, сохраняем действие
                    action = {
                        'type': 'fill',  # Используем fill вместо type
                        'selector': selector or {'type': 'unknown', 'original': line},
                        'value': value_match.group(1),
                        'line': i
                    }
                    if in_alternative_block:
                        current_alternative_variant.append(action)
                    else:
                        actions.append(action)
                continue

        # Если блок альтернатив не был закрыт - закрыть автоматически
        if in_alternative_block and current_alternative_variant:
            current_alternative_group.append(current_alternative_variant)
        if current_alternative_group:
            actions.append({
                'type': 'alternatives',
                'variants': current_alternative_group
            })

        return actions

    def _extract_playwright_selector(self, line: str) -> Optional[Dict]:
        """
        Извлекает Playwright селектор из строки кода

        Поддерживает полные цепочки методов:
        - page.locator("div").filter(has_text="...").first.click()
        - page.get_by_role('button', name='Submit').click()
        - page.get_by_test_id('submit').fill("text")
        """
        # Извлечь полную цепочку от page. до действия (.click(), .fill(), .type())
        # Ищем от page. до .click()/.fill()/.type()
        chain_match = re.search(r'page\.(.+?)\.(?:click|fill|type)\s*\(', line)
        if not chain_match:
            return None

        chain = chain_match.group(1)  # Цепочка без page. и без .click()

        # Проверить, есть ли модификаторы (.first, .last, .nth())
        modifier = None
        if '.first' in chain:
            modifier = 'first'
            chain = chain.replace('.first', '')
        elif '.last' in chain:
            modifier = 'last'
            chain = chain.replace('.last', '')
        elif '.nth(' in chain:
            nth_match = re.search(r'\.nth\((\d+)\)', chain)
            if nth_match:
                modifier = f'nth({nth_match.group(1)})'
                chain = re.sub(r'\.nth\(\d+\)', '', chain)

        # Сохранить полную цепочку для генерации
        return {
            'type': 'chain',
            'chain': chain.strip(),
            'modifier': modifier,
            'original': line
        }

    def _optimize_actions(self, actions: List[Dict]) -> List[Dict]:
        """
        Оптимизирует действия:
        - Убирает избыточные клики перед fill
        """
        optimized = []
        i = 0

        while i < len(actions):
            current = actions[i]
            next_action = actions[i + 1] if i + 1 < len(actions) else None

            # Если это клик и следующее - fill на том же элементе, пропустить клик
            if (current['type'] == 'click' and
                next_action and
                next_action['type'] == 'fill' and
                current.get('selector') == next_action.get('selector')):
                # Пропустить клик, он избыточен
                i += 1
                continue

            optimized.append(current)
            i += 1

        return optimized

    def _extract_values_from_actions(self, actions: List[Dict]):
        """Извлекает значения из действий для параметризации"""
        self.extracted_values = []
        self.variable_names = []
        self.field_types = []

        # Собрать все значения и метки
        values = []
        labels = []

        for action in actions:
            if action['type'] == 'fill' and 'value' in action:
                values.append(action['value'])
                # Попытаться получить метку из селектора
                label = self._extract_label_from_selector(action.get('selector', {}))
                labels.append(label)

        # Анализировать значения с помощью детектора
        analysis = self.detector.analyze_script_data(values, labels)

        # Сохранить результаты
        for field in analysis['fields']:
            value = field['value']
            field_type = field['type']
            confidence = field['confidence']

            # ПРИОРИТЕТ 1: Ручные подсказки от пользователя
            if self.manual_phone_value and value == self.manual_phone_value:
                field_type = 'phone'
                print(f"[PARSER] ✓ Поле '{value}' помечено как PHONE (ручная подсказка)")
            elif self.manual_otp_value and value == self.manual_otp_value:
                field_type = 'otp'
                print(f"[PARSER] ✓ Поле '{value}' помечено как OTP (ручная подсказка)")
            # ПРИОРИТЕТ 2: Автоматическое определение детектором
            # (field_type уже установлен детектором)

            # Генерировать имя переменной на основе типа
            var_name = self._generate_variable_name_with_type(value, field_type, len(self.extracted_values))

            self.extracted_values.append(value)
            self.variable_names.append(var_name)
            self.field_types.append(field_type)

    def _extract_label_from_selector(self, selector: Dict) -> Optional[str]:
        """Извлекает метку из селектора для анализа типа поля"""
        if not selector:
            return None

        sel_type = selector.get('type')

        # Для цепочки методов - попытаться извлечь метку из строки
        if sel_type == 'chain':
            chain = selector.get('chain', '')

            # Искать get_by_label
            label_match = re.search(r"get_by_label\(['\"](.+?)['\"]\)", chain)
            if label_match:
                return label_match.group(1)

            # Искать get_by_placeholder
            placeholder_match = re.search(r"get_by_placeholder\(['\"](.+?)['\"]\)", chain)
            if placeholder_match:
                return placeholder_match.group(1)

            # Искать name= в get_by_role
            name_match = re.search(r"name\s*=\s*['\"](.+?)['\"]", chain)
            if name_match:
                return name_match.group(1)

            # Искать get_by_test_id
            testid_match = re.search(r"get_by_test_id\(['\"](.+?)['\"]\)", chain)
            if testid_match:
                return testid_match.group(1)

            return None

        # Старые типы для обратной совместимости
        if sel_type == 'label':
            return selector.get('value')
        elif sel_type == 'placeholder':
            return selector.get('value')
        elif sel_type == 'role':
            return selector.get('name')
        elif sel_type == 'testid':
            return selector.get('value')

        return None

    def _generate_variable_name_with_type(self, value: str, field_type: str, index: int) -> str:
        """
        Генерирует имя переменной на основе типа поля

        Args:
            value: Значение поля
            field_type: Тип поля ('phone', 'otp', 'unknown')
            index: Индекс поля

        Returns:
            Имя переменной
        """
        # Если тип определен детектором
        if field_type == 'phone':
            # Подсчитать сколько уже есть phone полей
            phone_count = sum(1 for t in self.field_types if t == 'phone')
            if phone_count == 0:
                return 'phone_number'
            else:
                return f'phone_number_{phone_count + 1}'

        elif field_type == 'otp':
            # Подсчитать сколько уже есть OTP полей
            otp_count = sum(1 for t in self.field_types if t == 'otp')
            if otp_count == 0:
                return 'otp_code'
            else:
                return f'otp_code_{otp_count + 1}'

        # Для unknown - используем старую логику
        return self._generate_variable_name_legacy(value, index)

    def _generate_variable_name_legacy(self, value: str, index: int) -> str:
        """Генерирует имя переменной на основе значения (старая логика)"""
        # Определить тип значения
        if '@' in value and '.' in value:
            return 'email'

        # Дата с слешами
        if '/' in value and any(char.isdigit() for char in value):
            return 'date_of_birth'

        if value.isdigit():
            if len(value) == 8:
                return 'date_of_birth'
            else:
                return 'number'

        # Если первое значение - вероятно firstname, второе - lastname
        if index == 0:
            return 'firstname'
        elif index == 1:
            return 'lastname'
        elif index == 2 and '@' not in value:
            return 'address'
        else:
            # Простое текстовое значение
            if len(value) <= 10:
                clean = re.sub(r'[^a-z0-9]', '', value.lower())
                if clean:
                    return clean[:10]
            return f'field_{index + 1}'

    def _generate_converted_code(self, actions: List[Dict], url: str) -> str:
        """Генерирует конвертированный код для Playwright"""
        code_lines = []
        var_index = 0

        # === SMART BUTTON HANDLER ADDED ===
        # Добавить определение вспомогательной SYNC функции smart_click_button в начало
        code_lines.append('# === SMART BUTTON CLICK HANDLER ===')
        code_lines.append('# Функция для устойчивого клика по кнопкам (независимо от порядка появления)')
        code_lines.append('def smart_click_button(page, name: str, exact: bool = False):')
        code_lines.append('    """Умный клик по кнопке с ожиданием появления"""')
        code_lines.append('    locator = page.get_by_role("button", name=name, exact=exact)')
        code_lines.append('    try:')
        code_lines.append('        locator.wait_for(state="visible", timeout=30000)')
        code_lines.append('        if locator.is_visible():')
        code_lines.append('            print(f"[SMART CLICK] Кликаю кнопку: {name}")')
        code_lines.append('            locator.click(delay=100)')
        code_lines.append('            page.wait_for_load_state("networkidle", timeout=10000)')
        code_lines.append('    except Exception as e:')
        code_lines.append('        print(f"[SMART CLICK] Кнопка \'{name}\' не появилась за 30 сек или уже была обработана: {e}")')
        code_lines.append('')
        code_lines.append('# === END SMART BUTTON HANDLER ===')
        code_lines.append('')

        # === SMART QUESTION-ANSWER HANDLER ADDED ===
        code_lines.append('# === SMART QUESTION-ANSWER HANDLER ===')
        code_lines.append('# Функция для устойчивого ответа на вопросы (клик по heading → ответ на button)')
        code_lines.append('def answer_question(page, heading: str, answer_button: str, exact: bool = False):')
        code_lines.append('    """Ждёт появления вопроса (heading) и кликает по кнопке ответа"""')
        code_lines.append('    print(f"[ANSWER] Жду вопрос: {heading}")')
        code_lines.append('    heading_locator = page.get_by_role("heading", name=heading, exact=True)')
        code_lines.append('    try:')
        code_lines.append('        heading_locator.wait_for(state="visible", timeout=35000)')
        code_lines.append('        print(f"[ANSWER] Вопрос появился: {heading} → отвечаю: {answer_button}")')
        code_lines.append('        smart_click_button(page, answer_button, exact=exact)')
        code_lines.append('    except Exception as e:')
        code_lines.append('        print(f"[ANSWER] Вопрос \'{heading}\' не появился за 35 сек: {e}")')
        code_lines.append('')
        code_lines.append('# === END SMART QUESTION-ANSWER HANDLER ===')
        code_lines.append('')

        # === RANDOM ANSWER SUPPORT ADDED ===
        code_lines.append('# === RANDOM ANSWER SUPPORT ===')
        code_lines.append('# Функция для случайного ответа на вопрос (обход A/B тестов и антиботов)')
        code_lines.append('def answer_question_random(')
        code_lines.append('    page,')
        code_lines.append('    heading: str,')
        code_lines.append('    min_options: int = 1,')
        code_lines.append('    max_options: int = 100')
        code_lines.append('):')
        code_lines.append('    """Ждёт вопрос и выбирает случайный ответ из доступных кнопок"""')
        code_lines.append('    import random')
        code_lines.append('    ')
        code_lines.append('    print(f"[RANDOM] Жду вопрос: {heading}")')
        code_lines.append('    heading_locator = page.get_by_role("heading", name=heading, exact=True)')
        code_lines.append('    ')
        code_lines.append('    try:')
        code_lines.append('        heading_locator.wait_for(state="visible", timeout=35000)')
        code_lines.append('        print(f"[RANDOM] Вопрос появился: {heading} → ищу кнопки-ответы...")')
        code_lines.append('        ')
        code_lines.append('        # Попробовать найти контейнер с вопросом (поднимаемся на 2-3 уровня)')
        code_lines.append('        try:')
        code_lines.append('            parent = heading_locator.locator("xpath=ancestor::*[3]").first')
        code_lines.append('            if parent.count() > 0:')
        code_lines.append('                buttons = parent.get_by_role("button")')
        code_lines.append('            else:')
        code_lines.append('                buttons = page.get_by_role("button")')
        code_lines.append('        except:')
        code_lines.append('            buttons = page.get_by_role("button")')
        code_lines.append('        ')
        code_lines.append('        # Собрать все видимые кнопки')
        code_lines.append('        page.wait_for_timeout(1000)  # Дать время кнопкам появиться')
        code_lines.append('        all_buttons = buttons.all()')
        code_lines.append('        ')
        code_lines.append('        # Фильтр: только видимые кнопки с текстом (исключая навигационные)')
        code_lines.append('        visible_buttons = []')
        code_lines.append('        excluded_texts = ["back", "previous", "skip", "need help", "live chat", "help", "cancel", "close"]')
        code_lines.append('        ')
        code_lines.append('        for btn in all_buttons:')
        code_lines.append('            try:')
        code_lines.append('                if btn.is_visible():')
        code_lines.append('                    text = btn.inner_text().strip().lower()')
        code_lines.append('                    if text and text not in excluded_texts:')
        code_lines.append('                        visible_buttons.append(btn)')
        code_lines.append('            except:')
        code_lines.append('                continue')
        code_lines.append('        ')
        code_lines.append('        # Проверка количества вариантов')
        code_lines.append('        if len(visible_buttons) < min_options:')
        code_lines.append('            print(f"[RANDOM] Недостаточно вариантов: {len(visible_buttons)}, беру все доступные")')
        code_lines.append('        ')
        code_lines.append('        # Ограничить max_options')
        code_lines.append('        if len(visible_buttons) > max_options:')
        code_lines.append('            visible_buttons = visible_buttons[:max_options]')
        code_lines.append('        ')
        code_lines.append('        if not visible_buttons:')
        code_lines.append('            raise Exception(f"[RANDOM] Не найдено ни одной кнопки-ответа для вопроса: {heading}")')
        code_lines.append('        ')
        code_lines.append('        # Выбрать случайную кнопку')
        code_lines.append('        chosen = random.choice(visible_buttons)')
        code_lines.append('        answer_text = chosen.inner_text()')
        code_lines.append('        print(f"[RANDOM] Выбрал ответ {visible_buttons.index(chosen)+1}/{len(visible_buttons)}: {answer_text.strip()}")')
        code_lines.append('        ')
        code_lines.append('        # Кликнуть с имитацией человека')
        code_lines.append('        chosen.click(delay=150)')
        code_lines.append('        page.wait_for_load_state("networkidle", timeout=10000)')
        code_lines.append('        ')
        code_lines.append('    except Exception as e:')
        code_lines.append('        print(f"[RANDOM] Ошибка случайного ответа на вопрос \'{heading}\': {e}")')
        code_lines.append('')
        code_lines.append('# === END RANDOM ANSWER SUPPORT ===')
        code_lines.append('')

        # === OCTO BROWSER POPUP HANDLER ADDED ===
        code_lines.append('# === OCTO BROWSER POPUP HANDLER ===')
        code_lines.append('# Универсальный обработчик новых вкладок для Octo Browser')
        code_lines.append('def wait_and_switch_to_popup(page, context, trigger_action=None, timeout=15000):')
        code_lines.append('    """Надёжное переключение на новую вкладку в Octo Browser"""')
        code_lines.append('    print("[POPUP] Ожидаю открытия новой вкладки...")')
        code_lines.append('    before_pages = len(context.pages)')
        code_lines.append('    ')
        code_lines.append('    # Выполнить действие, которое откроет попап')
        code_lines.append('    if trigger_action:')
        code_lines.append('        trigger_action()')
        code_lines.append('    ')
        code_lines.append('    # Ждём появления новой вкладки (polling)')
        code_lines.append('    import time')
        code_lines.append('    start_time = time.time()')
        code_lines.append('    while len(context.pages) <= before_pages:')
        code_lines.append('        if (time.time() - start_time) * 1000 > timeout:')
        code_lines.append('            raise Exception(f"[POPUP] Новая вкладка не открылась за {timeout}ms")')
        code_lines.append('        time.sleep(0.1)')
        code_lines.append('    ')
        code_lines.append('    # Берём последнюю открывшуюся вкладку')
        code_lines.append('    new_page = context.pages[-1]')
        code_lines.append('    ')
        code_lines.append('    # Проверка что это действительно новая вкладка')
        code_lines.append('    if new_page == page:')
        code_lines.append('        new_page = context.pages[-2] if len(context.pages) > 1 else context.pages[-1]')
        code_lines.append('    ')
        code_lines.append('    # Гарантированно активируем и ждём загрузки')
        code_lines.append('    new_page.bring_to_front()')
        code_lines.append('    time.sleep(0.5)  # Дать время браузеру переключиться')
        code_lines.append('    new_page.wait_for_load_state("domcontentloaded", timeout=20000)')
        code_lines.append('    print(f"[POPUP] Переключились на новую вкладку: {new_page.url}")')
        code_lines.append('    ')
        code_lines.append('    return new_page')
        code_lines.append('')
        code_lines.append('# === END OCTO BROWSER POPUP HANDLER ===')
        code_lines.append('')

        # 🔥 Отслеживание номера страницы для маркеров
        current_page_number = 0
        page_started = False

        for action in actions:
            # 🔥 PAGE SECTION MARKER: Добавить маркер начала страницы при первом действии
            if not page_started and action['type'] in ['goto', 'click', 'fill']:
                code_lines.append(f'# {"="*80}')
                code_lines.append(f'# 🎯 PAGE {current_page_number} START: Initial Form')
                code_lines.append(f'# {"="*80}')
                code_lines.append('')
                page_started = True

            if action['type'] == 'goto':
                code_lines.append(f'# Переход на страницу')
                code_lines.append(f'try:')
                code_lines.append(f'    # Используем domcontentloaded вместо load - быстрее и надежнее')
                code_lines.append(f'    page.goto("{action["url"]}", wait_until="domcontentloaded", timeout=60000)')
                code_lines.append(f'    print("[OK] Страница загружена: {action["url"]}")')
                code_lines.append(f'    ')
                code_lines.append(f'    # 🔥 Убедиться что страница полностью готова')
                code_lines.append(f'    ensure_page_ready(page)')
                code_lines.append(f'    ')
                code_lines.append(f'    # 🔥 Закрыть маркетинговые опросники если появились')
                code_lines.append(f'    close_popup_if_exists(page)')
                code_lines.append(f'    ')
                code_lines.append(f'    page.wait_for_timeout(2000)  # Доп. пауза для загрузки JS')
                code_lines.append(f'except Exception as e:')
                code_lines.append(f'    print(f"[WARNING] Проблема при загрузке страницы: {{e}}")')
                code_lines.append(f'    print("[INFO] Продолжаем работу...")')
                code_lines.append('')

            elif action['type'] == 'alternatives':
                # Генерация кода для альтернативных сценариев
                variants = action['variants']
                code_lines.append('# ========== АЛЬТЕРНАТИВНЫЕ СЦЕНАРИИ ==========')
                code_lines.append('# Пробуем разные варианты UI (A/B тесты, модальные окна, разные состояния)')
                code_lines.append('alternative_success = False')
                code_lines.append('')

                for variant_idx, variant_actions in enumerate(variants, 1):
                    code_lines.append(f'# --- Вариант {variant_idx} ---')
                    code_lines.append(f'if not alternative_success:')
                    code_lines.append(f'    try:')
                    code_lines.append(f'        print("[ALTERNATIVE] Пробуем вариант {variant_idx}...")')

                    # Генерировать код для каждого действия в варианте
                    for sub_action in variant_actions:
                        if sub_action['type'] == 'click':
                            selector = sub_action['selector']
                            selector_code = self._generate_selector_code(selector)
                            code_lines.append(f'        page.{selector_code}.wait_for(state="visible", timeout=5000)')
                            code_lines.append(f'        page.{selector_code}.click()')
                            code_lines.append(f'        page.wait_for_timeout(1000)')

                        elif sub_action['type'] == 'fill':
                            selector = sub_action['selector']
                            selector_code = self._generate_selector_code(selector)
                            value = sub_action['value']
                            code_lines.append(f'        page.{selector_code}.wait_for(state="visible", timeout=5000)')
                            code_lines.append(f'        page.{selector_code}.fill("{value}")')
                            code_lines.append(f'        page.wait_for_timeout(500)')

                        elif sub_action['type'] == 'goto':
                            url = sub_action['url']
                            code_lines.append(f'        page.goto("{url}", wait_until="domcontentloaded", timeout=30000)')
                            code_lines.append(f'        page.wait_for_timeout(2000)')

                    code_lines.append(f'        print("[ALTERNATIVE] [SUCCESS] Вариант {variant_idx} сработал!")')
                    code_lines.append(f'        alternative_success = True')
                    code_lines.append(f'    except Exception as e:')
                    code_lines.append(f'        print(f"[ALTERNATIVE] Вариант {variant_idx} не сработал: {{e}}")')
                    code_lines.append('')

                code_lines.append('if not alternative_success:')
                code_lines.append('    print("[ALTERNATIVE] [WARNING] Ни один из вариантов не сработал, продолжаем...")')
                code_lines.append('')

            elif action['type'] == 'popup':
                # === OCTO BROWSER POPUP HANDLER ===
                # Генерация кода для обработки попапов
                page_var = action['page_var']
                trigger_lines = action['trigger_lines']

                # 🔥 PAGE SECTION MARKER: Закрыть предыдущую страницу и открыть новую
                if page_started:
                    code_lines.append(f'# {"="*80}')
                    code_lines.append(f'# ✅ PAGE {current_page_number} END')
                    code_lines.append(f'# {"="*80}')
                    code_lines.append('')

                current_page_number += 1

                code_lines.append(f'# {"="*80}')
                code_lines.append(f'# 🎯 PAGE {current_page_number} START: Popup Window ({page_var})')
                code_lines.append(f'# {"="*80}')
                code_lines.append('')

                code_lines.append(f'# Открытие новой вкладки (popup)')
                code_lines.append(f'{page_var} = wait_and_switch_to_popup(page, context,')
                code_lines.append(f'    trigger_action=lambda: (')

                # Добавить trigger действия (преобразовать sync в async не нужно, т.к. это lambda)
                for idx, trigger_line in enumerate(trigger_lines):
                    # Удалить await если есть (внутри lambda не работает)
                    clean_line = trigger_line.replace('await ', '')
                    if idx == len(trigger_lines) - 1:
                        # Последняя строка без запятой
                        code_lines.append(f'        {clean_line}')
                    else:
                        # Промежуточные строки с запятой
                        code_lines.append(f'        {clean_line},')

                code_lines.append(f'    )')
                code_lines.append(f')')
                code_lines.append(f'print(f"[POPUP] Переключились на новую вкладку {{page_var}}: {{{page_var}.url}}")')
                code_lines.append('')

            elif action['type'] == 'click':
                selector = action['selector']
                selector_code = self._generate_selector_code(selector)
                # Экранировать кавычки для использования в f-строке
                selector_code_escaped = selector_code.replace('"', '\\"')

                # === SMART BUTTON HANDLER ADDED ===
                # Проверить, является ли это кликом по кнопке
                is_button_click = self._is_button_click(selector_code)

                if is_button_click:
                    # Для кнопок - использовать smart_click_button (с await!)
                    button_name, exact = self._extract_button_params(selector_code)
                    if button_name:
                        code_lines.append(f'# Умный клик по кнопке: {button_name}')
                        if exact:
                            code_lines.append(f'smart_click_button(page, "{button_name}", exact=True)')
                        else:
                            code_lines.append(f'smart_click_button(page, "{button_name}")')
                        code_lines.append('')
                    else:
                        # Fallback если не смогли извлечь параметры
                        self._generate_standard_click_code(code_lines, selector_code, selector_code_escaped)
                else:
                    # Для остальных элементов (textbox, link, combobox и т.д.) - обычный код
                    self._generate_standard_click_code(code_lines, selector_code, selector_code_escaped)

            elif action['type'] == 'fill':
                selector = action['selector']
                selector_code = self._generate_selector_code(selector)
                # Экранировать кавычки для использования в f-строке
                selector_code_escaped = selector_code.replace('"', '\\"')
                var_name = self.variable_names[var_index] if var_index < len(self.variable_names) else f'field_{var_index + 1}'
                field_type = self.field_types[var_index] if var_index < len(self.field_types) else 'unknown'

                # СПЕЦИАЛЬНАЯ ЛОГИКА ДЛЯ OTP (с RETRY!) - ТОЛЬКО если OTP включен
                if self.otp_enabled and field_type == 'otp' and var_name.startswith('otp'):
                    code_lines.append(f'# ========== ПОЛУЧЕНИЕ OTP (ТОЛЬКО если SMS включен) ==========')
                    code_lines.append(f'if USE_SMS_PROVIDER and sms_activation_id:')
                    code_lines.append(f'    print("[OTP] Ожидание OTP кода...")')
                    code_lines.append(f'    otp_code = get_sms_code(sms_activation_id, timeout=180)')
                    code_lines.append(f'    if otp_code:')
                    code_lines.append(f'        data_row["{var_name}"] = otp_code  # Перезаписать OTP из CSV')
                    code_lines.append(f'        print(f"[OTP] [OK] Получен код: {{otp_code}}")')
                    code_lines.append(f'        # ЗАПИСЬ В CSV: сохранить полученный OTP для логирования')
                    code_lines.append(f'        update_csv_row(CSV_FILENAME, iteration_number - 1, otp_code=otp_code)')
                    code_lines.append(f'    else:')
                    code_lines.append(f'        print("[OTP ERROR] Не удалось получить OTP код")')
                    code_lines.append('')
                    code_lines.append(f'# ========== УМНЫЙ ВВОД OTP (множество стратегий) ==========')
                    code_lines.append(f'otp_entered = False')
                    code_lines.append(f'print("[OTP] Начинаем ввод OTP кода...")')
                    code_lines.append('')
                    code_lines.append(f'# СТРАТЕГИЯ 1: Прямой ввод через keyboard (если поле уже в фокусе)')
                    code_lines.append(f'try:')
                    code_lines.append(f'    print("[OTP] [Стратегия 1] Пробуем ввести в активное поле через keyboard...")')
                    code_lines.append(f'    page.wait_for_timeout(2000)  # Пауза для загрузки поля')
                    code_lines.append(f'    delay = random.randint(80, 120)')
                    code_lines.append(f'    page.keyboard.type(data_row["{var_name}"], delay=delay)')
                    code_lines.append(f'    print(f"[OTP] [SUCCESS] OTP введен через keyboard: {{data_row[\'{var_name}\']}}")')
                    code_lines.append(f'    otp_entered = True')
                    code_lines.append(f'except Exception as e:')
                    code_lines.append(f'    print(f"[OTP] [Стратегия 1] Не удалась: {{e}}")')
                    code_lines.append('')
                    code_lines.append(f'# СТРАТЕГИЯ 2: Поиск по generic селекторам (если keyboard не сработал)')
                    code_lines.append(f'if not otp_entered:')
                    code_lines.append(f'    fallback_selectors = [')
                    code_lines.append(f'        \'input[type="text"]:focus\',  # Поле в фокусе')
                    code_lines.append(f'        \'input[type="tel"]:focus\',   # Телефонное поле в фокусе')
                    code_lines.append(f'        \'input[autocomplete*="one-time"]\',  # OTP autocomplete')
                    code_lines.append(f'        \'input[name*="otp" i]\',  # name содержит otp')
                    code_lines.append(f'        \'input[name*="code" i]\',  # name содержит code')
                    code_lines.append(f'        \'input[placeholder*="code" i]\',  # placeholder содержит code')
                    code_lines.append(f'        \'input[type="text"]\',  # Любое текстовое поле')
                    code_lines.append(f'        \'input[type="tel"]\'  # Любое телефонное поле')
                    code_lines.append(f'    ]')
                    code_lines.append(f'    ')
                    code_lines.append(f'    for i, fallback_sel in enumerate(fallback_selectors, 1):')
                    code_lines.append(f'        try:')
                    code_lines.append(f'            print(f"[OTP] [Стратегия 2.{{i}}] Пробуем селектор: {{fallback_sel}}")')
                    code_lines.append(f'            otp_field = page.locator(fallback_sel).first')
                    code_lines.append(f'            otp_field.wait_for(state="visible", timeout=5000)')
                    code_lines.append(f'            otp_field.click()')
                    code_lines.append(f'            page.wait_for_timeout(500)')
                    code_lines.append(f'            otp_field.clear()')
                    code_lines.append(f'            delay = random.randint(80, 120)')
                    code_lines.append(f'            otp_field.press_sequentially(data_row["{var_name}"], delay=delay)')
                    code_lines.append(f'            print(f"[OTP] [SUCCESS] OTP введен через fallback селектор {{i}}: {{data_row[\'{var_name}\']}}")')
                    code_lines.append(f'            otp_entered = True')
                    code_lines.append(f'            break')
                    code_lines.append(f'        except Exception as e:')
                    code_lines.append(f'            print(f"[OTP] [Стратегия 2.{{i}}] Не удалась: {{e}}")')
                    code_lines.append(f'            continue')
                    code_lines.append('')
                    code_lines.append(f'# СТРАТЕГИЯ 3: Оригинальный селектор из recorder')
                    code_lines.append(f'if not otp_entered:')
                    code_lines.append(f'    try:')
                    code_lines.append(f'        print(f"[OTP] [Стратегия 3] Пробуем оригинальный селектор...")')
                    code_lines.append(f'        page.{selector_code}.wait_for(state="visible", timeout=10000)')
                    code_lines.append(f'        page.{selector_code}.click()')
                    code_lines.append(f'        page.wait_for_timeout(500)')
                    code_lines.append(f'        page.{selector_code}.clear()')
                    code_lines.append(f'        delay = random.randint(80, 120)')
                    code_lines.append(f'        page.{selector_code}.press_sequentially(data_row["{var_name}"], delay=delay)')
                    code_lines.append(f'        print(f"[OTP] [SUCCESS] OTP введен через оригинальный селектор: {{data_row[\'{var_name}\']}}")')
                    code_lines.append(f'        otp_entered = True')
                    code_lines.append(f'    except Exception as e:')
                    code_lines.append(f'        print(f"[OTP] [Стратегия 3] Не удалась: {{e}}")')
                    code_lines.append('')
                    code_lines.append(f'if not otp_entered:')
                    code_lines.append(f'    print("[OTP CRITICAL] Не удалось ввести OTP после всех стратегий!")')
                    code_lines.append('')

                    # TODO: OTP-module v2 — вынести в отдельный плагин, поддержка разных провайдеров SMS (sms-activate, 5sim и т.д.)

                # ОБЫЧНЫЕ ПОЛЯ (с имитацией человеческого ввода)
                else:
                    code_lines.append(f'# Ввод текста: {var_name}')
                    code_lines.append(f'print(f"DEBUG: Заполнение поля {var_name}: {selector_code_escaped}")')
                    code_lines.append(f'try:')
                    code_lines.append(f'    page.{selector_code}.wait_for(state="visible", timeout=20000)')
                    code_lines.append(f'    page.{selector_code}.scroll_into_view_if_needed()')
                    code_lines.append(f'    page.wait_for_timeout(500)')
                    code_lines.append(f'    page.{selector_code}.clear()')
                    code_lines.append(f'    # Имитация человеческого ввода')
                    code_lines.append(f'    delay = random.randint(50, 150)')
                    code_lines.append(f'    page.{selector_code}.press_sequentially(data_row["{var_name}"], delay=delay)')
                    code_lines.append(f'    print(f"[OK] Введено {{data_row[\'{var_name}\']}}")')
                    code_lines.append(f'except Exception as e:')
                    code_lines.append(f'    print(f"[WARNING] Не удалось заполнить поле {var_name}: {{e}}")')
                    code_lines.append(f'    print("[INFO] Пропускаем поле и продолжаем...")')
                    code_lines.append('')  # Пустая строка для разделения

                var_index += 1

            # === RANDOM ANSWER SUPPORT ADDED ===
            elif action['type'] == 'random_marker':
                # Вставить маркер для пост-обработки
                min_opt = action.get('min_options', 1)
                max_opt = action.get('max_options', 100)
                code_lines.append(f'# RANDOM_MARKER[{min_opt}-{max_opt}]')
                code_lines.append('')

        # 🔥 PAGE SECTION MARKER: Закрыть последнюю страницу
        if page_started:
            code_lines.append(f'# {"="*80}')
            code_lines.append(f'# ✅ PAGE {current_page_number} END')
            code_lines.append(f'# {"="*80}')
            code_lines.append('')

        # === SMART BUTTON HANDLER ADDED ===
        # Трансформация теперь происходит на этапе генерации, пост-обработка не нужна
        converted_code = '\n'.join(code_lines)

        # === RANDOM ANSWER SUPPORT ADDED ===
        # Пост-обработка: найти пары heading→#random и заменить на answer_question_random
        # ВАЖНО: Обрабатываем СНАЧАЛА #random, потом обычные кнопки!
        converted_code = self._transform_heading_random_pairs(converted_code)

        # === SMART QUESTION-ANSWER HANDLER ADDED ===
        # Пост-обработка: найти пары heading→button и заменить на answer_question
        converted_code = self._transform_heading_button_pairs(converted_code)

        return converted_code

    def _transform_heading_button_pairs(self, code: str) -> str:
        """
        === SMART QUESTION-ANSWER HANDLER ADDED ===
        Находит пары: клик по heading → клик по button (smart_click_button)
        Заменяет их на один вызов answer_question()

        Правила:
        1. Ищет клик по get_by_role("heading", name="...")
        2. Проверяет следующие 0-3 "действия"
        3. Если находит await smart_click_button(...) - это пара
        4. НЕ трогает если между ними есть fill()
        5. Заменяет оба на await answer_question(heading_text, button_text, exact=...)
        """
        lines = code.split('\n')
        i = 0
        skip_until = -1  # Индекс до которого нужно пропускать строки

        result_lines = []

        while i < len(lines):
            # Пропустить строки, которые являются частью замененной пары
            if i <= skip_until:
                i += 1
                continue

            line = lines[i]

            # Проверить, начинается ли блок клика по heading (комментарий "# Клик по элементу")
            if line.strip().startswith('# Клик по элементу'):
                # Проверить следующие строки на наличие heading click
                heading_click_idx = self._find_heading_click_in_block(lines, i)

                if heading_click_idx != -1:
                    # Нашли клик по heading
                    heading_text = self._extract_heading_text(lines[heading_click_idx])

                    if heading_text:
                        # Найти конец блока клика
                        block_end = self._find_click_block_end(lines, heading_click_idx)

                        # Искать smart_click_button после блока
                        search_start = block_end + 1
                        button_info = self._find_next_smart_click_button(lines, search_start, max_distance=20)

                        if button_info:
                            button_line_idx, button_text, exact = button_info

                            # Проверить что между ними нет fill()
                            has_fill = self._has_fill_between(lines, block_end, button_line_idx)

                            if not has_fill:
                                # ПАРА НАЙДЕНА! Заменяем оба блока на answer_question

                                # Найти комментарий перед smart_click_button (если есть)
                                smart_click_end = button_line_idx
                                # Пропустить пустую строку после smart_click_button
                                if button_line_idx + 1 < len(lines) and not lines[button_line_idx + 1].strip():
                                    smart_click_end = button_line_idx + 1

                                # Установить skip_until чтобы пропустить все строки пары
                                skip_until = smart_click_end

                                # Добавить answer_question вместо пары
                                result_lines.append('# Ответ на вопрос (heading → button)')
                                if exact:
                                    result_lines.append(f'answer_question(page, "{heading_text}", "{button_text}", exact=True)')
                                else:
                                    result_lines.append(f'answer_question(page, "{heading_text}", "{button_text}")')
                                result_lines.append('')

                                i += 1
                                continue

            # Если не нашли пару - оставить строку как есть
            result_lines.append(line)
            i += 1

        return '\n'.join(result_lines)

    def _find_heading_click_in_block(self, lines: List[str], start_idx: int) -> int:
        """
        Ищет строку с heading click в блоке (в пределах 15 строк от комментария)
        Возвращает индекс строки или -1
        """
        for i in range(start_idx, min(start_idx + 15, len(lines))):
            line = lines[i]
            if 'page.get_by_role("heading"' in line and '.click(' in line:
                return i
        return -1

    def _extract_heading_text(self, line: str) -> Optional[str]:
        """Извлекает текст из get_by_role("heading", name="...")"""
        # Паттерн с двойными кавычками
        pattern_double = r'get_by_role\("heading",\s*name="([^"]+)"\)'
        match = re.search(pattern_double, line)
        if match:
            return match.group(1)

        # Паттерн с одинарными кавычками
        pattern_single = r"get_by_role\('heading',\s*name='([^']+)'\)"
        match = re.search(pattern_single, line)
        if match:
            return match.group(1)

        return None

    def _find_click_block_end(self, lines: List[str], click_line_idx: int) -> int:
        """
        Находит конец блока клика (try-except + await page.wait_for_timeout)
        Возвращает индекс последней непустой строки блока
        """
        i = click_line_idx + 1

        # Пройтись до конца блока try-except
        in_try_block = True
        while i < len(lines):
            line = lines[i].strip()

            # Конец блока - пустая строка после await page.wait_for_timeout
            if not line:
                return i - 1

            # Или await page.wait_for_timeout с комментарием
            if 'page.wait_for_timeout' in line and '# Пауза' in line:
                return i

            i += 1

        return i - 1

    def _find_next_smart_click_button(self, lines: List[str], start_idx: int, max_distance: int = 20) -> Optional[tuple]:
        """
        Ищет следующий вызов smart_click_button в пределах max_distance строк

        Returns:
            (line_idx, button_text, exact) или None
        """
        for i in range(start_idx, min(start_idx + max_distance, len(lines))):
            line = lines[i]

            if 'smart_click_button(' in line:
                # Извлечь параметры
                # Паттерн с exact=True
                pattern_exact = r'await smart_click_button\("([^"]+)",\s*exact=True\)'
                match = re.search(pattern_exact, line)
                if match:
                    return (i, match.group(1), True)

                # Паттерн без exact
                pattern = r'await smart_click_button\("([^"]+)"\)'
                match = re.search(pattern, line)
                if match:
                    return (i, match.group(1), False)

        return None

    def _has_fill_between(self, lines: List[str], start_idx: int, end_idx: int) -> bool:
        """
        Проверяет есть ли fill() между двумя индексами
        Если есть - это НЕ пара вопрос-ответ
        """
        for i in range(start_idx, end_idx):
            line = lines[i]
            if '.fill(' in line or '.press_sequentially(' in line:
                return True
        return False

    def _transform_heading_random_pairs(self, code: str) -> str:
        """
        === RANDOM ANSWER SUPPORT ADDED ===
        Находит пары: клик по heading → # RANDOM_MARKER[min-max]
        Заменяет их на один вызов answer_question_random()

        Правила:
        1. Ищет клик по get_by_role("heading", name="...")
        2. Проверяет следующие строки на наличие # RANDOM_MARKER[min-max]
        3. Заменяет оба на await answer_question_random(heading="...", min_options=min, max_options=max)
        """
        lines = code.split('\n')
        i = 0
        skip_until = -1

        result_lines = []

        while i < len(lines):
            # Пропустить строки, которые являются частью замененной пары
            if i <= skip_until:
                i += 1
                continue

            line = lines[i]

            # Проверить, начинается ли блок клика по heading
            if line.strip().startswith('# Клик по элементу'):
                # Проверить следующие строки на наличие heading click
                heading_click_idx = self._find_heading_click_in_block(lines, i)

                if heading_click_idx != -1:
                    # Нашли клик по heading
                    heading_text = self._extract_heading_text(lines[heading_click_idx])

                    if heading_text:
                        # Найти конец блока клика
                        block_end = self._find_click_block_end(lines, heading_click_idx)

                        # Искать # RANDOM_MARKER после блока (может быть через кнопки)
                        search_start = block_end + 1
                        random_marker_info = self._find_random_marker(lines, search_start, max_distance=50)

                        if random_marker_info:
                            marker_line_idx, min_opt, max_opt = random_marker_info

                            # ПАРА НАЙДЕНА! Проверить что между heading и #random только кнопки (не fill)
                            # Это нормально - пользователь показал варианты ответов
                            has_fill = self._has_fill_between(lines, block_end, marker_line_idx)

                            if not has_fill:
                                # Установить skip_until чтобы пропустить все строки пары (включая промежуточные кнопки)
                                skip_until = marker_line_idx
                                if marker_line_idx + 1 < len(lines) and not lines[marker_line_idx + 1].strip():
                                    skip_until = marker_line_idx + 1

                                # Добавить answer_question_random вместо пары
                                result_lines.append('# Случайный ответ на вопрос (heading → #random)')
                                if min_opt == 1 and max_opt == 100:
                                    # Стандартные параметры - не указываем
                                    result_lines.append(f'answer_question_random(page, "{heading_text}")')
                                else:
                                    # Кастомные параметры
                                    result_lines.append(f'answer_question_random(page, "{heading_text}", min_options={min_opt}, max_options={max_opt})')
                                result_lines.append('')

                                i += 1
                                continue

            # Если не нашли пару - оставить строку как есть
            result_lines.append(line)
            i += 1

        return '\n'.join(result_lines)

    def _find_random_marker(self, lines: List[str], start_idx: int, max_distance: int = 10) -> Optional[tuple]:
        """
        Ищет следующий # RANDOM_MARKER[min-max] в пределах max_distance строк

        Returns:
            (line_idx, min_options, max_options) или None
        """
        for i in range(start_idx, min(start_idx + max_distance, len(lines))):
            line = lines[i].strip()

            if line.startswith('# RANDOM_MARKER'):
                # Извлечь параметры [min-max]
                pattern = r'# RANDOM_MARKER\[(\d+)-(\d+)\]'
                match = re.search(pattern, line)
                if match:
                    min_opt = int(match.group(1))
                    max_opt = int(match.group(2))
                    return (i, min_opt, max_opt)

        return None

    def _transform_popup_handlers(self, code: str) -> str:
        """
        === OCTO BROWSER POPUP HANDLER ADDED ===
        Находит конструкции with page.expect_popup() и заменяет на wait_and_switch_to_popup()

        Было:
            with page.expect_popup() as page1_info:
                page.get_by_role("button", name="View quotes").click()
            page1 = page1_info.value

        Стало:
            page1 = wait_and_switch_to_popup(
                trigger_action=lambda: smart_click_button("View quotes")
            )
        """
        lines = code.split('\n')
        i = 0
        result_lines = []
        skip_until = -1

        while i < len(lines):
            # Пропустить строки, которые уже обработаны
            if i <= skip_until:
                i += 1
                continue

            line = lines[i]

            # Ищем конструкцию with page.expect_popup() as xxx_info:
            popup_match = re.search(r'^\s*with\s+page\.expect_popup\(\)\s+as\s+(\w+):', line)

            if popup_match:
                info_var = popup_match.group(1)  # например: page1_info
                base_indent = len(line) - len(line.lstrip())

                # Собрать все строки внутри with блока
                trigger_lines = []
                j = i + 1
                while j < len(lines):
                    next_line = lines[j]
                    if not next_line.strip():
                        # Пустая строка - пропустить
                        j += 1
                        continue

                    line_indent = len(next_line) - len(next_line.lstrip())
                    if line_indent <= base_indent:
                        # Конец with блока
                        break

                    # Это строка внутри with - добавить
                    trigger_lines.append(next_line.strip())
                    j += 1

                # Теперь ищем строку pageX = xxx_info.value
                value_line_idx = -1
                page_var = None

                # Проверить следующие несколько строк после with блока
                for k in range(j, min(j + 5, len(lines))):
                    value_match = re.search(rf'^\s*(\w+)\s*=\s*{re.escape(info_var)}\.value', lines[k])
                    if value_match:
                        page_var = value_match.group(1)  # например: page1
                        value_line_idx = k
                        break

                if page_var and trigger_lines:
                    # ТРАНСФОРМАЦИЯ НАЙДЕНА!
                    # Создать lambda из trigger_lines
                    if len(trigger_lines) == 1:
                        trigger_action = trigger_lines[0]
                    else:
                        # Несколько строк - объединить
                        trigger_action = '; '.join(trigger_lines)

                    # Заменить на wait_and_switch_to_popup
                    result_lines.append(f'{" " * base_indent}{page_var} = wait_and_switch_to_popup(')
                    result_lines.append(f'{" " * (base_indent + 4)}trigger_action=lambda: {trigger_action}')
                    result_lines.append(f'{" " * base_indent})')

                    # Пропустить все строки до конца value assignment
                    skip_until = value_line_idx
                    i += 1
                    continue

            # Если не нашли паттерн - оставить строку как есть
            result_lines.append(line)
            i += 1

        return '\n'.join(result_lines)

    def _is_button_click(self, selector_code: str) -> bool:
        """
        === SMART BUTTON HANDLER ADDED ===
        Проверяет является ли селектор кликом по кнопке
        """
        return 'get_by_role("button"' in selector_code or "get_by_role('button'" in selector_code

    def _extract_button_params(self, selector_code: str) -> tuple:
        """
        === SMART BUTTON HANDLER ADDED ===
        Извлекает параметры name и exact из селектора кнопки

        Returns:
            (button_name, exact) или (None, False) если не удалось извлечь
        """
        # Паттерн с exact=True (двойные кавычки)
        pattern_exact_double = r'get_by_role\("button",\s*name="([^"]+)",\s*exact=True\)'
        match = re.search(pattern_exact_double, selector_code)
        if match:
            return (match.group(1), True)

        # Паттерн с exact=True (одинарные кавычки)
        pattern_exact_single = r"get_by_role\('button',\s*name='([^']+)',\s*exact=True\)"
        match = re.search(pattern_exact_single, selector_code)
        if match:
            return (match.group(1), True)

        # Паттерн без exact (двойные кавычки)
        pattern_double = r'get_by_role\("button",\s*name="([^"]+)"\)'
        match = re.search(pattern_double, selector_code)
        if match:
            return (match.group(1), False)

        # Паттерн без exact (одинарные кавычки)
        pattern_single = r"get_by_role\('button',\s*name='([^']+)'\)"
        match = re.search(pattern_single, selector_code)
        if match:
            return (match.group(1), False)

        return (None, False)

    def _generate_standard_click_code(self, code_lines: list, selector_code: str, selector_code_escaped: str):
        """
        === SMART BUTTON HANDLER ADDED ===
        Генерирует стандартный код клика для НЕ-кнопок (textbox, link, combobox и т.д.)
        """
        code_lines.append('# Клик по элементу')
        code_lines.append(f'print(f"DEBUG: Клик по: {selector_code_escaped}")')
        code_lines.append(f'try:')
        code_lines.append(f'    page.{selector_code}.wait_for(state="visible", timeout=20000)')
        code_lines.append(f'    page.{selector_code}.scroll_into_view_if_needed()')
        code_lines.append(f'    page.wait_for_timeout(500)')
        code_lines.append(f'    page.{selector_code}.click(timeout=10000)')
        code_lines.append(f'    print("[OK] Клик выполнен")')
        code_lines.append(f'except Exception as e:')
        code_lines.append(f'    print(f"[WARNING] Не удалось кликнуть: {{e}}")')
        code_lines.append(f'    print("[INFO] Пропускаем клик и продолжаем...")')
        code_lines.append('')  # Пустая строка для разделения

    def _generate_selector_code(self, selector: Dict) -> str:
        """Генерирует код селектора Playwright"""
        sel_type = selector['type']

        # Новый тип: полная цепочка методов
        if sel_type == 'chain':
            chain = selector['chain']
            modifier = selector.get('modifier')

            # НЕ нормализуем кавычки - оставляем как есть из оригинала
            # Playwright recorder уже создал корректный Python код
            # Замена кавычек ломает апострофы (You're, Let's и т.д.)

            # Построить полный селектор
            result = chain
            if modifier:
                if modifier == 'first':
                    result = f"{result}.first"
                elif modifier == 'last':
                    result = f"{result}.last"
                elif modifier.startswith('nth('):
                    result = f"{result}.{modifier}"

            return result

        # Старые типы для обратной совместимости
        if sel_type == 'role':
            role = selector['role']
            name = selector.get('name')
            if name:
                # Экранировать кавычки
                name_escaped = name.replace("'", "\\'")
                return f"get_by_role('{role}', name='{name_escaped}')"
            else:
                return f"get_by_role('{role}')"

        elif sel_type == 'testid':
            value = selector['value'].replace("'", "\\'")
            return f"get_by_test_id('{value}')"

        elif sel_type == 'text':
            value = selector['value'].replace("'", "\\'")
            return f"get_by_text('{value}')"

        elif sel_type == 'label':
            value = selector['value'].replace("'", "\\'")
            return f"get_by_label('{value}')"

        elif sel_type == 'placeholder':
            value = selector['value'].replace("'", "\\'")
            return f"get_by_placeholder('{value}')"

        elif sel_type == 'filter_text':
            value = selector['value'].replace("'", "\\'")
            return f"filter(has_text='{value}')"

        elif sel_type == 'locator':
            value = selector['value'].replace("'", "\\'")
            return f"locator('{value}')"

        elif sel_type == 'unknown':
            # Если селектор неизвестен, вернуть оригинальную строку
            original = selector.get('original', '')
            # Попробуем извлечь хоть что-то полезное из оригинальной строки
            if 'page.' in original:
                # Извлечь часть после page.
                match = re.search(r'page\.(.+?)(?:\.fill|\.click|\.type|\()', original)
                if match:
                    return match.group(1)
            return "locator('body')"  # Последний fallback

        return "locator('body')"

    def generate_csv_content(self, num_rows: int = 3) -> str:
        """Генерирует содержимое CSV файла"""
        if not self.variable_names:
            return ''

        # Заголовки
        csv_lines = [','.join(self.variable_names)]

        # Первая строка - оригинальные значения
        csv_lines.append(','.join(self.extracted_values))

        # Дополнительные строки с примерами
        for i in range(num_rows - 1):
            row_values = []
            for j, var_name in enumerate(self.variable_names):
                original_value = self.extracted_values[j] if j < len(self.extracted_values) else ''
                example_value = self._generate_example_value(var_name, original_value, i + 1)
                row_values.append(example_value)
            csv_lines.append(','.join(row_values))

        return '\n'.join(csv_lines)

    def _generate_example_value(self, var_name: str, original_value: str, index: int) -> str:
        """Генерирует примерное значение для CSV"""
        if var_name == 'email':
            return f'user{index}@example.com'
        elif var_name == 'firstname':
            names = ['John', 'Jane', 'Bob', 'Alice', 'Charlie']
            return names[index % len(names)]
        elif var_name == 'lastname':
            surnames = ['Smith', 'Doe', 'Johnson', 'Williams', 'Brown']
            return surnames[index % len(surnames)]
        elif var_name in ['password', 'date_of_birth', 'phone', 'phone_number', 'number', 'otp_code']:
            # Для номеров и кодов - НЕ изменять оригинальное значение
            # API сам даст реальные номера/OTP
            return original_value
        else:
            return f'{original_value}_{index}' if original_value else f'value_{index}'
