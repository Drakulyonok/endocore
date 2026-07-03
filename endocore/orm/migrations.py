"""Migrations with rollback.

State-based, forward+reverse migrations. ``makemigrations`` diffs the current
models against the last recorded state and writes a JSON file with the SQL to
apply (``forward``) and to undo (``reverse``) the change, plus the new state.
``migrate`` applies pending files; ``rollback`` undoes the most recent ones.

Scope (beta): create/drop tables, add/drop columns, and M2M through tables.
Column renames and data migrations are out of scope (a rename reads as
drop+add). Migrations are generated for the project's configured dialect.
"""

from __future__ import annotations

import datetime
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
        return sorted(self.dir.glob("[0-9]*.json"))

    def _last_state(self) -> dict:
        empty = {"tables": {}, "through": {}, "indexes": {}}
        files = self._files()
        if not files:
            return empty
        return json.loads(files[-1].read_text(encoding="utf-8")).get("state", empty)

    # -- commands ---------------------------------------------------------

    def makemigrations(self, name: str | None = None) -> str | None:
        new_state = build_state(self.models, self.backend)
        forward, reverse = diff_state(self._last_state(), new_state, self.backend)
        if not forward:
            return None
        self.dir.mkdir(parents=True, exist_ok=True)
        number = len(self._files()) + 1
        filename = f"{number:04d}_{name or 'auto'}.json"
        payload = {"name": filename[:-5], "forward": forward, "reverse": reverse, "state": new_state}
        (self.dir / filename).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return filename

    def migrate(self, target: str | None = None) -> list[str]:
        """Apply pending migrations (up to and including ``target`` if given)."""
        applied = set(self.applied())
        done: list[str] = []
        for file in self._files():
            name = file.stem
            if name not in applied:
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
        """The forward SQL of a migration (matched by name/prefix)."""
        for file in self._files():
            if file.stem == name or file.stem.startswith(name):
                data = json.loads(file.read_text(encoding="utf-8"))
                return ";\n".join(data["forward"]) + ";"
        raise FileNotFoundError(f"no migration matching {name!r}")

    def rollback(self, steps: int = 1) -> list[str]:
        applied = self.applied()
        targets = list(reversed(applied[-steps:])) if steps > 0 else []
        reverted: list[str] = []
        for name in targets:
            file = self.dir / f"{name}.json"
            if not file.is_file():
                raise FileNotFoundError(f"migration file for {name!r} is missing; cannot roll back")
            data = json.loads(file.read_text(encoding="utf-8"))
            with self.conn.atomic():
                for statement in data["reverse"]:
                    self.conn.executescript(statement)
                self._unrecord(name)
            reverted.append(name)
        return reverted
