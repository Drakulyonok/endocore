"""Migration column alter (table rebuild) and rename."""

from __future__ import annotations

import json

import pytest

from endocore.orm import Model, fields, configure
from endocore.orm.backends import SQLiteBackend
from endocore.orm.connection import get_connection
from endocore.orm.migrations import Migrator, _rebuild, build_state, diff_state


def test_rebuild_statements():
    q = SQLiteBackend().quote
    stmts = _rebuild("t", 'CREATE TABLE IF NOT EXISTS "t" ("a" INT, "b" INT)',
                     {"a": "x", "b": "y"}, {"a": "x2", "b": "y"}, q)
    assert any("__new" in s for s in stmts)
    assert any(s.startswith("INSERT INTO") for s in stmts)
    assert any("DROP TABLE" in s for s in stmts)
    assert any("RENAME TO" in s for s in stmts)


def test_diff_detects_altered_column():
    b = SQLiteBackend()

    class A(Model):
        class Meta:
            table = "amod"
        v = fields.IntegerField(default=0)

    old = build_state([A], b)

    class A2(Model):
        class Meta:
            table = "amod"
        v = fields.BigIntegerField(default=0)

    forward, reverse = diff_state(old, build_state([A2], b), b)
    assert any("__new" in s for s in forward)


@pytest.fixture()
def db(tmp_path):
    configure(backend="sqlite", database=str(tmp_path / "m.db"))
    yield tmp_path
    get_connection().close()


class Gadget(Model):
    name = fields.CharField(max_length=20)
    size = fields.IntegerField(default=0)


def test_alter_preserves_data(db):
    m = Migrator([Gadget], directory=str(db / "migrations"))
    m.makemigrations("initial")
    m.migrate()
    Gadget.objects.create(name="a", size=5)

    class Gadget2(Model):
        class Meta:
            table = "gadget"
        name = fields.CharField(max_length=20)
        size = fields.BigIntegerField(default=0)

    m2 = Migrator([Gadget2], directory=str(db / "migrations"))
    f = m2.makemigrations("alter")
    assert f is not None
    m2.migrate()
    assert Gadget2.objects.get(name="a").size == 5  # data survived the rebuild
    m2.rollback(1)
    assert Gadget2.objects.get(name="a").size == 5  # and the rollback


def test_rename_column(db):
    m = Migrator([Gadget], directory=str(db / "migrations"))
    m.makemigrations("initial")
    m.migrate()
    Gadget.objects.create(name="a", size=1)

    class Gadget3(Model):
        class Meta:
            table = "gadget"
        title = fields.CharField(max_length=20)
        size = fields.IntegerField(default=0)

    m3 = Migrator([Gadget3], directory=str(db / "migrations"))
    f = m3.makemigrations("rename", renames={"gadget.name": "title"})
    assert f is not None
    forward = json.loads((db / "migrations" / f).read_text())["forward"]
    assert any("RENAME COLUMN" in s for s in forward)
    m3.migrate()
    assert Gadget3.objects.get(title="a").size == 1
    m3.rollback(1)
    assert Gadget.objects.get(name="a").size == 1
