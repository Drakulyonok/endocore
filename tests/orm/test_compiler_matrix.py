"""Compiler emits correct parameterized SQL for both dialects, every lookup."""

from __future__ import annotations

import pytest

from endocore.orm import Model, fields, Q
from endocore.orm.backends import PostgresBackend, SQLiteBackend
from endocore.orm.compiler import SQLCompiler


class M(Model):
    class Meta:
        table = "m"

    name = fields.CharField(max_length=20)
    n = fields.IntegerField(default=0)


META = M._meta
BACKENDS = {"sqlite": SQLiteBackend, "postgres": PostgresBackend}
PLACEHOLDER = {"sqlite": "?", "postgres": "%s"}


@pytest.fixture(params=["sqlite", "postgres"])
def backend(request):
    return BACKENDS[request.param](), request.param


LEAF_CASES = [
    ("n", 5, '"n" = {p}', [5]),
    ("n__gt", 5, '"n" > {p}', [5]),
    ("n__gte", 5, '"n" >= {p}', [5]),
    ("n__lt", 5, '"n" < {p}', [5]),
    ("n__lte", 5, '"n" <= {p}', [5]),
    ("name__iexact", "x", 'LOWER("name") = LOWER({p})', ["x"]),
    ("n__range", (1, 9), '"n" BETWEEN {p} AND {p}', [1, 9]),
]


@pytest.mark.parametrize("key,value,sql_tmpl,params", LEAF_CASES)
def test_leaf_sql(backend, key, value, sql_tmpl, params):
    b, name = backend
    sql, got_params = SQLCompiler(b)._leaf(META, key, value)
    assert sql == sql_tmpl.format(p=PLACEHOLDER[name])
    assert got_params == params


@pytest.mark.parametrize("n", [1, 2, 3, 5, 8])
def test_in_expands_placeholders(backend, n):
    b, name = backend
    sql, params = SQLCompiler(b)._leaf(META, "n__in", list(range(n)))
    assert sql == f'"n" IN ({", ".join([PLACEHOLDER[name]] * n)})'
    assert params == list(range(n))


@pytest.mark.parametrize("truth,expected", [(True, "IS NULL"), (False, "IS NOT NULL")])
def test_isnull(backend, truth, expected):
    b, _ = backend
    sql, params = SQLCompiler(b)._leaf(META, "n__isnull", truth)
    assert sql == f'"n" {expected}' and params == []


@pytest.mark.parametrize("lookup", ["contains", "icontains", "startswith", "endswith"])
def test_like_has_escape(backend, lookup):
    b, _ = backend
    sql, params = SQLCompiler(b)._leaf(META, f"name__{lookup}", "val")
    assert "LIKE" in sql and "ESCAPE" in sql
    assert len(params) == 1


@pytest.mark.parametrize("distinct", [False, True])
def test_select_shape(backend, distinct):
    b, name = backend
    sql, params = SQLCompiler(b).select(
        META, wheres=[Q(n__gte=1)], order_by=["-n"], limit=5, offset=2,
        columns=["id", "name", "n"], distinct=distinct,
    )
    kw = "SELECT DISTINCT" if distinct else "SELECT"
    assert sql.startswith(f'{kw} "id", "name", "n" FROM "m"')
    assert "ORDER BY \"n\" DESC" in sql and "LIMIT 5" in sql and "OFFSET 2" in sql
    assert params == [1]


def test_insert_returning_only_postgres(backend):
    b, name = backend
    sql, params, returning = SQLCompiler(b).insert(META, ["name", "n"], ["x", 1])
    assert ("RETURNING" in sql) is (name == "postgres")
    assert returning is (name == "postgres")


@pytest.mark.parametrize("bad", ["a b", "a;b", 'a"b', "1a", "", "a-b", "select*"])
def test_bad_identifier_rejected(backend, bad):
    from endocore.orm.exceptions import UnsafeIdentifierError

    b, _ = backend
    with pytest.raises(UnsafeIdentifierError):
        b.quote(bad)


@pytest.mark.parametrize("good", ["a", "abc", "a1", "_x", "user_name", "Table1"])
def test_good_identifier_quoted(backend, good):
    b, _ = backend
    assert b.quote(good) == f'"{good}"'


@pytest.mark.parametrize("bad", ["5; DROP", "1.5", 3.5, True, -1, "abc"])
def test_limit_coercion_rejects(backend, bad):
    b, _ = backend
    with pytest.raises((ValueError, TypeError)):
        b.as_limit(bad)


@pytest.mark.parametrize("good", [0, 1, 5, 100, 999999])
def test_limit_coercion_accepts(backend, good):
    b, _ = backend
    assert b.as_limit(good) == good
