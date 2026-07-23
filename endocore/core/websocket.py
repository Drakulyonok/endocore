"""WebSocket support over the raw ASGI ``websocket`` scope.

A websocket endpoint is a file named ``Socket.py`` (or ``Ws.py``) in the Api
tree; it defines ``async def handler(websocket)`` (dependency injection works
too). Example:

    # Api/v1/Chat/Socket.py  ->  ws /v1/chat
    async def handler(websocket):
        await websocket.accept()
        async for message in websocket.iter_text():
            await websocket.send_text(f"echo: {message}")
"""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse

from endocore.core.datastructures import QueryParams


def origin_allowed(headers: dict[str, str], allowed: Any) -> bool:
    """Same-origin check for the websocket handshake (mitigates cross-site
    websocket hijacking, since a browser attaches cookies to the handshake
    regardless of which site's script opened the connection).

    ``allowed`` is ``None`` (enforce same-origin against ``Host``), ``"*"``
    (disable the check), or an origin allowlist — same shape as
    ``cors_middleware``'s ``allow_origins``. A request with no ``Origin``
    header (any non-browser client) is always allowed.
    """
    origin = headers.get("origin")
    if origin is None or allowed == "*":
        return True
    if allowed is not None:
        return origin in allowed
    host = headers.get("host", "")
    try:
        origin_host = urlparse(origin).netloc.lower()
    except ValueError:
        return False
    return bool(origin_host) and origin_host == host.lower()


class WebSocketDisconnect(Exception):
    """Raised when the client disconnects."""

    def __init__(self, code: int = 1000) -> None:
        self.code = code
        super().__init__(f"websocket disconnected (code={code})")


def _parse_headers(raw: list[tuple[bytes, bytes]]) -> dict[str, str]:
    return {name.decode("latin-1").lower(): value.decode("latin-1") for name, value in raw}


class WebSocket:
    """A single websocket connection."""

    def __init__(self, scope: dict, receive: Callable[[], Awaitable[dict]],
                 send: Callable[[dict], Awaitable[None]]) -> None:
        self.scope = scope
        self._receive = receive
        self._send = send
        self.path: str = scope["path"]
        self.headers: dict[str, str] = _parse_headers(scope.get("headers", []))
        self.query: QueryParams = QueryParams(scope.get("query_string", b""))
        self.path_params: dict[str, str] = {}
        self.accepted = False
        self.closed = False

    async def accept(self, subprotocol: str | None = None) -> None:
        # The first client event is websocket.connect; consume it, then accept.
        message = await self._receive()
        if message["type"] != "websocket.connect":
            raise RuntimeError(f"expected websocket.connect, got {message['type']!r}")
        await self._send({"type": "websocket.accept", "subprotocol": subprotocol})
        self.accepted = True

    async def receive(self) -> dict:
        message = await self._receive()
        if message["type"] == "websocket.disconnect":
            self.closed = True
            raise WebSocketDisconnect(message.get("code", 1000))
        return message

    async def receive_text(self) -> str:
        message = await self.receive()
        return message.get("text") or ""

    async def receive_bytes(self) -> bytes:
        message = await self.receive()
        return message.get("bytes") or b""

    async def receive_json(self) -> Any:
        return json.loads(await self.receive_text())

    async def send_text(self, data: str) -> None:
        await self._send({"type": "websocket.send", "text": data})

    async def send_bytes(self, data: bytes) -> None:
        await self._send({"type": "websocket.send", "bytes": data})

    async def send_json(self, obj: Any) -> None:
        await self.send_text(json.dumps(obj))

    async def close(self, code: int = 1000) -> None:
        if not self.closed:
            self.closed = True
            await self._send({"type": "websocket.close", "code": code})

    async def iter_text(self):
        try:
            while True:
                yield await self.receive_text()
        except WebSocketDisconnect:
            return

    async def iter_json(self):
        try:
            while True:
                yield await self.receive_json()
        except WebSocketDisconnect:
            return
