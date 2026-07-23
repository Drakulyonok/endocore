"""Security invariants — the whole point of this beta.

These tests assert that hostile input cannot escape parameter binding and that
identifiers are validated before any SQL is built.
"""

from __future__ import annotations

import pytest

from endocore.orm import Model, fields, Q, configure, create_all
from endocore.orm.backends import SQLiteBackend
from endocore.orm.backends.base import BaseBackend
from endocore.orm.compiler import SQLCompiler
from endocore.orm.connection import get_connection
from endocore.orm.exceptions import FieldError, UnsafeIdentifierError


class Account(Model):
    class Meta:
        table = "account"

    name = fields.CharField(max_length=50)


META = Account._meta
COLS = [f.column for f in META.fields]


# -- values never reach the SQL string --------------------------------------

def test_injection_value_is_parameterized():
    evil = "x'; DROP TABLE account; --"
    sql, params = SQLCompiler(SQLiteBackend()).select(
        META, wheres=[Q(name=evil)], order_by=[], limit=None, offset=0, columns=COLS
    )
    # The payload is a bound parameter, not part of the SQL text.
    assert evil not in sql
    assert "DROP TABLE" not in sql
    assert params == [evil]
    assert sql.count("?") == 1


# -- identifiers are validated before quoting -------------------------------

@pytest.mark.parametrize("bad", [
    "name; DROP TABLE account",
    'a"b',
    "1abc",
    "col-name",
    "",
    "spaces here",
])
def test_bad_identifiers_rejected(bad):
    with pytest.raises(UnsafeIdentifierError):
        SQLiteBackend().quote(bad)


def test_good_identifier_quoted():
    assert SQLiteBackend().quote("user_name") == '"user_name"'


def test_unknown_field_is_field_error_not_injection():
    # A crafted "field name" never becomes raw SQL; it fails as a missing field.
    with pytest.raises(FieldError):
        SQLCompiler(SQLiteBackend()).select(
            META, wheres=[Q(**{"name; DROP": 1})], order_by=[], limit=None, offset=0, columns=COLS
        )


# -- LIMIT/OFFSET must be integers ------------------------------------------

@pytest.mark.parametrize("bad", ["5; DROP", "10", 3.5, True, -1])
def test_limit_must_be_int(bad):
    with pytest.raises(ValueError):
        SQLiteBackend().as_limit(bad)


# -- LIKE wildcards in user input are escaped -------------------------------

def test_like_escaping():
    b = SQLiteBackend()
    assert b.like_escape("50%_off") == "50\\%\\_off"

    sql, params = SQLCompiler(b)._leaf(META, "name__contains", "50%_off")
    assert "ESCAPE '\\'" in sql
    assert params == ["%50\\%\\_off%"]  # wildcards neutralized, wrapped for contains


def test_icontains_lowercases_param():
    sql, params = SQLCompiler(SQLiteBackend())._leaf(META, "name__icontains", "ADMIN")
    assert "LOWER(" in sql
    assert params == ["%admin%"]


# -- placeholder count for IN --------------------------------------------------

def test_empty_in_is_safe_constant():
    sql, params = SQLCompiler(SQLiteBackend())._leaf(META, "name__in", [])
    assert sql == "1 = 0"
    assert params == []


# -- __repr__ doesn't leak secret-looking fields ----------------------------


def test_repr_masks_sensitive_field_values():
    configure(backend="sqlite", database=":memory:")

    class User(Model):
        password_hash = fields.CharField(max_length=200)
        email = fields.CharField(max_length=100)

    create_all(User)
    user = User.objects.create(password_hash="scrypt$16384$8$1$salt$hash", email="a@b.com")
    text = repr(user)
    assert "scrypt" not in text
    assert "password_hash='***'" in text
    get_connection().close()


def test_repr_shows_normal_field_values():
    configure(backend="sqlite", database=":memory:")

    class Widget(Model):
        name = fields.CharField(max_length=100)

    create_all(Widget)
    widget = Widget.objects.create(name="gizmo")
    assert repr(widget) == "<Widget id=1 name='gizmo'>"
    get_connection().close()
