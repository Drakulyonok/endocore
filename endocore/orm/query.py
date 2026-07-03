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
        self._values_list = False  # True -> tuples; False -> dicts (for values())
        self._distinct = False
        self._select_related: list[str] = []
        self._prefetch: list[str] = []
        self._only: tuple[str, ...] | None = None
        self._defer: tuple[str, ...] | None = None
        self._annotations: dict = {}
        self._is_empty = False

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
        clone._values_list = self._values_list
        clone._distinct = self._distinct
        clone._select_related = list(self._select_related)
        clone._prefetch = list(self._prefetch)
        clone._only = self._only
        clone._defer = self._defer
        clone._annotations = dict(self._annotations)
        clone._is_empty = self._is_empty
        return clone

    @property
    def _effective_order(self) -> list[str]:
        """Explicit order_by, else the model's ``Meta.ordering``."""
        return list(self._order_by) if self._order_by else list(self._meta.ordering)

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

    def distinct(self) -> "QuerySet":
        clone = self._clone()
        clone._distinct = True
        return clone

    def select_related(self, *paths: str) -> "QuerySet":
        clone = self._clone()
        clone._select_related = list(self._select_related) + list(paths)
        return clone

    def prefetch_related(self, *names: str) -> "QuerySet":
        clone = self._clone()
        clone._prefetch = list(self._prefetch) + list(names)
        return clone

    def only(self, *fields: str) -> "QuerySet":
        """Fetch only these columns (plus the pk); other fields default to None."""
        clone = self._clone()
        clone._only = fields
        clone._defer = None
        return clone

    def defer(self, *fields: str) -> "QuerySet":
        """Fetch all columns except these."""
        clone = self._clone()
        clone._defer = fields
        clone._only = None
        return clone

    def annotate(self, **annotations) -> "QuerySet":
        """Attach an aggregate over a relation/field to each row.

            Author.objects.annotate(n=Count("books"))   # reverse FK
            Book.objects.annotate(n=Count("tags"))       # M2M
        """
        clone = self._clone()
        clone._annotations = {**self._annotations, **annotations}
        return clone

    def all(self) -> "QuerySet":
        return self._clone()

    def none(self) -> "QuerySet":
        """An always-empty QuerySet that never hits the database."""
        clone = self._clone()
        clone._is_empty = True
        return clone

    # -- projection -------------------------------------------------------

    def values(self, *fields: str) -> "QuerySet":
        clone = self._clone()
        clone._values_fields = fields or tuple(f.name for f in self._meta.fields)
        clone._values_flat = False
        clone._values_list = False
        return clone

    def values_list(self, *fields: str, flat: bool = False) -> "QuerySet":
        if flat and len(fields) != 1:
            raise FieldError("values_list(flat=True) requires exactly one field")
        clone = self._clone()
        clone._values_fields = fields or tuple(f.name for f in self._meta.fields)
        clone._values_flat = flat
        clone._values_list = True
        return clone

    # -- SQL helpers ------------------------------------------------------

    def _compiler(self):
        from endocore.orm.compiler import SQLCompiler

        return SQLCompiler(self._backend)

    def _select_columns(self) -> list[str]:
        if self._values_fields is not None:
            return [self._meta.get_field(n).column if n != "pk" else self._meta.pk.column
                    for n in self._values_fields]
        fields = self._meta.fields
        if self._only is not None:
            keep = set(self._only) | {self._meta.pk.name}
            fields = [f for f in fields if f.name in keep]
        elif self._defer is not None:
            drop = set(self._defer) - {self._meta.pk.name}
            fields = [f for f in fields if f.name not in drop]
        return [f.column for f in fields]

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

    # -- relational (join) support ---------------------------------------

    def _uses_joins(self) -> bool:
        from endocore.orm.compiler import split_lookup

        if self._select_related:
            return True
        for spec in self._effective_order:
            name = spec[1:] if spec.startswith("-") else spec
            if "__" in name:
                return True
        return any(self._q_has_relation(node) for node in self._wheres)

    def _q_has_relation(self, node: Q) -> bool:
        from endocore.orm.compiler import split_lookup

        for child in node.children:
            if isinstance(child, Q):
                if self._q_has_relation(child):
                    return True
            else:
                field_name, _ = split_lookup(child[0])
                if "__" in field_name:
                    return True
        return False

    @staticmethod
    def _instance_from_fields(model, field_values: dict) -> Any:
        kwargs: dict[str, Any] = {}
        for field, value in field_values.items():
            if isinstance(field, ForeignKey):
                kwargs[field.id_attr_name] = value
            else:
                kwargs[field.name] = value
        return model(**kwargs)

    def _row_to_instance_joined(self, result_map, row) -> Any:
        from collections import defaultdict

        data: dict[tuple, dict] = defaultdict(dict)
        for (path, field), raw in zip(result_map, row):
            data[path][field] = field.to_python(raw)

        base = self._instance_from_fields(self.model, data[()])
        built: dict[tuple, Any] = {(): base}

        for path in sorted((p for p in data if p != ()), key=len):
            field_values = data[path]
            related_model = next(iter(field_values)).model
            pk_field = related_model._meta.pk
            related = None
            if field_values.get(pk_field) is not None:
                related = self._instance_from_fields(related_model, field_values)

            parent = built.get(path[:-1])
            if parent is not None:
                setattr(parent, f"_{path[-1]}_cache", related)
            built[path] = related

        return base

    # -- evaluation -------------------------------------------------------

    def _fetch(self) -> list:
        if self._result_cache is not None:
            return self._result_cache
        if self._is_empty:
            self._result_cache = []
            return self._result_cache

        if self._annotations:
            self._result_cache = self._fetch_annotated()
            return self._result_cache

        if self._uses_joins():
            self._result_cache = self._fetch_joined()
            return self._result_cache

        columns = self._select_columns()
        sql, params = self._compiler().select(
            self._meta,
            wheres=self._wheres,
            order_by=self._effective_order,
            limit=self._limit,
            offset=self._offset,
            columns=columns,
            distinct=self._distinct,
        )
        cursor = self._connection().execute(sql, params)
        rows = cursor.fetchall()

        if self._values_fields is not None:
            names = self._values_fields
            fields = [self._meta.get_field(n) if n != "pk" else self._meta.pk for n in names]
            if self._values_flat:
                result = [fields[0].to_python(row[0]) for row in rows]
            elif self._values_list:
                result = [
                    tuple(field.to_python(row[i]) for i, field in enumerate(fields))
                    for row in rows
                ]
            else:
                result = [
                    {name: field.to_python(row[i]) for i, (name, field) in enumerate(zip(names, fields))}
                    for row in rows
                ]
        else:
            result = [self._row_to_instance(columns, row) for row in rows]
            if self._prefetch:
                self._apply_prefetch(result)

        self._result_cache = result
        return result

    def _fetch_joined(self) -> list:
        if self._values_fields is not None:
            raise FieldError("values()/values_list() with relational lookups is not supported yet")
        sql, params, result_map = self._compiler().build_joined(
            self._meta,
            wheres=self._wheres,
            order_by=self._effective_order,
            select_related=self._select_related,
            distinct=self._distinct,
            limit=self._limit,
            offset=self._offset,
        )
        rows = self._connection().execute(sql, params).fetchall()
        instances = [self._row_to_instance_joined(result_map, row) for row in rows]
        if self._prefetch:
            self._apply_prefetch(instances)
        return instances

    # -- prefetch (batch-load relations to avoid N+1) --------------------

    def _apply_prefetch(self, instances: list) -> None:
        for name in self._prefetch:
            m2m = next((f for f in self._meta.many_to_many if f.name == name), None)
            if m2m is not None:
                self._prefetch_m2m(m2m, instances)
                continue
            field = self._meta.fields_by_name.get(name)
            if field is not None and isinstance(field, ForeignKey):
                self._prefetch_fk(field, instances)
                continue
            raise FieldError(f"prefetch_related: {name!r} is not a relation on {self.model.__name__}")

    def _prefetch_m2m(self, field, instances: list) -> None:
        backend = self._backend
        pks = [i.pk for i in instances if i.pk is not None]
        if not pks:
            for inst in instances:
                setattr(inst, f"_m2m_{field.name}", [])
            return
        table = backend.quote(field.through_table())
        src, tgt = backend.quote(field.source_column()), backend.quote(field.target_column())
        sql = f"SELECT {src}, {tgt} FROM {table} WHERE {src} IN ({backend.placeholders(len(pks))})"
        groups: dict = {}
        targets: set = set()
        for source_id, target_id in self._connection().execute(sql, pks).fetchall():
            groups.setdefault(source_id, []).append(target_id)
            targets.add(target_id)
        objmap = {o.pk: o for o in field.to.objects.filter(pk__in=list(targets))} if targets else {}
        for inst in instances:
            setattr(inst, f"_m2m_{field.name}",
                    [objmap[t] for t in groups.get(inst.pk, []) if t in objmap])

    def _prefetch_fk(self, field, instances: list) -> None:
        ids = {getattr(i, field.id_attr_name) for i in instances}
        ids.discard(None)
        objmap = {o.pk: o for o in field.to.objects.filter(pk__in=list(ids))} if ids else {}
        for inst in instances:
            setattr(inst, f"_{field.name}_cache", objmap.get(getattr(inst, field.id_attr_name)))

    # -- annotate (aggregate over a relation/field, GROUP BY base) --------

    def _fetch_annotated(self) -> list:
        from endocore.orm.fields import ManyToManyField

        backend = self._backend
        meta = self._meta
        base = backend.quote(meta.table)
        pk_col = f"{base}.{backend.quote(meta.pk.column)}"

        base_cols = [f"{base}.{backend.quote(f.column)}" for f in meta.fields]
        joins: list[str] = []
        agg_selects: list[str] = []
        aliases: list[str] = list(self._annotations)

        for i, (alias, agg) in enumerate(self._annotations.items()):
            target = agg.field
            m2m = next((f for f in meta.many_to_many if f.name == target), None)
            if target == "*" or target in meta.fields_by_name:
                col = "*" if target == "*" else f"{base}.{backend.quote(meta.get_field(target).column)}"
                agg_selects.append(f"{agg.function}({col})")
            elif m2m is not None:
                jt = backend.quote(f"a{i}")
                joins.append(
                    f"LEFT JOIN {backend.quote(m2m.through_table())} {jt} "
                    f"ON {jt}.{backend.quote(m2m.source_column())} = {pk_col}"
                )
                agg_selects.append(f"{agg.function}({jt}.{backend.quote(m2m.target_column())})")
            elif target in meta.reverse_relations:
                source_model, fk = meta.reverse_relations[target]
                src = backend.quote(f"a{i}")
                joins.append(
                    f"LEFT JOIN {backend.quote(source_model._meta.table)} {src} "
                    f"ON {src}.{backend.quote(fk.column)} = {pk_col}"
                )
                agg_selects.append(f"{agg.function}({src}.{backend.quote(source_model._meta.pk.column)})")
            else:
                raise FieldError(f"annotate: {target!r} is not a field or relation of {self.model.__name__}")

        select_sql = ", ".join(base_cols + agg_selects)
        sql = f"SELECT {select_sql} FROM {base}"
        if joins:
            sql += " " + " ".join(joins)
        where_sql, params = self._compiler()._where_clause(meta, self._wheres)
        sql += where_sql
        sql += " GROUP BY " + ", ".join(base_cols)
        sql += self._compiler()._order_clause(meta, self._effective_order)
        if self._limit is not None:
            sql += f" LIMIT {backend.as_limit(self._limit)}"
        if self._offset:
            sql += f" OFFSET {backend.as_limit(self._offset)}"

        rows = self._connection().execute(sql, params).fetchall()
        columns = [f.column for f in meta.fields]
        n = len(columns)
        result = []
        for row in rows:
            instance = self._row_to_instance(columns, row[:n])
            for j, alias in enumerate(aliases):
                setattr(instance, alias, row[n + j])
            result.append(instance)
        return result

    # -- bulk update ------------------------------------------------------

    def bulk_update(self, objects: list, fields: list[str]) -> int:
        """Write the given fields of each instance back to the DB (one UPDATE each)."""
        if not objects:
            return 0
        backend = self._backend
        meta = self._meta
        field_objs = [meta.get_field(f) for f in fields]
        conn = self._connection()
        count = 0
        with conn.atomic():
            for obj in objects:
                assignments = {f.column: f.to_db(obj._value_of(f), backend) for f in field_objs}
                sql, params = self._compiler().update(meta, assignments, [Q(pk=obj.pk)])
                conn.execute(sql, params, write=True)
                count += 1
        return count

    def __iter__(self) -> Iterator:
        return iter(self._fetch())

    def __len__(self) -> int:
        return len(self._fetch())

    def __bool__(self) -> bool:
        return bool(self._fetch())

    def __contains__(self, obj) -> bool:
        return obj in self._fetch()

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
        order = self._effective_order or ["pk"]
        result = self.order_by(*order)[:1]._fetch()
        return result[0] if result else None

    def last(self):
        order = self._effective_order or ["pk"]
        reversed_order = [f[1:] if f.startswith("-") else f"-{f}" for f in order]
        result = self.order_by(*reversed_order)[:1]._fetch()
        return result[0] if result else None

    def count(self) -> int:
        if self._is_empty:
            return 0
        if self._uses_joins() and not self._distinct:
            sql, params = self._compiler().count_joined(self._meta, wheres=self._wheres)
        else:
            sql, params = self._compiler().count(self._meta, wheres=self._wheres, distinct=self._distinct)
        cursor = self._connection().execute(sql, params)
        return int(cursor.fetchone()[0])

    def exists(self) -> bool:
        return bool(self[:1]._fetch())

    def in_bulk(self, ids: Iterable[Any]) -> dict:
        """Return a ``{pk: instance}`` map for the given primary keys."""
        ids = list(ids)
        if not ids:
            return {}
        return {obj.pk: obj for obj in self.filter(pk__in=ids)}

    def aggregate(self, **kwargs) -> dict:
        from endocore.orm.expressions import Aggregate

        frags, keys = [], []
        for key, agg in kwargs.items():
            if not isinstance(agg, Aggregate):
                raise FieldError(f"aggregate() values must be aggregates, got {agg!r}")
            frags.append(agg.as_sql(self._meta, self._backend))
            keys.append(key)
        sql, params = self._compiler().aggregate(self._meta, frags, self._wheres)
        row = self._connection().execute(sql, params).fetchone()
        return {key: row[i] for i, key in enumerate(keys)}

    def earliest(self, field: str):
        return self._edge(field)

    def latest(self, field: str):
        return self._edge("-" + field)

    def _edge(self, order_field: str):
        result = self.order_by(order_field)[:1]._fetch()
        if not result:
            raise self.model.DoesNotExist(
                f"{self.model.__name__} matching query does not exist"
            )
        return result[0]

    def get_or_create(self, defaults: dict | None = None, **kwargs):
        try:
            return self.get(**kwargs), False
        except self.model.DoesNotExist:
            return self.create(**{**kwargs, **(defaults or {})}), True

    def update_or_create(self, defaults: dict | None = None, **kwargs):
        defaults = defaults or {}
        try:
            obj = self.get(**kwargs)
        except self.model.DoesNotExist:
            return self.create(**{**kwargs, **defaults}), True
        for name, value in defaults.items():
            setattr(obj, name, value)
        obj.save()
        return obj, False

    def create(self, **kwargs: Any):
        instance = self.model(**kwargs)
        instance.save()
        return instance

    def bulk_create(self, objects: list) -> list:
        """Insert many rows in one statement, populating primary keys.

        Uses RETURNING on Postgres; on SQLite the contiguous rowids of a single
        multi-row INSERT are backfilled from ``lastrowid``."""
        if not objects:
            return objects
        backend = self._backend
        meta = self._meta
        insert_fields = [f for f in meta.fields if not f.auto_increment]
        columns = [f.column for f in insert_fields]

        rows = []
        for obj in objects:
            obj._apply_auto_now(adding=True)
            for f in meta.fields:
                f.pre_save(obj)
            obj.full_clean()
            rows.append([f.to_db(obj._value_of(f), backend) for f in insert_fields])

        sql, params, returning = self._compiler().insert_many(meta, columns, rows)
        conn = self._connection()
        with conn.atomic():
            cursor = conn.execute(sql, params, write=True)
            if returning:
                ids = [r[0] for r in cursor.fetchall()]
                for obj, new_pk in zip(objects, ids):
                    obj.pk = meta.pk.to_python(new_pk)
            elif meta.pk is not None and meta.pk.auto_increment and cursor.lastrowid:
                # A single multi-row INSERT assigns contiguous rowids ending at
                # lastrowid — safe to backfill in order.
                last = cursor.lastrowid
                for offset, obj in enumerate(reversed(objects)):
                    obj.pk = meta.pk.to_python(last - offset)
        return objects

    # -- write operations -------------------------------------------------

    def _assignments_from_kwargs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        from endocore.orm.model import Model
        from endocore.orm.expressions import Combinable

        backend = self._backend
        assignments: dict[str, Any] = {}
        for name, value in kwargs.items():
            field = self._meta.pk if name == "pk" else self._meta.get_field(name)
            if isinstance(value, Combinable):
                assignments[field.column] = value  # F()/expression, compiled later
                continue
            if isinstance(value, Model):
                value = value.pk
            field.validate(value)
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
            if field.auto_increment and instance._value_of(field) is None:
                continue  # let the DB assign the pk
            columns.append(field.column)
            values.append(field.to_db(instance._value_of(field), backend))

        sql, params, returning = self._compiler().insert(meta, columns, values)
        cursor = self._connection().execute(sql, params, write=True)
        if returning:
            return meta.pk.to_python(backend.last_insert_id(cursor, meta.pk.column))
        return meta.pk.to_python(cursor.lastrowid) if meta.pk else None

    def _update_instance(self, instance, only: set[str] | None = None) -> None:
        backend = self._backend
        meta = self._meta
        assignments = {
            field.column: field.to_db(instance._value_of(field), backend)
            for field in meta.fields
            if not field.primary_key and (only is None or field.name in only)
        }
        if not assignments:
            return
        sql, params = self._compiler().update(
            meta, assignments, [Q(pk=instance.pk)]
        )
        self._connection().execute(sql, params, write=True)
