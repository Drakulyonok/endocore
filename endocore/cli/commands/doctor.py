"""``endo doctor`` — environment/dependency/config sanity check."""

from __future__ import annotations

import argparse
import importlib
import platform
import sys
from pathlib import Path


def _probe(module: str) -> str:
    try:
        mod = importlib.import_module(module)
        return getattr(mod, "__version__", "installed")
    except Exception:
        return "MISSING"


def register(subparsers) -> None:
    parser = subparsers.add_parser("doctor", help="check versions, deps, and config")
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from endocore import __version__

    print(f"EndoCore     {__version__}")
    print(f"Python       {platform.python_version()} ({sys.platform})")
    print("dependencies:")
    print(f"  uvicorn      {_probe('uvicorn')}   (required)")
    print(f"  watchfiles   {_probe('watchfiles')}   (dev watcher)")
    print(f"  psycopg      {_probe('psycopg')}   (postgres)")
    print(f"  cryptography {_probe('cryptography')}   (encrypted files)")

    cwd = Path.cwd()
    print("project:")
    print(f"  cwd          {cwd}")
    print(f"  Api/         {'found' if (cwd / 'Api').is_dir() else 'missing'}")
    for name in ("Services", "Models", "Middleware", "Tests"):
        if (cwd / name).is_dir():
            print(f"  {name + '/':<12} found")
    print(f"  hooks.py     {'found' if (cwd / 'hooks.py').is_file() else '-'}")
    return 0
