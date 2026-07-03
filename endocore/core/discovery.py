"""Filesystem scanning: the ``Api/`` tree -> route specifications.

This is the single tree-walk the framework relies on. Routing, versioning and
the CLI are all operations over the same directory tree (TZ §1). Everything
downstream (registry, resolver) consumes :class:`RouteSpec` objects produced
here.

Shared constants (``HTTP_METHODS``, ``VERSION_RE``, ``DYNAMIC_RE``) live here so
router, registry and CLI agree on one definition of "what is a version" and
"what is a dynamic segment".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

#: HTTP methods that a file stem (upper-cased) may name. A file whose stem is
#: not one of these is treated as code (service/util/init), not a route.
HTTP_METHODS: frozenset[str] = frozenset(
    {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
)

#: File stems that mark a websocket endpoint (mapped to the WEBSOCKET method).
WEBSOCKET_STEMS: frozenset[str] = frozenset({"SOCKET", "WS", "WEBSOCKET"})
WEBSOCKET_METHOD = "WEBSOCKET"

#: First path/folder segment matching this is a version (TZ §5).
VERSION_RE = re.compile(r"^v\d+$")

#: A folder named ``[name]`` is a dynamic segment capturing ``name`` (TZ §4.3).
DYNAMIC_RE = re.compile(r"^\[(?P<name>[^\[\]]+)\]$")

#: Folders that hold code, not routes, and must be skipped by the scanner.
NON_ROUTE_DIRS: frozenset[str] = frozenset({"Services", "__pycache__"})


@dataclass(frozen=True)
class Segment:
    """One URL segment derived from a folder name.

    ``User`` -> Segment(raw="User", name="user", dynamic=False)
    ``[id]`` -> Segment(raw="[id]", name="id",   dynamic=True)
    """

    raw: str
    name: str
    dynamic: bool

    @classmethod
    def parse(cls, folder: str) -> "Segment":
        m = DYNAMIC_RE.match(folder)
        if m:
            return cls(raw=folder, name=m.group("name"), dynamic=True)
        return cls(raw=folder, name=folder.lower(), dynamic=False)


@dataclass(frozen=True)
class RouteSpec:
    """A discovered route, before its handler is imported.

    Pure description of a file's place in the tree — no runtime behaviour.
    """

    version: str
    method: str
    segments: tuple[Segment, ...]
    file: Path

    @property
    def url(self) -> str:
        """Human-readable URL template, e.g. ``/v2/user/{id}/role``."""
        parts = [self.version]
        for s in self.segments:
            parts.append(f"{{{s.name}}}" if s.dynamic else s.name)
        return "/" + "/".join(parts)


@dataclass(frozen=True)
class SkippedFile:
    """A ``*.py`` file the scanner deliberately ignored, with the reason."""

    file: Path
    reason: str


def scan_routes(api_dir: Path) -> tuple[list[RouteSpec], list[SkippedFile]]:
    """Walk ``api_dir`` (``rglob("*.py")``) and classify every file.

    Returns the discovered route specs and the files that were skipped (with
    reasons, useful for the boot summary / debugging). Does **not** import
    anything — that is the loader's job.
    """
    specs: list[RouteSpec] = []
    skipped: list[SkippedFile] = []

    if not api_dir.is_dir():
        return specs, skipped

    for file in sorted(api_dir.rglob("*.py")):
        rel = file.relative_to(api_dir)
        parts = rel.parts  # e.g. ("v1", "User", "Role", "Post.py")

        method = file.stem.upper()
        if method in WEBSOCKET_STEMS:
            method = WEBSOCKET_METHOD
        elif method not in HTTP_METHODS:
            # Not an endpoint: service, util, __init__, or a helper module.
            continue

        version = parts[0]
        if not VERSION_RE.match(version):
            skipped.append(SkippedFile(file, "not under a version folder (vN)"))
            continue

        middle = parts[1:-1]  # folder segments between version and file
        skip_dir = next((p for p in middle if p in NON_ROUTE_DIRS), None)
        if skip_dir is not None:
            skipped.append(SkippedFile(file, f"inside non-route folder '{skip_dir}'"))
            continue

        segments = tuple(Segment.parse(p) for p in middle)
        specs.append(RouteSpec(version=version, method=method, segments=segments, file=file))

    return specs, skipped


def list_versions(api_dir: Path) -> list[str]:
    """Return version folder names under ``api_dir`` sorted ascending by number.

    Used by both the resolver and the ``end version`` CLI commands.
    """
    if not api_dir.is_dir():
        return []
    versions = [
        child.name
        for child in api_dir.iterdir()
        if child.is_dir() and VERSION_RE.match(child.name)
    ]
    return sorted(versions, key=lambda v: int(v[1:]))
