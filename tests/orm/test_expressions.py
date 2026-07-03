"""F expressions and aggregate SQL generation."""

from __future__ import annotations

import pytest

from endocore.orm import Model, fields, F, Count, Sum, Avg, Min, Max
from endocore.orm.backends import PostgresBackend, SQLiteBackend


class E(Model):
    class Meta:
        table = "e"

    a = fields.IntegerField(default=0)
    b = fields.IntegerField(default=0)


META = E._meta


@pytest.fixture(params=["sqlite", "postgres"])
def backend(request):
    return {"sqlite": SQLiteBackend, "postgres": PostgresBackend}[request.param]()


@pytest.mark.parametrize("expr,sql_contains", [
    (F("a") + 1, '"a" + '),
    (F("a") - 1, '"a" - '),
    (F("a") * 2, '"a" * '),
    (F("a") + F("b"), '"a" + "b"'),
    (F("a") * F("b"), '"a" * "b"'),
    ((F("a") + 1) * 2, '("a" + '),
])
def test_f_as_sql(backend, expr, sql_contains):
    sql, params = expr.as_sql(META, backend)
    assert sql_contains in sql


@pytest.mark.parametrize("expr,nparams", [
    (F("a") + 1, 1),
    (F("a") + F("b"), 0),
    ((F("a") + 1) * 2, 2),
    (F("a") - 5, 1),
])
def test_f_param_count(backend, expr, nparams):
    _, params = expr.as_sql(META, backend)
    assert len(params) == nparams


@pytest.mark.parametrize("agg,func", [
    (Count("*"), "COUNT(*)"),
    (Sum("a"), 'SUM("a")'),
    (Avg("a"), 'AVG("a")'),
    (Min("a"), 'MIN("a")'),
    (Max("b"), 'MAX("b")'),
    (Count("a"), 'COUNT("a")'),
])
def test_aggregate_as_sql(backend, agg, func):
    sql, params = agg.as_sql(META, backend)
    assert sql == func and params == []


@pytest.mark.parametrize("value", [1, 5, 10, -3, 0, 100])
def test_reflected_operators(backend, value):
    sql, params = (value + F("a")).as_sql(META, backend)
    assert '"a"' in sql and value in params
