"""Service integrations for the example app.

The framework calls each extension's ``setup(app)`` at boot and runs
``startup``/``shutdown`` on the ASGI lifespan. Uncomment Redis/Celery once the
services (and optional deps) are available.
"""

from endocore.extensions import CacheExtension  # , RedisExtension, CeleryExtension

extensions = [
    CacheExtension(backend="memory"),          # -> Depends by name "cache"
    # RedisExtension(url="redis://localhost:6379/0"),
    # CeleryExtension(broker="redis://localhost:6379/1"),
]
