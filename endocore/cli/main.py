"""``end`` entry point — argparse dispatch.

    end create <path> [method]     scaffold an endpoint (optionally versioned)
    end dev                        run server + file watcher
    end version create N           copy latest version -> vN (endpoints + local services)
    end version list               list existing versions
    end test                       run user tests (optional)
"""

from __future__ import annotations

import argparse

from endocore import __version__
from endocore.cli.commands import check as check_cmd
from endocore.cli.commands import create as create_cmd
from endocore.cli.commands import dev as dev_cmd
from endocore.cli.commands import doctor as doctor_cmd
from endocore.cli.commands import migrate as migrate_cmd
from endocore.cli.commands import new as new_cmd
from endocore.cli.commands import routes as routes_cmd
from endocore.cli.commands import test as test_cmd
from endocore.cli.commands import version as version_cmd


def build_parser() -> argparse.ArgumentParser:
    """Assemble the ``end`` argument parser and its subcommands."""
    parser = argparse.ArgumentParser(
        prog="end",
        description="EndoCore CLI — the folder tree is the API.",
    )
    parser.add_argument("--version", action="version", version=f"EndoCore {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in (
        new_cmd, create_cmd, dev_cmd, routes_cmd, check_cmd, doctor_cmd,
        migrate_cmd, version_cmd, test_cmd,
    ):
        command.register(subparsers)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code."""
    parser = build_parser()
    # parse_known_args lets `end test -q -k name` pass flags straight to pytest
    # without the argparse REMAINDER quirk that needs a leading `--`.
    args, extra = parser.parse_known_args(argv)
    if getattr(args, "command", None) == "test":
        args.pytest_args = list(getattr(args, "pytest_args", [])) + extra
    elif extra:
        parser.error(f"unrecognized arguments: {' '.join(extra)}")
    return args.func(args)
