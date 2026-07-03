# Extensions

An **extension** wires a third-party service into your app: it registers DI
providers in `setup(app)` and can hook the ASGI lifespan via `startup()` /
`shutdown()`.

List them in `extensions.py` at your app root:

```python
# extensions.py
from endocore.extensions import RedisExtension, CacheExtension, EmailExtension

extensions = [
    RedisExtension(url="redis://localhost:6379/0"),
    CacheExtension(backend="redis"),
    EmailExtension(host="smtp.example.com", port=587, use_tls=True),
]
```

At boot, EndoCore calls each `setup(app)` and adds each extension's
`startup`/`shutdown` to the lifespan — so connections open and close cleanly
without touching `hooks.py`.

## Shipped extensions

- [**Redis**](redis.md) — a Redis client provider (`endocore[redis]`).
- [**Celery**](celery.md) — a Celery app provider (`endocore[celery]`).
- [**Email**](email.md) — an SMTP email client (stdlib, no extra dep).
- **Cache** — `CacheExtension(backend=...)` configures the [cache](../guide/cache.md)
  and injects it as `cache`.

## Using an injected service

Once an extension registers a provider, inject it by name (or type) in any
handler:

```python
async def handler(request, redis, cache):
    cache.set("k", "v", ttl=60)
    redis.publish("events", "hello")
    ...
```

## Write your own

Subclass `Extension` — that's the whole contract:

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

That's how "support for many services" scales — the framework ships a few
common ones and gives everyone the same clean pattern for the rest.
