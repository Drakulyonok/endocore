"""CORS middleware factory.

    from endocore.middleware import cors_middleware
    # in Middleware/__init__.py:
    middlewares = [cors_middleware(allow_origins=["https://app.example.com"])]
"""

from __future__ import annotations

from endocore.core.middleware import Next
from endocore.core.request import Request
from endocore.core.response import Response

_DEFAULT_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")


def cors_middleware(
    *,
    allow_origins=("*",),
    allow_methods=_DEFAULT_METHODS,
    allow_headers=("*",),
    allow_credentials: bool = False,
    max_age: int = 600,
):
    allow_origins = tuple(allow_origins)
    wildcard = "*" in allow_origins

    def _apply(response: Response, origin: str | None) -> None:
        if origin is None:
            return
        if wildcard and not allow_credentials:
            allowed = "*"
        elif wildcard or origin in allow_origins:
            allowed = origin
        else:
            return
        response.headers["Access-Control-Allow-Origin"] = allowed
        if allowed != "*":
            response.headers["Vary"] = "Origin"
        if allow_credentials:
            response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = ", ".join(allow_methods)
        response.headers["Access-Control-Allow-Headers"] = (
            "*" if "*" in allow_headers else ", ".join(allow_headers)
        )
        response.headers["Access-Control-Max-Age"] = str(max_age)

    async def middleware(request: Request, call_next: Next) -> Response:
        origin = request.headers.get("origin")
        # Preflight: answer directly, don't hit the route.
        if request.method == "OPTIONS" and "access-control-request-method" in request.headers:
            response = Response.no_content()
            _apply(response, origin)
            return response
        response = await call_next(request)
        _apply(response, origin)
        return response

    return middleware
