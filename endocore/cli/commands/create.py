"""``endo create <path> [method]`` — scaffold an endpoint.

``path`` is ``user/role`` or an explicit ``v2/user/role``. Without a version
prefix the target is the latest existing version (or ``v1`` if none exists).
Folders are created as PascalCase on disk (``User/Role``); dynamic ``[id]``
segments are preserved. With a ``method`` a ``<Method>.py`` handler is written;
without one only the folder structure is created.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from endocore.core.discovery import HTTP_METHODS, Segment, list_versions
from endocore.core.router import is_version
from endocore.cli.templates import endpoint_body


def register(subparsers) -> None:
    parser = subparsers.add_parser("create", help="scaffold an endpoint")
    parser.add_argument("path", help="resource path, e.g. user/role or v2/user/[id]")
    parser.add_argument("method", nargs="?", help="HTTP method (post, get, ...)")
    parser.set_defaults(func=run)


def _folder_name(segment: Segment) -> str:
    """PascalCase folder for a static segment; ``[id]`` kept verbatim."""
    if segment.dynamic:
        return segment.raw
    return segment.raw[:1].upper() + segment.raw[1:]


def _url_name(segment: Segment) -> str:
    return f"{{{segment.name}}}" if segment.dynamic else segment.name


def run(args: argparse.Namespace) -> int:
    api_dir = Path.cwd() / "Api"

    raw_parts = [p for p in args.path.strip("/").split("/") if p]
    if not raw_parts:
        print("error: a resource path is required")
        return 2

    if is_version(raw_parts[0]):
        version, resource_parts = raw_parts[0], raw_parts[1:]
    else:
        existing = list_versions(api_dir)
        version = existing[-1] if existing else "v1"
        resource_parts = raw_parts

    if not resource_parts:
        print("error: need at least one resource segment after the version")
        return 2

    segments = [Segment.parse(p) for p in resource_parts]
    target = api_dir.joinpath(version, *[_folder_name(s) for s in segments])
    target.mkdir(parents=True, exist_ok=True)

    url = "/" + "/".join([version] + [_url_name(s) for s in segments])

    if args.method:
        method = args.method.upper()
        if method not in HTTP_METHODS:
            print(f"error: unknown HTTP method '{args.method}'")
            return 2
        file = target / f"{method.capitalize()}.py"
        if file.exists():
            print(f"exists:  {file}")
        else:
            file.write_text(endpoint_body(method, url), encoding="utf-8")
            print(f"created: {file}   ({method} {url})")
    else:
        print(f"created: {target}{'/'}   (structure for {url})")

    return 0
