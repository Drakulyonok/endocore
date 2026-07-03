"""Cross-table lookups (JOINs) and select_related."""

from __future__ import annotations

import pytest

from endocore.orm import Model, fields, configure, create_all
from endocore.orm.connection import get_connection


class Country(Model):
    name = fields.CharField(max_length=50)


class City(Model):
    name = fields.CharField(max_length=50)
    country = fields.ForeignKey(Country)


class Person(Model):
    name = fields.CharField(max_length=50)
    city = fields.ForeignKey(City, null=True, default=None)


@pytest.fixture()
def db():
    configure(backend="sqlite", database=":memory:")
    create_all(Country, City, Person)
    fr = Country.objects.create(name="France")
    de = Country.objects.create(name="Germany")
    paris = City.objects.create(name="Paris", country=fr)
    berlin = City.objects.create(name="Berlin", country=de)
    Person.objects.create(name="Ada", city=paris)
    Person.objects.create(name="Bob", city=berlin)
    Person.objects.create(name="Cy", city=None)
    yield
    get_connection().close()


def test_one_level_relation_filter(db):
    assert [p.name for p in Person.objects.filter(city__name="Paris")] == ["Ada"]


def test_two_level_relation_filter(db):
    assert [p.name for p in Person.objects.filter(city__country__name="France")] == ["Ada"]


def test_relation_lookup_with_operator(db):
    names = {p.name for p in Person.objects.filter(city__country__name__icontains="ran")}
    assert names == {"Ada"}


def test_order_by_relation(db):
    names = [p.name for p in Person.objects.filter(city__isnull=False).order_by("city__country__name", "name")]
    assert names == ["Ada", "Bob"]


def test_count_with_join(db):
    assert Person.objects.filter(city__country__name="Germany").count() == 1


def test_select_related_two_levels(db):
    p = Person.objects.select_related("city__country").get(name="Ada")
    assert p.city.name == "Paris"
    assert p.city.country.name == "France"


def test_select_related_null_fk(db):
    p = Person.objects.select_related("city").get(name="Cy")
    assert p.city is None


def test_not_a_relation_raises(db):
    from endocore.orm.exceptions import FieldError

    with pytest.raises(FieldError):
        list(Person.objects.filter(name__country__x=1))
