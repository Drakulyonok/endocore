"""WebSocketManager's Redis fan-out against a real Redis server.

Skipped unless ``ENDOCORE_TEST_REDIS_URL`` is set, e.g.::

    ENDOCORE_TEST_REDIS_URL=redis://localhost:6379/0

The fakes in test_pubsub.py prove the origin-tagging/dispatch logic; this is
the one that matters before trusting a real redis-py pub/sub connection —
psubscribe/listen/close behave a little differently from the in-memory fake,
and this is what catches it.
"""

from __future__ import annotations

import asyncio
import os

import pytest

DSN = os.environ.get("ENDOCORE_TEST_REDIS_URL")

pytestmark = pytest.mark.skipif(
    not DSN, reason="set ENDOCORE_TEST_REDIS_URL to run the live Redis pub/sub test"
)
if DSN:
    pytest.importorskip("redis")

from endocore.core.pubsub import WebSocketManager  # noqa: E402


class FakeWS:
    def __init__(self) -> None:
        self.accepted = False
        self.sent: list = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_text(self, text: str) -> None:
        self.sent.append(("text", text))

    async def send_json(self, obj) -> None:
        self.sent.append(("json", obj))


@pytest.fixture()
def redis_client():
    import redis

    client = redis.Redis.from_url(DSN)
    yield client
    client.close()


async def _wait_until(predicate, timeout: float = 5.0) -> None:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.05)
    assert predicate(), "condition never became true"


def test_broadcast_reaches_a_second_manager_over_real_redis(redis_client):
    import redis

    prefix = "endocore:test:live-pubsub:"
    a = WebSocketManager(redis_client=redis.Redis.from_url(DSN), channel_prefix=prefix)
    b = WebSocketManager(redis_client=redis.Redis.from_url(DSN), channel_prefix=prefix)

    ws_a, ws_b = FakeWS(), FakeWS()

    async def scenario():
        await a.connect(ws_a, "lobby")
        await b.connect(ws_b, "lobby")
        await a.start()
        await b.start()
        try:
            await a.broadcast("hi", room="lobby")
            await _wait_until(lambda: ws_b.sent == [("text", "hi")])
            assert ws_a.sent == [("text", "hi")]  # delivered locally, not via the echo path
        finally:
            await a.stop()
            await b.stop()

    asyncio.run(scenario())
