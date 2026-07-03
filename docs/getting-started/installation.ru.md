# Установка

## Требования

- **Python 3.11+**
- Единственная обязательная зависимость времени выполнения — **`uvicorn`** (ASGI-сервер).

## Установка с PyPI

```bash
pip install endocore
```

Это даёт полный фреймворк, CLI (`end`) и ORM для **SQLite** (поддержка SQLite
построена на стандартной библиотеке — ставить ничего не нужно).

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
end --version         # EndoCore 0.6.0b1
end doctor            # окружение, зависимости, проверки проекта
```

`end doctor` печатает версию Python, наличие опциональных зависимостей и
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

На некоторых Windows-конфигурациях «голый» `python` сломан — используйте лаунчер:

```bash
py -3 -m pip install endocore
py -3 -m endocore --version     # то же, что `end --version`
```

Дальше — [Быстрый старт](quickstart.md).
