"""Transaction isolation and the async transaction API.

Regression suite for the review fixes:
- concurrent threads can no longer interleave statements inside an open
  ``atomic()`` block (the transaction lock is held for the whole block);
- ``aatomic()`` gives async code the same semantics without blocking the loop,
  and ``a*`` ORM calls made inside it join the transaction via the ownership
  token propagated by ``asyncio.to_thread``;
- Unicode ``iexact`` / ``icontains`` work on SQLite (custom LOWER);
- ForeignKeys to non-integer pks (UUID) assign, save and load correctly.
"""

from __future__ import annotations

import asyncio
import threading
import time
import uuid

import pytest

from endocore.orm import Model, fields, configure, create_all, atomic, aatomic
from endocore.orm.connection import get_connection


class Entry(Model):
    class Meta:
        table = "txiso_entries"

    name = fields.CharField(max_length=50)


@pytest.fixture()
def db():
    configure(backend="sqlite", database=":memory:")
    create_all(Entry)
    yield
    get_connection().close()


# -- cross-thread isolation -------------------------------------------------

def test_writer_outside_tx_waits_for_rollback(db):
    """A concurrent autocommit write blocks until the transaction ends, and a
    rollback discards only the transaction's own work."""
    tx_started = threading.Event()
    release_tx = threading.Event()
    outsider_done = threading.Event()

    def transaction():
        try:
            with atomic():
                Entry.objects.create(name="inside")
                tx_started.set()
                release_tx.wait(5)
                raise RuntimeError("boom")
        except RuntimeError:
            pass

    def outsider():
        Entry.objects.create(name="outside")  # must wait out the open tx
        outsider_done.set()

    t1 = threading.Thread(target=transaction)
    t1.start()
    assert tx_started.wait(5)
    t2 = threading.Thread(target=outsider)
    t2.start()

    time.sleep(0.15)
    assert not outsider_done.is_set(), "outsider ran inside a foreign transaction"

    release_tx.set()
    t1.join(5)
    t2.join(5)
    assert outsider_done.is_set()
    assert [e.name for e in Entry.objects.all()] == ["outside"]


def test_two_transactions_serialize(db):
    """Two atomic() blocks in different threads run one after the other."""
    order: list[str] = []

    def tx(tag: str):
        with atomic():
            order.append(f"{tag}-in")
            Entry.objects.create(name=tag)
            time.sleep(0.05)
            order.append(f"{tag}-out")

    threads = [threading.Thread(target=tx, args=(t,)) for t in ("a", "b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(5)

    # Whole blocks are serialized: in/out pairs never interleave.
    assert order in (["a-in", "a-out", "b-in", "b-out"],
                     ["b-in", "b-out", "a-in", "a-out"])
    assert Entry.objects.count() == 2


def test_nested_atomic_still_uses_savepoints(db):
    with atomic():
        Entry.objects.create(name="outer")
        try:
            with atomic():
                Entry.objects.create(name="inner")
                raise ValueError("inner fails")
        except ValueError:
            pass
    assert [e.name for e in Entry.objects.all()] == ["outer"]


# -- aatomic ---------------------------------------------------------------

def test_aatomic_commit_and_visibility(db):
    async def main():
        async with aatomic():
            await Entry.objects.acreate(name="a")
            # The a* call above ran in a worker thread but joined this
            # transaction via the context token — so it is visible here.
            return await Entry.objects.acount()

    assert asyncio.run(main()) == 1
    assert Entry.objects.count() == 1


def test_aatomic_rollback(db):
    async def main():
        async with aatomic():
            await Entry.objects.acreate(name="ghost")
            raise ValueError("boom")

    with pytest.raises(ValueError):
        asyncio.run(main())
    assert Entry.objects.count() == 0


def test_aatomic_nested_savepoint(db):
    async def main():
        async with aatomic():
            await Entry.objects.acreate(name="outer")
            try:
                async with aatomic():
                    await Entry.objects.acreate(name="inner")
                    raise ValueError("inner fails")
            except ValueError:
                pass

    asyncio.run(main())
    assert [e.name for e in Entry.objects.all()] == ["outer"]


def test_atomic_on_event_loop_warns(db):
    async def main():
        with pytest.warns(RuntimeWarning, match="aatomic"):
            with atomic():
                Entry.objects.create(name="x")

    asyncio.run(main())
    assert Entry.objects.count() == 1


# -- eager results ----------------------------------------------------------

def test_select_results_survive_concurrent_rollback(db):
    """A rollback on the shared SQLite connection between execute and fetch
    must not wipe an already-returned result set (sqlite3 resets lazy cursors
    on rollback; the pool materializes results before release)."""
    Entry.objects.create(name="kept")
    conn = get_connection()
    cursor = conn.execute('SELECT "name" FROM "txiso_entries"')
    conn._all[0].rollback()  # what another thread's failed transaction does
    assert cursor.fetchall() == [("kept",)]


# -- connection pool -------------------------------------------------------

def test_pool_reader_not_blocked_by_open_tx(tmp_path):
    """With pool_size=2 a concurrent read borrows the second connection: it
    neither waits for the open transaction nor sees its uncommitted rows."""
    configure(backend="sqlite", database=str(tmp_path / "pool.db"), pool_size=2)
    create_all(Entry)
    try:
        tx_started = threading.Event()
        release_tx = threading.Event()

        def transaction():
            with atomic():
                Entry.objects.create(name="uncommitted")
                tx_started.set()
                release_tx.wait(5)

        t = threading.Thread(target=transaction)
        t.start()
        assert tx_started.wait(5)

        began = time.monotonic()
        seen = Entry.objects.count()          # second pool conn: no waiting
        assert time.monotonic() - began < 1.0
        assert seen == 0                      # and no dirty reads

        release_tx.set()
        t.join(5)
        assert Entry.objects.count() == 1     # committed now
        conn = get_connection()
        assert len(conn._all) <= 2            # never exceeded the pool bound
    finally:
        get_connection().close()


def test_pool_size_validation(tmp_path):
    from endocore.orm.exceptions import ConfigurationError

    with pytest.raises(ConfigurationError):
        configure(backend="sqlite", database=str(tmp_path / "x.db"), pool_size=0)
    configure(backend="sqlite", database=":memory:")  # restore a sane default


def test_exhausted_pool_raises_instead_of_hanging_forever(tmp_path):
    """A stuck/exhausted pool must fail fast and loud, not hang the caller
    (and the worker thread behind it) forever with no diagnostic."""
    from endocore.orm.exceptions import PoolTimeoutError

    configure(backend="sqlite", database=str(tmp_path / "timeout.db"), pool_size=1, pool_timeout=0.3)
    conn = get_connection()
    try:
        held = conn._acquire()
        started = time.monotonic()
        with pytest.raises(PoolTimeoutError):
            conn._acquire()
        elapsed = time.monotonic() - started
        assert 0.2 < elapsed < 2.0, elapsed
        conn._release(held)
    finally:
        conn.close()
        configure(backend="sqlite", database=":memory:")


def test_pool_wait_wakes_up_promptly_on_release(tmp_path):
    """A waiter must not sit out the full pool_timeout once a connection is
    actually released — the timeout is a ceiling, not a fixed delay."""
    configure(backend="sqlite", database=str(tmp_path / "wake.db"), pool_size=1, pool_timeout=5.0)
    conn = get_connection()
    try:
        held = conn._acquire()
        waited: list[float] = []

        def waiter():
            started = time.monotonic()
            got = conn._acquire()
            waited.append(time.monotonic() - started)
            conn._release(got)

        t = threading.Thread(target=waiter)
        t.start()
        time.sleep(0.2)
        conn._release(held)
        t.join(3)
        assert waited and waited[0] < 1.0, waited
    finally:
        conn.close()
        configure(backend="sqlite", database=":memory:")


# -- Unicode case-insensitive lookups on SQLite ----------------------------

def test_icontains_iexact_cyrillic(db):
    Entry.objects.create(name="ИВАН Петров")
    assert Entry.objects.filter(name__icontains="иван").count() == 1
    assert Entry.objects.filter(name__istartswith="иВаН").count() == 1
    assert Entry.objects.filter(name__iexact="иван петров").count() == 1
    assert Entry.objects.filter(name__icontains="сидоров").count() == 0


# -- ForeignKey to a UUID primary key --------------------------------------

class UAccount(Model):
    class Meta:
        table = "txiso_uaccounts"

    id = fields.UUIDField(primary_key=True, default=uuid.uuid4)
    name = fields.CharField(max_length=50)


class UNote(Model):
    class Meta:
        table = "txiso_unotes"

    text = fields.CharField(max_length=50)
    owner = fields.ForeignKey(UAccount, on_delete="CASCADE", null=True)


@pytest.fixture()
def udb():
    configure(backend="sqlite", database=":memory:")
    create_all(UAccount, UNote)
    yield
    get_connection().close()


def test_fk_assign_raw_uuid_pk(udb):
    acc = UAccount.objects.create(name="ada")

    note = UNote(text="hi")
    note.owner = str(acc.pk)          # raw pk as its string form
    assert note.owner_id == acc.pk    # coerced through UUIDField.to_python

    note.owner = acc.pk               # raw pk as a UUID instance
    assert note.owner_id == acc.pk


def test_fk_filter_by_attname(udb):
    """Django-style ``filter(owner_id=pk)`` resolves the FK by its attname."""
    acc = UAccount.objects.create(name="ada")
    UNote.objects.create(text="hi", owner=acc)
    assert UNote.objects.filter(owner_id=acc.pk).count() == 1
    assert UNote.objects.filter(owner_id=uuid.uuid4()).count() == 0


def test_fk_uuid_roundtrip_and_lookup(udb):
    acc = UAccount.objects.create(name="ada")
    UNote.objects.create(text="hi", owner=acc)

    fetched = UNote.objects.get(text="hi")
    assert fetched.owner_id == acc.pk
    assert fetched.owner.name == "ada"
    assert UNote.objects.filter(owner=acc).count() == 1
    assert UNote.objects.filter(owner__name="ada").count() == 1


def test_fk_uuid_column_type_matches_target_pk(udb):
    from endocore.orm.schema import create_table_sql

    ddl = create_table_sql(UNote, get_connection().backend)
    assert "CHAR(32)" in ddl  # FK column mirrors the UUID pk type, not INTEGER
