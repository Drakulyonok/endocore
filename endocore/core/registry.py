"""Route registry: the resolved tree of routes, built once at boot and cached.

The registry stores handlers in a small trie of :class:`RouteNode` keyed by
version, then by folder segment. Static segments take priority over the dynamic
(``[id]``) child. Resolution is a single walk down this trie — see
:mod:`endocore.core.router` for the matching rules this encodes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from endocore.core.discovery import RouteSpec
from endocore.core.router import split_path, is_version

# Resolution statuses.
FOUND = 200
NOT_FOUND = 404
METHOD_NOT_ALLOWED = 405


@dataclass
class HandlerEntry:
    """A route whose handler has been imported and is ready to call."""

    spec: RouteSpec
    handler: Callable
    is_async: bool


class RouteNode:
    """A node in the route trie (one folder level)."""

    __slots__ = ("static", "dynamic", "param_name", "handlers")

    def __init__(self) -> None:
        self.static: dict[str, RouteNode] = {}
        self.dynamic: "RouteNode | None" = None
        self.param_name: str | None = None
        self.handlers: dict[str, HandlerEntry] = {}


@dataclass
class Match:
    entry: HandlerEntry
    params: dict[str, str] = field(default_factory=dict)


@dataclass
class Resolution:
    """Outcome of resolving a request against the registry.

    ``status`` is 200 (matched), 404 (no such path/version) or 405 (path exists
    but not for this method). ``allowed`` lists methods for the 405 ``Allow``
    header.
    """

    match: "Match | None"
    status: int
    allowed: tuple[str, ...] = ()


class Registry:
    """In-memory route table. Built at boot, then read-only per request."""

    def __init__(self) -> None:
        self._versions: dict[str, RouteNode] = {}
        self._count = 0

    def add(self, entry: HandlerEntry) -> None:
        """Insert a resolved handler into the trie."""
        spec = entry.spec
        node = self._versions.setdefault(spec.version, RouteNode())
        for seg in spec.segments:
            if seg.dynamic:
                if node.dynamic is None:
                    node.dynamic = RouteNode()
                    node.dynamic.param_name = seg.name
                node = node.dynamic
            else:
                node = node.static.setdefault(seg.name, RouteNode())
        if spec.method not in node.handlers:
            self._count += 1
        node.handlers[spec.method] = entry

    def resolve(self, method: str, path: str) -> Resolution:
        """Match ``method`` + ``path`` to a handler (the hot path).

        Walks the trie: first segment as version (``^v\\d+$``), then static
        segments preferred over the dynamic child, capturing path params.
        """
        segments = split_path(path)

        # No version prefix -> 404 in the MVP (explicit over implicit, TZ §5).
        if not segments or not is_version(segments[0]):
            return Resolution(None, NOT_FOUND)

        node = self._versions.get(segments[0])
        if node is None:
            return Resolution(None, NOT_FOUND)

        params: dict[str, str] = {}
        for seg in segments[1:]:
            child = node.static.get(seg)
            if child is not None:
                node = child
            elif node.dynamic is not None:
                params[node.dynamic.param_name] = seg  # already URL-decoded
                node = node.dynamic
            else:
                return Resolution(None, NOT_FOUND)

        entry = node.handlers.get(method.upper())
        if entry is not None:
            return Resolution(Match(entry, params), FOUND)

        # Path exists but not for this method.
        if node.handlers:
            return Resolution(None, METHOD_NOT_ALLOWED, tuple(sorted(node.handlers)))
        return Resolution(None, NOT_FOUND)

    def latest_version(self) -> str | None:
        """The newest registered version (e.g. ``"v2"``), or ``None`` if empty."""
        if not self._versions:
            return None
        return max(self._versions, key=lambda v: int(v[1:]))

    def entries(self) -> list[HandlerEntry]:
        """All registered handler entries (route + imported handler)."""
        collected: list[HandlerEntry] = []

        def walk(node: RouteNode) -> None:
            collected.extend(node.handlers.values())
            for child in node.static.values():
                walk(child)
            if node.dynamic is not None:
                walk(node.dynamic)

        for root in self._versions.values():
            walk(root)
        return collected

    def routes(self) -> list:
        """All registered route specs (for ``end routes`` / introspection)."""
        return [entry.spec for entry in self.entries()]

    def __len__(self) -> int:
        return self._count
