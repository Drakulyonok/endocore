"""SQL compiler — turns models + Q trees into parameterized SQL.

Security invariants enforced here (and nowhere bypassed):
- Identifiers (tables/columns/aliases) go through ``backend.quote``.
- Values are only ever emitted as placeholders; the data travels in a separate
  params list bound by the driver.
- Only whitelisted lookups produce SQL. An unknown lookup raises.
- LIMIT/OFFSET are coerced to ints; LIKE wildcards in user input are escaped.

Relational lookups (``team__name``) and ``select_related`` add LEFT JOINs via
:class:`RelationResolver`. When a query has no relations it uses the plain path,
emitting unqualified columns (simpler SQL, and stable for the dialect tests).
"""

from __future__ import annotations

from typing import Any

from endocore.orm.backends.base import LIKE_ESCAPE, BaseBackend
from endocore.orm.exceptions import FieldError
from endocore.orm.fields import ForeignKey
from endocore.orm.query import Q


LOOKUPS = frozenset(
    {
        "exact", "iexact",
        "contains", "icontains",
        "startswith", "istartswith",
        "endswith", "iendswith",
        "gt", "gte", "lt", "lte",
        "in", "isnull", "range",
    }
)

_COMPARISON = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}

_LIKE_PATTERNS = {
    "contains": ("%{v}%", False),
    "icontains": ("%{v}%", True),
    "startswith": ("{v}%", False),
    "istartswith": ("{v}%", True),
    "endswith": ("%{v}", False),
    "iendswith": ("%{v}", True),
}


def split_lookup(key: str) -> tuple[str, str]:
    """``age__gte`` -> ``("age", "gte")``; ``name`` -> ``("name", "exact")``."""
    if "__" in key:
        field_name, lookup = key.rsplit("__", 1)
        if lookup in LOOKUPS:
            return field_name, lookup
    return key, "exact"


class RelationResolver:
    """Registers LEFT JOINs for relational lookup paths and qualifies columns.

    A path like ``team__owner__name`` walks ForeignKeys ``team`` then ``owner``
    (each a JOIN) and resolves ``name`` on the final model.
    """

    def __init__(self, base_meta, backend: BaseBackend) -> None:
        self.base = base_meta
        self.backend = backend
        self.joins: list[str] = []
        self._counter = 0
        # path tuple of FK names -> (quoted table/alias ref, meta)
        self._cache: dict[tuple, tuple[str, Any]] = {(): (backend.quote(base_meta.table), base_meta)}

    def follow(self, parts: tuple) -> tuple[str, Any]:
        if parts in self._cache:
            return self._cache[parts]
        parent_ref, parent_meta = self.follow(parts[:-1])
        fk = parent_meta.get_field(parts[-1])
        if not isinstance(fk, ForeignKey):
            raise FieldError(f"{parts[-1]!r} is not a relation on {parent_meta.model.__name__}")
        rel_meta = fk.to._meta
        self._counter += 1
        alias = self.backend.quote(f"J{self._counter}")
        left = f"{parent_ref}.{self.backend.quote(fk.column)}"
        right = f"{alias}.{self.backend.quote(rel_meta.pk.column)}"
        self.joins.append(f"LEFT JOIN {self.backend.quote(rel_meta.table)} {alias} ON {left} = {right}")
        self._cache[parts] = (alias, rel_meta)
        return self._cache[parts]

    def resolve_lookup(self, key: str) -> tuple[str, Any, str]:
        parts = key.split("__")
        lookup = "exact"
        if len(parts) > 1 and parts[-1] in LOOKUPS:
            lookup, parts = parts[-1], parts[:-1]
        *rel, field_name = parts
        ref, meta = self.follow(tuple(rel))
        field = meta.pk if field_name == "pk" else meta.get_field(field_name)
        return f"{ref}.{self.backend.quote(field.column)}", field, lookup

    def resolve_ref(self, name: str) -> tuple[str, Any]:
        parts = name.split("__")
        *rel, field_name = parts
        ref, meta = self.follow(tuple(rel))
        field = meta.pk if field_name == "pk" else meta.get_field(field_name)
        return f"{ref}.{self.backend.quote(field.column)}", field


class SQLCompiler:
    def __init__(self, backend: BaseBackend) -> None:
        self.backend = backend

    # -- helpers ----------------------------------------------------------

    def _resolve(self, meta, field_name: str):
        return meta.pk if field_name == "pk" else meta.get_field(field_name)

    def _adapt(self, field, value: Any) -> Any:
        from endocore.orm.model import Model

        if isinstance(value, Model):
            value = value.pk
        return field.to_db(value, self.backend)

    def _like(self, col_sql: str, value: str, *, ci: bool, pattern: str) -> tuple[str, list]:
        escaped = self.backend.like_escape(str(value))
        param = pattern.format(v=escaped)
        if ci:
            param = param.lower()
            frag = f"LOWER({col_sql}) LIKE {self.backend.placeholder} ESCAPE '{LIKE_ESCAPE}'"
        else:
            frag = f"{col_sql} LIKE {self.backend.placeholder} ESCAPE '{LIKE_ESCAPE}'"
        return frag, [param]

    # -- operator core (shared by simple & joined paths) ------------------

    def _operator_sql(self, col: str, field, lookup: str, value: Any) -> tuple[str, list]:
        ph = self.backend.placeholder

        if lookup == "exact":
            if value is None:
                return f"{col} IS NULL", []
            return f"{col} = {ph}", [self._adapt(field, value)]

        if lookup == "iexact":
            return f"LOWER({col}) = LOWER({ph})", [self._adapt(field, value)]

        if lookup in _COMPARISON:
            return f"{col} {_COMPARISON[lookup]} {ph}", [self._adapt(field, value)]

        if lookup == "in":
            values = list(value)
            if not values:
                return "1 = 0", []
            params = [self._adapt(field, v) for v in values]
            return f"{col} IN ({self.backend.placeholders(len(params))})", params

        if lookup == "isnull":
            return f"{col} IS {'NULL' if value else 'NOT NULL'}", []

        if lookup == "range":
            low, high = value
            return f"{col} BETWEEN {ph} AND {ph}", [self._adapt(field, low), self._adapt(field, high)]

        pattern, ci = _LIKE_PATTERNS[lookup]
        return self._like(col, value, ci=ci, pattern=pattern)

    # -- simple (no-join) leaf & where -----------------------------------

    def _leaf(self, meta, key: str, value: Any) -> tuple[str, list]:
        field_name, lookup = split_lookup(key)
        field = self._resolve(meta, field_name)
        return self._operator_sql(self.backend.quote(field.column), field, lookup, value)

    def compile_q(self, meta, node: Q, resolver: RelationResolver | None = None) -> tuple[str, list]:
        if not node.children:
            return "", []
        parts: list[str] = []
        params: list = []
        for child in node.children:
            if isinstance(child, Q):
                sub_sql, sub_params = self.compile_q(meta, child, resolver)
                if not sub_sql:
                    continue
                parts.append(f"({sub_sql})")
                params.extend(sub_params)
            else:
                key, value = child
                if resolver is None:
                    frag, frag_params = self._leaf(meta, key, value)
                else:
                    col, field, lookup = resolver.resolve_lookup(key)
                    frag, frag_params = self._operator_sql(col, field, lookup, value)
                parts.append(frag)
                params.extend(frag_params)
        if not parts:
            return "", []
        joined = f" {node.connector} ".join(parts)
        if node.negated:
            joined = f"NOT ({joined})"
        return joined, params

    def _where_clause(self, meta, wheres: list[Q], resolver: RelationResolver | None = None) -> tuple[str, list]:
        parts: list[str] = []
        params: list = []
        for node in wheres:
            sql, node_params = self.compile_q(meta, node, resolver)
            if sql:
                parts.append(f"({sql})")
                params.extend(node_params)
        if not parts:
            return "", []
        return " WHERE " + " AND ".join(parts), params

    def _order_clause(self, meta, order_by: list[str], resolver: RelationResolver | None = None) -> str:
        if not order_by:
            return ""
        terms = []
        for spec in order_by:
            descending = spec.startswith("-")
            name = spec[1:] if descending else spec
            if resolver is None:
                field = self._resolve(meta, name)
                col = self.backend.quote(field.column)
            else:
                col, _ = resolver.resolve_ref(name)
            terms.append(f"{col} {'DESC' if descending else 'ASC'}")
        return " ORDER BY " + ", ".join(terms)

    # -- statements (simple path) ----------------------------------------

    def select(self, meta, *, wheres, order_by, limit, offset, columns, distinct=False) -> tuple[str, list]:
        cols = ", ".join(self.backend.quote(c) for c in columns)
        keyword = "SELECT DISTINCT" if distinct else "SELECT"
        sql = f"{keyword} {cols} FROM {self.backend.quote(meta.table)}"
        where_sql, params = self._where_clause(meta, wheres)
        sql += where_sql
        sql += self._order_clause(meta, order_by)
        if limit is not None:
            sql += f" LIMIT {self.backend.as_limit(limit)}"
        if offset:
            sql += f" OFFSET {self.backend.as_limit(offset)}"
        return sql, params

    def count(self, meta, *, wheres, distinct=False) -> tuple[str, list]:
        inner = "*" if not distinct else f"DISTINCT {self.backend.quote(meta.pk.column)}"
        # identifier quoted; no values
        sql = f"SELECT COUNT({inner}) FROM {self.backend.quote(meta.table)}"  # nosec B608
        where_sql, params = self._where_clause(meta, wheres)
        return sql + where_sql, params

    def aggregate(self, meta, frags: list[tuple[str, list]], wheres) -> tuple[str, list]:
        cols = ", ".join(sql for sql, _ in frags)
        params: list = []
        for _, frag_params in frags:
            params.extend(frag_params)
        # identifier quoted; cols are pre-built aggregate SQL; no raw values
        sql = f"SELECT {cols} FROM {self.backend.quote(meta.table)}"  # nosec B608
        where_sql, where_params = self._where_clause(meta, wheres)
        return sql + where_sql, params + where_params

    def insert(self, meta, columns: list[str], values: list) -> tuple[str, list, bool]:
        quoted = ", ".join(self.backend.quote(c) for c in columns)
        placeholders = self.backend.placeholders(len(values))
        # identifiers quoted; values are bound placeholders
        sql = f"INSERT INTO {self.backend.quote(meta.table)} ({quoted}) VALUES ({placeholders})"  # nosec B608
        returning = self.backend.supports_returning and meta.pk is not None
        if returning:
            sql += f" RETURNING {self.backend.quote(meta.pk.column)}"
        return sql, list(values), returning

    def insert_many(self, meta, columns: list[str], rows: list[list]) -> tuple[str, list, bool]:
        quoted = ", ".join(self.backend.quote(c) for c in columns)
        one = f"({self.backend.placeholders(len(columns))})"
        groups = ", ".join([one] * len(rows))
        # identifiers quoted; values are bound placeholders
        sql = f"INSERT INTO {self.backend.quote(meta.table)} ({quoted}) VALUES {groups}"  # nosec B608
        params: list = []
        for row in rows:
            params.extend(row)
        returning = self.backend.supports_returning and meta.pk is not None
        if returning:
            sql += f" RETURNING {self.backend.quote(meta.pk.column)}"
        return sql, params, returning

    def update(self, meta, assignments: dict[str, Any], wheres) -> tuple[str, list]:
        if not assignments:
            raise FieldError("update() requires at least one field")
        set_parts = []
        params: list = []
        for column, value in assignments.items():
            col = self.backend.quote(column)
            if hasattr(value, "as_sql"):  # F() / expression
                value_sql, value_params = value.as_sql(meta, self.backend)
                set_parts.append(f"{col} = {value_sql}")
                params.extend(value_params)
            else:
                set_parts.append(f"{col} = {self.backend.placeholder}")
                params.append(value)
        # identifiers quoted; values are bound placeholders
        sql = f"UPDATE {self.backend.quote(meta.table)} SET {', '.join(set_parts)}"  # nosec B608
        where_sql, where_params = self._where_clause(meta, wheres)
        sql += where_sql
        params.extend(where_params)
        return sql, params

    def delete(self, meta, wheres) -> tuple[str, list]:
        # identifier quoted; no values
        sql = f"DELETE FROM {self.backend.quote(meta.table)}"  # nosec B608
        where_sql, params = self._where_clause(meta, wheres)
        return sql + where_sql, params

    # -- joined path (relations / select_related) ------------------------

    def build_joined(self, meta, *, wheres, order_by, select_related, distinct,
                     limit, offset) -> tuple[str, list, list]:
        resolver = RelationResolver(meta, self.backend)
        base_ref = self.backend.quote(meta.table)

        select_cols: list[str] = []
        result_map: list[tuple[tuple, Any]] = []
        for f in meta.fields:
            select_cols.append(f"{base_ref}.{self.backend.quote(f.column)}")
            result_map.append(((), f))

        for rel in select_related:
            parts = tuple(rel.split("__"))
            ref, rmeta = resolver.follow(parts)
            for f in rmeta.fields:
                select_cols.append(f"{ref}.{self.backend.quote(f.column)}")
                result_map.append((parts, f))

        # Compile WHERE and ORDER BY (these may register more joins).
        where_sql, params = self._where_clause(meta, wheres, resolver)
        order_sql = self._order_clause(meta, order_by, resolver)

        keyword = "SELECT DISTINCT" if distinct else "SELECT"
        sql = f"{keyword} {', '.join(select_cols)} FROM {base_ref}"
        if resolver.joins:
            sql += " " + " ".join(resolver.joins)
        sql += where_sql + order_sql
        if limit is not None:
            sql += f" LIMIT {self.backend.as_limit(limit)}"
        if offset:
            sql += f" OFFSET {self.backend.as_limit(offset)}"
        return sql, params, result_map

    def count_joined(self, meta, *, wheres) -> tuple[str, list]:
        resolver = RelationResolver(meta, self.backend)
        where_sql, params = self._where_clause(meta, wheres, resolver)
        # identifier quoted; no values
        sql = f"SELECT COUNT(*) FROM {self.backend.quote(meta.table)}"  # nosec B608
        if resolver.joins:
            sql += " " + " ".join(resolver.joins)
        return sql + where_sql, params
