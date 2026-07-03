"""gzip response compression middleware."""

from __future__ import annotations

import gzip as _gzip

from endocore.core.middleware import Next
from endocore.core.request import Request
from endocore.core.response import Response


def gzip_middleware(*, minimum_size: int = 500, level: int = 6):
    async def middleware(request: Request, call_next: Next) -> Response:
        response = await call_next(request)
        if not isinstance(response, Response):
            return response  # streaming responses are passed through
        if "gzip" not in request.headers.get("accept-encoding", ""):
            return response
        if len(response.body) < minimum_size:
            return response
        if any(k.lower() == "content-encoding" for k in response.headers):
            return response
        response.body = _gzip.compress(response.body, level)  # __call__ recomputes length
        response.headers["Content-Encoding"] = "gzip"
        response.headers["Vary"] = "Accept-Encoding"
        return response

    return middleware
