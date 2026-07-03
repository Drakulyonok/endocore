"""``end makemigrations`` / ``end migrate`` / ``end rollback``.

These import the project (so models register and the DB connection is
configured), then drive :class:`endocore.orm.Migrator`.
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path


def _load_project(cwd: Path) -> None:
    """Import handlers (-> models) and every Models/*.py so models register."""
    from endocore.core.application import Application

    Application(app_dir=cwd)  # side effects: import handlers, configure the DB

    models_dir = cwd / "Models"
    if models_dir.is_dir():
        for file in sorted(models_dir.glob("*.py")):
            if file.stem == "__init__":
                continue
            spec = importlib.util.spec_from_file_location(f"Models.{file.stem}", file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                try:
                    spec.loader.exec_module(module)
                except Exception:  # noqa: BLE001 - a bad model file shouldn't kill the CLI
                    pass


def _migrator():
    from endocore.orm import Migrator, get_models
    from endocore.orm.exceptions import ConfigurationError

    try:
        return Migrator(get_models())
    except ConfigurationError as exc:
        print(f"error: {exc}")
        return None


def register(subparsers) -> None:
    make = subparsers.add_parser("makemigrations", help="generate a migration from model changes")
    make.add_argument("name", nargs="?", default=None, help="optional migration name")
    make.add_argument(
        "--rename", action="append", default=[], metavar="TABLE.OLD=NEW",
        help="rename a column (repeatable), e.g. --rename user.fullname=name",
    )
    make.set_defaults(func=run_make)

    mig = subparsers.add_parser("migrate", help="apply pending migrations")
    mig.add_argument("target", nargs="?", default=None, help="migrate up to this migration")
    mig.set_defaults(func=run_migrate)

    rb = subparsers.add_parser("rollback", help="undo the most recent migration(s)")
    rb.add_argument("--steps", type=int, default=1, help="how many migrations to undo (default 1)")
    rb.set_defaults(func=run_rollback)

    show = subparsers.add_parser("showmigrations", help="list migrations and their state")
    show.set_defaults(func=run_show)

    sqlm = subparsers.add_parser("sqlmigrate", help="print a migration's forward SQL")
    sqlm.add_argument("name", help="migration name or prefix (e.g. 0001)")
    sqlm.set_defaults(func=run_sqlmigrate)


def run_make(args: argparse.Namespace) -> int:
    _load_project(Path.cwd())
    migrator = _migrator()
    if migrator is None:
        return 2
    renames = {}
    for spec in getattr(args, "rename", []) or []:
        target, _, new_col = spec.partition("=")
        if not new_col:
            print(f"error: bad --rename {spec!r} (expected TABLE.OLD=NEW)")
            return 2
        renames[target] = new_col
    created = migrator.makemigrations(args.name, renames=renames or None)
    if created is None:
        print("no changes detected")
    else:
        print(f"created migrations/{created}")
    return 0


def run_migrate(args: argparse.Namespace) -> int:
    _load_project(Path.cwd())
    migrator = _migrator()
    if migrator is None:
        return 2
    done = migrator.migrate(getattr(args, "target", None))
    if not done:
        print("no migrations to apply")
    else:
        for name in done:
            print(f"applied {name}")
    return 0


def run_show(args: argparse.Namespace) -> int:
    _load_project(Path.cwd())
    migrator = _migrator()
    if migrator is None:
        return 2
    rows = migrator.showmigrations()
    if not rows:
        print("no migrations yet")
    for name, applied in rows:
        print(f"  [{'x' if applied else ' '}] {name}")
    return 0


def run_sqlmigrate(args: argparse.Namespace) -> int:
    _load_project(Path.cwd())
    migrator = _migrator()
    if migrator is None:
        return 2
    try:
        print(migrator.sqlmigrate(args.name))
    except FileNotFoundError as exc:
        print(f"error: {exc}")
        return 2
    return 0


def run_rollback(args: argparse.Namespace) -> int:
    _load_project(Path.cwd())
    migrator = _migrator()
    if migrator is None:
        return 2
    reverted = migrator.rollback(args.steps)
    if not reverted:
        print("nothing to roll back")
    else:
        for name in reverted:
            print(f"rolled back {name}")
    return 0
