"""Pool concurrency against a real PostgreSQL server.

Skipped unless ``ENDOCORE_TEST_POSTGRES_DSN`` is set, e.g.::

    ENDOCORE_TEST_POSTGRES_DSN=postgresql://user:pass@localhost:5432/endocore_test

These are the tests that must pass before trusting ``pool_size > 1`` in
production: genuine transaction concurrency, no-overdraft conditional spends
(the shop pattern), and UNIQUE races that must not poison the pool.
"""

from __future__ import annotations

import os
import threading

import pytest

DSN = os.environ.get("ENDOCORE_TEST_POSTGRES_DSN")

pytestmark = pytest.mark.skipif(
    not DSN, reason="set ENDOCORE_TEST_POSTGRES_DSN to run PostgreSQL pool tests"
)
if DSN:
    pytest.importorskip("psycopg")

from endocore.orm import F, Model, atomic, configure, create_all, fields  # noqa: E402
from endocore.orm.connection import get_connection  # noqa: E402

POOL_SIZE = 4


class PgWallet(Model):
    class Meta:
        table = "pgpool_wallets"

    owner = fields.CharField(max_length=50, unique=True)
    balance = fields.IntegerField(default=0)


class PgClaim(Model):
    class Meta:
        table = "pgpool_claims"

    key = fields.CharField(max_length=80, unique=True)


@pytest.fixture()
def pg():
    conn = configure(backend="postgres", conninfo=DSN, pool_size=POOL_SIZE)
    for model in (PgWallet, PgClaim):
        conn.executescript(f'DROP TABLE IF EXISTS "{model._meta.table}"')
    create_all(PgWallet, PgClaim)
    yield conn
    for model in (PgWallet, PgClaim):
        conn.executescript(f'DROP TABLE IF EXISTS "{model._meta.table}"')
    conn.close()


def test_transactions_run_truly_concurrently(pg):
    """POOL_SIZE threads all sit *inside* their own open transaction at the
    same time. With a serialized pool the barrier could never be crossed."""
    barrier = threading.Barrier(POOL_SIZE, timeout=10)
    errors: list[BaseException] = []

    def worker(n: int):
        try:
            with atomic():
                PgWallet.objects.create(owner=f"user{n}", balance=n)
                barrier.wait()  # requires POOL_SIZE simultaneous open txs
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(POOL_SIZE)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)

    assert not errors, errors
    assert PgWallet.objects.count() == POOL_SIZE
    assert len(pg._all) <= POOL_SIZE


def test_no_overdraft_under_concurrent_spends(pg):
    """The shop pattern: conditional UPDATE ... WHERE balance >= cost is the
    only spend primitive that survives READ COMMITTED concurrency. 100 coins,
    8 racers spending 30 -> exactly 3 wins, balance 10, never negative."""
    wallet = PgWallet.objects.create(owner="buyer", balance=100)
    attempts, cost = 8, 30
    barrier = threading.Barrier(attempts, timeout=10)
    results: list[bool] = []
    lock = threading.Lock()

    def spend():
        barrier.wait()
        won = PgWallet.objects.filter(
            pk=wallet.pk, balance__gte=cost
        ).update(balance=F("balance") - cost)
        with lock:
            results.append(bool(won))

    threads = [threading.Thread(target=spend) for _ in range(attempts)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)

    assert results.count(True) == 3, results
    wallet = PgWallet.objects.get(pk=wallet.pk)
    assert wallet.balance == 10


def test_unique_race_does_not_poison_the_pool(pg):
    """8 threads claim one idempotency key inside transactions: one insert
    wins, the losers' failed transactions roll back cleanly and their
    connections keep serving queries afterwards."""
    attempts = 8
    barrier = threading.Barrier(attempts, timeout=10)
    outcomes: list[str] = []
    lock = threading.Lock()

    def claim():
        barrier.wait()
        try:
            with atomic():
                PgClaim.objects.create(key="the-one-key")
            outcome = "won"
        except Exception as exc:  # noqa: BLE001
            outcome = "unique" if "unique" in str(exc).lower() else f"error: {exc!r}"
        with lock:
            outcomes.append(outcome)

    threads = [threading.Thread(target=claim) for _ in range(attempts)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)

    assert outcomes.count("won") == 1, outcomes
    assert outcomes.count("unique") == attempts - 1, outcomes
    assert PgClaim.objects.count() == 1
    # The pool still works after the failed transactions.
    assert PgClaim.objects.filter(key="the-one-key").exists()
