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
    make.set_defaults(func=run_make)

    mig = subparsers.add_parser("migrate", help="apply pending migrations")
    mig.set_defaults(func=run_migrate)

    rb = subparsers.add_parser("rollback", help="undo the most recent migration(s)")
    rb.add_argument("--steps", type=int, default=1, help="how many migrations to undo (default 1)")
    rb.set_defaults(func=run_rollback)


def run_make(args: argparse.Namespace) -> int:
    _load_project(Path.cwd())
    migrator = _migrator()
    if migrator is None:
        return 2
    created = migrator.makemigrations(args.name)
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
    done = migrator.migrate()
    if not done:
        print("no migrations to apply")
    else:
        for name in done:
            print(f"applied {name}")
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
