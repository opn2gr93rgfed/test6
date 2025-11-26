# ИНСТРУКЦИЯ ПО ИСПРАВЛЕНИЮ КОНФЛИКТА ПРОКСИ И 9PROXY

## Проблема
В сгенерированном скрипте одновременно включены:
- `USE_PROXY_LIST = True` (обычные прокси)
- `NINE_PROXY_ENABLED = True` (9Proxy)

Это создает конфликт - скрипт пытается использовать оба источника прокси одновременно.

## Решение

### 1. Логика приоритета (в генераторе)

При генерации конфигурации нужно проверять:
```python
# В методе _generate_config или аналогичном:

# Проверяем 9Proxy
nine_proxy_enabled = proxy_list_config.get('nine_proxy_enabled', False)
nine_proxy_ports = proxy_list_config.get('nine_proxy_ports', [6001, 6002])  # БЕЗ 6000!

if nine_proxy_enabled:
    # Если 9Proxy включен - отключаем обычные прокси
    config += f'''# 9Proxy API Dynamic Rotation (ПРИОРИТЕТ)
NINE_PROXY_ENABLED = True
NINE_PROXY_API_URL = "{proxy_list_config.get('nine_proxy_url', 'http://localhost:10101')}"
NINE_PROXY_PORTS = {json.dumps(nine_proxy_ports)}
NINE_PROXY_STRATEGY = "{proxy_list_config.get('nine_proxy_strategy', 'sequential')}"
NINE_PROXY_AUTO_ROTATE = {proxy_list_config.get('nine_proxy_auto_rotate', True)}

# Обычные прокси отключены (9Proxy активен)
USE_PROXY_LIST = False
USE_PROXY = False

'''
else:
    # Если 9Proxy выключен - используем обычные прокси
    config += f'''# 9Proxy отключен
NINE_PROXY_ENABLED = False

# Обычные прокси
USE_PROXY_LIST = {len(proxies_list) > 0}
'''
    # ... остальная логика обычных прокси
```

### 2. Исключение проблемного порта 6000

**ВАЖНО**: Порт 6000 имеет постоянные проблемы с таймаутами.

```python
# При парсинге конфигурации 9Proxy - исключаем порт 6000
nine_proxy_ports = proxy_list_config.get('nine_proxy_ports', [6001, 6002, 6003])

# Фильтруем порт 6000
nine_proxy_ports = [port for port in nine_proxy_ports if port != 6000]

# Если после фильтрации список пустой - ошибка
if nine_proxy_enabled and not nine_proxy_ports:
    print("[WARNING] Все порты 9Proxy исключены. Добавляю дефолтные порты.")
    nine_proxy_ports = [6001, 6002]
```

### 3. Исправление в GUI (если применимо)

В файле `src/gui/main_window.py` или аналогичном:

```python
# При включении 9Proxy - автоматически отключать обычные прокси
def on_nine_proxy_toggle(self):
    if self.nine_proxy_enabled.get():
        # Отключаем обычные прокси
        self.use_proxy_list.set(False)
        self.use_proxy.set(False)

        # Показываем предупреждение о порте 6000
        messagebox.showwarning(
            "9Proxy включен",
            "Обычные прокси отключены.\n\n"
            "ВАЖНО: Порт 6000 исключен из-за проблем с таймаутами.\n"
            "Используются порты: 6001, 6002, 6003..."
        )
```

### 4. Проверка конфигурации при генерации

Добавить валидацию перед генерацией скрипта:

```python
def validate_proxy_config(config):
    """Валидация конфигурации прокси"""
    nine_proxy = config.get('nine_proxy_enabled', False)
    proxy_list = len(config.get('proxy_list', {}).get('proxies', [])) > 0

    if nine_proxy and proxy_list:
        print("[WARNING] Обнаружен конфликт: 9Proxy и обычные прокси включены одновременно!")
        print("[INFO] Приоритет отдается 9Proxy. Обычные прокси будут отключены.")
        config['proxy_list']['proxies'] = []

    # Проверяем порт 6000
    if nine_proxy:
        ports = config.get('nine_proxy_ports', [])
        if 6000 in ports:
            print("[WARNING] Порт 6000 найден в конфигурации 9Proxy!")
            print("[INFO] Исключаю порт 6000 (известные проблемы с таймаутами)")
            config['nine_proxy_ports'] = [p for p in ports if p != 6000]

    return config
```

## Дополнительные рекомендации

1. **Логирование**: Добавить четкие логи при генерации:
   ```
   [CONFIG] 9Proxy: ENABLED
   [CONFIG] 9Proxy Ports: [6001, 6002]
   [CONFIG] Regular Proxies: DISABLED (9Proxy has priority)
   ```

2. **Документация**: Обновить README с примерами конфигурации

3. **Fallback**: Если 9Proxy API недоступен - переключаться на обычные прокси

## Пример итоговой конфигурации

```python
# ============================================================
# ПРОКСИ КОНФИГУРАЦИЯ
# ============================================================

# 9Proxy API Dynamic Rotation (ПРИОРИТЕТ)
NINE_PROXY_ENABLED = True
NINE_PROXY_API_URL = "http://localhost:10101"
NINE_PROXY_PORTS = [6001, 6002]  # Порт 6000 исключен!
NINE_PROXY_STRATEGY = "sequential"
NINE_PROXY_AUTO_ROTATE = True

# Обычные прокси отключены (9Proxy активен)
USE_PROXY_LIST = False
USE_PROXY = False

# Thread-safe счетчик для ротации
_nine_proxy_counter = 0
_nine_proxy_lock = threading.Lock()
```

---

**Статус**: Готово к применению
**Автор**: Claude
**Дата**: 2025-11-26
