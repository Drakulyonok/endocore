"""Request-timeout middleware: abort slow requests with 504."""

from __future__ import annotations

import asyncio

from endocore.core.exceptions import HTTPError
from endocore.core.middleware import Next
from endocore.core.request import Request
from endocore.core.response import Response


def timeout_middleware(*, seconds: float = 30.0):
    async def middleware(request: Request, call_next: Next) -> Response:
        try:
            return await asyncio.wait_for(call_next(request), timeout=seconds)
        except asyncio.TimeoutError:
            raise HTTPError(504, "Gateway Timeout") from None

    return middleware
