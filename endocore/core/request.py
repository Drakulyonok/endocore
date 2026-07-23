"""Our own Request over the raw ASGI ``scope`` (no Starlette).

Reads metadata from ``scope`` and lazily assembles the body from ``receive``.
Headers arrive as a list of **byte** tuples ``[(b"content-type", b"...")]`` — we
decode them ourselves. For the MVP the body is buffered fully in memory before
parsing; streaming is available via :meth:`Request.stream`.
"""

from __future__ import annotations

import json
from http.cookies import SimpleCookie
from typing import Any, Awaitable, Callable

from endocore.core.datastructures import (
    FormData,
    QueryParams,
    parse_multipart,
    parse_urlencoded,
)
from endocore.core.exceptions import BadRequest, PayloadTooLarge


def _parse_headers(raw: list[tuple[bytes, bytes]]) -> dict[str, str]:
    """Decode ASGI byte-tuple headers into a lower-cased str dict."""
    return {name.decode("latin-1").lower(): value.decode("latin-1") for name, value in raw}


def _parse_cookies(header: str) -> dict[str, str]:
    if not header:
        return {}
    jar: SimpleCookie = SimpleCookie()
    try:
        jar.load(header)
    except Exception:  # noqa: BLE001 - malformed cookies shouldn't crash a request
        return {}
    return {key: morsel.value for key, morsel in jar.items()}


class Request:
    """A single inbound HTTP request."""

    def __init__(
        self,
        scope: dict,
        receive: Callable[[], Awaitable[dict]],
        *,
        max_body_size: int | None = None,
    ) -> None:
        self.scope = scope
        self._receive = receive
        self.method: str = scope["method"]
        self.path: str = scope["path"]
        self.headers: dict[str, str] = _parse_headers(scope.get("headers", []))
        #: parsed query string; ``request.query.get("page")`` / ``.getlist(...)``
        self.query: QueryParams = QueryParams(scope.get("query_string", b""))
        #: dynamic segments captured by the resolver (``[id]`` -> "42")
        self.path_params: dict[str, str] = {}
        self._max_body_size = max_body_size
        self._body: bytes | None = None
        self._form: FormData | None = None
        self._cookies: dict[str, str] | None = None

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "")

    @property
    def cookies(self) -> dict[str, str]:
        if self._cookies is None:
            self._cookies = _parse_cookies(self.headers.get("cookie", ""))
        return self._cookies

    def get_signed_cookie(
        self, key: str, secret: str, *, max_age: int | None = None, default: Any = None
    ) -> Any:
        """Read and verify an HMAC-signed cookie. Missing -> ``default``; tampered/expired -> raises."""
        from endocore.core.signing import Signer

        raw = self.cookies.get(key)
        if raw is None:
            return default
        return Signer(secret).unsign(raw, max_age=max_age)

    async def body(self) -> bytes:
        """Read and cache the full request body, enforcing the size limit."""
        if self._body is None:
            chunks: list[bytes] = []
            total = 0
            more = True
            while more:
                message = await self._receive()
                chunk = message.get("body", b"")
                total += len(chunk)
                if self._max_body_size is not None and total > self._max_body_size:
                    raise PayloadTooLarge(
                        f"request body exceeds limit of {self._max_body_size} bytes"
                    )
                chunks.append(chunk)
                more = message.get("more_body", False)
            self._body = b"".join(chunks)
        return self._body

    async def json(self) -> Any:
        """Parse the body as JSON (``None`` for an empty body)."""
        raw = await self.body()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise BadRequest(f"invalid JSON: {exc}") from None
        except RecursionError:
            # deeply nested input (e.g. thousands of "[") blows the Python
            # recursion limit in the stdlib's pure-Python JSON scanner —
            # still just malformed input, not a server error
            raise BadRequest("invalid JSON: too deeply nested") from None

    async def form(self) -> FormData:
        """Parse an ``application/x-www-form-urlencoded`` or ``multipart/form-data`` body."""
        if self._form is None:
            raw = await self.body()
            ctype = self.content_type
            if ctype.startswith("multipart/form-data"):
                boundary = ""
                for part in ctype.split(";"):
                    part = part.strip()
                    if part.startswith("boundary="):
                        boundary = part[len("boundary="):].strip().strip('"')
                if not boundary:
                    raise BadRequest("multipart form is missing a boundary")
                self._form = parse_multipart(raw, boundary)
            else:
                self._form = parse_urlencoded(raw)
        return self._form

    async def files(self) -> dict:
        """Return only the uploaded files from a multipart form."""
        return (await self.form()).files

    async def stream(self):
        """Yield the request body in chunks as they arrive (for large uploads).

        Consumes ``receive`` directly, so don't mix with ``body()``/``json()`` on
        the same request. If the body was already buffered, yields it once.
        """
        if self._body is not None:
            if self._body:
                yield self._body
            return
        more = True
        while more:
            message = await self._receive()
            chunk = message.get("body", b"")
            if chunk:
                yield chunk
            more = message.get("more_body", False)
