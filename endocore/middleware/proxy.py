"""Trusted-proxy middleware: honour X-Forwarded-* only from trusted clients."""

from __future__ import annotations

from endocore.core.middleware import Next
from endocore.core.request import Request
from endocore.core.response import Response


def proxy_headers_middleware(*, trusted=("127.0.0.1", "::1")):
    trusted = set(trusted)

    async def middleware(request: Request, call_next: Next) -> Response:
        client = request.scope.get("client")
        host = client[0] if client else None
        if host in trusted or "*" in trusted:
            proto = request.headers.get("x-forwarded-proto")
            if proto:
                request.scope["scheme"] = proto.split(",")[0].strip()
            forwarded_for = request.headers.get("x-forwarded-for")
            if forwarded_for:
                request.scope["client"] = (forwarded_for.split(",")[0].strip(), 0)
            forwarded_host = request.headers.get("x-forwarded-host")
            if forwarded_host:
                request.headers["host"] = forwarded_host
        return await call_next(request)

    return middleware
