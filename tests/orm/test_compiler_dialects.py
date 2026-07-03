"""The compiler emits correct, parameterized SQL per dialect."""

from __future__ import annotations

from endocore.orm import Model, fields, Q
from endocore.orm.backends import PostgresBackend, SQLiteBackend
from endocore.orm.compiler import SQLCompiler


class Widget(Model):
    class Meta:
        table = "widget"

    name = fields.CharField(max_length=10)
    qty = fields.IntegerField(default=0)


META = Widget._meta
COLS = [f.column for f in META.fields]  # ["id", "name", "qty"]


def test_select_sqlite():
    sql, params = SQLCompiler(SQLiteBackend()).select(
        META, wheres=[Q(qty__gte=5)], order_by=["-name"], limit=10, offset=5, columns=COLS
    )
    assert sql == (
        'SELECT "id", "name", "qty" FROM "widget" '
        'WHERE ("qty" >= ?) ORDER BY "name" DESC LIMIT 10 OFFSET 5'
    )
    assert params == [5]


def test_select_postgres_uses_pyformat():
    sql, params = SQLCompiler(PostgresBackend()).select(
        META, wheres=[Q(qty__gte=5)], order_by=[], limit=None, offset=0, columns=COLS
    )
    assert sql == 'SELECT "id", "name", "qty" FROM "widget" WHERE ("qty" >= %s)'
    assert params == [5]


def test_insert_dialects():
    sqlite_sql, _, ret_s = SQLCompiler(SQLiteBackend()).insert(META, ["name", "qty"], ["x", 5])
    assert sqlite_sql == 'INSERT INTO "widget" ("name", "qty") VALUES (?, ?)'
    assert ret_s is False

    pg_sql, _, ret_p = SQLCompiler(PostgresBackend()).insert(META, ["name", "qty"], ["x", 5])
    assert pg_sql == 'INSERT INTO "widget" ("name", "qty") VALUES (%s, %s) RETURNING "id"'
    assert ret_p is True


def test_update_and_delete():
    c = SQLCompiler(SQLiteBackend())
    usql, uparams = c.update(META, {"qty": 7}, [Q(pk=1)])
    assert usql == 'UPDATE "widget" SET "qty" = ? WHERE ("id" = ?)'
    assert uparams == [7, 1]

    dsql, dparams = c.delete(META, [Q(name="z")])
    assert dsql == 'DELETE FROM "widget" WHERE ("name" = ?)'
    assert dparams == ["z"]


def test_in_expands_placeholders():
    sql, params = SQLCompiler(SQLiteBackend()).select(
        META, wheres=[Q(qty__in=[1, 2, 3])], order_by=[], limit=None, offset=0, columns=COLS
    )
    assert 'WHERE ("qty" IN (?, ?, ?))' in sql
    assert params == [1, 2, 3]


def test_q_or_grouping():
    sql, params = SQLCompiler(SQLiteBackend()).select(
        META, wheres=[Q(qty__lt=1) | Q(qty__gt=9)], order_by=[], limit=None, offset=0, columns=COLS
    )
    assert 'WHERE (("qty" < ?) OR ("qty" > ?))' in sql
    assert params == [1, 9]
