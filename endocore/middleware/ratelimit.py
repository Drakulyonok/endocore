"""Fixed-window rate limiter (per client IP): in-memory or Redis-backed.

The in-memory counter is per-process — correct for one process, wrong the
moment you run more than one worker, since each worker enforces its own
independent limit (4 workers effectively multiply the real limit by 4).
Pass a Redis client to share one counter across every worker instead:
``INCR`` is atomic, so concurrent workers can't race each other into
under-counting. Either way, returns 429 (``TooManyRequests``) with how many
seconds until the window resets once the limit is exceeded.
"""

from __future__ import annotations

import asyncio
import time

from endocore.core.exceptions import TooManyRequests
from endocore.core.middleware import Next
from endocore.core.request import Request
from endocore.core.response import Response


def _client_ip(request: Request) -> str:
    client = request.scope.get("client")
    return client[0] if client else "?"


def rate_limit_middleware(
    *, limit: int = 60, window: int = 60, redis_client=None, key_prefix: str = "endocore:ratelimit:"
):
    """Build the middleware. Pass ``redis_client`` (a ``redis.Redis`` — see
    ``endocore.extensions.redis_client`` or ``RedisExtension``) to share the
    limit across every worker process instead of counting per-process."""
    if redis_client is not None:
        return _redis_rate_limit_middleware(limit, window, redis_client, key_prefix)
    return _memory_rate_limit_middleware(limit, window)


def _memory_rate_limit_middleware(limit: int, window: int):
    hits: dict[str, tuple[float, int]] = {}
    last_sweep = 0.0

    async def middleware(request: Request, call_next: Next) -> Response:
        nonlocal last_sweep
        ip = _client_ip(request)
        now = time.monotonic()
        # Sweep expired windows (at most once per window) so the table is bounded.
        if now - last_sweep >= window:
            expired = [key for key, (s, _) in hits.items() if now - s >= window]
            for key in expired:
                del hits[key]
            last_sweep = now
        start, count = hits.get(ip, (now, 0))
        if now - start >= window:
            start, count = now, 0
        count += 1
        hits[ip] = (start, count)
        if count > limit:
            retry = max(1, int(window - (now - start)))
            raise TooManyRequests(f"rate limit exceeded; retry in {retry}s")
        return await call_next(request)

    return middleware


def _redis_rate_limit_middleware(limit: int, window: int, redis_client, key_prefix: str):
    def _hit(key: str) -> tuple[int, int]:
        """INCR the counter (sync redis-py call — see below), set its expiry
        only on the first hit of a fresh window, and return (count, ttl)."""
        count = redis_client.incr(key)
        if count == 1:
            redis_client.expire(key, window)
            ttl = window
        else:
            ttl = redis_client.ttl(key)
        return count, ttl

    async def middleware(request: Request, call_next: Next) -> Response:
        key = f"{key_prefix}{_client_ip(request)}"
        # redis-py is a sync client; offload to a worker thread so a slow or
        # unreachable Redis can't stall the event loop for other requests.
        count, ttl = await asyncio.to_thread(_hit, key)
        if count > limit:
            retry = ttl if ttl and ttl > 0 else window
            raise TooManyRequests(f"rate limit exceeded; retry in {retry}s")
        return await call_next(request)

    return middleware
