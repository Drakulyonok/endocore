"""Cache extension — configures the cache layer and exposes it via DI."""

from __future__ import annotations

from endocore.core.cache import configure_cache, get_cache
from endocore.extensions import Extension


class CacheExtension(Extension):
    """Configures a cache backend and registers it as the ``cache`` provider."""

    name = "cache"

    def __init__(self, backend: str = "memory", *, name: str = "cache", **params) -> None:
        self.backend = backend
        self.name = name
        self.params = params

    def setup(self, app) -> None:
        configure_cache(self.backend, **self.params)
        app.provide(self.name, get_cache, singleton=True)
