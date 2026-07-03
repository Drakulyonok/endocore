"""``end new <Name>`` — scaffold a fresh EndoCore project."""

from __future__ import annotations

import argparse
from pathlib import Path

_HEALTH = '''"""GET /v1/health — liveness probe."""

from endocore import Request, Response


async def handler(request: Request) -> Response:
    return Response.json({"status": "ok"})
'''

_MIDDLEWARE = '''"""Register ordered middleware here (first = outermost)."""

# from endocore.middleware import cors_middleware, security_headers_middleware

middlewares = [
    # cors_middleware(allow_origins=["*"]),
    # security_headers_middleware(),
]
'''

_HOOKS = '''"""Startup/shutdown hooks (open/close Redis, schedulers, ...)."""


async def _connect():
    pass  # e.g. open a connection pool


async def _disconnect():
    pass


on_startup = [_connect]
on_shutdown = [_disconnect]
'''

_README = """# {name}

An EndoCore project. Run the dev server:

    end dev

Useful commands: `end routes`, `end check`, `end doctor`, `end create user/profile get`.
"""


def register(subparsers) -> None:
    parser = subparsers.add_parser("new", help="scaffold a new project")
    parser.add_argument("name", help="project directory name")
    parser.set_defaults(func=run)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    root = Path.cwd() / args.name
    if root.exists():
        print(f"error: {root} already exists")
        return 2

    _write(root / "Api" / "v1" / "Health" / "Get.py", _HEALTH)
    _write(root / "Middleware" / "__init__.py", _MIDDLEWARE)
    _write(root / "hooks.py", _HOOKS)
    _write(root / "README.md", _README.format(name=args.name))
    for folder in ("Services", "Models", "Utils", "Tests"):
        (root / folder).mkdir(parents=True, exist_ok=True)
        (root / folder / ".gitkeep").write_text("", encoding="utf-8")

    print(f"created project {args.name}/")
    print("next:")
    print(f"  cd {args.name}")
    print("  end dev        # http://127.0.0.1:8000/v1/health")
    return 0
