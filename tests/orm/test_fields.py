"""New field types, adaptation, and validation."""

from __future__ import annotations

import datetime
import uuid

import pytest

from endocore.orm import Model, fields, configure, create_all, ValidationError
from endocore.orm.connection import get_connection


class Thing(Model):
    slug = fields.SlugField()
    email = fields.EmailField(null=True, default=None)
    site = fields.URLField(null=True, default=None)
    ip = fields.GenericIPAddressField(null=True, default=None)
    uid = fields.UUIDField(default=uuid.uuid4)
    data = fields.JSONField(default=dict)
    blob = fields.BinaryField(null=True, default=None)
    when = fields.TimeField(null=True, default=None)
    dur = fields.DurationField(null=True, default=None)
    qty = fields.PositiveIntegerField(default=0)
    small = fields.SmallIntegerField(default=0)
    status = fields.CharField(max_length=10, choices=["new", "done"], default="new")


@pytest.fixture()
def db():
    configure(backend="sqlite", database=":memory:")
    create_all(Thing)
    yield
    get_connection().close()


def test_roundtrip_all_types(db):
    t = Thing.objects.create(
        slug="hello-world", email="a@b.com", site="https://x.io", ip="10.0.0.1",
        data={"k": [1, 2, 3]}, blob=b"\x00\x01\x02", when=datetime.time(12, 30),
        dur=datetime.timedelta(seconds=90), qty=5, small=100, status="done",
    )
    g = Thing.objects.get(pk=t.pk)
    assert isinstance(g.uid, uuid.UUID)
    assert g.data == {"k": [1, 2, 3]}
    assert bytes(g.blob) == b"\x00\x01\x02"
    assert g.when == datetime.time(12, 30)
    assert g.dur == datetime.timedelta(seconds=90)
    assert g.status == "done"


@pytest.mark.parametrize("kwargs", [
    {"slug": "not a slug!"},
    {"slug": "ok", "email": "nope"},
    {"slug": "ok", "site": "ftp://x"},
    {"slug": "ok", "ip": "999.1.1.1"},
    {"slug": "ok", "qty": -1},
    {"slug": "ok", "small": 999999},
    {"slug": "ok", "status": "weird"},
])
def test_validation_rejects_bad_values(db, kwargs):
    with pytest.raises(ValidationError):
        Thing.objects.create(**kwargs)


def test_json_and_uuid_query(db):
    u = uuid.uuid4()
    Thing.objects.create(slug="a", uid=u)
    assert Thing.objects.get(uid=u).slug == "a"
