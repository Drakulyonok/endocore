# Redis

```bash
pip install "endocore[redis]"
```

## Регистрация клиента

```python
# extensions.py
from endocore.extensions import RedisExtension

extensions = [
    RedisExtension(url="redis://localhost:6379/0"),   # или host=, port=, db=, ...
]
```

Это регистрирует Redis-клиент как DI-провайдер под именем `redis` (и по типу
`redis.Redis`) и закрывает его при остановке.

## Использование в обработчике

```python
async def handler(request, redis):
    redis.set("hits", 0)
    redis.incr("hits")
    return Response.json({"hits": int(redis.get("hits"))})
```

## Как бэкенд кэша

В паре с расширением кэша получаете кэш на Redis:

```python
# extensions.py
from endocore.extensions import RedisExtension, CacheExtension

extensions = [
    RedisExtension(url="redis://localhost:6379/0"),
    CacheExtension(backend="redis"),      # использует клиент выше
]
```

```python
async def handler(request, cache):
    cache.set("user:1", {"name": "Ada"}, ttl=60)
    return Response.json(cache.get("user:1"))
```

## Только фабрика клиента

Если расширение не нужно, соберите клиент напрямую:

```python
from endocore.extensions import redis_client
r = redis_client(url="redis://localhost:6379/0")
```

## Pub/Sub между воркерами

Менеджер [WebSocket pub/sub](../guide/websockets.md) работает в пределах одного
процесса. Чтобы рассылать между воркерами, публикуйте в Redis-канал при
broadcast, а каждый воркер пусть подписывается и ретранслирует в свою локальную
комнату.
