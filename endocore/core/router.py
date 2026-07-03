"""The resolver — the heart of the framework.

Given ``POST /v2/user/42/role`` it must find ``Api/v2/User/[id]/Role/Post.py``
and extract ``id=42``. The mechanics of the match live in
:class:`endocore.core.registry.Registry` (a trie); this module owns the *rules*
that turn a raw request path into the pieces the registry walks, and the parsing
of an incoming URL path into segments.

Matching rules (TZ §4.3):
- The first segment is a version iff it matches ``^v\\d+$``.
- Remaining segments match folder names; a folder ``[name]`` is a dynamic param.
- The file name (``Post``, ``Get``, ...) maps to the HTTP method after ``.upper()``.
- No version prefix -> 404 in the MVP (no default-to-latest).
"""

from __future__ import annotations

from urllib.parse import unquote

from endocore.core.discovery import VERSION_RE


def split_path(path: str) -> list[str]:
    """Split a URL path into non-empty, URL-decoded segments.

    ``"/v2/user/42/role"`` -> ``["v2", "user", "42", "role"]``.
    """
    return [unquote(part) for part in path.split("/") if part]


def is_version(segment: str) -> bool:
    """Whether ``segment`` is a version prefix (``^v\\d+$``)."""
    return bool(VERSION_RE.match(segment))
