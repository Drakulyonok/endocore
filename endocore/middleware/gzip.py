"""gzip response compression middleware.

Compressing a response that mixes a secret (a CSRF token, a session id) with
attacker-influenced reflected input (an echoed query param) is the BREACH
compression-oracle pattern — response size leaks information about the
secret across repeated requests. Not something this middleware can detect or
fix generically; keep secrets and reflected input out of the same response,
or don't compress pages that embed one.
"""

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
