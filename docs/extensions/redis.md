# Redis

```bash
pip install "endocore[redis]"
```

## Register the client

```python
# extensions.py
from endocore.extensions import RedisExtension

extensions = [
    RedisExtension(url="redis://localhost:6379/0"),   # or host=, port=, db=, ...
]
```

This registers a Redis client as a DI provider under the name `redis` (and by
the `redis.Redis` type), and closes it on shutdown.

## Use it in a handler

```python
async def handler(request, redis):
    redis.set("hits", 0)
    redis.incr("hits")
    return Response.json({"hits": int(redis.get("hits"))})
```

## As a cache backend

Pair it with the cache extension to get a Redis-backed cache:

```python
# extensions.py
from endocore.extensions import RedisExtension, CacheExtension

extensions = [
    RedisExtension(url="redis://localhost:6379/0"),
    CacheExtension(backend="redis"),      # uses the client above
]
```

```python
async def handler(request, cache):
    cache.set("user:1", {"name": "Ada"}, ttl=60)
    return Response.json(cache.get("user:1"))
```

## Just the client factory

If you don't want the extension, build a client directly:

```python
from endocore.extensions import redis_client
r = redis_client(url="redis://localhost:6379/0")
```

## Pub/Sub across workers

The [WebSocket pub/sub](../guide/websockets.md) manager is per-process. To fan
out across workers, publish to a Redis channel on broadcast and have each worker
subscribe and re-broadcast to its local room.
