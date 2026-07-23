# Установка

## Требования

- **Python 3.11+**
- Единственная обязательная зависимость времени выполнения — **`uvicorn`** (ASGI-сервер).

## Установка с PyPI

```bash
pip install endocore
```

Это даёт полный фреймворк, CLI (`endo`) и ORM для **SQLite** (поддержка SQLite
построена на стандартной библиотеке — ставить ничего не нужно).

??? tip "Новичок в Python? Используйте виртуальное окружение"
    Виртуальное окружение хранит пакеты каждого проекта отдельно, чтобы ничего
    не сломать в системе. Сначала создайте и активируйте его:

    ```bash
    python -m venv .venv
    # Windows:
    .venv\Scripts\activate
    # Linux / macOS:
    source .venv/bin/activate

    pip install endocore
    ```

## Опциональные extras

EndoCore держит ядро крошечным; подключайте только нужное:

| Extra | Ставит | Включает |
|-------|--------|----------|
| `postgres` | `psycopg` | Бэкенд PostgreSQL для ORM |
| `files` | `cryptography` | Зашифрованный `FileField` (AES-256-GCM at rest) |
| `redis` | `redis` | Redis-бэкенд кэша + `RedisExtension` |
| `celery` | `celery` | Интеграция очереди задач `CeleryExtension` |
| `pydantic` | `pydantic` | Типизированные тела запросов + богаче OpenAPI |
| `watch` | `watchfiles` | Авто-перезагрузка в dev-режиме |

```bash
pip install "endocore[postgres,files,pydantic]"
# всё полезное для разработки:
pip install "endocore[postgres,files,redis,celery,pydantic,watch]"
```

## Проверка установки

```bash
endo --version         # EndoCore 0.9.0b1
endo doctor            # окружение, зависимости, проверки проекта
```

`endo doctor` печатает версию Python, наличие опциональных зависимостей и
похоже ли текущая директория на проект EndoCore.

## Из исходников (разработка)

```bash
git clone https://github.com/Drakulyonok/endocore
cd endocore
pip install -e ".[postgres,files,redis,celery,pydantic,watch]"
pip install pytest
pytest -q             # 1600+ тестов
```

## Про Windows

**PowerShell:** `endo` — зарезервированное слово, `endo dev` там не распарсится.
Используйте идентичный алиас `endo`:

```powershell
endo --version
endo dev
```

**Сломанный `python`:** на некоторых конфигурациях «голый» `python` не
работает — используйте лаунчер:

```bash
py -3 -m pip install endocore
py -3 -m endocore --version     # то же, что `endo --version`
```

Дальше — [Быстрый старт](quickstart.md).
