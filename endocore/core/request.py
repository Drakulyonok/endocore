"""Our own Request over the raw ASGI ``scope`` (no Starlette).

Reads metadata from ``scope`` and lazily assembles the body from ``receive``.
Headers arrive as a list of **byte** tuples ``[(b"content-type", b"...")]`` — we
decode them ourselves. For the MVP the body is buffered fully in memory before
parsing; streaming is deliberately out of scope.
"""

from __future__ import annotations

import json
from urllib.parse import parse_qs
from typing import Any, Awaitable, Callable


def _parse_headers(raw: list[tuple[bytes, bytes]]) -> dict[str, str]:
    """Decode ASGI byte-tuple headers into a lower-cased str dict."""
    return {name.decode("latin-1").lower(): value.decode("latin-1") for name, value in raw}


class Request:
    """A single inbound HTTP request."""

    def __init__(self, scope: dict, receive: Callable[[], Awaitable[dict]]) -> None:
        self.scope = scope
        self._receive = receive
        self.method: str = scope["method"]
        self.path: str = scope["path"]
        #: decoded, lower-cased header name -> value
        self.headers: dict[str, str] = _parse_headers(scope.get("headers", []))
        #: parsed query string, key -> list of values (``parse_qs``)
        self.query: dict[str, list[str]] = parse_qs(
            scope.get("query_string", b"").decode("latin-1")
        )
        #: dynamic segments captured by the resolver (``[id]`` -> "42")
        self.path_params: dict[str, str] = {}
        self._body: bytes | None = None

    async def body(self) -> bytes:
        """Read and cache the full request body from ``receive``.

        The body arrives as chunks with ``more_body``; for a JSON API we buffer
        it all before parsing (streaming is out of MVP scope).
        """
        if self._body is None:
            chunks: list[bytes] = []
            more = True
            while more:
                message = await self._receive()
                chunks.append(message.get("body", b""))
                more = message.get("more_body", False)
            self._body = b"".join(chunks)
        return self._body

    async def json(self) -> Any:
        """Parse the body as JSON (``None`` for an empty body)."""
        raw = await self.body()
        if not raw:
            return None
        return json.loads(raw)
