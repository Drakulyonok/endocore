"""F expressions, aggregates, distinct, edges, get_or_create, bulk_create."""

from __future__ import annotations

import pytest

from endocore.orm import Model, fields, configure, create_all, F, Count, Sum, Avg, Min, Max
from endocore.orm.connection import get_connection


class Row(Model):
    name = fields.CharField(max_length=20)
    n = fields.IntegerField(default=0)


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
