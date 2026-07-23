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


# -- data migrations -----------------------------------------------------------


def test_makedatamigration_writes_a_python_stub(db):
    m = _migrator(db, [Alpha])
    filename = m.makedatamigration("backfill_names")
    assert filename == "0001_backfill_names.py"
    path = m.dir / filename
    assert path.is_file()
    source = path.read_text(encoding="utf-8")
    assert "def forward(conn)" in source
    assert "def reverse(conn)" in source


def test_data_migration_numbered_after_schema_migrations(db):
    m = _migrator(db, [Alpha])
    m.makemigrations("initial")
    filename = m.makedatamigration("backfill")
    assert filename == "0002_backfill.py"


def test_data_migration_applies_and_is_recorded(db):
    m = _migrator(db, [Alpha])
    m.makemigrations("initial")
    m.migrate()

    filename = m.makedatamigration("seed_alpha")
    (m.dir / filename).write_text(
        '''
def forward(conn) -> None:
    from tests.orm.test_migrations import Alpha
    Alpha.objects.create(name="seeded")


def reverse(conn) -> None:
    from tests.orm.test_migrations import Alpha
    Alpha.objects.filter(name="seeded").delete()
''',
        encoding="utf-8",
    )

    applied = m.migrate()
    assert applied == ["0002_seed_alpha"]
    assert m.applied() == ["0001_initial", "0002_seed_alpha"]
    assert Alpha.objects.filter(name="seeded").count() == 1

    # idempotent: already applied, migrate() is a no-op
    assert m.migrate() == []


def test_data_migration_rollback_runs_reverse(db):
    m = _migrator(db, [Alpha])
    m.makemigrations("initial")
    m.migrate()

    filename = m.makedatamigration("seed_alpha")
    (m.dir / filename).write_text(
        '''
def forward(conn) -> None:
    from tests.orm.test_migrations import Alpha
    Alpha.objects.create(name="seeded")


def reverse(conn) -> None:
    from tests.orm.test_migrations import Alpha
    Alpha.objects.filter(name="seeded").delete()
''',
        encoding="utf-8",
    )
    m.migrate()
    assert Alpha.objects.filter(name="seeded").count() == 1

    reverted = m.rollback(1)
    assert reverted == ["0002_seed_alpha"]
    assert Alpha.objects.filter(name="seeded").count() == 0
    assert m.applied() == ["0001_initial"]


def test_data_migration_without_reverse_cannot_roll_back(db):
    m = _migrator(db, [Alpha])
    m.makemigrations("initial")
    m.migrate()

    filename = m.makedatamigration("irreversible")
    m.migrate()  # applies the default stub, whose reverse() raises NotImplementedError

    with pytest.raises(NotImplementedError):
        m.rollback(1)
    # the failed rollback's atomic() block rolled back; still recorded as applied
    assert m.applied() == ["0001_initial", "0002_irreversible"]


def test_data_migration_forward_failure_is_not_recorded(db):
    m = _migrator(db, [Alpha])
    m.makemigrations("initial")
    m.migrate()

    filename = m.makedatamigration("boom")
    (m.dir / filename).write_text(
        '''
def forward(conn) -> None:
    raise RuntimeError("boom")


def reverse(conn) -> None:
    pass
''',
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError):
        m.migrate()
    assert m.applied() == ["0001_initial"]  # the failed migration was not recorded


def test_sqlmigrate_on_data_migration_prints_source_not_sql(db):
    m = _migrator(db, [Alpha])
    m.makemigrations("initial")
    filename = m.makedatamigration("backfill")
    out = m.sqlmigrate("0002")
    assert "data migration" in out
    assert "def forward(conn)" in out


def test_makemigrations_after_data_migration_diffs_against_last_schema(db):
    """A Python data migration carries no schema state; the next
    makemigrations() must still diff against the last JSON migration's state,
    not silently think there's nothing to compare against."""
    m = _migrator(db, [Alpha])
    m.makemigrations("initial")
    m.migrate()
    m.makedatamigration("noop")

    m2 = _migrator(db, [Alpha, Beta])
    filename = m2.makemigrations("add_beta")
    assert filename == "0003_add_beta.json"
    assert m2.applied() == ["0001_initial"]
