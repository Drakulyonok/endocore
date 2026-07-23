"""Migrations with rollback.

State-based, forward+reverse migrations. ``makemigrations`` diffs the current
models against the last recorded state and writes a JSON file with the SQL to
apply (``forward``) and to undo (``reverse``) the change, plus the new state.
``migrate`` applies pending files; ``rollback`` undoes the most recent ones.

Schema changes (create/drop tables, add/drop columns, M2M through tables,
column renames) are auto-generated JSON files. Data transformations that
don't fit "diff the schema" — backfilling a new column, reshaping a JSON blob,
merging two tables' worth of rows — are Python files (``makedatamigration``):
a ``forward(conn)``/``reverse(conn)`` pair that runs in the *same* numbered
history as the JSON ones, so ``migrate``/``rollback``/``showmigrations`` see
and order them together instead of a one-off script run by hand and hoped to
land in the right order relative to the schema change it depends on.

Migrations are generated for the project's configured dialect.
"""

from __future__ import annotations

import datetime
import importlib.util
import json
from pathlib import Path

from endocore.orm.connection import get_connection
from endocore.orm.model import get_models
from endocore.orm.schema import create_table_sql, index_specs, through_table_sql, _column_def

_MIGRATIONS_TABLE = "endocore_migrations"


def build_state(models, backend) -> dict:
    """Serializable snapshot of the schema implied by ``models``."""
    tables: dict = {}
    through: dict = {}
    indexes: dict = {}
    for model in models:
        meta = model._meta
        coldefs = {f.column: _column_def(backend, f) for f in meta.fields}
        tables[meta.table] = {
            "coldefs": coldefs,
            "create": create_table_sql(model, backend),
        }
        for field in meta.many_to_many:
            through[field.through_table()] = {"create": through_table_sql(field, backend)}
        for name, sql in index_specs(model, backend).items():
            indexes[name] = {"create": sql}
    return {"tables": tables, "through": through, "indexes": indexes}


def _rebuild(table: str, create_sql: str, from_cols: dict, to_cols: dict, q) -> list[str]:
    """Recreate ``table`` with a new schema, copying columns common to both.

    The portable way to change a column definition (SQLite can't ALTER COLUMN):
    create a new table, copy data, drop the old, rename the new into place.
    """
    temp = table + "__new"
    temp_create = create_sql.replace(q(table), q(temp), 1)
    common = [c for c in to_cols if c in from_cols]
    cols_sql = ", ".join(q(c) for c in common)
    return [
        temp_create,
        f"INSERT INTO {q(temp)} ({cols_sql}) SELECT {cols_sql} FROM {q(table)}",
        f"DROP TABLE {q(table)}",
        f"ALTER TABLE {q(temp)} RENAME TO {q(table)}",
    ]


def diff_state(old: dict, new: dict, backend) -> tuple[list[str], list[str]]:
    """Return (forward_sql, reverse_sql) turning ``old`` into ``new``."""
    forward: list[str] = []
    reverse: list[str] = []

    def q(name: str) -> str:
        return backend.quote(name)

    old_tables, new_tables = old.get("tables", {}), new.get("tables", {})

    # Created tables.
    for table in new_tables:
        if table not in old_tables:
            forward.append(new_tables[table]["create"])
            reverse.insert(0, f"DROP TABLE {q(table)}")

    # Dropped tables.
    for table in old_tables:
        if table not in new_tables:
            forward.append(f"DROP TABLE {q(table)}")
            reverse.insert(0, old_tables[table]["create"])

    # Column changes on surviving tables.
    for table in new_tables:
        if table not in old_tables:
            continue
        old_cols = old_tables[table]["coldefs"]
        new_cols = new_tables[table]["coldefs"]
        # A changed definition of an existing column can't be done with a simple
        # ALTER portably (SQLite), so rebuild the whole table.
        altered = any(c in old_cols and c in new_cols and old_cols[c] != new_cols[c]
                      for c in new_cols)
        if altered:
            forward.extend(_rebuild(table, new_tables[table]["create"], old_cols, new_cols, q))
            reverse = _rebuild(table, old_tables[table]["create"], new_cols, old_cols, q) + reverse
            continue
        for col, ddl in new_cols.items():
            if col not in old_cols:
                forward.append(f"ALTER TABLE {q(table)} ADD COLUMN {ddl}")
                reverse.insert(0, f"ALTER TABLE {q(table)} DROP COLUMN {q(col)}")
        for col, ddl in old_cols.items():
            if col not in new_cols:
                forward.append(f"ALTER TABLE {q(table)} DROP COLUMN {q(col)}")
                reverse.insert(0, f"ALTER TABLE {q(table)} ADD COLUMN {ddl}")

    # Through (M2M) tables.
    old_through, new_through = old.get("through", {}), new.get("through", {})
    for name in new_through:
        if name not in old_through:
            forward.append(new_through[name]["create"])
            reverse.insert(0, f"DROP TABLE {q(name)}")
    for name in old_through:
        if name not in new_through:
            forward.append(f"DROP TABLE {q(name)}")
            reverse.insert(0, old_through[name]["create"])

    # Indexes.
    old_ix, new_ix = old.get("indexes", {}), new.get("indexes", {})
    for name in new_ix:
        if name not in old_ix:
            forward.append(new_ix[name]["create"])
            reverse.insert(0, f"DROP INDEX {q(name)}")
    for name in old_ix:
        if name not in new_ix:
            forward.append(f"DROP INDEX {q(name)}")
            reverse.insert(0, old_ix[name]["create"])

    return forward, reverse


class Migrator:
    def __init__(self, models=None, *, using: str = "default", directory: str = "migrations") -> None:
        self.models = list(models) if models is not None else get_models()
        self.using = using
        self.dir = Path(directory)
        self.conn = get_connection(using)
        self.backend = self.conn.backend

    # -- recorder ---------------------------------------------------------

    def _ensure_table(self) -> None:
        self.conn.executescript(
            f"CREATE TABLE IF NOT EXISTS {self.backend.quote(_MIGRATIONS_TABLE)} "
            f"({self.backend.quote('name')} VARCHAR(255) PRIMARY KEY, "
            f"{self.backend.quote('applied_at')} VARCHAR(64))"
        )

    def applied(self) -> list[str]:
        self._ensure_table()
        sql = f"SELECT {self.backend.quote('name')} FROM {self.backend.quote(_MIGRATIONS_TABLE)} " \
              f"ORDER BY {self.backend.quote('name')}"
        return [row[0] for row in self.conn.execute(sql).fetchall()]

    def _record(self, name: str) -> None:
        ph = self.backend.placeholder
        sql = (
            f"INSERT INTO {self.backend.quote(_MIGRATIONS_TABLE)} "
            f"({self.backend.quote('name')}, {self.backend.quote('applied_at')}) VALUES ({ph}, {ph})"
        )
        self.conn.execute(sql, [name, datetime.datetime.now().isoformat()], write=True)

    def _unrecord(self, name: str) -> None:
        sql = f"DELETE FROM {self.backend.quote(_MIGRATIONS_TABLE)} " \
              f"WHERE {self.backend.quote('name')} = {self.backend.placeholder}"
        self.conn.execute(sql, [name], write=True)

    # -- files ------------------------------------------------------------

    def _files(self) -> list[Path]:
        if not self.dir.is_dir():
            return []
        files = list(self.dir.glob("[0-9]*.json")) + list(self.dir.glob("[0-9]*.py"))
        return sorted(files, key=lambda p: p.stem)

    def _last_state(self) -> dict:
        empty = {"tables": {}, "through": {}, "indexes": {}}
        # Python data migrations carry no schema state; walk back to the last
        # JSON (schema) migration, which is the one that does.
        for file in reversed(self._files()):
            if file.suffix == ".json":
                return json.loads(file.read_text(encoding="utf-8")).get("state", empty)
        return empty

    def _load_module(self, file: Path):
        spec = importlib.util.spec_from_file_location(f"_endocore_migration_{file.stem}", file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    # -- commands ---------------------------------------------------------

    def makemigrations(self, name: str | None = None, renames: dict | None = None) -> str | None:
        new_state = build_state(self.models, self.backend)
        old_state = self._last_state()
        q = self.backend.quote

        rename_forward: list[str] = []
        rename_reverse: list[str] = []
        if renames:
            import copy as _copy

            old_state = _copy.deepcopy(old_state)
            for target, new_col in renames.items():
                table, _, old_col = target.partition(".")
                tdef = old_state.get("tables", {}).get(table)
                if tdef and old_col in tdef["coldefs"]:
                    ddl = tdef["coldefs"].pop(old_col)
                    tdef["coldefs"][new_col] = ddl.replace(q(old_col), q(new_col), 1)
                rename_forward.append(
                    f"ALTER TABLE {q(table)} RENAME COLUMN {q(old_col)} TO {q(new_col)}"
                )
                rename_reverse.insert(
                    0, f"ALTER TABLE {q(table)} RENAME COLUMN {q(new_col)} TO {q(old_col)}"
                )

        forward, reverse = diff_state(old_state, new_state, self.backend)
        forward = rename_forward + forward
        reverse = reverse + rename_reverse
        if not forward:
            return None
        self.dir.mkdir(parents=True, exist_ok=True)
        number = len(self._files()) + 1
        filename = f"{number:04d}_{name or 'auto'}.json"
        payload = {"name": filename[:-5], "forward": forward, "reverse": reverse, "state": new_state}
        (self.dir / filename).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return filename

    def makedatamigration(self, name: str) -> str:
        """Write an empty Python data migration: ``forward(conn)``/``reverse(conn)``,
        numbered into the same history as the schema (JSON) migrations."""
        self.dir.mkdir(parents=True, exist_ok=True)
        number = len(self._files()) + 1
        filename = f"{number:04d}_{name}.py"
        template = f'''"""Data migration: {name}.

Runs inside its own atomic() block, in the same numbered migration history as
schema changes (migrate/rollback/showmigrations all see it). Import and use
your models directly -- the app is already configured by the time this runs.
"""


def forward(conn) -> None:
    ...


def reverse(conn) -> None:
    raise NotImplementedError("this data migration cannot be reversed")
'''
        (self.dir / filename).write_text(template, encoding="utf-8")
        return filename

    def migrate(self, target: str | None = None) -> list[str]:
        """Apply pending migrations (up to and including ``target`` if given)."""
        applied = set(self.applied())
        done: list[str] = []
        for file in self._files():
            name = file.stem
            if name not in applied:
                if file.suffix == ".py":
                    module = self._load_module(file)
                    with self.conn.atomic():
                        module.forward(self.conn)
                        self._record(name)
                else:
                    data = json.loads(file.read_text(encoding="utf-8"))
                    with self.conn.atomic():
                        for statement in data["forward"]:
                            self.conn.executescript(statement)
                        self._record(name)
                done.append(name)
            if target is not None and (name == target or name.startswith(target)):
                break
        return done

    def showmigrations(self) -> list[tuple[str, bool]]:
        """Every migration file with whether it has been applied."""
        applied = set(self.applied())
        return [(f.stem, f.stem in applied) for f in self._files()]

    def sqlmigrate(self, name: str) -> str:
        """The forward SQL of a migration (matched by name/prefix); for a
        Python data migration, its source instead (there's no SQL to show)."""
        for file in self._files():
            if file.stem == name or file.stem.startswith(name):
                if file.suffix == ".py":
                    return f"-- data migration (Python), not SQL: {file}\n\n" + file.read_text(encoding="utf-8")
                data = json.loads(file.read_text(encoding="utf-8"))
                return ";\n".join(data["forward"]) + ";"
        raise FileNotFoundError(f"no migration matching {name!r}")

    def rollback(self, steps: int = 1) -> list[str]:
        applied = self.applied()
        targets = list(reversed(applied[-steps:])) if steps > 0 else []
        reverted: list[str] = []
        for name in targets:
            json_file = self.dir / f"{name}.json"
            py_file = self.dir / f"{name}.py"
            if py_file.is_file():
                module = self._load_module(py_file)
                if not hasattr(module, "reverse"):
                    raise RuntimeError(f"data migration {name!r} has no reverse(); cannot roll back")
                with self.conn.atomic():
                    module.reverse(self.conn)
                    self._unrecord(name)
            elif json_file.is_file():
                data = json.loads(json_file.read_text(encoding="utf-8"))
                with self.conn.atomic():
                    for statement in data["reverse"]:
                        self.conn.executescript(statement)
                    self._unrecord(name)
            else:
                raise FileNotFoundError(f"migration file for {name!r} is missing; cannot roll back")
            reverted.append(name)
        return reverted
