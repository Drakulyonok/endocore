"""Third-party service integrations.

An **extension** is a small object that wires a service into the app: it
registers DI providers in ``setup(app)`` and can hook the lifespan via
``startup()`` / ``shutdown()``. List them in the app's ``extensions.py``:

    # extensions.py
    from endocore.extensions import RedisExtension, CacheExtension
    extensions = [
        RedisExtension(url="redis://localhost:6379/0"),
        CacheExtension(backend="redis"),   # uses the redis client above
    ]

The framework calls ``setup`` at boot and runs ``startup``/``shutdown`` on the
ASGI lifespan. Ship-your-own: subclass :class:`Extension`.
"""

from __future__ import annotations

from typing import Any


class Extension:
    """Base class for service integrations."""

    #: DI name the service is registered under (also used as an alias).
    name: str = "extension"

    def setup(self, app) -> None:
        """Register providers on ``app`` (called once at boot)."""

    async def startup(self) -> None:
        """Open connections / start workers (ASGI lifespan startup)."""

    async def shutdown(self) -> None:
        """Close connections cleanly (ASGI lifespan shutdown)."""


from endocore.extensions.cache_ext import CacheExtension
from endocore.extensions.celery import CeleryExtension, celery_app
from endocore.extensions.email import EmailClient, EmailExtension
from endocore.extensions.redis import RedisExtension, redis_client

__all__ = [
    "Extension",
    "RedisExtension",
    "redis_client",
    "CeleryExtension",
    "celery_app",
    "EmailExtension",
    "EmailClient",
    "CacheExtension",
]
