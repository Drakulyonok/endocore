# Cache

A small cache interface with **in-memory** and **Redis** backends, plus a
`@cached` decorator.

## Configure & use

```python
from endocore import configure_cache, get_cache

configure_cache("memory")                       # process-local, TTL-aware
# or:  configure_cache("redis", client=redis_client)  # pip install "endocore[redis]"

cache = get_cache()
cache.set("user:1", {"name": "Ada"}, ttl=60)    # ttl in seconds (optional)
cache.get("user:1", default=None)
cache.has("user:1")
cache.delete("user:1")
cache.incr("hits", amount=1)                     # atomic-ish counter
cache.clear()
```

If you never call `configure_cache`, `get_cache()` returns a default in-memory
cache.

## `@cached` decorator

Memoize a function's result (sync or async) with an optional TTL:

```python
from endocore import cached

@cached(ttl=30)
async def expensive(user_id: int):
    return await slow_lookup(user_id)

@cached(ttl=300, key=lambda a, b: f"sum:{a}:{b}")
def add(a, b):
    return a + b
```

## Inject the cache

Via [DI](dependency-injection.md), either with the `CacheExtension` or a
provider:

```python
# extensions.py
from endocore.extensions import CacheExtension
extensions = [CacheExtension(backend="memory")]
```

```python
async def handler(request, cache):        # injected by name
    hit = cache.get("k")
    ...
```

## Redis backend

```python
# extensions.py
from endocore.extensions import RedisExtension, CacheExtension
extensions = [
    RedisExtension(url="redis://localhost:6379/0"),
    CacheExtension(backend="redis"),      # uses the Redis client above
]
```

Values are pickled; keys are namespaced with a prefix (`endocore:` by default).

!!! tip "Rate limiting"
    The built-in `rate_limit_middleware` uses its own in-memory counter. For a
    distributed limiter, back it with Redis.
