"""Migrations extras: index diffing, showmigrations, sqlmigrate, migrate target."""

from __future__ import annotations

import pytest

from endocore.orm import Model, fields, configure
from endocore.orm.backends import SQLiteBackend
from endocore.orm.connection import get_connection
from endocore.orm.migrations import Migrator, build_state, diff_state


class Widget(Model):
    name = fields.CharField(max_length=20)
    slug = fields.CharField(max_length=20, db_index=True, default="")


@pytest.fixture()
def db(tmp_path):
    configure(backend="sqlite", database=str(tmp_path / "m.db"))
    yield tmp_path
    get_connection().close()


def _m(tmp_path, models=(Widget,)):
    return Migrator(list(models), directory=str(tmp_path / "migrations"))


def test_state_includes_indexes():
    state = build_state([Widget], SQLiteBackend())
    assert "indexes" in state
    assert any("slug" in name for name in state["indexes"])


def test_diff_creates_index():
    forward, reverse = diff_state({"tables": {}, "through": {}, "indexes": {}},
                                  build_state([Widget], SQLiteBackend()), SQLiteBackend())
    assert any("CREATE INDEX" in s for s in forward)
    assert any("DROP INDEX" in s for s in reverse)


def test_showmigrations(db):
    m = _m(db)
    m.makemigrations("initial")
    assert m.showmigrations() == [("0001_initial", False)]
    m.migrate()
    assert m.showmigrations() == [("0001_initial", True)]


def test_sqlmigrate(db):
    m = _m(db)
    m.makemigrations("initial")
    sql = m.sqlmigrate("0001")
    assert "CREATE TABLE" in sql and sql.strip().endswith(";")


def test_sqlmigrate_by_prefix(db):
    m = _m(db)
    m.makemigrations("initial")
    assert "CREATE TABLE" in m.sqlmigrate("0001_initial")


def test_sqlmigrate_missing(db):
    m = _m(db)
    with pytest.raises(FileNotFoundError):
        m.sqlmigrate("9999")


def test_migrate_idempotent(db):
    m = _m(db)
    m.makemigrations("initial")
    assert m.migrate() == ["0001_initial"]
    assert m.migrate() == []


def test_migrate_target_stops(db):
    m = _m(db)
    m.makemigrations("one")
    applied = m.migrate("0001")
    assert applied == ["0001_one"]


def test_index_created_in_db(db):
    m = _m(db)
    m.makemigrations("initial")
    m.migrate()
    conn = get_connection()
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
    names = [r[0] for r in rows]
    assert any("slug" in n for n in names)
