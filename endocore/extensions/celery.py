"""Celery integration (optional ``celery`` dependency)."""

from __future__ import annotations

from endocore.extensions import Extension


def celery_app(name: str = "endocore", *, broker: str | None = None,
               backend: str | None = None, **kwargs):
    """Create a Celery app. Requires ``pip install endocore[celery]``."""
    try:
        from celery import Celery
    except ImportError as exc:  # pragma: no cover - depends on optional dep
        raise ImportError("Celery support needs the 'celery' package: pip install endocore[celery]") from exc
    return Celery(name, broker=broker, backend=backend, **kwargs)


class CeleryExtension(Extension):
    """Registers a Celery app as a DI provider under ``name`` (default 'celery')."""

    name = "celery"

    def __init__(self, app_name: str = "endocore", *, broker: str | None = None,
                 backend: str | None = None, name: str = "celery", app=None, **kwargs) -> None:
        self.app_name = app_name
        self.broker = broker
        self.backend = backend
        self.name = name
        self.kwargs = kwargs
        self._app = app

    def app(self):
        if self._app is None:
            self._app = celery_app(self.app_name, broker=self.broker, backend=self.backend, **self.kwargs)
        return self._app

    def setup(self, app) -> None:
        app.provide(self.name, self.app, singleton=True)
