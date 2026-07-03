"""``end version ...`` — versioning as a tree operation.

    end version create N        copy the latest version -> vN
    end version list            list existing versions

``create`` is ``shutil.copytree`` with a filter: endpoint files and **local**
services (``Api/vX/.../Services/``) are copied; global ``/Services/`` live
outside ``Api/`` and are never touched. Copying with the file bodies is the
default, because a new version is usually "the same, with a couple of edits".
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

from endocore.core.discovery import HTTP_METHODS, list_versions

_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc")


def register(subparsers) -> None:
    parser = subparsers.add_parser("version", help="manage API versions")
    version_sub = parser.add_subparsers(dest="version_command", required=True)

    create = version_sub.add_parser("create", help="copy a version into a new one")
    create.add_argument("number", type=int, help="new version number, e.g. 2 -> v2")
    create.add_argument(
        "--from", dest="from_version", type=int, default=None,
        help="branch from a specific version instead of the latest",
    )
    create.add_argument(
        "--empty", action="store_true", help="scaffold files without bodies",
    )
    create.set_defaults(func=run)

    listing = version_sub.add_parser("list", help="list existing versions")
    listing.set_defaults(func=run)


def _rewrite_local_imports(dest: Path, src_name: str, dest_name: str) -> None:
    """Repoint version-qualified imports of local services to the new version.

    A copied handler that did ``from Api.v1.User.Services... import ...`` must now
    reference ``Api.v2...`` — otherwise v2 would silently run v1's local services
    and version isolation would be fake (TZ §10.3). Only the exact version
    package prefix is rewritten; nothing else in the file is touched.
    """
    pattern = re.compile(rf"\bApi\.{re.escape(src_name)}\b")
    for path in dest.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        new_text = pattern.sub(f"Api.{dest_name}", text)
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")


def _copy_empty(src: Path, dest: Path) -> None:
    """Replicate the tree of ``src`` into ``dest`` with stubbed file bodies."""
    for path in sorted(src.rglob("*")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(src)
        out = dest / rel
        if path.is_dir():
            out.mkdir(parents=True, exist_ok=True)
        elif path.suffix == ".py":
            out.parent.mkdir(parents=True, exist_ok=True)
            method = path.stem.upper()
            if method in HTTP_METHODS:
                out.write_text(
                    '"""TODO: implement this endpoint."""\n\n\n'
                    "async def handler(request):\n    ...\n",
                    encoding="utf-8",
                )
            else:
                out.write_text("", encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    api_dir = Path.cwd() / "Api"

    if args.version_command == "list":
        versions = list_versions(api_dir)
        if not versions:
            print("no versions yet (create Api/v1/... first)")
        else:
            for name in versions:
                print(name)
        return 0

    # create
    versions = list_versions(api_dir)
    dest_name = f"v{args.number}"
    dest = api_dir / dest_name
    if dest.exists():
        print(f"error: {dest_name} already exists")
        return 2

    if args.from_version is not None:
        src_name = f"v{args.from_version}"
    elif versions:
        src_name = versions[-1]
    else:
        print("error: no existing version to copy from (create Api/v1/... first)")
        return 2

    src = api_dir / src_name
    if not src.is_dir():
        print(f"error: source version {src_name} not found")
        return 2

    if args.empty:
        _copy_empty(src, dest)
    else:
        shutil.copytree(src, dest, ignore=_IGNORE)
        _rewrite_local_imports(dest, src_name, dest_name)

    print(f"created {dest_name} from {src_name}"
          + (" (empty stubs)" if args.empty else " (with bodies)"))
    return 0
