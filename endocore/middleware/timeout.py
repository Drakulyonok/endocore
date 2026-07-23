"""Request-timeout middleware: abort slow requests with 504.

Only actually stops an *async* handler — cancellation reaches its next
``await``. A sync handler runs in a worker thread (``asyncio.to_thread``);
Python cannot forcibly kill a running thread, so it keeps running to
completion in the shared thread pool even after the client gets its 504.
Enough slow sync handlers can still exhaust that pool and stall unrelated
requests — bound the actual work too (a DB statement timeout, an HTTP client
timeout), don't rely on this alone for anything sync.
"""

from __future__ import annotations

import asyncio

from endocore.core.exceptions import HTTPError
from endocore.core.logging import get_logger
from endocore.core.middleware import Next
from endocore.core.request import Request
from endocore.core.response import Response

_logger = get_logger()


def timeout_middleware(*, seconds: float = 30.0):
    async def middleware(request: Request, call_next: Next) -> Response:
        try:
            return await asyncio.wait_for(call_next(request), timeout=seconds)
        except asyncio.TimeoutError:
            _logger.warning(
                "%s %s timed out after %ss (a sync handler keeps running in its "
                "worker thread regardless — see timeout_middleware's docstring)",
                request.method, request.path, seconds,
            )
            raise HTTPError(504, "Gateway Timeout") from None

    return middleware
