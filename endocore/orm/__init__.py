"""EndoCore ORM — a small, secure, Django-flavoured ORM for SQLite & PostgreSQL.

    from endocore.orm import Model, fields, configure, create_all

    class User(Model):
        name = fields.CharField(max_length=100)
        age = fields.IntegerField(default=0)

    configure(backend="sqlite", database=":memory:")
    create_all(User)
    User.objects.create(name="Ada", age=36)
    User.objects.filter(age__gte=18).order_by("name")

Security: every value is bound by the driver (never string-formatted into SQL),
identifiers are validated and quoted, and only whitelisted lookups produce SQL.
"""

from __future__ import annotations

from endocore.orm import fields
from endocore.orm.connection import atomic, close_all, configure, connect, get_connection
from endocore.orm.exceptions import (
    ConfigurationError,
    DoesNotExist,
    FieldError,
    MultipleObjectsReturned,
    ORMError,
    UnsafeIdentifierError,
)
from endocore.orm.model import Model
from endocore.orm.query import Q, QuerySet
from endocore.orm.schema import create_all, create_table, drop_table

__all__ = [
    "Model",
    "fields",
    "Q",
    "QuerySet",
    "configure",
    "connect",
    "get_connection",
    "atomic",
    "close_all",
    "create_all",
    "create_table",
    "drop_table",
    "ORMError",
    "ConfigurationError",
    "UnsafeIdentifierError",
    "FieldError",
    "DoesNotExist",
    "MultipleObjectsReturned",
]
