"""Middleware chain (the onion / ``call_next`` model).

Each middleware is an async callable ``(request, call_next) -> Response``. It may
return an early response (e.g. auth rejection) or await ``call_next(request)`` to
pass control inward. The innermost layer is the endpoint dispatcher.
"""

from __future__ import annotations

from functools import partial
from typing import Awaitable, Callable

from endocore.core.request import Request
from endocore.core.response import Response

#: The next callable in the chain.
Next = Callable[[Request], Awaitable[Response]]
#: A middleware: wraps the next callable.
Middleware = Callable[[Request, Next], Awaitable[Response]]
#: The terminal endpoint dispatcher.
Endpoint = Callable[[Request], Awaitable[Response]]


def build_chain(middlewares: list[Middleware], endpoint: Endpoint) -> Endpoint:
    """Fold ``middlewares`` around ``endpoint`` into a single callable.

    The first middleware in the list becomes the outermost layer.
    """
    handler: Endpoint = endpoint
    for mw in reversed(middlewares):
        # Bind the current inner handler as ``call_next`` for this middleware.
        handler = partial(_invoke, mw, handler)
    return handler


async def _invoke(mw: Middleware, call_next: Endpoint, request: Request) -> Response:
    return await mw(request, call_next)
