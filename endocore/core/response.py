"""Our own Response — turns a value into ASGI ``send`` messages.

A handler may return a :class:`Response`, or a plain ``dict``/``list`` (wrapped
as JSON 200), or a ``str`` (text). The Application coerces those; this class is
the canonical form that knows how to write itself to ``send``.
"""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable


class Response:
    """An outbound HTTP response."""

    def __init__(
        self,
        content: Any = None,
        status: int = 200,
        headers: dict[str, str] | None = None,
        media_type: str = "application/json",
    ) -> None:
        self.status = status
        self.media_type = media_type
        self.headers = headers or {}
        self.body: bytes = self._render(content)

    def _render(self, content: Any) -> bytes:
        """Serialize ``content`` to bytes (JSON for dict/list, utf-8 for str)."""
        if content is None:
            return b""
        if isinstance(content, (bytes, bytearray)):
            return bytes(content)
        if isinstance(content, str):
            return content.encode("utf-8")
        # dict / list / number / bool -> JSON. ``default=str`` keeps unusual
        # values (dates, UUIDs) from blowing up the whole response.
        return json.dumps(content, default=str).encode("utf-8")

    async def __call__(self, send: Callable[[dict], Awaitable[None]]) -> None:
        """Emit ``http.response.start`` + ``http.response.body`` to ``send``."""
        raw_headers: list[tuple[bytes, bytes]] = [
            (b"content-type", self.media_type.encode("latin-1")),
            (b"content-length", str(len(self.body)).encode("latin-1")),
        ]
        for name, value in self.headers.items():
            raw_headers.append((name.encode("latin-1"), str(value).encode("latin-1")))

        await send(
            {"type": "http.response.start", "status": self.status, "headers": raw_headers}
        )
        await send({"type": "http.response.body", "body": self.body})

    @classmethod
    def json(cls, content: Any, status: int = 200, headers: dict[str, str] | None = None) -> "Response":
        return cls(content, status=status, headers=headers, media_type="application/json")

    @classmethod
    def text(cls, content: str, status: int = 200, headers: dict[str, str] | None = None) -> "Response":
        return cls(content, status=status, headers=headers, media_type="text/plain; charset=utf-8")


def _to_bytes(chunk: Any) -> bytes:
    if isinstance(chunk, (bytes, bytearray)):
        return bytes(chunk)
    return str(chunk).encode("utf-8")


class StreamingResponse:
    """A response whose body is produced incrementally (no Content-Length).

    ``content`` may be any sync or async iterable of ``bytes``/``str`` chunks —
    each is written to ``send`` with ``more_body=True`` until the stream ends.
    """

    def __init__(
        self,
        content: Any,
        status: int = 200,
        headers: dict[str, str] | None = None,
        media_type: str = "application/octet-stream",
    ) -> None:
        self.content = content
        self.status = status
        self.media_type = media_type
        self.headers = headers or {}

    async def _aiter(self):
        content = self.content
        if hasattr(content, "__aiter__"):
            async for chunk in content:
                yield chunk
        else:
            for chunk in content:
                yield chunk

    async def __call__(self, send: Callable[[dict], Awaitable[None]]) -> None:
        raw_headers: list[tuple[bytes, bytes]] = [
            (b"content-type", self.media_type.encode("latin-1")),
        ]
        for name, value in self.headers.items():
            raw_headers.append((name.encode("latin-1"), str(value).encode("latin-1")))

        await send({"type": "http.response.start", "status": self.status, "headers": raw_headers})
        async for chunk in self._aiter():
            await send({"type": "http.response.body", "body": _to_bytes(chunk), "more_body": True})
        await send({"type": "http.response.body", "body": b"", "more_body": False})
