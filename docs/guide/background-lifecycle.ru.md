# Фоновые задачи и жизненный цикл

На этой странице две вещи: код, который выполняется при старте и остановке
приложения (открыть пул БД, закрыть его), и работа, отложенная до момента после
отправки ответа (отправить письмо, не заставляя клиента ждать).

## Хуки startup / shutdown

Положите хуки жизненного цикла в `hooks.py` в корне приложения. Они выполняются
на ASGI-событиях `lifespan` — это место для открытия/закрытия пулов, запуска
планировщиков и т.д.

```python
# hooks.py
from Services.db import pool

async def _connect():
    await pool.open()

async def _disconnect():
    await pool.close()

on_startup = [_connect]
on_shutdown = [_disconnect]
```

Хуки могут быть sync или async. Упавший startup-хук прерывает запуск (об этом
сообщается ASGI-серверу); shutdown-хуки выполняются всегда.

## Фоновые задачи (после ответа)

Верните работу, которая выполнится **после** отправки ответа — отлично подходит
для писем, вебхуков, метрик:

```python
from endocore import Response

async def send_receipt(order_id):
    await email.send(...)

async def handler(request):
    order = create_order(...)
    return Response.json({"id": order.id}, background=lambda: send_receipt(order.id))
```

Фоновый callable выполняется после того, как байты ответа отправлены, так что
клиент не ждёт.

!!! note "Тяжёлая или надёжная работа"
    Фоновые задачи — best-effort и внутри процесса. Для работы, которая должна
    переживать рестарты или масштабироваться, используйте очередь задач — см.
    [расширение Celery](../extensions/celery.md).

## Интеграции сервисов и lifespan

Расширения, перечисленные в `extensions.py`, подключаются при старте, а их
`startup`/`shutdown` автоматически добавляются в lifespan — так `RedisExtension`
открывает клиент на старте и закрывает при остановке без правок `hooks.py`.
См. [Расширения](../extensions/index.md).
