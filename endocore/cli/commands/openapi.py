"""``end openapi`` — dump the OpenAPI 3.0 schema for the project."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def register(subparsers) -> None:
    parser = subparsers.add_parser("openapi", help="print or write the OpenAPI schema")
    parser.add_argument("--out", default=None, help="write to a file instead of stdout")
    parser.add_argument("--title", default="EndoCore API")
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from endocore.core.application import Application
    from endocore.core.openapi import generate_openapi

    app = Application(app_dir=Path.cwd())
    schema = generate_openapi(app, title=args.title)
    text = json.dumps(schema, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out} ({len(schema['paths'])} paths)")
    else:
        print(text)
    return 0
