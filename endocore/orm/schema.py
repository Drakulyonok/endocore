"""Schema/DDL generation. Enough to stand a database up from models.

Full migrations are out of scope for this beta; this creates and drops tables.
Identifiers are always quoted through the backend; defaults are applied in
Python (``Field.get_default``), not emitted as SQL defaults.
"""

from __future__ import annotations

from endocore.orm.connection import get_connection
from endocore.orm.fields import ForeignKey


def _column_def(backend, field) -> str:
    col = backend.quote(field.column)

    if field.internal_type == "AutoField":
        return f"{col} {backend.autoincrement_pk_sql}"

    parts = [col, backend.column_type(field)]
    if field.primary_key:
        parts.append("PRIMARY KEY")
    elif field.unique:
        parts.append("UNIQUE")
    parts.append("NULL" if field.null else "NOT NULL")
    return " ".join(parts)


def create_table_sql(model, backend, *, if_not_exists: bool = True) -> str:
    meta = model._meta
    lines = [_column_def(backend, f) for f in meta.fields]

    for field in meta.fields:
        if isinstance(field, ForeignKey):
            ref_meta = field.to._meta
            lines.append(
                f"FOREIGN KEY ({backend.quote(field.column)}) "
                f"REFERENCES {backend.quote(ref_meta.table)} ({backend.quote(ref_meta.pk.column)}) "
                f"ON DELETE {field.on_delete}"
            )

    exists = "IF NOT EXISTS " if if_not_exists else ""
    body = ",\n    ".join(lines)
    return f"CREATE TABLE {exists}{backend.quote(meta.table)} (\n    {body}\n)"


def create_table(model, *, using: str = "default", if_not_exists: bool = True) -> None:
    conn = get_connection(using)
    conn.executescript(create_table_sql(model, conn.backend, if_not_exists=if_not_exists))


def drop_table(model, *, using: str = "default", if_exists: bool = True) -> None:
    conn = get_connection(using)
    exists = "IF EXISTS " if if_exists else ""
    conn.executescript(f"DROP TABLE {exists}{conn.backend.quote(model._meta.table)}")


def create_all(*models, using: str = "default") -> None:
    """Create tables for all given models (in the order provided)."""
    for model in models:
        create_table(model, using=using)
