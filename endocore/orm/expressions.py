"""Expressions: ``F`` column references, arithmetic, and aggregates.

These compile to SQL fragments that still bind every literal as a parameter — an
``update(views=F('views') + 1)`` becomes ``"views" = ("views" + ?)`` with ``1``
bound, never inlined.
"""

from __future__ import annotations

from typing import Any


def _resolve_column(meta, name: str) -> str:
    field = meta.pk if name == "pk" else meta.get_field(name)
    return field.column


class Combinable:
    """Mixin giving expressions arithmetic that produces CombinedExpression."""

    def _wrap(self, other: Any) -> "Combinable":
        return other if isinstance(other, Combinable) else Value(other)

    def __add__(self, other): return CombinedExpression(self, "+", self._wrap(other))
    def __sub__(self, other): return CombinedExpression(self, "-", self._wrap(other))
    def __mul__(self, other): return CombinedExpression(self, "*", self._wrap(other))
    def __truediv__(self, other): return CombinedExpression(self, "/", self._wrap(other))
    def __radd__(self, other): return CombinedExpression(self._wrap(other), "+", self)
    def __rsub__(self, other): return CombinedExpression(self._wrap(other), "-", self)
    def __rmul__(self, other): return CombinedExpression(self._wrap(other), "*", self)


class F(Combinable):
    """A reference to a column, e.g. ``F('views')``."""

    def __init__(self, name: str) -> None:
        self.name = name

    def as_sql(self, meta, backend) -> tuple[str, list]:
        return backend.quote(_resolve_column(meta, self.name)), []


class Value(Combinable):
    """A literal bound as a parameter."""

    def __init__(self, value: Any) -> None:
        self.value = value

    def as_sql(self, meta, backend) -> tuple[str, list]:
        return backend.placeholder, [self.value]


class CombinedExpression(Combinable):
    _ALLOWED = {"+", "-", "*", "/"}

    def __init__(self, lhs: Combinable, op: str, rhs: Combinable) -> None:
        if op not in self._ALLOWED:
            raise ValueError(f"unsupported operator {op!r}")
        self.lhs, self.op, self.rhs = lhs, op, rhs

    def as_sql(self, meta, backend) -> tuple[str, list]:
        lsql, lp = self.lhs.as_sql(meta, backend)
        rsql, rp = self.rhs.as_sql(meta, backend)
        return f"({lsql} {self.op} {rsql})", lp + rp


class Aggregate:
    """Base aggregate. ``function`` is a fixed keyword, never user input."""

    function = ""

    def __init__(self, field: str = "*") -> None:
        self.field = field

    def as_sql(self, meta, backend) -> tuple[str, list]:
        if self.field == "*":
            inner = "*"
        else:
            inner = backend.quote(_resolve_column(meta, self.field))
        return f"{self.function}({inner})", []


class Count(Aggregate):
    function = "COUNT"


class Sum(Aggregate):
    function = "SUM"


class Avg(Aggregate):
    function = "AVG"


class Min(Aggregate):
    function = "MIN"


class Max(Aggregate):
    function = "MAX"
