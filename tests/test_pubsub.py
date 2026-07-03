"""WebSocket pub/sub manager: rooms + broadcast."""

from __future__ import annotations

import asyncio

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
