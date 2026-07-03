"""``end check`` — validate the project: broken handlers, duplicate routes."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from endocore.core.discovery import scan_routes


def register(subparsers) -> None:
    parser = subparsers.add_parser("check", help="validate handlers and routes")
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from endocore.core.application import Application

    cwd = Path.cwd()
    problems = 0

    # 1) Duplicate route definitions (same version+method+url across files).
    specs, skipped = scan_routes(cwd / "Api")
    seen = Counter((s.version, s.method, s.url) for s in specs)
    duplicates = [key for key, n in seen.items() if n > 1]
    for version, method, url in duplicates:
        problems += 1
        print(f"[dup]   {method} {url} defined more than once")

    # 2) Handlers that fail to import (booting collects them, never crashes).
    app = Application(app_dir=cwd)
    for err in app.boot_errors:
        problems += 1
        print(f"[error] {err.path}: {err.error!r}")

    # 3) Files skipped by the scanner (informational).
    for sf in skipped:
        print(f"[skip]  {sf.file.relative_to(cwd)}: {sf.reason}")

    if problems == 0:
        print(f"ok: {len(app.registry)} route(s), no problems found")
        return 0
    print(f"\n{problems} problem(s) found")
    return 1
