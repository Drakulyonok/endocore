"""Cache layer: a small interface with in-memory and Redis backends.

    from endocore.core.cache import configure_cache, get_cache, cached

    configure_cache("memory")                    # or "redis", client=<redis client>
    cache = get_cache()
    cache.set("k", {"v": 1}, ttl=60)
    cache.get("k")

    @cached(ttl=30)
    async def expensive(x): ...
"""

from __future__ import annotations

import functools
import inspect
import pickle
import threading
import time
from typing import Any, Callable

from endocore.core.exceptions import ConfigurationError

_MISS = object()


class InMemoryCache:
    """Process-local cache with per-key TTL. Thread-safe."""

    def __init__(self) -> None:
        self._data: dict[str, tuple[Any, float | None]] = {}
        self._lock = threading.RLock()

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return default
            value, expiry = item
            if expiry is not None and expiry < time.time():
                self._data.pop(key, None)
                return default
            return value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        with self._lock:
            self._data[key] = (value, time.time() + ttl if ttl else None)

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def has(self, key: str) -> bool:
        return self.get(key, _MISS) is not _MISS

    def incr(self, key: str, amount: int = 1) -> int:
        with self._lock:
            value = int(self.get(key, 0)) + amount
            self.set(key, value)
            return value


class RedisCache:
    """Cache backed by a Redis client (values pickled). Client injected lazily."""

    def __init__(self, client, *, prefix: str = "endocore:") -> None:
        self.client = client
        self.prefix = prefix

    def _k(self, key: str) -> str:
        return self.prefix + key

    def get(self, key: str, default: Any = None) -> Any:
        raw = self.client.get(self._k(key))
        return default if raw is None else pickle.loads(raw)

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        data = pickle.dumps(value)
        if ttl:
            self.client.setex(self._k(key), ttl, data)
        else:
            self.client.set(self._k(key), data)

    def delete(self, key: str) -> None:
        self.client.delete(self._k(key))

    def clear(self) -> None:
        keys = list(self.client.keys(self.prefix + "*"))
        if keys:
            self.client.delete(*keys)

    def has(self, key: str) -> bool:
        return bool(self.client.exists(self._k(key)))

    def incr(self, key: str, amount: int = 1) -> int:
        value = int(self.get(key, 0)) + amount
        self.set(key, value)
        return value


_caches: dict[str, Any] = {}


def configure_cache(backend: str = "memory", *, alias: str = "default", **params) -> Any:
    """Register a cache backend. ``backend`` is ``"memory"`` or ``"redis"``."""
    if backend == "memory":
        cache = InMemoryCache()
    elif backend == "redis":
        client = params.get("client")
        if client is None:
            from endocore.extensions.redis import redis_client  # lazy

            client = redis_client(**{k: v for k, v in params.items() if k != "prefix"})
        cache = RedisCache(client, prefix=params.get("prefix", "endocore:"))
    else:
        raise ConfigurationError(f"unknown cache backend {backend!r} (use 'memory' or 'redis')")
    _caches[alias] = cache
    return cache


def get_cache(alias: str = "default") -> Any:
    cache = _caches.get(alias)
    if cache is None:
        cache = configure_cache("memory", alias=alias)  # sensible default
    return cache


def _make_key(func: Callable, args: tuple, kwargs: dict) -> str:
    name = getattr(func, "__qualname__", func.__name__)
    return f"{name}({args!r},{sorted(kwargs.items())!r})"


def cached(ttl: int | None = None, *, key: Callable | None = None, alias: str = "default"):
    """Cache a function's result. Works on sync and async functions."""

    def decorator(func: Callable):
        make = key or (lambda *a, **k: _make_key(func, a, k))

        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def awrapper(*args, **kwargs):
                cache = get_cache(alias)
                k = make(*args, **kwargs)
                hit = cache.get(k, _MISS)
                if hit is not _MISS:
                    return hit
                result = await func(*args, **kwargs)
                cache.set(k, result, ttl)
                return result

            return awrapper

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache(alias)
            k = make(*args, **kwargs)
            hit = cache.get(k, _MISS)
            if hit is not _MISS:
                return hit
            result = func(*args, **kwargs)
            cache.set(k, result, ttl)
            return result

        return wrapper

    return decorator
