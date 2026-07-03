"""Property-style roundtrip coverage: many values survive DB write/read."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import pytest

from endocore.orm import Model, fields, configure, create_all
from endocore.orm.connection import get_connection


class Box(Model):
    i = fields.IntegerField(default=0)
    big = fields.BigIntegerField(default=0)
    small = fields.SmallIntegerField(default=0)
    f = fields.FloatField(default=0.0)
    dec = fields.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0"))
    s = fields.CharField(max_length=200, default="")
    t = fields.TextField(default="")
    b = fields.BooleanField(default=False)
    u = fields.UUIDField(default=uuid.uuid4)
    j = fields.JSONField(default=dict)
    blob = fields.BinaryField(null=True, default=None)
    when = fields.DateTimeField(null=True, default=None)
    day = fields.DateField(null=True, default=None)
    clock = fields.TimeField(null=True, default=None)
    dur = fields.DurationField(null=True, default=None)


@pytest.fixture(scope="module")
def db():
    configure(backend="sqlite", database=":memory:")
    create_all(Box)
    yield
    get_connection().close()


def _roundtrip(field: str, value):
    obj = Box.objects.create(**{field: value})
    return getattr(Box.objects.get(pk=obj.pk), field)


@pytest.mark.parametrize("value", list(range(0, 150)))
def test_integer_roundtrip(db, value):
    assert _roundtrip("i", value) == value


@pytest.mark.parametrize("value", [0, 1, -1, 2**31, -(2**31), 2**53, -(2**53), 9999999999])
def test_bigint_roundtrip(db, value):
    assert _roundtrip("big", value) == value


@pytest.mark.parametrize("value", list(range(-32768, 32768, 517)))
def test_smallint_roundtrip(db, value):
    assert _roundtrip("small", value) == value


@pytest.mark.parametrize("value", [0.0, 1.5, -2.25, 3.141592653589793, 1e10, -1e-10, 100.001])
def test_float_roundtrip(db, value):
    assert _roundtrip("f", value) == pytest.approx(value)


@pytest.mark.parametrize("value", [Decimal("0"), Decimal("1.5"), Decimal("-9.9999"),
                                   Decimal("12345.6789"), Decimal("0.0001"), Decimal("99999999.9999")])
def test_decimal_roundtrip(db, value):
    assert _roundtrip("dec", value) == value


@pytest.mark.parametrize("value", [
    "", "a", "hello world", "unicode: héllo", "emoji 🚀", "quote ' \" ",
    "line\nbreak", "tab\tchar", "50% _off", "null\x00byte", "  spaces  ",
    "<script>alert(1)</script>", "'; DROP TABLE box; --", "русский текст",
    "x" * 200,
])
def test_char_roundtrip(db, value):
    assert _roundtrip("s", value) == value


@pytest.mark.parametrize("value", ["short", "long " * 1000, "多字节文本" * 50, ""])
def test_text_roundtrip(db, value):
    assert _roundtrip("t", value) == value


@pytest.mark.parametrize("value", [True, False])
def test_bool_roundtrip(db, value):
    assert _roundtrip("b", value) is value


@pytest.mark.parametrize("_", list(range(30)))
def test_uuid_roundtrip(db, _):
    value = uuid.uuid4()
    got = _roundtrip("u", value)
    assert isinstance(got, uuid.UUID) and got == value


@pytest.mark.parametrize("value", [
    {}, {"a": 1}, {"nested": {"x": [1, 2, 3]}}, [1, 2, 3], {"unicode": "héllo"},
    {"bool": True, "null": None, "float": 1.5}, list(range(20)),
    {"deep": {"deeper": {"deepest": {"v": "x"}}}},
])
def test_json_roundtrip(db, value):
    assert _roundtrip("j", value) == value


@pytest.mark.parametrize("value", [b"", b"\x00\x01\x02", b"binary" * 100, bytes(range(256))])
def test_binary_roundtrip(db, value):
    assert bytes(_roundtrip("blob", value)) == value


@pytest.mark.parametrize("value", [
    datetime.datetime(2020, 1, 1, 12, 30, 45),
    datetime.datetime(1999, 12, 31, 23, 59, 59),
    datetime.datetime(2026, 7, 3, 0, 0, 0),
])
def test_datetime_roundtrip(db, value):
    assert _roundtrip("when", value) == value


@pytest.mark.parametrize("value", [datetime.date(2020, 1, 1), datetime.date(2026, 7, 3), datetime.date(1970, 1, 1)])
def test_date_roundtrip(db, value):
    assert _roundtrip("day", value) == value


@pytest.mark.parametrize("value", [datetime.time(0, 0), datetime.time(12, 30, 45), datetime.time(23, 59, 59)])
def test_time_roundtrip(db, value):
    assert _roundtrip("clock", value) == value


@pytest.mark.parametrize("seconds", [0, 1, 60, 3600, 86400, 90, 123456])
def test_duration_roundtrip(db, seconds):
    value = datetime.timedelta(seconds=seconds)
    assert _roundtrip("dur", value) == value
