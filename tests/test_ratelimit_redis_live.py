"""Redis-backed rate limiter against a real Redis server.

Skipped unless ``ENDOCORE_TEST_REDIS_URL`` is set, e.g.::

    ENDOCORE_TEST_REDIS_URL=redis://localhost:6379/0

The in-process fakes in test_middleware_bundle.py prove the middleware's own
logic; this is the one that actually matters before trusting a Redis-backed
limit across real worker processes — many concurrent requests racing a
single real INCR must never let more than ``limit`` through.
"""

from __future__ import annotations

import os
import threading

import pytest

DSN = os.environ.get("ENDOCORE_TEST_REDIS_URL")

pytestmark = pytest.mark.skipif(
    not DSN, reason="set ENDOCORE_TEST_REDIS_URL to run the live Redis rate-limit test"
)
if DSN:
    pytest.importorskip("redis")

from endocore.core.middleware import build_chain  # noqa: E402
from endocore.core.request import Request  # noqa: E402
from endocore.core.response import Response  # noqa: E402
from endocore.middleware import rate_limit_middleware  # noqa: E402
from endocore.middleware.logging import logging_middleware  # noqa: E402


def _drive(pipeline, ip: str) -> int:
    import asyncio

    scope = {
        "type": "http", "method": "GET", "path": "/", "query_string": b"",
        "headers": [], "client": (ip, 0),
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def go():
        request = Request(scope, receive)
        response = await pipeline(request)
        return response.status

    return asyncio.run(go())


@pytest.fixture()
def redis_client():
    import redis

    client = redis.Redis.from_url(DSN)
    client.flushdb()
    yield client
    client.flushdb()
    client.close()


def test_concurrent_requests_never_exceed_the_shared_limit(redis_client):
    limit, attempts = 5, 20
    key_prefix = "endocore:test:live-ratelimit:"

    async def endpoint(request):
        return Response.json({"ok": True})

    # Two independent middleware instances share the same Redis client and
    # key prefix — standing in for two separate worker processes.
    workers = [
        build_chain(
            [logging_middleware, rate_limit_middleware(
                limit=limit, window=60, redis_client=redis_client, key_prefix=key_prefix
            )],
            endpoint,
        )
        for _ in range(4)
    ]

    barrier = threading.Barrier(attempts, timeout=10)
    statuses: list[int] = []
    lock = threading.Lock()

    def attempt(i: int):
        barrier.wait()
        pipeline = workers[i % len(workers)]
        status = _drive(pipeline, "203.0.113.7")  # same client IP for all
        with lock:
            statuses.append(status)

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(attempts)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)

    assert sorted(statuses) == [200] * limit + [429] * (attempts - limit), statuses
