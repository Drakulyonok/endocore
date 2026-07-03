"""Security-headers middleware factory.

Adds sensible hardening headers to every response.
"""

from __future__ import annotations

from endocore.core.middleware import Next
from endocore.core.request import Request
from endocore.core.response import Response


def security_headers_middleware(
    *,
    hsts: bool = False,
    frame_options: str = "DENY",
    content_type_options: str = "nosniff",
    referrer_policy: str = "no-referrer",
):
    async def middleware(request: Request, call_next: Next) -> Response:
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", content_type_options)
        headers.setdefault("X-Frame-Options", frame_options)
        headers.setdefault("Referrer-Policy", referrer_policy)
        if hsts:
            headers.setdefault(
                "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
            )
        return response

    return middleware
