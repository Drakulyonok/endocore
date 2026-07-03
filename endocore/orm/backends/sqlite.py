"""SQLite dialect (stdlib ``sqlite3``). First-class target and the test backend."""

from __future__ import annotations

from endocore.orm.backends.base import BaseBackend


class SQLiteBackend(BaseBackend):
    name = "sqlite"
    quote_char = '"'
    placeholder = "?"           # sqlite3 uses qmark paramstyle
    supports_returning = False  # rely on cursor.lastrowid for portability

    autoincrement_pk_sql = "INTEGER PRIMARY KEY AUTOINCREMENT"

    _TYPES = {
        "IntegerField": "INTEGER",
        "BigIntegerField": "BIGINT",
        "BooleanField": "INTEGER",
        "FloatField": "REAL",
        "TextField": "TEXT",
        "DateTimeField": "TEXT",
        "DateField": "TEXT",
    }

    def column_type(self, field) -> str:
        internal = field.internal_type
        if internal == "CharField":
            return f"VARCHAR({int(field.max_length)})"
        if internal == "DecimalField":
            return f"DECIMAL({int(field.max_digits)}, {int(field.decimal_places)})"
        if internal == "ForeignKey":
            return "INTEGER"
        return self._TYPES.get(internal, "TEXT")

    def connect(self, **params):
        import sqlite3

        database = params.pop("database", ":memory:")
        conn = sqlite3.connect(database, **params)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
