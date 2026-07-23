"""``endo routes`` — print the resolved route table (method + URL + file)."""

from __future__ import annotations

import argparse
from pathlib import Path


def register(subparsers) -> None:
    parser = subparsers.add_parser("routes", help="list all routes")
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from endocore.core.application import Application

    app = Application(app_dir=Path.cwd())
    specs = app.registry.routes()
    if not specs:
        print("no routes found (is there an Api/ directory with vN handlers?)")
        return 0

    specs.sort(key=lambda s: (s.version, s.url, s.method))
    width = max(len(s.method) for s in specs)
    for spec in specs:
        rel = spec.file.relative_to(app.app_dir)
        print(f"  {spec.method:<{width}}  {spec.url:<40}  {rel}")
    print(f"\n{len(specs)} route(s), {len(app.boot_errors)} file(s) with errors")
    return 0
