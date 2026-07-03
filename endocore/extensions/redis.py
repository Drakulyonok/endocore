"""Redis integration (optional ``redis`` dependency)."""

from __future__ import annotations

from endocore.extensions import Extension


def redis_client(url: str | None = None, **kwargs):
    """Create a Redis client. Requires ``pip install endocore[redis]``."""
    try:
        import redis
    except ImportError as exc:  # pragma: no cover - depends on optional dep
        raise ImportError("Redis support needs the 'redis' package: pip install endocore[redis]") from exc
    return redis.Redis.from_url(url, **kwargs) if url else redis.Redis(**kwargs)


class RedisExtension(Extension):
    """Registers a Redis client as a DI provider (by name and by type)."""

    name = "redis"

    def __init__(self, url: str | None = None, *, name: str = "redis", client=None, **kwargs) -> None:
        self.url = url
        self.name = name
        self.kwargs = kwargs
        self._client = client

    def client(self):
        if self._client is None:
            self._client = redis_client(self.url, **self.kwargs)
        return self._client

    def setup(self, app) -> None:
        app.provide(self.name, self.client, singleton=True)
        try:
            import redis

            app.provide(redis.Redis, self.client, singleton=True)
        except ImportError:
            pass

    async def shutdown(self) -> None:
        if self._client is not None and hasattr(self._client, "close"):
            self._client.close()
