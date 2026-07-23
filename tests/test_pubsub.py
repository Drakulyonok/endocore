"""WebSocket pub/sub manager: rooms + broadcast."""

from __future__ import annotations

import asyncio
import threading
import time
from queue import Queue

import pytest

from endocore.core.pubsub import WebSocketManager


class FakeWS:
    def __init__(self, *, fail=False):
        self.accepted = False
        self.sent: list = []
        self.fail = fail

    async def accept(self):
        self.accepted = True

    async def send_text(self, text):
        if self.fail:
            raise RuntimeError("dead")
        self.sent.append(("text", text))

    async def send_json(self, obj):
        if self.fail:
            raise RuntimeError("dead")
        self.sent.append(("json", obj))


def run(coro):
    return asyncio.run(coro)


def test_connect_accepts_and_joins():
    m = WebSocketManager()
    ws = FakeWS()
    run(m.connect(ws, room="lobby"))
    assert ws.accepted
    assert m.count("lobby") == 1


def test_add_without_accept():
    m = WebSocketManager()
    ws = FakeWS()
    ws.accepted = True
    m.add(ws, "r")
    assert m.count("r") == 1


@pytest.mark.parametrize("n", [1, 2, 5])
def test_broadcast(n):
    m = WebSocketManager()
    sockets = [FakeWS() for _ in range(n)]
    for ws in sockets:
        run(m.connect(ws, room="r"))
    run(m.broadcast("hello", room="r"))
    assert all(ws.sent == [("text", "hello")] for ws in sockets)


def test_broadcast_exclude():
    m = WebSocketManager()
    a, b = FakeWS(), FakeWS()
    run(m.connect(a, "r"))
    run(m.connect(b, "r"))
    run(m.broadcast("hi", room="r", exclude=a))
    assert a.sent == [] and b.sent == [("text", "hi")]


def test_broadcast_json():
    m = WebSocketManager()
    ws = FakeWS()
    run(m.connect(ws, "r"))
    run(m.broadcast_json({"k": "v"}, room="r"))
    assert ws.sent == [("json", {"k": "v"})]


def test_disconnect():
    m = WebSocketManager()
    ws = FakeWS()
    run(m.connect(ws, "r"))
    m.disconnect(ws, "r")
    assert m.count("r") == 0


def test_disconnect_all_rooms():
    m = WebSocketManager()
    ws = FakeWS()
    run(m.connect(ws, "a"))
    m.add(ws, "b")
    m.disconnect(ws)
    assert m.count("a") == 0 and m.count("b") == 0


def test_dead_connection_removed_on_broadcast():
    m = WebSocketManager()
    good, bad = FakeWS(), FakeWS(fail=True)
    run(m.connect(good, "r"))
    run(m.connect(bad, "r"))
    run(m.broadcast("x", room="r"))
    assert m.count("r") == 1  # dead one dropped
    assert good.sent == [("text", "x")]


def test_rooms_isolated():
    m = WebSocketManager()
    a, b = FakeWS(), FakeWS()
    run(m.connect(a, "r1"))
    run(m.connect(b, "r2"))
    run(m.broadcast("only-r1", room="r1"))
    assert a.sent and not b.sent


def test_members_and_rooms_of():
    m = WebSocketManager()
    ws = FakeWS()
    run(m.connect(ws, "x"))
    assert ws in m.members("x")
    assert m.rooms_of(ws) == ["x"]


# -- Redis fan-out ------------------------------------------------------------


class FakeBroker:
    """In-process stand-in for a Redis pub/sub channel space, shared by every
    FakeRedisClient built on top of it — mirrors how several worker
    processes actually share one real Redis server."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: list[tuple[str, Queue]] = []

    def publish(self, channel: str, message: str) -> int:
        with self._lock:
            subs = list(self._subscribers)
        n = 0
        for prefix, q in subs:
            if channel.startswith(prefix):
                q.put({"type": "pmessage", "channel": channel, "data": message})
                n += 1
        return n

    def _register(self, prefix: str, q: Queue) -> None:
        with self._lock:
            self._subscribers.append((prefix, q))

    def _unregister(self, q: Queue) -> None:
        with self._lock:
            self._subscribers = [(p, other) for p, other in self._subscribers if other is not q]


class FakePubSub:
    def __init__(self, broker: FakeBroker) -> None:
        self._broker = broker
        self._queue: Queue = Queue()
        self._closed = False

    def psubscribe(self, pattern: str) -> None:
        self._broker._register(pattern.rstrip("*"), self._queue)

    def listen(self):
        while True:
            message = self._queue.get()
            if message is None:
                return
            yield message

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._broker._unregister(self._queue)
        self._queue.put(None)


class FakeRedisClient:
    """Enough of redis-py's pub/sub API for the WebSocketManager fan-out:
    publish/pubsub/psubscribe/listen/close, backed by a shared FakeBroker so
    multiple instances behave like multiple workers on one real server."""

    def __init__(self, broker: FakeBroker) -> None:
        self._broker = broker

    def publish(self, channel: str, message: str) -> int:
        return self._broker.publish(channel, message)

    def pubsub(self, ignore_subscribe_messages: bool = True) -> FakePubSub:
        return FakePubSub(self._broker)


async def _wait_until(predicate, timeout: float = 2.0) -> None:
    """asyncio.sleep, not time.sleep — a blocking sleep here would starve the
    event loop and with it the manager's own dispatch task, which runs on
    that same loop."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.01)
    assert predicate(), "condition never became true"


def test_fanout_delivers_to_a_second_process_room():
    broker = FakeBroker()
    a = WebSocketManager(redis_client=FakeRedisClient(broker))
    b = WebSocketManager(redis_client=FakeRedisClient(broker))

    ws_a, ws_b = FakeWS(), FakeWS()
    run(a.connect(ws_a, "lobby"))
    run(b.connect(ws_b, "lobby"))

    async def scenario():
        await a.start()
        await b.start()
        try:
            await a.broadcast("hi", room="lobby")
            await _wait_until(lambda: ws_b.sent == [("text", "hi")])
            # local delivery on the publishing side happens directly, not via Redis
            assert ws_a.sent == [("text", "hi")]
        finally:
            await a.stop()
            await b.stop()

    run(scenario())


def test_fanout_does_not_double_deliver_to_the_publisher_itself():
    broker = FakeBroker()
    a = WebSocketManager(redis_client=FakeRedisClient(broker))
    ws_a = FakeWS()
    run(a.connect(ws_a, "lobby"))

    async def scenario():
        await a.start()
        try:
            await a.broadcast("hi", room="lobby")
            await asyncio.sleep(0.2)  # give a stray echo a chance to arrive
            assert ws_a.sent == [("text", "hi")]
        finally:
            await a.stop()

    run(scenario())


def test_fanout_json_and_room_isolation():
    broker = FakeBroker()
    a = WebSocketManager(redis_client=FakeRedisClient(broker))
    b = WebSocketManager(redis_client=FakeRedisClient(broker))

    ws_b_lobby, ws_b_other = FakeWS(), FakeWS()
    run(b.connect(ws_b_lobby, "lobby"))
    run(b.connect(ws_b_other, "other"))

    async def scenario():
        await a.start()
        await b.start()
        try:
            await a.broadcast_json({"k": "v"}, room="lobby")
            await _wait_until(lambda: ws_b_lobby.sent == [("json", {"k": "v"})])
            assert ws_b_other.sent == []
        finally:
            await a.stop()
            await b.stop()

    run(scenario())


def test_without_redis_client_start_and_stop_are_noops():
    m = WebSocketManager()

    async def scenario():
        await m.start()
        await m.stop()

    run(scenario())  # must not raise
