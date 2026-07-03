"""QuerySet/manager method coverage."""

from __future__ import annotations

import pytest

from endocore.orm import Model, fields, configure, create_all, F, Count, Sum, Avg, Min, Max
from endocore.orm.connection import get_connection


class Num(Model):
    class Meta:
        ordering = ["v"]

    label = fields.CharField(max_length=10)
    v = fields.IntegerField(default=0)


@pytest.fixture()
def db():
    configure(backend="sqlite", database=":memory:")
    create_all(Num)
    yield
    get_connection().close()


def _seed(n):
    Num.objects.bulk_create([Num(label=chr(97 + i % 26), v=i) for i in range(n)])


@pytest.mark.parametrize("n", [0, 1, 2, 5, 10, 25, 50])
def test_count(db, n):
    _seed(n)
    assert Num.objects.count() == n


@pytest.mark.parametrize("n", [0, 1, 5, 20])
def test_len_and_bool(db, n):
    _seed(n)
    qs = Num.objects.all()
    assert len(qs) == n
    assert bool(qs) is (n > 0)


@pytest.mark.parametrize("n", [1, 2, 10, 30])
def test_first_last_ordering(db, n):
    _seed(n)
    assert Num.objects.first().v == 0
    assert Num.objects.last().v == n - 1


def test_first_last_empty(db):
    assert Num.objects.first() is None
    assert Num.objects.last() is None


@pytest.mark.parametrize("start,stop", [(0, 5), (2, 8), (5, 10), (0, 1), (3, 3), (10, 20)])
def test_slicing(db, start, stop):
    _seed(30)
    got = [r.v for r in Num.objects.order_by("v")[start:stop]]
    assert got == list(range(start, stop))


@pytest.mark.parametrize("i", [0, 1, 5, 9])
def test_indexing(db, i):
    _seed(10)
    assert Num.objects.order_by("v")[i].v == i


@pytest.mark.parametrize("n,exists", [(0, False), (1, True), (5, True)])
def test_exists(db, n, exists):
    _seed(n)
    assert Num.objects.exists() is exists


def test_none(db):
    _seed(5)
    assert list(Num.objects.none()) == []
    assert Num.objects.none().count() == 0
    assert Num.objects.none().exists() is False


@pytest.mark.parametrize("v", [0, 3, 7])
def test_get(db, v):
    _seed(10)
    assert Num.objects.get(v=v).v == v


def test_get_raises(db):
    _seed(3)
    with pytest.raises(Num.DoesNotExist):
        Num.objects.get(v=999)
    Num.objects.create(label="dup", v=0)  # a second row with v=0
    with pytest.raises(Num.MultipleObjectsReturned):
        Num.objects.get(v=0)


@pytest.mark.parametrize("n", [1, 5, 10])
def test_values(db, n):
    _seed(n)
    rows = list(Num.objects.values("v").order_by("v"))
    assert rows == [{"v": i} for i in range(n)]


@pytest.mark.parametrize("n", [1, 5, 10])
def test_values_list_flat(db, n):
    _seed(n)
    assert list(Num.objects.values_list("v", flat=True).order_by("v")) == list(range(n))


def test_values_list_tuples(db):
    _seed(3)
    rows = list(Num.objects.values_list("label", "v").order_by("v"))
    assert rows == [("a", 0), ("b", 1), ("c", 2)]


def test_distinct(db):
    Num.objects.bulk_create([Num(label="a", v=1), Num(label="a", v=2), Num(label="b", v=3)])
    assert sorted(Num.objects.values_list("label", flat=True).distinct()) == ["a", "b"]


@pytest.mark.parametrize("agg,expected", [
    (lambda: {"s": Sum("v")}, {"s": 45}),
    (lambda: {"c": Count("*")}, {"c": 10}),
    (lambda: {"a": Avg("v")}, {"a": 4.5}),
    (lambda: {"mn": Min("v")}, {"mn": 0}),
    (lambda: {"mx": Max("v")}, {"mx": 9}),
])
def test_aggregate(db, agg, expected):
    _seed(10)
    assert Num.objects.aggregate(**agg()) == expected


@pytest.mark.parametrize("delta", [1, 5, 100, -3])
def test_f_update(db, delta):
    _seed(5)
    Num.objects.all().update(v=F("v") + delta)
    assert sorted(Num.objects.values_list("v", flat=True)) == sorted(i + delta for i in range(5))


def test_get_or_create(db):
    obj, created = Num.objects.get_or_create(label="x", defaults={"v": 7})
    assert created and obj.v == 7
    obj2, created2 = Num.objects.get_or_create(label="x", defaults={"v": 9})
    assert not created2 and obj2.v == 7


def test_update_or_create(db):
    _, created = Num.objects.update_or_create(label="x", defaults={"v": 1})
    assert created
    obj, created2 = Num.objects.update_or_create(label="x", defaults={"v": 2})
    assert not created2 and obj.v == 2


def test_in_bulk(db):
    _seed(5)
    ids = list(Num.objects.values_list("pk", flat=True))
    mapping = Num.objects.in_bulk(ids)
    assert set(mapping) == set(ids)
    assert all(mapping[i].pk == i for i in ids)


@pytest.mark.parametrize("n", [1, 3, 10])
def test_delete_returns_count(db, n):
    _seed(n)
    assert Num.objects.all().delete() == n
    assert Num.objects.count() == 0


def test_earliest_latest(db):
    _seed(10)
    assert Num.objects.earliest("v").v == 0
    assert Num.objects.latest("v").v == 9


@pytest.mark.parametrize("n", [1, 5, 20])
def test_iteration_and_contains(db, n):
    _seed(n)
    objs = list(Num.objects.all())
    assert len(objs) == n
    if objs:
        assert objs[0] in Num.objects.all()
