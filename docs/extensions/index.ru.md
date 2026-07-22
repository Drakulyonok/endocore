# Расширения

**Расширение** подключает сторонний сервис к приложению: регистрирует
DI-провайдеры в `setup(app)` и может встраиваться в ASGI-lifespan через
`startup()` / `shutdown()`.

Перечислите их в `extensions.py` в корне приложения:

```python
# extensions.py
from endocore.extensions import RedisExtension, CacheExtension, EmailExtension

extensions = [
    RedisExtension(url="redis://localhost:6379/0"),
    CacheExtension(backend="redis"),
    EmailExtension(host="smtp.example.com", port=587, use_tls=True),
]
```

При старте EndoCore вызывает `setup(app)` каждого расширения и добавляет его
`startup`/`shutdown` в lifespan — соединения открываются и закрываются чисто,
без правок `hooks.py`.

## Расширения из коробки

- [**Redis**](redis.md) — провайдер Redis-клиента (`endocore[redis]`).
- [**Celery**](celery.md) — провайдер Celery-приложения (`endocore[celery]`).
- [**Email**](email.md) — SMTP-клиент (stdlib, без дополнительных зависимостей).
- **Cache** — `CacheExtension(backend=...)` настраивает [кэш](../guide/cache.md)
  и инжектирует его как `cache`.

## Использование инжектированного сервиса

Как только расширение зарегистрировало провайдер, инжектируйте его по имени
(или типу) в любом обработчике:

```python
async def handler(request, redis, cache):
    cache.set("k", "v", ttl=60)
    redis.publish("events", "hello")
    ...
```

## Напишите своё

Отнаследуйтесь от `Extension` — вот и весь контракт:

```python
from endocore.extensions import Extension

class KafkaExtension(Extension):
    name = "kafka"

    def __init__(self, *, brokers):
        self.brokers = brokers
        self._producer = None

    def _client(self):
        if self._producer is None:
            from kafka import KafkaProducer
            self._producer = KafkaProducer(bootstrap_servers=self.brokers)
        return self._producer

    def setup(self, app):
        app.provide("kafka", self._client, singleton=True)

    async def shutdown(self):
        if self._producer:
            self._producer.close()
```

```python
# extensions.py
from Extensions.kafka import KafkaExtension
extensions = [KafkaExtension(brokers="localhost:9092")]
```

Так и масштабируется «поддержка множества сервисов»: фреймворк поставляет
несколько распространённых, а для остальных даёт всем один и тот же чистый
паттерн.
