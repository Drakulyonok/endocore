"""F expressions, aggregates, distinct, edges, get_or_create, bulk_create."""

from __future__ import annotations

import threading

import pytest

from endocore.orm import Model, fields, configure, create_all, F, Count, Sum, Avg, Min, Max
from endocore.orm.connection import get_connection


class Row(Model):
    name = fields.CharField(max_length=20)
    n = fields.IntegerField(default=0)


class Claim(Model):
    key = fields.CharField(max_length=40, unique=True)


@pytest.fixture()
def db():
    configure(backend="sqlite", database=":memory:")
    create_all(Row)
    yield
    get_connection().close()


def test_bulk_create_one_statement(db):
    Row.objects.bulk_create([Row(name="a", n=1), Row(name="b", n=2), Row(name="a", n=3)])
    assert Row.objects.count() == 3


def test_f_expression_update(db):
    Row.objects.create(name="a", n=10)
    Row.objects.create(name="a", n=20)
    Row.objects.filter(name="a").update(n=F("n") + 5)
    assert sorted(Row.objects.values_list("n", flat=True)) == [15, 25]


def test_aggregate(db):
    Row.objects.bulk_create([Row(name="a", n=10), Row(name="b", n=20), Row(name="c", n=30)])
    result = Row.objects.aggregate(total=Sum("n"), c=Count("*"), a=Avg("n"), mn=Min("n"), mx=Max("n"))
    assert result == {"total": 60, "c": 3, "a": 20.0, "mn": 10, "mx": 30}


def test_distinct(db):
    Row.objects.bulk_create([Row(name="a", n=1), Row(name="a", n=2), Row(name="b", n=3)])
    assert sorted(Row.objects.values_list("name", flat=True).distinct()) == ["a", "b"]


def test_earliest_latest(db):
    Row.objects.bulk_create([Row(name="a", n=5), Row(name="b", n=1), Row(name="c", n=9)])
    assert Row.objects.latest("n").name == "c"
    assert Row.objects.earliest("n").name == "b"


def test_earliest_on_empty_raises(db):
    with pytest.raises(Row.DoesNotExist):
        Row.objects.earliest("n")


def test_get_or_create(db):
    obj, created = Row.objects.get_or_create(name="x", defaults={"n": 7})
    assert created and obj.n == 7
    obj2, created2 = Row.objects.get_or_create(name="x", defaults={"n": 999})
    assert not created2 and obj2.n == 7


def test_update_or_create(db):
    obj, created = Row.objects.update_or_create(name="x", defaults={"n": 1})
    assert created
    obj2, created2 = Row.objects.update_or_create(name="x", defaults={"n": 2})
    assert not created2 and obj2.n == 2
    assert Row.objects.count() == 1


@pytest.fixture()
def claim_db():
    configure(backend="sqlite", database=":memory:", pool_size=1)
    create_all(Claim)
    yield
    get_connection().close()


def _race(fn, attempts=8):
    barrier = threading.Barrier(attempts, timeout=10)
    outcomes: list = []
    lock = threading.Lock()

    def run():
        barrier.wait()
        outcomes.append(fn())

    threads = [threading.Thread(target=run) for _ in range(attempts)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    return outcomes


def test_get_or_create_concurrent_race_has_exactly_one_winner(claim_db):
    """Two get_or_create() calls racing the same not-yet-existing row must
    never let the loser's create() raise an IntegrityError past the caller —
    it should quietly see the winner's row instead."""

    def attempt():
        try:
            _, created = Claim.objects.get_or_create(key="the-one-key")
            return "created" if created else "found"
        except Exception as exc:  # noqa: BLE001
            return f"error: {exc!r}"

    outcomes = _race(attempt)
    assert outcomes.count("created") == 1, outcomes
    assert outcomes.count("found") == len(outcomes) - 1, outcomes
    assert Claim.objects.filter(key="the-one-key").count() == 1


def test_update_or_create_concurrent_race_has_exactly_one_winner(claim_db):
    def attempt():
        try:
            _, created = Claim.objects.update_or_create(key="the-one-key")
            return "created" if created else "found"
        except Exception as exc:  # noqa: BLE001
            return f"error: {exc!r}"

    outcomes = _race(attempt)
    assert outcomes.count("created") == 1, outcomes
    assert outcomes.count("found") == len(outcomes) - 1, outcomes
    assert Claim.objects.filter(key="the-one-key").count() == 1
