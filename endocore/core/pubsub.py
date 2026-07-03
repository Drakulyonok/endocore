"""In-process pub/sub for websockets: rooms + broadcast.

    from endocore.core.pubsub import WebSocketManager
    chat = WebSocketManager()

    # Api/v1/Chat/Socket.py
    async def handler(websocket):
        await chat.connect(websocket, room="lobby")
        try:
            async for msg in websocket.iter_text():
                await chat.broadcast(msg, room="lobby")
        finally:
            chat.disconnect(websocket, room="lobby")

Single-process only (rooms live in memory). For multi-worker fan-out, pair a
Redis pub/sub in front of it.
"""

from __future__ import annotations

from typing import Any


class WebSocketManager:
    """Tracks connected websockets by room and fans messages out to them."""

    def __init__(self) -> None:
        self.rooms: dict[str, set] = {}

    async def connect(self, websocket, room: str = "default") -> None:
        """Accept the socket (if not already) and join it to ``room``."""
        if not getattr(websocket, "accepted", False):
            await websocket.accept()
        self.rooms.setdefault(room, set()).add(websocket)

    def add(self, websocket, room: str = "default") -> None:
        """Join an already-accepted socket to ``room``."""
        self.rooms.setdefault(room, set()).add(websocket)

    def disconnect(self, websocket, room: str | None = None) -> None:
        """Remove a socket from ``room`` (or from every room if None)."""
        rooms = [room] if room is not None else list(self.rooms)
        for name in rooms:
            self.rooms.get(name, set()).discard(websocket)
            if name in self.rooms and not self.rooms[name]:
                del self.rooms[name]

    def members(self, room: str = "default") -> set:
        return set(self.rooms.get(room, set()))

    def count(self, room: str = "default") -> int:
        return len(self.rooms.get(room, set()))

    def rooms_of(self, websocket) -> list[str]:
        return [name for name, members in self.rooms.items() if websocket in members]

    async def _send(self, sender, websocket, payload, exclude) -> None:
        if websocket is exclude:
            return
        try:
            await sender(websocket, payload)
        except Exception:  # noqa: BLE001 - drop a dead connection
            self.disconnect(websocket)

    async def broadcast(self, message: str, room: str = "default", *, exclude=None) -> None:
        """Send a text message to everyone in ``room``."""
        for websocket in list(self.rooms.get(room, set())):
            await self._send(lambda ws, m: ws.send_text(m), websocket, message, exclude)

    async def broadcast_json(self, obj: Any, room: str = "default", *, exclude=None) -> None:
        for websocket in list(self.rooms.get(room, set())):
            await self._send(lambda ws, o: ws.send_json(o), websocket, obj, exclude)

    async def send_to(self, websocket, message: str) -> None:
        await self._send(lambda ws, m: ws.send_text(m), websocket, message, None)
