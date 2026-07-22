"""SQLite dialect (stdlib ``sqlite3``). First-class target and the test backend."""

from __future__ import annotations

from endocore.orm.backends.base import BaseBackend


class SQLiteBackend(BaseBackend):
    name = "sqlite"
    quote_char = '"'
    placeholder = "?"           # sqlite3 uses qmark paramstyle
    supports_returning = False  # rely on cursor.lastrowid for portability
    materialize_results = True  # lazy cursors + shared conn: fetch before release

    autoincrement_pk_sql = "INTEGER PRIMARY KEY AUTOINCREMENT"

    _TYPES = {
        "IntegerField": "INTEGER",
        "SmallIntegerField": "INTEGER",
        "BigIntegerField": "BIGINT",
        "BooleanField": "INTEGER",
        "FloatField": "REAL",
        "TextField": "TEXT",
        "DateTimeField": "TEXT",
        "DateField": "TEXT",
        "TimeField": "TEXT",
        "DurationField": "BIGINT",
        "UUIDField": "CHAR(32)",
        "JSONField": "TEXT",
        "BinaryField": "BLOB",
        "GenericIPAddressField": "VARCHAR(39)",
        "FileField": "VARCHAR(255)",
    }

    def column_type(self, field) -> str:
        internal = field.internal_type
        if internal == "CharField":
            return f"VARCHAR({int(field.max_length)})"
        if internal == "DecimalField":
            return f"DECIMAL({int(field.max_digits)}, {int(field.decimal_places)})"
        if internal == "ForeignKey":
            return self.fk_column_type(field)
        return self._TYPES.get(internal, "TEXT")

    def auto_pk_sql(self, field) -> str:
        return "INTEGER PRIMARY KEY AUTOINCREMENT"

    def connect(self, **params):
        import sqlite3

        database = params.pop("database", ":memory:")
        # check_same_thread=False so the single app connection survives being
        # touched from a worker thread; Connection serializes access with a lock.
        params.setdefault("check_same_thread", False)
        conn = sqlite3.connect(database, **params)
        conn.execute("PRAGMA foreign_keys = ON")
        # SQLite's LIKE is case-insensitive by default; Postgres LIKE is not.
        # Make them consistent so `contains` is case-sensitive and `icontains`
        # (which uses LOWER on both sides) is case-insensitive everywhere.
        conn.execute("PRAGMA case_sensitive_like = ON")
        # Built-in LOWER() folds ASCII only; override with str.lower so
        # iexact/icontains work for non-Latin text (the compiler lowercases
        # LIKE parameters with str.lower too, keeping both sides aligned).
        conn.create_function(
            "lower", 1, lambda s: s.lower() if isinstance(s, str) else s, deterministic=True
        )
        return conn
