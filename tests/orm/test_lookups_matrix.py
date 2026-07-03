"""Every lookup against a fixed dataset — exact result sets."""

from __future__ import annotations

import pytest

from endocore.orm import Model, fields, configure, create_all, Q
from endocore.orm.connection import get_connection


class Row(Model):
    name = fields.CharField(max_length=30)
    n = fields.IntegerField(default=0)


DATA = [("apple", 10), ("banana", 20), ("cherry", 30), ("date", 40), ("Apple", 15), ("BANANA", 25)]


@pytest.fixture(scope="module")
def db():
    configure(backend="sqlite", database=":memory:")
    create_all(Row)
    for name, n in DATA:
        Row.objects.create(name=name, n=n)
    yield
    get_connection().close()


def _names(qs):
    return sorted(r.name for r in qs)


# -- integer lookups ---------------------------------------------------------

INT_CASES = [
    ("n", 10, ["apple"]),
    ("n__gt", 20, ["BANANA", "cherry", "date"]),
    ("n__gte", 20, ["BANANA", "banana", "cherry", "date"]),
    ("n__lt", 20, ["Apple", "apple"]),
    ("n__lte", 20, ["Apple", "apple", "banana"]),
    ("n__in", [10, 30], ["apple", "cherry"]),
    ("n__in", [], []),
    ("n__range", (15, 30), ["BANANA", "Apple", "banana", "cherry"]),
    ("n__isnull", False, ["Apple", "BANANA", "apple", "banana", "cherry", "date"]),
    ("n__isnull", True, []),
]


@pytest.mark.parametrize("lookup,value,expected", INT_CASES)
def test_int_lookup(db, lookup, value, expected):
    assert _names(Row.objects.filter(**{lookup: value})) == sorted(expected)


@pytest.mark.parametrize("lookup,value,expected", INT_CASES)
def test_int_lookup_count(db, lookup, value, expected):
    assert Row.objects.filter(**{lookup: value}).count() == len(expected)


@pytest.mark.parametrize("lookup,value,expected", INT_CASES)
def test_int_exclude_is_complement(db, lookup, value, expected):
    everyone = {name for name, _ in DATA}
    assert _names(Row.objects.exclude(**{lookup: value})) == sorted(everyone - set(expected))


# -- string lookups ----------------------------------------------------------

STR_CASES = [
    ("name", "apple", ["apple"]),
    ("name__iexact", "apple", ["Apple", "apple"]),
    ("name__contains", "an", ["banana"]),
    ("name__icontains", "an", ["BANANA", "banana"]),
    ("name__startswith", "a", ["apple"]),
    ("name__istartswith", "a", ["Apple", "apple"]),
    ("name__endswith", "e", ["Apple", "apple", "date"]),
    ("name__iendswith", "E", ["Apple", "apple", "date"]),
    ("name__contains", "z", []),
    ("name__in", ["apple", "date"], ["apple", "date"]),
]


@pytest.mark.parametrize("lookup,value,expected", STR_CASES)
def test_str_lookup(db, lookup, value, expected):
    assert _names(Row.objects.filter(**{lookup: value})) == sorted(expected)


@pytest.mark.parametrize("lookup,value,expected", STR_CASES)
def test_str_lookup_count(db, lookup, value, expected):
    assert Row.objects.filter(**{lookup: value}).count() == len(expected)


# -- Q combinations ----------------------------------------------------------

@pytest.mark.parametrize("q,expected", [
    (Q(n__lt=20) | Q(n__gt=30), ["Apple", "apple", "date"]),
    (Q(n__gte=20) & Q(n__lte=30), ["BANANA", "banana", "cherry"]),
    (~Q(n__lt=30), ["cherry", "date"]),
    (Q(name__icontains="apple") | Q(name__icontains="date"), ["Apple", "apple", "date"]),
    (Q(n__in=[10, 20]) & ~Q(name="apple"), ["banana"]),
])
def test_q_combinations(db, q, expected):
    assert _names(Row.objects.filter(q)) == sorted(expected)


# -- chained filters ---------------------------------------------------------

def test_chained_filters_and(db):
    qs = Row.objects.filter(n__gte=15).filter(n__lte=30)
    assert _names(qs) == sorted(["Apple", "BANANA", "banana", "cherry"])


@pytest.mark.parametrize("field,reverse", [("n", False), ("n", True), ("name", False), ("name", True)])
def test_order_by(db, field, reverse):
    spec = f"-{field}" if reverse else field
    values = [getattr(r, field) for r in Row.objects.order_by(spec)]
    assert values == sorted(values, reverse=reverse)
