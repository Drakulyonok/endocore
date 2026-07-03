"""Q objects and the lazy QuerySet."""

from __future__ import annotations

import copy
from typing import Any, Iterator

from endocore.orm.exceptions import FieldError, MultipleObjectsReturned
from endocore.orm.fields import ForeignKey


class Q:
    """A tree of field lookups combinable with ``&``, ``|`` and ``~``."""

    AND = "AND"
    OR = "OR"

    def __init__(self, *args: "Q", **lookups: Any) -> None:
        self.connector = self.AND
        self.negated = False
        self.children: list = list(args) + list(lookups.items())

    def _combine(self, other: "Q", connector: str) -> "Q":
        if not isinstance(other, Q):
            raise TypeError("Q can only combine with another Q")
        combined = Q()
        combined.connector = connector
        combined.children = [self, other]
        return combined

    def __and__(self, other: "Q") -> "Q":
        return self._combine(other, self.AND)

    def __or__(self, other: "Q") -> "Q":
        return self._combine(other, self.OR)

    def __invert__(self) -> "Q":
        clone = copy.deepcopy(self)
        clone.negated = not clone.negated
        return clone

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"<Q {self.connector} neg={self.negated} {self.children}>"


class QuerySet:
    """Lazy, chainable query builder. Hits the database only on evaluation."""

    def __init__(self, model) -> None:
        self.model = model
        self._wheres: list[Q] = []
        self._order_by: list[str] = []
        self._limit: int | None = None
        self._offset: int = 0
        self._result_cache: list | None = None
        self._values_fields: tuple[str, ...] | None = None
        self._values_flat = False

    # -- infra ------------------------------------------------------------

    @property
    def _meta(self):
        return self.model._meta

    @property
    def _backend(self):
        from endocore.orm.connection import get_connection

        return get_connection(self._meta.using).backend

    def _clone(self) -> "QuerySet":
        clone = QuerySet(self.model)
        clone._wheres = list(self._wheres)
        clone._order_by = list(self._order_by)
        clone._limit = self._limit
        clone._offset = self._offset
        clone._values_fields = self._values_fields
        clone._values_flat = self._values_flat
        return clone

    def _connection(self):
        from endocore.orm.connection import get_connection

        return get_connection(self._meta.using)

    # -- filtering --------------------------------------------------------

    def filter(self, *args: Q, **lookups: Any) -> "QuerySet":
        clone = self._clone()
        if args or lookups:
            clone._wheres.append(Q(*args, **lookups))
        return clone

    def exclude(self, *args: Q, **lookups: Any) -> "QuerySet":
        clone = self._clone()
        clone._wheres.append(~Q(*args, **lookups))
        return clone

    def order_by(self, *fields: str) -> "QuerySet":
        clone = self._clone()
        clone._order_by = list(fields)
        return clone

    def all(self) -> "QuerySet":
        return self._clone()

    # -- projection -------------------------------------------------------

    def values(self, *fields: str) -> "QuerySet":
        clone = self._clone()
        clone._values_fields = fields or tuple(f.name for f in self._meta.fields)
        clone._values_flat = False
        return clone

    def values_list(self, *fields: str, flat: bool = False) -> "QuerySet":
        if flat and len(fields) != 1:
            raise FieldError("values_list(flat=True) requires exactly one field")
        clone = self._clone()
        clone._values_fields = fields or tuple(f.name for f in self._meta.fields)
        clone._values_flat = flat
        return clone

    # -- SQL helpers ------------------------------------------------------

    def _compiler(self):
        from endocore.orm.compiler import SQLCompiler

        return SQLCompiler(self._backend)

    def _select_columns(self) -> list[str]:
        if self._values_fields is not None:
            return [self._meta.get_field(n).column if n != "pk" else self._meta.pk.column
                    for n in self._values_fields]
        return [f.column for f in self._meta.fields]

    def _row_to_instance(self, columns: list[str], row) -> Any:
        col_to_field = {f.column: f for f in self._meta.fields}
        kwargs: dict[str, Any] = {}
        for column, raw in zip(columns, row):
            field = col_to_field[column]
            value = field.to_python(raw)
            if isinstance(field, ForeignKey):
                kwargs[field.id_attr_name] = value
            else:
                kwargs[field.name] = value
        return self.model(**kwargs)

    # -- evaluation -------------------------------------------------------

    def _fetch(self) -> list:
        if self._result_cache is not None:
            return self._result_cache

        columns = self._select_columns()
        sql, params = self._compiler().select(
            self._meta,
            wheres=self._wheres,
            order_by=self._order_by,
            limit=self._limit,
            offset=self._offset,
            columns=columns,
        )
        cursor = self._connection().execute(sql, params)
        rows = cursor.fetchall()

        if self._values_fields is not None:
            names = self._values_fields
            fields = [self._meta.get_field(n) if n != "pk" else self._meta.pk for n in names]
            if self._values_flat:
                result = [fields[0].to_python(row[0]) for row in rows]
            else:
                result = [
                    {name: field.to_python(row[i]) for i, (name, field) in enumerate(zip(names, fields))}
                    for row in rows
                ]
        else:
            result = [self._row_to_instance(columns, row) for row in rows]

        self._result_cache = result
        return result

    def __iter__(self) -> Iterator:
        return iter(self._fetch())

    def __len__(self) -> int:
        return len(self._fetch())

    def __bool__(self) -> bool:
        return bool(self._fetch())

    def __getitem__(self, item):
        if isinstance(item, slice):
            if item.step is not None:
                raise FieldError("QuerySet slicing does not support a step")
            clone = self._clone()
            start = item.start or 0
            clone._offset = self._offset + start
            if item.stop is not None:
                clone._limit = item.stop - start
            return clone
        if isinstance(item, int):
            if item < 0:
                raise FieldError("negative indexing is not supported")
            return self._fetch()[item] if self._result_cache is not None else self[item:item + 1]._fetch()[0]
        raise TypeError("QuerySet indices must be ints or slices")

    def __repr__(self) -> str:
        data = list(self[:21])
        more = "..." if len(data) > 20 else ""
        return f"<QuerySet {data[:20]}{more}>"

    # -- terminal operations ---------------------------------------------

    def get(self, *args: Q, **lookups: Any):
        qs = self.filter(*args, **lookups)[:2]
        rows = qs._fetch()
        if not rows:
            raise self.model.DoesNotExist(
                f"{self.model.__name__} matching query does not exist"
            )
        if len(rows) > 1:
            raise self.model.MultipleObjectsReturned(
                f"get() returned more than one {self.model.__name__}"
            )
        return rows[0]

    def first(self):
        qs = self if self._order_by else self.order_by("pk")
        result = qs[:1]._fetch()
        return result[0] if result else None

    def last(self):
        order = self._order_by or ["pk"]
        reversed_order = [f[1:] if f.startswith("-") else f"-{f}" for f in order]
        result = self.order_by(*reversed_order)[:1]._fetch()
        return result[0] if result else None

    def count(self) -> int:
        sql, params = self._compiler().count(self._meta, wheres=self._wheres)
        cursor = self._connection().execute(sql, params)
        return int(cursor.fetchone()[0])

    def exists(self) -> bool:
        return bool(self[:1]._fetch())

    def create(self, **kwargs: Any):
        instance = self.model(**kwargs)
        instance.save()
        return instance

    def bulk_create(self, objects: list) -> list:
        for obj in objects:
            obj.save()
        return objects

    # -- write operations -------------------------------------------------

    def _assignments_from_kwargs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        from endocore.orm.model import Model

        backend = self._backend
        assignments: dict[str, Any] = {}
        for name, value in kwargs.items():
            field = self._meta.pk if name == "pk" else self._meta.get_field(name)
            if isinstance(value, Model):
                value = value.pk
            assignments[field.column] = field.to_db(value, backend)
        return assignments

    def update(self, **kwargs: Any) -> int:
        assignments = self._assignments_from_kwargs(kwargs)
        sql, params = self._compiler().update(self._meta, assignments, self._wheres)
        cursor = self._connection().execute(sql, params, write=True)
        return cursor.rowcount

    def delete(self) -> int:
        sql, params = self._compiler().delete(self._meta, self._wheres)
        cursor = self._connection().execute(sql, params, write=True)
        return cursor.rowcount

    # -- used by Model.save() ---------------------------------------------

    def _insert_instance(self, instance) -> Any:
        backend = self._backend
        meta = self._meta
        columns: list[str] = []
        values: list = []
        for field in meta.fields:
            if field.primary_key and field.internal_type == "AutoField" and instance._value_of(field) is None:
                continue  # let the DB assign the pk
            columns.append(field.column)
            values.append(field.to_db(instance._value_of(field), backend))

        sql, params, returning = self._compiler().insert(meta, columns, values)
        cursor = self._connection().execute(sql, params, write=True)
        if returning:
            return meta.pk.to_python(backend.last_insert_id(cursor, meta.pk.column))
        return meta.pk.to_python(cursor.lastrowid) if meta.pk else None

    def _update_instance(self, instance) -> None:
        backend = self._backend
        meta = self._meta
        assignments = {
            field.column: field.to_db(instance._value_of(field), backend)
            for field in meta.fields
            if not field.primary_key
        }
        sql, params = self._compiler().update(
            meta, assignments, [Q(pk=instance.pk)]
        )
        self._connection().execute(sql, params, write=True)
