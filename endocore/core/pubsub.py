"""Pub/sub for websockets: rooms + broadcast, single-process or fanned out
across workers via Redis.

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

Without ``redis_client``, rooms live in memory and only reach sockets
connected to *this* process — fine for a single worker, wrong the moment you
run more than one (a broadcast from worker A never reaches a socket held
open by worker B). Pass a Redis client to fan broadcasts out to every worker
instead; see ``docs/guide/websockets.md``.
"""

from __future__ import annotations

import asyncio
import json
import queue
import threading
import uuid
from typing import Any


class WebSocketManager:
    """Tracks connected websockets by room and fans messages out to them."""

    def __init__(self, *, redis_client=None, channel_prefix: str = "endocore:ws:") -> None:
        self.rooms: dict[str, set] = {}
        self._redis = redis_client
        self._channel_prefix = channel_prefix
        #: unique per instance/process, so a broadcast this process publishes
        #: to Redis is ignored when its own listener receives it back — local
        #: sockets already got it directly, from the broadcast call itself.
        self._origin = uuid.uuid4().hex
        self._queue: "queue.Queue | None" = None
        self._listener_thread: threading.Thread | None = None
        self._dispatch_task: "asyncio.Task | None" = None
        self._stop_event: "threading.Event | None" = None
        self._pubsub = None

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

    async def _broadcast_local(self, kind: str, payload: Any, room: str, exclude=None) -> None:
        sender = (lambda ws, m: ws.send_text(m)) if kind == "text" else (lambda ws, o: ws.send_json(o))
        for websocket in list(self.rooms.get(room, set())):
            await self._send(sender, websocket, payload, exclude)

    async def broadcast(self, message: str, room: str = "default", *, exclude=None) -> None:
        """Send a text message to everyone in ``room`` — on this process, and
        (if configured) fanned out to every other worker's copy of ``room``."""
        await self._broadcast_local("text", message, room, exclude)
        await self._publish("text", message, room)

    async def broadcast_json(self, obj: Any, room: str = "default", *, exclude=None) -> None:
        await self._broadcast_local("json", obj, room, exclude)
        await self._publish("json", obj, room)

    async def send_to(self, websocket, message: str) -> None:
        await self._send(lambda ws, m: ws.send_text(m), websocket, message, None)

    # -- Redis fan-out ------------------------------------------------------

    async def _publish(self, kind: str, payload: Any, room: str) -> None:
        if self._redis is None:
            return
        envelope = json.dumps({"origin": self._origin, "kind": kind, "payload": payload})
        # redis-py is a sync client; keep it off the event loop.
        await asyncio.to_thread(self._redis.publish, f"{self._channel_prefix}{room}", envelope)

    def _listen(self, stop_event: threading.Event, out: "queue.Queue") -> None:
        """Runs in a background thread: blocks on Redis pub/sub forever,
        pushing (room, envelope) pairs for the asyncio side to dispatch."""
        pubsub = self._redis.pubsub(ignore_subscribe_messages=True)
        self._pubsub = pubsub
        pubsub.psubscribe(f"{self._channel_prefix}*")
        try:
            for message in pubsub.listen():
                if stop_event.is_set():
                    break
                if message.get("type") != "pmessage":
                    continue
                channel = message["channel"]
                channel = channel.decode() if isinstance(channel, bytes) else channel
                room = channel[len(self._channel_prefix):]
                out.put((room, message["data"]))
        except Exception:  # noqa: BLE001 - stop() closing the connection ends listen()
            pass
        finally:
            try:
                pubsub.close()
            except Exception:  # noqa: BLE001
                pass

    async def _dispatch_loop(self, out: "queue.Queue", stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            try:
                room, raw = await asyncio.to_thread(out.get, True, 1.0)
            except queue.Empty:
                continue
            try:
                data = json.loads(raw)
            except (ValueError, TypeError):
                continue
            if data.get("origin") == self._origin:
                continue  # our own broadcast() already delivered this locally
            await self._broadcast_local(data.get("kind", "text"), data.get("payload"), room)

    async def start(self) -> None:
        """Start the Redis subscriber (no-op without a redis_client). Wire
        this into ``hooks.py``'s ``on_startup``."""
        if self._redis is None or self._listener_thread is not None:
            return
        self._queue = queue.Queue()
        self._stop_event = threading.Event()
        self._listener_thread = threading.Thread(
            target=self._listen, args=(self._stop_event, self._queue), daemon=True
        )
        self._listener_thread.start()
        self._dispatch_task = asyncio.ensure_future(self._dispatch_loop(self._queue, self._stop_event))

    async def stop(self) -> None:
        """Stop the subscriber. Wire this into ``hooks.py``'s ``on_shutdown``."""
        if self._stop_event is not None:
            self._stop_event.set()
        if self._pubsub is not None:
            # unblocks the thread's blocking listen() call
            try:
                await asyncio.to_thread(self._pubsub.close)
            except Exception:  # noqa: BLE001
                pass
        if self._listener_thread is not None:
            await asyncio.to_thread(self._listener_thread.join, 5)
            self._listener_thread = None
            self._pubsub = None
        if self._dispatch_task is not None:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._dispatch_task = None
