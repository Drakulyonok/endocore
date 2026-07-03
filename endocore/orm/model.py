"""Declarative models: metaclass, ``_meta``, instances, ``save``/``delete``."""

from __future__ import annotations

import datetime
from typing import Any

from endocore.orm.exceptions import DoesNotExist, FieldError, MultipleObjectsReturned
from endocore.orm.fields import AutoField, DateTimeField, Field, ForeignKey


class Options:
    """Resolved metadata for a model (its ``_meta``)."""

    def __init__(self, model, table: str, fields: list[Field]) -> None:
        self.model = model
        self.table = table
        self.fields = fields
        self.fields_by_name = {f.name: f for f in fields}
        self.pk = next((f for f in fields if f.primary_key), None)
        self.using = "default"

    def get_field(self, name: str) -> Field:
        try:
            return self.fields_by_name[name]
        except KeyError:
            raise FieldError(
                f"{self.model.__name__} has no field {name!r}"
            ) from None


class ForeignObjectDescriptor:
    """Lazily loads a related object from the stored ``<name>_id`` value."""

    def __init__(self, field: ForeignKey) -> None:
        self.field = field
        self.cache_attr = f"_{field.name}_cache"
        self.id_attr = f"{field.name}_id"

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        if hasattr(instance, self.cache_attr):
            return getattr(instance, self.cache_attr)
        related_id = getattr(instance, self.id_attr, None)
        related = None if related_id is None else self.field.to.objects.get(pk=related_id)
        setattr(instance, self.cache_attr, related)
        return related

    def __set__(self, instance, value) -> None:
        if value is None:
            setattr(instance, self.id_attr, None)
        elif isinstance(value, self.field.to):
            setattr(instance, self.id_attr, value.pk)
        else:
            setattr(instance, self.id_attr, int(value))
        # Drop any stale cached object.
        instance.__dict__.pop(self.cache_attr, None)


class ModelBase(type):
    """Collects fields into ``_meta`` and wires the manager."""

    def __new__(mcls, name, bases, namespace):
        # The base Model class itself has no fields/meta.
        parents = [b for b in bases if isinstance(b, ModelBase)]
        if not parents:
            return super().__new__(mcls, name, bases, namespace)

        meta = namespace.pop("Meta", None)

        fields: list[Field] = []
        for attr, value in list(namespace.items()):
            if isinstance(value, Field):
                fields.append(value)
                namespace.pop(attr)
                value._pending_name = attr  # remember declared name

        # Ensure a primary key exists.
        if not any(f.primary_key for f in fields):
            pk = AutoField()
            pk._pending_name = "id"
            fields.insert(0, pk)

        fields.sort(key=lambda f: (not f.primary_key, f._order))

        cls = super().__new__(mcls, name, bases, namespace)

        for field in fields:
            field.bind(field._pending_name, cls)
            if isinstance(field, ForeignKey):
                setattr(cls, field.name, ForeignObjectDescriptor(field))

        table = getattr(meta, "table", None) or name.lower()
        cls._meta = Options(cls, table, fields)

        # Per-model exception subclasses (like Django).
        cls.DoesNotExist = type("DoesNotExist", (DoesNotExist,), {})
        cls.MultipleObjectsReturned = type(
            "MultipleObjectsReturned", (MultipleObjectsReturned,), {}
        )

        # Attach the manager lazily to avoid an import cycle.
        from endocore.orm.manager import Manager

        cls.objects = Manager()
        cls.objects.contribute_to_class(cls)
        return cls


class Model(metaclass=ModelBase):
    """Base class for all models."""

    _meta: Options

    def __init__(self, **kwargs: Any) -> None:
        for field in self._meta.fields:
            if isinstance(field, ForeignKey):
                if field.name in kwargs:
                    setattr(self, field.name, kwargs.pop(field.name))
                elif field.id_attr_name in kwargs:
                    setattr(self, field.id_attr_name, kwargs.pop(field.id_attr_name))
                else:
                    setattr(self, field.id_attr_name, field.get_default())
            else:
                if field.name in kwargs:
                    setattr(self, field.name, kwargs.pop(field.name))
                else:
                    setattr(self, field.name, field.get_default())

        if kwargs:
            raise FieldError(
                f"{type(self).__name__} got unexpected field(s): {', '.join(kwargs)}"
            )

    # -- identity ---------------------------------------------------------

    @property
    def pk(self) -> Any:
        return getattr(self, self._meta.pk.name)

    @pk.setter
    def pk(self, value: Any) -> None:
        setattr(self, self._meta.pk.name, value)

    def __repr__(self) -> str:
        return f"<{type(self).__name__}: pk={self.pk!r}>"

    def __eq__(self, other: object) -> bool:
        return (
            type(self) is type(other)
            and self.pk is not None
            and self.pk == other.pk  # type: ignore[attr-defined]
        )

    def __hash__(self) -> int:
        return hash((type(self).__name__, self.pk))

    # -- row value access -------------------------------------------------

    def _value_of(self, field: Field) -> Any:
        attr = field.id_attr_name if isinstance(field, ForeignKey) else field.name
        return getattr(self, attr, None)

    def _apply_auto_now(self, *, adding: bool) -> None:
        now = datetime.datetime.now()
        for field in self._meta.fields:
            if isinstance(field, DateTimeField) and (
                field.auto_now or (field.auto_now_add and adding)
            ):
                setattr(self, field.name, now)

    # -- persistence ------------------------------------------------------

    def save(self) -> "Model":
        from endocore.orm.manager import get_queryset

        adding = self.pk is None
        self._apply_auto_now(adding=adding)
        qs = get_queryset(type(self))
        if adding:
            new_pk = qs._insert_instance(self)
            self.pk = new_pk
        else:
            qs._update_instance(self)
        return self

    def delete(self) -> None:
        from endocore.orm.manager import get_queryset

        if self.pk is None:
            raise FieldError("cannot delete an unsaved instance (pk is None)")
        get_queryset(type(self)).filter(pk=self.pk).delete()
        self.pk = None
