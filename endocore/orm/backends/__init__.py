"""Database backends. One base (security-critical) + per-dialect subclasses."""

from __future__ import annotations

from endocore.orm.backends.base import BaseBackend
from endocore.orm.backends.postgres import PostgresBackend
from endocore.orm.backends.sqlite import SQLiteBackend
from endocore.orm.exceptions import ConfigurationError

_BACKENDS = {
    "sqlite": SQLiteBackend,
    "postgres": PostgresBackend,
    "postgresql": PostgresBackend,
}


def get_backend(name: str) -> BaseBackend:
    try:
        return _BACKENDS[name]()
    except KeyError:
        raise ConfigurationError(
            f"unknown backend {name!r}; available: {', '.join(sorted(_BACKENDS))}"
        ) from None


__all__ = ["BaseBackend", "SQLiteBackend", "PostgresBackend", "get_backend"]
