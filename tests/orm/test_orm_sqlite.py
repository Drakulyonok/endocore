"""End-to-end ORM behaviour against a real (in-memory) SQLite database."""

from __future__ import annotations

import pytest

from endocore.orm import Model, fields, Q, configure, create_all, atomic
from endocore.orm.connection import get_connection


class Team(Model):
    name = fields.CharField(max_length=50, unique=True)


class Member(Model):
    name = fields.CharField(max_length=100)
    age = fields.IntegerField(default=0)
    active = fields.BooleanField(default=True)
    team = fields.ForeignKey(Team, null=True, default=None)


@pytest.fixture()
def db():
    # Fresh in-memory database for each test.
    configure(backend="sqlite", database=":memory:")
    create_all(Team, Member)
    yield
    get_connection().close()


def test_create_and_get(db):
    m = Member.objects.create(name="Ada", age=36)
    assert m.pk is not None
    assert Member.objects.get(name="Ada").age == 36


def test_filter_lookups(db):
    Member.objects.create(name="Ada", age=36)
    Member.objects.create(name="Bob", age=17)
    Member.objects.create(name="Cy", age=42)

    assert Member.objects.count() == 3
    assert {m.name for m in Member.objects.filter(age__gte=18)} == {"Ada", "Cy"}
    assert {m.name for m in Member.objects.filter(age__in=[17, 42])} == {"Bob", "Cy"}
    assert [m.name for m in Member.objects.filter(age__range=(18, 40))] == ["Ada"]
    assert {m.name for m in Member.objects.filter(name__icontains="a")} == {"Ada"}


def test_q_objects(db):
    Member.objects.create(name="Ada", age=16)
    Member.objects.create(name="Bob", age=30)
    Member.objects.create(name="Cy", age=70)
    names = [m.name for m in Member.objects.filter(Q(age__lt=18) | Q(age__gt=60)).order_by("age")]
    assert names == ["Ada", "Cy"]


def test_get_raises(db):
    with pytest.raises(Member.DoesNotExist):
        Member.objects.get(name="nobody")
    Member.objects.create(name="d", age=1)
    Member.objects.create(name="d", age=2)
    with pytest.raises(Member.MultipleObjectsReturned):
        Member.objects.get(name="d")


def test_foreign_key_roundtrip(db):
    red = Team.objects.create(name="red")
    m = Member.objects.create(name="Ada", team=red)
    fetched = Member.objects.get(pk=m.pk)
    assert fetched.team_id == red.pk
    assert fetched.team.name == "red"          # lazy load
    assert {x.name for x in Member.objects.filter(team=red)} == {"Ada"}


def test_update_and_delete(db):
    Member.objects.create(name="Ada", age=36)
    Member.objects.create(name="Bob", age=42)
    changed = Member.objects.filter(age__gte=40).update(active=False)
    assert changed == 1
    assert Member.objects.get(name="Bob").active is False

    bob = Member.objects.get(name="Bob")
    bob.delete()
    assert Member.objects.count() == 1
    assert bob.pk is None


def test_instance_save_updates(db):
    m = Member.objects.create(name="Ada", age=1)
    m.age = 99
    m.save()
    assert Member.objects.get(pk=m.pk).age == 99


def test_values_and_values_list(db):
    Member.objects.create(name="Ada", age=36)
    Member.objects.create(name="Bob", age=17)
    assert list(Member.objects.values("name").order_by("name")) == [{"name": "Ada"}, {"name": "Bob"}]
    assert list(Member.objects.values_list("age", flat=True).order_by("age")) == [17, 36]


def test_ordering_and_first_last(db):
    for n, a in [("Ada", 36), ("Bob", 17), ("Cy", 42)]:
        Member.objects.create(name=n, age=a)
    assert Member.objects.order_by("age").first().name == "Bob"
    assert Member.objects.order_by("age").last().name == "Cy"
    assert [m.name for m in Member.objects.order_by("-age")] == ["Cy", "Ada", "Bob"]


def test_stored_injection_payload_is_inert(db):
    payload = "Robert'); DROP TABLE member; --"
    Member.objects.create(name=payload, age=1)
    # Table still exists and the value round-trips verbatim.
    assert Member.objects.get(name=payload).name == payload
    assert Member.objects.count() == 1


def test_atomic_rollback(db):
    Member.objects.create(name="keep", age=1)
    try:
        with atomic():
            Member.objects.create(name="temp", age=2)
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert {m.name for m in Member.objects.all()} == {"keep"}
