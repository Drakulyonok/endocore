"""SQL compiler — turns models + Q trees into parameterized SQL.

Security invariants enforced here (and nowhere bypassed):
- Identifiers (tables/columns) go through ``backend.quote`` (validated + quoted).
- Values are only ever emitted as placeholders; the actual data travels in a
  separate params list bound by the driver.
- Only whitelisted lookups produce SQL. An unknown lookup raises, never falls
  through to string building.
- LIMIT/OFFSET are coerced to ints; LIKE wildcards in user input are escaped.
"""

from __future__ import annotations

from typing import Any

from endocore.orm.backends.base import LIKE_ESCAPE, BaseBackend
from endocore.orm.exceptions import FieldError
from endocore.orm.fields import ForeignKey
from endocore.orm.query import Q


#: Whitelisted lookups. Anything not here is rejected.
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


class SQLCompiler:
    def __init__(self, backend: BaseBackend) -> None:
        self.backend = backend

    # -- helpers ----------------------------------------------------------

    def _split_lookup(self, key: str) -> tuple[str, str]:
        if "__" in key:
            field_name, lookup = key.rsplit("__", 1)
            if lookup in LOOKUPS:
                return field_name, lookup
        return key, "exact"

    def _resolve(self, meta, field_name: str):
        field = meta.pk if field_name == "pk" else meta.get_field(field_name)
        return field

    def _adapt(self, field, value: Any) -> Any:
        from endocore.orm.model import Model

        if isinstance(value, Model):
            value = value.pk
        return field.to_db(value, self.backend)

    def _like(self, col_sql: str, value: str, *, ci: bool, pattern: str) -> tuple[str, list]:
        """Build a LIKE fragment with wildcards escaped (see ``pattern``)."""
        escaped = self.backend.like_escape(str(value))
        param = pattern.format(v=escaped)
        if ci:
            param = param.lower()
            frag = f"LOWER({col_sql}) LIKE {self.backend.placeholder} ESCAPE '{LIKE_ESCAPE}'"
        else:
            frag = f"{col_sql} LIKE {self.backend.placeholder} ESCAPE '{LIKE_ESCAPE}'"
        return frag, [param]

    # -- leaf compilation (the operator whitelist) ------------------------

    def _leaf(self, meta, key: str, value: Any) -> tuple[str, list]:
        field_name, lookup = self._split_lookup(key)
        field = self._resolve(meta, field_name)
        col = self.backend.quote(field.column)
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
                return "1 = 0", []  # IN () matches nothing; keep it valid SQL
            params = [self._adapt(field, v) for v in values]
            return f"{col} IN ({self.backend.placeholders(len(params))})", params

        if lookup == "isnull":
            return f"{col} IS {'NULL' if value else 'NOT NULL'}", []

        if lookup == "range":
            low, high = value
            return (
                f"{col} BETWEEN {ph} AND {ph}",
                [self._adapt(field, low), self._adapt(field, high)],
            )

        # LIKE family — wildcards in user input are escaped inside _like.
        patterns = {
            "contains": ("%{v}%", False),
            "icontains": ("%{v}%", True),
            "startswith": ("{v}%", False),
            "istartswith": ("{v}%", True),
            "endswith": ("%{v}", False),
            "iendswith": ("%{v}", True),
        }
        pattern, ci = patterns[lookup]
        return self._like(col, value, ci=ci, pattern=pattern)

    # -- WHERE (recurse over the Q tree) ----------------------------------

    def compile_q(self, meta, node: Q) -> tuple[str, list]:
        if not node.children:
            return "", []
        parts: list[str] = []
        params: list = []
        for child in node.children:
            if isinstance(child, Q):
                sub_sql, sub_params = self.compile_q(meta, child)
                if not sub_sql:
                    continue
                parts.append(f"({sub_sql})")
                params.extend(sub_params)
            else:
                key, value = child
                frag, frag_params = self._leaf(meta, key, value)
                parts.append(frag)
                params.extend(frag_params)
        if not parts:
            return "", []
        joined = f" {node.connector} ".join(parts)
        if node.negated:
            joined = f"NOT ({joined})"
        return joined, params

    def _where_clause(self, meta, wheres: list[Q]) -> tuple[str, list]:
        parts: list[str] = []
        params: list = []
        for node in wheres:
            sql, node_params = self.compile_q(meta, node)
            if sql:
                parts.append(f"({sql})")
                params.extend(node_params)
        if not parts:
            return "", []
        return " WHERE " + " AND ".join(parts), params

    def _order_clause(self, meta, order_by: list[str]) -> str:
        if not order_by:
            return ""
        terms = []
        for spec in order_by:
            descending = spec.startswith("-")
            name = spec[1:] if descending else spec
            field = self._resolve(meta, name)
            terms.append(f"{self.backend.quote(field.column)} {'DESC' if descending else 'ASC'}")
        return " ORDER BY " + ", ".join(terms)

    # -- statements -------------------------------------------------------

    def select(self, meta, *, wheres, order_by, limit, offset, columns) -> tuple[str, list]:
        cols = ", ".join(self.backend.quote(c) for c in columns)
        sql = f"SELECT {cols} FROM {self.backend.quote(meta.table)}"
        where_sql, params = self._where_clause(meta, wheres)
        sql += where_sql
        sql += self._order_clause(meta, order_by)
        if limit is not None:
            sql += f" LIMIT {self.backend.as_limit(limit)}"
        if offset:
            sql += f" OFFSET {self.backend.as_limit(offset)}"
        return sql, params

    def count(self, meta, *, wheres) -> tuple[str, list]:
        sql = f"SELECT COUNT(*) FROM {self.backend.quote(meta.table)}"
        where_sql, params = self._where_clause(meta, wheres)
        return sql + where_sql, params

    def insert(self, meta, columns: list[str], values: list) -> tuple[str, list, bool]:
        quoted = ", ".join(self.backend.quote(c) for c in columns)
        placeholders = self.backend.placeholders(len(values))
        sql = f"INSERT INTO {self.backend.quote(meta.table)} ({quoted}) VALUES ({placeholders})"
        returning = self.backend.supports_returning and meta.pk is not None
        if returning:
            sql += f" RETURNING {self.backend.quote(meta.pk.column)}"
        return sql, list(values), returning

    def update(self, meta, assignments: dict[str, Any], wheres) -> tuple[str, list]:
        if not assignments:
            raise FieldError("update() requires at least one field")
        set_parts = []
        params: list = []
        for column, value in assignments.items():
            set_parts.append(f"{self.backend.quote(column)} = {self.backend.placeholder}")
            params.append(value)
        sql = f"UPDATE {self.backend.quote(meta.table)} SET {', '.join(set_parts)}"
        where_sql, where_params = self._where_clause(meta, wheres)
        sql += where_sql
        params.extend(where_params)
        return sql, params

    def delete(self, meta, wheres) -> tuple[str, list]:
        sql = f"DELETE FROM {self.backend.quote(meta.table)}"
        where_sql, params = self._where_clause(meta, wheres)
        return sql + where_sql, params
