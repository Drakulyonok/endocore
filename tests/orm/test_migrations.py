"""Migrations: state, diff, make/migrate/rollback."""

from __future__ import annotations

import pytest

from endocore.orm import Model, fields, configure
from endocore.orm.backends import SQLiteBackend
from endocore.orm.connection import get_connection
from endocore.orm.migrations import Migrator, build_state, diff_state


class Alpha(Model):
    name = fields.CharField(max_length=20)


class Beta(Model):
    n = fields.IntegerField(default=0)
    alpha = fields.ForeignKey(Alpha, null=True, default=None)


@pytest.fixture()
def db(tmp_path):
    configure(backend="sqlite", database=str(tmp_path / "m.db"))
    yield tmp_path
    get_connection().close()


def _migrator(tmp_path, models):
    return Migrator(models, directory=str(tmp_path / "migrations"))


def test_build_state_shape():
    state = build_state([Alpha], SQLiteBackend())
    assert "alpha" in state["tables"]
    assert "name" in state["tables"]["alpha"]["coldefs"]


def test_diff_new_table():
    forward, reverse = diff_state({"tables": {}, "through": {}},
                                  build_state([Alpha], SQLiteBackend()), SQLiteBackend())
    assert any("CREATE TABLE" in s for s in forward)
    assert any("DROP TABLE" in s for s in reverse)


def test_diff_add_column():
    b = SQLiteBackend()
    old = build_state([Alpha], b)

    class Alpha2(Model):
        class Meta:
            table = "alpha"
        name = fields.CharField(max_length=20)
        extra = fields.IntegerField(default=0)

    new = build_state([Alpha2], b)
    forward, reverse = diff_state(old, new, b)
    assert any("ADD COLUMN" in s for s in forward)
    assert any("DROP COLUMN" in s for s in reverse)


def test_make_migrate_rollback(db):
    m = _migrator(db, [Alpha, Beta])
    assert m.makemigrations("initial") is not None
    assert m.applied() == []
    applied = m.migrate()
    assert applied == ["0001_initial"]
    assert m.applied() == ["0001_initial"]
    # tables really exist
    Alpha.objects.create(name="x")
    assert Alpha.objects.count() == 1
    # rollback drops them
    assert m.rollback(1) == ["0001_initial"]
    assert m.applied() == []


def test_no_change_returns_none(db):
    m = _migrator(db, [Alpha])
    m.makemigrations("a")
    assert m.makemigrations("b") is None  # nothing changed


def test_migrate_is_idempotent(db):
    m = _migrator(db, [Alpha])
    m.makemigrations("initial")
    m.migrate()
    assert m.migrate() == []  # already applied


@pytest.mark.parametrize("steps", [1, 2, 3])
def test_rollback_steps(db, steps):
    m = _migrator(db, [Alpha])
    # create several migrations by evolving the model via extra tables
    m.makemigrations("one")
    m.migrate()
    # second migration: add Beta
    m2 = _migrator(db, [Alpha, Beta])
    m2.makemigrations("two")
    m2.migrate()
    reverted = m2.rollback(steps)
    assert len(reverted) == min(steps, 2)
