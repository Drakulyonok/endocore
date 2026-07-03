"""Field types — the declarative description of a column.

A field knows its column type (via the backend), its default, and how to adapt
values between Python and the database (``to_db`` / ``to_python``). Fields never
build SQL and never see user-controlled identifiers.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any

from endocore.orm.exceptions import FieldError


class _Unset:
    """Sentinel distinguishing "no default" from ``default=None``."""

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return "UNSET"


UNSET = _Unset()


class Field:
    """Base field. Subclasses set ``internal_type`` used by backends for DDL."""

    internal_type = "Field"
    _creation_counter = 0

    def __init__(
        self,
        *,
        primary_key: bool = False,
        null: bool = False,
        default: Any = UNSET,
        unique: bool = False,
        db_column: str | None = None,
    ) -> None:
        self.primary_key = primary_key
        self.null = null
        self.default = default
        self.unique = unique
        self.db_column = db_column

        # Preserve declaration order across a class body (like Django).
        self._order = Field._creation_counter
        Field._creation_counter += 1

        # Filled in by the model metaclass.
        self.name: str = ""
        self.model = None

    def bind(self, name: str, model) -> None:
        self.name = name
        self.model = model
        if self.db_column is None:
            self.db_column = name

    @property
    def column(self) -> str:
        return self.db_column or self.name

    def has_default(self) -> bool:
        return self.default is not UNSET

    def get_default(self) -> Any:
        if callable(self.default):
            return self.default()
        return None if self.default is UNSET else self.default

    # -- value adaptation -------------------------------------------------

    def to_db(self, value: Any, backend) -> Any:
        """Adapt a Python value to a driver-bindable value."""
        return value

    def to_python(self, value: Any) -> Any:
        """Adapt a value coming back from the driver to Python."""
        return value


class AutoField(Field):
    """Auto-incrementing integer primary key."""

    internal_type = "AutoField"

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("primary_key", True)
        super().__init__(**kwargs)

    def to_python(self, value: Any) -> Any:
        return None if value is None else int(value)


class IntegerField(Field):
    internal_type = "IntegerField"

    def to_python(self, value: Any) -> Any:
        return None if value is None else int(value)


class BigIntegerField(IntegerField):
    internal_type = "BigIntegerField"


class CharField(Field):
    internal_type = "CharField"

    def __init__(self, *, max_length: int, **kwargs: Any) -> None:
        if not isinstance(max_length, int) or max_length <= 0:
            raise FieldError("CharField requires a positive integer max_length")
        self.max_length = max_length
        super().__init__(**kwargs)

    def to_db(self, value: Any, backend) -> Any:
        if value is None:
            return None
        text = str(value)
        if len(text) > self.max_length:
            raise FieldError(
                f"{self.name!r}: value exceeds max_length={self.max_length}"
            )
        return text


class TextField(Field):
    internal_type = "TextField"


class BooleanField(Field):
    internal_type = "BooleanField"

    def to_db(self, value: Any, backend) -> Any:
        if value is None:
            return None
        # SQLite has no native bool; store 0/1. Postgres takes a real bool.
        return bool(value) if backend.name == "postgres" else int(bool(value))

    def to_python(self, value: Any) -> Any:
        return None if value is None else bool(value)


class FloatField(Field):
    internal_type = "FloatField"

    def to_python(self, value: Any) -> Any:
        return None if value is None else float(value)


class DecimalField(Field):
    internal_type = "DecimalField"

    def __init__(self, *, max_digits: int, decimal_places: int, **kwargs: Any) -> None:
        self.max_digits = max_digits
        self.decimal_places = decimal_places
        super().__init__(**kwargs)

    def to_db(self, value: Any, backend) -> Any:
        if value is None:
            return None
        dec = value if isinstance(value, Decimal) else Decimal(str(value))
        # SQLite has no DECIMAL affinity; store as text to preserve precision.
        return str(dec) if backend.name == "sqlite" else dec

    def to_python(self, value: Any) -> Any:
        return None if value is None else Decimal(str(value))


class DateTimeField(Field):
    internal_type = "DateTimeField"

    def __init__(self, *, auto_now: bool = False, auto_now_add: bool = False, **kwargs: Any) -> None:
        self.auto_now = auto_now
        self.auto_now_add = auto_now_add
        super().__init__(**kwargs)

    def to_db(self, value: Any, backend) -> Any:
        if value is None:
            return None
        if backend.name == "sqlite" and isinstance(value, (datetime.datetime, datetime.date)):
            return value.isoformat(sep=" ")
        return value

    def to_python(self, value: Any) -> Any:
        if value is None or isinstance(value, datetime.datetime):
            return value
        if isinstance(value, str):
            return datetime.datetime.fromisoformat(value)
        return value


class DateField(Field):
    internal_type = "DateField"

    def to_db(self, value: Any, backend) -> Any:
        if value is None:
            return None
        if backend.name == "sqlite" and isinstance(value, datetime.date):
            return value.isoformat()
        return value

    def to_python(self, value: Any) -> Any:
        if value is None or isinstance(value, datetime.date):
            return value
        if isinstance(value, str):
            return datetime.date.fromisoformat(value)
        return value


class ForeignKey(Field):
    """A reference to another model, stored as ``<name>_id``.

    Cross-table lookups (``author__name=...``) are not part of this beta; a
    ForeignKey stores/loads the related pk and lazily fetches the object.
    """

    internal_type = "ForeignKey"

    def __init__(self, to, *, on_delete: str = "CASCADE", **kwargs: Any) -> None:
        self.to = to
        self.on_delete = on_delete
        super().__init__(**kwargs)

    def bind(self, name: str, model) -> None:
        super().bind(name, model)
        if self.db_column == name:  # default column is "<name>_id"
            self.db_column = f"{name}_id"

    @property
    def id_attr_name(self) -> str:
        """Instance attribute holding the raw related pk (``<name>_id``)."""
        return f"{self.name}_id"

    def to_python(self, value: Any) -> Any:
        return None if value is None else int(value)
