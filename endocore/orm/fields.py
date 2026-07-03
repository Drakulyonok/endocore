"""Field types — the declarative description of a column.

A field knows its column type (via the backend), its default, how to adapt
values between Python and the database (``to_db`` / ``to_python``), and how to
validate a value on the write path (``validate``). Fields never build SQL and
never see user-controlled identifiers.
"""

from __future__ import annotations

import datetime
import json
import uuid
from decimal import Decimal
from typing import Any, Callable, Sequence

from endocore.orm.exceptions import FieldError
from endocore.orm import validators as v
from endocore.orm.validators import ValidationError


class _Unset:
    """Sentinel distinguishing "no default" from ``default=None``."""

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return "UNSET"


UNSET = _Unset()


class Field:
    """Base field. Subclasses set ``internal_type`` used by backends for DDL."""

    internal_type = "Field"
    auto_increment = False
    _creation_counter = 0

    def __init__(
        self,
        *,
        primary_key: bool = False,
        null: bool = False,
        default: Any = UNSET,
        unique: bool = False,
        db_column: str | None = None,
        db_index: bool = False,
        choices: Sequence | None = None,
        validators: Sequence[Callable[[Any], None]] | None = None,
    ) -> None:
        self.primary_key = primary_key
        self.null = null
        self.default = default
        self.unique = unique
        self.db_column = db_column
        self.db_index = db_index
        self.choices = list(choices) if choices else None
        self.validators = list(validators) if validators else []

        self._order = Field._creation_counter
        Field._creation_counter += 1

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

    # -- validation (write path only) ------------------------------------

    def validate(self, value: Any) -> None:
        """Raise ``ValidationError`` if ``value`` is not storable in this field."""
        if value is None:
            if self.null or self.primary_key:
                return
            raise ValidationError(f"{self.name!r} cannot be null")
        if self.choices is not None:
            allowed = {c[0] if isinstance(c, (tuple, list)) else c for c in self.choices}
            if value not in allowed:
                raise ValidationError(f"{self.name!r}: {value!r} is not a valid choice")
        self._validate(value)
        for validator in self.validators:
            validator(value)

    def _validate(self, value: Any) -> None:
        """Type-specific validation hook."""

    def pre_save(self, instance) -> None:
        """Hook run before a row is written. FileField writes its file here."""


# -- integers ---------------------------------------------------------------

class IntegerField(Field):
    internal_type = "IntegerField"
    _min: int | None = None
    _max: int | None = None

    def to_python(self, value: Any) -> Any:
        return None if value is None else int(value)

    def _validate(self, value: Any) -> None:
        try:
            ivalue = int(value)
        except (TypeError, ValueError):
            raise ValidationError(f"{self.name!r}: {value!r} is not an integer") from None
        if self._min is not None and ivalue < self._min:
            raise ValidationError(f"{self.name!r}: must be >= {self._min}")
        if self._max is not None and ivalue > self._max:
            raise ValidationError(f"{self.name!r}: must be <= {self._max}")


class SmallIntegerField(IntegerField):
    internal_type = "SmallIntegerField"
    _min, _max = -32768, 32767


class BigIntegerField(IntegerField):
    internal_type = "BigIntegerField"


class PositiveSmallIntegerField(IntegerField):
    internal_type = "SmallIntegerField"
    _min, _max = 0, 32767


class PositiveIntegerField(IntegerField):
    internal_type = "IntegerField"
    _min = 0


class PositiveBigIntegerField(IntegerField):
    internal_type = "BigIntegerField"
    _min = 0


class AutoField(IntegerField):
    """Auto-incrementing integer primary key."""

    internal_type = "AutoField"
    auto_increment = True

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("primary_key", True)
        super().__init__(**kwargs)


class BigAutoField(AutoField):
    internal_type = "BigAutoField"


# -- floats / decimals ------------------------------------------------------

class FloatField(Field):
    internal_type = "FloatField"

    def to_python(self, value: Any) -> Any:
        return None if value is None else float(value)

    def _validate(self, value: Any) -> None:
        try:
            float(value)
        except (TypeError, ValueError):
            raise ValidationError(f"{self.name!r}: {value!r} is not a float") from None


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
        return str(dec) if backend.name == "sqlite" else dec

    def to_python(self, value: Any) -> Any:
        return None if value is None else Decimal(str(value))


# -- boolean ----------------------------------------------------------------

class BooleanField(Field):
    internal_type = "BooleanField"

    def to_db(self, value: Any, backend) -> Any:
        if value is None:
            return None
        return bool(value) if backend.name == "postgres" else int(bool(value))

    def to_python(self, value: Any) -> Any:
        return None if value is None else bool(value)


# -- text -------------------------------------------------------------------

class CharField(Field):
    internal_type = "CharField"

    def __init__(self, *, max_length: int, **kwargs: Any) -> None:
        if not isinstance(max_length, int) or max_length <= 0:
            raise FieldError("CharField requires a positive integer max_length")
        self.max_length = max_length
        super().__init__(**kwargs)

    def to_db(self, value: Any, backend) -> Any:
        return None if value is None else str(value)

    def _validate(self, value: Any) -> None:
        if len(str(value)) > self.max_length:
            raise ValidationError(
                f"{self.name!r}: value exceeds max_length={self.max_length}"
            )


class TextField(Field):
    internal_type = "TextField"

    def to_db(self, value: Any, backend) -> Any:
        return None if value is None else str(value)


class SlugField(CharField):
    def __init__(self, *, max_length: int = 50, **kwargs: Any) -> None:
        super().__init__(max_length=max_length, **kwargs)

    def _validate(self, value: Any) -> None:
        super()._validate(value)
        v.validate_slug(value)


class EmailField(CharField):
    def __init__(self, *, max_length: int = 254, **kwargs: Any) -> None:
        super().__init__(max_length=max_length, **kwargs)

    def _validate(self, value: Any) -> None:
        super()._validate(value)
        v.validate_email(value)


class URLField(CharField):
    def __init__(self, *, max_length: int = 200, **kwargs: Any) -> None:
        super().__init__(max_length=max_length, **kwargs)

    def _validate(self, value: Any) -> None:
        super()._validate(value)
        v.validate_url(value)


class GenericIPAddressField(Field):
    internal_type = "GenericIPAddressField"

    def to_db(self, value: Any, backend) -> Any:
        return None if value is None else str(value)

    def _validate(self, value: Any) -> None:
        v.validate_ip(str(value))


# -- uuid / json / binary ---------------------------------------------------

class UUIDField(Field):
    internal_type = "UUIDField"

    def to_db(self, value: Any, backend) -> Any:
        if value is None:
            return None
        u = value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        return u.hex if backend.name == "sqlite" else str(u)

    def to_python(self, value: Any) -> Any:
        if value is None or isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


class JSONField(Field):
    internal_type = "JSONField"

    def to_db(self, value: Any, backend) -> Any:
        if value is None:
            return None
        if backend.name == "postgres":
            from psycopg.types.json import Jsonb  # lazy: only when Postgres is used

            return Jsonb(value)
        return json.dumps(value)

    def to_python(self, value: Any) -> Any:
        if value is None or isinstance(value, (dict, list)):
            return value
        return json.loads(value)


class BinaryField(Field):
    internal_type = "BinaryField"

    def to_db(self, value: Any, backend) -> Any:
        return None if value is None else bytes(value)

    def to_python(self, value: Any) -> Any:
        if value is None:
            return None
        return bytes(value) if isinstance(value, (memoryview, bytearray)) else value

    def _validate(self, value: Any) -> None:
        if not isinstance(value, (bytes, bytearray, memoryview)):
            raise ValidationError(f"{self.name!r}: expected bytes")


# -- date / time ------------------------------------------------------------

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


class TimeField(Field):
    internal_type = "TimeField"

    def to_db(self, value: Any, backend) -> Any:
        if value is None:
            return None
        if backend.name == "sqlite" and isinstance(value, datetime.time):
            return value.isoformat()
        return value

    def to_python(self, value: Any) -> Any:
        if value is None or isinstance(value, datetime.time):
            return value
        if isinstance(value, str):
            return datetime.time.fromisoformat(value)
        return value


class DurationField(Field):
    """A ``timedelta``, stored portably as an integer number of microseconds."""

    internal_type = "DurationField"

    def to_db(self, value: Any, backend) -> Any:
        if value is None:
            return None
        if isinstance(value, datetime.timedelta):
            return int(value / datetime.timedelta(microseconds=1))
        return int(value)

    def to_python(self, value: Any) -> Any:
        if value is None or isinstance(value, datetime.timedelta):
            return value
        return datetime.timedelta(microseconds=int(value))


# -- files (encrypted at rest) ----------------------------------------------

class FieldFile:
    """Handle to a stored file. Lazily reads/decrypts through the storage.

    A freshly-assigned file is "pending" (bytes in memory) until the instance is
    saved; a file loaded from the database is "committed" (only its key is held,
    content read on demand).
    """

    def __init__(self, field: "FileField", *, name: str | None = None,
                 pending: bytes | None = None, committed: bool = False) -> None:
        self.field = field
        self.name = name              # stored relative key (in the DB column)
        self._pending = pending       # not-yet-saved bytes
        self._committed = committed

    @property
    def storage(self):
        return self.field.get_storage()

    def read(self) -> bytes:
        if self._pending is not None and not self._committed:
            return bytes(self._pending)
        if self.name is None:
            raise ValueError("file has no content")
        return self.storage.open(self.name)

    def open(self):
        import io

        return io.BytesIO(self.read())

    def size(self) -> int:
        if self._pending is not None and not self._committed:
            return len(self._pending)
        return self.storage.size(self.name)

    def delete(self) -> None:
        if self.name:
            self.storage.delete(self.name)
        self.name = None
        self._pending = None
        self._committed = False

    def __bool__(self) -> bool:
        return self.name is not None or self._pending is not None

    def __str__(self) -> str:
        return self.name or ""

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"<FieldFile {self.name or '(pending)'}>"


class FileDescriptor:
    """Turns assigned bytes/file-like/str into a :class:`FieldFile` on the instance."""

    def __init__(self, field: "FileField") -> None:
        self.field = field

    def __set__(self, instance, value) -> None:
        if value is None or isinstance(value, FieldFile):
            instance.__dict__[self.field.name] = value
        elif isinstance(value, (bytes, bytearray)):
            instance.__dict__[self.field.name] = FieldFile(self.field, pending=bytes(value))
        elif hasattr(value, "read"):
            instance.__dict__[self.field.name] = FieldFile(self.field, pending=value.read())
        elif isinstance(value, str):
            # An existing stored key (e.g. loaded from the database).
            instance.__dict__[self.field.name] = FieldFile(self.field, name=value, committed=True)
        else:
            raise FieldError(f"cannot assign {type(value).__name__} to FileField {self.field.name!r}")

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        return instance.__dict__.get(self.field.name)


class FileField(Field):
    """Stores a file **encrypted at rest** via the configured storage.

    The database column holds only an opaque key (the encrypted file's relative
    path). Assign ``bytes`` or a file-like object; read via ``instance.field.read()``.
    """

    internal_type = "FileField"

    def __init__(self, *, upload_to: str = "", storage=None, **kwargs: Any) -> None:
        self.upload_to = upload_to
        self._storage = storage
        super().__init__(**kwargs)

    def get_storage(self):
        if self._storage is not None:
            return self._storage
        from endocore.orm.storage import get_storage

        return get_storage()

    def to_db(self, value: Any, backend) -> Any:
        if value is None:
            return None
        if isinstance(value, FieldFile):
            return value.name
        if isinstance(value, str):
            return value
        raise FieldError("FileField value must be saved (call obj.save()) before writing")

    def to_python(self, value: Any) -> Any:
        return value  # the stored key; the descriptor wraps it into a FieldFile

    def pre_save(self, instance) -> None:
        value = instance.__dict__.get(self.name)
        if isinstance(value, FieldFile) and not value._committed and value._pending is not None:
            key = self.get_storage().save(self.upload_to, value._pending)
            instance.__dict__[self.name] = FieldFile(self, name=key, committed=True)


# -- relations --------------------------------------------------------------

#: Referential actions -> the SQL emitted in ``ON DELETE``. PROTECT has no pure
#: SQL equivalent, so it maps to RESTRICT (the DB refuses the delete).
_ON_DELETE = {
    "CASCADE": "CASCADE",
    "SET NULL": "SET NULL",
    "SET_NULL": "SET NULL",
    "RESTRICT": "RESTRICT",
    "PROTECT": "RESTRICT",
    "NO ACTION": "NO ACTION",
    "DO_NOTHING": "NO ACTION",
}


class ForeignKey(Field):
    """A reference to another model, stored as ``<name>_id``."""

    internal_type = "ForeignKey"

    def __init__(self, to, *, on_delete: str = "CASCADE", **kwargs: Any) -> None:
        self.to = to
        key = on_delete.upper()
        if key not in _ON_DELETE:
            raise FieldError(
                f"invalid on_delete {on_delete!r}; use one of "
                f"{', '.join(sorted(set(_ON_DELETE)))}"
            )
        self.on_delete = key
        super().__init__(**kwargs)

    def on_delete_sql(self) -> str:
        return _ON_DELETE[self.on_delete]

    def bind(self, name: str, model) -> None:
        super().bind(name, model)
        if self.db_column == name:  # default column is "<name>_id"
            self.db_column = f"{name}_id"

    @property
    def id_attr_name(self) -> str:
        return f"{self.name}_id"

    def to_python(self, value: Any) -> Any:
        return None if value is None else int(value)


class OneToOneField(ForeignKey):
    """A ForeignKey constrained to be unique — a one-to-one relation."""

    def __init__(self, to, *, on_delete: str = "CASCADE", **kwargs: Any) -> None:
        kwargs.setdefault("unique", True)
        super().__init__(to, on_delete=on_delete, **kwargs)


class ManyToManyField(Field):
    """A many-to-many relation stored in an auto-created through table.

    Not a column on the model. Access via a manager: ``obj.tags.add(...)``,
    ``obj.tags.all()``, ``.remove()``, ``.set([...])``, ``.clear()``.
    """

    internal_type = "ManyToManyField"

    def __init__(self, to, *, through: str | None = None, **kwargs: Any) -> None:
        self.to = to
        self.through = through
        super().__init__(**kwargs)

    def through_table(self) -> str:
        return self.through or f"{self.model._meta.table}_{self.name}"

    def source_column(self) -> str:
        return f"{self.model._meta.table}_id"

    def target_column(self) -> str:
        return f"{self.to._meta.table}_id"


class ManyRelatedManager:
    """Manages one instance's side of a many-to-many relation."""

    def __init__(self, field: ManyToManyField, instance) -> None:
        self.field = field
        self.instance = instance
        self.to = field.to

    def _conn(self):
        from endocore.orm.connection import get_connection

        return get_connection(self.to._meta.using)

    def _backend(self):
        return self._conn().backend

    def _target_ids(self) -> list:
        b = self._backend()
        table, src, tgt = (
            b.quote(self.field.through_table()),
            b.quote(self.field.source_column()),
            b.quote(self.field.target_column()),
        )
        sql = f"SELECT {tgt} FROM {table} WHERE {src} = {b.placeholder}"
        rows = self._conn().execute(sql, [self.instance.pk]).fetchall()
        return [r[0] for r in rows]

    def all(self) -> list:
        cached = getattr(self.instance, f"_m2m_{self.field.name}", None)
        if cached is not None:
            return cached
        ids = self._target_ids()
        return list(self.to.objects.filter(pk__in=ids)) if ids else []

    def count(self) -> int:
        return len(self._target_ids())

    def add(self, *objects) -> None:
        b = self._backend()
        table, src, tgt = (
            b.quote(self.field.through_table()),
            b.quote(self.field.source_column()),
            b.quote(self.field.target_column()),
        )
        existing = set(self._target_ids())
        conn = self._conn()
        with conn.atomic():
            for obj in objects:
                target_pk = obj.pk if hasattr(obj, "pk") else obj
                if target_pk in existing:
                    continue
                sql = (
                    f"INSERT INTO {table} ({src}, {tgt}) "
                    f"VALUES ({b.placeholder}, {b.placeholder})"
                )
                conn.execute(sql, [self.instance.pk, target_pk], write=True)
                existing.add(target_pk)

    def remove(self, *objects) -> None:
        b = self._backend()
        table, src, tgt = (
            b.quote(self.field.through_table()),
            b.quote(self.field.source_column()),
            b.quote(self.field.target_column()),
        )
        ids = [obj.pk if hasattr(obj, "pk") else obj for obj in objects]
        if not ids:
            return
        placeholders = b.placeholders(len(ids))
        sql = f"DELETE FROM {table} WHERE {src} = {b.placeholder} AND {tgt} IN ({placeholders})"
        self._conn().execute(sql, [self.instance.pk, *ids], write=True)

    def clear(self) -> None:
        b = self._backend()
        table, src = b.quote(self.field.through_table()), b.quote(self.field.source_column())
        sql = f"DELETE FROM {table} WHERE {src} = {b.placeholder}"
        self._conn().execute(sql, [self.instance.pk], write=True)

    def set(self, objects) -> None:
        self.clear()
        self.add(*objects)


class ManyRelatedDescriptor:
    def __init__(self, field: ManyToManyField) -> None:
        self.field = field

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        return ManyRelatedManager(self.field, instance)
