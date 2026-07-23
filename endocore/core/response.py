"""Our own Response — turns a value into ASGI ``send`` messages.

A handler may return a :class:`Response`, or a plain ``dict``/``list`` (wrapped
as JSON 200), or a ``str`` (text). The Application coerces those; this class is
the canonical form that knows how to write itself to ``send``.
"""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

#: A raw CR/LF/NUL here would let a header/cookie value forge extra header
#: lines in the response (CWE-113, "HTTP response splitting").
_FORBIDDEN_HEADER_CHARS = ("\r", "\n", "\x00")


def _check_header_value(name: str, value: str) -> None:
    if any(ch in value for ch in _FORBIDDEN_HEADER_CHARS):
        raise ValueError(f"{name} must not contain CR, LF, or NUL characters: {value!r}")


class Response:
    """An outbound HTTP response."""

    def __init__(
        self,
        content: Any = None,
        status: int = 200,
        headers: dict[str, str] | None = None,
        media_type: str = "application/json",
        background: Any = None,
    ) -> None:
        self.status = status
        self.media_type = media_type
        self.headers = headers or {}
        #: raw ``Set-Cookie`` header values (a dict can't hold several)
        self._cookies: list[str] = []
        #: a coroutine/callable run after the response is sent
        self.background = background
        self.body: bytes = self._render(content)

    def set_cookie(
        self,
        key: str,
        value: str = "",
        *,
        max_age: int | None = None,
        path: str = "/",
        domain: str | None = None,
        secure: bool = False,
        httponly: bool = False,
        samesite: str | None = "lax",
    ) -> "Response":
        """Queue a ``Set-Cookie`` header. Defaults are safe (SameSite=Lax)."""
        _check_header_value("cookie key", key)
        _check_header_value("cookie value", value)
        if domain:
            _check_header_value("cookie domain", domain)
        if path:
            _check_header_value("cookie path", path)
        cookie = f"{key}={value}"
        if max_age is not None:
            cookie += f"; Max-Age={int(max_age)}"
        if path:
            cookie += f"; Path={path}"
        if domain:
            cookie += f"; Domain={domain}"
        if secure:
            cookie += "; Secure"
        if httponly:
            cookie += "; HttpOnly"
        if samesite:
            cookie += f"; SameSite={samesite.capitalize()}"
        self._cookies.append(cookie)
        return self

    def delete_cookie(self, key: str, *, path: str = "/", domain: str | None = None) -> "Response":
        return self.set_cookie(key, "", max_age=0, path=path, domain=domain)

    def set_signed_cookie(self, key: str, value: str, secret: str, **kwargs: Any) -> "Response":
        """Set an HMAC-signed cookie (tamper-proof). Read with ``request.get_signed_cookie``."""
        from endocore.core.signing import Signer

        kwargs.setdefault("httponly", True)
        return self.set_cookie(key, Signer(secret).sign(value), **kwargs)

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
        _check_header_value("content-type", self.media_type)
        raw_headers: list[tuple[bytes, bytes]] = [
            (b"content-type", self.media_type.encode("latin-1")),
            (b"content-length", str(len(self.body)).encode("latin-1")),
        ]
        for name, value in self.headers.items():
            value = str(value)
            _check_header_value("header name", name)
            _check_header_value("header value", value)
            raw_headers.append((name.encode("latin-1"), value.encode("latin-1")))
        for cookie in self._cookies:
            raw_headers.append((b"set-cookie", cookie.encode("latin-1")))

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

    @classmethod
    def redirect(cls, location: str, status: int = 307, headers: dict[str, str] | None = None) -> "Response":
        headers = dict(headers or {})
        headers["Location"] = location
        return cls(None, status=status, headers=headers, media_type="text/plain")

    @classmethod
    def no_content(cls) -> "Response":
        return cls(None, status=204)


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
        _check_header_value("content-type", self.media_type)
        raw_headers: list[tuple[bytes, bytes]] = [
            (b"content-type", self.media_type.encode("latin-1")),
        ]
        for name, value in self.headers.items():
            value = str(value)
            _check_header_value("header name", name)
            _check_header_value("header value", value)
            raw_headers.append((name.encode("latin-1"), value.encode("latin-1")))

        await send({"type": "http.response.start", "status": self.status, "headers": raw_headers})
        async for chunk in self._aiter():
            await send({"type": "http.response.body", "body": _to_bytes(chunk), "more_body": True})
        await send({"type": "http.response.body", "body": b"", "more_body": False})
