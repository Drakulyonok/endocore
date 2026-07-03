"""``end dev`` — run the server with a file watcher.

Runs uvicorn against the ``endocore.asgi:create_app`` factory with ``--reload``
so the route tree is rebuilt on handler changes (TZ §4.1: the tree is cached and
rebuilt on a watcher event, not per request). On the MVP we lean on uvicorn's
own reloader.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def register(subparsers) -> None:
    parser = subparsers.add_parser("dev", help="run the dev server + file watcher")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-reload", action="store_true", help="disable auto-reload")
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    import uvicorn

    cwd = Path.cwd()
    if not (cwd / "Api").is_dir():
        print(f"warning: no Api/ directory in {cwd} — no routes will be served")

    uvicorn.run(
        "endocore.asgi:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=not args.no_reload,
        reload_dirs=[str(cwd)],
    )
    return 0
