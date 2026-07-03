"""Simple in-memory fixed-window rate limiter (per client IP).

In-process only (not shared across workers) — enough for a single-process dev/
small deployment. Returns 429 with a ``Retry-After`` header when exceeded.
"""

from __future__ import annotations

import time

from endocore.core.exceptions import TooManyRequests
from endocore.core.middleware import Next
from endocore.core.request import Request
from endocore.core.response import Response


def rate_limit_middleware(*, limit: int = 60, window: int = 60):
    hits: dict[str, tuple[float, int]] = {}

    async def middleware(request: Request, call_next: Next) -> Response:
        client = request.scope.get("client")
        ip = client[0] if client else "?"
        now = time.monotonic()
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
