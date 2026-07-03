"""Connection registry and transactions.

A single lazily-opened connection per alias. Values passed to ``execute`` are
always bound by the driver — never formatted into the SQL string. Credentials
live only in the config dict and are never logged.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from endocore.orm.backends import BaseBackend, get_backend
from endocore.orm.exceptions import ConfigurationError

#: Keys never echoed back in reprs / errors.
_SECRET_KEYS = frozenset({"password", "passwd", "secret", "dsn"})


class Connection:
    """Owns one DB-API connection and its transaction state for an alias."""

    def __init__(self, backend: BaseBackend, params: dict[str, Any], alias: str) -> None:
        self.backend = backend
        self.params = params
        self.alias = alias
        self._conn = None
        self._depth = 0  # atomic() nesting depth

    def _raw(self):
        if self._conn is None:
            self._conn = self.backend.connect(**self.params)
        return self._conn

    def execute(self, sql: str, params: Any = (), *, write: bool = False):
        """Run one statement with bound params. Commits writes when not in atomic."""
        cursor = self._raw().cursor()
        cursor.execute(sql, tuple(params))
        if write and self._depth == 0:
            self._raw().commit()
        return cursor

    def executescript(self, sql: str) -> None:
        """Run DDL (no bound params). Commits immediately when not in atomic."""
        self._raw().cursor().execute(sql)
        if self._depth == 0:
            self._raw().commit()

    @contextmanager
    def atomic(self) -> Iterator[None]:
        """Transaction block. Nested blocks join the outermost (no savepoints)."""
        conn = self._raw()
        self._depth += 1
        try:
            yield
        except BaseException:
            if self._depth == 1:
                conn.rollback()
            raise
        else:
            if self._depth == 1:
                conn.commit()
        finally:
            self._depth -= 1

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __repr__(self) -> str:
        safe = {k: ("***" if k in _SECRET_KEYS else v) for k, v in self.params.items()}
        return f"<Connection {self.alias} {self.backend.name} {safe}>"


_connections: dict[str, Connection] = {}


def configure(alias: str = "default", *, backend: str, **params: Any) -> Connection:
    """Register (or replace) a connection for ``alias``. Opens lazily on first use."""
    conn = Connection(get_backend(backend), params, alias)
    _connections[alias] = conn
    return conn


def connect(*, backend: str, **params: Any) -> Connection:
    """Configure the ``default`` connection and open it eagerly to validate."""
    conn = configure("default", backend=backend, **params)
    conn._raw()
    return conn


def get_connection(alias: str = "default") -> Connection:
    try:
        return _connections[alias]
    except KeyError:
        raise ConfigurationError(
            f"no connection configured for alias {alias!r}; call endocore.orm.configure(...) first"
        ) from None


def atomic(alias: str = "default"):
    """Convenience: ``with endocore.orm.atomic(): ...`` on the default connection."""
    return get_connection(alias).atomic()


def close_all() -> None:
    for conn in _connections.values():
        conn.close()
