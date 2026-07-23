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
import hashlib
import hmac
import inspect
import pickle  # nosec B403
import threading
import time
import warnings
from typing import Any, Callable

from endocore.core.exceptions import ConfigurationError

_MISS = object()
_SIG_BYTES = 32  # HMAC-SHA256 digest size


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
    """Cache backed by a Redis client (values pickled). Client injected lazily.

    ``pickle.loads`` on whatever Redis returns is only as safe as Redis itself
    (CWE-502). Pass ``secret=`` to HMAC-sign each blob and verify it on read;
    a bad or missing signature is treated as a cache miss. Without ``secret=``,
    blobs stay unsigned and a warning is raised once per instance.
    """

    def __init__(self, client, *, prefix: str = "endocore:", secret: str | bytes | None = None) -> None:
        self.client = client
        self.prefix = prefix
        self._key: bytes | None = None
        if secret is not None:
            secret_bytes = secret.encode("utf-8") if isinstance(secret, str) else secret
            self._key = hashlib.sha256(b"endocore.cache:" + secret_bytes).digest()
        else:
            warnings.warn(
                "RedisCache configured without secret=...: cached values are "
                "unauthenticated pickle blobs. If this Redis instance is ever "
                "exposed, shared, or reachable by a compromised neighbor, "
                "pickle.loads() on injected bytes is remote code execution. "
                "Pass configure_cache('redis', ..., secret=...) to sign/verify "
                "blobs instead.",
                stacklevel=2,
            )

    def _k(self, key: str) -> str:
        return self.prefix + key

    def _pack(self, redis_key: str, value: Any) -> bytes:
        data = pickle.dumps(value)
        if self._key is None:
            return data
        # bind the key into the signature so a blob can't be copied to another key
        mac = hmac.new(self._key, redis_key.encode("utf-8") + b"\x00" + data, hashlib.sha256)
        return mac.digest() + data

    def _unpack(self, redis_key: str, raw: bytes) -> Any:
        if self._key is None:
            # unsigned path; a warning is raised in __init__ for this
            return pickle.loads(raw)  # nosec B301
        signature, data = raw[:_SIG_BYTES], raw[_SIG_BYTES:]
        expected = hmac.new(
            self._key, redis_key.encode("utf-8") + b"\x00" + data, hashlib.sha256
        ).digest()
        if not hmac.compare_digest(signature, expected):
            return _MISS  # tampered, foreign, or copied from another key — fail closed
        # signature already verified above
        return pickle.loads(data)  # nosec B301

    def get(self, key: str, default: Any = None) -> Any:
        redis_key = self._k(key)
        raw = self.client.get(redis_key)
        if raw is None:
            return default
        value = self._unpack(redis_key, raw)
        return default if value is _MISS else value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        redis_key = self._k(key)
        data = self._pack(redis_key, value)
        if ttl:
            self.client.setex(redis_key, ttl, data)
        else:
            self.client.set(redis_key, data)

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

            client = redis_client(**{
                k: v for k, v in params.items() if k not in ("prefix", "secret")
            })
        cache = RedisCache(client, prefix=params.get("prefix", "endocore:"), secret=params.get("secret"))
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
