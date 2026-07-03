"""PostgreSQL dialect (``psycopg`` 3). Driver imported lazily on connect."""

from __future__ import annotations

from endocore.orm.backends.base import BaseBackend


class PostgresBackend(BaseBackend):
    name = "postgres"
    quote_char = '"'
    placeholder = "%s"          # psycopg uses pyformat (%s) for positional binds
    supports_returning = True   # INSERT ... RETURNING id

    autoincrement_pk_sql = "SERIAL PRIMARY KEY"

    _TYPES = {
        "IntegerField": "INTEGER",
        "BigIntegerField": "BIGINT",
        "BooleanField": "BOOLEAN",
        "FloatField": "DOUBLE PRECISION",
        "TextField": "TEXT",
        "DateTimeField": "TIMESTAMP",
        "DateField": "DATE",
    }

    def column_type(self, field) -> str:
        internal = field.internal_type
        if internal == "CharField":
            return f"VARCHAR({int(field.max_length)})"
        if internal == "DecimalField":
            return f"NUMERIC({int(field.max_digits)}, {int(field.decimal_places)})"
        if internal == "ForeignKey":
            return "INTEGER"
        return self._TYPES.get(internal, "TEXT")

    def connect(self, **params):
        import psycopg  # lazy: only needed when a Postgres connection is opened

        return psycopg.connect(**params)

    def last_insert_id(self, cursor, pk_column: str):
        # With supports_returning the compiler adds RETURNING <pk>; read it here.
        row = cursor.fetchone()
        return row[0] if row else None
