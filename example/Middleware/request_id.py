"""Example middleware: attach a request id and expose it on the response.

Shows the middleware contract without blocking access: it enriches the request
(``scope["request_id"]``) and adds an ``X-Request-ID`` response header.
"""

from uuid import uuid4

from endocore import Request, Response


async def request_id_middleware(request: Request, call_next) -> Response:
    request_id = request.headers.get("x-request-id") or uuid4().hex
    request.scope["request_id"] = request_id

    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response
