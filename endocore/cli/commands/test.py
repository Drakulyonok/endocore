"""``endo test`` — run the user's tests (optional convenience).

The framework never generates tests; the user writes them under ``Tests/``. This
just shells out to pytest if it is installed, with the application directory on
``sys.path`` so tests can ``from Api.vN... import ...`` / ``from Services...``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def register(subparsers) -> None:
    parser = subparsers.add_parser("test", help="run user tests via pytest")
    # Flags like -q / -k are collected by main() via parse_known_args and appended.
    parser.add_argument(
        "pytest_args", nargs="*",
        help="extra arguments passed straight to pytest (e.g. -q -k name)",
    )
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    try:
        import pytest
    except ImportError:
        print("error: pytest is not installed (pip install pytest)")
        return 1

    cwd = Path.cwd()
    # Same rule as the app loader: the app root is importable (namespace packages).
    if str(cwd) not in sys.path:
        sys.path.insert(0, str(cwd))

    extra = list(args.pytest_args)
    if extra and extra[0] == "--":  # argparse keeps a leading -- with REMAINDER
        extra = extra[1:]

    target = ["Tests"] if (cwd / "Tests").is_dir() else ["."]
    return pytest.main(extra or target)
