"""Schema/DDL generation. Enough to stand a database up from models.

Full migrations are out of scope for this beta; this creates and drops tables.
Identifiers are always quoted through the backend; defaults are applied in
Python (``Field.get_default``), not emitted as SQL defaults.
"""

from __future__ import annotations

from endocore.orm.connection import get_connection
from endocore.orm.fields import ForeignKey


def _sql_literal(value) -> str | None:
    """Render a simple default value as a safe SQL literal (or None to skip)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).replace("'", "''")  # escape quotes; developer-provided value
    return f"'{text}'"


def _column_def(backend, field) -> str:
    col = backend.quote(field.column)

    if field.auto_increment:
        return f"{col} {backend.auto_pk_sql(field)}"

    parts = [col, backend.column_type(field)]
    if field.primary_key:
        parts.append("PRIMARY KEY")
    elif field.unique:
        parts.append("UNIQUE")
    parts.append("NULL" if field.null else "NOT NULL")

    # Emit a DB-level DEFAULT for constant defaults so ADD COLUMN works on
    # populated tables (migrations) and inserts are safe.
    if field.has_default() and not callable(field.default) and field.internal_type != "ForeignKey":
        literal = _sql_literal(field.to_db(field.default, backend))
        if literal is not None:
            parts.append(f"DEFAULT {literal}")
    return " ".join(parts)


def _index_statements(model, backend) -> list[str]:
    """CREATE INDEX for every field marked db_index (and every ForeignKey)."""
    from endocore.orm.fields import ForeignKey

    meta = model._meta
    statements: list[str] = []
    for field in meta.fields:
        if field.primary_key or field.unique:
            continue
        if field.db_index or isinstance(field, ForeignKey):
            index_name = f"ix_{meta.table}_{field.column}"
            statements.append(
                f"CREATE INDEX IF NOT EXISTS {backend.quote(index_name)} "
                f"ON {backend.quote(meta.table)} ({backend.quote(field.column)})"
            )

    # Composite indexes declared via Meta.indexes = [["a", "b"], ...].
    for names in meta.indexes:
        cols = [meta.get_field(n).column for n in names]
        index_name = "ix_" + meta.table + "_" + "_".join(cols)
        quoted = ", ".join(backend.quote(c) for c in cols)
        statements.append(
            f"CREATE INDEX IF NOT EXISTS {backend.quote(index_name)} "
            f"ON {backend.quote(meta.table)} ({quoted})"
        )
    return statements


def create_table_sql(model, backend, *, if_not_exists: bool = True) -> str:
    meta = model._meta
    lines = [_column_def(backend, f) for f in meta.fields]

    for field in meta.fields:
        if isinstance(field, ForeignKey):
            ref_meta = field.to._meta
            lines.append(
                f"FOREIGN KEY ({backend.quote(field.column)}) "
                f"REFERENCES {backend.quote(ref_meta.table)} ({backend.quote(ref_meta.pk.column)}) "
                f"ON DELETE {field.on_delete_sql()}"
            )

    # Composite uniqueness declared via Meta.unique_together.
    for names in meta.unique_together:
        cols = ", ".join(backend.quote(meta.get_field(n).column) for n in names)
        lines.append(f"UNIQUE ({cols})")

    exists = "IF NOT EXISTS " if if_not_exists else ""
    body = ",\n    ".join(lines)
    return f"CREATE TABLE {exists}{backend.quote(meta.table)} (\n    {body}\n)"


def through_table_sql(field, backend, *, if_not_exists: bool = True) -> str:
    """DDL for a many-to-many through table (two FK columns, composite PK)."""
    src_meta = field.model._meta
    tgt_meta = field.to._meta
    src, tgt = field.source_column(), field.target_column()
    exists = "IF NOT EXISTS " if if_not_exists else ""
    return (
        f"CREATE TABLE {exists}{backend.quote(field.through_table())} (\n"
        f"    {backend.quote(src)} INTEGER NOT NULL,\n"
        f"    {backend.quote(tgt)} INTEGER NOT NULL,\n"
        f"    PRIMARY KEY ({backend.quote(src)}, {backend.quote(tgt)}),\n"
        f"    FOREIGN KEY ({backend.quote(src)}) REFERENCES "
        f"{backend.quote(src_meta.table)} ({backend.quote(src_meta.pk.column)}) ON DELETE CASCADE,\n"
        f"    FOREIGN KEY ({backend.quote(tgt)}) REFERENCES "
        f"{backend.quote(tgt_meta.table)} ({backend.quote(tgt_meta.pk.column)}) ON DELETE CASCADE\n"
        f")"
    )


def create_table(model, *, using: str = "default", if_not_exists: bool = True) -> None:
    conn = get_connection(using)
    conn.executescript(create_table_sql(model, conn.backend, if_not_exists=if_not_exists))
    for statement in _index_statements(model, conn.backend):
        conn.executescript(statement)


def create_through_tables(model, *, using: str = "default") -> None:
    conn = get_connection(using)
    for field in model._meta.many_to_many:
        conn.executescript(through_table_sql(field, conn.backend))


def drop_table(model, *, using: str = "default", if_exists: bool = True) -> None:
    conn = get_connection(using)
    exists = "IF EXISTS " if if_exists else ""
    conn.executescript(f"DROP TABLE {exists}{conn.backend.quote(model._meta.table)}")


def create_all(*models, using: str = "default") -> None:
    """Create tables for all given models, then their M2M through tables."""
    for model in models:
        create_table(model, using=using)
    for model in models:  # second pass: through tables reference both sides
        create_through_tables(model, using=using)
