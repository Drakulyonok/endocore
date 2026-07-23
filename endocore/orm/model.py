"""Declarative models: metaclass, ``_meta``, instances, ``save``/``delete``.

Supports abstract base models (``class Meta: abstract = True``) whose fields are
inherited by subclasses — handy for shared columns like created/updated.
"""

from __future__ import annotations

import asyncio
import copy
import datetime
from typing import Any, Iterable

from endocore.orm.exceptions import DoesNotExist, FieldError, MultipleObjectsReturned
from endocore.orm.fields import (
    AutoField,
    DateTimeField,
    Field,
    FileDescriptor,
    FileField,
    ForeignKey,
    ManyRelatedDescriptor,
    ManyToManyField,
    OneToOneField,
)

#: All concrete (non-abstract) models, in definition order — used by migrations.
_MODEL_REGISTRY: list = []

#: Field-name substrings masked in __repr__ (password_hash, api_key, ...) —
#: same idea as the log masking in endocore.core.logging, kept local since
#: the ORM has no dependency on that package.
_SENSITIVE_FIELD_HINTS = ("password", "passwd", "secret", "token", "api_key", "apikey")


def get_models() -> list:
    """Every concrete model defined so far (order of definition)."""
    return list(_MODEL_REGISTRY)


def _normalize_together(value) -> list[tuple[str, ...]]:
    """Accept ``('a','b')`` or ``(('a','b'), ('c',))`` -> list of tuples."""
    if not value:
        return []
    if all(isinstance(item, str) for item in value):
        return [tuple(value)]
    return [tuple(item) for item in value]


class Options:
    """Resolved metadata for a model (its ``_meta``)."""

    def __init__(self, model, table: str, fields: list[Field], *, abstract: bool = False,
                 ordering: Iterable[str] = (), unique_together=(), indexes=(),
                 many_to_many=()) -> None:
        self.model = model
        self.table = table
        self.fields = fields
        self.fields_by_name = {f.name: f for f in fields}
        self.pk = next((f for f in fields if f.primary_key), None)
        self.using = "default"
        self.abstract = abstract
        self.ordering = list(ordering or ())
        self.unique_together = _normalize_together(unique_together)
        self.indexes = [list(ix) for ix in (indexes or ())]
        self.many_to_many = list(many_to_many or ())
        #: reverse relation name -> (source_model, fk_field)
        self.reverse_relations: dict = {}

    def get_field(self, name: str) -> Field:
        try:
            return self.fields_by_name[name]
        except KeyError:
            # Django-style attname access: ``filter(user_id=5)`` for FK ``user``.
            field = self.fields_by_attname.get(name)
            if field is not None:
                return field
            raise FieldError(f"{self.model.__name__} has no field {name!r}") from None

    @property
    def fields_by_attname(self) -> dict:
        cached = self.__dict__.get("_fields_by_attname")
        if cached is None:
            cached = {
                f.id_attr_name: f for f in self.fields if isinstance(f, ForeignKey)
            }
            self.__dict__["_fields_by_attname"] = cached
        return cached


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
            # Coerce a raw pk through the related model's pk field so FKs to
            # non-integer primary keys (e.g. UUIDField) round-trip correctly.
            setattr(instance, self.id_attr, self.field.to._meta.pk.to_python(value))
        instance.__dict__.pop(self.cache_attr, None)


class ReverseManyToOneDescriptor:
    """``author.book_set`` -> a QuerySet of the related-many side of a FK."""

    def __init__(self, source_model, field) -> None:
        self.source_model = source_model
        self.field = field
        self.cache_attr = f"_prefetch_cache_{field.reverse_name()}"

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        cached = instance.__dict__.get(self.cache_attr)
        if cached is not None:
            return cached
        return self.source_model.objects.filter(**{self.field.name: instance})


class ReverseOneToOneDescriptor:
    """``author.profile`` -> the single related object of a OneToOneField (or None)."""

    def __init__(self, source_model, field) -> None:
        self.source_model = source_model
        self.field = field

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        try:
            return self.source_model.objects.get(**{self.field.name: instance})
        except self.source_model.DoesNotExist:
            return None


def _inherited_fields(bases) -> list[Field]:
    """Copies of fields declared on abstract parent models."""
    inherited: list[Field] = []
    for base in bases:
        meta = getattr(base, "_meta", None)
        if meta is None or not meta.abstract:
            continue
        for field in meta.fields:
            clone = copy.copy(field)
            clone.name = ""
            clone.model = None
            clone._pending_name = field.name
            inherited.append(clone)
    return inherited


class ModelBase(type):
    """Collects fields into ``_meta`` and wires the manager."""

    def __new__(mcls, name, bases, namespace):
        parents = [b for b in bases if isinstance(b, ModelBase)]
        if not parents:  # the base Model class itself
            return super().__new__(mcls, name, bases, namespace)

        meta = namespace.pop("Meta", None)
        abstract = bool(getattr(meta, "abstract", False))

        own: list[Field] = []
        m2m: list[ManyToManyField] = []
        for attr, value in list(namespace.items()):
            if isinstance(value, ManyToManyField):
                value._pending_name = attr
                m2m.append(value)
                namespace.pop(attr)
            elif isinstance(value, Field):
                value._pending_name = attr
                own.append(value)
                namespace.pop(attr)

        # Inherit abstract-parent fields, then let own fields override by name.
        fields = _inherited_fields(bases)
        own_names = {f._pending_name for f in own}
        fields = [f for f in fields if f._pending_name not in own_names] + own

        if not abstract and not any(f.primary_key for f in fields):
            pk = AutoField()
            pk._pending_name = "id"
            fields.insert(0, pk)

        fields.sort(key=lambda f: (not f.primary_key, f._order))

        cls = super().__new__(mcls, name, bases, namespace)

        # Bind first so field.name/column are set before _meta indexes them.
        for field in fields:
            field.bind(field._pending_name, cls)
        for field in m2m:
            field.bind(field._pending_name, cls)

        table = getattr(meta, "table", None) or name.lower()
        cls._meta = Options(
            cls, table, fields,
            abstract=abstract,
            ordering=getattr(meta, "ordering", ()),
            unique_together=getattr(meta, "unique_together", ()),
            indexes=getattr(meta, "indexes", ()),
            many_to_many=m2m,
        )

        if abstract:
            # Abstract models only contribute fields; they are never queried.
            return cls

        for field in fields:
            if isinstance(field, ForeignKey):
                setattr(cls, field.name, ForeignObjectDescriptor(field))
                # Reverse accessor on the target model (author.book_set / author.profile).
                reverse = field.reverse_name()
                target = field.to
                target._meta.reverse_relations[reverse] = (cls, field)
                if isinstance(field, OneToOneField):
                    setattr(target, reverse, ReverseOneToOneDescriptor(cls, field))
                else:
                    setattr(target, reverse, ReverseManyToOneDescriptor(cls, field))
            elif isinstance(field, FileField):
                setattr(cls, field.name, FileDescriptor(field))
        for field in m2m:
            setattr(cls, field.name, ManyRelatedDescriptor(field))

        cls.DoesNotExist = type("DoesNotExist", (DoesNotExist,), {})
        cls.MultipleObjectsReturned = type("MultipleObjectsReturned", (MultipleObjectsReturned,), {})

        from endocore.orm.manager import Manager

        cls.objects = Manager()
        cls.objects.contribute_to_class(cls)
        _MODEL_REGISTRY.append(cls)
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

        # True until this instance is known to exist as a DB row. Lets save()
        # INSERT rows whose pk is client-generated (e.g. UUIDField with a
        # default), where "pk is None" alone can't tell insert from update.
        self.__dict__["_state_adding"] = True

    # -- identity ---------------------------------------------------------

    @property
    def pk(self) -> Any:
        return getattr(self, self._meta.pk.name)

    @pk.setter
    def pk(self, value: Any) -> None:
        setattr(self, self._meta.pk.name, value)

    def __repr__(self) -> str:
        bits = [f"{self._meta.pk.name}={self.pk!r}"]
        for field in self._meta.fields:
            if field.primary_key:
                continue
            if field.internal_type in {"CharField", "TextField"}:
                if any(hint in field.name.lower() for hint in _SENSITIVE_FIELD_HINTS):
                    value = "***"
                else:
                    value = getattr(self, field.name, None)
                bits.append(f"{field.name}={value!r}")
                break
        return f"<{type(self).__name__} {' '.join(bits)}>"

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True
        if not isinstance(other, Model) or type(self) is not type(other):
            return NotImplemented if not isinstance(other, Model) else False
        if self.pk is None or other.pk is None:
            return False
        return self.pk == other.pk

    def __hash__(self) -> int:
        return hash(self.pk) if self.pk is not None else id(self)

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

    def full_clean(self) -> None:
        """Validate every field value; raises ``ValidationError`` on the first bad one."""
        for field in self._meta.fields:
            field.validate(self._value_of(field))

    def save(self, update_fields: Iterable[str] | None = None) -> "Model":
        from endocore.orm.manager import get_queryset

        adding = self.pk is None or self.__dict__.get("_state_adding", True)
        if adding and update_fields is not None:
            raise FieldError("update_fields cannot be used when inserting a new row")

        self._apply_auto_now(adding=adding)
        for field in self._meta.fields:
            field.pre_save(self)  # FileField encrypts + writes here
        self.full_clean()

        qs = get_queryset(type(self))
        if adding:
            returned_pk = qs._insert_instance(self)
            if self.pk is None:  # keep a client-generated pk (e.g. UUID default)
                self.pk = returned_pk
            self.__dict__["_state_adding"] = False
        else:
            only = set(update_fields) if update_fields is not None else None
            qs._update_instance(self, only=only)
        return self

    def delete(self) -> None:
        from endocore.orm.manager import get_queryset

        if self.pk is None:
            raise FieldError("cannot delete an unsaved instance (pk is None)")
        get_queryset(type(self)).filter(pk=self.pk).delete()
        self.pk = None
        self.__dict__["_state_adding"] = True

    def refresh_from_db(self) -> "Model":
        """Reload every field value from the database into this instance."""
        if self.pk is None:
            raise FieldError("cannot refresh an unsaved instance (pk is None)")
        fresh = type(self).objects.get(pk=self.pk)
        for field in self._meta.fields:
            if isinstance(field, ForeignKey):
                setattr(self, field.id_attr_name, getattr(fresh, field.id_attr_name))
                self.__dict__.pop(f"_{field.name}_cache", None)
            else:
                self.__dict__[field.name] = fresh.__dict__.get(field.name)
        self.__dict__["_state_adding"] = False
        return self

    # -- async API (threadpool offload) -----------------------------------

    async def asave(self, update_fields: Iterable[str] | None = None) -> "Model":
        return await asyncio.to_thread(lambda: self.save(update_fields))

    async def adelete(self) -> None:
        return await asyncio.to_thread(self.delete)

    async def arefresh_from_db(self) -> "Model":
        return await asyncio.to_thread(self.refresh_from_db)
