"""Base backend — the security-critical layer.

Every dialect goes through here for the two things that decide whether the ORM
is injection-safe:

1. **Identifiers** (table/column names) are validated against a strict pattern
   and quoted with the dialect's quote character, doubling any embedded quote.
   Values are *never* allowed to reach SQL as identifiers.
2. **Values** never touch the SQL string. They are emitted as positional
   placeholders and passed to the driver's parameter binding.

A dialect subclass only customizes tokens and type names; it must not build SQL
by interpolating values.
"""

from __future__ import annotations

import re
from typing import Any

from endocore.orm.exceptions import UnsafeIdentifierError

#: A valid SQL identifier for this ORM: a letter/underscore then word chars.
#: Deliberately strict — model field/table names are plain Python identifiers.
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

#: The escape character used with LIKE so user ``%``/``_`` are treated literally.
LIKE_ESCAPE = "\\"


class BaseBackend:
    """Dialect-agnostic SQL construction primitives. Subclass per database."""

    name: str = "base"
    quote_char: str = '"'
    placeholder: str = "%s"       # positional bind token for the driver
    supports_returning: bool = False
    autoincrement_pk_sql: str = "INTEGER PRIMARY KEY"

    # -- identifiers (injection boundary) --------------------------------

    def quote(self, identifier: str) -> str:
        """Validate then quote an identifier. Raises on anything suspicious."""
        if not isinstance(identifier, str) or not _IDENTIFIER_RE.match(identifier):
            raise UnsafeIdentifierError(f"invalid SQL identifier: {identifier!r}")
        q = self.quote_char
        return q + identifier.replace(q, q + q) + q

    def qualify(self, table: str, column: str) -> str:
        """Quoted ``"table"."column"``."""
        return f"{self.quote(table)}.{self.quote(column)}"

    # -- value placeholders ----------------------------------------------

    def placeholders(self, n: int) -> str:
        """``%s, %s, %s`` (or ``?, ?, ?``) for ``n`` bound values."""
        if n < 0:
            raise ValueError("placeholder count must be non-negative")
        return ", ".join([self.placeholder] * n)

    def as_limit(self, value: Any) -> int:
        """Coerce a LIMIT/OFFSET to a plain int (never interpolate a string)."""
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"LIMIT/OFFSET must be an int, got {value!r}")
        if value < 0:
            raise ValueError("LIMIT/OFFSET must be non-negative")
        return value

    # -- LIKE escaping ----------------------------------------------------

    def like_escape(self, value: str) -> str:
        """Escape LIKE wildcards so user input matches literally."""
        return (
            value.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
            .replace("%", LIKE_ESCAPE + "%")
            .replace("_", LIKE_ESCAPE + "_")
        )

    # -- DDL / typing (overridden per dialect) ---------------------------

    def column_type(self, field) -> str:
        """SQL column type for a field (without PK/NULL clauses)."""
        raise NotImplementedError

    # -- connection (overridden per dialect) -----------------------------

    def connect(self, **params):
        """Open a DB-API 2.0 connection. Imports the driver lazily."""
        raise NotImplementedError

    def last_insert_id(self, cursor, pk_column: str):
        """Return the pk of the row just inserted (dialect-specific)."""
        return cursor.lastrowid
