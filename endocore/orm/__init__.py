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
from endocore.orm.connection import aatomic, atomic, close_all, configure, connect, get_connection
from endocore.orm.exceptions import (
    ConfigurationError,
    DoesNotExist,
    FieldError,
    MultipleObjectsReturned,
    ORMError,
    PoolTimeoutError,
    UnsafeIdentifierError,
)
from endocore.orm.expressions import Avg, Count, F, Max, Min, Sum
from endocore.orm.migrations import Migrator
from endocore.orm.model import Model, get_models
from endocore.orm.query import Q, QuerySet
from endocore.orm.schema import create_all, create_table, create_through_tables, drop_table
from endocore.orm.storage import (
    EncryptedFileSystemStorage,
    StorageError,
    configure_storage,
    generate_key,
    get_storage,
)
from endocore.orm.validators import ValidationError

__all__ = [
    "Model",
    "fields",
    "Q",
    "QuerySet",
    "F",
    "Count",
    "Sum",
    "Avg",
    "Min",
    "Max",
    "ValidationError",
    "configure_storage",
    "get_storage",
    "generate_key",
    "EncryptedFileSystemStorage",
    "StorageError",
    "configure",
    "connect",
    "get_connection",
    "aatomic",
    "atomic",
    "close_all",
    "create_all",
    "create_table",
    "create_through_tables",
    "drop_table",
    "get_models",
    "Migrator",
    "ORMError",
    "ConfigurationError",
    "UnsafeIdentifierError",
    "FieldError",
    "DoesNotExist",
    "MultipleObjectsReturned",
    "PoolTimeoutError",
]
