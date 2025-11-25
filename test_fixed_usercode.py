#!/usr/bin/env python3
"""
Тест с ИСПРАВЛЕННЫМ user_code (без проблемной строки heading)
"""

from src.providers.smart_dynamic.generator import Generator

USER_CODE = """
import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://www.compare.com/")
    page.get_by_role("textbox", name="Enter your ZIP code").click()
    page.get_by_role("textbox", name="Enter your ZIP code").click()
    page.get_by_role("textbox", name="Enter your ZIP code").fill(data_row["Field1"])
    page.get_by_role("button", name="See My Quotes").click()
    #pause15
    page.get_by_role("heading", name="Are you currently insured?")
    page.get_by_role("button", name="No").click()
    page.get_by_role("heading", name="Are you looking to buy")
    page.get_by_role("button", name="No").click()
    page.get_by_role("heading", name="Do you own or rent your home?")
    page.get_by_role("button", name="Own").click()
    page.get_by_role("heading", name="Why are you shopping for")
    page.get_by_role("button", name="My policy expired").click()
    page.get_by_role("heading", name="How soon do you need your")
    page.get_by_role("button", name="More than a month from now").click()
    page.get_by_role("heading", name="When do you plan to purchase your new insurance policy?")
    page.get_by_role("button", name="More than a month from now").click()
    page.get_by_role("heading", name="What's your car year?")
    page.get_by_role("button", name="2017").click()
    page.get_by_role("heading", name="What's your car make?")
    page.get_by_role("button", name="Ford icon Ford").click()
    page.get_by_role("heading", name="What's your car model?")
    page.get_by_role("button", name="Edge").click()
    page.get_by_role("heading", name="What's your car trim?")
    page.get_by_role("button", name="I don't know").click()
    page.get_by_role("heading", name="What's your car body style?")
    page.get_by_role("button", name="I don't know").click()
    page.get_by_role("heading", name="What's the main use of your")
    page.get_by_role("button", name="Commuting or personal use").click()
    page.get_by_role("heading", name="How many miles do you drive")
    page.get_by_role("button", name="Miles National average").click()
    page.get_by_role("heading", name="Do you own or lease this car?")
    page.get_by_role("button", name="Owned").click()
    page.get_by_role("heading", name="Would you like to include")
    page.get_by_role("button", name="No").click()
    page.get_by_role("heading", name="Would you like to add another driver?")
    page.get_by_role("button", name="No").click()
    page.get_by_role("heading", name="What's your date of birth?")
    page.get_by_role("textbox", name="MM").click()
    page.get_by_role("textbox", name="MM").fill(data_row["Field2"])
    page.get_by_role("textbox", name="DD").click()
    page.get_by_role("textbox", name="DD").fill(data_row["Field3"])
    page.get_by_role("textbox", name="YYYY").click()
    page.get_by_role("textbox", name="YYYY").fill(data_row["Field4"])
    page.get_by_role("button", name="Next").click()
    page.get_by_role("heading", name="What's your gender?")
    page.get_by_role("button", name="Female").click()
    page.get_by_role("heading", name="Do you have an active U.S.")
    page.get_by_role("button", name="Yes").click()
    page.get_by_role("heading", name="How old were you when you first got your US driver's license?")
    page.get_by_role("button", name="16").click()
    page.get_by_role("heading", name="What's your credit score?")
    page.get_by_role("button", name="Excellent (720+)").click()
    page.get_by_role("heading", name="What's your highest level of")
    page.get_by_role("button", name="High School/GED").click()
    page.get_by_role("heading", name="Have you or an immediate family member honorably or actively served in the U.S. military?")
    page.get_by_role("button", name="No").click()
    page.get_by_role("heading", name="Do any of these apply to you?")
    page.get_by_role("button", name="Continue").click()
    page.get_by_role("heading", name="Would you also like to receive a home insurance quote? to")
    page.get_by_role("button", name="No").click()
    page.get_by_role("heading", name="Why don't you have insurance?")
    page.get_by_role("button", name="My policy expired").click()
    page.get_by_role("heading", name="How long has it been since you had car insurance?")
    page.get_by_role("button", name="More than a month").click()
    page.get_by_role("heading", name="How many at-fault accidents have you had in the past 3 years?")
    page.get_by_role("button", name="0").click()
    page.get_by_role("heading", name="How many cars you are looking to insure?")
    page.get_by_role("button", name="1 car").click()
    page.get_by_role("heading", name="How many speeding tickets have you had in the past 3 years?")
    page.get_by_role("button", name="0").click()
    page.get_by_role("heading", name="How many insurance claims have you had in the past 3 years?")
    page.get_by_role("button", name="0").click()
    page.get_by_role("heading", name="How many DUI/DWI convictions have you had in the past 3 years?")
    page.get_by_role("button", name="0").click()
    page.get_by_role("heading", name="Do you require an SR-22 Certificate?")
    page.get_by_role("button", name="No Common choice").click()
    page.get_by_role("heading", name="You're so close! Let's wrap this up")
    page.get_by_role("textbox", name="First name").click()
    page.get_by_role("textbox", name="First name").fill(data_row["Field5"])
    page.get_by_role("textbox", name="Last name").click()
    page.get_by_role("textbox", name="Last name").fill(data_row["Field6"])
    page.get_by_role("button", name="Next").click()
    page.get_by_role("heading", name="Would you like to add another")
    page.get_by_role("button", name="No").click()
    page.get_by_role("heading", name="Where do you park your car overnight?")
    page.get_by_role("textbox", name="Enter location").click()
    page.get_by_role("textbox", name="Enter location").fill(data_row["Field7"])
    #pause10
    page.get_by_role("textbox", name="Enter location").press("ArrowDown")
    #pause5
    page.get_by_role("textbox", name="Enter location").press("Enter")
    #pause5
    page.get_by_role("button", name="Next").click()
    page.get_by_role("heading", name="Where would you like to receive a copy of your quotes?")
    page.get_by_role("textbox", name="Email address").click()
    page.get_by_role("textbox", name="Email address").fill(data_row["Field8"])
    page.get_by_role("textbox", name="Email address").press("ArrowDown")
    page.get_by_role("button", name="Next").click()
    page.get_by_role("heading", name="One final step")
    page.get_by_role("textbox", name="Phone number").click()
    page.get_by_role("textbox", name="Phone number").fill(data_row["Field9"])
    with page.expect_popup() as page1_info:
        page.get_by_role("button", name="View my quotes").click()
    page1 = page1_info.value

    #optional
    page1.get_by_role("button", name="Not Now").click()

    page1.locator('[data-testid="quote_skeleton_card"]').wait_for(state='detached', timeout=120000)
    time.sleep(2)

    #scroll_search
    page1.locator('[data-testid="show-more"] span').click()


    #scroll_search
    page1.locator('xpath=//img[@alt="Root" and contains(@src, "high-definition/root.svg")]').click()
    with page1.expect_popup() as page2_info:
        page1.get_by_role("button", name="Buy online").click()
    page2 = page2_info.value

    #pause15
    page2.get_by_role("button", name="Looks good").click()
    #pause5
    #optional
    page2.get_by_role("button", name="Continue with this address").click()

    #pause15
    page2.get_by_role("button", name="Let", exact=False).click()
    #pause15

    page2.get_by_role("button", name="Continue").click()
    #optional
    #pause15

    page2.get_by_role("button", name="Continue and exclude").click()

    #pause10
    all_switches = page2.locator('form#prefill_vehicles_form input[type="checkbox"][role="switch"]')
    all_switches.nth(0).click()  # Было Covered → станет Not Covered
    #pause3
    all_switches.nth(1).click()  # Было Not Covered → станет Covered
    #pause5
    page2.get_by_role("button", name="Continue").click()

    #pause10
    page2.get_by_role("button", name="Continue to quote").dblclick()


    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
"""

print("="*80)
print("ТЕСТ С ИСПРАВЛЕННЫМ USER_CODE")
print("="*80)

# Конфигурация для генератора
CONFIG = {
    'api_token': 'test_token',
    'proxy': {'enabled': False},
    'proxy_list': {'proxies': [], 'rotation_mode': 'random'},
    'profile': {'fingerprint': {'os': 'win'}, 'tags': []},
    'threads_count': 1,
    'network_capture_patterns': [],
    'simulate_typing': True,
    'typing_delay': 100
}

print("\n[1] Инициализация генератора...")
generator = Generator()

print("\n[2] Запуск генерации с исправленным user_code...")
try:
    script = generator.generate_script(USER_CODE, CONFIG)
    print("\n[3] ✅ Генерация завершена успешно!")

    # Сохраняем сгенерированный скрипт
    output_file = "/home/user/test6/fixed_generated_script.py"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(script)

    print(f"\n[4] ✅ Скрипт сохранен в: {output_file}")
    print(f"\n[5] Размер скрипта: {len(script)} символов")

    # Проверяем наличие условного popup
    if "#auto_conditional_popup" in script or "CONDITIONAL_POPUP" in script:
        print("\n[6] ✅ Обнаружена обработка условного popup!")
    else:
        print("\n[6] ⚠️  Условный popup НЕ обнаружен")

    # Проверяем что проблемного вопроса больше нет
    if '"Want to get more quotes for your"' in script:
        print("\n[7] ❌ ПРОБЛЕМА: Вопрос 'Want to get more quotes for your' все еще в пуле!")
    else:
        print("\n[7] ✅ Вопрос 'Want to get more quotes for your' УДАЛЕН из пула")

    # Подсчитываем вопросы
    import re
    questions = re.findall(r'"([^"]+)":\s*{[^}]*"actions":', script)
    print(f"\n[8] Найдено вопросов в QUESTIONS_POOL: {len(questions)}")

    print("\n[9] Проверка критичных вопросов:")
    critical_questions = [
        "One final step",
        "How many insurance claims have you had in the past 3 years?",
        "How many DUI/DWI convictions have you had in the past 3 years?",
    ]
    for q in critical_questions:
        if f'"{q}"' in script:
            print(f"  ✅ '{q}' найден")
        else:
            print(f"  ❌ '{q}' НЕ НАЙДЕН")

except Exception as e:
    print(f"\n[3] ❌ ОШИБКА при генерации: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
print("ИТОГИ:")
print("  - Исправленный user_code (без проблемной строки heading)")
print("  - Conditional popup должен обрабатываться правильно")
print("  - Все вопросы должны отвечаться ДО попытки открыть popup")
print("="*80)
