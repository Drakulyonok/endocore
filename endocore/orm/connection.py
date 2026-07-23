"""Connection registry, pooling and transactions.

Each alias owns a small **pool** of lazily-opened DB-API connections
(``pool_size``; SQLite defaults to 1, PostgreSQL to 5). Values passed to
``execute`` are always bound by the driver — never formatted into the SQL
string. Credentials live only in the config dict and are never logged.

A root transaction **pins one pooled connection** for its whole block.
Ownership is a :class:`contextvars.ContextVar` token, not a thread id: the
async ORM offloads via ``asyncio.to_thread``, which *copies* the caller's
context — so ``a*`` calls inside ``async with aatomic():`` join the open
transaction even though they run on another thread. Sync code uses
``with atomic():``; nested blocks become SAVEPOINTs.
"""

from __future__ import annotations

import asyncio
import threading
import time
import warnings
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

from endocore.orm.backends import BaseBackend, get_backend
from endocore.orm.exceptions import ConfigurationError, PoolTimeoutError

#: Keys never echoed back in reprs / errors.
_SECRET_KEYS = frozenset({"password", "passwd", "secret", "dsn"})

#: alias -> owner token of an open transaction, propagated into worker threads
#: by ``asyncio.to_thread`` (which runs in a copy of the caller's context).
_TX: ContextVar[dict] = ContextVar("endocore_tx", default={})


class _TxState:
    """An open root transaction: its pinned raw connection and nesting depth."""

    __slots__ = ("raw", "depth")

    def __init__(self, raw) -> None:
        self.raw = raw
        self.depth = 1


class _EagerCursor:
    """A cursor whose result set was fetched at execute time.

    sqlite3 cursors pull rows lazily and a ``rollback()`` on the shared
    connection resets every pending statement — so a caller fetching after the
    connection went back to the pool could read an empty result. Materializing
    up front closes that window; dialects with client-side results (psycopg)
    don't need it.
    """

    __slots__ = ("rowcount", "lastrowid", "description", "_rows", "_idx")

    def __init__(self, cursor) -> None:
        self.rowcount = cursor.rowcount
        self.lastrowid = cursor.lastrowid
        self.description = cursor.description
        self._rows = cursor.fetchall() if cursor.description is not None else []
        self._idx = 0

    def fetchone(self):
        if self._idx >= len(self._rows):
            return None
        row = self._rows[self._idx]
        self._idx += 1
        return row

    def fetchall(self):
        rows = self._rows[self._idx:]
        self._idx = len(self._rows)
        return rows


class Connection:
    """Owns a pool of DB-API connections and transaction state for an alias."""

    def __init__(self, backend: BaseBackend, params: dict[str, Any], alias: str) -> None:
        self.backend = backend
        self.params = dict(params)
        self.alias = alias
        self.pool_size = int(self.params.pop("pool_size", backend.default_pool_size))
        if self.pool_size < 1:
            raise ConfigurationError("pool_size must be >= 1")
        #: max seconds to wait for a free pooled connection before raising
        #: PoolTimeoutError, instead of blocking forever on a stuck/exhausted pool.
        self.pool_timeout = float(self.params.pop("pool_timeout", 30.0))
        self._idle: list = []   # returned raw connections, ready to borrow
        self._all: list = []    # every raw connection ever opened (for close())
        self._cond = threading.Condition()
        self._active_tx: dict[object, _TxState] = {}  # token -> pinned tx state

    # -- pool --------------------------------------------------------------

    def _acquire(self):
        """Borrow a raw connection: reuse an idle one, open a new one while
        under ``pool_size``, else wait for a release (up to ``pool_timeout``)."""
        deadline = time.monotonic() + self.pool_timeout
        with self._cond:
            while True:
                if self._idle:
                    return self._idle.pop()
                if len(self._all) < self.pool_size:
                    raw = self.backend.connect(**self.params)
                    self._all.append(raw)
                    return raw
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise PoolTimeoutError(
                        f"timed out after {self.pool_timeout}s waiting for a free "
                        f"{self.alias!r} connection (pool_size={self.pool_size}); "
                        "raise pool_size or check for a transaction held open too long"
                    )
                self._cond.wait(remaining)

    def _release(self, raw) -> None:
        """Return a raw connection to the pool."""
        if self.backend.reset_on_release:
            # End the driver's implicit transaction (e.g. psycopg after a bare
            # SELECT) so pooled connections never sit "idle in transaction".
            try:
                raw.rollback()
            except Exception:  # noqa: BLE001 - a broken conn must not poison the pool
                with self._cond:
                    if raw in self._all:
                        self._all.remove(raw)
                    self._cond.notify()
                try:
                    raw.close()
                except Exception:  # noqa: BLE001
                    pass
                return
        with self._cond:
            self._idle.append(raw)
            self._cond.notify()

    # -- statements --------------------------------------------------------

    def _current_tx(self) -> _TxState | None:
        """The open transaction owned by the *calling context*, if any."""
        token = _TX.get().get(self.alias)
        if token is None:
            return None
        return self._active_tx.get(token)

    def execute(self, sql: str, params: Any = (), *, write: bool = False):
        """Run one statement with bound params.

        Inside the owning transaction: executes on its pinned connection
        (commit happens at the ``atomic()`` exit). Outside: borrows a pool
        connection for the statement and commits writes immediately.
        """
        tx = self._current_tx()
        if tx is not None:
            cursor = tx.raw.cursor()
            cursor.execute(sql, tuple(params))
            if self.backend.materialize_results:
                cursor = _EagerCursor(cursor)
            return cursor
        raw = self._acquire()
        try:
            cursor = raw.cursor()
            cursor.execute(sql, tuple(params))
            if self.backend.materialize_results:
                # Fetch before releasing: a rollback on the shared connection
                # would otherwise reset this cursor mid-read (sqlite3).
                cursor = _EagerCursor(cursor)
            if write:
                raw.commit()
            return cursor
        finally:
            # Results are client-side by here, so callers may fetch after this.
            self._release(raw)

    def executescript(self, sql: str) -> None:
        """Run DDL (no bound params). Commits immediately when not in atomic."""
        tx = self._current_tx()
        if tx is not None:
            tx.raw.cursor().execute(sql)
            return
        raw = self._acquire()
        try:
            raw.cursor().execute(sql)
            raw.commit()
        finally:
            self._release(raw)

    # -- transactions ------------------------------------------------------

    def _root_tx(self, raw) -> Iterator[None]:
        """Body of an outermost transaction on an already-acquired connection."""
        token = object()
        self._active_tx[token] = _TxState(raw)
        reset = _TX.set({**_TX.get(), self.alias: token})
        try:
            yield
        except BaseException:
            raw.rollback()
            raise
        else:
            raw.commit()
        finally:
            del self._active_tx[token]
            try:
                _TX.reset(reset)
            except ValueError:
                # Exited in a different context (aatomic offload); the stale
                # token is inert because it is gone from _active_tx.
                pass
            self._release(raw)

    def _nested_tx(self, tx: _TxState) -> Iterator[None]:
        """A SAVEPOINT inside the current context's open transaction."""
        tx.depth += 1
        savepoint = f"endo_sp_{tx.depth}"
        tx.raw.cursor().execute(f"SAVEPOINT {savepoint}")
        try:
            yield
        except BaseException:
            tx.raw.cursor().execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            raise
        else:
            tx.raw.cursor().execute(f"RELEASE SAVEPOINT {savepoint}")
        finally:
            tx.depth -= 1

    @contextmanager
    def atomic(self) -> Iterator[None]:
        """Transaction block. Nested blocks use SAVEPOINTs, so an inner failure
        can roll back just its own work if the caller catches the exception.

        The block pins one pooled connection until it exits, so concurrent
        requests can never interleave statements inside it. In async code use
        ``async with connection.aatomic():`` instead — waiting on an exhausted
        pool here would block the event loop.
        """
        tx = self._current_tx()
        if tx is not None:
            yield from self._nested_tx(tx)
            return
        self._warn_if_event_loop()
        yield from self._root_tx(self._acquire())

    def aatomic(self) -> "_AsyncAtomic":
        """:meth:`atomic` for async code: ``async with connection.aatomic():``.

        Pool waits and commit/rollback happen in a worker thread (the loop is
        never blocked); ``a*`` ORM calls inside the block join the transaction.
        """
        return _AsyncAtomic(self)

    def _warn_if_event_loop(self) -> None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        warnings.warn(
            "atomic() entered on the event loop thread; waiting on the "
            "connection pool would block the loop. Use 'async with aatomic()' "
            "in async code.",
            RuntimeWarning,
            stacklevel=4,
        )

    def close(self) -> None:
        with self._cond:
            conns, self._idle, self._all = self._all, [], []
        for raw in conns:
            try:
                raw.close()
            except Exception:  # noqa: BLE001
                pass

    def __repr__(self) -> str:
        safe = {k: ("***" if k in _SECRET_KEYS else v) for k, v in self.params.items()}
        return f"<Connection {self.alias} {self.backend.name} pool={self.pool_size} {safe}>"


class _AsyncAtomic:
    """Async context manager driving the sync transaction generators off-loop."""

    def __init__(self, connection: Connection) -> None:
        self._connection = connection
        self._gen: Iterator[None] | None = None

    async def __aenter__(self) -> None:
        conn = self._connection
        tx = conn._current_tx()
        if tx is not None:
            self._gen = conn._nested_tx(tx)
        else:
            # Waiting on the pool must not block the loop; the raw connection
            # object is safely handed back to this task's context.
            raw = await asyncio.to_thread(conn._acquire)
            self._gen = conn._root_tx(raw)
        # Runs in the caller's context so the ownership token lands in the
        # awaiting task's context (and is inherited by to_thread offloads).
        next(self._gen)

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        gen = self._gen

        def finish() -> None:
            if exc is None:
                try:
                    next(gen)
                except StopIteration:
                    pass
            else:
                try:
                    gen.throw(exc)
                except BaseException as raised:  # noqa: BLE001
                    if raised is not exc:  # rollback itself failed
                        raise

        # Commit/rollback are I/O — keep them off the event loop too.
        await asyncio.to_thread(finish)
        return False


_connections: dict[str, Connection] = {}


def configure(alias: str = "default", *, backend: str, **params: Any) -> Connection:
    """Register (or replace) a connection for ``alias``. Opens lazily on first
    use. ``pool_size=N`` bounds the number of physical connections (defaults:
    SQLite 1, PostgreSQL 5)."""
    conn = Connection(get_backend(backend), params, alias)
    _connections[alias] = conn
    return conn


def connect(*, backend: str, **params: Any) -> Connection:
    """Configure the ``default`` connection and open one eagerly to validate."""
    conn = configure("default", backend=backend, **params)
    conn._release(conn._acquire())
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


def aatomic(alias: str = "default"):
    """Convenience: ``async with endocore.orm.aatomic(): ...`` (non-blocking)."""
    return get_connection(alias).aatomic()


def close_all() -> None:
    for conn in _connections.values():
        conn.close()
