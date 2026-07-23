"""``endo dev`` — run the server with in-process auto-reload.

Serves ``endocore.asgi:create_app`` (dev mode). The framework's own watchfiles
watcher rebuilds the route tree in-process on change (TZ §4.1) — no process
restart — so uvicorn's reloader is not used. ``--no-reload`` turns the watcher
off; ``--default-version latest`` resolves version-less paths to the newest one.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def register(subparsers) -> None:
    parser = subparsers.add_parser("dev", help="run the dev server + in-process watcher")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-reload", action="store_true", help="disable the in-process watcher")
    parser.add_argument(
        "--default-version", default=None,
        help="resolve a version-less path to this policy (e.g. 'latest')",
    )
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    import uvicorn

    cwd = Path.cwd()
    if not (cwd / "Api").is_dir():
        print(f"warning: no Api/ directory in {cwd} — no routes will be served")

    os.environ["ENDOCORE_DEV"] = "0" if args.no_reload else "1"
    if args.default_version:
        os.environ["ENDOCORE_DEFAULT_VERSION"] = args.default_version

    # No uvicorn --reload: our in-process watcher rebuilds routes without a restart.
    uvicorn.run("endocore.asgi:create_app", factory=True, host=args.host, port=args.port)
    return 0
